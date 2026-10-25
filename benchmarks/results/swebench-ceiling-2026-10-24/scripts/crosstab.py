"""One row per dev instance: the leaderboard (how many of the collected Lite submissions resolved it), OpenAI's annotations
(underspecified, false_negative: 0-3, empty when not annotated), and each of our attempts that has a grade: D184's two arms
(official), then every run's local calibrated grade per arm. Prints the table's summary; writes crosstab.csv beside it.

    python crosstab.py
"""

import csv
import json
import sys
from pathlib import Path

TMP = Path(__file__).resolve().parent
sys.path.insert(0, str(TMP))
from final_grades import final

DATA = Path("C:/Users/ozcin/swebench-data")
RUNS = ["c0-s1", "c1-s1", "c4-opus", "c4-fable", "c3-opus-2", "c3-opus-3", "c3-fable-2", "c3-fable-3", "diag-hints",
        "diag-tests"]
ARMS = {"none": "plain", "verinoda_guided": "guided"}


def num(v):
    return None if v in ("", None) else float(v)


rows = json.loads((TMP / "ceiling.json").read_text(encoding="utf-8"))
cols = ["d184:plain", "d184:guided"]
grades: dict[str, dict[str, bool | None]] = {r["id"]: {"d184:plain": r["plain"], "d184:guided": r["guided"]} for r in rows}
for run in RUNS:
    for arm, short in ARMS.items():
        # amendment 2's regrade and amendment 6's re-runs (the last session counts) are in final()
        got = {i: v["resolved"] for i, v in final(run, arm).items() if v["resolved"] is not None}
        if not got:
            continue
        col = f"{run}:{short}"
        cols.append(col)
        for iid, resolved in got.items():
            if iid in grades:
                grades[iid][col] = resolved

out = []
for r in rows:
    g = grades[r["id"]]
    ours = [c for c in cols if g.get(c)]
    out.append({"id": r["id"], "lite_solved": r["lite_solved"], "underspecified": num(r["underspecified"]),
                "false_negative": num(r["false_negative"]), "in_verified": r["in_verified"],
                **{c: ("" if c not in g else int(bool(g[c])) if g[c] is not None else "?") for c in cols},
                "ours_any": int(bool(ours)), "ours_which": " ".join(ours)})
with (TMP / "crosstab.csv").open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0]))
    w.writeheader()
    w.writerows(out)

n = len(out)
lb = sum(1 for o in out if o["lite_solved"] > 0)
print(f"{n} dev instances; columns: {', '.join(cols)}")
print(f"leaderboard (the {rows[0]['lite_subs']} Lite submissions collected): {lb} resolved by at least one, {n - lb} by none")
for c in cols:
    graded = [o for o in out if o[c] != ""]
    print(f"  {c:22} graded {len(graded):3}  resolved {sum(1 for o in graded if o[c] == 1):3}")
union = sum(o["ours_any"] for o in out)
both = sum(1 for o in out if o["ours_any"] or o["lite_solved"] > 0)
print(f"our attempts, any column (an oracle over attempts, not a score): {union}; with the leaderboard: {both}")
never = [o for o in out if not o["ours_any"]]
print(f"resolved by no attempt of ours ({len(never)}):")
for o in sorted(never, key=lambda o: o["lite_solved"]):
    print(f"  {o['id']:38} leaderboard {o['lite_solved']:3}  underspecified {o['underspecified']}  "
          f"false_negative {o['false_negative']}  verified {o['in_verified']}")
fn = [o for o in out if (o["false_negative"] or 0) >= 2]
print(f"false_negative >= 2 (the tests may reject a valid fix): {len(fn)}; of them resolved by an attempt of ours: "
      f"{sum(o['ours_any'] for o in fn)}; by the leaderboard: {sum(1 for o in fn if o['lite_solved'] > 0)}")
