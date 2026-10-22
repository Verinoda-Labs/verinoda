import json
import sys
from collections import defaultdict

g = json.load(open(sys.argv[1]))
defs, edges = g["defs"], g["edges"]
ATLAS = "verinoda.mcp.server:AtlasTools"


def blocked(src, dst):
    if src in ("verinoda.cli:build_parser", "verinoda.cli", "verinoda.cli:main") and dst.startswith("verinoda.cli:cmd_"):
        return True
    if src == ATLAS and dst.startswith(ATLAS + ".") and not dst.split(".")[-1].startswith("_"):
        return True
    return False


def reach(entries):
    seen = set()
    stack = [e for e in entries if e in defs]
    missing = [e for e in entries if e not in defs]
    if missing:
        print("missing entries:", missing, file=sys.stderr)
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        for m in edges.get(n, ()):
            if m not in seen and m in defs and not blocked(n, m):
                stack.append(m)
    return seen


def lines(nodes):
    return sum(defs[n]["lines"] for n in nodes)


cli_cmds = sorted(n for n in defs if n.startswith("verinoda.cli:cmd_"))
tools = sorted(n for n in defs if n.startswith(ATLAS + ".") and not n.split(".")[-1].startswith("_"))
base = reach(["verinoda.cli:main", "verinoda.cli:build_parser", "verinoda.cli:_run_command"])
total = lines(defs)
print("total lines", total, "base (main+parser)", lines(base))

if len(sys.argv) > 2 and sys.argv[2] == "per":
    rows = []
    for c in cli_cmds + tools:
        r = reach([c])
        rows.append((lines(r - base), c))
    for n, c in sorted(rows, reverse=True):
        print(f"{n:7d} {c}")
    sys.exit()

core_cli = sys.argv[2].split(",")
core_tools = sys.argv[3].split(",") if len(sys.argv) > 3 and sys.argv[3] else []
entries = ["verinoda.cli:main", "verinoda.cli:build_parser", "verinoda.cli:_run_command"]
entries += [f"verinoda.cli:cmd_{c.replace('-', '_')}" for c in core_cli]
entries += [f"{ATLAS}.{t}" for t in core_tools]
entries += sys.argv[4].split(",") if len(sys.argv) > 4 else []
core = reach(entries)
print("core lines", lines(core), "of", total)
per_mod = defaultdict(lambda: [0, 0])
for n, d in defs.items():
    per_mod[d["mod"]][1] += d["lines"]
    if n in core:
        per_mod[d["mod"]][0] += d["lines"]
dead_mods = [(t, m) for m, (c, t) in per_mod.items() if c == 0]
part = [(t - c, c, t, m) for m, (c, t) in per_mod.items() if 0 < c < t]
print("\nmodules wholly outside core:", len(dead_mods), "lines", sum(t for t, _ in dead_mods))
for t, m in sorted(dead_mods, reverse=True):
    print(f"  {t:6d} {g['files'][m]}")
print("\npartly outside core (top 40 by unreachable lines):")
for u, c, t, m in sorted(part, reverse=True)[:40]:
    print(f"  {u:6d} of {t:6d} {g['files'][m]}")
