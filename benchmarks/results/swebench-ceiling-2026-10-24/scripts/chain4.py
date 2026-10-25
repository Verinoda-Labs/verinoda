"""Run the study's conditions in turn on the same copies (DESIGN_SWEBENCH_CEILING.md, amendments 4 and 6); chain3.py's
successor, with amendment 6's re-runs: a run "<run>-r1" takes the lanes whose session in <run> lost its Bash PATH
(swebench_shellcheck.py), "<run>-r2" those whose "-r1" session did. The re-runs come after every other run of the study,
so a lane is never reset for one while an earlier run's session may be working in it.

Each copy (an instance and an arm: a lane) goes through its study's runs in order. Between two runs the lane's copy is
reset (swebench_reuse.py reset: the base commit, nothing the session wrote, the Verinoda snapshot back, Claude Code's
memory folder for its path emptied); the study's state file records the run a lane was reset for, and "<run>:started"
once a runner was given it: a lane so marked, not done, with no runner of that run alive, may hold a dead session's edits
and is reset again. A run may name its instances ("ids") or, for a re-run, take the lanes flagged in the run it repeats:
a lane outside them counts as done for it. A study's first run takes its Verinoda copies once their snapshot is taken
(their setup finished). A run's runner (one per arm, each with its config and its script) is started on the lanes ready
for it and not done, at most the study's runner limit per arm at once, earlier runs first; runners start before the
round's resets, so a long reset delays no runner. When no evaluation is running, the evaluation jobs run one after another
(each skips what it graded), at below-normal priority so a session's start keeps the processor (amendment 6): every run's
finished sessions, C0's first repeat, and the held-out gold patches once chain-allow-heldout (a file) exists. The
evaluator installs into shared environments, so two evaluations never run at once. chain-reload (a file) ends the loop
before its next round, for a restart with new runs: the state stays.

Amendment 9: a session that ended on the account's usage limit is not a session; once no runner of its run is alive, its
row moves aside (limit_rows.py) and its lane runs again. No runner starts while Claude Code's own /usage reads 85 % or
more of the 5-hour window, the week's ceiling (chain-week-max.txt, default 75 %) or more, or cannot be read; a runner gets
at most 10 lanes, so one started just before a limit leaves few such rows.

    python chain4.py [--dry-run]
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

DATA = Path("C:/Users/ozcin/swebench-data")
AC = Path("C:/Users/ozcin/Desktop/vwt-ceiling/benchmarks/agent_compare")
TMP = Path("C:/Users/ozcin/.claude/jobs/df423e2d/tmp")
PY = DATA / "tools-venv" / "Scripts" / "python.exe"
RELOAD = DATA / "chain-reload"
ALLOW_HELDOUT = DATA / "chain-allow-heldout"
ARMS = ("none", "verinoda_guided")
RUN_SCRIPT = AC / "swebench_run.py"
DIAG_SCRIPT = AC / "swebench_run_diag.py"
DIAG_IDS = DATA / "diag-ids.json"
WEEK_MAX = DATA / "chain-week-max.txt"
CLAUDE = "C:/Users/ozcin/AppData/Roaming/npm/node_modules/@anthropic-ai/claude-code/bin/claude.exe"
SESSION_MAX = 85
BATCH = 10
sys.path.insert(0, str(AC))
sys.path.insert(0, str(TMP))
from swebench_shellcheck import check as shell_check

from limit_rows import is_limit
from limit_rows import move as move_limit_rows


def run_spec(name: str, script: Path = RUN_SCRIPT, ids: set[str] | str | None = None, repeats: str | None = None,
             arms: tuple[str, ...] = ARMS) -> dict:
    """IDS: the run's instances, or the name of a list in diag-ids.json (read every round: amendment 10's lists change)."""
    return {"name": name, "script": script, "ids": ids, "repeats": repeats, "arms": arms,
            "configs": {a: DATA / "configs" / f"{name}-{'none' if a == 'none' else 'guided'}.json" for a in ARMS}}


def diag_lists() -> dict[str, list[str]]:
    try:
        return json.loads(DIAG_IDS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def ids_of(run: dict) -> set[str] | None:
    return set(diag_lists().get(run["ids"], [])) if isinstance(run["ids"], str) else run["ids"]


def with_reruns(runs: list[dict]) -> list[dict]:
    """The runs, then each one's first re-runs, then the second (amendment 6)."""
    first = [run_spec(f"{r['name']}-r1", r["script"], r["ids"], r["name"], r["arms"]) for r in runs]
    return [*runs, *first,
            *[run_spec(f"{r['name']}-r2", r["script"], r["ids"], f"{r['name']}-r1", r["arms"]) for r in runs]]


# a study: its lanes (WORK/copies/<id>/<arm>), tasks, Verinoda snapshots, state file, runner limit per arm, its runs in
# order, and what its runs' evaluations are given (eval_run.sh: GOLD, the gold reports; COPIES, where a clean checkout is
# cloned from)
STUDIES = [
    {"name": "dev", "work": "C:/Users/ozcin/swebench-run/c1-s1", "tasks": DATA / "ceiling" / "tasks-dev.json",
     "snaps": DATA / "snapshots" / "c1-s1", "state": DATA / "chain-state.json",
     "max_runners": DATA / "chain-max-runners.txt", "eval_env": "",
     # the user's decision (2026-10-24 ~12:30, cost): Fable's guided arm stops at the sessions it has; plain arm only
     # C3 (amendments 4 and 9): Opus's second and third attempts, its C4 session the first
     # the diagnostics (amendments 5 and 10) after every C3 session and re-run of their lanes
     "runs": with_reruns([run_spec("c1-s1"), run_spec("c4-opus"), run_spec("c4-fable", arms=("none",)),
                          run_spec("c3-opus-2"), run_spec("c3-opus-3")])
             + with_reruns([run_spec("diag-hints", DIAG_SCRIPT, "diag-hints"),
                            run_spec("diag-tests", DIAG_SCRIPT, "diag-tests")])},
]
RUNS = [r for st in STUDIES for r in st["runs"]]
# (label, bash command, the condition for it to run now)
EVAL_JOBS = [*[(f"{r['name']} {a}", f"{st['eval_env']}{(TMP / 'eval_run.sh').as_posix()} {r['name']} {a}",
                lambda r=r: (DATA / "runs" / r["name"] / "results.jsonl").exists())
               for st in STUDIES for r in st["runs"] for a in ARMS],
             *[(f"{c0} {a}", f"{(TMP / 'eval_run.sh').as_posix()} {c0} {a}",
                lambda c0=c0: (DATA / "runs" / c0 / "results.jsonl").exists())
               for c0 in ("c0-s1", "c0-s1-r1") for a in ARMS],
             ("gold heldout", (f"{(TMP / 'eval_gold.sh').as_posix()} heldout ceiling/tasks-heldout.json "
                               "C:/Users/ozcin/swebench-run/heldout/copies"),
              lambda: ALLOW_HELDOUT.exists() and not any("swebench_localeval.py build" in p for p in processes()))]
# a finished session's transcript does not change: whether its Bash lost its PATH is read once
FLAGGED: dict[str, bool] = {}
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "GRAPHIFY_MAX_WORKERS": "3"}
DRY = "--dry-run" in sys.argv


def now() -> str:
    return time.strftime("%H:%M:%S")


def say(text: str) -> None:
    print(f"{now()} {'(dry run) ' if DRY else ''}{text}", flush=True)


def processes(name: str = "python.exe") -> list[str]:
    query = f"Get-CimInstance Win32_Process -Filter \"Name='{name}'\" | Select-Object -ExpandProperty CommandLine"
    return subprocess.run(["powershell", "-NoProfile", "-Command", query], capture_output=True, text=True,
                          check=False).stdout.splitlines()


def save(study: dict, state: dict) -> None:
    if DRY:
        return
    tmp = study["state"].with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1, sort_keys=True), encoding="utf-8", newline="\n")
    os.replace(tmp, study["state"])


def rows(name: str) -> list[dict]:
    out = DATA / "runs" / name / "results.jsonl"
    got = []
    for line in out.read_text(encoding="utf-8").splitlines() if out.exists() else []:
        try:
            got.append(json.loads(line))
        except ValueError:
            say(f"{name}: a results line does not parse: {line[:120]}")
    return got


def flagged(name: str) -> set[tuple[str, str]]:
    """The lanes whose session in run NAME lost its Bash PATH (amendment 6)."""
    out = set()
    for r in rows(name):
        sid = r.get("session_id") or ""
        if sid not in FLAGGED:
            FLAGGED[sid] = shell_check(sid) is not None
        if FLAGGED[sid]:
            out.add((r["id"], r["arm"]))
    return out


def done(run: dict, tasks: list[str]) -> set[tuple[str, str]]:
    scope = flagged(run["repeats"]) if run["repeats"] else None
    ids = ids_of(run)
    got = {(i, a) for i in tasks for a in ARMS
           if a not in run["arms"] or (ids is not None and i not in ids)
           or (scope is not None and (i, a) not in scope)}
    return got | {(r["id"], r["arm"]) for r in rows(run["name"])}


def alive_runs(procs: list[str]) -> set[tuple[str, str]]:
    return {(r["name"], a) for r in RUNS for a in ARMS
            if any(r["script"].name in p and r["configs"][a].name in p for p in procs)}


def reset(study: dict, arm: str, ids: list[str]) -> set[str]:
    if DRY:
        say(f"{study['name']}: would reset {len(ids)} {arm} lanes")
        return set()
    p = subprocess.run([str(PY), str(AC / "swebench_reuse.py"), "reset", study["work"], str(study["tasks"]),
                        str(study["snaps"]), "--arms", arm, "--only", ",".join(ids)], env=ENV, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", check=False)
    ok = set()
    for line in p.stdout.splitlines():
        head, _, verdict = line.partition(": ")
        iid = head.rsplit(":", 1)[0]
        if iid in ids and verdict.startswith("reset"):
            ok.add(iid)
            if "memory" in verdict:
                say(line)
        elif iid in ids:
            say(f"RESET FAILED {line}")
    return ok


def limits(study: dict) -> dict[str, int]:
    """Runners at once per arm: the file holds one number for both arms, or "none=N guided=M" (read every round, so the
    guided arm can take the plain arm's share once the plain arm has nothing to run)."""
    text = study["max_runners"].read_text(encoding="utf-8").strip() if study["max_runners"].exists() else "1"
    if "=" not in text:
        return {a: int(text) for a in ARMS}
    got = dict(part.split("=", 1) for part in text.split())
    return {a: int(got.get("none" if a == "none" else "guided", 1)) for a in ARMS}


def usage() -> tuple[int, int] | None:
    """Claude Code's own /usage: the 5-hour window's share and the week's (all models), in percent; None if unreadable."""
    try:
        p = subprocess.run([CLAUDE, "-p", "/usage"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=120, cwd=str(TMP), check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    window = re.search(r"Current session: (\d+)% used", p.stdout)
    week = re.search(r"Current week \(all models\): (\d+)% used", p.stdout)
    return (int(window.group(1)), int(week.group(1))) if window and week else None


def may_start() -> bool:
    """Amendment 9: no runner starts near the account's usage limits, nor when they cannot be read."""
    try:
        week_max = int(WEEK_MAX.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        week_max = 75
    got = usage()
    if got is None or got[0] >= SESSION_MAX or got[1] >= week_max:
        say(f"usage {'unreadable' if got is None else f'5-hour {got[0]} %, week {got[1]} %'}: no runner starts "
            f"(under {SESSION_MAX} % and {week_max} % needed)")
        return False
    return True


def start_runners(study: dict, ready: dict, finished: dict, state: dict, tasks: list[str]) -> None:
    alive = alive_runs(processes())
    limit_of = limits(study)
    # the plain arm's share goes to the guided arm once the plain arm has nothing left in any run
    if not any((i, "none") not in finished[r["name"]] for r in study["runs"] for i in tasks):
        limit_of["verinoda_guided"] += limit_of["none"]
    allowed = None
    # amendment 10: the diagnostics' lanes go first, in a batch and among the runs; the diagnostics have one runner per
    # arm of their own
    first = set().union(*map(set, diag_lists().values()))
    for arm in ARMS:
        todo_of = {j: sorted({i for i in ready.get((j, arm), []) if (i, arm) not in finished[run["name"]]},
                             key=lambda i: (i not in first, i))[:BATCH] for j, run in enumerate(study["runs"])}
        order = sorted(todo_of, key=lambda j: (not first & set(todo_of[j]), j))
        for diag in (False, True):
            limit = 1 if diag else limit_of[arm]
            mine = [j for j in order if (study["runs"][j]["script"] == DIAG_SCRIPT) == diag]
            active = sum((study["runs"][j]["name"], arm) in alive for j in mine)
            for j in mine:
                run, todo = study["runs"][j], todo_of[j]
                if not todo or (run["name"], arm) in alive:
                    continue
                if active >= limit:
                    break
                if allowed is None:
                    allowed = may_start()
                if not allowed:
                    return
                active += 1
                start_one(study, run, j, arm, todo, state)


def start_one(study: dict, run: dict, j: int, arm: str, todo: list[str], state: dict) -> None:
    say(f"{run['name']} {arm}: started on {len(todo)} instances")
    if DRY:
        return
    if j > 0:
        for iid in todo:
            state[f"{iid}:{arm}"] = f"{run['name']}:started"
        save(study, state)
    config = run["configs"][arm]
    cfg = json.loads(config.read_text(encoding="utf-8"))
    cfg["only"] = todo
    config.write_text(json.dumps(cfg, indent=1), encoding="utf-8", newline="\n")
    log = DATA / f"runs-{run['name']}-{'none' if arm == 'none' else 'guided'}.log"
    with log.open("a", encoding="utf-8") as f:
        subprocess.Popen([str(PY), str(run["script"]), str(config)], stdout=f, stderr=f, env=ENV,
                         cwd=str(DATA), creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)


def start_evals() -> None:
    # the jobs' own shell too: between two jobs no evaluator runs for a moment
    if any("swebench_localeval.py" in p and "preds-" in p for p in processes()) or \
            any("eval_run.sh" in p or "eval_gold.sh" in p for p in processes("bash.exe")):
        return
    steps = [cmd for label, cmd, ok in EVAL_JOBS if ok()]
    say(f"evaluations: {len(steps)} jobs")
    if DRY or not steps:
        return
    with (DATA / "eval-chain.log").open("a", encoding="utf-8") as f:
        subprocess.Popen(["bash", "-c", "; ".join(steps)], stdout=f, stderr=f,
                         creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS)


def one_round(study: dict) -> int:
    """One round over a study's lanes; returns the sessions it has left."""
    runs = study["runs"]
    tasks = [t["id"] for t in json.loads(study["tasks"].read_text(encoding="utf-8"))["tasks"]]
    state = json.loads(study["state"].read_text(encoding="utf-8")) if study["state"].exists() else {}
    if not DRY:
        subprocess.run([str(PY), str(AC / "swebench_reuse.py"), "snapshot", study["work"], str(study["tasks"]),
                        str(study["snaps"])], env=ENV, capture_output=True, check=False)
    snaps = {p.name for p in study["snaps"].iterdir() if p.is_dir() and not p.name.endswith(".part")} \
        if study["snaps"].is_dir() else set()
    alive = alive_runs(processes())
    for r in runs:
        # amendment 9: results.jsonl belongs to the run's runners until none of them, in either arm, is alive
        if not DRY and not any((r["name"], a) in alive for a in ARMS) and any(map(is_limit, rows(r["name"]))):
            say(f"{r['name']}: {move_limit_rows(DATA / 'runs' / r['name'])} usage-limit rows moved aside (amendment 9)")
    finished = {r["name"]: done(r, tasks) for r in runs}
    ready: dict[tuple[int, str], list[str]] = {}
    to_reset: dict[tuple[int, str], list[str]] = {}
    for iid in tasks:
        for arm in ARMS:
            j = next((k for k, r in enumerate(runs) if (iid, arm) not in finished[r["name"]]), None)
            if j is None:
                continue
            name, mark = runs[j]["name"], state.get(f"{iid}:{arm}")
            if j == 0:
                if arm == "none" or iid in snaps:
                    ready.setdefault((0, arm), []).append(iid)
            elif mark == name or (mark == f"{name}:started" and (name, arm) in alive):
                ready.setdefault((j, arm), []).append(iid)
            else:
                to_reset.setdefault((j, arm), []).append(iid)
    start_runners(study, ready, finished, state, tasks)
    for (j, arm), ids in to_reset.items():
        for iid in reset(study, arm, ids):
            state[f"{iid}:{arm}"] = runs[j]["name"]
        save(study, state)
    left = sum(len(tasks) * len(ARMS) - len(finished[r["name"]]) for r in runs)
    say(f"{study['name']}: snapshots {len(snaps)}; sessions left {left}; lanes to reset "
        f"{sum(map(len, to_reset.values()))}")
    return left


def main() -> int:
    while True:
        if RELOAD.exists() and not DRY:
            RELOAD.unlink()
            say("chain-reload: ending for a restart")
            return 0
        left = sum(one_round(st) for st in STUDIES)
        start_evals()
        if left == 0 or DRY:
            return 0
        time.sleep(120)


if __name__ == "__main__":
    sys.exit(main())
