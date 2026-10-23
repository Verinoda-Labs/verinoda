"""Token-turns per session: the fixed delta (Verinoda first prompt minus the plain first prompt of the same task) times
the model calls, and every Verinoda result's exact tokens times the calls that read it; by tool."""
import json, os, statistics as st
from collections import defaultdict

D = os.path.dirname(os.path.abspath(__file__))
S = json.load(open(os.path.join(D, "sessions.json"), encoding="utf-8"))
T = {os.path.basename(k): v for k, v in json.load(open(os.path.join(D, "counts-results.json"), encoding="utf-8")).items()}
plain = {s["id"]: s for s in S if s["arm"] == "none"}
ver = [s for s in S if s["arm"] == "verinoda_guided"]
paired = [s for s in ver if s["id"] in plain]
print("verinoda sessions", len(ver), "with a plain pair", len(paired))
deltas = [s["prompt0"] - plain[s["id"]]["prompt0"] for s in paired]
print("fixed delta tokens: median", st.median(deltas), "min", min(deltas), "max", max(deltas))
fixed_d = st.median(deltas)
by_tool = defaultdict(lambda: [0, 0, 0])   # tool -> [results, tokens, token-turns]
fixed_tt = res_tt = 0
calls = []
for s in ver:
    calls.append(s["calls"])
    fixed_tt += fixed_d * s["calls"]
    for r in s["verinoda"]:
        t = T[r["file"]]
        bt = by_tool[r["tool"].replace("mcp__verinoda__", "")]
        bt[0] += 1; bt[1] += t; bt[2] += t * r["rereads"]
        res_tt += t * r["rereads"]
n = len(ver)
print(f"model calls per session: mean {st.mean(calls):.2f} median {st.median(calls)}")
print(f"per session: fixed token-turns {fixed_tt/n:,.0f}; result token-turns {res_tt/n:,.0f}")
for tool, (k, t, tt) in sorted(by_tool.items(), key=lambda kv: -kv[1][2]):
    print(f"  {tool:28} results {k:3}  tokens {t:7,} (mean {t/k:6,.0f})  token-turns {tt:8,}  per session {tt/n:7,.0f}")
# dollars at the D186 cost model's SWE-bench table: cache write $4/M, cache read $0.20/M
w, rd = 4e-6, 0.2e-6
fixed_cost = sum(fixed_d * w + fixed_d * (s["calls"] - 1) * rd for s in ver) / n
res_cost = sum(T[r["file"]] * w + T[r["file"]] * max(r["rereads"] - 1, 0) * rd for s in ver for r in s["verinoda"]) / n
print(f"per session dollars (write once, read after): fixed ${fixed_cost:.4f}, results ${res_cost:.4f}")
