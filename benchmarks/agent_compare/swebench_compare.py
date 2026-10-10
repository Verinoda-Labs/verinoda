"""Compare two SWE-bench evaluation reports of the study (DESIGN_SWEBENCH.md): the share resolved in each arm and the paired difference.

    python benchmarks/agent_compare/swebench_compare.py PLAIN_REPORT.json GUIDED_REPORT.json TASKS.json [OUT.json]

PLAIN_REPORT / GUIDED_REPORT: the evaluation reports of the arms ``none`` and ``verinoda_guided`` (a JSON object with the list
``resolved_ids``, as the SWE-bench harness writes it); TASKS.json: ``tasks.json`` of the run, whose instances are the sample.
An instance missing from a report counts as not resolved in that arm, and is listed. The paired comparison is over the
instances in TASKS.json: how many were resolved in both, in one arm only, in neither; the difference of the shares with a
bootstrap 95 % interval (seed 20261010, 10,000 resamples) and an exact two-sided McNemar test on the instances that differ.
"""

from __future__ import annotations

import json
import random
import sys
from math import comb
from pathlib import Path


def load(path: Path) -> tuple[set[str], set[str] | None]:
    """The resolved ids of a report, and its ``completed_ids`` (None when the report has none)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    for key in ("resolved_ids", "resolved"):
        if isinstance(data.get(key), list):
            done = data.get("completed_ids")
            return set(data[key]), set(done) if isinstance(done, list) else None
    raise SystemExit(f"error: {path} has no list `resolved_ids`; is it an evaluation report of the SWE-bench harness?")


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact p of b against c discordant pairs under a fair coin."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2**n)


def main() -> int:
    (plain, plain_done), (guided, guided_done) = load(Path(sys.argv[1])), load(Path(sys.argv[2]))
    ids = [t["id"] for t in json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))["tasks"]]
    a = [i in plain for i in ids]
    g = [i in guided for i in ids]
    both = sum(x and y for x, y in zip(a, g))
    only_plain = sum(x and not y for x, y in zip(a, g))
    only_guided = sum(y and not x for x, y in zip(a, g))
    neither = len(ids) - both - only_plain - only_guided
    diffs = [int(y) - int(x) for x, y in zip(a, g)]
    rnd = random.Random(20261010)
    means = sorted(sum(rnd.choices(diffs, k=len(diffs))) / len(diffs) for _ in range(10000))
    out = {
        "instances": len(ids), "resolved_plain": sum(a), "resolved_guided": sum(g),
        "share_plain": round(sum(a) / len(ids), 3), "share_guided": round(sum(g) / len(ids), 3),
        "both": both, "only_plain": only_plain, "only_guided": only_guided, "neither": neither,
        "difference_guided_minus_plain": round(sum(diffs) / len(diffs), 3),
        "ci95": [round(means[250], 3), round(means[9750], 3)],
        "mcnemar_exact_p": round(mcnemar_exact(only_plain, only_guided), 4),
        # instances the harness did not finish (an error, or not in the predictions): counted as not resolved, listed here
        "not_completed_plain": [i for i in ids if plain_done is not None and i not in plain_done],
        "not_completed_guided": [i for i in ids if guided_done is not None and i not in guided_done],
        "claim": ("a difference: the interval excludes zero" if not (means[250] <= 0 <= means[9750])
                  else "no measured difference: the interval includes zero"),
    }
    text = json.dumps(out, indent=1, ensure_ascii=False)
    if len(sys.argv) > 4:
        Path(sys.argv[4]).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
