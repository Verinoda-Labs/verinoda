"""god_nodes() honours exclude_hubs_percentile (#3205).

The percentile only ever reached cluster()'s community-resolution step; the
god-node ranking had no exclusion parameter at all, so running it at every
percentile value returned identical output and utility hubs stayed at the
top regardless of the setting. The same threshold computation cluster()
uses now applies to the ranking, and the CLI/MCP surfaces expose it.
"""
# Verinoda patch (D186): the tests of the upstream CLI (`python -m verinoda.project_index`), its installer,
# hooks, wiki, `affected` and `diagnostics` left the package with them (docs/UPSTREAM.md); the tests below
# are upstream's.
from __future__ import annotations

import inspect

import networkx as nx

from verinoda.project_index.analyze import god_nodes


def _graph():
    """One mega-hub (degree 40), two mid symbols, a tail of leaves.

    The hub label must not be in _BUILTIN_NOISE_LABELS - the ranking already
    filters those - so the test isolates the percentile mechanism."""
    G = nx.Graph()
    G.add_node("hub", label="Registry", file_type="code", source_file="u.py", source_location="L1")
    for i in range(40):
        G.add_node(f"leaf{i}", label=f"leaf{i}", file_type="code",
                   source_file=f"l{i}.py", source_location="L1")
        G.add_edge("hub", f"leaf{i}", relation="calls")
    for name, deg in (("core", 6), ("svc", 4)):
        G.add_node(name, label=name, file_type="code", source_file=f"{name}.py",
                   source_location="L1")
        for i in range(deg):
            G.add_edge(name, f"leaf{i}", relation="calls")
    return G


def test_without_the_parameter_the_hub_still_ranks_first():
    assert god_nodes(_graph(), top_n=3)[0]["label"] == "Registry"


def test_the_percentile_suppresses_the_hub():
    gods = god_nodes(_graph(), top_n=10, exclude_hubs_percentile=90)
    labels = [g["label"] for g in gods]
    assert "Registry" not in labels, labels
    assert gods, "suppressing the hub must not empty the ranking"
    assert max(g["degree"] for g in gods) < 40


def test_the_threshold_matches_clusters_computation():
    """The ranking must exclude exactly what cluster()'s formula excludes:
    degrees sorted ascending, idx = max(0, int(n * pct / 100) - 1),
    everything with degree > degrees[idx] is a hub."""
    G = _graph()
    pct = 90
    degrees = sorted(d for _, d in G.degree())
    idx = max(0, int(len(degrees) * pct / 100) - 1)
    threshold = degrees[idx]
    expected_hubs = {n for n, d in G.degree() if d > threshold}
    assert "hub" in expected_hubs
    gods = {g["id"] for g in god_nodes(G, top_n=100, exclude_hubs_percentile=pct)}
    assert gods.isdisjoint(expected_hubs)
    assert gods, "non-hub symbols must survive"


def test_percentile_100_excludes_nothing():
    gods = god_nodes(_graph(), top_n=3, exclude_hubs_percentile=100)
    assert gods[0]["label"] == "Registry"


def test_the_analyzer_signature_stays_backward_compatible():
    sig = inspect.signature(god_nodes)
    assert sig.parameters["exclude_hubs_percentile"].default is None


# ---------------------------------------------------------------------------
# CLI surface
# ---------------------------------------------------------------------------


