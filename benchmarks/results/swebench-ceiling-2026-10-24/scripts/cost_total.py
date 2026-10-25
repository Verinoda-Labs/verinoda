"""The study's cost as Claude Code reports it (cost_usd per session; on a subscription it is usage, not dollars): every
session row of every run (re-runs and the usage-limit rows set aside included; the merged views c3-att-* hold no session
of their own), and the closed-book probe's replies from its log.

    python cost_total.py
"""

import collections
import json
import re
from pathlib import Path

RUNS = Path("C:/Users/ozcin/swebench-data/runs")
by_run: dict[str, float] = collections.defaultdict(float)
sessions: dict[str, int] = collections.Counter()
for f in sorted(RUNS.glob("*/results*.jsonl")):
    run = f.parent.name
    if run.startswith("c3-att-"):
        continue
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            by_run[run] += float(r.get("cost_usd") or 0)
            sessions[run] += 1
log = Path("C:/Users/ozcin/swebench-data/closedbook.log").read_text(encoding="utf-8", errors="replace")
probe = [float(x) for x in re.findall(r", \$([0-9.]+), ", log)]
for run in sorted(by_run):
    print(f"{run:14} {sessions[run]:4} rows  {by_run[run]:8.2f}")
print(f"{'closed-book':14} {len(probe):4} replies {sum(probe):8.2f}")
print(f"total {sum(by_run.values()) + sum(probe):.2f}")
