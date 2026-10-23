"""The files the busiest finished compaction cycle of a transcript read or edited, edited first then the latest
reads, kept to those under ROOT; one per line (at most 40)."""
import json
import sys

FT = {"Read": "file_path", "Edit": "file_path", "Write": "file_path", "NotebookEdit": "notebook_path"}
path, root = sys.argv[1], sys.argv[2].rstrip("\\/") + "\\"
cycles = [[]]
for line in open(path, encoding="utf-8", errors="replace"):
    if '"compact_boundary"' in line:
        cycles.append([])
        continue
    if '"tool_use"' not in line:
        continue
    m = json.loads(line)
    if m.get("type") != "assistant" or m.get("isSidechain"):
        continue
    for x in (m.get("message") or {}).get("content") or []:
        if x.get("type") == "tool_use" and x.get("name") in FT:
            fp = (x.get("input") or {}).get(FT[x["name"]])
            if fp:
                cycles[-1].append((x["name"], fp))
last = max(cycles[:-1], key=len)
edited, read = [], []
for name, fp in reversed(last):
    (read if name == "Read" else edited).append(fp)
order = list(dict.fromkeys(edited + read))
inside = [p for p in order if p.replace("/", "\\").lower().startswith(root.lower())]
print("\n".join(inside[:40]))
print(len(order), "distinct,", len(inside), "under the root", file=sys.stderr)
