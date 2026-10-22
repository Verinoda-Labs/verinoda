"""Move the 39 per-session usage logs of the zero-call Verinoda sessions into superseded-zero-call/usage/ (move, not delete).

    python move_usage.py WORK_DIR

The re-run's sessions write to the same file names (``<task id>-verinoda_guided-r<repeat>.jsonl``) and the logger appends, so the
old two lines would sit at the head of the new logs. Each file is checked by sha256 before and after the move; usage/ stays as an
empty folder. Refuses to run when usage/ holds a file the 39 rows do not name, or when the target folder exists.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import time
from pathlib import Path


def main() -> int:
    w = Path(sys.argv[1])
    sup = w / "superseded-zero-call"
    src, dst = w / "usage", sup / "usage"
    rows = [json.loads(x) for x in (sup / "results-verinoda-zero-call.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    expected = {f"{r['id']}-{r['arm']}-r{r['repeat']}.jsonl" for r in rows}
    present = {p.name for p in src.iterdir()}
    if present != expected:
        print("refusing: usage/ differs from the 39 rows:", sorted(present ^ expected))
        return 1
    if dst.exists():
        print("refusing: superseded-zero-call/usage/ exists already")
        return 1
    dst.mkdir()
    manifest = {}
    for name in sorted(present):
        f = src / name
        data = f.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        shutil.move(str(f), str(dst / name))
        assert hashlib.sha256((dst / name).read_bytes()).hexdigest() == digest and not f.exists()
        manifest[name] = {"bytes": len(data), "sha256": digest, "lines": len(data.decode("utf-8").splitlines())}
    out = {"moved_at": time.strftime("%Y-%m-%d %H:%M:%S"), "files": len(manifest), "usage_left_in_place": len(list(src.iterdir())),
           "lines_per_file": sorted({m["lines"] for m in manifest.values()}), "manifest": manifest}
    (sup / "usage-move-manifest.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "manifest"}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
