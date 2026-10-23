"""Fresh working copies of instances an earlier run prepared, for a repeat run that leaves that run's copies as they are
(DESIGN_SWEBENCH_CEILING.md, C0).

    python benchmarks/agent_compare/swebench_copies.py TASKS.json FROM_COPIES NEW_WORK [--only IDS]
        [--arms none,verinoda_guided] [--workers N]

Each ``NEW_WORK/copies/<id>/<arm>`` borrows the objects of ``FROM_COPIES/<id>/none`` (git alternates, no remote) and is
checked out at the base commit; a ``verinoda_guided`` copy is then set up with ``verinoda setup`` (``VERINODA_PY``, as in
swebench_prepare). One NEW_WORK per repeat: a session's edits never have to be reset away. Resumable: a copy already made
(a guided one: recorded in ``NEW_WORK/builds.json``) is kept.
"""

from __future__ import annotations

import json
import shutil
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from guard_run import _force_remove, git_env, run
from swebench_prepare import setup_verinoda, share_copy


def at_base(copy: Path, base: str) -> bool:
    env = git_env()
    return (run(["git", "rev-parse", "HEAD"], copy, env)[1].strip() == base
            and not run(["git", "status", "--porcelain"], copy, env)[1].strip())


def main(argv: list[str]) -> int:
    tasks_path, source, work = Path(argv[0]), Path(argv[1]), Path(argv[2])
    only = set(argv[argv.index("--only") + 1].split(",")) if "--only" in argv else None
    arms = (argv[argv.index("--arms") + 1] if "--arms" in argv else "none,verinoda_guided").split(",")
    workers = int(argv[argv.index("--workers") + 1]) if "--workers" in argv else 2
    tasks = [t for t in json.loads(tasks_path.read_text(encoding="utf-8"))["tasks"] if only is None or t["id"] in only]
    builds_path = work / "builds.json"
    builds = json.loads(builds_path.read_text(encoding="utf-8")) if builds_path.exists() else {}
    lock = threading.Lock()

    def make(item: tuple[dict, str]) -> str:
        t, arm = item
        key, dest = f"{t['id']}:{arm}", work / "copies" / t["id"] / arm
        if dest.exists() and (key in builds if arm != "none" else at_base(dest, t["base_commit"])):
            return f"{key}: kept"
        if dest.exists():  # one a killed run left half made
            shutil.rmtree(dest, onerror=_force_remove)
        share_copy(source / t["id"] / "none", dest, t["base_commit"])
        if arm == "none":
            return f"{key}: ready"
        info = setup_verinoda(dest)
        with lock:
            builds[key] = info
            builds_path.write_text(json.dumps(builds, indent=1), encoding="utf-8")
        return f"{key}: set up ({info['setup_seconds']} s)"

    with ThreadPoolExecutor(workers) as pool:
        for line in pool.map(make, [(t, a) for t in tasks for a in arms]):
            print(line, flush=True)
    print("made", len(tasks), "instances", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
