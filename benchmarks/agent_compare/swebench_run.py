"""Run the SWE-bench Lite study (DESIGN_SWEBENCH.md): one headless Claude Code session per instance and arm, each asked to
fix the issue; the session's patch is what ``git diff`` shows afterwards.

    python benchmarks/agent_compare/swebench_run.py CONFIG.json

CONFIG: {"work": swebench_prepare's WORK_DIR, "model": "claude-sonnet-5-5", "plugin_dir": the mod, "mod_options": {"auto": "nudge"},
"verinoda_bin": [dirs put on PATH in the verinoda arm], "drop_path": [dirs taken off PATH], "arms": ["none", "verinoda_guided"],
"arm_workers": {arm: n}, "timeout_s": s, "max_turns": n, "max_budget_usd": per session, "only": [instance ids] (optional)}.
Resumable: an instance and arm already in ``results.jsonl`` is skipped. Writes ``predictions-<arm>.jsonl`` (SWE-bench format).

Optional (DESIGN_SWEBENCH_CEILING.md): "tasks": tasks.json elsewhere and "out": the folder for results and predictions, both
outside the sessions' folder tree; "env_data": swebench_localeval's DATA folder, which gives every session, in both arms, the
instance's Python environment (its venv first on PATH, the checkout importable) and the prompt that asks it to reproduce the
issue and run the related tests (condition C1); "env_only": [instance ids], when given, limits that to the instances whose gold
patch passes in the local environment, the others getting the plain prompt (amendment 2).
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from big_run import claude_version, isolated_plugin_store, run_by_arm, session_stats
from guard_run import find_transcript, git_env, run
from swebench_localeval import COMPILED, copy_outputs, write_generated

GUIDE = (
    "This repository has Verinoda installed and indexed. Work in this order. (1) Load its tools first: call ToolSearch with the "
    "query `select:mcp__verinoda__analyze,mcp__verinoda__project_query,mcp__verinoda__code_check`. (2) Before you use Grep, Glob or "
    "Read on the code, call `mcp__verinoda__analyze` with the problem above (the symptom in your own words) to find the code "
    "that matters, with file:line evidence; `mcp__verinoda__project_query` finds more. Its hits are leads, not proof: read the "
    "code before you change it. (3) After you edit Python files, call `mcp__verinoda__code_check` on the files you changed, "
    "and fix what it reports as absent. You may use any other tool as well."
)
# C1: the prompt already orders the work (reproduce, fix, run the script and the tests); GUIDE's own order ended at
# code_check, the shortcut D184's transcripts show (analyze, edit, code_check, done), so here Verinoda joins those steps
GUIDE_C1 = (
    "This repository also has Verinoda installed and indexed; use it within the steps above, not instead of any of them. Load "
    "its tools first: call ToolSearch with the query "
    "`select:mcp__verinoda__analyze,mcp__verinoda__project_query,mcp__verinoda__code_check`. Before you use Grep, Glob or Read on "
    "the code, call `mcp__verinoda__analyze` with the problem above (the symptom in your own words) to find the code that "
    "matters, with file:line evidence; `mcp__verinoda__project_query` finds more. Its hits are leads, not proof: read the code "
    "before you change it. After you edit Python files, call `mcp__verinoda__code_check` on the files you changed and fix what "
    "it reports as absent; it does not replace running your reproduction script and the tests."
)
EXCLUDES =[":(exclude).verinoda", ":(exclude).claude", ":(exclude).mcp.json", ":(exclude).scratch"]
# the repositories whose tests import the checkout through PYTHONPATH in the evaluator too; every session imports its
# checkout through PYTHONPATH, from src/ in a src-layout project
PYTHONPATH_REPOS = {"django/django", "sympy/sympy", "psf/requests"}
SRC_LAYOUT = {"pytest-dev/pytest", "pallets/flask"}
TEST_HINTS = {
    "django/django": "Run Django's tests from the repository root with `python tests/runtests.py <app_label or test module> "
                     "--settings=test_sqlite --parallel 1` (for example `python tests/runtests.py admin_checks "
                     "--settings=test_sqlite --parallel 1`).",
    "sympy/sympy": "Run a test file from the repository root with `python bin/test <path to test file>` (add `-k <name>` to pick "
                   "tests).",
}


def prompt_for(task: dict, copy: Path, arm: str, with_env: bool = False) -> str:
    if with_env:
        hint = TEST_HINTS.get(task["repo"], "Run tests from the repository root with `python -m pytest <path> -q`.")
        scratch = (copy / ".scratch").as_posix()
        text = (f"You are working in the {task['repo']} repository at {copy.as_posix()} (a git checkout of the project at this "
                "point of its history). Its Python environment is ready: `python` is the project's interpreter with its "
                "dependencies installed, and the repository's code is importable. A user filed this issue:\n\n"
                f"{task['problem_statement']}\n\n"
                "Task: fix the issue by editing the repository's source code in place. Work in this order: reproduce the issue "
                f"with a short script in {scratch}/ (create the folder) that fails (an assert, a non-zero exit) while the issue "
                "is present and passes once it is fixed; fix it; run your script again, then run the project's "
                f"existing tests for the code you changed and fix anything you broke. {hint} Do not modify or add test files "
                "in the repository, do not use the network or look the issue up on the web or on GitHub, and work only in "
                f"{copy.as_posix()}. When you are done, reply with one sentence on what you changed.")
    else:
        text = (f"You are working in the {task['repo']} repository at {copy.as_posix()} (a git checkout; its dependencies are "
                "not installed, so the project's tests may not run). A user filed this issue:\n\n"
                f"{task['problem_statement']}\n\n"
                "Task: fix the issue by editing the repository's source code in place. Do not modify or add test files, do not "
                "use the network or look the issue up on the web or on GitHub, and work only in "
                f"{copy.as_posix()}. When you are done, reply with one sentence on what you changed.")
    if arm != "verinoda_guided":
        return text
    return f"{text}\n\n{GUIDE_C1 if with_env else GUIDE}"


def claude_exe(cfg: dict) -> str:
    """The `claude` program: ``cfg["claude"]``, else the first ``claude.exe`` of an npm install next to a `claude` on PATH, else
    the name (Windows cannot start an npm ``.cmd`` shim without a shell, which would mangle the prompt)."""
    import shutil

    if cfg.get("claude"):
        return cfg["claude"]
    found = shutil.which("claude")
    if found:
        npm = Path(found).parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
        return str(npm) if npm.is_file() else found
    return "claude"


def tools_for(arm: str) -> str:
    return "Bash Read Glob Grep Edit Write" + (" mcp__verinoda" if arm == "verinoda_guided" else "")


def session_argv(prompt: str, arm: str, copy: Path, cfg: dict) -> list[str]:
    argv = [claude_exe(cfg), "-p", prompt, "--output-format", "json", "--model", cfg["model"], "--setting-sources", "project,local",
            "--strict-mcp-config", "--allowedTools", tools_for(arm), "--max-turns", str(cfg.get("max_turns", 100)),
            "--permission-mode", "acceptEdits"]
    if cfg.get("max_budget_usd"):
        argv += ["--max-budget-usd", str(cfg["max_budget_usd"])]
    if arm == "verinoda_guided":
        argv += ["--mcp-config", str(copy / ".mcp.json"), "--plugin-dir", cfg["plugin_dir"], "--settings",
                 json.dumps({"pluginConfigs": {"verinoda-live": {"options": cfg.get("mod_options", {"auto": "nudge"})}}})]
    return argv


def env_for(arm: str, cfg: dict, venv: Path | None = None, pythonpath: Path | None = None) -> dict:
    env = git_env()
    drop = [d.lower().replace("/", "\\") for d in cfg.get("drop_path", [])]
    keep = [p for p in env.get("PATH", "").split(os.pathsep) if p.lower().replace("/", "\\").rstrip("\\") not in drop]
    # the project's venv comes first, so that `python` is the project's interpreter and not Verinoda's (also on PATH)
    first = [str(venv / "Scripts")] if venv is not None else []
    env["PATH"] = os.pathsep.join([*first, *(cfg.get("verinoda_bin", []) if arm == "verinoda_guided" else []), *keep])
    for k in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        env.pop(k, None)
    if venv is not None:
        env.update({"VIRTUAL_ENV": str(venv), "PYTHONIOENCODING": "utf-8"})
    if pythonpath is not None:
        env["PYTHONPATH"] = str(pythonpath)
    return env


def scm_env(task: dict) -> dict:
    return {"SETUPTOOLS_SCM_PRETEND_VERSION": f"{task['version']}.0"}


def session_venv(task: dict, copy: Path, arm: str, data: Path) -> tuple[Path, Path]:
    """The venv a session runs the project's code with, and its PYTHONPATH (the checkout's import folder): the instance's
    shared environment, or a venv of the session's own made from it (uv's cache makes it quick)."""
    from swebench_envspec import env_key, parse

    spec = parse(data / "tasks" / task["id"] / "Dockerfile")
    shared = data / "envs" / env_key(spec)
    if task["repo"] in COMPILED:
        # the evaluator's build of this instance's base commit (swebench_localeval.build_outputs): its outputs make the copy
        # importable without a build of its own, which takes minutes
        marker = data / "build" / f"{task['id']}.json"
        if marker.exists():
            copy_outputs({**json.loads(marker.read_text(encoding="utf-8")), "root": data / "build" / task["id"]}, copy)
        return shared, copy / COMPILED[task["repo"]]
    root = copy / "src" if task["repo"] in SRC_LAYOUT else copy
    if task["repo"] in PYTHONPATH_REPOS or spec["python"].startswith("3.6"):
        return shared, root
    # the evaluator installs this project into the shared environment, whose editable install then points at its checkout
    # (with a patch and the test patch while it runs): a session gets a venv of its own instead, holding the shared one's
    # packages as the gold patch's evaluation left them (the project's own dependencies included) and no install of the project
    own = copy.parent / f"env-{arm}"
    if not (own / "verinoda-env.json").exists():
        if own.exists():
            shutil.rmtree(own, ignore_errors=True)
        mm = ".".join(spec["python"].split(".")[:2])
        subprocess.run(["uv", "venv", "-q", "--seed", "-p", mm, str(own)], check=True, capture_output=True)
        py = str(own / "Scripts" / "python.exe")
        frozen = subprocess.run(["uv", "pip", "freeze", "-q", "--exclude-editable", "--python",
                                 str(shared / "Scripts" / "python.exe")], capture_output=True, check=True).stdout
        reqs = own / "requirements.txt"
        reqs.write_bytes(frozen)
        subprocess.run(["uv", "pip", "install", "-q", "--python", py, "--no-deps", "-r", str(reqs)], capture_output=True,
                       check=False)
        (own / "verinoda-env.json").write_text(json.dumps({"from": str(shared), "packages": frozen.count(b"\n")}),
                                               encoding="utf-8")
    return own, root


def patch_of(copy: Path, base: str, test_files: list[str]) -> tuple[str, list[str]]:
    """The session's change as one diff against the base commit: new files included, Verinoda's own files and the files the
    instance's test patch changes left out (the evaluation applies that patch over the model's)."""
    env = git_env()
    skip = [f":(exclude){f}" for f in test_files]
    subprocess.run(["git", "-C", str(copy), "add", "-A", "--", ".", *EXCLUDES, *skip], env=env, check=False,
                   capture_output=True)
    # bytes, not text: text mode would turn a CRLF in a file's lines into LF and the patch would no longer apply
    diff = subprocess.run(["git", "-C", str(copy), "diff", "--cached", "--no-color", base, "--", ".", *EXCLUDES, *skip],
                          env=env, capture_output=True, check=False).stdout.decode("utf-8", errors="replace")
    touched_tests = sorted(f for f in test_files if subprocess.run(
        ["git", "-C", str(copy), "diff", "--cached", "--quiet", base, "--", f], env=env, check=False).returncode == 1)
    return diff, touched_tests


def applies(diff: str, copy: Path, base: str) -> bool:
    """Does the patch apply to the base commit? Checked against a throwaway index holding the base tree, so what the
    session did to the working copy does not matter."""
    if not diff.strip():
        return False
    env = {**git_env(), "GIT_INDEX_FILE": str(copy / ".git" / "swebench-check.index")}
    try:
        if subprocess.run(["git", "-C", str(copy), "read-tree", base], env=env, check=False, capture_output=True).returncode:
            return False
        p = subprocess.run(["git", "-C", str(copy), "apply", "--cached", "--check", "-"], input=diff.encode("utf-8"),
                           capture_output=True, check=False, env=env)
        return p.returncode == 0
    finally:
        Path(env["GIT_INDEX_FILE"]).unlink(missing_ok=True)


def verinoda_tools(transcript: Path | None) -> dict:
    """Calls to each of Verinoda's MCP tools in a session, and whether the first call that edits or searches the code
    (not ToolSearch) was one of them: what the study needs to say that the arm used Verinoda."""
    out: dict = {"calls": {}, "before_first_code_tool": None}
    if transcript is None or not transcript.is_file():
        return out
    for line in transcript.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            m = json.loads(line).get("message") or {}
        except ValueError:
            continue
        if m.get("role") != "assistant" or not isinstance(m.get("content"), list):
            continue
        for x in m["content"]:
            name = x.get("name", "") if x.get("type") == "tool_use" else ""
            if name.startswith("mcp__verinoda__"):
                short = name.removeprefix("mcp__verinoda__")
                out["calls"][short] = out["calls"].get(short, 0) + 1
                if out["before_first_code_tool"] is None:
                    out["before_first_code_tool"] = True
            elif name in ("Grep", "Glob", "Read", "Edit", "Write", "Bash") and out["before_first_code_tool"] is None:
                out["before_first_code_tool"] = False
    return out


def one(cfg: dict, task: dict, arm: str) -> dict:
    copy = Path(cfg["work"]) / "copies" / task["id"] / arm
    with_env = bool(cfg.get("env_data")) and ("env_only" not in cfg or task["id"] in cfg["env_only"])
    if with_env:
        write_generated(copy, task)
        with (copy / ".git" / "info" / "exclude").open("a", encoding="utf-8") as f:
            f.write("\n.scratch/\nsrc/_pytest/_version.py\n")
    venv, pythonpath = session_venv(task, copy, arm, Path(cfg["env_data"])) if with_env else (None, None)
    argv = session_argv(prompt_for(task, copy, arm, with_env), arm, copy, cfg)
    env = env_for(arm, cfg, venv, pythonpath)
    if with_env:  # a build the session starts itself gets the same version
        env.update(scm_env(task))
    rc, out, err, secs = run(argv, copy, env, timeout=cfg.get("timeout_s", 2400))
    try:
        rep = json.loads(out)
    except ValueError:
        rep = {"is_error": True, "result": (out or err)[-500:]}
    diff, touched_tests = patch_of(copy, task["base_commit"], task["test_files"])
    if with_env and (copy / ".scratch").is_dir() and cfg.get("out"):
        # the reproductions are kept: a selector among several attempts may run them (condition C3)
        keep = Path(cfg["out"]) / "scratch" / f"{task['id']}--{arm}"
        shutil.rmtree(keep, ignore_errors=True)
        shutil.copytree(copy / ".scratch", keep, ignore=shutil.ignore_patterns("__pycache__"))
    st = session_stats(find_transcript(rep.get("session_id", "")))
    usage = rep.get("usage") or {}
    files = sorted(set(re.findall(r"^diff --git a/(\S+) b/", diff, re.MULTILINE)))
    gold = set(task["gold_files"])
    return {"id": task["id"], "arm": arm, "env": with_env, "model": cfg["model"], "claude": claude_version(), "exit": rc,
            "seconds": secs,
            "patch": diff, "patch_files": files, "patch_lines": diff.count("\n"), "touched_tests": touched_tests,
            "gold_files": sorted(gold), "overlap": len(gold & set(files)), "covers_gold": bool(gold) and gold <= set(files),
            "extra_files": len(set(files) - gold), "is_error": rep.get("is_error"), "subtype": rep.get("subtype"),
            "session_id": rep.get("session_id"), "num_turns": rep.get("num_turns"), "cost_usd": rep.get("total_cost_usd"),
            "input_tokens": sum(int(usage.get(k) or 0) for k in ("input_tokens", "cache_creation_input_tokens",
                                                                 "cache_read_input_tokens")),
            "output_tokens": int(usage.get("output_tokens") or 0), "final": (rep.get("result") or "")[:300],
            "tool_calls": st["tool_calls"], "verinoda_calls": st["verinoda_calls"], "first_tools": st["first_tools"],
            "verinoda_tools": verinoda_tools(find_transcript(rep.get("session_id", ""))),
            "assist": st["assist"], "network": st["network"], "applies": applies(diff, copy, task["base_commit"])}


def main() -> int:
    cfg = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    work = Path(cfg["work"])
    tasks = json.loads(Path(cfg.get("tasks") or work / "tasks.json").read_text(encoding="utf-8"))["tasks"]
    if cfg.get("only"):
        tasks = [t for t in tasks if t["id"] in cfg["only"]]
    out_dir = Path(cfg.get("out") or work)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "results.jsonl"
    done = set()
    if out.exists():
        done = {(r["id"], r["arm"]) for r in map(json.loads, out.read_text(encoding="utf-8").splitlines()) if r}
    todo = [(t, a) for t in tasks for a in cfg["arms"] if (t["id"], a) not in done]
    lock = threading.Lock()
    print(f"{len(todo)} sessions to run ({len(done)} done)", flush=True)

    def work_item(item):
        t, a = item
        r = one(cfg, t, a)
        with lock, out.open("ab") as f:
            f.write((json.dumps(r) + "\n").encode("utf-8"))
        print(f"{time.strftime('%H:%M:%S')} {t['id']}:{a} patch={r['patch_lines']} lines files={r['patch_files']} "
              f"gold={r['overlap']}/{len(r['gold_files'])} verinoda_calls={r['verinoda_calls']} turns={r['num_turns']} "
              f"${r['cost_usd']} {r['seconds']} s", flush=True)

    uses_mod = "verinoda_guided" in cfg["arms"]
    with isolated_plugin_store() if uses_mod else contextlib.nullcontext():
        for item, err in run_by_arm(todo, cfg.get("arm_workers", {}), work_item, 2):
            print(f"FAILED {item[0]['id']}:{item[1]} {err}", flush=True)
    if not out.exists():
        print("no session produced a result", flush=True)
        return 1
    for arm in cfg["arms"]:
        rows = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines() if x]
        with (out_dir / f"predictions-{arm}.jsonl").open("w", encoding="utf-8", newline="\n") as f:
            for r in rows:
                if r["arm"] == arm:
                    f.write(json.dumps({"instance_id": r["id"], "model_name_or_path": f"claude-code-{arm}",
                                        "model_patch": r["patch"]}) + "\n")
    print("all done", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
