"""`import('…')` in plain .ts/.js must produce exactly one edge per fact (#2575).

tree-sitter models ``await import('x')`` as a ``call_expression``, not an
``import_statement``, so the specifier only reaches the graph when the call
walk visits it. Two holes remained: module-scope dynamic imports (no function
body is ever walked for them) and calls inside NESTED named functions (the
function boundary in walk_calls descended into arrow/function-expression
closures but returned at a nested ``function_declaration``). The fixes are a
regex rescue pass for plain JS/TS (mirroring the Svelte/Astro/Vue ones) plus
descending the boundary into nested named declarations — deduped so an
AST-captured dynamic import (already a ``deferred`` ``imports_from`` edge) is
not restated as a second ``dynamic_import`` edge.
"""
# Verinoda patch (D186): the tests of the upstream CLI (`python -m verinoda.project_index`), its installer,
# hooks, wiki, `affected` and `diagnostics` left the package with them (docs/UPSTREAM.md); the tests below
# are upstream's.
from __future__ import annotations

import json
from pathlib import Path


from verinoda.project_index.extract import _file_node_id, extract


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _edges_to(result: dict, target: str, *relations: str) -> list[dict]:
    tgt = _file_node_id(Path(target))
    rels = relations or ("dynamic_import", "imports_from")
    return [e for e in result["edges"]
            if e["target"] == tgt and e["relation"] in rels]


def test_nested_named_function_dynamic_import_edges(tmp_path: Path):
    """#2575: the reported case — `await import()` inside a nested named
    function produced no edge at all (the boundary returned before the call
    walk could see it)."""
    _write(tmp_path / "src/dep.ts", "export const dep = 1\n")
    importer = _write(
        tmp_path / "src/page.ts",
        "export function outer() {\n"
        "    async function inner() {\n"
        "        const { dep } = await import('./dep')\n"
        "        return dep\n"
        "    }\n"
        "    return inner\n"
        "}\n",
    )

    result = extract([tmp_path / "src/dep.ts", importer], root=tmp_path)

    assert _edges_to(result, "src/dep.ts"), "nested dynamic import produced no edge"


def test_doubly_nested_dynamic_import_edges(tmp_path: Path):
    _write(tmp_path / "src/dep.ts", "export const dep = 1\n")
    importer = _write(
        tmp_path / "src/page.ts",
        "export function a() {\n"
        "    function b() {\n"
        "        async function c() {\n"
        "            return await import('./dep')\n"
        "        }\n"
        "        return c\n"
        "    }\n"
        "    return b\n"
        "}\n",
    )

    result = extract([tmp_path / "src/dep.ts", importer], root=tmp_path)

    assert _edges_to(result, "src/dep.ts"), "doubly nested dynamic import lost"


def test_module_scope_dynamic_import_edges(tmp_path: Path):
    """Module scope is outside every walked function body, so only the rescue
    pass can see it."""
    _write(tmp_path / "src/dep.ts", "export const dep = 1\n")
    importer = _write(
        tmp_path / "src/boot.ts",
        "const { dep } = await import('./dep')\n"
        "export const booted = dep\n",
    )

    result = extract([tmp_path / "src/dep.ts", importer], root=tmp_path)

    edges = _edges_to(result, "src/dep.ts")
    assert edges, "module-scope dynamic import produced no edge"
    assert any(e["relation"] == "dynamic_import" for e in edges)


def test_module_scope_dynamic_import_is_still_one_fact(tmp_path: Path):
    """At module scope `caller_nid` IS the file node, so the rescue is genuinely redundant.

    This is the half of the old dedupe that was always correct, kept as its own test so a
    future change cannot quietly restore double-counting here while fixing #2584.
    """
    _write(tmp_path / "src/dep.ts", "export const dep = 1\n")
    importer = _write(
        tmp_path / "src/boot2.ts",
        "const { dep } = await import('./dep')\nexport const booted = dep\n",
    )

    result = extract([tmp_path / "src/dep.ts", importer], root=tmp_path)

    assert len(_edges_to(result, "src/dep.ts")) == 1


def test_tsconfig_aliased_dynamic_import_edges(tmp_path: Path):
    _write(
        tmp_path / "tsconfig.json",
        json.dumps({"compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["./src/*"]}}}),
    )
    _write(tmp_path / "src/agent/runner.ts", "export const run = () => 1\n")
    importer = _write(
        tmp_path / "src/boot.ts",
        "export const runner = await import('@/agent/runner')\n",
    )

    result = extract([tmp_path / "src/agent/runner.ts", importer], root=tmp_path)

    assert _edges_to(result, "src/agent/runner.ts")


def test_template_literal_specifier_without_substitution(tmp_path: Path):
    """A backtick specifier with no `${` is as static as a quoted one — the
    AST path already resolved it, the rescue must too."""
    _write(tmp_path / "src/dep.ts", "export const dep = 1\n")
    importer = _write(
        tmp_path / "src/boot.ts",
        "export const dep = await import(`./dep`)\n",
    )

    result = extract([tmp_path / "src/dep.ts", importer], root=tmp_path)

    assert _edges_to(result, "src/dep.ts")


def test_identifier_ending_in_import_is_not_matched(tmp_path: Path):
    """`fooimport('./x')` is a call to `fooimport`, not a dynamic import."""
    _write(tmp_path / "src/x.ts", "export const x = 1\n")
    importer = _write(
        tmp_path / "src/caller.ts",
        "declare function fooimport(s: string): unknown\n"
        "export const r = fooimport('./x')\n",
    )

    result = extract([tmp_path / "src/x.ts", importer], root=tmp_path)

    assert not _edges_to(result, "src/x.ts")


def test_line_commented_dynamic_import_is_not_matched(tmp_path: Path):
    _write(tmp_path / "src/x.ts", "export const x = 1\n")
    importer = _write(
        tmp_path / "src/caller.ts",
        "// const { x } = await import('./x')\n"
        "export const r = 1\n",
    )

    result = extract([tmp_path / "src/x.ts", importer], root=tmp_path)

    assert not _edges_to(result, "src/x.ts")


def test_nested_named_function_calls_resolve(tmp_path: Path):
    """ordinary calls inside a nested named function attribute to that inner function now that #2653 emits nested nodes."""
    f = _write(
        tmp_path / "src/mod.ts",
        "export function helper() { return 1 }\n"
        "export function outer() {\n"
        "    function inner() { return helper() }\n"
        "    return inner\n"
        "}\n",
    )

    result = extract([f], root=tmp_path)

    by_id = {n["id"]: n["label"].rstrip("()") for n in result["nodes"]}
    calls = {(by_id.get(e["source"]), by_id.get(e["target"]))
             for e in result["edges"] if e["relation"] == "calls"}
    contains = {(by_id.get(e["source"]), by_id.get(e["target"]))
                for e in result["edges"] if e["relation"] == "contains"}
    assert ("inner", "helper") in calls, f"calls found: {calls}"
    assert ("outer", "inner") in contains, f"contains found: {contains}"


