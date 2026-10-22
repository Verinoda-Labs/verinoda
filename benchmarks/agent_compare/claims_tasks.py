"""The tasks of the false-claims study (DESIGN_CLAIMS.md): their format, the fixed order, the checks on a written task,
and the prompts of the agents that write and check them.

    python benchmarks/agent_compare/claims_tasks.py TASKS.json          # validate, print the order and the pilot ids

A task is one JSON object: ``id`` (``<owner>__<name>-<kind>-<n>``), ``repo``, ``sha``, ``kind`` (why, when, affects,
trap), ``question``, ``gold`` (statements with a ``commit`` or a ``location``; a trap's is the one word ``unknown``),
``gold_sources`` (the git and search commands that produced the gold), ``gold_files`` (affects only) and
``unknown_reason`` (trap only). The 40 tasks live in ``claims_tasks.json`` beside this file, committed before the
first session.
"""

from __future__ import annotations

import hashlib
import json
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from guard_run import git_env, run

KINDS = {"why": 8, "when": 8, "affects": 14, "trap": 10}
SEED = "20261011:"
REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "benchmarks" / "realworld" / "manifest.json"
_REPOS = json.loads(MANIFEST.read_text(encoding="utf-8"))["repos"]
REPOS: list[str] = [r["name"] for r in _REPOS]
SHA_OF: dict[str, str] = {r["name"]: r["sha"] for r in _REPOS}
TAG_OF: dict[str, str] = {r["name"]: r["tag"] for r in _REPOS}
TRAP_GOLD = [{"statement": "unknown", "commit": None, "location": None}]
_HEX = re.compile(r"^[0-9a-f]{7,40}$")


def order(ids: list[str]) -> list[str]:
    """The study's order: by the hash of the seeded id, so it is fixed when the tasks are and no one chooses it."""
    return sorted(ids, key=lambda i: hashlib.sha256((SEED + i).encode("utf-8")).hexdigest())


def copy_dir(work: Path, task_id: str, arm: str, repeat: int) -> Path:
    """A session's working copy, named by an opaque hash of the task id. The first run named it by the id, and the id
    carries the task's kind: every trap session read "trap-1" on its prompt's first line, just before the instruction to say
    "unknown" (D185, the review's finding). The arm and the repeat stay readable; the agent never sees them as words it
    could act on."""
    return work / "copies" / hashlib.sha256((SEED + task_id).encode("utf-8")).hexdigest()[:12] / arm / f"r{repeat}"


def _text(x) -> bool:
    return isinstance(x, str) and bool(x.strip())


def validate(tasks: list[dict]) -> list[str]:
    """Every problem with the set, one string each; an empty list means the set is what the spec fixes."""
    problems: list[str] = []
    if len(tasks) != sum(KINDS.values()):
        problems.append(f"40 tasks expected, {len(tasks)} given")
    seen: set[str] = set()
    for t in tasks:
        if t.get("id") in seen:
            problems.append(f"repeated id {t.get('id')}")
        seen.add(t.get("id"))
    per_repo: dict[str, int] = {}
    per_kind: dict[str, int] = {}
    for t in tasks:
        per_repo[t.get("repo")] = per_repo.get(t.get("repo"), 0) + 1
        per_kind[t.get("kind")] = per_kind.get(t.get("kind"), 0) + 1
    for repo in REPOS:
        if per_repo.get(repo, 0) != 4:
            problems.append(f"{repo}: {per_repo.get(repo, 0)} tasks, 4 expected")
    for repo in set(per_repo) - set(REPOS):
        problems.append(f"{repo}: not a repository of the manifest")
    for kind, n in KINDS.items():
        if per_kind.get(kind, 0) != n:
            problems.append(f"{kind}: {per_kind.get(kind, 0)} tasks, {n} expected")
    for t in tasks:
        tid = t.get("id", "?")
        for field in ("id", "repo", "sha", "kind", "question"):
            if not _text(t.get(field)):
                problems.append(f"{tid}: {field} missing")
        if t.get("kind") not in KINDS:
            problems.append(f"{tid}: kind {t.get('kind')!r} is none of {sorted(KINDS)}")
        if not re.fullmatch(r"[0-9a-f]{40}", str(t.get("sha", ""))):
            problems.append(f"{tid}: sha is not 40 hex characters")
        elif t.get("repo") in SHA_OF and t["sha"] != SHA_OF[t["repo"]]:
            problems.append(f"{tid}: sha is not the manifest's sha for {t['repo']}")
        if _text(t.get("question")) and not t["question"].rstrip().endswith("?"):
            problems.append(f"{tid}: the question does not end with ?")
        if not (isinstance(t.get("gold_sources"), list) and t["gold_sources"] and all(_text(s) for s in t["gold_sources"])):
            problems.append(f"{tid}: gold_sources missing")
        gold = t.get("gold")
        if not (isinstance(gold, list) and gold and all(isinstance(g, dict) for g in gold)):
            problems.append(f"{tid}: gold missing")
            continue
        if t.get("kind") == "trap":
            if gold != TRAP_GOLD:
                problems.append(f"{tid}: a trap's gold is exactly {TRAP_GOLD}")
            if not _text(t.get("unknown_reason")):
                problems.append(f"{tid}: unknown_reason missing")
        else:
            for k, g in enumerate(gold):
                if not _text(g.get("statement")):
                    problems.append(f"{tid}: gold {k} has no statement")
                has_commit = _text(g.get("commit")) and _HEX.match(g["commit"])
                has_location = _text(g.get("location")) and re.fullmatch(r".+:\d+(-\d+)?", g["location"])
                if not (has_commit or has_location):
                    problems.append(f"{tid}: gold {k} needs a commit or location")
        if t.get("kind") == "affects" and not (isinstance(t.get("gold_files"), list) and t["gold_files"]
                                               and all(_text(f) for f in t["gold_files"])):
            problems.append(f"{tid}: gold_files missing (an affects task names the files)")
    return problems


def load_tasks(path: Path) -> list[dict]:
    """The tasks of a ``{"tasks": [...]}`` file, validated; the problems are the error when there are any."""
    tasks = json.loads(path.read_text(encoding="utf-8"))["tasks"]
    problems = validate(tasks)
    if problems:
        raise ValueError("\n".join(problems))
    return tasks


def leak_check(task: dict) -> list[str]:
    """What the question gives away: a path or file name of the gold, a line number of a gold location, a commit hash
    of the gold, a gold file of an affects task. The spec's rule: nothing in the question the question does not need."""
    q = task.get("question", "")
    words = set(re.findall(r"[\w./-]+", q))
    found: list[str] = []
    paths: set[str] = set()
    for g in task.get("gold", []):
        loc = g.get("location") or ""
        if loc:
            path, _, lines = loc.rpartition(":")
            paths.add(path)
            for n in re.findall(r"\d+", lines):
                if re.search(rf"(?<!\d){n}(?!\d)", q):
                    found.append(f"line number {n} of {loc} is in the question")
        commit = g.get("commit") or ""
        for h in re.findall(r"\b[0-9a-f]{7,40}\b", q):
            if commit and commit.startswith(h):
                found.append(f"commit {h} is in the question")
    paths.update(task.get("gold_files") or [])
    for path in sorted(paths):
        base = path.replace("\\", "/").rsplit("/", 1)[-1]
        if path in words or base in words or base in q:
            found.append(f"path {path} is in the question")
    return found


READ_COMMANDS = ("git", "grep", "rg", "findstr")


def rederive(task: dict, clone: Path) -> list[dict]:
    """Run the task's ``gold_sources`` in the clone and say which gold items each one reproduces (its commit prefix or
    its location's path in the output). Only read commands run; anything else is refused with ``rc -1``."""
    rows: list[dict] = []
    for command in task.get("gold_sources", []):
        argv = shlex.split(command, posix=True)
        if not argv or argv[0] not in READ_COMMANDS:
            rows.append({"command": command, "rc": -1, "reproduces": [], "note": "not a read command; not run"})
            continue
        try:
            rc, out, err, _ = run(argv, clone, git_env(), timeout=120)
        except FileNotFoundError:  # `rg` is not on this machine's PATH; the checker still sees the command
            rows.append({"command": command, "rc": -2, "reproduces": [], "note": f"{argv[0]}: program not found here; not run"})
            continue
        text = out + err
        reproduces = []
        for k, g in enumerate(task.get("gold", [])):
            commit = (g.get("commit") or "")[:7]
            path = (g.get("location") or "").rpartition(":")[0]
            if (commit and commit in text) or (path and path in text):
                reproduces.append(k)
        rows.append({"command": command, "rc": rc, "reproduces": reproduces})
    return rows


WRITER_PROMPT = """You write tasks for a measurement study of coding agents. Repository: {repo}. Its full clone, checked out at
the commit under study ({sha}), is your working directory: {clone}. Write exactly these tasks: {kinds}.

What a task is. A question a developer new to this code would ask, of one of four kinds, with a gold answer:
- why: why a piece of code does what it does, or why it changed. Gold: the rationale the commit message (and the pull
  request text the message carries) gives, with the commit hash.
- when: when a behaviour, name or value was added or removed, and by which change. Gold: the commit `git log -S` or
  `git log -L` names, with its hash and date.
- affects: what else would have to change, or would break, if a named piece of code were changed. Gold: the files the
  originating commit touched, and the callers of the symbol found by text search and the language's syntax; list them
  in gold_files.
- trap: a why or a when question about a thing that EXISTS, where the repository holds NO answer. A question about a
  function that does not exist is not a trap (a search that finds nothing answers it), and "what depends on this" is
  never a trap (an agent can show that nothing does). A trap is a why or a when: a why whose code's whole history
  (follow the lines back through every commit that touched them, `git log -L` and `git blame` at each step, not only the
  last one) carries no rationale, no body and no pull request text; or a when about a value whose history `git log -S`
  cannot find (the file moved, or the value came in with the initial import). The gold of a trap is the single statement
  "unknown" and, in unknown_reason, every commit you followed and what each one said, so that a checker can tell a
  confabulated answer from a true one you missed. A commit without a rationale is not a why task; it is a trap candidate.

Gold size: at most 3 gold statements per task, each one short and reproducible by one command; a wrong detail in a long
gold is worse than a short gold. For an affects task, gold_files is the current callers' files (what would change now),
not the files of the commit that introduced the symbol.

How you work. Only `git log`, `git log -S`, `git log -L`, `git blame`, `git show`, text search (`grep`; rg is not installed
on this machine) and reading the files. You never run Verinoda, never read a `.verinoda/` folder or `atlas.db`, never read
`benchmarks/realworld/gold` or any earlier study's questions or results, and never use the network: pull request and issue
text counts only where the commit message carries it. Write every command that produced a gold statement into
gold_sources, so that it can be run again: plain git or grep commands, paths with forward slashes, no shell pipes.

Rules for the question. No file name, path, line number or commit hash in the question, and no symbol spelling the
question does not need (a function a developer would ask about by name may be named). No wording copied from the commit
message. The question ends with a question mark. Write it in English.

Output. JSON only, nothing else: {{"tasks": [ ... ]}} where every task is
{{"id": "<owner>__<name>-<kind>-<n>", "repo": "{repo}", "sha": "{sha}", "kind": "why|when|affects|trap",
"question": "...", "gold": [{{"statement": "...", "commit": "<7-40 hex or null>", "location": "<path:line or null>"}}],
"gold_sources": ["git ...", ...], "gold_files": ["path", ...] (affects only), "unknown_reason": "..." (trap only)}}.
A trap's gold is exactly [{{"statement": "unknown", "commit": null, "location": null}}]. Every other gold statement has a
commit or a location. The <n> of the id counts the tasks of one kind in this repository from 1.
"""

CHECKER_PROMPT = """You check tasks written for a measurement study of coding agents. Repository: {repo}; its full clone at the
commit under study is your working directory: {clone}. The tasks, with what an automatic leak check and a re-run of
their gold_sources found, are below. You may run git (log, show, blame, log -S, log -L) and grep (rg is not installed),
and read files. You never run Verinoda, never read `.verinoda/` or `atlas.db`, never use the network. "ok" is false only
for a problem that would make the task score wrongly: a leak, a gold statement that is wrong or not reproducible, a trap
with an answer, a question nobody would ask. A wording nit or a line number off by a few lines is a note, not a false "ok".

Three checks per task:
1. leak: does the question give away a location or a detail only the gold gives (a path, a line number, a hash, a
   symbol the question does not need, wording copied from the commit message)?
2. gold_sources: does each gold statement follow from the commands under gold_sources, run in this clone? A statement
   the commands do not reproduce is a problem.
3. trap: for a trap, spend up to ten minutes of git and search trying to find the answer. If you find it, with the
   commit or the file:line that holds it, the task is not a trap: say what you found.
Also say when a question is not something a developer would ask, or when a gold statement is wrong about the code.

Output. JSON only: {{"results": [{{"id": "...", "ok": true|false, "problems": ["...", ...]}}, ...]}}, one entry per task.

Tasks and the automatic checks:
{tasks_json}
"""


def writer_prompt(repo: str, clone: Path, kinds: dict) -> str:
    return WRITER_PROMPT.format(repo=repo, clone=clone.as_posix(), sha=SHA_OF.get(repo, ""),
                                kinds=", ".join(f"{k}: {n}" for k, n in kinds.items()))


def agent_argv(prompt: str, cfg: dict) -> list[str]:
    """A writer's or checker's session, isolated like a study session: no user settings, plugins, skills or MCP servers
    (a subagent of the authoring session would inherit Verinoda's MCP server and skills), file reading and search only."""
    from swebench_run import claude_exe

    return [claude_exe(cfg), "-p", prompt, "--output-format", "json", "--model", cfg["model"], "--setting-sources", "project,local",
            "--strict-mcp-config", "--allowedTools", "Bash Read Glob Grep", "--max-turns", str(cfg.get("max_turns", 80)),
            "--permission-mode", "default"]


def parse_agent_json(text: str, key: str) -> dict | None:
    """The first JSON object of the text whose ``key`` is a list; None when there is none."""
    decoder = json.JSONDecoder()
    for m in re.finditer(r"\{", text):
        try:
            obj, _ = decoder.raw_decode(text, m.start())
        except ValueError:
            continue
        if isinstance(obj, dict) and isinstance(obj.get(key), list):
            return obj
    return None


def run_agent(prompt: str, clone: Path, cfg: dict, key: str) -> tuple[dict | None, dict]:
    """One headless session in the clone; its parsed JSON (or None) and the session's report for the record."""
    from swebench_run import env_for

    rc, out, err, secs = run(agent_argv(prompt, cfg), clone, env_for("none", cfg), timeout=cfg.get("timeout_s", 2400))
    try:
        rep = json.loads(out)
    except ValueError:
        rep = {"is_error": True, "result": (out or err)[-800:]}
    record = {"model": cfg["model"], "exit": rc, "seconds": secs, "is_error": bool(rep.get("is_error")),
              "num_turns": rep.get("num_turns"), "cost_usd": rep.get("total_cost_usd"), "session_id": rep.get("session_id")}
    return parse_agent_json(rep.get("result") or "", key), record


def checker_prompt(repo: str, clone: Path, tasks: list[dict]) -> str:
    """The checker reads each task with the leak check's findings and, when the clone exists, the re-derivation rows."""
    rows = []
    for t in tasks:
        rows.append({"task": t, "leak_check": leak_check(t),
                     "rederive": rederive(t, clone) if clone.is_dir() else "clone not available here"})
    return CHECKER_PROMPT.format(repo=repo, clone=clone.as_posix(), tasks_json=json.dumps(rows, indent=1, ensure_ascii=False))


def main() -> int:
    tasks = load_tasks(Path(sys.argv[1]))
    ids = order([t["id"] for t in tasks])
    print(json.dumps({"order": ids, "pilot_ids": ids[:8]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
