"""Per session of the D186 re-run: model calls, first prompt size, and every Verinoda tool result with the number of
model calls that re-read it. Writes results/<sid>-<n>.txt (the text the model saw) and sessions.json."""
import glob, json, os, sys
from collections import Counter

RES = r"C:\Users\me\Desktop\verinoda-symbiosis\benchmarks\results\claims-rerun-2026-10-13\results.jsonl"
PROJ = r"C:\Users\me\.claude\projects"
OUT = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(OUT, "results"), exist_ok=True)

rows = [json.loads(l) for l in open(RES, encoding="utf-8")]
out = []
for r in rows:
    hits = glob.glob(os.path.join(PROJ, "*", r["session_id"] + ".jsonl"))
    if not hits:
        print("missing", r["id"], r["arm"]); continue
    calls = []          # (message id, usage) in order
    seen = set()
    pending = {}        # tool_use id -> (name, call index)
    results = []
    for line in open(hits[0], encoding="utf-8"):
        m = json.loads(line)
        msg = m.get("message") or {}
        if m.get("type") == "assistant":
            mid = msg.get("id")
            if mid not in seen and msg.get("usage"):
                seen.add(mid); calls.append(msg["usage"])
            for c in msg.get("content") or []:
                if c.get("type") == "tool_use":
                    pending[c["id"]] = (c["name"], len(calls), c.get("input"))
        elif m.get("type") == "user" and isinstance(msg.get("content"), list):
            for c in msg["content"]:
                if c.get("type") == "tool_result" and c.get("tool_use_id") in pending:
                    name, at, inp = pending[c["tool_use_id"]]
                    cc = c.get("content")
                    text = cc if isinstance(cc, str) else "\n".join(x.get("text", "") for x in cc or [] if x.get("type") == "text")
                    results.append({"tool": name, "after_call": at, "chars": len(text), "input": inp, "text": text})
    n = len(calls)
    first = calls[0] if calls else {}
    prompt0 = sum(first.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    vres = []
    for i, x in enumerate(results):
        if x["tool"].startswith("mcp__verinoda__") or x["tool"] == "ToolSearch":
            fname = f"{r['session_id'][:8]}-{i}.txt"
            with open(os.path.join(OUT, "results", fname), "w", encoding="utf-8", newline="") as f:
                f.write(x["text"])
            sub = (x["input"] or {}).get("name") if x["tool"].endswith("run_tool") else None
            vres.append({"file": fname, "tool": x["tool"] + (f":{sub}" if sub else ""), "chars": x["chars"],
                         "rereads": n - x["after_call"]})
    out.append({"id": r["id"], "arm": r["arm"], "sid": r["session_id"], "calls": n, "prompt0": prompt0,
                "cost": r["cost_usd"], "verinoda": vres,
                "all_results": [(x["tool"], x["chars"], n - x["after_call"]) for x in results]})
json.dump(out, open(os.path.join(OUT, "sessions.json"), "w", encoding="utf-8"), indent=1)
print(len(out), "sessions;", Counter(o["arm"] for o in out))
