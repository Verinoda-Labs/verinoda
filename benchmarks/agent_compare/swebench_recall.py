"""How much of the upstream fix a patch reproduces that the issue does not give (DESIGN_SWEBENCH_CEILING.md, amendment 7).

    python benchmarks/agent_compare/swebench_recall.py DATA RESULTS.jsonl ARM

A model that recalls the upstream fix writes it nearly verbatim, including what the issue does not determine (a message's
wording, a docstring, exact numbers). The measure: the gold patch's added lines in non-test files, whitespace removed, 8
characters or more, leaving out those the problem statement already holds (whitespace removed); `recall` is the share of
them the patch also adds, None when none is left. A patch is "verbatim" at recall >= 0.9. Analysis only: the gold patch is
read after grading, never by a session. Prints one line per instance of ARM in RESULTS (a `swebench_run.py` results file)
and the mean.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

TEST_FILE = re.compile(r"(^|/)(tests?|testing)/|(^|/)test_[^/]*\.py$|_tests?\.py$")
VERBATIM = 0.9


def added_lines(patch: str) -> list[str]:
    """The patch's added lines in non-test files, whitespace removed, 8 characters or more."""
    out, skip = [], False
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            skip = bool(TEST_FILE.search(line.split(" b/", 1)[-1]))
        elif line.startswith("+++"):
            # a diff written without git's header (the closed-book probe's) names its file here only
            skip = bool(TEST_FILE.search(line[3:].strip().removeprefix("b/")))
        elif skip:
            continue
        elif line.startswith("+"):
            text = re.sub(r"\s+", "", line[1:])
            if len(text) >= 8:
                out.append(text)
    return out


def recall(patch: str, gold: str, issue: str) -> float | None:
    given = re.sub(r"\s+", "", issue)
    wanted = [t for t in added_lines(gold) if t not in given]
    if not wanted:
        return None
    mine = set(added_lines(patch))
    return sum(t in mine for t in wanted) / len(wanted)


def main() -> int:
    import pyarrow.parquet as pq

    data, results, arm = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    lite = {r["instance_id"]: r for r in pq.read_table(data / "lite.parquet").to_pylist()}
    got = []
    for line in results.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            if r["arm"] == arm and r["id"] in lite:
                x = recall(r.get("patch") or "", lite[r["id"]]["patch"], lite[r["id"]]["problem_statement"])
                got.append(x)
                print(f"{r['id']}\t{'' if x is None else f'{x:.2f}'}")
    known = [x for x in got if x is not None]
    print(f"{len(got)} patches, {len(known)} measured, mean recall {sum(known) / max(len(known), 1):.2f}, "
          f"verbatim {sum(x >= VERBATIM for x in known)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
