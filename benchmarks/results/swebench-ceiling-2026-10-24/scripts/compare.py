"""Paired comparison of two attempts on the dev instances graded in both: the 2x2 table, the exact McNemar test (two-sided
binomial on the discordant pairs) and a bootstrap 95 % interval for the difference in resolved share.

    python compare.py A B [--list]

A and B: "d184:plain", "d184:guided" (D184's official grades) or "RUN:ARM" with ARM none/guided (local calibrated, amendment
2's regrade, amendment 6's re-runs: the last session counts). --list prints the discordant instances.
"""

import json
import random
import sys
from math import comb
from pathlib import Path

TMP = Path(__file__).resolve().parent
sys.path.insert(0, str(TMP))
from final_grades import final

CEILING = {r["id"]: r for r in json.loads((TMP / "ceiling.json").read_text(encoding="utf-8"))}


def grades(spec: str) -> dict[str, bool]:
    run, arm = spec.split(":")
    if run == "d184":
        return {i: bool(r[arm]) for i, r in CEILING.items() if r[arm] is not None}
    got = final(run, "none" if arm in ("none", "plain") else "verinoda_guided")
    return {i: bool(v["resolved"]) for i, v in got.items() if v["resolved"] is not None}


def mcnemar(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(comb(n, k) for k in range(min(b, c) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def main() -> None:
    a_spec, b_spec = sys.argv[1], sys.argv[2]
    a, b = grades(a_spec), grades(b_spec)
    ids = sorted(set(a) & set(b))
    both = sum(a[i] and b[i] for i in ids)
    only_a = [i for i in ids if a[i] and not b[i]]
    only_b = [i for i in ids if b[i] and not a[i]]
    rng = random.Random(20261024)
    diffs = []
    for _ in range(10000):
        s = [rng.choice(ids) for _ in ids]
        diffs.append((sum(b[i] for i in s) - sum(a[i] for i in s)) / len(s))
    diffs.sort()
    print(f"{len(ids)} instances graded in both: {a_spec} {sum(a[i] for i in ids)}, {b_spec} {sum(b[i] for i in ids)}; "
          f"both {both}, only {a_spec} {len(only_a)}, only {b_spec} {len(only_b)}, neither "
          f"{len(ids) - both - len(only_a) - len(only_b)}")
    print(f"difference ({b_spec} - {a_spec}): {(sum(b[i] for i in ids) - sum(a[i] for i in ids)) / len(ids):+.3f}, "
          f"bootstrap 95 % [{diffs[250]:+.3f}, {diffs[9749]:+.3f}]; exact McNemar p = "
          f"{mcnemar(len(only_a), len(only_b)):.3f}")
    if "--list" in sys.argv:
        print(f"only {a_spec}:", " ".join(only_a))
        print(f"only {b_spec}:", " ".join(only_b))


if __name__ == "__main__":
    main()
