"""Usage-limit rows (DESIGN_SWEBENCH_CEILING.md, amendment 9): a session whose result is the account's usage-limit message
is not a session of the study. move(RUN_DIR) moves each such row, its grade rows (first grade and regrade), its prediction
lines, its kept reproductions and its evaluation log beside the run's own, so that its lane runs again in the same run and
the evaluator grades the new session. Only while no runner of the run (either arm) is alive: results.jsonl is theirs.
Grades are moved as lines, never read or printed.

    python limit_rows.py RUN_DIR [RUN_DIR ...]
"""

import json
import os
import re
import shutil
import sys
from pathlib import Path

LIMIT = re.compile(r"you.ve hit your (\w+ )?limit", re.IGNORECASE)


def is_limit(row: dict) -> bool:
    return bool(row.get("is_error")) and bool(LIMIT.search(row.get("final") or ""))


def _split(path: Path, moved: set[str]) -> int:
    """Move the lines of PATH whose instance_id is in MOVED to PATH's "-limit" file beside it; returns how many."""
    if not path.exists():
        return 0
    keep, out = [], []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            iid = json.loads(line).get("instance_id") if line.strip() else None
        except ValueError:
            iid = None
        (out if iid in moved else keep).append(line)
    if out:
        with path.with_name(f"{path.stem}-limit{path.suffix}").open("a", encoding="utf-8", newline="\n") as f:
            f.write("".join(x + "\n" for x in out))
        tmp = path.with_suffix(".tmp")
        tmp.write_text("".join(x + "\n" for x in keep), encoding="utf-8", newline="\n")
        os.replace(tmp, path)
    return len(out)


def _aside(src: Path, dest: Path) -> bool:
    if not src.exists():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    n = 1
    while dest.exists():
        n += 1
        dest = dest.with_name(f"{src.name}.{n}")
    shutil.move(str(src), str(dest))
    return True


def move(run_dir: Path) -> int:
    """Move RUN_DIR's usage-limit rows aside (see the module's text); returns how many rows moved."""
    results = run_dir / "results.jsonl"
    if not results.exists():
        return 0
    keep, out = [], []
    for line in results.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        (out if is_limit(json.loads(line)) else keep).append(line)
    if not out:
        return 0
    with (run_dir / "results-limit.jsonl").open("a", encoding="utf-8", newline="\n") as f:
        f.write("".join(x + "\n" for x in out))
    tmp = results.with_suffix(".tmp")
    tmp.write_text("".join(x + "\n" for x in keep), encoding="utf-8", newline="\n")
    os.replace(tmp, results)
    logs = run_dir.parent.parent / "logs"
    for arm in sorted({json.loads(x)["arm"] for x in out}):
        ids = {json.loads(x)["id"] for x in out if json.loads(x)["arm"] == arm}
        for name in (f"eval-{arm}.jsonl", f"eval-{arm}-regrade.jsonl", f"predictions-{arm}.jsonl", f"preds-{arm}.jsonl"):
            _split(run_dir / name, ids)
        for iid in sorted(ids):
            _aside(run_dir / "scratch" / f"{iid}--{arm}", run_dir / "scratch-limit" / f"{iid}--{arm}")
            _aside(logs / f"{run_dir.name}-{arm}" / f"{iid}.log", logs / f"{run_dir.name}-{arm}-limit" / f"{iid}.log")
    return len(out)


if __name__ == "__main__":
    for d in sys.argv[1:]:
        print(f"{Path(d).name}: {move(Path(d))} usage-limit rows moved aside", flush=True)
