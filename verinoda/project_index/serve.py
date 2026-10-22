# graph query helpers: term extraction, node scoring, subgraph and shortest-path rendering
# Verinoda patch (D186): the upstream MCP server (stdio and HTTP, with its PR tools) left the package; the
# helpers stay for verinoda.index, verinoda.retrieval and the benchmark's Graphify baseline (docs/UPSTREAM.md).
from __future__ import annotations
import json
import math
import os
import re
import sys
import warnings
from array import array
from collections import OrderedDict
from pathlib import Path
import threading
from typing import NamedTuple
import networkx as nx
from networkx.readwrite import json_graph
from verinoda.project_index.security import sanitize_label, check_graph_file_size_cap
from verinoda.project_index.build import edge_datas

try:
    with warnings.catch_warnings():
        # jieba/jieba-py carry invalid regex escapes that emit a SyntaxWarning on
        # compile; the message and line moved across Python versions (3.12 also
        # reworded it), so ignore the category wholesale here rather than pinning
        # a message/lineno. Under `-W error::SyntaxWarning` this keeps the import
        # from escalating to a fatal SyntaxError.
        warnings.simplefilter("ignore", SyntaxWarning)
        import jieba as _jieba  # type: ignore[import-untyped]
except (ImportError, SyntaxError):
    # A stray/broken jieba must never take down the whole server import.
    _jieba = None


def _load_graph(graph_path: str) -> nx.Graph:
    try:
        resolved = Path(graph_path).resolve()
        if resolved.suffix != ".json":
            raise ValueError(f"Graph path must be a .json file, got: {graph_path!r}")
        if not resolved.exists():
            raise FileNotFoundError(f"Graph file not found: {resolved}")
        check_graph_file_size_cap(resolved)
        safe = resolved
        data = json.loads(safe.read_text(encoding="utf-8"))
        if "links" not in data and "edges" in data:
            data = dict(data, links=data["edges"])
        # Stash the on-disk logical flag before the load-time override below:
        # `directed: True` exists only so renderers can recover stored arc
        # order (#2309); tools that care about logical direction (#2487) must
        # not mistake the override for graph truth.
        _logical_directed = bool(data.get("directed", False))
        data = {**data, "directed": True}
        try:
            from verinoda.project_index.build import graph_has_legacy_ids as _legacy
            if _legacy(data.get("nodes", [])):
                print(
                    "[graphify] note: this graph uses the pre-#1504 node-ID scheme; "
                    "rebuild with `graphify extract --force` for path-qualified IDs.",
                    file=sys.stderr,
                )
        except Exception:
            pass
        try:
            G = json_graph.node_link_graph(data, edges="links")
        except TypeError:
            G = json_graph.node_link_graph(data)
        G.graph["_logical_directed"] = _logical_directed
        # Attach the work-memory overlay (derived sidecar next to graph.json) so
        # the query/MCP read surface can annotate NODE lines display-only. Empty
        # when no sidecar exists, leaving un-annotated output byte-identical.
        try:
            from verinoda.project_index.reflect import load_learning_overlay as _llo
            G.graph["_learning_overlay"] = _llo(resolved)
        except Exception:
            G.graph["_learning_overlay"] = {}
        return G
    except json.JSONDecodeError as exc:
        print(f"error: graph.json is corrupted ({exc}). Re-run /graphify to rebuild.", file=sys.stderr)
        sys.exit(1)
    except (ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


def _communities_from_graph(G: nx.Graph) -> dict[int, list[str]]:
    """Reconstruct community dict from community property stored on nodes."""
    communities: dict[int, list[str]] = {}
    for node_id, data in G.nodes(data=True):
        cid = data.get("community")
        if cid is not None:
            communities.setdefault(int(cid), []).append(node_id)
    return communities


def _max_server_contexts() -> int:
    """Return the project-context LRU capacity (default 8, minimum 1).

    ``GRAPHIFY_MAX_CONTEXTS`` overrides the default. Invalid or blank values
    use 8; zero and negative values clamp to 1, since each request needs a
    graph context. The server's configured default graph is pinned separately
    and does not count against this limit.
    """
    raw = os.environ.get("GRAPHIFY_MAX_CONTEXTS", "").strip()
    if not raw:
        return 8
    try:
        return max(1, int(raw))
    except ValueError:
        return 8


class _GraphContextCache:
    """Thread-safe graph contexts: one pinned default plus an LRU of projects."""

    def __init__(self, max_contexts: int):
        self._max_contexts = max_contexts
        self._entries: OrderedDict[str, dict] = OrderedDict()
        self._pinned: dict[str, dict] = {}
        self._lock = threading.Lock()

    def _load_entry(self, resolved_path: str, key: tuple[int, int]) -> dict:
        """Build one entry for an already-resolved path and known file key.

        ``_load_graph`` is also used by the CLI, where invalid input terminates
        the process. A client-supplied ``project_path`` must instead become a
        tool error, so the shared MCP server can continue serving other graphs.
        """
        try:
            graph = _load_graph(resolved_path)
        except SystemExit as exc:
            raise RuntimeError(f"could not load graph.json at {resolved_path}") from exc
        # Warm the index before exposing the graph so its first query does not
        # pay the expensive build cost.
        _get_trigram_index(graph)
        communities = _communities_from_graph(graph)
        entry = {
            "key": key,
            "G": graph,
            "communities": communities,
        }
        return entry

    def load(self, resolved_path: str, *, pinned: bool = False) -> tuple[nx.Graph, dict[int, list[str]]]:
        """Return a fresh context, retaining project contexts by LRU order.

        ``resolved_path`` is resolved by the caller, making this method the
        sole owner of file statting and cache-key construction.

        ``pinned=True`` is reserved for the server's configured default graph;
        it remains warm without consuming a project-cache slot.
        """
        with self._lock:
            try:
                stat_result = Path(resolved_path).stat()
            except FileNotFoundError:
                raise FileNotFoundError(f"graph.json not found: {resolved_path}") from None
            key = (stat_result.st_mtime_ns, stat_result.st_size)
            entries = self._pinned if pinned else self._entries
            entry = entries.get(resolved_path)
            if entry is not None and entry["key"] == key:
                if not pinned:
                    self._entries.move_to_end(resolved_path)
                return entry["G"], entry["communities"]

            entry = self._load_entry(resolved_path, key)
            entries[resolved_path] = entry
            if not pinned:
                self._entries.move_to_end(resolved_path)
                while len(self._entries) > self._max_contexts:
                    self._entries.popitem(last=False)
            return entry["G"], entry["communities"]


def _strip_diacritics(text: str | None) -> str:
    import unicodedata
    if not isinstance(text, str):
        text = "" if text is None else str(text)
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _search_tokens(text: str) -> list[str]:
    """Split text into word tokens, stripping punctuation and diacritics.

    `_` is a separator, exactly like `-`. `\\w` counts underscore as a word
    character but not hyphen, so `graph_first_guard` stayed one token while the
    label `graph-first-guard.py` split into three — and the query matched
    nothing. Both the query and the node label pass through here, so splitting
    on `_` keeps the two sides consistent and snake_case lookups still resolve
    (their tokens simply match the same way). Found 2026-07-29: the graph could
    not find the underscore spelling of its own `local_id`.
    """
    return re.findall(r"[^\W_]+", _strip_diacritics(str(text)).lower())


def _has_chinese(text: str) -> bool:
    return any("一" <= ch <= "鿿" for ch in text)


def _segment_chinese(text: str) -> list[str]:
    """Segment Chinese text and keep the original term for exact matching."""
    if _jieba is not None:
        segments = [w for w in _jieba.cut(text) if len(w.strip()) > 0]
    else:
        segments = [text[i:i + 2] for i in range(len(text) - 1)] or [text]
    if len(text) > 1 and text not in segments:
        segments.append(text)
    return segments


def _is_searchable(term: str) -> bool:
    """True if term is Chinese, non-English, or an English word longer than 2 chars."""
    if all("a" <= ch <= "z" for ch in term):
        return len(term) > 2
    return True


# Question/filler words dropped from query terms so content words drive BFS
# seeding. Without this, "how does the frontier cache work" seeds on "how"/
# "the"/"work" (which prefix-match prose labels like "Working Principles" at 100x)
# instead of "frontier"/"cache", and lands in the wrong part of the graph. Applied
# to query terms only — node text is never filtered, so a symbol literally named
# `work` stays findable via explain/path. `work`/`works`/`working` are included
# because "how does X work" / "how X works" is the most common question phrasing.
#
# Non-English question words are just as damaging (#1900): in a mostly-English
# code corpus, German "wie"/"funktioniert" are rare, so they get HIGH IDF weight
# and out-seed the actual content noun by orders of magnitude. So this also
# carries a curated German set plus a trimmed French/Spanish/Portuguese/Italian
# set of question/filler words. Diacritics are kept intact (the query tokenizer
# does not NFKD-strip).
#
# Collision tradeoff: a few foreign stopwords are also English content words.
# We include high-German-value ones like "die"/"hat" (the all-stopword fallback
# in _query_terms and the unfiltered find_node path keep an English "die"/"hat"
# query workable), but deliberately OMIT "war"/"bald" (German was/soon) so
# English queries about "war" or "bald" are not clobbered. On the Romance side
# we likewise omit "comment" (FR how), "come" (IT how), "son"/"sin"/"con" (ES),
# and "pour"/"des" (FR) — all too common as English/code terms.
_QUERY_STOPWORDS = frozenset({
    # English
    "how", "what", "why", "when", "where", "which", "who", "whom", "whose",
    "does", "did", "is", "are", "was", "were", "be", "been", "being",
    "can", "could", "should", "would", "will", "shall", "may", "might", "must",
    "has", "have", "had", "the", "and", "but", "not", "for", "from", "with",
    "without", "into", "onto", "off", "that", "this", "these", "those", "there",
    "here", "its", "their", "them", "they", "about", "any", "all", "some",
    "work", "works", "working",
    # German (articles/conjunctions/question words/auxiliaries/prepositions)
    "der", "die", "das", "den", "dem", "ein", "eine", "und", "oder", "nicht",
    "wie", "wer", "wann", "wo", "warum", "wieso",
    "welche", "welcher", "welches",
    "ist", "sind", "wird", "wurde", "hat", "haben",
    "kann", "koennen", "können", "soll", "muss", "sich",
    "bei", "mit", "von", "fuer", "für", "ueber", "über", "nach", "aus",
    "gibt", "es",
    "funktioniert", "geaendert", "geändert", "aendert", "ändert",
    # French
    "pourquoi", "quand", "quel", "quelle", "quels", "quelles", "quoi",
    "qui", "que", "est", "sont", "fonctionne", "cette", "dans", "avec", "où",
    # Spanish
    "cómo", "como", "qué", "cuál", "cuáles", "cuándo", "dónde", "donde",
    "porque", "por", "para", "funciona", "está", "están", "hay",
    # Portuguese
    "qual", "quais", "quando", "onde", "são", "estão", "tem", "uma", "não",
    # Italian
    "perché", "cosa", "quale", "quali", "dove", "funziona", "sono", "che",
    "della",
})


def _query_terms(question: str) -> list[str]:
    """Split a query into searchable terms, segmenting Chinese text, then drop
    question/filler words (`_QUERY_STOPWORDS`, English plus common German/
    Romance-language fillers) so content words drive seeding. Falls back to the
    unfiltered terms if the query is all stopwords, so a question like "how does
    it work" or "wie funktioniert das" still seeds on something."""
    terms: list[str] = []
    for raw in question.split():
        if _has_chinese(raw):
            for seg in _segment_chinese(raw.lower().strip()):
                seg = seg.strip()
                if seg and _is_searchable(seg):
                    terms.append(seg)
        else:
            # Strip punctuation without touching Unicode characters (avoid NFKD mangling non-Latin scripts)
            for tok in re.findall(r"\w+", raw.lower()):
                if _is_searchable(tok):
                    terms.append(tok)
    content = [t for t in terms if t not in _QUERY_STOPWORDS]
    return content or terms


_EXACT_MATCH_BONUS = 1000.0
_PREFIX_MATCH_BONUS = 100.0
_SUBSTRING_MATCH_BONUS = 1.0
_SOURCE_MATCH_BONUS = 0.5
# The extraction spec stores the WHY of a concept as a `rationale` attribute
# on the node, not as a node of its own, so for a "why does X …" question that
# prose is often the only place the question's words occur (#2293). Score it
# as its own tier: below a label substring hit (the label still names the
# thing), above a source-path hit, and — like the source tier — never counted
# toward term coverage, so a long rationale adds recall without winning back
# an exact-label tier it did not earn.
_RATIONALE_MATCH_BONUS = 0.75
_ATTRIBUTE_MATCH_BONUS = 0.75


def _flatten_attr_text(val, parts: list[str]) -> None:
    if isinstance(val, dict):
        for k, v in val.items():
            parts.append(str(k))
            _flatten_attr_text(v, parts)
    elif isinstance(val, (list, tuple)):
        for item in val:
            _flatten_attr_text(item, parts)
    elif val is not None:
        parts.append(str(val))


def _node_attributes_text(data: dict) -> tuple[str, str]:
    """The node's `attributes` key-value pairs normalized and tokenized for search."""
    attrs = data.get("attributes")
    if not isinstance(attrs, dict) or not attrs:
        return "", ""
    parts: list[str] = []
    _flatten_attr_text(attrs, parts)
    if not parts:
        return "", ""
    raw_text = " ".join(parts)
    norm = _strip_diacritics(raw_text).lower()
    tokens = " ".join(_search_tokens(norm))
    return norm, tokens



def _compute_idf(G: nx.Graph, terms: list[str]) -> dict[str, float]:
    """IDF weights for query terms, cached in G.graph['_idf_cache'].

    Common terms like 'error' or 'exception' that match hundreds of nodes get
    low weights; rare identifiers like 'FooBarService' get high weights.
    Cache is stored on the graph object itself so it auto-invalidates when
    a hot-reload replaces G with a new object.
    """
    cache: dict[str, float] = G.graph.setdefault("_idf_cache", {})
    N = G.number_of_nodes() or 1
    uncached = [t for t in terms if t not in cache]
    if uncached:
        df: dict[str, int] = {t: 0 for t in uncached}
        for _, data in G.nodes(data=True):
            norm_label = (
                data.get("norm_label") or _strip_diacritics(data.get("label") or "")
            ).lower()
            for t in uncached:
                if t in norm_label:
                    df[t] += 1
        for t in uncached:
            cache[t] = math.log(1 + N / (1 + df[t]))
    return {t: cache.get(t, math.log(1 + N)) for t in terms}


def _trigrams(text: str) -> set[str]:
    """Character trigrams of `text`; for <3-char text the whole string is the key."""
    if len(text) < 3:
        return {text} if text else set()
    return {text[i:i + 3] for i in range(len(text) - 2)}


def _node_rationale_text(data: dict) -> str:
    """The node's `rationale` attribute normalized like a label (diacritics
    folded, lower-cased) for substring matching. Semantic cleanup writes it as
    one string (several sources joined with blank lines); an extractor may hand
    over a list — join it. Missing or empty -> "" so callers can `if rationale`.
    """
    raw = data.get("rationale")
    if not raw:
        return ""
    if isinstance(raw, (list, tuple)):
        raw = " ".join(str(part) for part in raw if part)
    return _strip_diacritics(str(raw)).lower()


def _node_search_text(data: dict, nid: str) -> str:
    """Concatenate every field _score_nodes / _find_node match a query against, so
    one trigram index over this text is a complete candidate generator for both.

    - `rationale` (normalized via `_node_rationale_text`) feeds _score_nodes'
      rationale tier (#2293); appended last, and only when present, so every
      other field position is unchanged.

    - `norm_label` and `source_file` feed _score_nodes' per-term substring tiers.
    - `label_tokens` (the space-joined token form) feeds _find_node's
      `term in label_tokens` branch, where a multi-word `term` can span a token
      boundary that punctuation hides in `norm_label` (e.g. query "foo bar" matches
      label "foo.bar" only via its tokenized form).
    - `source_tokens` feeds _find_node's exact source-file path lookup, where a
      query like "app/api/example/route.ts" tokenizes to "app api example route ts".
    - `nid` feeds the whole-query `joined == nid_lower` tier.
    - a trailing diacritic-folded `nid` feeds _find_node's `norm_query == nid_norm`
      tier. Every query path folds through `_strip_diacritics` (NFKD), so a raw-only
      id field leaves the needle and the posting under different normal forms and
      the node is dropped before any predicate runs (#2467). Hangul is the common
      case: NFKD decomposes a syllable into conjoining jamo, which have combining
      class 0 and therefore survive the combining-character filter. The field is
      appended only when the fold actually differs, so the text an all-ASCII graph
      indexes — and every field position the other readers rely on — is unchanged.

    NUL separators stop a trigram from spanning two fields (a query never contains
    NUL, so a cross-field trigram can never be a real match).
    """
    norm_label = data.get("norm_label") or _strip_diacritics(data.get("label") or "").lower()
    label_tokens = " ".join(_search_tokens(data.get("label") or ""))
    source = (data.get("source_file") or "").lower()
    source_tokens = " ".join(_search_tokens(data.get("source_file") or ""))
    nid_text = str(nid).lower()
    fields = (norm_label, label_tokens, nid_text, source, source_tokens)
    if not nid_text.isascii():
        nid_folded = _strip_diacritics(str(nid)).lower()
        if nid_folded != nid_text:
            fields += (nid_folded,)
    rationale = _node_rationale_text(data)
    if rationale:
        fields += (rationale,)
    attr_norm, attr_tokens = _node_attributes_text(data)
    if attr_norm:
        fields += (attr_norm, attr_tokens)
    return "\x00".join(fields)


def _get_trigram_index(G: nx.Graph) -> dict:
    """Lazily build and cache a trigram -> node-position postings map on the graph.

    Cached on `G.graph` so it auto-invalidates when a hot-reload swaps in a
    fresh graph object, exactly like `_idf_cache`. `set_cache` memoizes per-trigram
    id-sets across queries within one graph generation.
    """
    idx = G.graph.get("_trigram_index")
    if idx is not None:
        return idx
    ids = list(G.nodes())
    postings: dict[str, array] = {}
    for i, nid in enumerate(ids):
        for g in _trigrams(_node_search_text(G.nodes[nid], nid)):
            bucket = postings.get(g)
            if bucket is None:
                bucket = array("i")
                postings[g] = bucket
            bucket.append(i)
    idx = {"ids": ids, "postings": postings, "set_cache": {}}
    G.graph["_trigram_index"] = idx
    return idx


def _trigram_candidates(G: nx.Graph, needles: list[str], *, guard_frac: float = 0.10) -> list[str] | None:
    """Node IDs whose text could contain any `needle` as a substring, via the
    trigram index — a *superset* the caller then re-scores with the exact predicates.

    Returns candidates in graph-iteration order (so order-sensitive callers like
    _find_node stay byte-identical to a full scan), or **None** when the index isn't
    worth it — a needle is too short to trigram, or its rarest trigram is still
    common enough that the candidate set would approach the whole graph. The caller
    falls back to the full scan, preserving the never-worse contract. The guard is
    cheap: postings-length lookups only, no set intersection.
    """
    idx = _get_trigram_index(G)
    ids, postings, set_cache = idx["ids"], idx["postings"], idx["set_cache"]
    n = len(ids)
    if n == 0:
        return []
    needles = [s for s in needles if s]
    thresh = int(n * guard_frac)
    for s in needles:
        tgs = _trigrams(s)
        if not tgs or any(len(g) < 3 for g in tgs):
            return None  # too short to trigram-filter
        present = [len(postings[g]) for g in tgs if g in postings]
        if not present:
            continue  # this needle matches nothing — contributes no candidates
        if min(present) > thresh:
            return None  # rarest trigram still too common -> not worth the index
    cand: set[int] = set()
    for s in needles:
        sets: list[set] | None = []
        for g in _trigrams(s):
            bucket = postings.get(g)
            if bucket is None:
                sets = None  # a trigram absent everywhere -> needle matches nothing
                break
            cached = set_cache.get(g)
            if cached is None:
                cached = set(bucket)
                set_cache[g] = cached
            sets.append(cached)
        if not sets:
            continue
        sets.sort(key=len)  # intersect smallest-first
        hit = set(sets[0])
        for other in sets[1:]:
            hit &= other
            if not hit:
                break
        cand |= hit
    return [ids[i] for i in sorted(cand)]


class _QueryScores(NamedTuple):
    """Per-query scoring result, returned by the private `_score_query` helper.

    `ranked` is the existing ordered `(score, node_id)` ranking produced by the
    combined query scorer (the value `_score_nodes` always returned). When the
    caller asks for it via `collect_per_term_seeds=True`, `best_seed_by_term`
    additionally carries the winning node id for each normalized search token —
    the seed `_pick_seeds` would have picked for that token via the now-retired
    per-token `_score_nodes([token])` rescoring pass — computed in the *same*
    per-node traversal so the query path makes exactly one graph scoring pass
    regardless of query length. Empty when `collect_per_term_seeds=False`.
    """
    ranked: list[tuple[float, str]]
    best_seed_by_term: dict[str, str]


def _score_nodes(G: nx.Graph, terms: list[str]) -> list[tuple[float, str]]:
    """Combined query scorer returning the existing ranked `(score, node_id)` list.

    Backwards-compatible thin wrapper around `_score_query` for path, explain,
    tests, and every other caller that only needs the combined ranking. The
    per-term seed metadata computed by `_score_query` (when requested) is
    discarded here so existing callers see no API or runtime-cost change.
    """
    return _score_query(G, terms, collect_per_term_seeds=False).ranked


def _score_query(
    G: nx.Graph, terms: list[str], *, collect_per_term_seeds: bool
) -> _QueryScores:
    """Single-pass combined scorer that optionally also records the best seed
    for each normalized query token.

    The combined ranking is byte-identical to what `_score_nodes` produced
    before the refactor; `_score_nodes` is now a thin wrapper that asks for
    `collect_per_term_seeds=False` and returns only `.ranked`.

    When `collect_per_term_seeds=True`, the per-token singleton winner is
    computed alongside the combined score in the *same* per-node visit (it
    reuses the same `norm_label` / `label_tokens` / `source` already evaluated
    for the combined tier), so `_query_graph_text` can feed `best_seed_by_term`
    straight into `_pick_seeds` and skip the T additional whole-graph rescoring
    passes the old per-token `_score_nodes([token])` loop ran.

    Singleton-winner semantics match the legacy per-token path exactly. The
    score itself mirrors `_score_nodes([token])` with `n_terms == 1` (so the
    coverage term is 1 and the per-token tier is unscaled) plus the broader
    joined-singlet tier (which also checks `label_tokens` and `nid_lower`).
    Tie-break order is (1) highest singleton score, (2) highest graph degree,
    (3) shortest displayed label, (4) lexicographically smallest node id —
    exactly what `max(tied, key=degree)` over a sort by `(-score, label_len,
    nid)` produced in the legacy `_pick_seeds` per-token loop. The combined
    trigram candidate set (needles `norm_terms + [joined]`) is a superset of
    each per-token `[t]` candidate set, so iterating combined candidates
    discovers every non-zero singleton-score node for every term.
    """
    scored: list[tuple[float, str]] = []
    # Dedupe tokens, order-preserving (as _pick_seeds already does): a repeated
    # query word must not double-count every tier, and with coverage scaling
    # below it would also inflate the matched-term ratio (#1602).
    norm_terms = list(dict.fromkeys(tok for t in terms for tok in _search_tokens(t)))
    n_terms = len(norm_terms)
    idf = _compute_idf(G, norm_terms)
    # Whole-query string for full-label matching (mirrors _find_node's `term`).
    joined = " ".join(norm_terms)
    # Weight the full-query bonus by the rarest constituent term so a specific
    # multi-word label still outweighs common-token noise; floor at 1.0.
    joined_w = max((idf.get(t, 1.0) for t in norm_terms), default=1.0)
    # Trigram prefilter: score only nodes whose text could match a term, falling
    # back to the whole graph when the index isn't selective. The result is
    # identical either way — the per-node scoring below is unchanged and a
    # non-candidate node always scores 0. (IDF above stays a whole-graph statistic.)
    candidate_ids = _trigram_candidates(G, norm_terms + ([joined] if joined else []))
    node_iter = (
        G.nodes(data=True) if candidate_ids is None
        else ((nid, G.nodes[nid]) for nid in candidate_ids)
    )
    # Per-token best tracking, only when the caller (the query path) wants the
    # seed metadata. The key tuple is the full multi-key tie-break
    # (`(-singleton_score, -degree, label_len, nid)`), so `min` over the
    # stored key mirrors the legacy `max(tied, key=degree)` over a
    # (-score, label_len, nid)-sorted term_scored list. `None` is comparable
    # as "smaller" than every tuple, so the first non-zero candidate seeds the
    # entry without a separate `if t not in best_by_term` branch.
    best_by_term: dict[str, tuple[tuple, str]] | None = (
        {} if collect_per_term_seeds else None
    )
    for nid, data in node_iter:
        norm_label = data.get("norm_label") or _strip_diacritics(data.get("label") or "").lower()
        bare_label = norm_label.rstrip("()")
        # Tokenized form of the label (punctuation stripped, same transform as the
        # query). norm_label may still carry punctuation like ':' or '-', which a
        # tokenized query can never equal; comparing token-joined forms on both
        # sides makes "uoce: dehumidifier driver" match query "uoce dehumidifier
        # driver".
        label_tokens = " ".join(_search_tokens(data.get("label") or ""))
        source = (data.get("source_file") or "").lower()
        rationale = _node_rationale_text(data)
        attr_norm, attr_tokens = _node_attributes_text(data)
        # `nid_lower` is needed both by the full-query tier (`if joined`) and by
        # the per-token singleton tier (joined-singlet exact-match check). When
        # neither runs (`joined` empty AND not collecting seeds) skip the call;
        # this preserves the single-query-time perf where nid_lower was lazy.
        nid_lower = nid.lower() if (joined or collect_per_term_seeds) else ""
        score = 0.0
        # Full-query tier: a multi-word query that equals (or prefixes) the whole
        # label must dominate the per-token bag-of-words sums below, so `path`/
        # `query` resolve the same node `explain` does (via _find_node). Without
        # this, no single token equals a multi-word label, the per-token exact
        # tier never fires, and every node sharing the token set ties -> arbitrary
        # node-id sort -> wrong/disconnected endpoint -> false "No path found".
        if joined:
            if joined in (norm_label, bare_label, label_tokens, nid_lower):
                score += _EXACT_MATCH_BONUS * 10 * joined_w
            elif (
                norm_label.startswith(joined)
                or bare_label.startswith(joined)
                or label_tokens.startswith(joined)
            ):
                score += _PREFIX_MATCH_BONUS * 10 * joined_w
        # Term coverage (#1602): scale the per-term exact/prefix tiers by the
        # squared fraction of query terms the node's LABEL matches, so a lone
        # generic word that happens to equal a short label (query term "home"
        # vs. a home() leaf) cannot bury nodes that match several of the
        # query's terms. Squaring matters because the exact tier is 10x the
        # prefix tier: at linear coverage a 1-of-10-terms exact match still
        # outscores a 3-of-10 prefix+substring match. Single-term and
        # full-coverage queries are unchanged (coverage == 1), so identifier
        # lookups keep exact-match dominance. Source-file hits score but do
        # not count as coverage: a colliding leaf whose directory shares
        # tokens with the query (common near the intended target) must not
        # win back its exact tier via path fragments. The substring/source
        # bonuses and the full-query tier above stay unscaled.
        matched = 0
        tiered = 0.0
        for t in norm_terms:
            w = idf.get(t, 1.0)
            # Per-tier contributions for this token, kept separate so the
            # singleton tracking below can reuse them without re-evaluating
            # the same predicates. Three-tier precedence: exact > prefix >
            # substring (take the strongest tier per term so a single term
            # cannot double-count).
            tier_value = 0.0
            substr_value = 0.0
            source_value = 0.0
            if t == norm_label or t == bare_label:
                tier_value = _EXACT_MATCH_BONUS * w
                matched += 1
            elif norm_label.startswith(t) or bare_label.startswith(t):
                tier_value = _PREFIX_MATCH_BONUS * w
                matched += 1
            elif t in norm_label:
                substr_value = _SUBSTRING_MATCH_BONUS * w
                score += substr_value
                matched += 1
            if t in source:
                source_value = _SOURCE_MATCH_BONUS * w
                score += source_value
            # Rationale tier (#2293): recall for "why" questions whose words
            # live only in the attribute. Adds to the score, not to `matched`.
            rationale_value = 0.0
            if rationale and t in rationale:
                rationale_value = _RATIONALE_MATCH_BONUS * w
                score += rationale_value
            # Attribute tier (#3625): recall for questions naming attributes or literal values.
            attr_value = 0.0
            if attr_norm and (t in attr_norm or t in attr_tokens):
                attr_value = _ATTRIBUTE_MATCH_BONUS * w
                score += attr_value
            tiered += tier_value
            if collect_per_term_seeds and best_by_term is not None:
                # Singleton score for [t] on this node, mirroring
                # `_score_nodes(G, [t])` exactly (n_terms == 1, no coverage
                # scaling). The joined-singlet tier is broader than the per-
                # token tier: it also checks `label_tokens` and `nid_lower`,
                # matching the legacy single-token `_score_nodes([t])` call
                # (where `joined == t`).
                if t in (norm_label, bare_label, label_tokens, nid_lower):
                    singleton = _EXACT_MATCH_BONUS * 10 * w
                elif (
                    norm_label.startswith(t)
                    or bare_label.startswith(t)
                    or label_tokens.startswith(t)
                ):
                    singleton = _PREFIX_MATCH_BONUS * 10 * w
                else:
                    singleton = 0.0
                singleton += tier_value + substr_value + source_value + rationale_value + attr_value
                if singleton > 0:
                    # Tie-break key mirrors the legacy sort+max(degree):
                    # (-singleton, -degree, label_len, nid) — the minimum
                    # tuple wins, exactly matching max(tied, key=degree)
                    # over (label_len asc, nid asc)-sorted ties.
                    key = (-singleton, -G.degree(nid), len(data.get("label") or nid), nid)
                    cur = best_by_term.get(t)
                    if cur is None or key < cur[0]:
                        best_by_term[t] = (key, nid)
        if tiered:
            score += tiered * (matched / n_terms) ** 2
        if score > 0:
            scored.append((score, nid))
    # Sort by score desc; break ties toward the shorter label so a concise exact
    # match beats a longer superset that happens to share the same score.
    scored.sort(key=lambda s: (-s[0], len(G.nodes[s[1]].get("label") or s[1]), s[1]))
    best_seed_by_term: dict[str, str] = {}
    if collect_per_term_seeds and best_by_term:
        best_seed_by_term = {t: nid for t, (_key, nid) in best_by_term.items()}
    return _QueryScores(ranked=scored, best_seed_by_term=best_seed_by_term)


def _pick_scored_endpoint(G: nx.Graph, scored: list[tuple[float, str]], query: str) -> str:
    """Pick a path endpoint from a _score_nodes result, preferring full-token matches.

    The full-query tier in _score_nodes only fires when the query equals or
    prefixes a label, so a query that is a token *subset* of the intended label
    (query "Reject-everything judge" vs. label "Degenerate Reject-Everything
    Judge") gets no bonus, and a node prefix-matching one rare token (label
    "Rejection Summary") can out-score it on IDF alone. Committing to scored[0]
    then anchors the path on an unrelated — often disconnected — node and yields
    a false "No path found". Scan the score-ordered list and take the first
    candidate whose label contains EVERY query token; when the top candidate
    already full-matches, or no candidate does, this is exactly scored[0].

    `scored` must be non-empty (both callers return early on no match).
    """
    qtokens = set(_search_tokens(query))
    if not qtokens:
        return scored[0][1]
    for _score, nid in scored:
        if qtokens <= set(_search_tokens(G.nodes[nid].get("label") or nid)):
            return nid
    return scored[0][1]


def _pick_seeds(
    scored: list[tuple[float, str]],
    max_k: int = 3,
    gap_ratio: float = 0.2,
    *,
    G: "nx.Graph | None" = None,
    best_seed_by_term: dict[str, str] | None = None,
) -> list[str]:
    """Select BFS seed nodes, stopping when score drops too far below the top.

    Prevents high-frequency noise terms (error, exception) from stealing seed
    slots from a dominant identifier match. When FooBarService scores 1000 and
    error nodes score 1.0, only FooBarService is seeded — the score gap is 99.9%
    which is well above the 20% threshold that would allow additional seeds.

    That same gap_ratio cutoff has a failure mode on multi-term natural-language
    queries: if one term happens to hit an EXACT label match on a node that is
    otherwise unrelated to the query's intent (e.g. a common word that is also
    used as an unrelated identifier or field name elsewhere in the corpus), it
    can outscore every SUBSTRING match on the query's other, actually-relevant
    terms by ~1000x (see `_EXACT_MATCH_BONUS` vs. `_SUBSTRING_MATCH_BONUS`).
    The 20%-gap cutoff then silently discards all of those substring-tier
    seeds, so the BFS traversal only ever explores the neighborhood of the one
    unrelated exact match — see #1445.

    When `G` and `best_seed_by_term` are supplied, this guarantees at least one
    seed per distinct query term that has any match at all, so one term's
    incidental collision cannot starve out the others. The per-token winners
    in `best_seed_by_term` are precomputed by `_score_query` (during the same
    traversal that produced `scored`) so this function no longer rescores the
    graph per term — see #1445 and the `_score_query` docstring.

    Coverage scaling in _score_nodes (#1602) now dampens a lone collision's
    exact tier on multi-term queries, which brings label-matching relevant
    nodes back inside the gap window; this per-term guarantee remains
    load-bearing for relevant nodes matched only via substrings, whose flat
    scores a dampened collision can still exceed.
    """
    if not scored:
        return []

    # Deduplicate seeds by (normalized) label so a generic, homonymous symbol —
    # e.g. dozens of route handlers all labelled `GET`/`POST`, or a `handler`
    # repeated across a framework — contributes at most one seed instead of
    # consuming every slot and flooding the BFS with near-identical neighborhoods
    # (#1766). The key mirrors _score_nodes' normalization so `GET`/`Get`/`get`
    # collapse together. When G is absent we can't read labels, so fall back to
    # the (unique) node id, which is a no-op — preserving the old behavior.
    def _seed_label_key(nid: str) -> str:
        if G is None:
            return nid
        data = G.nodes[nid]
        return (data.get("norm_label")
                or _strip_diacritics(data.get("label") or "").lower()) or nid

    top_score = scored[0][0]
    seeds: list[str] = []
    seen_labels: set[str] = set()
    for score, nid in scored:
        if len(seeds) >= max_k:
            break
        if seeds and score < top_score * gap_ratio:
            break
        key = _seed_label_key(nid)
        if key in seen_labels:
            continue
        seen_labels.add(key)
        seeds.append(nid)

    if G is not None and best_seed_by_term:
        # Guarantee one seed per distinct query term that has any match at all,
        # so an incidental exact match on one term cannot starve matches on
        # other terms (#1445). Iterate tokens in a deterministic sorted order
        # so seeds added by this loop have a stable order independent of dict
        # iteration — preserving the legacy `_pick_seeds(terms=...)` behavior
        # which iterated `sorted({tok ...})`. Per-token winners arrive
        # precomputed in `best_seed_by_term` from `_score_query`'s single
        # traversal, so `_pick_seeds` no longer rescoring the graph per term.
        # The per-label dedup cap also gates these additions, so the guarantee
        # cannot reintroduce a second copy of an already-seeded generic label
        # (#1766).
        for term in sorted(best_seed_by_term):
            best_nid = best_seed_by_term[term]
            # Honor the same per-label cap so the per-term guarantee can't
            # reintroduce a second copy of an already-seeded generic label.
            key = _seed_label_key(best_nid)
            if best_nid not in seeds and key not in seen_labels:
                seen_labels.add(key)
                seeds.append(best_nid)
    return seeds


# Verb-shaped tokens that express the RELATION a query asks about ("who calls
# X", "what uses Y") rather than a symbol to look up. `_query_terms` keeps them
# on purpose (a corpus can legitimately define an identifier named `calls`, see
# #1597), but they must not be handed a guaranteed seed slot in `_pick_seeds`:
# an incidental prefix match (e.g. "calls" prefixing `.callStoreWithAmount()`)
# would otherwise seat an unrelated decoy as a BFS root (#2507). Demotion
# happens at the `_query_graph_text` call site, so `_score_query`'s ranking —
# where such a verb can still win a seat on merit via the gap window — is
# untouched. Deliberately verbs only; relation NOUNS (module, field, return)
# stay eligible for the guarantee.
_RELATIONAL_INTENT_TERMS: frozenset[str] = frozenset({
    "call", "calls", "called", "caller", "callers",
    "invoke", "invokes", "invoked",
    "use", "uses", "used", "using",
    "import", "imports", "imported",
    "export", "exports", "exported",
    "extend", "extends", "extended",
    "implement", "implements", "implemented",
    "depend", "depends",
    "reference", "references", "referenced",
})


_CONTEXT_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("call", ("call", "calls", "called", "caller", "callers", "invoke", "invokes", "invoked")),
    ("import", ("import", "imports", "imported", "module", "modules")),
    ("field", ("field", "fields", "member", "members", "property", "properties")),
    ("parameter_type", ("parameter", "parameters", "param", "params", "argument", "arguments")),
    ("return_type", ("return", "returns", "returned")),
    ("generic_arg", ("generic", "generics", "template", "templates")),
)


_CONTEXT_FILTER_ALIASES: dict[str, str] = {
    "param": "parameter_type",
    "params": "parameter_type",
    "parameter": "parameter_type",
    "parameters": "parameter_type",
    "argument": "parameter_type",
    "arguments": "parameter_type",
    "arg": "parameter_type",
    "args": "parameter_type",
    "return": "return_type",
    "returns": "return_type",
    "returned": "return_type",
    "generic": "generic_arg",
    "generics": "generic_arg",
    "template": "generic_arg",
    "templates": "generic_arg",
    "annotation": "attribute",
    "annotations": "attribute",
    "decorator": "attribute",
    "decorators": "attribute",
    "calls": "call",
    "called": "call",
    "invoke": "call",
    "invocation": "call",
    "fields": "field",
    "property": "field",
    "properties": "field",
    "member": "field",
    "members": "field",
    "imports": "import",
    "imported": "import",
    "module": "import",
    "modules": "import",
    "exports": "export",
    "exported": "export",
}


def _normalize_context_filters(filters: list[str] | None) -> list[str]:
    if not filters:
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for value in filters:
        key = _strip_diacritics(str(value)).strip().lower()
        if not key:
            continue
        key = _CONTEXT_FILTER_ALIASES.get(key, key)
        if key not in seen:
            seen.add(key)
            normalized.append(key)
    return normalized


def _infer_context_filters(question: str) -> list[str]:
    lowered = {
        _strip_diacritics(token).lower()
        for token in question.replace("?", " ").replace(",", " ").split()
    }
    inferred: list[str] = []
    for context, hints in _CONTEXT_HINTS:
        if any(hint in lowered for hint in hints):
            inferred.append(context)
    return inferred


def _resolve_context_filters(question: str, explicit_filters: list[str] | None = None) -> tuple[list[str], str | None]:
    normalized = _normalize_context_filters(explicit_filters)
    if normalized:
        return normalized, "explicit"
    inferred = _infer_context_filters(question)
    if inferred:
        return inferred, "heuristic"
    return [], None


def _filter_graph_by_context(G: nx.Graph, context_filters: list[str] | None) -> nx.Graph:
    filters = set(_normalize_context_filters(context_filters))
    if not filters:
        return G
    H = G.__class__()
    H.add_nodes_from(G.nodes(data=True))
    if isinstance(G, (nx.MultiGraph, nx.MultiDiGraph)):
        for u, v, key, data in G.edges(keys=True, data=True):
            if data.get("context") in filters:
                H.add_edge(u, v, key=key, **data)
    else:
        for u, v, data in G.edges(data=True):
            if data.get("context") in filters:
                H.add_edge(u, v, **data)
    return H


def _complete_induced_edges(G: nx.Graph, visited: set[str], edges_seen: list[tuple]) -> None:
    """Append edges between visited nodes that the traversal never recorded (#2323).

    Both traversals only record an edge that *discovers* an unvisited neighbour,
    so what they return is a traversal tree, not the induced subgraph over the
    nodes they return. `_bfs` marks every seed visited up front, so an edge
    between two seeds can never be recorded — the reported symptom, where both
    endpoints render and the edge between them does not. It drops ordinary
    cross-edges for the same reason. `_dfs` appends on push rather than on
    visit, so it already captured those; its one gap is an edge between two
    non-seed hubs, since neither endpoint is ever expanded.

    Scans only edges incident to `visited`, so cost tracks the subgraph rather
    than the whole graph, bounded by O(2E) overall. A visited hub is rescanned
    in full even though the traversal deliberately did not expand it — that is
    unavoidable, since a hub-to-hub edge is exactly the case `_dfs` misses.
    `G` here is the context-filtered `traversal_graph` (see
    `_query_graph_text`), so a filtered-out relation cannot reappear.

    Self-loops are skipped. A recursive function legitimately carries one, but
    neither traversal has ever recorded one (`n` is always already visited when
    its own self-loop is examined), and surfacing them is a separate output
    change from the missing edges reported here.

    Dedup keys on the ordered pair for directed graphs and the unordered pair
    otherwise: on a DiGraph `u->v` and `v->u` are genuinely distinct edges
    (mutual recursion, circular imports), and collapsing them would drop a real
    one. On a multigraph parallel edges collapse to one entry, matching the
    renderer, which already shows only the first (`_subgraph_to_text`).

    Traversal edges keep their discovery order; completions are appended after.
    """
    directed = G.is_directed()

    def _key(u: str, v: str):
        return (u, v) if directed else frozenset((u, v))

    seen = {_key(u, v) for u, v in edges_seen}
    # sorted() so the appended order can't shift run-to-run with CPython's
    # per-process string-hash seed, the same reason the renderer sorts (#1753).
    for u, v in G.edges(sorted(visited)):
        if u == v or v not in visited:
            continue
        key = _key(u, v)
        if key in seen:
            continue
        seen.add(key)
        edges_seen.append((u, v))


def _bfs(G: nx.Graph, start_nodes: list[str], depth: int) -> tuple[set[str], list[tuple]]:
    # Compute hub threshold: nodes above this degree are not expanded as transit.
    # p99 of degree distribution, floored at 50 to avoid over-blocking small graphs.
    degrees = [G.degree(n) for n in G.nodes()]
    if degrees:
        degrees_sorted = sorted(degrees)
        p99_idx = int(len(degrees_sorted) * 0.99)
        hub_threshold = max(50, degrees_sorted[p99_idx])
    else:
        hub_threshold = 50
    seed_set = set(start_nodes)
    visited: set[str] = set(start_nodes)
    frontier = set(start_nodes)
    edges_seen: list[tuple] = []
    for _ in range(depth):
        next_frontier: set[str] = set()
        for n in frontier:
            # Don't expand through high-degree hubs (except seeds - a hub that
            # is the starting node should still be explored).
            if n not in seed_set and G.degree(n) >= hub_threshold:
                continue
            for neighbor in G.neighbors(n):
                if neighbor not in visited:
                    next_frontier.add(neighbor)
                    edges_seen.append((n, neighbor))
        visited.update(next_frontier)
        frontier = next_frontier
    _complete_induced_edges(G, visited, edges_seen)
    return visited, edges_seen


def _dfs(G: nx.Graph, start_nodes: list[str], depth: int) -> tuple[set[str], list[tuple]]:
    degrees = [G.degree(n) for n in G.nodes()]
    if degrees:
        degrees_sorted = sorted(degrees)
        p99_idx = int(len(degrees_sorted) * 0.99)
        hub_threshold = max(50, degrees_sorted[p99_idx])
    else:
        hub_threshold = 50
    seed_set = set(start_nodes)
    visited: set[str] = set()
    edges_seen: list[tuple] = []
    stack = [(n, 0) for n in reversed(start_nodes)]
    while stack:
        node, d = stack.pop()
        if node in visited or d > depth:
            continue
        visited.add(node)
        if node not in seed_set and G.degree(node) >= hub_threshold:
            continue
        for neighbor in G.neighbors(node):
            if neighbor not in visited:
                stack.append((neighbor, d + 1))
                edges_seen.append((node, neighbor))
    _complete_induced_edges(G, visited, edges_seen)
    return visited, edges_seen


def _subgraph_to_text(G: nx.Graph, nodes: set[str], edges: list[tuple], token_budget: int = 2000, *, seeds: list[str] | None = None) -> str:
    """Render subgraph as text, cutting at token_budget (approx 3 chars/token).

    seeds: exact-match nodes rendered first before the degree-sorted expansion,
    so the queried symbol always appears at the top of the output.
    """
    char_budget = token_budget * 3
    lines = []
    # Work-memory overlay (derived sidecar) stashed on the graph at load time.
    # Empty when no sidecar exists, so un-annotated output stays byte-identical.
    overlay = getattr(G, "graph", {}).get("_learning_overlay", {}) or {}
    seed_set = set(seeds or [])
    seed_hits = [n for n in (seeds or []) if n in nodes]
    # Rank non-seed nodes by hop distance from the seeds so the node that answers
    # the query (a direct hit or its close neighbors) survives the budget cut
    # instead of being pushed past it by incidental high-degree hubs (#BUG2). BFS
    # discovery order was discarded upstream (_bfs returns a set), so recompute
    # layers here over BOTH edge directions. Deterministic: neighbor iteration is
    # insertion-ordered and the sort key ends in str(n) (no hash-order).
    def _adj(n):
        if G.is_directed():
            yield from G.successors(n)
            yield from G.predecessors(n)
        else:
            yield from G.neighbors(n)
    dist: dict[str, int] = {n: 0 for n in seed_hits}
    frontier, hop = seed_hits, 0
    while frontier:
        hop += 1
        nxt = []
        for n in frontier:
            for nb in _adj(n):
                if nb in nodes and nb not in dist:
                    dist[nb] = hop
                    nxt.append(nb)
        frontier = nxt
    ordered = seed_hits + sorted(
        nodes - seed_set,
        key=lambda n: (dist.get(n, 1 << 30), -G.degree(n), str(n)),
    )
    for nid in ordered:
        d = G.nodes[nid]
        # Every LLM-derived field passes through sanitize_label before being
        # concatenated into MCP tool output (F-010): an attacker who controls a
        # corpus document can otherwise inject ANSI escapes, fake graphify-out
        # log lines, or prompt-injection markup into the model's context via
        # source_file / source_location / community.
        # The learning= suffix is appended INSIDE the bracket and BEFORE the
        # budget check below, so it counts in char_budget accounting.
        entry = overlay.get(str(nid))
        learning_suffix = ""
        if entry:
            status = sanitize_label(str(entry.get("status", "")))
            if status:
                learning_suffix = f" learning={status}{':stale' if entry.get('stale') else ''}"
        attrs = d.get("attributes")
        attrs_suffix = ""
        if isinstance(attrs, dict) and attrs:
            pairs = []
            for k, v in sorted(attrs.items()):
                if isinstance(v, (dict, list)):
                    v_str = json.dumps(v, sort_keys=True)
                elif isinstance(v, str):
                    v_str = f'"{v}"'
                elif isinstance(v, bool):
                    v_str = "true" if v else "false"
                elif v is None:
                    v_str = "null"
                else:
                    v_str = str(v)
                if len(v_str) > 60:
                    v_str = v_str[:57] + "..."
                pairs.append(f"{k}={v_str}")
                if len(pairs) >= 10:
                    pairs.append("...")
                    break
            attrs_summary = ", ".join(pairs)
            if len(attrs_summary) > 200:
                attrs_summary = attrs_summary[:197] + "..."
            attrs_suffix = f" attrs={{{sanitize_label(attrs_summary)}}}"
        line = (
            f"NODE {sanitize_label(d.get('label', nid))} "
            f"[src={sanitize_label(str(d.get('source_file', '')))} "
            f"loc={sanitize_label(str(d.get('source_location', '')))} "
            f"community={sanitize_label(str(d.get('community_name') or d.get('community', '')))}"
            f"{learning_suffix}"
            f"{attrs_suffix}]"
        )
        lines.append(line)
    for u, v in edges:
        if u in nodes and v in nodes:
            raw = G[u][v]
            d = next(iter(raw.values()), {}) if isinstance(G, (nx.MultiGraph, nx.MultiDiGraph)) else raw
            # (u, v) is BFS/DFS visit order, not necessarily the true edge
            # direction: on an undirected graph G.neighbors() walks callers
            # and callees alike, so a caller->callee edge renders backwards
            # whenever the callee is visited first. _src/_tgt (stashed on the
            # edge data by the `query` CLI loader) carry the real direction;
            # fall back to (u, v) for graphs/edges that don't set them.
            src = d.get("_src", u)
            tgt = d.get("_tgt", v)
            # Guard against a stray/dangling _src/_tgt (hand-edited or adversarial
            # graph.json): only trust them when they name exactly this edge's
            # endpoints, else fall back to (u, v). Without this, G.nodes[src]
            # would KeyError on an unknown id (#2080 review).
            if {src, tgt} != {u, v}:
                src, tgt = u, v
            context = d.get("context")
            context_suffix = f" context={sanitize_label(str(context))}" if context else ""
            # The relation SITE (call/import/reference line in the source's
            # file), not a def line — so "who calls X" cites a clickable call
            # location, not the caller's def (#BUG1).
            _loc = str(d.get("source_location") or "")
            at_suffix = (
                f" at={sanitize_label(str(d.get('source_file') or ''))}:{sanitize_label(_loc)}"
                if _loc else ""
            )
            line = (
                f"EDGE {sanitize_label(G.nodes[src].get('label', src))} "
                f"--{sanitize_label(str(d.get('relation', '')))} "
                f"[{sanitize_label(str(d.get('confidence', '')))}{context_suffix}]--> "
                f"{sanitize_label(G.nodes[tgt].get('label', tgt))}{at_suffix}"
            )
            lines.append(line)
    output = "\n".join(lines)
    if len(output) > char_budget:
        cut_at = output[:char_budget].rfind("\n")
        cut_at = cut_at if cut_at > 0 else char_budget
        # Never cut the seed nodes: they render first, so if the budget lands
        # inside the seed block, extend the cut to cover it. The symbol the
        # question named must always be in the answer (#BUG2). Seeds are bounded
        # (_pick_seeds max_k + one per term), so the overshoot is a few lines.
        if seed_hits:
            seed_block_end = sum(len(lines[i]) + 1 for i in range(len(seed_hits))) - 1
            cut_at = max(cut_at, min(seed_block_end, len(output)))
        total_nodes = sum(1 for l in lines if l.startswith("NODE "))
        shown_nodes = output[:cut_at].count("\nNODE ") + (1 if output.startswith("NODE ") else 0)
        cut_count = total_nodes - shown_nodes
        # Nodes render before edges, so a char-budget overflow whose cut lands
        # past the last NODE line drops only trailing edges — no whole node is
        # lost. Announcing "showing N of N nodes … among the 0 cut nodes" then
        # reads as a false truncation warning that teaches an agent to distrust a
        # complete answer and burn follow-up narrowing calls for nodes that were
        # never cut (#2601). When every node is shown the answer is complete, so
        # edges are never dropped either (returning output[:cut_at] here would
        # silently truncate them) — but that completeness guarantee is exactly
        # why a query can quietly cost 4-6x its requested budget once the last
        # node crosses the fit line (#2784): the check above only ever compared
        # the FULL output (nodes+edges) against char_budget, so this branch was
        # already known to be over budget, yet said nothing about it. Report the
        # real size instead of silence — still the complete, non-truncated
        # answer, just an honest one.
        if cut_count == 0:
            # Reached only inside `len(output) > char_budget`, so every node
            # fits but the full nodes+edges output does not: an honest
            # over-budget notice, never a truncation.
            total_edges = sum(1 for l in lines if l.startswith("EDGE "))
            est_tokens = len(output) // 3
            return (
                f"[i] Complete answer over budget: all {total_nodes} nodes and "
                f"{total_edges} edges shown (~{est_tokens} tokens vs the "
                f"requested ~{token_budget}-token budget). Edges are never "
                f"dropped once every node fits, so this is already the full "
                f"answer — raising --budget further will not shrink it. Narrow "
                f"with context_filter=['call'] or use get_node for a specific "
                f"symbol to reduce size instead.\n\n"
            ) + output
        # Prominent notice at the TOP so a truncated answer can never be mistaken
        # for a complete one — silence used to read as absence (#BUG2). The
        # notice + end marker sit OUTSIDE char_budget by design (two bounded
        # wrapper lines, like the existing end marker).
        output = (
            f"[!] TRUNCATED: showing {shown_nodes} of {total_nodes} nodes "
            f"(~{token_budget}-token budget). The answer may be among the "
            f"{cut_count} cut nodes — raise the token budget (CLI: --budget) or "
            f"narrow the query (e.g. context_filter=['call'], or get_node for a "
            f"specific symbol).\n\n"
            + output[:cut_at]
            + f"\n... (truncated — {cut_count} more nodes cut by ~{token_budget}-token budget."
            f" Narrow with context_filter=['call'] or use get_node for a specific symbol)"
        )
    return output


def _cut_lines_to_budget(lines: list[str], token_budget: int, narrow_hint: str) -> str:
    """Render pre-built lines under the same ~3-chars/token budget rule as
    _subgraph_to_text; over-budget output is cut at a line boundary with a count and a
    narrowing hint instead of flooding the caller's context window."""
    output = "\n".join(lines)
    char_budget = token_budget * 3
    if len(output) <= char_budget:
        return output
    cut_at = output[:char_budget].rfind("\n")
    cut_at = cut_at if cut_at > 0 else char_budget
    kept = output[:cut_at]
    shown = kept.count("\n") + 1
    cut_count = len(lines) - shown
    # Announce truncation at the TOP as well, matching _subgraph_to_text — a
    # bottom-only marker reads as silence/absence (the BUG-2 fix rationale). The
    # notice sits outside char_budget by design (one bounded wrapper line).
    return (
        f"[!] TRUNCATED: showing {shown} of {len(lines)} lines "
        f"(~{token_budget}-token budget). {narrow_hint}\n\n"
        + kept
        + f"\n... (truncated — {cut_count} more lines cut by ~{token_budget}-token budget. "
        + narrow_hint
        + ")"
    )


def _display_graph_path(graph_path: str) -> str:
    """Render a graph path for the query header.

    Relative to the CWD when it sits underneath it — `graphify-out/graph.json`,
    which is the ordinary case and stays short. Absolute otherwise, because a
    graph outside the directory you are standing in is precisely the situation
    the header exists to make visible (#2789). Always POSIX separators so the
    line reads the same on either platform. Falls back to the path as given if
    it cannot be resolved; this is a display helper and must never be the reason
    a query fails.
    """
    try:
        p = Path(graph_path).resolve()
        try:
            return p.relative_to(Path.cwd().resolve()).as_posix()
        except ValueError:
            return p.as_posix()
    except (OSError, RuntimeError, ValueError):
        return str(graph_path)


def _traversal_view(G: nx.Graph) -> nx.Graph:
    """Undirected copy of `G` for BFS/DFS, with true direction kept per edge.

    `_load_graph` forces `directed: True` so renderers can recover stored arc
    order (#2309), and on a DiGraph `G.neighbors()` yields successors only. The
    query traversals rely on `neighbors()`, so a seed with no outgoing edges — a
    leaf function that is only ever called, imported and contained — expanded
    to nothing: `query_graph` over MCP answered with the seed alone while the
    CLI `query`, which loads the same file undirected, returned the callers,
    the test and the neighbouring modules. Every other MCP tool was unaffected:
    `get_neighbors` walks successors and predecessors explicitly, and
    `shortest_path` builds its own graph from `_src`/`_tgt`.

    Mirrors the CLI loader: traverse undirected, stash `_src`/`_tgt` on each
    edge so `_subgraph_to_text` still renders caller->callee regardless of the
    side the traversal reached the edge from. Markers already present on an
    edge win, for the same reason as in the CLI (#2309). An undirected input is
    returned as-is, so the CLI path is unchanged.

    Mutual arcs `u->v` and `v->u` (mutual recursion, a circular import) fold
    into one undirected edge on a plain `DiGraph` input, the later one winning
    — the same fold the CLI loader performs when `json_graph.node_link_graph`
    reads the undirected on-disk graph into an `nx.Graph`, which is what keeps
    the two surfaces' output identical. The renderer shows one edge per pair
    in any case. On a `MultiDiGraph` input the copy is a `MultiGraph` and the
    stored keys are not carried over: a key is unique per unordered pair on an
    undirected multigraph, so mutual arcs that happen to share a key would
    fold there too; letting networkx assign the keys keeps both, and nothing
    downstream reads the key.

    A fresh copy per query rather than a cached one: `_filter_graph_by_context`
    already copies per query when a filter applies, and the copy shares node
    data dicts with `G`, so only the edge dicts are duplicated.
    """
    if not G.is_directed():
        return G
    H = nx.MultiGraph() if G.is_multigraph() else nx.Graph()
    H.graph.update(G.graph)
    H.add_nodes_from(G.nodes(data=True))
    for u, v, d in G.edges(data=True):
        H.add_edge(u, v, **{**d, "_src": d.get("_src", u), "_tgt": d.get("_tgt", v)})
    return H

def _query_graph_text(
    G: nx.Graph,
    question: str,
    *,
    mode: str = "bfs",
    depth: int = 3,
    token_budget: int = 2000,
    context_filters: list[str] | None = None,
    graph_path: str | None = None,
) -> str:
    terms = _query_terms(question)
    # One graph scoring pass produces both the combined ranking (used to drive
    # the gap-based seed selection below) and the per-token singleton winners
    # (used by _pick_seeds' per-term guarantee). Previously this was T+1 passes
    # — one combined + one per query token — re-walking the whole graph each
    # time; on a 100k-node, three-term benchmark ~71% of scoring time was
    # spent in those redundant per-term passes.
    qs = _score_query(G, terms, collect_per_term_seeds=True)
    # Relational-intent verbs ("calls", "uses", ...) describe the relation the
    # question asks about, not a symbol to seed from; drop them from the
    # per-term seed GUARANTEE so an incidental verb match cannot seat a decoy
    # BFS root (#2507). They keep their place in `qs.ranked`, so a genuine
    # identifier named after a verb can still win a seat on merit via the gap
    # window — and when the query consists ONLY of intent words (bare "calls"),
    # the guarantee is left intact so such an identifier stays reachable.
    best_seed_by_term = qs.best_seed_by_term
    intent = {t for t in best_seed_by_term if t in _RELATIONAL_INTENT_TERMS}
    if intent and any(t not in _RELATIONAL_INTENT_TERMS for t in terms):
        best_seed_by_term = {
            t: nid for t, nid in best_seed_by_term.items() if t not in intent
        }
    start_nodes = _pick_seeds(qs.ranked, G=G, best_seed_by_term=best_seed_by_term)
    if not start_nodes:
        return "No matching nodes found."
    resolved_filters, filter_source = _resolve_context_filters(question, context_filters)
    traversal_graph = _filter_graph_by_context(_traversal_view(G), resolved_filters)
    nodes, edges = _dfs(traversal_graph, start_nodes, depth) if mode == "dfs" else _bfs(traversal_graph, start_nodes, depth)
    header_parts = [
        f"Traversal: {mode.upper()} depth={depth}",
        f"Start: {[G.nodes[n].get('label', n) for n in start_nodes]}",
    ]
    # Name the graph this answer came from. `graphify-out/` resolves against the
    # CWD, so running a query from a parent project while thinking about a
    # vendored subproject silently answers from the wrong corpus — the output is
    # well-formed and confidently wrong, and nothing in it said which graph was
    # opened (#2789). Shown relative when the graph is under the CWD (the normal
    # case, and short), absolute when it is not — which is exactly the case worth
    # noticing. The node count travels with it because "355 nodes" vs "3178
    # nodes" is often the first thing that looks wrong.
    if graph_path:
        header_parts.insert(0, f"Graph: {_display_graph_path(graph_path)} "
                               f"({G.number_of_nodes()} nodes)")
    if resolved_filters:
        header_parts.append(f"Context: {', '.join(resolved_filters)} ({filter_source})")
    header_parts.append(f"{len(nodes)} nodes found")
    header = " | ".join(header_parts) + "\n\n"
    # Pass the seeds so the queried symbol renders first and survives truncation
    # (#BUG2): a branch merge had silently dropped this argument, leaving the
    # seed-first ordering as dead code.
    return header + _subgraph_to_text(traversal_graph, nodes, edges, token_budget, seeds=start_nodes)


def _resolve_path_scoped_symbol(G: nx.Graph, path_part: str, symbol_part: str) -> list[str]:
    """Nodes whose source_file matches path_part and label/id matches symbol_part.

    Backs the `path::Symbol` query form (#3485): a bare path resolves to the
    FILE node (`_find_node_tiers`'s own `source_exact` tier, which prefers
    the file over its members once #2032-disambiguated), and a bare symbol
    name can be ambiguous across files -- the same-named local declaration
    guard from #3176 exists for exactly that case, and its own suggested
    retry ("the repo-relative path") pointed at a form that resolved to the
    wrong node or nothing at all, since no prior tier combined a path with
    a label. This combines both constraints in one query, so a specific
    symbol in a specific file is reachable without needing its opaque id.
    """
    path_tokens = " ".join(_search_tokens(path_part))
    norm_path_query = _strip_diacritics(path_part).lower().strip()
    symbol_term = " ".join(_search_tokens(symbol_part))
    norm_symbol_query = _strip_diacritics(symbol_part).lower().strip()
    if not (path_tokens or norm_path_query) or not (symbol_term or norm_symbol_query):
        return []
    candidate_ids = _trigram_candidates(G, [symbol_term, norm_symbol_query])
    node_iter = (
        G.nodes(data=True) if candidate_ids is None
        else ((nid, G.nodes[nid]) for nid in candidate_ids)
    )
    matches: list[str] = []
    for nid, d in node_iter:
        source_file = d.get("source_file") or ""
        source_tokens = " ".join(_search_tokens(source_file))
        norm_source = _strip_diacritics(source_file).lower().strip()
        if not (
            source_tokens == path_tokens
            or norm_source == norm_path_query
            or (norm_path_query and norm_source.endswith("/" + norm_path_query))
            or (path_tokens and source_tokens.endswith(" " + path_tokens))
        ):
            continue
        norm_label = d.get("norm_label") or _strip_diacritics(d.get("label") or "").lower()
        bare_label = norm_label.rstrip("()")
        label_tokens = " ".join(_search_tokens(d.get("label") or ""))
        nid_lower = nid.lower()
        if (
            symbol_term == norm_label or symbol_term == bare_label
            or symbol_term == label_tokens or symbol_term == nid_lower
            or norm_symbol_query == norm_label or norm_symbol_query == bare_label
        ):
            matches.append(nid)
    return matches


def _label_has_literal_exact_match(G: nx.Graph, term: str, norm_query: str) -> bool:
    """Does the RAW, unsplit query already exact-match some node's own label/id?

    Mirrors the `exact` tier's own condition below, run early and standalone so
    `_find_node_tiers` can tell a literal `::`-bearing label (Rust modules, C++
    namespaces) from a deliberately path-scoped query before choosing between
    them. A real label essentially never equals a whole `path::symbol` string
    verbatim, so this is a safe way to prefer the literal interpretation
    whenever one genuinely exists.
    """
    candidate_ids = _trigram_candidates(G, [term, norm_query])
    node_iter = (
        G.nodes(data=True) if candidate_ids is None
        else ((nid, G.nodes[nid]) for nid in candidate_ids)
    )
    for nid, d in node_iter:
        norm_label = d.get("norm_label") or _strip_diacritics(d.get("label") or "").lower()
        bare_label = norm_label.rstrip("()")
        label_tokens = " ".join(_search_tokens(d.get("label") or ""))
        nid_lower = nid.lower()
        nid_norm = nid_lower if nid.isascii() else _strip_diacritics(nid).lower()
        if (
            term == norm_label or term == bare_label or term == label_tokens or term == nid_lower
            or norm_query == norm_label or norm_query == bare_label or norm_query == nid_norm
        ):
            return True
    return False


def _find_node_tiers(
    G: nx.Graph, label: str
) -> tuple[list[str], list[str], list[str], list[str]]:
    """Return match tiers in precedence order: (source_exact, exact, prefix, substring).

    Split out of `_find_node` so callers that must not guess between equally-good
    matches can inspect the winning tier alone. `_find_node` flattens these, and
    its consumers take `[0]` — which resolves by graph-iteration order when one
    tier holds several nodes from different files. See `find_node_ambiguity`.
    """
    term = " ".join(_search_tokens(label))
    # Punctuation-preserving normalized query. `term` tokenizes on \w+ (so
    # "blockStream.ts" -> "blockstream ts", space where the '.' was), but a node's
    # stored `norm_label` keeps punctuation ("blockstream.ts"). Matching only via
    # `term`/`label_tokens` works when the node label tokenizes the same way, but is
    # fragile if `label` and `norm_label` diverge. `norm_query` matches `norm_label`
    # symmetrically so an exactly-typed punctuated label always resolves (#1704).
    # `nid_norm` below extends that symmetry to node ids, which keep their
    # punctuation too and are compared raw against the tokenized `term` (#2467).
    norm_query = _strip_diacritics(str(label)).lower().strip()

    # `path::Symbol` restricts the label match to nodes defined in that
    # file (#3485) -- checked before the ordinary tiers below so a
    # deliberately path-scoped query never falls back to guessing among
    # same-named symbols in other files. Returned as source_exact (the
    # tier `find_node_ambiguity` already treats as maximally specific) so
    # existing callers need no changes; an empty result falls through to
    # ordinary matching rather than reporting no match outright, in case
    # "::" is meaningful some other way to a caller this was not designed
    # for. Skipped when the raw label already literally matches a node (a
    # native `::`-bearing label, e.g. Rust modules or C++ namespaces) so that
    # an unrelated file whose path happens to resemble the label's prefix
    # cannot hijack a query that was never meant to be path-scoped.
    if "::" in label and not _label_has_literal_exact_match(G, term, norm_query):
        path_part, _, symbol_part = label.partition("::")
        path_part, symbol_part = path_part.strip(), symbol_part.strip()
        if path_part and symbol_part:
            scoped = _resolve_path_scoped_symbol(G, path_part, symbol_part)
            if scoped:
                return scoped, [], [], []

    if not term:
        return [], [], [], []
    source_exact: list[str] = []
    exact: list[str] = []
    prefix: list[str] = []
    substring: list[str] = []
    # Trigram prefilter (graph-iteration order preserved so exact/prefix/substring
    # ordering — and thus matches[0] — is byte-identical to the full scan).
    candidate_ids = _trigram_candidates(G, [term, norm_query])
    node_iter = (
        G.nodes(data=True) if candidate_ids is None
        else ((nid, G.nodes[nid]) for nid in candidate_ids)
    )
    for nid, d in node_iter:
        norm_label = d.get("norm_label") or _strip_diacritics(d.get("label") or "").lower()
        bare_label = norm_label.rstrip("()")
        label_tokens = " ".join(_search_tokens(d.get("label") or ""))
        source_tokens = " ".join(_search_tokens(d.get("source_file") or ""))
        nid_lower = nid.lower()
        # `_strip_diacritics` is the identity on ASCII, so the NFKD fold is only
        # paid for ids that actually carry non-ASCII text.
        nid_norm = nid_lower if nid.isascii() else _strip_diacritics(nid).lower()
        if term == source_tokens:
            source_exact.append(nid)
        elif (
            term == norm_label or term == bare_label or term == label_tokens or term == nid_lower
            or norm_query == norm_label or norm_query == bare_label or norm_query == nid_norm
        ):
            exact.append(nid)
        elif (
            norm_label.startswith(term)
            or bare_label.startswith(term)
            or label_tokens.startswith(term)
            or nid_lower.startswith(term)
            or norm_label.startswith(norm_query)
            or bare_label.startswith(norm_query)
        ):
            prefix.append(nid)
        elif term in norm_label or term in label_tokens or norm_query in norm_label:
            substring.append(nid)

    if source_exact:
        query_basename = _strip_diacritics(Path(label).name).lower()
        preferred = []
        for nid in source_exact:
            if str(G.nodes[nid].get("source_location", "")) != "L1":
                continue
            # File-node label is the bare basename OR a directory-qualified form
            # from the #2032 disambiguation pass (e.g. "process-order/index.ts").
            lbl = _strip_diacritics(str(G.nodes[nid].get("label") or "")).lower()
            if lbl == query_basename or lbl.endswith("/" + query_basename):
                preferred.append(nid)
        if len(preferred) == 1:
            source_exact = preferred + [nid for nid in source_exact if nid != preferred[0]]

    return source_exact, exact, prefix, substring


def _find_node(G: nx.Graph, label: str) -> list[str]:
    """Return node IDs whose label or ID matches the search term (diacritic-insensitive).

    Results are ordered by precedence: exact source-file path match first, then
    exact (label/ID) match, then prefix match, then substring match. Node-ID exact
    matches are grouped with label exact matches.
    """
    source_exact, exact, prefix, substring = _find_node_tiers(G, label)
    return source_exact + exact + prefix + substring


def find_node_ambiguity(G: nx.Graph, label: str) -> list[str]:
    """Return rival candidates when the winning match tier spans several source files.

    `_find_node` ranks matches but never reports that a tie was broken, so callers
    taking `[0]` present one arbitrary file as the answer. Two workspaces that each
    define `MetricsPort` put both nodes in the same `exact` tier, separated only by
    `G.nodes()` iteration order — reorder the graph and the same query answers with
    a different file, equally confidently.

    Returns one representative node id per distinct source file when the winning
    tier is split that way, else `[]`. Several matches *within one file* (a file
    node plus its members) are ordinary precedence, not ambiguity, and return `[]`.

    `_disambiguate_file_node_labels` (#2032) already relabels colliding *file*
    nodes; this covers the symbol case it does not reach.
    """
    for tier in _find_node_tiers(G, label):
        if not tier:
            continue
        by_source: dict[str, str] = {}
        for nid in tier:
            source = str(G.nodes[nid].get("source_file") or "")
            by_source.setdefault(source, nid)
        return list(by_source.values()) if len(by_source) > 1 else []
    return []


def _resolve_single_node(G: nx.Graph, label: str) -> tuple[str | None, str | None]:
    """Shared node resolution for the get_node / get_neighbors tools.

    Returns ``(node_id, None)`` when *label* resolves to a single winner via the
    tiered `_find_node` ranking, or ``(None, message)`` when there is no match or
    the winning tier spans several source files. Routing both tools through this
    keeps get_node from silently returning a `G.nodes()` iteration-order match for
    a hub name while get_neighbors reports the same lookup as ambiguous (#ADR-0001).
    """
    matches = _find_node(G, label)
    if not matches:
        return None, f"No node matching '{label}' found."
    rivals = find_node_ambiguity(G, label)
    if rivals:
        listing = "\n".join(
            f"  {G.nodes[r].get('source_file') or r}\n    id: {r}" for r in rivals
        )
        return None, (
            f"Ambiguous: '{label}' matches {len(rivals)} nodes in different files.\n"
            f"{listing}\n"
            f"Retry with path::symbol using one of the paths above (e.g. "
            f"<path>::{label}) or the full node id."
        )
    return matches[0], None


def _shortest_path_text(G: nx.Graph, arguments: dict) -> str:
    """Body of the `shortest_path` MCP tool (module-level so tests can call it
    without an mcp install).

    Directed by default (#2487): the returned path must follow stored
    caller→callee direction; pass ``undirected=True`` to ignore it.
    """
    src_scored = _score_nodes(G, [t.lower() for t in arguments["source"].split()])
    tgt_scored = _score_nodes(G, [t.lower() for t in arguments["target"].split()])
    if not src_scored:
        return f"No node matching source '{arguments['source']}' found."
    if not tgt_scored:
        return f"No node matching target '{arguments['target']}' found."
    src_nid = _pick_scored_endpoint(G, src_scored, arguments["source"])
    tgt_nid = _pick_scored_endpoint(G, tgt_scored, arguments["target"])
    # Ambiguity guard: when both queries resolve to the same node, the
    # shortest path is trivially zero hops, which is almost never what the
    # caller wanted (see bug #828).
    if src_nid == tgt_nid:
        return (
            f"'{arguments['source']}' and '{arguments['target']}' both resolved to "
            f"the same node '{src_nid}'. Use a more specific label or the exact node ID."
        )
    warnings: list[str] = []
    for name, scored, nid in (
        ("source", src_scored, src_nid),
        ("target", tgt_scored, tgt_nid),
    ):
        # Only meaningful when the raw score head is what got picked — a
        # full-token override was chosen on token coverage, not score.
        if len(scored) >= 2 and nid == scored[0][1]:
            top, runner = scored[0][0], scored[1][0]
            if top > 0 and (top - runner) / top < 0.10:
                warnings.append(
                    f"warning: {name} match was ambiguous "
                    f"(top score {top:g}, runner-up {runner:g})"
                )
    max_hops = int(arguments.get("max_hops", 8))
    undirected = bool(arguments.get("undirected", False))
    try:
        # Deterministic path (#2074): the hash-seeded undirected view picked an
        # arbitrary route among equal-length paths. Build a sorted, materialized
        # graph so the chosen path is canonical. Serve's shared G is left
        # untouched (its degree feeds query-seed tie-breaks).
        if undirected:
            _und = nx.Graph()
            _und.add_nodes_from(sorted(G.nodes))
            _und.add_edges_from(sorted((min(u, v), max(u, v)) for u, v in G.edges()))
            path_nodes = nx.shortest_path(_und, src_nid, tgt_nid)
        else:
            # Directed by default (#2487). True direction is NOT raw arc
            # order: legacy canonicalized files persist a flipped arc with
            # _src/_tgt markers (#2309), so build the digraph from _src/_tgt
            # (falling back to the loaded arc) rather than to_directed().
            _dg = nx.DiGraph()
            _dg.add_nodes_from(sorted(G.nodes))
            _dg.add_edges_from(sorted(
                (d.get("_src", u), d.get("_tgt", v)) for u, v, d in G.edges(data=True)
            ))
            path_nodes = nx.shortest_path(_dg, src_nid, tgt_nid)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        src_label = G.nodes[src_nid].get("label", src_nid)
        tgt_label = G.nodes[tgt_nid].get("label", tgt_nid)
        if undirected:
            return f"No path found between '{src_label}' and '{tgt_label}'."
        return (
            f"No directed path found between '{src_label}' and '{tgt_label}'. "
            "Retry with undirected=true to search ignoring edge direction."
        )
    hops = len(path_nodes) - 1
    if hops > max_hops:
        return f"Path exceeds max_hops={max_hops} ({hops} hops found)."
    segments = []
    for i in range(len(path_nodes) - 1):
        u, v = path_nodes[i], path_nodes[i + 1]
        # Report the actual stored relation(s), never a fabricated `calls`;
        # fall back to an honest "related" when the edge has no relation (#2074).
        # Direction truth lives in the per-link _src/_tgt markers (#2309): a
        # legacy canonicalized file can persist a flipped arc, so classify each
        # hop by _src (falling back to the arc tail) instead of raw arc order.
        fwd, bwd = [], []
        for a, b in ((u, v), (v, u)):
            if G.has_edge(a, b):
                for d in edge_datas(G, a, b):
                    (fwd if d.get("_src", a) == u else bwd).append(d)
        datas = fwd or bwd
        forward = bool(fwd)
        rels = sorted({d.get("relation") for d in datas if d.get("relation")})
        rel = "/".join(rels) if rels else "related"
        confs = sorted({d.get("confidence") for d in datas if d.get("confidence")})
        conf_str = f" [{'/'.join(confs)}]" if confs else ""
        if i == 0:
            segments.append(G.nodes[u].get("label", u))
        if forward:
            segments.append(f"--{rel}{conf_str}--> {G.nodes[v].get('label', v)}")
        else:
            segments.append(f"<--{rel}{conf_str}-- {G.nodes[v].get('label', v)}")
    prefix = ("\n".join(warnings) + "\n") if warnings else ""
    return prefix + f"Shortest path ({hops} hops):\n  " + " ".join(segments)


def _community_header(cid: int, community_name) -> str:
    # Header for get_community: "Community N — Name", matching get_node / query
    # output which read the community_name attribute to_json writes onto nodes.
    # Skip the name when it is just the "Community N" placeholder (written for
    # unnamed communities) so the header never reads "Community 12 — Community 12";
    # also falls back to the bare id when there is no name. Name is sanitised
    # (F-010) like every other LLM-derived field.
    base = f"Community {cid}"
    if community_name:
        clean = sanitize_label(str(community_name))
        if clean and clean != base:
            return f"{base} — {clean}"
    return base
