"""Score the SWE-bench Lite study without Docker (DESIGN_SWEBENCH.md): the proxies the study can measure here, paired per instance.

    python benchmarks/agent_compare/swebench_score.py RESULTS.jsonl [OUT.json]

The resolved share is NOT computed here: it needs the official evaluation of the predictions (SWEBENCH_EVAL.md). What is: whether a
patch exists and applies to the base commit, the gold patch's files it covers, extra files, patch size, turns, tokens, dollars,
seconds, and the calls to Verinoda's tools. Differences are paired (Verinoda arm minus plain arm, per instance) with a bootstrap
95 % interval over instances (seed 20261010, 10,000 resamples).
"""

from __future__ import annotations

import json
import random
import statistics as st
import sys
from pathlib import Path

PLAIN, GUIDED = "none", "verinoda_guided"


def boot(diffs: list[float], n: int = 10000, seed: int = 20261010) -> tuple[float, float, float]:
    """Mean difference and its bootstrap 95 % interval."""
    rnd = random.Random(seed)
    k = len(diffs)
    means = sorted(sum(rnd.choices(diffs, k=k)) / k for _ in range(n))
    return sum(diffs) / k, means[int(0.025 * n)], means[int(0.975 * n)]


def main() -> int:
    rows = [json.loads(line) for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if line.strip()]
    by: dict[str, dict[str, dict]] = {}
    for r in rows:
        by.setdefault(r["id"], {})[r["arm"]] = r
    pairs = {i: a for i, a in by.items() if PLAIN in a and GUIDED in a}
    out: dict = {"instances": len(by), "pairs": len(pairs), "sessions": len(rows)}

    def arm_rows(arm: str) -> list[dict]:
        return [a[arm] for a in pairs.values()]

    for arm in (PLAIN, GUIDED):
        a = arm_rows(arm)
        out[arm] = {
            "patch_nonempty": sum(r["patch_lines"] > 0 for r in a), "applies_to_base": sum(bool(r["applies"]) for r in a),
            "covers_all_gold_files": sum(bool(r["covers_gold"]) for r in a), "touches_a_gold_file": sum(r["overlap"] > 0 for r in a),
            "with_extra_files": sum(r["extra_files"] > 0 for r in a), "touched_test_files": sum(bool(r["touched_tests"]) for r in a),
            "session_errors": sum(bool(r["is_error"]) for r in a),
            "cost_usd_total": round(sum(r["cost_usd"] or 0 for r in a), 2),
            "median_turns": st.median(r["num_turns"] or 0 for r in a), "median_seconds": st.median(r["seconds"] for r in a),
            "median_patch_lines": st.median(r["patch_lines"] for r in a),
            "input_tokens_total": sum(r["input_tokens"] for r in a), "output_tokens_total": sum(r["output_tokens"] for r in a),
        }
    g = arm_rows(GUIDED)
    out[GUIDED]["analyze_called"] = sum(bool(r["verinoda_tools"]["calls"].get("analyze")) for r in g)
    out[GUIDED]["code_check_called"] = sum(bool(r["verinoda_tools"]["calls"].get("code_check")) for r in g)
    out[GUIDED]["verinoda_before_first_code_tool"] = sum(bool(r["verinoda_tools"]["before_first_code_tool"]) for r in g)
    out[GUIDED]["no_verinoda_call"] = sum(not r["verinoda_tools"]["calls"] for r in g)
    out[PLAIN]["verinoda_calls"] = sum(r["verinoda_calls"] for r in arm_rows(PLAIN))

    paired = {}
    for key, label in (("cost_usd", "dollars"), ("num_turns", "turns"), ("seconds", "seconds"), ("input_tokens", "input tokens"),
                       ("output_tokens", "output tokens"), ("patch_lines", "patch lines"), ("extra_files", "extra files")):
        d = [float(a[GUIDED][key] or 0) - float(a[PLAIN][key] or 0) for a in pairs.values()]
        m, lo, hi = boot(d)
        paired[label] = {"mean_difference": round(m, 4), "ci95": [round(lo, 4), round(hi, 4)],
                         "guided_more": sum(x > 0 for x in d), "same": sum(x == 0 for x in d), "guided_less": sum(x < 0 for x in d)}
    out["paired_guided_minus_plain"] = paired
    same_files = sum(a[GUIDED]["patch_files"] == a[PLAIN]["patch_files"] for a in pairs.values())
    same_patch = sum(a[GUIDED]["patch"] == a[PLAIN]["patch"] for a in pairs.values())
    out["same_file_set"] = same_files
    out["identical_patch"] = same_patch
    out["gold_cover_differs"] = [i for i, a in pairs.items() if a[GUIDED]["covers_gold"] != a[PLAIN]["covers_gold"]]
    out["applies_differs"] = [i for i, a in pairs.items() if bool(a[GUIDED]["applies"]) != bool(a[PLAIN]["applies"])]
    out["by_repo"] = {}
    for i, a in pairs.items():
        repo = i.split("__")[0]
        d = out["by_repo"].setdefault(repo, {"n": 0, "guided_cost": 0.0, "plain_cost": 0.0})
        d["n"] += 1
        d["guided_cost"] += a[GUIDED]["cost_usd"] or 0
        d["plain_cost"] += a[PLAIN]["cost_usd"] or 0
    for d in out["by_repo"].values():
        d["guided_cost"], d["plain_cost"] = round(d["guided_cost"], 2), round(d["plain_cost"], 2)
    text = json.dumps(out, indent=1, ensure_ascii=False)
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
