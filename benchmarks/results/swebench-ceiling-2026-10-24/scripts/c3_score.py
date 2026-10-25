"""C3's numbers (DESIGN_SWEBENCH_CEILING.md, amendments 4, 6, 7 and 9), once the selection (c3_select.sh) and amendment 2's
regrade are done. A selected patch is the patch of one attempt's session that counts; it takes that session's final grade
(final_grades.final: the last session after re-runs, the regrade, the leak review). Per arm: the selected resolved count
(C3's result), each attempt alone, pass@3 (any attempt resolved; a diagnostic only), the selected patches' recall
(amendment 7), and the selection paired with the first attempt (C4 Opus).

    python c3_score.py
"""

import json
import sys
from pathlib import Path

TMP = Path(__file__).resolve().parent
sys.path.insert(0, str(TMP))
sys.path.insert(0, "C:/Users/ozcin/Desktop/vwt-ceiling/benchmarks/agent_compare")
from swebench_recall import VERBATIM, recall

from final_grades import final
from report import lite, paired

DATA = Path("C:/Users/ozcin/swebench-data")
ATTEMPTS = ["c4-opus", "c3-opus-2", "c3-opus-3"]
MERGED = ["c3-att-1", "c3-att-2", "c3-att-3"]


def patches(name: str, arm: str) -> dict[str, str]:
    f = DATA / "runs" / name / "results.jsonl"
    rows = (json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip())
    return {r["id"]: r.get("patch") or "" for r in rows if r["arm"] == arm}


def main() -> None:
    data = lite()
    for arm, short in (("none", "plain"), ("verinoda_guided", "guided")):
        grades = [final(run, arm) for run in ATTEMPTS]
        merged = [patches(name, arm) for name in MERGED]
        f = DATA / "runs" / "c3-select" / f"select-{arm}.jsonl"
        chosen = {r["instance_id"]: r["model_patch"] for r in map(json.loads, f.read_text(encoding="utf-8").splitlines())}
        lanes = sorted(set().union(*(set(g) for g in grades)))
        sel: dict[str, bool | None] = {}
        source = {}
        for iid in lanes:
            k = next((k for k in range(3) if iid in chosen and merged[k].get(iid) == chosen[iid]), None)
            source[iid] = k
            sel[iid] = None if k is None and iid in chosen else \
                (False if k is None else grades[k].get(iid, {}).get("resolved"))
        unmatched = [i for i in lanes if i in chosen and source[i] is None]
        graded = {i: bool(v) for i, v in sel.items() if v is not None}
        print(f"C3 {short}: selected resolved {sum(graded.values())} of {len(graded)} graded ({len(lanes)} lanes; "
              f"{len(lanes) - len(chosen)} with no candidate patch; {len(unmatched)} selected patches matching no attempt"
              f"{': ' + ', '.join(unmatched) if unmatched else ''})")
        print(f"  chosen from attempt 1/2/3: {[sum(source[i] == k for i in lanes) for k in range(3)]}")
        for k, run in enumerate(ATTEMPTS):
            g = {i: bool(v["resolved"]) for i, v in grades[k].items() if v["resolved"] is not None}
            print(f"  attempt {k + 1} ({run}) alone: {sum(g.values())} of {len(g)}")
        any3 = {i: any(bool(grades[k].get(i, {}).get("resolved")) for k in range(3)) for i in lanes}
        print(f"  pass@3 (any attempt resolved; a diagnostic, not a score): {sum(any3.values())} of {len(lanes)}")
        rec = {i: recall(chosen[i], data[i]["patch"], data[i]["problem_statement"]) for i in graded if graded[i]}
        known = [x for x in rec.values() if x is not None]
        print(f"  recall among the selected resolved: mean {sum(known) / max(len(known), 1):.2f}, verbatim "
              f"{sum(x >= VERBATIM for x in known)}")
        first = {i: bool(v["resolved"]) for i, v in grades[0].items() if v["resolved"] is not None}
        print(f"  selection - attempt 1: {paired(first, graded)}")


if __name__ == "__main__":
    main()
