"""C3's two arms paired per instance on the selected patch (c3_score.py's selection, the same final grades): the
comparison the design makes for every run, here for the selector's output.

    python c3_pair.py
"""

import json

from c3_score import ATTEMPTS, DATA, MERGED, patches
from final_grades import final
from report import paired


def selected(arm: str) -> dict[str, bool]:
    grades = [final(run, arm) for run in ATTEMPTS]
    merged = [patches(name, arm) for name in MERGED]
    f = DATA / "runs" / "c3-select" / f"select-{arm}.jsonl"
    chosen = {r["instance_id"]: r["model_patch"] for r in map(json.loads, f.read_text(encoding="utf-8").splitlines())}
    out: dict[str, bool] = {}
    for iid in sorted(set().union(*(set(g) for g in grades))):
        k = next((k for k in range(3) if iid in chosen and merged[k].get(iid) == chosen[iid]), None)
        v = False if k is None else grades[k].get(iid, {}).get("resolved")
        if v is not None and not (k is None and iid in chosen):
            out[iid] = bool(v)
    return out


if __name__ == "__main__":
    plain, guided = selected("none"), selected("verinoda_guided")
    print(f"C3 selected, guided - plain: {paired(plain, guided)}")
    print("  guided only:", sorted(i for i in plain if i in guided and guided[i] and not plain[i]))
    print("  plain only:", sorted(i for i in plain if i in guided and plain[i] and not guided[i]))
