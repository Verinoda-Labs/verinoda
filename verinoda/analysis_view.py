"""What a model reads of an analysis: the answer and its evidence, not the run (docs/DESIGN.md D20).

:func:`analysis.analyze` returns the full record (plan check, per-sub-question plumbing, steps, usage,
every claim with every field); ``verinoda analyze --json`` prints it. A model answering the user
needs less, and every token of plumbing is a token not spent on evidence. Three views of the same
result:

* :func:`render_text` - the default output of ``verinoda analyze``: the snapshot, how the question
  was understood, one block per sub-question (verdict, answer claims, unknowns), the other claims,
  and the passages ``verinoda query`` gives for the question, as plain text;
* :func:`lead_view` - the MCP ``analyze`` response (docs/DESIGN.md D186): the verdict, the answer
  claims whole, at most eight leads (``path:a-b  symbol  (why)``: what to read next, not claims; the
  answers' files first and always, whatever their path), the unknowns, at most six context claims as
  one line each and one line of coverage, under a budget of 2,500 characters that this builder keeps
  itself (context lines go first, then leads beyond the answers' files, then an unknown's commit list
  from the middle; answer claims, clarifications and errors never); passages, plan links, critique,
  steps and usage are not sent (``project_query`` gives the passages, ``claim_inspect`` the rest).
  ``show="lead"`` adds the first lead's numbered source lines (at most 60) inside 4,500 characters;
* :func:`lean` - the whole result as compact JSON (what the MCP response was before D186: every
  claim, the plan check, the passages).

Rules of the text and the lean view (nothing an answer rests on is dropped; the full record stays one
``--json`` away):

* claims keep id, status and text; confidence only where it differs from the status's cap
  (``claims.CONFIDENCE_CAP``), evidence only where it adds a locator the text does not carry
  (a ``supports`` locator the text quotes, or a graph edge restating a relation the text states
  with its call site, is left out), uncertainties and "not challenged" reasons always;
* a verified context claim (not an answer claim) whose cited lines all lie in a window the
  passages print is left out and counted: the passage shows those lines;
* the plan's links stay (where the question's words resolved in the code: a locator), weak ones go;
* dropped: steps, usage (unless a budget ran out), the question echo, plan id/source, per
  sub-question done_when / links_used / retrieval / handler / claim_ids, weak plan links.
"""

from __future__ import annotations

import json
import re
from typing import Callable

from verinoda import textnorm as tn
from verinoda.claims import CONFIDENCE_CAP

# verified statuses whose cited lines are the whole support: a printed passage shows the same
LINE_VERIFIED = ("statically_verified", "primary_source_verified")
# A sub-question's text as the views repeat it (its heading; an unknown's question is clipped to the same
# length where it is made): one line, at most this long. A long message pasted as the question is not
# printed again before the evidence; ``--json`` keeps every text whole (docs/DESIGN.md D67).
ECHO_CHARS = 160
_LOC_RX = re.compile(r"([A-Za-z0-9_.][\w.\-/]*\.[A-Za-z0-9_]+:\d+(?:-\d+)?)")
_HEAD_RX = re.compile(r"^## (\S+):(\d+)-(\d+)(?: |$)")
_SUB_RX = re.compile(r"^  (\S+):(\d+)-(\d+)$")
_ITEM_LINE_RX = re.compile(r"^\S+:\d+-\d+ ")
_META = ("  doc: ", "  names: ", "  named by: ", "  same content: ", "  calls: ", "  called by: ", "  const ",
         "  mixin: ", "  runs: ", "  backlog: ")
_NOT_BODY = ("## ", "… ", "(calls / called by", "not indexed, and", "next: ", "expanded: ",
             "changed since indexing", "no candidate locations")


def _evidence(c: dict) -> list[str]:
    """Evidence strings that add something to the claim's text (see the module rules)."""
    text = c.get("text") or ""
    out = []
    for e in c.get("evidence") or []:
        role, _, rest = e.partition(":")
        kind, _, where = rest.partition(":")
        if role == "supports":
            if kind == "graph_edge" and _LOC_RX.search(text):
                continue  # the relation and its call site are the text itself
            m = _LOC_RX.search(where)
            if m and m.group(1) in _LOC_RX.findall(text):  # the same locator, not one it is a prefix of
                continue
            out.append(f"{kind}:{where}")
        else:
            out.append(e)
    return out


def _confidence(c: dict) -> float | None:
    conf = c.get("confidence")
    if conf is None or CONFIDENCE_CAP.get(c.get("status")) == conf:
        return None
    return conf


def lean_claim(c: dict) -> dict:
    """A claim as the lean views carry it."""
    out = {"id": c["id"], "status": c["status"], "text": c["text"]}
    conf = _confidence(c)
    if conf is not None:
        out["confidence"] = conf
    ev = _evidence(c)
    if ev:
        out["evidence"] = ev
    if c.get("uncertainties"):
        out["uncertainties"] = c["uncertainties"]
    if c.get("challenged") is False:
        out["not_challenged"] = c.get("not_challenged_reason") or "yes"
    return out


def printed_windows(passages: list[str]) -> list[tuple[str, int, int]]:
    """Line ranges whose source lines the passages print (``retrieval.render_text`` layout).

    A ``  path:x-y`` sub-window counts (its lines follow it in one block); an item's ``## path:a-b``
    header counts only when its body follows directly (after its doc/calls/... lines). A window
    covers only the lines that follow it: passages cut short (the MCP response cap keeps a prefix)
    print a window's first lines, and only those count."""
    out = []
    for i, ln in enumerate(passages):
        m = _SUB_RX.match(ln)
        j = i + 1
        if not m:
            m = _HEAD_RX.match(ln)
            if not m:
                continue
            while j < len(passages) and passages[j].startswith(_META):
                j += 1
            if j < len(passages) and (_SUB_RX.match(passages[j]) or _ITEM_LINE_RX.match(passages[j])):
                continue  # a sub-window or the next item follows: the header prints no body
        path, lo, hi = m.group(1), int(m.group(2)), int(m.group(3))
        n = 0
        while j + n < len(passages) and n < hi - lo + 1 and not _block_start(passages[j + n]):
            n += 1
        if n:
            out.append((path, lo, lo + n - 1))
    return out


def _block_start(ln: str) -> bool:
    """Does ``ln`` start a new block of the text (not a source line of the window above it)?"""
    return bool(ln.startswith(_NOT_BODY) or _SUB_RX.match(ln) or _ITEM_LINE_RX.match(ln))


def _covered(loc: str, wins: list[tuple[str, int, int]]) -> bool:
    path, _, rng = loc.rpartition(":")
    a, _, b = rng.partition("-")
    lo, hi = int(a), int(b or a)
    return any(p == path and x <= lo and hi <= y for p, x, y in wins)


def answer_ids(res: dict) -> list[str]:
    return list(dict.fromkeys(cid for s in res.get("subquestions") or [] for cid in s.get("answer_claim_ids") or []))


def shown_by_passages(res: dict) -> set[str]:
    """Ids of verified context claims whose cited lines all lie in windows the passages print."""
    wins = printed_windows(res.get("passages") or [])
    if not wins:
        return set()
    answering = set(answer_ids(res))
    out = set()
    for c in res.get("claims") or []:
        if c["id"] in answering or c.get("status") not in LINE_VERIFIED:
            continue
        locs = _LOC_RX.findall(c.get("text") or "")
        if not locs:
            locs = [x for e in c.get("evidence") or [] for x in _LOC_RX.findall(e.split(":", 2)[-1])]
        if locs and all(_covered(loc, wins) for loc in locs):
            out.add(c["id"])
    return out


# -- MCP: lean JSON ------------------------------------------------------------------------------

def _link(lk: dict, *, untagged: str | None = None) -> str | None:
    """One plan link as a line (None for a weak one); a link whose status is ``untagged`` goes without it."""
    st = lk.get("status")
    if st == "weak":
        return None
    if st == "not_found":
        dym = lk.get("did_you_mean") or []
        return f"{lk.get('text')}: not_found" + (f" (did you mean {', '.join(map(str, dym[:3]))})" if dym else "")
    tag = "" if st == untagged else f" ({st})"
    if lk.get("at"):
        return f"{lk.get('text')} -> {lk['at']}{tag}"
    return f"{lk.get('text')}{tag}"


def lean_plan_check(pc: dict) -> dict:
    out: dict = {"status": pc.get("status")}
    for k in ("errors", "warnings", "clarifications", "references", "intent_divergence"):
        if pc.get(k):
            out[k] = pc[k]
    links = [x for x in (_link(lk) for lk in pc.get("links") or []) if x]
    if links:
        out["links"] = links
    return out


SUB_KEYS = ("id", "intent", "text", "status", "answer_claim_ids", "flags", "proposition", "references",
            "decision_brief")


def lean(res: dict, *, shown_by: list[str] | None = None) -> dict:
    """The whole result as compact JSON (see the module rules); ``unknowns`` carry their ``sub_question``.

    ``shown_by``: the passage lines that leave claims out as printed (default: all of them)."""
    out: dict = {k: res[k] for k in ("analysis_id", "status", "understood_as") if res.get(k) is not None}
    snap = res.get("snapshot")
    if snap:
        out["snapshot"] = {"id": snap.get("id"), "commit": snap.get("commit"), **({"dirty": True} if snap.get("dirty")
                                                                                   else {})}
    # a stale answer is never silent, nor one given without the plan drafted for it
    for k in ("errors", "clarifications", "plan_fallback", "intent_check", "index_refresh_error", "index_refresh"):
        if res.get(k):
            out[k] = res[k]
    if res.get("plan_check"):
        out["plan_check"] = lean_plan_check(res["plan_check"])
    if res.get("plan_source") == "host":
        out["plan_id"] = res.get("plan_id")
    out["subquestions"] = [{k: (tn.clip(s[k], ECHO_CHARS) if k == "text" else s[k]) for k in SUB_KEYS if s.get(k)}
                           for s in res.get("subquestions") or []]
    hidden = shown_by_passages(res if shown_by is None else {**res, "passages": shown_by})
    out["claims"] = [lean_claim(c) for c in res.get("claims") or [] if c["id"] not in hidden]
    if hidden:
        out["claims_in_passages"] = len(hidden)
    for k in ("unknowns", "critique"):
        if res.get(k):
            out[k] = res[k]
    exhausted = (res.get("usage") or {}).get("exhausted")
    if exhausted:
        out["budget_exhausted"] = exhausted
    for k in ("facts", "facts_error"):
        if res.get(k):
            out[k] = res[k]
    if res.get("passages"):
        out["passages"] = res["passages"]
    return out


# -- MCP: leads, not an investigation (D186) -----------------------------------------------------

LEAD_BUDGET = 2500        # compact-JSON characters of the MCP analyze response (about 1,000 tokens)
LEAD_LINES_BUDGET = 4500  # the same with show="lead": the first lead's source lines on top
LEADS = 8                 # locations named as what to read next
CONTEXT_LINES = 6         # context claims carried as one line each (claim_inspect gives the rest)
LEAD_LINES = 60           # source lines show="lead" adds for the first lead
QUOTED_COMMITS = 3        # an unknown's commit list keeps this many at each end when the budget cuts it
_WHY_RANK = {"answer": 0, "claim": 1, "linked": 2, "passage": 3}
# Paths a reader opens last for a how or why question: tests after the other noise (examples, docs, vendored
# and generated code); an answer's own file is never noise (a decision record, the test a question asks about).
# The gold file of the SWE-bench analyze outputs was at rank 1 in 31 of 100 in the order the model read, 60 of
# 100 with the answers' files first and these paths last, and the same 60 with an answer's file first whatever
# its path (two of the 100 answers cite one; checked offline, D186).
_NOISE_RX = re.compile(r"(^|/)(tests?|testing|examples?|galleries|docs?|benchmarks?|vendor|vendored|third_party|"
                       r"site-packages|_build|build|dist|scripts?|tutorials?)(/|$)"
                       r"|(^|/)(test_[^/]*|[^/]*_tests?\.py|conftest\.py)$")
_TEST_RX = re.compile(r"(^|/)(tests?|testing)(/|$)|(^|/)(test_[^/]*|[^/]*_tests?\.py|conftest\.py)$")
_NAME_RX = re.compile(r"`([^`\s]+)`")
# a why or when claim: the lines in its text, the path in its evidence ("commit <sha> <path>")
_HISTORY_RX = re.compile(r"^`([^`]+)` lines (\d+)-(\d+) were changed in ")
_COMMIT_PATH_RX = re.compile(r"^commit [0-9a-f]{7,40} (\S+)$")
_PASSAGE_RX = re.compile(r"^(?:## )?(\S+?):(\d+)-(\d+)(?: (.*))?$")
_SYMBOL_RX = re.compile(r"^[\w.$]+$")
_NOT_A_SYMBOL = {"def", "class", "async", "function", "fn", "func", "public", "private", "protected", "static",
                 "final", "const", "let", "var", "export", "interface", "struct", "enum", "type", "abstract",
                 "module", "package", "trait", "impl"}


def _loc(text: str) -> dict | None:
    """``path:a-b`` or ``path:a`` as a site; None for anything else."""
    path, _, rng = text.rpartition(":")
    a, _, b = rng.partition("-")
    if not path or not a.isdigit() or (b and not b.isdigit()):
        return None
    return {"path": path, "start": int(a), "end": int(b or a)}


def _bare(name: str | None) -> str:
    """A symbol as a lead names it: ``place_order()`` -> ``place_order``, ``.save()`` -> ``save``."""
    return str(name or "").strip().strip(".").removesuffix("()")


def _symbol_of(rest: str | None) -> str:
    """The symbol a passage header or item line names after its locator (``def save(self)`` -> ``save``)."""
    for tok in (rest or "").split():
        if tok in _NOT_A_SYMBOL:
            continue
        name = re.split(r"[(:=<\[{]", tok, 1)[0]
        return name if _SYMBOL_RX.match(name) else ""
    return ""


def _claim_sites(c: dict, why: str) -> list[dict]:
    """The locations a claim cites: the ``path:a-b`` locators of its text, then of its supporting evidence."""
    text = c.get("text") or ""
    m = _NAME_RX.search(text)
    symbol = _bare(m.group(1)) if m else ""
    out = [dict(loc, symbol=symbol, why=why) for loc in map(_loc, _LOC_RX.findall(text)) if loc]
    hist = _HISTORY_RX.match(text)
    for e in c.get("evidence") or []:
        role, _, rest = e.partition(":")
        kind, _, where = rest.partition(":")
        if role != "supports":
            continue
        out += [dict(loc, symbol=symbol, why=why) for loc in map(_loc, _LOC_RX.findall(where)) if loc]
        cm = _COMMIT_PATH_RX.match(where) if kind == "git_history" else None
        if cm and hist:
            out.append({"path": cm.group(1), "start": int(hist.group(2)), "end": int(hist.group(3)),
                        "symbol": _bare(hist.group(1)), "why": why})
        elif cm:
            out.append({"path": cm.group(1), "start": None, "end": None, "symbol": symbol, "why": why})
    return out


def _sites(res: dict) -> list[dict]:
    """Every location the result cites, in the order a reader should open them: the answer claims', the other
    claims', the plan's linked mentions', the passages' (headers and item lines; a sub-window belongs to its
    header)."""
    claims = res.get("claims") or []
    answering = answer_ids(res)
    by_id = {c["id"]: c for c in claims}
    out = [s for cid in answering if cid in by_id for s in _claim_sites(by_id[cid], "answer")]
    out += [s for c in claims if c["id"] not in answering for s in _claim_sites(c, "claim")]
    for lk in (res.get("plan_check") or {}).get("links") or []:
        loc = _loc(lk.get("at") or "") if lk.get("status") in ("linked", "ambiguous") else None
        if loc:
            out.append(dict(loc, symbol=_bare(lk.get("label") or lk.get("text")), why="linked"))
    for ln in res.get("passages") or []:
        m = _PASSAGE_RX.match(ln)
        if m:
            out.append({"path": m.group(1), "start": int(m.group(2)), "end": int(m.group(3)),
                        "symbol": _symbol_of(m.group(4)), "why": "passage"})
    return out


def _tier(path: str) -> int:
    return 2 if _TEST_RX.search(path) else 1 if _NOISE_RX.search(path) else 0


def _ranked(sites: list[dict]) -> list[dict]:
    """One lead per file: the first site seen gives the file its place (the answers' files first, whatever their
    path; among them as among the rest, source paths before test, example, doc, generated and vendored paths,
    tests last of all; then the group, then first seen) and the lines shown; ``spans`` keeps every range the
    file's own group cites and ``other_spans`` the other groups' (``show="lead"`` reads the narrowest of the
    first, else of the second)."""
    leads: dict[str, dict] = {}
    for i, s in enumerate(sites):
        lead = leads.get(s["path"])
        if lead is None:
            lead = leads[s["path"]] = {**s, "spans": [], "other_spans": [],
                                       "rank": (s["why"] != "answer", _tier(s["path"]), _WHY_RANK[s["why"]], i)}
        if s["start"] is not None:
            if lead["start"] is None:
                lead["start"], lead["end"] = s["start"], s["end"]
            lead["spans" if s["why"] == lead["why"] else "other_spans"].append((s["start"], s["end"]))
        if not lead["symbol"] and s["symbol"]:
            lead["symbol"] = s["symbol"]
    return sorted(leads.values(), key=lambda x: x["rank"])


def _lead_line(x: dict) -> str:
    where = x["path"] if x["start"] is None else (f"{x['path']}:{x['start']}" if x["start"] == x["end"]
                                                   else f"{x['path']}:{x['start']}-{x['end']}")
    return where + (f"  {x['symbol']}" if x["symbol"] else "") + f"  ({x['why']})"


def _top(ranked: list[dict], limit: int) -> list[dict]:
    """The first ``limit`` leads, and every answer's file whatever their count: the cap takes the other files,
    never one the answer rests on (as the answer claims are never cut), so more answer files than ``limit``
    make a longer list, not a shorter answer."""
    return ranked[:max(limit, sum(x["why"] == "answer" for x in ranked))]


def leads_for(res: dict, limit: int = LEADS) -> list[str]:
    """At most ``limit`` leads (every answer's file always), ``path:a-b  symbol  (answer|claim|linked|passage)``:
    the files of the answer claims first, then the other claims', the plan's linked mentions', the passages';
    test, example, doc, generated and vendored paths after source paths (see :func:`_ranked`)."""
    return [_lead_line(x) for x in _top(_ranked(_sites(res)), limit)]


def _query_names(res: dict) -> str:
    """What to give ``project_query`` for the passages: the words the plan linked, else the answers' names."""
    names = [str(lk.get("text")) for lk in (res.get("plan_check") or {}).get("links") or []
             if lk.get("status") in ("linked", "ambiguous") and lk.get("text")]
    if not names:
        by_id = {c["id"]: c for c in res.get("claims") or []}
        names = [_bare(n) for cid in answer_ids(res) if cid in by_id for n in _NAME_RX.findall(by_id[cid]["text"])]
    return " ".join(list(dict.fromkeys(n for n in names if n))[:3])


def _refresh_line(res: dict) -> str:
    ref = res.get("index_refresh") or {}
    err = res.get("index_refresh_error") or ref.get("error")
    if err:
        return "index not refreshed: " + tn.clip(str(err), ECHO_CHARS)
    if ref.get("ran"):
        return f"re-indexed {ref.get('changed_count', 0)} changed file(s) first"
    if ref.get("skipped"):
        line = f"index predates {ref.get('stale_count', 0)} changed file(s), not refreshed: {ref['skipped']}"
        return line + (f"; background update {ref['background_update']}" if ref.get("background_update") else "")
    return "index current" if ref else ""


def _coverage(res: dict, *, hidden: int, dropped: int, notes: list[str]) -> str:
    """One line: what was searched and what the reader does not see (the snapshot, the index's state, the
    context and leads the budget cut, and the way to the passages)."""
    snap = res.get("snapshot") or {}
    parts = []
    if snap:
        parts.append(f"snapshot {snap.get('id')} (commit {(snap.get('commit') or 'no-git')[:10]}"
                     f"{', dirty' if snap.get('dirty') else ''})")
    parts.append(_refresh_line(res))
    if hidden:
        parts.append(f"+{hidden} context claim(s) not shown (claim_inspect; `verinoda analyze --json` lists all)")
    if dropped:
        parts.append(f"{dropped} lead(s) left out for the budget")
    parts += notes
    names = _query_names(res)
    parts.append(f"passages not included: `project_query {names}` returns them" if names
                 else "passages not included: project_query with the question returns them")
    return "; ".join(p for p in parts if p)


def _fold_commits(unknowns: list[dict], originals: list[dict], k: int) -> bool:
    """Shorten the commit lists the unknowns carry (the why handler's leads) to their newest and oldest ``k``
    with one line naming the count between: the first appearance is evidence as much as the last change, and a
    cut that drops it silently reads as "no such change" (D185). ``unknowns`` are copies of ``originals``, which
    stay whole. True when a list changed."""
    changed = False
    for u, orig in zip(unknowns, originals):
        for key, val in orig.items():
            if isinstance(val, list) and len(u.get(key) or ()) > 2 * k + 1 and all(isinstance(x, str) for x in val):
                between = (f"... {len(val) - 2 * k} more commit(s) between them: history_search with the symbol "
                           "lists every one, both ends kept")
                u[key] = [*val[:k], between, *val[-k:]]
                changed = True
    return changed


def lead_view(res: dict, *, budget: int = LEAD_BUDGET, show: str | None = None,
              read: Callable[[str, int, int], str | None] | None = None,
              lead_budget: int = LEAD_LINES_BUDGET) -> dict:
    """The MCP ``analyze`` response (see the module docstring): under ``budget`` compact-JSON characters, cut by
    this builder alone, so the generic response cap never marks it ``truncated``. ``show="lead"`` adds
    ``lead_lines`` (the first lead's narrowest cited span, at most ``LEAD_LINES`` lines, numbered) through
    ``read(path, start, end)`` inside ``lead_budget``."""
    if show not in (None, "lead"):
        raise ValueError(f"show must be 'lead' or None, not {show!r}")
    head: dict = {k: res[k] for k in ("status", "understood_as") if res.get(k) is not None}
    snap = res.get("snapshot")
    if snap:
        head["snapshot"] = {"id": snap.get("id"), "commit": snap.get("commit"), **({"dirty": True} if snap.get("dirty")
                                                                                   else {})}
    if res.get("analysis_id"):
        head["analysis_id"] = res["analysis_id"]   # the handle plan_audit takes
    for k in ("errors", "clarifications", "plan_fallback", "intent_check"):  # a reader must see these: never cut
        if res.get(k):
            head[k] = res[k]
    exhausted = (res.get("usage") or {}).get("exhausted")
    if exhausted:
        head["budget_exhausted"] = exhausted
    if res.get("plan_source") == "host":
        head["plan_id"] = res.get("plan_id")
    claims = res.get("claims") or []
    by_id = {c["id"]: c for c in claims}
    answering = set(answer_ids(res))
    head["subquestions"] = [{"id": s.get("id"), "intent": s.get("intent"), "status": s.get("status"),
                             "answers": [lean_claim(by_id[cid]) for cid in s.get("answer_claim_ids") or []
                                         if cid in by_id]} for s in res.get("subquestions") or []]
    leads = _top(_ranked(_sites(res)), LEADS)
    unknowns = [dict(u) for u in res.get("unknowns") or []]
    facts = list(res.get("facts") or [])
    # context the critique refuted on the way is not part of the answer (render_text leaves it out too)
    context = [c for c in claims if c["id"] not in answering and not (answering and c.get("status") == "contradicted")]
    shown = min(len(context), CONTEXT_LINES)
    dropped = 0
    notes: list[str] = []

    def assemble() -> dict:
        out = dict(head)
        if leads:
            out["leads"] = [_lead_line(x) for x in leads]
        if unknowns:
            out["unknowns"] = unknowns
        if facts:
            out["facts"] = facts
        if shown:
            out["context"] = [f"{c['id']} {c['status']} {tn.clip(c['text'], ECHO_CHARS)}" for c in context[:shown]]
        out["coverage"] = _coverage(res, hidden=len(context) - shown, dropped=dropped, notes=notes)
        return out

    def fit() -> dict:
        # context lines first, then leads beyond the answers' files, the facts beyond the first, an unknown's commit
        # list from the middle (three at each end, then one); the answer claims, clarifications and errors never
        # (above 12,000 the generic cap of the server still says what it cut)
        nonlocal shown, dropped
        while True:
            out = assemble()
            if _size(out) <= budget:
                return out
            if shown:
                shown -= 1
            elif leads and leads[-1]["why"] != "answer":  # the answers' files lead the list: never cut
                leads.pop()
                dropped += 1
            elif len(facts) > 1:
                facts.pop()
            elif not (_fold_commits(unknowns, res.get("unknowns") or [], QUOTED_COMMITS)
                      or _fold_commits(unknowns, res.get("unknowns") or [], 1)):
                return out

    out = fit()
    if show == "lead" and leads:
        first = leads[0]
        spans = sorted(first["spans"] or first["other_spans"], key=lambda ab: (ab[1] - ab[0], ab[0]))
        body = None
        if spans:
            a, b = spans[0][0], min(spans[0][1], spans[0][0] + LEAD_LINES - 1)
            body = read(first["path"], a, b) if read is not None else None
        if body is None:
            notes.append(f"lead lines: {_lead_line(first).split('  ')[0]} not read")
            out = fit()
        else:
            from verinoda.retrieval import numbered_lines

            lines = body.split("\n")
            lead_lines = {"path": first["path"], "start": a, "end": a + len(lines) - 1, "text": numbered_lines(body, a)}
            out["lead_lines"] = lead_lines
            while _size(out) > lead_budget and len(lines) > 1:
                lines.pop()
                lead_lines.update(end=a + len(lines) - 1, text=numbered_lines("\n".join(lines), a))
    return out


def _size(obj) -> int:
    """Compact-JSON characters, as the MCP response cap (``mcp.server._size``) measures them."""
    return len(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))


# -- CLI: plain text -----------------------------------------------------------------------------

CONTEXT_SHOWN = 6     # context claims printed after the answer (the rest counted; --json has them all)
CRITIQUE_CHARS = 140  # a critique line's findings, clipped (the claim's own line already says why)


def _distinct_uncertainties(items: list[str]) -> list[str]:
    """The uncertainties minus one another's repeats: critique's ``call site path:line: <reason>`` restates a reason
    the claim already gives (``... not confirmed to name the target (<reason>)``) - said once."""
    out: list[str] = []
    for u in dict.fromkeys(str(x) for x in items):
        core = re.sub(r"^call site \S+:\d+: ", "", u)
        if any(core in o for o in items if o != u) or any(core in o for o in out):
            continue
        out.append(u)
    return out


def claim_line(c: dict) -> str:
    conf = _confidence(c)
    line = f"[{c['status']}{f' {conf:.2f}' if conf is not None else ''}] {c['text']}"
    ev = _evidence(c)
    if ev:
        line += " {" + "; ".join(ev) + "}"
    if c.get("uncertainties"):
        line += " (uncertain: " + "; ".join(_distinct_uncertainties(c["uncertainties"])) + ")"
    line += f"  ({c['id']})"
    if c.get("challenged") is False:
        reason = c.get("not_challenged_reason")
        line += f"  [not challenged: {reason}]" if reason else "  [not challenged]"
    return line


def problem_lines(problems: list[dict], indent: str = "  ") -> list[str]:
    return [f"{indent}{p.get('at', '/')}: {p.get('msg')}" + (f"  fix: {p['fix']}" if p.get("fix") else "")
            for p in problems]


def clarification_lines(clar: list[dict], indent: str = "  ") -> list[str]:
    out = []
    for c in clar:
        out.append(f"{indent}{c['id']}: {c.get('question_user_lang') or c.get('question_en')}")
        for o in c.get("options") or []:
            ev = f"  [{o['evidence']}]" if o.get("evidence") else ""
            out.append(f"{indent}   - {o.get('value')}: {o.get('label')}{ev}")
    return out


def _brief(b: dict) -> list[str]:
    out = []
    for f in b.get("forces") or []:
        out.append(f"  [{f['status']}] {f['fact'][:200]}  ({', '.join(f['at'][:3])})")
    for a in b.get("absences") or []:
        out.append(f"  absent: {a['what']}")
    for q in b.get("questions_for_human") or []:
        out.append(f"  ask the user {q['id']}: {q['text']}")
    return out


def _unknown(u: dict, echo: str | None = None) -> str:
    """One unknown as a line; under a sub-question whose text it only repeats (``echo``), without the repeat."""
    q = u.get("question")
    head = "unknown: " if echo is not None and q in (echo, tn.clip(echo, ECHO_CHARS)) else f"unknown: {q}: "
    return head + f"{u.get('why')}" + (f"; next: {u['next_step']}" if u.get("next_step") else "")


def render_text(res: dict) -> str:
    """The default ``verinoda analyze`` output (see the module rules)."""
    out: list[str] = []
    snap = res.get("snapshot") or {}
    head = f"analysis {res.get('analysis_id')}"
    if snap:
        head += (f", snapshot {snap.get('id')} (commit {(snap.get('commit') or 'no-git')[:10]}"
                 f"{', dirty' if snap.get('dirty') else ''})")
    out.append(head)
    if res.get("understood_as"):
        out.append(f"understood as: {res['understood_as']}")
    fb = res.get("plan_fallback") or {}
    if fb:
        first = (fb.get("errors") or [""])[0]
        out.append(f"note: {fb.get('why') or 'answered without the drafted plan'}"
                   + (f" ({tn.clip(first, ECHO_CHARS)})" if first else ""))
    ic = res.get("intent_check") or {}
    if ic:
        read = ", ".join(ic.get("read_as") or []) or "no intent"
        out.append(f"host intent {ic.get('given')}: " + (f"used for {', '.join(ic.get('sub_questions') or [])}"
                                                         if ic.get("applied") else
                                                         f"not used: {ic.get('why') or f'the rules read {read}'}"))
    status = res.get("status")
    pc = res.get("plan_check") or {}
    if res.get("plan_source") == "host":
        out.append(f"plan {res.get('plan_id')}: {pc.get('status') or status}")
    linked: dict[tuple, list[str]] = {}  # (at, status) -> the words that resolved there
    for lk in pc.get("links") or []:
        if lk.get("status") == "not_found":
            out.append("plan check: " + _link(lk))
        elif lk.get("status") != "weak":
            linked.setdefault((lk.get("at"), lk.get("status")), []).append(str(lk.get("text")))
    if linked:  # where the question's words resolved in the code (the MCP view lists the same links)
        out.append("plan links: " + "; ".join(_link({"text": ", ".join(words), "at": at, "status": st},
                                                    untagged="linked") for (at, st), words in linked.items()))
    if res.get("index_refresh_error"):
        out.append(f"warning: {res['index_refresh_error']}")
    if status == "invalid_plan":
        out.append("the plan is invalid; nothing was analysed:")
        out += problem_lines(res.get("errors") or pc.get("errors") or [])
        out.append("  next: fix the plan file (`verinoda plan schema`, `verinoda plan check FILE`)")
    elif status == "needs_clarification":
        out.append("clarification needed before analysing (ask the user, record the choice in the plan's answers[] "
                   "with its clarification_id, then re-run):")
        out += clarification_lines(res.get("clarifications") or pc.get("clarifications") or [])
    elif status == "no_index":
        out.append("no index to analyse: run `verinoda scan` first")
    claims = {c["id"]: c for c in res.get("claims") or []}
    unknowns = list(res.get("unknowns") or [])
    printed: set[str] = set()
    for s in res.get("subquestions") or []:
        text = tn.clip(s.get("text") or "", ECHO_CHARS)
        out.append(f"{s['id']} [{s.get('status') or '?'}] {s.get('intent')}: {text}")
        b = s.get("decision_brief") or {}
        if b.get("forces") is not None:  # a choice: what the human decides with (no recommendation)
            out.append(f"  decision brief {b.get('brief_id')} [{b.get('verdict')}]: {b.get('understood_as')}")
            out += _brief(b)
        for cid in s.get("answer_claim_ids") or []:
            if cid in printed:
                out.append(f"  (also answers this: {cid})")
            elif cid in claims:
                out.append("  " + claim_line(claims[cid]))
                printed.add(cid)
        for u in [u for u in unknowns if u.get("sub_question") == s["id"]]:
            out.append("  " + _unknown(u, s.get("text") or ""))
    hidden = shown_by_passages(res)
    rest = [c for c in claims.values() if c["id"] not in printed and c["id"] not in hidden]
    # context the critique refuted on the way is not part of the answer: counted, not printed (nor its critique)
    refuted = {c["id"] for c in rest if c.get("status") == "contradicted"} if printed else set()
    rest = [c for c in rest if c["id"] not in refuted]
    if rest or hidden or refuted:
        out.append("context (found on the way; not what answers):" if printed else "claims:")
        shown = rest if not printed else rest[:CONTEXT_SHOWN]
        out += ["  " + claim_line(c) for c in shown]
        if len(rest) > len(shown):
            out.append(f"  +{len(rest) - len(shown)} more context claim(s) (--json lists them)")
        if refuted:
            out.append(f"  +{len(refuted)} context claim(s) the critique refuted (--json lists them)")
        if hidden:
            out.append(f"  +{len(hidden)} verified claim(s) about lines the passages below print (--json lists them)")
    loose = [u for u in unknowns if not u.get("sub_question")]
    if loose:
        out += [_unknown(u) for u in loose]
    for c in res.get("critique") or []:
        if c.get("claim") in refuted:
            continue
        out.append(f"critique {c['claim']}: {c['before']} -> {c['after']}  "
                   + "; ".join((c.get("fails") or []) + (c.get("warns") or []))[:CRITIQUE_CHARS])
    exhausted = (res.get("usage") or {}).get("exhausted")
    if exhausted:
        out.append(f"budget exhausted: {exhausted} (what was not reached is listed as unknown)")
    if res.get("facts"):
        from verinoda.facts import lead_lines

        out += lead_lines(res["facts"])
    if res.get("passages"):
        out.append("passages (what `verinoda query` gives for the question; search results, not claims):")
        out += res["passages"]
    return "\n".join(out)
