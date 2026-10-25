"""One attempt as the selector reads it (swebench_select.py RUN_DIR), after amendment 6's re-runs: per lane the session
that counts (<run>-r2, else <run>-r1, else <run>), its results row and its reproductions (scratch/<id>--<arm>/).

    python merge_attempt.py RUN OUT_NAME

Writes runs/OUT_NAME/results.jsonl and runs/OUT_NAME/scratch/ (replaced if present).
"""

import json
import shutil
import sys
from pathlib import Path

DATA = Path("C:/Users/ozcin/swebench-data")


def rows(run: str) -> dict[tuple[str, str], str]:
    f = DATA / "runs" / run / "results.jsonl"
    out = {}
    for line in f.read_text(encoding="utf-8").splitlines() if f.exists() else []:
        if line.strip():
            r = json.loads(line)
            out[(r["id"], r["arm"])] = line
    return out


def main() -> None:
    run, name = sys.argv[1], sys.argv[2]
    attempts = [run, f"{run}-r1", f"{run}-r2"]
    got = [rows(a) for a in attempts]
    out = DATA / "runs" / name
    shutil.rmtree(out / "scratch", ignore_errors=True)
    (out / "scratch").mkdir(parents=True, exist_ok=True)
    lines, moved = [], 0
    for lane in got[0]:
        k = max(i for i in range(3) if lane in got[i])
        moved += k > 0
        lines.append(got[k][lane])
        src = DATA / "runs" / attempts[k] / "scratch" / f"{lane[0]}--{lane[1]}"
        if src.is_dir():
            shutil.copytree(src, out / "scratch" / src.name)
    (out / "results.jsonl").write_text("".join(x + "\n" for x in lines), encoding="utf-8", newline="\n")
    print(f"{name}: {len(lines)} lanes from {run}, {moved} of them from a re-run")


if __name__ == "__main__":
    main()
