"""Functions and classes no product entry point reaches (all CLI commands, all MCP tools, the module-level code of
every module that is itself reached, the __main__ modules)."""
import json
import sys
from collections import defaultdict

g = json.load(open(sys.argv[1]))
defs, edges, files = g["defs"], g["edges"], g["files"]

entries = [n for n in defs if n.startswith("verinoda.cli:cmd_")]
entries += [n for n in defs if n.startswith("verinoda.mcp.server:AtlasTools.")]
entries += ["verinoda.cli", "verinoda.cli:main", "verinoda.__main__", "verinoda.benchmark.__main__",
            "verinoda.mcp.server:build_server", "verinoda.mcp.server:serve"]
entries += [m for m in files if m.startswith("verinoda.runtime.")]  # pytest plugins loaded by name
seen = set()
stack = [e for e in entries if e in defs]
while stack:
    n = stack.pop()
    if n in seen:
        continue
    seen.add(n)
    stack.extend(m for m in edges.get(n, ()) if m in defs and m not in seen)

dead = [(defs[n]["lines"], n) for n in defs if n not in seen and ":" in n]
dead_mods = [m for m in files if m not in seen]
print("reached", len(seen), "of", len(defs), "; dead defs", len(dead), "lines", sum(l for l, _ in dead))
print("modules never loaded:", dead_mods)
by_mod = defaultdict(list)
for l, n in dead:
    by_mod[defs[n]["mod"]].append((l, n.split(":", 1)[1]))
out = []
for m, items in sorted(by_mod.items(), key=lambda kv: -sum(l for l, _ in kv[1])):
    out.append(f"{sum(l for l, _ in items):5d} {files[m]}: " + ", ".join(f"{n}({l})" for l, n in sorted(items, reverse=True)))
open(sys.argv[2], "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out[:60]))
