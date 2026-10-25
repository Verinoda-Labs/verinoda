"""Each condition's grades after amendment 6's re-runs: per lane the last session counts (<run>-r2, else <run>-r1, else
<run>), graded locally (calibrated) and, for an unresolved row, as amendment 2's quiet-machine regrade says. A session the
leak review does not count (runs/not-counted.json: network use, withheld information) counts in neither the resolved
number nor the graded one.

    python final_grades.py RUN [RUN ...]

Prints per run and arm: lanes, graded, resolved (final), not counted, the flagged sessions (lost Bash PATH) in the first
attempt and in the last, and the sensitivity line (the first attempts, flagged sessions left out). Importable:
final(run, arm).
"""

import json
import sys
from pathlib import Path

DATA = Path("C:/Users/ozcin/swebench-data")
sys.path.insert(0, "C:/Users/ozcin/Desktop/vwt-ceiling/benchmarks/agent_compare")
from swebench_shellcheck import check

ARMS = ("none", "verinoda_guided")
_FLAGS: dict[str, bool] = {}
NOT_COUNTED = {(e["run"], e["id"], e["arm"]): e["reason"]
               for e in json.loads((DATA / "runs" / "not-counted.json").read_text(encoding="utf-8"))}


def rows(run: str) -> dict[tuple[str, str], dict]:
    f = DATA / "runs" / run / "results.jsonl"
    out = {}
    for line in f.read_text(encoding="utf-8").splitlines() if f.exists() else []:
        if line.strip():
            r = json.loads(line)
            out[(r["id"], r["arm"])] = r
    return out


def grades(run: str, arm: str) -> dict[str, bool | None]:
    f = DATA / "runs" / run / f"eval-{arm}.jsonl"
    out: dict[str, bool | None] = {}
    for line in f.read_text(encoding="utf-8").splitlines() if f.exists() else []:
        if line.strip():
            g = json.loads(line)
            out[g["instance_id"]] = g.get("resolved_calibrated")
    again = f.with_name(f"eval-{arm}-regrade.jsonl")
    for line in again.read_text(encoding="utf-8").splitlines() if again.exists() else []:
        if line.strip():
            g = json.loads(line)
            if g["instance_id"] in out and not out[g["instance_id"]]:
                out[g["instance_id"]] = g.get("resolved_calibrated")
    return out


def flagged(row: dict) -> bool:
    sid = row.get("session_id") or ""
    if sid not in _FLAGS:
        _FLAGS[sid] = check(sid) is not None
    return _FLAGS[sid]


def final(run: str, arm: str) -> dict[str, dict]:
    """Per instance: the run whose session counts, its grade (None: not graded yet), and the flags of the first and last."""
    attempts = [run, f"{run}-r1", f"{run}-r2"]
    got = [rows(a) for a in attempts]
    marks = [grades(a, arm) for a in attempts]
    out = {}
    for (iid, a), first in got[0].items():
        if a != arm:
            continue
        k = max(i for i in range(3) if (iid, arm) in got[i])
        dropped = NOT_COUNTED.get((attempts[k], iid, arm))
        first_dropped = NOT_COUNTED.get((run, iid, arm))
        out[iid] = {"run": attempts[k], "resolved": None if dropped else marks[k].get(iid), "not_counted": dropped,
                    "first_flagged": flagged(first), "last_flagged": flagged(got[k][(iid, arm)]),
                    "first_resolved": None if first_dropped else marks[0].get(iid)}
    return out


def main() -> None:
    for run in sys.argv[1:]:
        for arm in ARMS:
            f = final(run, arm)
            if not f:
                continue
            graded = [v for v in f.values() if v["resolved"] is not None]
            first_ok = [v for v in f.values() if not v["first_flagged"] and v["first_resolved"] is not None]
            print(f"{run} {arm}: {len(f)} lanes, {len(graded)} graded, {sum(bool(v['resolved']) for v in graded)} resolved "
                  f"(last session counts), {sum(bool(v['not_counted']) for v in f.values())} not counted; flagged: first "
                  f"{sum(v['first_flagged'] for v in f.values())}, last {sum(v['last_flagged'] for v in f.values())}, "
                  f"re-run so far {sum(v['run'] != run for v in f.values())}; sensitivity (first attempts, flagged left "
                  f"out): {sum(bool(v['first_resolved']) for v in first_ok)} of {len(first_ok)}")


if __name__ == "__main__":
    main()
