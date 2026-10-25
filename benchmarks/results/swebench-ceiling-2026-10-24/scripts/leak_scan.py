"""Scan the sessions of a SWE-bench run for reads or commands that reach outside the session's own copy."""
import json
import re
import sys
from pathlib import Path

results = Path(sys.argv[1])
root = Path.home() / ".claude" / "projects"
SUSPECT = re.compile(r"tasks\.json|results\.jsonl|predictions-|lite\.parquet|swebench-data|swebench-run/work/(?!copies)|"
                     r"\.\./\.\.|git (fetch|pull|log --all)|curl|wget|pip install|github\.com|WebFetch|WebSearch", re.I)
rows = [json.loads(x) for x in results.read_text(encoding="utf-8").splitlines() if x.strip()]
missing, hits = 0, []
for r in rows:
    sid = r.get("session_id") or ""
    found = list(root.glob(f"*/{sid}.jsonl")) if sid else []
    if not found:
        missing += 1
        continue
    copy = f"copies/{r['id']}/{r['arm']}".lower()
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
            paths = re.findall(r"[A-Za-z]:/[^\"' ]+|/c/[^\"' ]+", text)
            outside = [p for p in paths if copy not in p.lower()]
            if SUSPECT.search(text) or outside:
                hits.append((r["id"], r["arm"], x.get("name"), text[:200], outside[:3]))
print(f"{len(rows)} sessions, {missing} transcripts not found, {len(hits)} suspicious tool calls")
for h in hits[:60]:
    print(h)
