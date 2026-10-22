"""Static reference graph of the verinoda package at function granularity.

Nodes: "mod" (module-level code), "mod:func", "mod:Class" (class body), "mod:Class.meth".
Edges: a name or attribute reference that resolves (through imports and own definitions) to another node.
Over-approximates (any reference counts, a class reaches its methods) except where blocked.
"""
from __future__ import annotations

import ast
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(sys.argv[1])
PKG = ROOT / "verinoda"


def modname(p: Path) -> str:
    rel = p.relative_to(ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


files = {modname(p): p for p in PKG.rglob("*.py")}
is_pkg = {m: p.name == "__init__.py" for m, p in files.items()}

defs: dict[str, dict] = {}  # node -> {"lines": n, "refs": set(), "file": str, "span": (a, b)}
module_bind: dict[str, dict[str, tuple[str, str | None]]] = {}


def resolve_from(mod: str, level: int, target: str | None) -> str:
    if level == 0:
        return target or ""
    base = mod.split(".")
    if not is_pkg.get(mod):
        base = base[:-1]
    base = base[: len(base) - (level - 1)] if level > 1 else base
    return ".".join(base + ([target] if target else []))


def import_binds(node, mod: str) -> dict[str, tuple[str, str | None]]:
    out = {}
    if isinstance(node, ast.Import):
        for a in node.names:
            if a.asname:
                out[a.asname] = (a.name, None)
            else:
                out[a.name.split(".")[0]] = (a.name.split(".")[0], None)
                # `import verinoda.x` binds verinoda; attribute chains resolve below
    elif isinstance(node, ast.ImportFrom):
        src = resolve_from(mod, node.level, node.module)
        for a in node.names:
            if a.name == "*":
                continue
            out[a.asname or a.name] = (src, a.name)
    return out


def target_of(bind: tuple[str, str | None]) -> tuple[str | None, str | None]:
    """(module, name) -> the node it denotes: a module node or a def node."""
    m, name = bind
    if name is None:
        return (m if m in files else None), None
    sub = f"{m}.{name}"
    if sub in files:
        return sub, None
    if m in files:
        return m, name
    return None, None


class Collector(ast.NodeVisitor):
    def __init__(self, mod: str):
        self.mod = mod
        self.binds_stack: list[dict] = []
        self.refs: set = set()  # raw refs: ("name", n) / ("attr", base_name, attr) / ("self", attr) / ("bind", ...)

    def visit_Import(self, node):
        b = import_binds(node, self.mod)
        self.binds_stack[-1].update(b)
        for k, v in b.items():
            self.refs.add(("import", v))

    visit_ImportFrom = visit_Import

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.refs.add(("name", node.id))

    def visit_Attribute(self, node):
        chain = []
        cur = node
        while isinstance(cur, ast.Attribute):
            chain.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            chain.reverse()
            if cur.id in ("self", "cls"):
                self.refs.add(("self", chain[0]))
            else:
                self.refs.add(("chain", cur.id, tuple(chain)))
            self.refs.add(("name", cur.id))
            for sub in ast.iter_child_nodes(node):
                if not isinstance(sub, ast.Attribute):
                    pass
            return
        self.generic_visit(node)

    def visit_Constant(self, node):
        # module names used dynamically, e.g. importlib.import_module("verinoda.x")
        if isinstance(node.value, str) and node.value.startswith("verinoda.") and node.value in files:
            self.refs.add(("import", (node.value, None)))


def scan_module(mod: str, path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    mb: dict[str, tuple[str, str | None]] = {}
    own: dict[str, str] = {}
    # module-level imports and defs (including inside top-level if/try)
    def top_stmts(body):
        for st in body:
            if isinstance(st, (ast.If, ast.Try)):
                yield from top_stmts(st.body)
                for h in getattr(st, "handlers", []):
                    yield from top_stmts(h.body)
                yield from top_stmts(st.orelse)
                yield from top_stmts(getattr(st, "finalbody", []))
            else:
                yield st
    for st in top_stmts(tree.body):
        if isinstance(st, (ast.Import, ast.ImportFrom)):
            mb.update(import_binds(st, mod))
        elif isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            own[st.name] = f"{mod}:{st.name}"
    module_bind[mod] = mb

    def node_lines(n):
        return n.end_lineno - n.lineno + 1

    def collect(stmts, extra_binds=None):
        c = Collector(mod)
        c.binds_stack.append(dict(extra_binds or {}))
        for s in stmts:
            c.visit(s)
        return c.refs, c.binds_stack[-1]

    total = len(path.read_text(encoding="utf-8").splitlines())
    used = 0
    mod_level = []
    for st in tree.body:
        if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)):
            refs, lb = collect(st.decorator_list + [st.args] + st.body)
            defs[f"{mod}:{st.name}"] = dict(lines=node_lines(st), refs=refs, lb=lb, mod=mod, cls=None)
            used += node_lines(st)
        elif isinstance(st, ast.ClassDef):
            body_other = []
            meths = []
            for b in st.body:
                if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    refs, lb = collect(b.decorator_list + [b.args] + b.body)
                    defs[f"{mod}:{st.name}.{b.name}"] = dict(lines=node_lines(b), refs=refs, lb=lb, mod=mod,
                                                            cls=st.name)
                    meths.append(b.name)
                    used += node_lines(b)
                else:
                    body_other.append(b)
            refs, lb = collect(st.decorator_list + st.bases + body_other)
            cl = node_lines(st) - sum(defs[f"{mod}:{st.name}.{m}"]["lines"] for m in meths)
            defs[f"{mod}:{st.name}"] = dict(lines=cl, refs=refs, lb=lb, mod=mod, cls=None, methods=meths)
            used += cl
        else:
            mod_level.append(st)
    refs, lb = collect(mod_level)
    defs[mod] = dict(lines=total - used, refs=refs, lb=lb, mod=mod, cls=None)
    return own


owns = {m: scan_module(m, p) for m, p in files.items()}


def resolve_bind(bind, chain=()):
    m, name = target_of(bind)
    if m is None:
        return None
    if name is None:
        # module; walk the chain through submodules / defs
        for i, a in enumerate(chain):
            sub = f"{m}.{a}"
            if sub in files:
                m = sub
                continue
            node = owns[m].get(a)
            if node:
                rest = chain[i + 1:]
                if rest and f"{node}.{rest[0]}" in defs:
                    return f"{node}.{rest[0]}"
                return node
            b = module_bind[m].get(a)
            if b:  # re-exported through the package's own import
                return resolve_bind(b, chain[i + 1:])
            return m
        return m
    node = owns[m].get(name)
    if node is None:
        # re-export through the module's own import binding
        b = module_bind[m].get(name)
        if b and b != bind:
            return resolve_bind(b, chain)
        return m
    if chain and f"{node}.{chain[0]}" in defs:
        return f"{node}.{chain[0]}"
    return node


edges: dict[str, set[str]] = defaultdict(set)
for node, d in defs.items():
    mod = d["mod"]
    own = owns[mod]
    binds = dict(module_bind[mod])
    binds.update(d["lb"])
    if node != mod:
        edges[node].add(mod)  # a def needs its module loaded
    for r in d["refs"]:
        kind = r[0]
        if kind == "import":
            t = resolve_bind(r[1])
            if t:
                # an import makes the module load; a name import does not make the def reachable by itself
                edges[node].add(t.split(":")[0])
        elif kind == "name":
            n = r[1]
            if n in d["lb"]:
                t = resolve_bind(d["lb"][n])
            elif n in own:
                t = own[n]
            elif n in binds:
                t = resolve_bind(binds[n])
            else:
                t = None
            if t:
                edges[node].add(t)
        elif kind == "chain":
            base, chain = r[1], r[2]
            b = d["lb"].get(base) or (None if base in own else binds.get(base))
            if b:
                t = resolve_bind(b, chain)
                if t:
                    edges[node].add(t)
            elif base in own:
                t = f"{own[base]}.{chain[0]}"
                if t in defs:
                    edges[node].add(t)
        elif kind == "self" and d.get("cls"):
            t = f"{mod}:{d['cls']}.{r[1]}"
            if t in defs:
                edges[node].add(t)
    if d.get("methods") is not None:
        for m in d["methods"]:
            edges[node].add(f"{node}.{m}")
    # a module reaches its package __init__
    parts = mod.split(".")
    for i in range(1, len(parts)):
        p = ".".join(parts[:i])
        if p in files:
            edges[mod].add(p)

json.dump({"defs": {k: {"lines": v["lines"], "mod": v["mod"]} for k, v in defs.items()},
           "edges": {k: sorted(v) for k, v in edges.items()},
           "files": {m: str(p.relative_to(ROOT)) for m, p in files.items()}},
          open(sys.argv[2], "w"), indent=0)
print(len(defs), "nodes", sum(len(v) for v in edges.values()), "edges")
