"""Copy the final run's files from the work folder into the repository's results folder (copy, never move).

    python assemble_results.py WORK_DIR RESULTS_DIR

Writes under RESULTS_DIR only (benchmarks/results/claims-rerun-2026-10-13/); refuses to run when it exists. README.md is written by
hand and is not touched here. The superseded zero-call appendix is copied whole; its README gets a header note that maps the
work-folder paths it names to this folder, and the one sentence about the 63-row backup is changed to say the backup is kept.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

FILES = ["config.json", "tasks.json", "results.jsonl", "judge.jsonl", "mechanical.jsonl", "mechanical-strict.jsonl", "summary.json",
         "hand_check.json", "hand_check_key.json", "hand_check.md"]
ANALYSIS = ["analyze_sessions.py", "compare_d185.py", "make_tables.py", "dry_plan.py", "split_superseded.py", "move_usage.py",
            "probe_deferral.py", "probe_prompt_tools.txt", "probe-p1-debug-excerpt.log", "analysis.json", "d185-comparison.json",
            "hand_reading_six.json", "tables.md", "dry-plan.json"]
LOGS = ["final-run.started", "final-step1-rerun.log", "final-step2.started", "final-step2-cost-sample.log", "final-step3.started",
        "final-step3-score.log", "final-step3b-mech-strict.log"]

NOTE = """> **Note on paths (appendix copy).** This folder is a copy of `C:/vbench-claims-rerun/superseded-zero-call/`. Where the text below
> names `../analysis/` it means this results folder's `analysis/` (the scripts and `probe-p1-debug-excerpt.log`); `../results.jsonl`,
> `../config.json` and `../logs/` mean the results folder's `results.jsonl`, `config.json` and `logs/` (its `results.jsonl` holds the
> 24 plain rows and the 39 rows of the re-run, not the 24 alone); `../probe/` (the p2 result and the coordinator's probe folders) and
> `../usage/` of the work folder are not copied: the 39 usage logs of these sessions are in `usage/` here, and the probe results
> are summarised in the results folder's README. The results folder's own `usage/` holds the re-run's logs.

"""


def main() -> int:
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    if dst.exists():
        print("refusing: the results folder exists")
        return 1
    dst.mkdir(parents=True)
    for name in FILES:
        if (src / name).is_file():
            shutil.copy2(src / name, dst / name)
        else:
            print("missing:", name)
    shutil.copytree(src / "usage", dst / "usage")
    (dst / "logs").mkdir()
    for name in LOGS:
        if (src / "logs" / name).is_file():
            shutil.copy2(src / "logs" / name, dst / "logs" / name)
        else:
            print("missing log:", name)
    (dst / "analysis").mkdir()
    for name in ANALYSIS:
        if (src / "analysis" / name).is_file():
            shutil.copy2(src / "analysis" / name, dst / "analysis" / name)
        else:
            print("missing analysis file:", name)
    shutil.copytree(src / "superseded-zero-call", dst / "superseded-zero-call")
    readme = dst / "superseded-zero-call" / "README.md"
    text = readme.read_text(encoding="utf-8")
    first_blank = text.index("\n\n") + 2  # after the title line
    text = text[:first_blank] + NOTE + text[first_blank:]
    old = "a backup so the split can be checked; delete it if the split is accepted"
    assert old in text
    text = text.replace(old, "a backup of the split, kept")
    readme.write_text(text, encoding="utf-8", newline="\n")
    print("copied to", dst)
    return 0


if __name__ == "__main__":
    sys.exit(main())
