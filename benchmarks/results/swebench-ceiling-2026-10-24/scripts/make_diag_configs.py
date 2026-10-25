"""The diagnostics' configs (DESIGN_SWEBENCH_CEILING.md, amendments 4, 5 and 9): C4 Opus's, each with its own "out", the
dataset and its "diag"; "only" is filled per batch by the orchestrator, and the instance lists come from amendment 5's rule
once C3 and the regrade are done. Writes configs/diag-{hints,tests}[-r1|-r2]-{none,guided}.json; an existing file is kept.

    python make_diag_configs.py
"""

import json
from pathlib import Path

DATA = Path("C:/Users/ozcin/swebench-data")

for diag in ("hints", "tests"):
    for rerun in ("", "-r1", "-r2"):
        for arm in ("none", "guided"):
            dest = DATA / "configs" / f"diag-{diag}{rerun}-{arm}.json"
            if dest.exists():
                print(f"{dest.name}: kept")
                continue
            cfg = json.loads((DATA / "configs" / f"c4-opus-{arm}.json").read_text(encoding="utf-8"))
            cfg.update({"out": (DATA / "runs" / f"diag-{diag}{rerun}").as_posix(), "dataset": (DATA / "lite.parquet").as_posix(),
                        "diag": diag, "only": []})
            dest.write_text(json.dumps(cfg, indent=1), encoding="utf-8", newline="\n")
            print(f"{dest.name}: written")
