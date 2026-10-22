"""Old (the base commit's worktree) and new (this branch) code timed back to back on the same inputs.

Each variant runs `python -m verinoda ...` / `python -c ...` with its own tree as the working directory, so the
interpreter imports that tree's package (cwd first on sys.path). Wall time, best of N.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

PY = r"C:\Users\me\Desktop\verinoda-symbiosis\.venv\Scripts\python.exe"
OLD = Path(r"C:\Users\me\Desktop\vs-baseline")
NEW = Path(r"C:\Users\me\Desktop\verinoda-symbiosis")
S = Path(sys.argv[1])
ORDERS = S / "setup_try" / "orders_app"
SQLMODEL = S / "sqlmodel"
env = dict(os.environ, PYTHONIOENCODING="utf-8")
env.pop("VERINODA_USAGE_LOG", None)


def wall(tree: Path, args: list[str]) -> float:
    t = time.perf_counter()
    r = subprocess.run([PY, *args], cwd=tree, env=env, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    d = time.perf_counter() - t
    if r.returncode not in (0, 1, 3, 4):
        raise SystemExit(f"{tree.name} {args[:4]} exit {r.returncode}: {r.stderr[-400:]}")
    return d


def best(n: int, args: list[str]) -> dict:
    out = {"old": [], "new": []}
    for _ in range(n):
        for name, tree in (("old", OLD), ("new", NEW)):
            out[name].append(wall(tree, args))
    return {k: round(min(v), 3) for k, v in out.items()}


rows = []
rows.append(("python -c pass", best(5, ["-c", "pass"])))
rows.append(("import verinoda.cli", best(5, ["-c", "import verinoda.cli"])))
rows.append(("verinoda --help", best(5, ["-m", "verinoda", "--help"])))
rows.append(("graph-state (orders_app)", best(5, ["-m", "verinoda", "graph-state", "--json", "--repo", str(ORDERS)])))
rows.append(("check gitexec.py --no-cache (145 sites)",
             best(3, ["-m", "verinoda", "check", "verinoda/gitexec.py", "--json", "--no-cache", "--repo", str(OLD)])))
q = "How does Session.exec run a select statement?"
rows.append(("analyze flow question (sqlmodel)",
             best(3, ["-m", "verinoda", "analyze", q, "--json", "--repo", str(SQLMODEL)])))
rows.append(("check cli.py --no-cache (6,244 sites)",
             best(1, ["-m", "verinoda", "check", "verinoda/cli.py", "--json", "--no-cache", "--repo", str(OLD)])))
for name, r in rows:
    print(f"{name:45s} old {r['old']:8.3f} s   new {r['new']:8.3f} s")
(S / "measure.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
