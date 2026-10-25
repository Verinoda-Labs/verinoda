"""C1's guided first calls: did the answer say the index predates a changed file, which file, and did the server start
a background update? Re-counts the D196 finding from the transcripts (tool_result text of each session's first
analyze).

    python c1_stale.py RUN_DIR"""
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "C:/Users/ozcin/Desktop/vwt-ownrepo/benchmarks/agent_compare")
from guard_run import find_transcript  # noqa: E402

run = Path(sys.argv[1])
rows = []
for line in (run / "results.jsonl").read_text(encoding="utf-8").splitlines():
    r = json.loads(line)
    if r.get("arm") != "verinoda_guided" or not r.get("session_id"):
        continue
    t = find_transcript(r["session_id"])
    if not t:
        rows.append({"id": r["id"], "transcript": False})
        continue
    first_use, text = None, None
    for entry in t.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            e = json.loads(entry)
        except ValueError:
            continue
        content = (e.get("message") or {}).get("content")
        for c in content if isinstance(content, list) else []:
            if not isinstance(c, dict):
                continue
            if first_use is None and c.get("type") == "tool_use" and c.get("name", "").endswith("__analyze"):
                first_use = c.get("id")
            elif first_use and text is None and c.get("type") == "tool_result" and c.get("tool_use_id") == first_use:
                body = c.get("content")
                text = body if isinstance(body, str) else " ".join(
                    x.get("text", "") for x in body or [] if isinstance(x, dict))
        if text is not None:
            break
    if text is None:
        rows.append({"id": r["id"], "transcript": True, "call": False})
        continue
    m = re.search(r"index predates (\d+) changed file\(s\) \(([^)]*)\)", text)
    took = re.search(r"last graph build took ([\d.]+) s", text)
    rows.append({"id": r["id"], "transcript": True, "call": True, "predates": bool(m),
                 "files": m.group(2) if m else None, "build_s": float(took.group(1)) if took else None,
                 "background": "background update started" in text,
                 "refreshed_inline": bool(re.search(r'"index_refresh":\s*\{', text))})

calls = [x for x in rows if x.get("call")]
print("sessions", len(rows), "with a first call", len(calls))
print("predates", sum(x["predates"] for x in calls), "background", sum(x["background"] for x in calls))
print("files", Counter(x["files"] for x in calls if x["predates"]).most_common(5))
b = [x["build_s"] for x in calls if x["build_s"] is not None]
if b:
    print("last build s: min", min(b), "median", statistics.median(b), "max", max(b))
print("not predates:", [(x["id"], x["background"], x["refreshed_inline"]) for x in calls if not x["predates"]])
print("no call:", [x["id"] for x in rows if not x.get("call")])
