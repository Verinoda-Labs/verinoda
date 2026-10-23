"""Verinoda inside one subagent's transcript: every shell command that ran `verinoda` (or an mcp__verinoda tool), its
result's size, the context right before and after it (measured from the model calls' usage), and how many later model
calls carried it until a compaction dropped it; then every tool's count and result size, and the model calls' totals.

    python vcalls.py <subagent.jsonl> [<out-dir for the results' full text>]
"""
import json
import re
import statistics
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path


def ts(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


path = sys.argv[1]
out = Path(sys.argv[2]) if len(sys.argv) > 2 else None
calls = []  # (t, ctx, input, cache_write, cache_read, output) per unique model call, in order
seen = set()
uses = {}  # tool_use id -> (name, input, t)
results = []  # (t, tool_use id, chars, text)
boundaries = []
first = last = None
for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
    try:
        m = json.loads(line)
    except ValueError:
        continue
    t = ts(m.get("timestamp"))
    if t:
        first = t if first is None else min(first, t)
        last = t if last is None else max(last, t)
    if m.get("type") == "system" and m.get("subtype") == "compact_boundary":
        boundaries.append(t)
        continue
    msg = m.get("message") or {}
    content = msg.get("content")
    if m.get("type") == "assistant":
        u = msg.get("usage")
        if u and msg.get("id") not in seen:
            seen.add(msg.get("id"))
            i, w, r = (u.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
            calls.append((t, i + w + r, i, w, r, u.get("output_tokens") or 0))
        for x in content or []:
            if isinstance(x, dict) and x.get("type") == "tool_use":
                uses[x.get("id")] = (x.get("name"), x.get("input") or {}, t)
    elif m.get("type") == "user" and isinstance(content, list):
        for x in content:
            if isinstance(x, dict) and x.get("type") == "tool_result":
                c = x.get("content")
                text = c if isinstance(c, str) else "".join(y.get("text") or "" for y in c or [] if isinstance(y, dict))
                results.append((t, x.get("tool_use_id"), len(text), text))


# the CLI word followed by a subcommand: not the "...-verinoda-symbiosis" scratchpad path, "verinoda-usage.jsonl" or the
# VERINODA_USAGE_LOG variable, which most commands of this session carry
CLI = re.compile(r"(?<![-\w])verinoda(\.exe)?[\"']?\s+[a-z]")


def is_verinoda(name, inp):
    if name.startswith("mcp__verinoda"):
        return True
    return name in ("Bash", "PowerShell") and bool(CLI.search(str(inp.get("command") or "")))


print(f"model calls {len(calls)}; wall {(last - first) / 60:.1f} min; compactions {len(boundaries)}")
ctx = [c[1] for c in calls]
print(f"context mean {statistics.mean(ctx):,.0f}, median {statistics.median(ctx):,.0f}, peak {max(ctx):,}")
print("totals: uncached input {:,}  cache write {:,}  cache read {:,}  output {:,}".format(
    *(sum(c[k] for c in calls) for k in (2, 3, 4, 5))))

by_tool = Counter()
by_tool_chars = Counter()
all_chars = 0
n = 0
for t, uid, chars, text in results:
    name, inp, _ = uses.get(uid, ("?", {}, None))
    key = "verinoda (shell)" if is_verinoda(name, inp) and not name.startswith("mcp__") else name
    by_tool[key] += 1
    by_tool_chars[key] += chars
    all_chars += chars
print(f"tool results {len(results)}, {all_chars:,} chars")
for k, v in by_tool_chars.most_common():
    print(f"   {k:22} {by_tool[k]:4}  chars {v:9,}  {v / (all_chars or 1):6.1%}")

for t, uid, chars, text in results:
    name, inp, tu = uses.get(uid, ("?", {}, None))
    if not is_verinoda(name, inp):
        continue
    n += 1
    before = [c for c in calls if c[0] is not None and tu is not None and c[0] <= tu]
    after = [c for c in calls if c[0] is not None and c[0] > t]
    nxt = min((b for b in boundaries if b and b > t), default=None)
    carried = [c for c in after if nxt is None or c[0] < nxt]
    delta = after[0][1] - before[-1][1] if before and after else None
    when = datetime.fromtimestamp(t).isoformat(timespec="seconds") if t else "?"
    print(f"\nverinoda call {n} at {when} via {name}:")
    print("   command:", str(inp.get("command") or json.dumps(inp, ensure_ascii=False))[:600])
    print(f"   result {chars:,} chars (~{chars // 4:,} tokens at 4 chars/token)")
    if delta is not None:
        print(f"   context before the call {before[-1][1]:,}, at the next model call {after[0][1]:,} (+{delta:,},"
              " which also holds the call itself and any text written with it)")
    print(f"   later model calls carrying it: {len(carried)} of {len(after)}"
          f" -> ~{len(carried) * chars // 4:,} tokens re-read (4 chars/token)")
    if out:
        out.mkdir(parents=True, exist_ok=True)
        (out / f"verinoda-result-{n}.txt").write_text(text, encoding="utf-8")
