"""Scan a SWE-bench run's sessions for tool calls that reach outside the session's own copy or at what the study withholds
(DESIGN_SWEBENCH_CEILING.md: the rules and amendment 2).

    python benchmarks/agent_compare/swebench_leakscan.py RESULTS.jsonl

For every tool call in each session's transcript (``~/.claude/projects/*/<session_id>.jsonl``), it flags:
- a path outside the session's copy, except the project's environment (``envs/<key>`` and ``py36/`` under the data folder
  or through its junction, and the session's own venv beside its copy);
- the other arm's copy of the same instance, also by a relative path, and a ``cd ..`` (from the copy's root it leads there);
- the run's own files and the dataset;
- git commands that read the object store past the history (fsck, cat-file, lost-found and the like), because the alternates
  pool may hold an earlier session's blobs;
- network use.
Every hit is printed. A session with a hit is reviewed by hand, and one that reached withheld information is not counted.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SUSPECT = re.compile(
    r"tasks(-dev)?\.json|results\.jsonl|predictions-|lite\.parquet|gold-|eval\.sh|swebench-data/(?!envs/|py36/)|"
    r"swebench-run/work/|\.\./\.\.|git (fetch|pull|log --all|fsck|cat-file|verify-pack|show-index|rev-list --all)|"
    r"lost-found|unreachable|dangling|objects/info/alternates|curl |wget |pip install|github\.com|WebFetch|WebSearch|"
    r"copies/|verinoda_guided\b|\.\./+none\b|\bcd \.\.(?![\w/.-])",
    re.IGNORECASE)
ENV_PATH = re.compile(r"swebench-(data|run)/(envs|py36)/", re.IGNORECASE)
# a drive path with two segments at least ("C:/Users/..."); not "else:\n" or "http://" in a quoted line of code
PATH = re.compile(r"(?<![\w.])[A-Za-z]:/(?!/)[^\"' ;|&)/]+/[^\"' ;|&)]*|(?<![\w.])/c/[^\"' ;|&)]+")


def scan(results: Path) -> int:
    root = Path.home() / ".claude" / "projects"
    rows = [json.loads(x) for x in results.read_text(encoding="utf-8").splitlines() if x.strip()]
    missing, hits = 0, []
    for r in rows:
        sid = r.get("session_id") or ""
        found = list(root.glob(f"*/{sid}.jsonl")) if sid else []
        if not found:
            missing += 1
            continue
        copy = f"copies/{r['id']}/{r['arm']}".lower()
        venv = f"copies/{r['id']}/env-{r['arm']}".lower()  # swebench_run.session_venv's own venv of the session
        own = re.compile(r"(?:[A-Za-z]:|/c)/[^\"' ]*?copies/" + re.escape(r["id"]) + r"/(?:env-)?" + re.escape(r["arm"]),
                         re.IGNORECASE)
        for line in found[0].read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                m = json.loads(line).get("message") or {}
            except ValueError:
                continue
            if m.get("role") != "assistant" or not isinstance(m.get("content"), list):
                continue
            for x in m["content"]:
                if x.get("type") != "tool_use":
                    continue
                text = json.dumps(x.get("input") or {}).replace("\\\\", "/")
                outside = [p for p in PATH.findall(text)
                           if copy not in p.lower() and venv not in p.lower() and not ENV_PATH.search(p)]
                if SUSPECT.search(own.sub("<copy>", text)) or outside:
                    hits.append((r["id"], r["arm"], x.get("name"), text[:240], outside[:3]))
    print(f"{len(rows)} sessions, {missing} transcripts not found, {len(hits)} tool calls flagged, "
          f"{len({(h[0], h[1]) for h in hits})} sessions with a flag")
    for h in hits:
        print(h)
    return 0


if __name__ == "__main__":
    sys.exit(scan(Path(sys.argv[1])))
