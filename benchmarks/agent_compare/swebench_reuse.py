"""Use a run's copies again for another attempt (DESIGN_SWEBENCH_CEILING.md, C3), without a new Verinoda setup per copy.

    python benchmarks/agent_compare/swebench_reuse.py snapshot WORK TASKS.json SNAPSHOTS [--only IDS]
    python benchmarks/agent_compare/swebench_reuse.py reset WORK TASKS.json SNAPSHOTS [--arms none,verinoda_guided]
        [--only IDS]

``snapshot``: Verinoda's files of every set-up ``verinoda_guided`` copy (``.verinoda``, ``.claude``, ``.mcp.json``), saved
to ``SNAPSHOTS/<id>`` before any session has run there (the copy must be at its base commit with nothing changed). A
snapshot already taken is kept.

``reset``: after a run's results are saved, every copy back to what its setup left. HEAD at the base commit; every other
ref, the reflog and the stash removed; every untracked and ignored file removed (the session's edits, its scratch files,
Verinoda's state); the objects nothing reaches pruned from the copy's own store, so nothing the session wrote can be read
back (the pool its objects borrow from is not touched); then checked: the copy's own store must hold no object at all
(``git count-objects -v``: everything it needs is the pool's). The session's own venv beside the copy is removed
(`swebench_run.session_venv` makes it again from the shared
one). A ``verinoda_guided`` copy then gets its snapshot back. The study's results, transcripts and kept reproductions are
outside the copies and are not touched.
"""

from __future__ import annotations

import json
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from guard_run import _force_remove, git_env, run

VERINODA_FILES = (".verinoda", ".claude", ".mcp.json")


def git(copy: Path, *args: str) -> tuple[int, str]:
    rc, out, err, _ = run(["git", *args], copy, git_env(), timeout=1800)
    return rc, (out or "") + (err or "")


def pristine(copy: Path, base: str) -> bool:
    return git(copy, "rev-parse", "HEAD")[1].strip() == base and not git(copy, "status", "--porcelain")[1].strip()


def copy_tree(src: Path, dest: Path) -> None:
    if src.is_dir():
        shutil.copytree(src, dest)
    elif src.is_file():
        shutil.copy2(src, dest)


def snapshot(copy: Path, base: str, dest: Path) -> str:
    if dest.exists():
        return "kept"
    if not (copy / ".verinoda").is_dir():
        return "SKIPPED: no .verinoda (not set up)"
    if not pristine(copy, base):
        return "REFUSED: not at its base commit with nothing changed (a session ran here?)"
    tmp = dest.with_name(dest.name + ".part")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    for name in VERINODA_FILES:
        copy_tree(copy / name, tmp / name)
    tmp.rename(dest)
    return "saved"


def reset(copy: Path, base: str, snap: Path | None) -> str:
    if snap is not None and not (snap / ".verinoda").is_dir():
        return "REFUSED: no snapshot"
    steps = [("checkout", "-q", "-f", "--detach", base), ("reset", "-q", "--hard", base)]
    for args in steps:
        rc, out = git(copy, *args)
        if rc:
            return f"FAILED git {' '.join(args)}: {out[-200:]}"
    refs = git(copy, "for-each-ref", "--format=%(refname)")[1].split()
    for ref in refs:
        git(copy, "update-ref", "-d", ref)
    for args in (("reflog", "expire", "--expire=now", "--all"), ("clean", "-ffdxq"),
                 ("gc", "-q", "--prune=now")):
        rc, out = git(copy, *args)
        if rc:
            return f"FAILED git {' '.join(args)}: {out[-200:]}"
    # the copy's own store must be empty: every object it needs is the pool's, so whatever the session wrote is gone
    counts = dict(x.split(": ", 1) for x in git(copy, "count-objects", "-v")[1].splitlines() if ": " in x)
    left = {k: counts.get(k) for k in ("count", "in-pack")}
    if left != {"count": "0", "in-pack": "0"} or not pristine(copy, base):
        return f"FAILED: objects left in the copy's store ({left}) or changes"
    venv = copy.parent / f"env-{copy.name}"
    if venv.exists():
        shutil.rmtree(venv, onerror=_force_remove)
    if snap is not None:
        for name in VERINODA_FILES:
            copy_tree(snap / name, copy / name)
    return "reset" + (" and restored" if snap is not None else "")


def main(argv: list[str]) -> int:
    cmd, work, tasks_path, snaps = argv[0], Path(argv[1]), Path(argv[2]), Path(argv[3])
    only = set(argv[argv.index("--only") + 1].split(",")) if "--only" in argv else None
    arms = (argv[argv.index("--arms") + 1] if "--arms" in argv else "none,verinoda_guided").split(",")
    tasks = [t for t in json.loads(tasks_path.read_text(encoding="utf-8"))["tasks"] if only is None or t["id"] in only]

    def one(item: tuple[dict, str]) -> str:
        t, arm = item
        copy = work / "copies" / t["id"] / arm
        if not (copy / ".git").exists():
            return f"{t['id']}:{arm}: no copy"
        if cmd == "snapshot":
            return f"{t['id']}:{arm}: {snapshot(copy, t['base_commit'], snaps / t['id'])}"
        return f"{t['id']}:{arm}: {reset(copy, t['base_commit'], snaps / t['id'] if arm == 'verinoda_guided' else None)}"

    if cmd == "snapshot":  # a copy still being set up has half an index: only those whose setup finished (builds.json)
        built = json.loads((work / "builds.json").read_text(encoding="utf-8")) if (work / "builds.json").exists() else {}
        tasks = [t for t in tasks if f"{t['id']}:verinoda_guided" in built]
    items = [(t, a) for t in tasks for a in (["verinoda_guided"] if cmd == "snapshot" else arms)]
    bad = 0
    with ThreadPoolExecutor(3) as pool:
        for line in pool.map(one, items):
            print(line, flush=True)
            bad += any(w in line for w in ("FAILED", "REFUSED"))
    print(f"{len(items)} copies, {bad} failed or refused", flush=True)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
