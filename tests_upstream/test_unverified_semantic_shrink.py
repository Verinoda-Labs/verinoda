"""Tests for unverified semantic document node shrink protection (#3203).

When an incremental extraction produces strictly fewer semantic document nodes
for an existing source file (prior > 1 and fresh < prior), it is treated as an
unverified semantic shrink. build_merge flags the anomaly on G.graph so the CLI
can arm the shrink guard (force=False) and prevent the under-produced source from
being stamped in manifest.json, preserving the existing graph and allowing
subsequent incremental runs to retry.
"""
# Verinoda patch (D186): the tests of the upstream CLI (`python -m verinoda.project_index`), its installer,
# hooks, wiki, `affected` and `diagnostics` left the package with them (docs/UPSTREAM.md); the tests below
# are upstream's.
from __future__ import annotations

import json
from pathlib import Path
import pytest

from verinoda.project_index.build import build_merge, merge_raw_extraction


def _sem_node(sf: str, name: str) -> dict:
    """Semantic node without _origin."""
    stem = sf.replace("/", "_").replace(".", "_")
    return {
        "id": f"{stem}_{name}",
        "label": f"{sf} {name}",
        "file_type": "document",
        "source_file": sf,
    }


def _ast_node(sf: str, name: str) -> dict:
    """AST node with _origin='ast'."""
    stem = sf.replace("/", "_").replace(".", "_")
    return {
        "id": f"{stem}_{name}",
        "label": f"{sf} {name}",
        "file_type": "code",
        "source_file": sf,
        "_origin": "ast",
    }


def _write_graph(graph_path: Path, nodes, edges=()) -> None:
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    graph_path.write_text(
        json.dumps({"nodes": list(nodes), "edges": list(edges), "hyperedges": []}),
        encoding="utf-8",
    )


# ── 1. Unit Tests for build_merge anomaly flagging ────────────────────────────

def test_build_merge_flags_unverified_semantic_shrink(tmp_path):
    """Semantic source with 3 prior nodes re-extracted with 1 node is flagged on G.graph."""
    gp = tmp_path / "graphify-out" / "graph.json"
    _write_graph(gp, [_sem_node("doc.md", f"n{i}") for i in range(3)])

    chunk = {"nodes": [_sem_node("doc.md", "n0")], "edges": []}
    G = build_merge([chunk], gp, dedup=False, root=tmp_path)

    assert G.number_of_nodes() == 1
    assert "_unverified_semantic_shrink" in G.graph
    assert G.graph["_unverified_semantic_shrink"] == {"doc.md": (3, 1)}


def test_build_merge_flags_shrink_when_surviving_id_is_renamed(tmp_path):
    """Surviving semantic node renamed (n0 -> renamed_concept) still flags based on count."""
    gp = tmp_path / "graphify-out" / "graph.json"
    _write_graph(gp, [_sem_node("doc.md", f"sec_{i}") for i in range(3)])

    chunk = {"nodes": [_sem_node("doc.md", "renamed_concept")], "edges": []}
    G = build_merge([chunk], gp, dedup=False, root=tmp_path)

    assert G.number_of_nodes() == 1
    assert G.graph.get("_unverified_semantic_shrink") == {"doc.md": (3, 1)}


def test_build_merge_own_file_shrink_remains_non_fatal(tmp_path):
    """build_merge must NOT raise an exception on own-file shrink; it returns G."""
    gp = tmp_path / "graphify-out" / "graph.json"
    _write_graph(gp, [_sem_node("doc.md", f"n{i}") for i in range(10)])

    chunk = {"nodes": [_sem_node("doc.md", "n0")], "edges": []}
    G = build_merge([chunk], gp, dedup=False, root=tmp_path)
    assert G.number_of_nodes() == 1


def test_build_merge_does_not_flag_ast_code_shrink(tmp_path):
    """Deterministic AST/code shrinkage (10 -> 1) is never flagged as unverified semantic shrink."""
    gp = tmp_path / "graphify-out" / "graph.json"
    _write_graph(gp, [_ast_node("mod.py", f"fn{i}") for i in range(10)])

    chunk = {"nodes": [_ast_node("mod.py", "fn0")], "edges": []}
    G = build_merge([chunk], gp, dedup=False, root=tmp_path)

    assert G.number_of_nodes() == 1
    assert "_unverified_semantic_shrink" not in G.graph


def test_build_merge_equal_count_different_ids_not_flagged(tmp_path):
    """10 -> 10 semantic nodes with completely different IDs is not flagged as a shrink."""
    gp = tmp_path / "graphify-out" / "graph.json"
    _write_graph(gp, [_sem_node("doc.md", f"old_{i}") for i in range(10)])

    chunk = {"nodes": [_sem_node("doc.md", f"new_{i}") for i in range(10)], "edges": []}
    G = build_merge([chunk], gp, dedup=False, root=tmp_path)

    assert G.number_of_nodes() == 10
    assert "_unverified_semantic_shrink" not in G.graph


def test_build_merge_semantic_growth_not_flagged(tmp_path):
    """Semantic growth (3 -> 4) is unaffected."""
    gp = tmp_path / "graphify-out" / "graph.json"
    _write_graph(gp, [_sem_node("doc.md", f"n{i}") for i in range(3)])

    chunk = {"nodes": [_sem_node("doc.md", f"n{i}") for i in range(4)], "edges": []}
    G = build_merge([chunk], gp, dedup=False, root=tmp_path)

    assert G.number_of_nodes() == 4
    assert "_unverified_semantic_shrink" not in G.graph


def test_build_merge_aggregates_multiple_chunks_per_source(tmp_path):
    """Multiple chunks for the same source are summed before comparison (2 + 2 = 4 >= 3 -> no shrink)."""
    gp = tmp_path / "graphify-out" / "graph.json"
    _write_graph(gp, [_sem_node("doc.md", f"n{i}") for i in range(3)])

    chunk1 = {"nodes": [_sem_node("doc.md", "c1_a"), _sem_node("doc.md", "c1_b")], "edges": []}
    chunk2 = {"nodes": [_sem_node("doc.md", "c2_a"), _sem_node("doc.md", "c2_b")], "edges": []}

    G = build_merge([chunk1, chunk2], gp, dedup=False, root=tmp_path)
    assert G.number_of_nodes() == 4
    assert "_unverified_semantic_shrink" not in G.graph


def test_build_merge_source_specific_growth_cannot_mask_shrink(tmp_path):
    """Growth in B (3 -> 20) cannot mask unverified shrink in A (6 -> 2)."""
    gp = tmp_path / "graphify-out" / "graph.json"
    _write_graph(
        gp,
        [_sem_node("a.md", f"a{i}") for i in range(6)]
        + [_sem_node("b.md", f"b{i}") for i in range(3)],
    )

    chunk_a = {"nodes": [_sem_node("a.md", f"a{i}") for i in range(2)], "edges": []}
    chunk_b = {"nodes": [_sem_node("b.md", f"b{i}") for i in range(20)], "edges": []}

    G = build_merge([chunk_a, chunk_b], gp, dedup=False, root=tmp_path)
    assert G.number_of_nodes() == 22
    assert G.graph.get("_unverified_semantic_shrink") == {"a.md": (6, 2)}


def test_merge_raw_extraction_parity(tmp_path):
    """merge_raw_extraction also flags unverified semantic shrink."""
    gp = tmp_path / "graph.json"
    _write_graph(gp, [_sem_node("doc.md", f"n{i}") for i in range(5)])

    new = {"nodes": [_sem_node("doc.md", "n0")], "edges": [], "hyperedges": []}
    merged = merge_raw_extraction(new, gp, root=tmp_path)

    assert merged.get("_unverified_semantic_shrink") == {"doc.md": (5, 1)}


# ── 2. Integration / CLI Tests for #3203 Behavior ─────────────────────────────


