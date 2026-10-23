"""compact_sim.py with the transcript's own compaction records: a context restarts only at a compact_boundary (its
size after it is the next call's), a one-step jump above +300k is a counting artefact and is left out; growth is
the conversation's. Simulated window W: when the context passes W it restarts at the session's median size after a
real compaction, plus one read of the context for the compaction's own call."""
import json, statistics, sys

def calls(path):
    seen, out, mark = set(), [], False
    for line in open(path, encoding="utf-8", errors="replace"):
        if '"compact_boundary"' in line:
            mark = True
            continue
        if '"usage"' not in line:
            continue
        try:
            m = json.loads(line)
        except Exception:
            continue
        msg = m.get("message") or {}
        if m.get("type") != "assistant" or m.get("isSidechain") or msg.get("id") in seen or not msg.get("usage"):
            continue
        seen.add(msg.get("id"))
        u = msg["usage"]
        out.append((sum(u.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")), mark))
        mark = False
    return out

for p in sys.argv[1:]:
    c = calls(p)
    sizes = [s for s, _ in c]
    bases = [s for s, after in c if after]
    base = int(statistics.median(bases)) if bases else 90_000
    grow = []
    for (a, _), (b, after) in zip(c, c[1:]):
        d = b - a
        grow.append(0 if after or d > 300_000 or d < 0 else d)
    actual = sum(min(s, 1_000_000) for s in sizes)
    print(f"== {p[-48:]}  calls {len(c)}  compactions {len(bases)}  size after one {base:,}  "
          f"mean context {actual / len(c):,.0f}  calls>500k {sum(s > 500_000 for s in sizes)}")
    for w in (200_000, 300_000, 400_000, 500_000, 967_000):
        cur, reads, comp = sizes[0], sizes[0], 0
        for g in grow:
            cur += g
            if cur > w:
                reads += cur; comp += 1; cur = base
            reads += cur
        print(f"   window {w // 1000:4}k: reads {reads / actual:6.1%} of actual  compactions {comp:3}  mean context {reads / len(c):9,.0f}")
