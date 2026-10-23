"""The person's own sessions (not the benchmark copies): every Verinoda tool call, its result's characters and the
model calls after it; per session the model calls and the largest prompt."""
import glob, json, os, sys
from collections import Counter, defaultdict

PROJ = r"C:\Users\me\.claude\projects"
OUT = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(OUT, "real"), exist_ok=True)
skip = ("vbench", "AppData-Local-Temp")
sessions = []
for f in glob.glob(os.path.join(PROJ, "*", "*.jsonl")):
    if any(s in f for s in skip):
        continue
    try:
        txt = open(f, encoding="utf-8").read()
    except Exception:
        continue
    if "mcp__verinoda__" not in txt:
        continue
    calls, seen, pend, res = [], set(), {}, []
    for line in txt.splitlines():
        try:
            m = json.loads(line)
        except Exception:
            continue
        msg = m.get("message") or {}
        content = msg.get("content")
        if m.get("type") == "assistant":
            if msg.get("id") not in seen and msg.get("usage"):
                seen.add(msg.get("id")); calls.append(msg["usage"])
            if isinstance(content, list):
                for c in content:
                    if c.get("type") == "tool_use":
                        pend[c["id"]] = (c["name"], len(calls), c.get("input"))
        elif m.get("type") == "user" and isinstance(content, list):
            for c in content:
                if c.get("type") == "tool_result" and c.get("tool_use_id") in pend:
                    name, at, inp = pend.pop(c["tool_use_id"])
                    cc = c.get("content")
                    if isinstance(cc, str):
                        text, kinds = cc, ["str"]
                    else:
                        text = "\n".join(x.get("text", "") for x in cc or [] if x.get("type") == "text")
                        kinds = [x.get("type") for x in cc or []]
                    res.append((name, at, inp, text, kinds))
    if not any(r[0].startswith("mcp__verinoda__") for r in res):
        continue
    n = len(calls)
    peak = max((sum(u.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")) for u in calls), default=0)
    v = []
    for i, (name, at, inp, text, kinds) in enumerate(res):
        if name.startswith("mcp__verinoda__"):
            sub = (inp or {}).get("name") if name.endswith("run_tool") else None
            fn = f"{os.path.basename(f)[:8]}-{i}.txt"
            with open(os.path.join(OUT, "real", fn), "w", encoding="utf-8", newline="") as fh:
                fh.write(text)
            v.append({"tool": name[15:] + (f":{sub}" if sub else ""), "chars": len(text), "rereads": n - at,
                      "file": fn, "kinds": kinds, "head": text[:60]})
    other = sum(len(r[3]) for r in res if not r[0].startswith("mcp__verinoda__"))
    sessions.append({"file": f, "calls": n, "peak_prompt": peak, "verinoda": v, "other_result_chars": other,
                     "mtime": os.path.getmtime(f)})
json.dump(sessions, open(os.path.join(OUT, "real.json"), "w", encoding="utf-8"), indent=1)
by = defaultdict(lambda: [0, 0])
for s in sessions:
    for r in s["verinoda"]:
        by[r["tool"]][0] += 1; by[r["tool"]][1] += r["chars"]
print(len(sessions), "sessions with a Verinoda call")
for t, (k, c) in sorted(by.items(), key=lambda kv: -kv[1][1]):
    print(f"  {t:30} calls {k:4} chars {c:9,} mean {c//k:6,}")
kinds = Counter(tuple(r["kinds"]) for s in sessions for r in s["verinoda"])
print("content kinds", kinds.most_common(5))
