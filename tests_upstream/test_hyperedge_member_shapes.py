"""Dict-shaped hyperedge member refs must never abort a build (#2486).

LLM/subagent drift sometimes emits a hyperedge member as an object
(``{"id": "a_ts"}``) instead of a bare id string. A dict is unhashable, so the
semantic-rekey pass's ``_rekey.get(n, n)`` used to raise ``TypeError`` and
abort the whole merge — destroying a completed extraction. The fix coerces
member values at ingest (``_normalize_hyperedge_members``) and at the LLM
parse chokepoint (``_sanitize_fragment``), dropping only the individual
unusable member with a stderr WARNING.
"""
# Verinoda patch (D186): the tests of the upstream LLM, PR and media layer (llm.py, prs.py,
# transcribe.py, google_workspace.py, exporters/graphdb.py) left the package with it
# (docs/UPSTREAM.md); the tests below are upstream's.
from __future__ import annotations

from verinoda.project_index.build import build_from_json


def _node(nid: str) -> dict:
    return {"id": nid, "label": nid, "file_type": "code", "source_file": f"{nid}.ts"}


def test_dict_members_coerced_via_canonical_nodes_key(capsys):
    extraction = {
        "nodes": [_node("a_ts"), _node("b_ts")],
        "edges": [],
        "hyperedges": [
            # the #2486 repro shape: object members mixed with bare ids,
            # including a duplicate that must dedupe after coercion
            {"id": "h_flow", "nodes": [{"id": "a_ts"}, "b_ts", {"id": "a_ts"}]},
        ],
    }
    G = build_from_json(extraction, directed=True)  # must not raise
    assert set(G.nodes()) == {"a_ts", "b_ts"}
    assert G.graph["hyperedges"][0]["nodes"] == ["a_ts", "b_ts"]


def test_dict_members_coerced_via_members_alias(capsys):
    extraction = {
        "nodes": [_node("a_ts"), _node("c_ts")],
        "edges": [],
        "hyperedges": [
            {"id": "h_alias", "members": ["a_ts", {"id": "c_ts"}]},
        ],
    }
    G = build_from_json(extraction, directed=True)
    (he,) = G.graph["hyperedges"]
    assert "members" not in he, "alias key must be folded onto nodes"
    assert he["nodes"] == ["a_ts", "c_ts"]


def test_member_object_without_id_dropped_with_one_warning(capsys):
    extraction = {
        "nodes": [_node("a_ts"), _node("b_ts")],
        "edges": [],
        "hyperedges": [
            {"id": "h_partial", "nodes": [{"label": "no id here"}, "b_ts"]},
        ],
    }
    G = build_from_json(extraction, directed=True)
    assert G.graph["hyperedges"][0]["nodes"] == ["b_ts"]
    err = capsys.readouterr().err
    warnings = [
        line for line in err.splitlines()
        if "no usable 'id'" in line and "h_partial" in line
    ]
    assert len(warnings) == 1, f"expected exactly one warning, got: {err!r}"


def test_hyperedge_losing_all_members_is_dropped_not_fatal(capsys):
    extraction = {
        "nodes": [_node("a_ts")],
        "edges": [],
        "hyperedges": [
            {"id": "h_empty", "nodes": [{"label": "no id"}, {"nested": True}]},
            {"id": "h_ok", "nodes": ["a_ts"]},
        ],
    }
    G = build_from_json(extraction, directed=True)  # must not raise
    assert [he["id"] for he in G.graph["hyperedges"]] == ["h_ok"]
    assert "h_empty" in capsys.readouterr().err


