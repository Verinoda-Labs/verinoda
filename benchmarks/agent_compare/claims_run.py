"""Run the false-claims study (DESIGN_CLAIMS.md): one headless Claude Code session per task, arm and repeat, each asked a
why / when / what-it-affects question about a pinned real-world repository; the session's final answer is what is scored.

    python benchmarks/agent_compare/claims_run.py CONFIG.json [--pilot] [--tasks id,id] [--repeats N] [--arms a,b]

CONFIG: {"work": WORK_DIR, "model": "claude-sonnet-5-5", "plugin_dir": the mod, "mod_options": {"auto": "nudge"},
"verinoda_bin": [dirs put on PATH in the Verinoda arm], "drop_path": [dirs taken off PATH], "arms": ["none", "verinoda_guided"],
"arm_workers": {arm: n}, "timeout_s": s, "max_turns": n, "repeats": 3, "pilot": bool, "only": [task ids] (optional),
"guide_text": the Verinoda arm's paragraph in place of GUIDE (optional; the D186 re-runs)}.
``--pilot`` (or ``"pilot": true``) runs the first 8 tasks of the fixed order once per arm. Layout: ``WORK/clones/<owner>__<name>``
(full clones), ``WORK/copies/<task>/<arm>/r<repeat>`` (shared clones, one per session), ``WORK/usage/`` (the Verinoda arm's
per-call usage logs, D178), ``WORK/results.jsonl`` (one row per session; resumable on task, arm and repeat).
"""

from __future__ import annotations

import contextlib
import json
import shutil
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from big_run import isolated_plugin_store, run_by_arm, session_stats
from claims_tasks import REPO_ROOT, TAG_OF, load_tasks, order
from claims_tasks import copy_dir as _copy_dir
from guard_run import _force_remove, find_transcript, git_env, run
from swebench_prepare import setup_verinoda
from swebench_run import claude_exe, env_for, verinoda_tools

# Both paragraphs are the spec's, word for word (the test compares them to DESIGN_CLAIMS.md). The stance goes to both arms,
# so that the only difference between the arms is the tool; the guide is the 2026-10-11 amendment's paragraph.
STANCE = ("Answer the question below about this repository. Every factual statement you make must carry its evidence: a "
          "`path:line` of this checkout, a commit's short hash, or both. When you infer something you did not see, mark the "
          "statement as an inference (\"likely\", \"it appears\") rather than stating it as a fact. When the repository does not "
          "hold the answer, say so plainly (\"unknown\") and say what you looked for; do not guess. Do not use the network. "
          "Answer in English, as a short list of statements, each with its evidence.")
GUIDE = ("Load the Verinoda tools first: call ToolSearch with the query "
         "`select:mcp__verinoda__analyze,mcp__verinoda__project_query,mcp__verinoda__run_tool`. Then use them before Grep, Glob, "
         "Read or a shell search: `analyze` with the question; for a question about when or why something changed, `run_tool` "
         "with `history_search`; for a question about what a change would affect, `run_tool` with `change_review` or the "
         "`impact` view. Verinoda answers with claims that carry a status: state as fact only what it marks "
         "`statically_verified` or what you confirmed yourself in the files; report its `unknown`s as unknown.")
PLAIN, GUIDED = "none", "verinoda_guided"
PILOT_N = 8


def prompt_for(task: dict, copy: Path, arm: str, cfg: dict | None = None) -> str:
    """The session's prompt: both arms get the stance; the Verinoda arm gets the guide too - the study's paragraph, or the
    text ``cfg["guide_text"]`` names (the D186 re-runs give the one status rule instead; GUIDE stays what the first run used)."""
    text = f"Repository: {task['repo']} at {copy.as_posix()}.\n\nQuestion: {task['question']}\n\n{STANCE}"
    guide = cfg["guide_text"] if cfg and "guide_text" in cfg else GUIDE   # "" : no guide; the mod's own section speaks
    return f"{text}\n\n{guide}" if arm == GUIDED and guide else text


def apply_flags(cfg: dict, argv: list[str]) -> dict:
    """The command line's choices over the config: ``--pilot``, ``--tasks id,id`` (the ``only`` filter), ``--repeats N``,
    ``--arms a,b``. Returns the same dict, updated."""
    if "--pilot" in argv:
        cfg["pilot"] = True
    if "--tasks" in argv:
        cfg["only"] = [x for x in argv[argv.index("--tasks") + 1].split(",") if x]
    if "--repeats" in argv:
        cfg["repeats"] = int(argv[argv.index("--repeats") + 1])
    if "--arms" in argv:
        cfg["arms"] = [x for x in argv[argv.index("--arms") + 1].split(",") if x]
    return cfg


def tools_for(arm: str) -> str:
    return "Bash Read Glob Grep" + (" mcp__verinoda" if arm == GUIDED else "")


def session_argv(prompt: str, arm: str, copy: Path, cfg: dict) -> list[str]:
    argv = [claude_exe(cfg), "-p", prompt, "--output-format", "json", "--model", cfg["model"], "--setting-sources", "project,local",
            "--strict-mcp-config", "--allowedTools", tools_for(arm), "--max-turns", str(cfg.get("max_turns", 40)),
            "--permission-mode", "default"]
    if cfg.get("max_budget_usd"):
        argv += ["--max-budget-usd", str(cfg["max_budget_usd"])]
    if arm == GUIDED:
        argv += ["--mcp-config", str(copy / ".mcp.json"), "--plugin-dir", cfg["plugin_dir"], "--settings",
                 json.dumps({"pluginConfigs": {"verinoda-live": {"options": cfg.get("mod_options", {"auto": "nudge"})}}})]
    return argv


def _git(argv: list[str], cwd: Path, timeout: int = 1800) -> str:
    rc, out, err, _ = run(["git", *argv], cwd, git_env(), timeout=timeout)
    if rc != 0:
        raise RuntimeError(f"git {' '.join(argv)} in {cwd}: {err[-400:]}")
    return out


def _clean_at(dest: Path, sha: str) -> bool:
    """Is ``dest`` a clean checkout at ``sha``? (A killed run may have left a half-made or dirty one.)"""
    if not (dest / ".git").exists():
        return False
    rc, head, _, _ = run(["git", "rev-parse", "HEAD"], dest, git_env())
    _, dirty, _, _ = run(["git", "status", "--porcelain", "--untracked-files=no"], dest, git_env())
    return rc == 0 and head.strip() == sha and not dirty.strip()


def clone_argv(repo: str, tag: str, dest: Path) -> list[str]:
    """Only the tag's own history: a clone of every branch and tag would carry commits past the sha, and an agent's
    `git log --all` could cite a later commit whose message answers what the repository at the sha does not (a true
    trap wrongly reclassified). Full depth, one branch, no other tags."""
    return ["clone", "-q", "--no-checkout", "--single-branch", "--no-tags", "--branch", tag, "-c", "core.autocrlf=false",
            "-c", "core.longpaths=true", f"https://github.com/{repo}.git", dest.as_posix()]


def clone_full(repo: str, sha: str, dest: Path, tag: str) -> None:
    """A full-depth clone of the pinned tag, checked out detached at the pinned sha, which the tag must resolve to. The
    real-world run's clones were one commit deep; those answer no when-question. A shallow result is refused."""
    if _clean_at(dest, sha):
        return
    if dest.exists():
        shutil.rmtree(dest, onerror=_force_remove)
    dest.parent.mkdir(parents=True, exist_ok=True)
    _git(clone_argv(repo, tag, dest), dest.parent, timeout=3600)
    if _git(["rev-parse", f"{tag}^{{commit}}"], dest).strip() != sha:
        raise RuntimeError(f"{repo}: tag {tag} does not resolve to {sha}")
    _git(["checkout", "-q", "--detach", sha], dest)
    if (dest / ".git" / "shallow").exists():
        raise RuntimeError(f"shallow clone at {dest}")


def copy_for(clone: Path, dest: Path, sha: str) -> None:
    """One session's working copy: a shared clone of the full clone (the objects stay in one place), detached at the sha."""
    if _clean_at(dest, sha):
        return
    if dest.exists():
        shutil.rmtree(dest, onerror=_force_remove)
    dest.parent.mkdir(parents=True, exist_ok=True)
    _git(["clone", "-q", "--shared", "--no-checkout", "-c", "core.autocrlf=false", "-c", "core.longpaths=true",
          clone.as_posix(), dest.as_posix()], dest.parent)
    _git(["checkout", "-q", "--detach", sha], dest)


def plan(tasks: list[dict], cfg: dict, done: set) -> list[tuple[dict, str, int]]:
    """The (task, arm, repeat) items still to run: task-major in the fixed order, then the arms, then the repeats, so a
    task's arms sit side by side and start together. The pilot is the first 8 of the order, once."""
    by_id = {t["id"]: t for t in tasks}
    ids = order(list(by_id))
    if cfg.get("only"):
        ids = [i for i in ids if i in set(cfg["only"])]
    repeats = 1 if cfg.get("pilot") else int(cfg.get("repeats", 3))
    if cfg.get("pilot"):
        ids = ids[:PILOT_N]
    return [(by_id[i], arm, r) for i in ids for arm in cfg["arms"] for r in range(1, repeats + 1) if (i, arm, r) not in done]


def copy_dir(work: Path, task: dict, arm: str, repeat: int) -> Path:
    return _copy_dir(work, task["id"], arm, repeat)


_CLAUDE_VERSION: str | None = None


def cli_version(cfg: dict) -> str:
    """`claude --version` through the resolved executable (big_run.claude_version runs the bare name, which on Windows is an
    npm shim a subprocess cannot start: every row of the first run said "unknown")."""
    global _CLAUDE_VERSION
    if _CLAUDE_VERSION is None:
        rc, out, _, _ = run([claude_exe(cfg), "--version"], Path.cwd(), git_env(), timeout=60)
        _CLAUDE_VERSION = out.strip() if rc == 0 and out.strip() else "unknown"
    return _CLAUDE_VERSION


def one(cfg: dict, task: dict, arm: str, repeat: int) -> dict:
    work = Path(cfg["work"])
    clone = work / "clones" / task["repo"].replace("/", "__")
    copy = copy_dir(work, task, arm, repeat)
    copy_for(clone, copy, task["sha"])
    setup = setup_verinoda(copy) if arm == GUIDED else {}
    env = env_for(arm, cfg)
    usage_log = work / "usage" / f"{task['id']}-{arm}-r{repeat}.jsonl"
    if arm == GUIDED:
        usage_log.parent.mkdir(parents=True, exist_ok=True)
        env["VERINODA_USAGE_LOG"] = str(usage_log)
    rc, out, err, secs = run(session_argv(prompt_for(task, copy, arm, cfg), arm, copy, cfg), copy, env,
                             timeout=cfg.get("timeout_s", 1200))
    try:
        rep = json.loads(out)
    except ValueError:
        rep = {"is_error": True, "result": (out or err)[-500:]}
    transcript = find_transcript(rep.get("session_id", ""))
    st = session_stats(transcript)
    usage = rep.get("usage") or {}
    return {"id": task["id"], "arm": arm, "repeat": repeat, "pilot": bool(cfg.get("pilot")), "kind": task["kind"],
            "model": cfg["model"], "claude": cli_version(cfg), "exit": rc, "seconds": secs, "is_error": bool(rep.get("is_error")),
            "subtype": rep.get("subtype"), "session_id": rep.get("session_id"), "num_turns": rep.get("num_turns"),
            "cost_usd": rep.get("total_cost_usd"),
            "input_tokens": sum(int(usage.get(k) or 0) for k in ("input_tokens", "cache_creation_input_tokens",
                                                                 "cache_read_input_tokens")),
            "output_tokens": int(usage.get("output_tokens") or 0), "answer": rep.get("result") or "",
            "tool_calls": st["tool_calls"], "verinoda_calls": st["verinoda_calls"], "verinoda_tools": verinoda_tools(transcript),
            "network": st["network"],
            "usage_log_lines": len(usage_log.read_text(encoding="utf-8").splitlines()) if usage_log.is_file() else 0,
            "setup_seconds": setup.get("setup_seconds")}


def main() -> int:
    cfg = apply_flags(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")), sys.argv[2:])
    work = Path(cfg["work"])
    work.mkdir(parents=True, exist_ok=True)
    tasks = load_tasks(REPO_ROOT / "benchmarks" / "agent_compare" / "claims_tasks.json")
    (work / "tasks.json").write_text(json.dumps({"tasks": tasks}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    out = work / "results.jsonl"
    done = set()
    if out.exists():
        done = {(r["id"], r["arm"], r["repeat"]) for r in map(json.loads, out.read_text(encoding="utf-8").splitlines()) if r}
    todo = plan(tasks, cfg, done)
    for repo, sha in sorted({(t["repo"], t["sha"]) for t, _, _ in todo}):
        print(f"clone {repo}", flush=True)
        clone_full(repo, sha, work / "clones" / repo.replace("/", "__"), TAG_OF[repo])
    lock = threading.Lock()
    print(f"{len(todo)} sessions to run ({len(done)} done)", flush=True)

    def work_item(item):
        t, a, r = item
        row = one(cfg, t, a, r)
        with lock, out.open("ab") as f:
            f.write((json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8"))
        print(f"{time.strftime('%H:%M:%S')} {t['id']}:{a}:r{r} answer={len(row['answer'])} chars verinoda_calls={row['verinoda_calls']} "
              f"turns={row['num_turns']} ${row['cost_usd']} {row['seconds']} s{' ERROR' if row['is_error'] else ''}", flush=True)

    with isolated_plugin_store() if GUIDED in cfg["arms"] else contextlib.nullcontext():
        for item, err in run_by_arm(todo, cfg.get("arm_workers", {}), work_item, 2):
            print(f"FAILED {item[0]['id']}:{item[1]}:r{item[2]} {err}", flush=True)
    print("all done", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
