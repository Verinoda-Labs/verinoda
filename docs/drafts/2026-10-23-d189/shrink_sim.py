"""How much a lower inline limit for tool results would have kept out of the context, on recorded sessions.

For each tool result (Bash, Read, Grep, Glob, WebFetch, MCP, Agent ...): its characters, and the token-reads it
caused (characters times the model calls that came after it, until the next compaction cleared the history).
Simulated: a result above LIMIT replaced by a head of HEAD and a tail of TAIL characters plus a 250-character note
(the full text saved to a file), as Claude Code's own <persisted-output> does above about 30,000 characters.

    python shrink_sim.py <out.json> <transcript.jsonl> [...]
"""
import json
import sys
from collections import defaultdict

LIMITS = (4000, 8000, 16000, 30000)
HEAD, TAIL, NOTE = 2000, 1000, 250


def results(path: str):
    """(tool, chars, calls after it before the next compaction) per tool result, in order."""
    pending: dict[str, str] = {}
    seen: set = set()
    calls = 0
    out = []          # [tool, chars, call index]
    bounds = []       # call index at each compaction
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                m = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            t = m.get("type")
            if t == "system" and m.get("subtype") == "compact_boundary":
                bounds.append(calls)
                continue
            msg = m.get("message") or {}
            content = msg.get("content")
            if t == "assistant":
                if msg.get("id") not in seen and msg.get("usage"):
                    seen.add(msg.get("id"))
                    calls += 1
                for x in content or []:
                    if x.get("type") == "tool_use":
                        pending[x.get("id")] = x.get("name") or "?"
            elif t == "user" and isinstance(content, list):
                for x in content:
                    if x.get("type") != "tool_result":
                        continue
                    name = pending.get(x.get("tool_use_id"), "?")
                    if name.startswith("mcp__"):
                        name = "mcp:" + name.split("__")[1]
                    c = x.get("content")
                    n = len(c) if isinstance(c, str) else sum(len(y.get("text") or "") for y in c or []
                                                               if isinstance(y, dict) and y.get("type") == "text")
                    out.append([name, n, calls])
    total = calls
    rows = []
    for name, n, at in out:
        nxt = next((b for b in bounds if b > at), total)
        rows.append((name, n, max(nxt - at, 0)))
    return rows, total, len(bounds)


def simulate(rows):
    by = defaultdict(lambda: {"results": 0, "chars": 0, "reads": 0, **{f"reads_{L}": 0 for L in LIMITS},
                              **{f"over_{L}": 0 for L in LIMITS}})
    for name, n, reads in rows:
        b = by[name]
        b["results"] += 1
        b["chars"] += n
        b["reads"] += n * reads
        for L in LIMITS:
            kept = n if n <= L else HEAD + TAIL + NOTE
            b[f"reads_{L}"] += kept * reads
            b[f"over_{L}"] += n > L
    return by


if __name__ == "__main__":
    report = {}
    grand = defaultdict(int)
    for p in sys.argv[2:]:
        rows, calls, comp = results(p)
        by = simulate(rows)
        report[p] = {"calls": calls, "compactions": comp, "by_tool": by}
        print(f"== {p[-60:]}  calls {calls}  compactions {comp}")
        for name, b in sorted(by.items(), key=lambda kv: -kv[1]["reads"])[:6]:
            cut = "  ".join(f">{L // 1000}k: {1 - b[f'reads_{L}'] / b['reads']:5.1%} ({b[f'over_{L}']})" for L in LIMITS
                            if b["reads"])
            print(f"   {name:22} results {b['results']:5}  chars {b['chars']:11,}  char-reads {b['reads']:15,}  cut {cut}")
        for b in by.values():
            for k, v in b.items():
                grand[k] += v
    json.dump(report, open(sys.argv[1], "w", encoding="utf-8"), indent=1, default=dict)
    print("== all sessions, every tool:", {L: f"{1 - grand[f'reads_{L}'] / grand['reads']:.1%}" for L in LIMITS})
