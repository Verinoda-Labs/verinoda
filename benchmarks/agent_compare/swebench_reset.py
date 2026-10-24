"""Put prepared copies back to their base commit before another session runs in them (DESIGN_SWEBENCH_CEILING.md).

    python benchmarks/agent_compare/swebench_reset.py TASKS.json WORK_DIR [--only IDS] [--arms none,verinoda_guided]
        [--setup] [--workers N]

Every change a session left is discarded (`git reset --hard`, `git clean -fdx`), except Verinoda's own files in the
``verinoda_guided`` copy (its index then catches up with the reset files by itself); the GitHub remote D184's copies kept is
removed, so a session cannot fetch the commits after the base. ``--setup`` instead removes Verinoda's files too and runs
``verinoda setup`` again: needed once when the installed Verinoda is newer than the one that built the index.
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from guard_run import git_env, run
from swebench_prepare import setup_verinoda

KEEP = [".verinoda/", ".claude/", ".mcp.json"]


def reset(copy: Path, base: str, arm: str, setup: bool) -> str:
    env = git_env()
    keep = [] if (arm == "none" or setup) else [x for k in KEEP for x in ("-e", k)]
    steps = [["git", "reset", "-q", "--hard", base], ["git", "clean", "-q", "-fdx", *keep]]
    for argv in steps:
        rc, _, err, _ = run(argv, copy, env, timeout=600)
        if rc != 0:
            return f"FAILED {' '.join(argv)}: {err[-300:]}"
    if "origin" in run(["git", "remote"], copy, env)[1].split():
        run(["git", "remote", "remove", "origin"], copy, env)
    head = run(["git", "rev-parse", "HEAD"], copy, env)[1].strip()
    dirty = run(["git", "status", "--porcelain"], copy, env)[1].strip()
    if head != base or (dirty and arm == "none"):
        return f"FAILED: HEAD {head[:12]}, dirty {dirty[:200]!r}"
    if arm == "verinoda_guided" and setup:
        exclude = copy / ".git" / "info" / "exclude"
        text = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
        exclude.write_text("\n".join(x for x in text.splitlines() if x.strip() not in KEEP) + "\n", encoding="utf-8")
        return f"set up again ({setup_verinoda(copy)['setup_seconds']} s)"
    return "reset"


def main() -> int:
    tasks = {t["id"]: t for t in json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["tasks"]}
    work = Path(sys.argv[2])

    def opt(name, default=None):
        return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default

    only = [x for x in (opt("--only") or "").split(",") if x] or list(tasks)
    arms = (opt("--arms") or "none,verinoda_guided").split(",")
    setup = "--setup" in sys.argv
    items = [(i, a) for i in only for a in arms]

    def one(item):
        i, a = item
        print(f"{i}:{a} {reset(work / 'copies' / i / a, tasks[i]['base_commit'], a, setup)}", flush=True)

    with ThreadPoolExecutor(int(opt("--workers") or "2")) as ex:
        list(ex.map(one, items))
    return 0


if __name__ == "__main__":
    sys.exit(main())
