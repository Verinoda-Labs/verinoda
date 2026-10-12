"""What a model reads of an analysis (verinoda.analysis_view): lean claims, the text and the MCP view."""

from __future__ import annotations

import json
import re

import pytest

from verinoda import analysis_view as av
from verinoda.mcp.server import _size

PASSAGES = [
    "expanded: databas->db",
    "## orders/pricing.py:6-8 compute_total",
    "  calls: apply_discount@8",
    "def compute_total(items: list[dict]) -> float:",
    "    subtotal = sum(i['price'] * i['qty'] for i in items)",
    "    return apply_discount(subtotal)",
    "## orders/repository.py:8-26 OrderRepository",
    "  called by: get_repo (orders/api.py:12)",
    "  orders/repository.py:15-20",
    "def save(self, customer: str, total: float) -> int:",
    "    cur = self.conn.execute(",
    "        'INSERT INTO orders (customer, total) VALUES (?, ?)', (customer, total)",
    "    )",
    "    self.conn.commit()",
    "    return cur.lastrowid",
    "## orders/api.py:16-21 create_order_handler",
    "## orders/api.py:24-28 get_order_handler",
    "orders/config.py:5-7 DATABASE_URL = os.environ.get('ORDERS_DATABASE_URL', 'orders.db')",
    "… 3 more candidates not shown: a.py:1-2 x",
    "next: verinoda query \"…\" --max-chars 12000",
]


def _claim(cid: str, text: str, status: str = "statically_verified", **kw) -> dict:
    conf = {"statically_verified": 0.9, "strong_inference": 0.7, "primary_source_verified": 0.85}[status]
    return {"id": cid, "text": text, "status": status, "confidence": kw.pop("confidence", conf),
            "evidence": kw.pop("evidence", []), "uncertainties": kw.pop("uncertainties", []), **kw}


def _result(**over) -> dict:
    res = {
        "analysis_id": "ana_1", "question": "how is an order saved?", "intents": ["flow"], "plan_id": "qpl_1",
        "plan_source": "fallback", "understood_as": "Understood (rules): q1 [flow] how is an order saved?",
        "snapshot": {"id": "snp_1", "commit": "0123456789abcdef", "dirty": False}, "status": "answered",
        "plan_check": {"status": "ready", "errors": [], "warnings": [], "references": [], "clarifications": [],
                       "intent_divergence": [],
                       "links": [{"mention": "m1", "text": "order", "status": "linked", "at": "orders/service.py:19-22",
                                  "label": "place_order", "score": 1.0, "tier": "name"},
                                 {"mention": "m2", "text": "saved", "status": "weak", "at": "x.py:1-2"},
                                 {"mention": "m3", "text": "persist_order", "status": "not_found",
                                  "did_you_mean": ["place_order"]}]},
        "subquestions": [{"id": "q1", "intent": "flow", "text": "how is an order saved?",
                          "done_when": {"kind": "path_found"}, "links_used": ["m1"], "retrieval": {"items": 10},
                          "handler": "flow", "claim_ids": ["c1", "c2", "c3", "c4", "c5"], "unknowns": [],
                          "status": "met_with_inference", "answer_claim_ids": ["c1", "c2"]}],
        "claims": [
            _claim("c1", "`place_order()` calls `compute_total()` (orders/service.py:21)",
                   evidence=["supports:source_code:orders/service.py:21",
                             "supports:graph_edge:place_order -[calls]-> compute_total"]),
            _claim("c2", "`place_order()` -> `.save()` reaches the database", "strong_inference", confidence=0.6,
                   evidence=["supports:source_code:orders/service.py:22", "qualifies:graph_edge:x -[calls]-> y"],
                   uncertainties=["the receiver is not resolved"], challenged=False, not_challenged_reason="budget"),
            _claim("c3", "`compute_total()` calls `apply_discount()` (orders/pricing.py:8)"),  # printed: hidden
            _claim("c4", "`save()` is defined at orders/repository.py:15-20"),                 # printed: hidden
            _claim("c5", "`get_order_handler()` is defined at orders/api.py:24-28"),           # header only: kept
            _claim("c6", "`compute_total()` probably rounds (orders/pricing.py:7)", "strong_inference"),  # not verified
        ],
        "unknowns": [{"question": "which tests reach save?", "why": "no test reaches it", "next_step": "run the tests",
                      "sub_question": "q1"},
                     {"question": "does the index describe the tree?", "why": "refresh failed", "next_step": "scan"}],
        "critique": [], "steps": [{"step": "plan", "detail": "x", "t": 0.1}],
        "passages": PASSAGES,
        "usage": {"elapsed_s": 0.3, "tool_calls": 12, "exhausted": None},
    }
    res.update(over)
    return res


def test_lean_claim_keeps_what_the_text_does_not_say():
    c1, c2 = _result()["claims"][:2]
    assert av.lean_claim(c1) == {"id": "c1", "status": "statically_verified", "text": c1["text"]}
    assert av.lean_claim(c2) == {"id": "c2", "status": "strong_inference", "text": c2["text"], "confidence": 0.6,
                                 "evidence": ["source_code:orders/service.py:22",
                                              "qualifies:graph_edge:x -[calls]-> y"],
                                 "uncertainties": ["the receiver is not resolved"], "not_challenged": "budget"}


def test_printed_windows_counts_only_lines_the_passages_print():
    wins = av.printed_windows(PASSAGES)
    assert ("orders/pricing.py", 6, 8) in wins            # header, calls line, then the whole body
    assert ("orders/repository.py", 15, 20) in wins       # a sub-window
    assert ("orders/repository.py", 8, 26) not in wins   # its header is followed by a sub-window, not its body
    assert not any(w[0] == "orders/api.py" for w in wins)  # headers with no body (budget ran out)
    assert not any(w[0] == "orders/config.py" for w in wins)  # a one-line item prints no body


def test_evidence_is_left_out_only_when_the_text_carries_the_same_whole_locator():
    """Line 18 is not line 180 (nor 18 in 18-20): the evidence stays unless the text quotes that locator."""
    c = _claim("cx", "`save()` is called at orders/api.py:180", evidence=["supports:source_code:orders/api.py:18"])
    assert av.lean_claim(c)["evidence"] == ["source_code:orders/api.py:18"]
    assert "{source_code:orders/api.py:18}" in av.claim_line(c)
    ranged = dict(c, text="`save()` is defined at orders/api.py:18-20")
    assert av.lean_claim(ranged)["evidence"] == ["source_code:orders/api.py:18"]
    other = dict(c, text="`save()` is called at other_orders/api.py:18")
    assert av.lean_claim(other)["evidence"] == ["source_code:orders/api.py:18"]
    same = dict(c, text="`save()` is called at orders/api.py:18")
    assert "evidence" not in av.lean_claim(same) and "{" not in av.claim_line(same)


def test_passages_cut_short_print_only_the_lines_they_keep():
    """The MCP response cap keeps a prefix of the passages: a window counts only the lines that follow it."""
    cut = PASSAGES[:PASSAGES.index("    )") + 1]  # save() up to its fourth line, 15-18
    wins = av.printed_windows(cut)
    assert ("orders/repository.py", 15, 18) in wins and ("orders/repository.py", 15, 20) not in wins
    head = PASSAGES[:PASSAGES.index("    return apply_discount(subtotal)")]  # compute_total up to line 7
    assert ("orders/pricing.py", 6, 7) in av.printed_windows(head)
    assert av.printed_windows(PASSAGES[:3]) == []  # a header and its calls line: no body yet
    assert av.shown_by_passages(_result(passages=cut)) == {"c3"}  # save() 15-20 is no longer all printed


def test_verified_context_claims_the_passages_print_are_left_out_and_counted():
    res = _result()
    assert av.shown_by_passages(res) == {"c3", "c4"}
    # never an answer claim, never a claim that is not line-verified
    res["subquestions"][0]["answer_claim_ids"] = ["c1", "c3"]
    assert av.shown_by_passages(res) == {"c4"}
    assert av.shown_by_passages(_result(passages=[])) == set()


def test_text_is_the_answer_then_the_passages():
    text = av.render_text(_result())
    lines = text.splitlines()
    assert lines[0] == "analysis ana_1, snapshot snp_1 (commit 0123456789)"
    assert lines[1].startswith("understood as: Understood (rules)")
    assert "plan check: persist_order: not_found (did you mean place_order)" in text
    # where the question's words resolved (the MCP view lists the same links): a locator, weak links left out
    assert "\nplan links: order -> orders/service.py:19-22\n" in text and "x.py:1-2" not in text
    ambiguous = {"mention": "m4", "text": "total", "status": "ambiguous", "at": "orders/pricing.py:6-8"}
    same = {"mention": "m5", "text": "placed", "status": "linked", "at": "orders/service.py:19-22"}
    more = _result()
    more["plan_check"]["links"] += [ambiguous, same]
    # words that resolved to the same place share one locator
    assert ("plan links: order, placed -> orders/service.py:19-22; total -> orders/pricing.py:6-8 (ambiguous)"
            in av.render_text(more))
    q1 = text.index("\nq1 [met_with_inference] flow: how is an order saved?")
    c1 = text.index("  [statically_verified] `place_order()` calls `compute_total()` (orders/service.py:21)  (c1)\n")
    c2 = text.index("  [strong_inference 0.60] `place_order()` -> `.save()` reaches the database "
                    "{source_code:orders/service.py:22; qualifies:graph_edge:x -[calls]-> y} "
                    "(uncertain: the receiver is not resolved)  (c2)  [not challenged: budget]")
    unk = text.index("  unknown: which tests reach save?: no test reaches it; next: run the tests")
    ctx = text.index("context (found on the way; not what answers):")
    assert q1 < c1 < c2 < unk < ctx
    assert "(c5)" in text and "(c6)" in text and "(c3)" not in text and "(c4)" not in text
    assert "+2 verified claim(s) about lines the passages below print" in text
    assert "\nunknown: does the index describe the tree?: refresh failed; next: scan" in text
    assert text.index("\npassages (") > ctx and text.endswith("next: verinoda query \"…\" --max-chars 12000")
    for noise in ("steps", "usage", "tool_calls", "done_when", "links_used", "qpl_1", "0.90"):
        assert noise not in text, noise
    exhausted = av.render_text(_result(usage={"exhausted": "time budget 60.0s spent"}))
    assert "budget exhausted: time budget 60.0s spent" in exhausted


def test_text_of_a_plan_that_needs_clarification_or_is_invalid():
    clar = av.render_text(_result(status="needs_clarification", subquestions=[], claims=[], passages=[],
                                  clarifications=[{"id": "c-version", "question_en": "which version?",
                                                   "options": [{"value": "v1", "label": "the old one"}]}]))
    assert "clarification needed" in clar and "c-version: which version?" in clar and "- v1: the old one" in clar
    bad = av.render_text(_result(status="invalid_plan", subquestions=[], claims=[], passages=[],
                                 errors=[{"at": "/language", "msg": "unknown language", "fix": "use tr or en"}]))
    assert "the plan is invalid" in bad and "/language: unknown language  fix: use tr or en" in bad


def test_lean_is_the_same_content_as_json():
    res = _result(critique=[{"claim": "c2", "before": "statically_verified", "after": "strong_inference",
                             "fails": ["receiver not resolved"], "warns": []}])
    lean = av.lean(res)
    assert list(lean)[:4] == ["analysis_id", "status", "understood_as", "snapshot"]
    assert lean["snapshot"] == {"id": "snp_1", "commit": "0123456789abcdef"}
    assert lean["plan_check"] == {"status": "ready", "links": ["order -> orders/service.py:19-22 (linked)",
                                                              "persist_order: not_found (did you mean place_order)"]}
    assert lean["subquestions"] == [{"id": "q1", "intent": "flow", "text": "how is an order saved?",
                                     "status": "met_with_inference", "answer_claim_ids": ["c1", "c2"]}]
    assert [c["id"] for c in lean["claims"]] == ["c1", "c2", "c5", "c6"] and lean["claims_in_passages"] == 2
    assert lean["unknowns"] == res["unknowns"] and lean["critique"] == res["critique"]
    assert lean["passages"] == PASSAGES
    for gone in ("steps", "usage", "question", "intents", "plan_id", "plan_source", "budget_exhausted"):
        assert gone not in lean, gone
    assert av.lean(_result(usage={"exhausted": "tool-call budget 3 spent"}))["budget_exhausted"] == \
        "tool-call budget 3 spent"
    assert av.lean(_result(plan_source="host"))["plan_id"] == "qpl_1"
    assert len(json.dumps(lean)) < len(json.dumps(res))


def test_a_long_subquestion_is_not_repeated_by_its_heading_and_unknowns():
    """D67: an issue pasted as the question: the heading shows one clipped line of it, and an unknown that only
    repeats the sub-question's text is printed without the repeat."""
    long_text = "Where is an order saved?\r\n\r\n" + " ".join(f"log line {i} says the save failed." for i in range(80))
    clipped = av.tn.clip(long_text, av.ECHO_CHARS)
    res = _result(subquestions=[{**_result()["subquestions"][0], "text": long_text}],
                  unknowns=[{"question": clipped, "why": "no test reaches it", "sub_question": "q1"},
                            {"question": "which tests reach save?", "why": "none found", "sub_question": "q1"}],
                  plan_fallback={"drafted_plan_id": "qpl_0", "why": "the plan drafted for the question failed its "
                                 "own checks; answered without it", "errors": ["/references: 1.2.3 dropped"]})
    text = av.render_text(res)
    lines = text.splitlines()
    assert lines[2] == ("note: the plan drafted for the question failed its own checks; answered without it "
                        "(/references: 1.2.3 dropped)")
    assert f"q1 [met_with_inference] flow: {clipped}" in lines
    assert "  unknown: no test reaches it" in lines and "  unknown: which tests reach save?: none found" in lines
    assert text.count("log line 79") == 0 and text.count("log line 1 ") <= 1
    lean = av.lean(res)
    assert lean["subquestions"][0]["text"] == clipped and lean["plan_fallback"] == res["plan_fallback"]


# -- MCP: leads, not an investigation (D186) --------------------------------------------------------

_LEAD_RX = re.compile(r"^(\S+?)(?::(\d+)(?:-(\d+))?)?  (?:(\S+)  )?\((answer|claim|linked|passage)\)$")


def _lead(line: str) -> tuple[str, str]:
    """``(path, why)`` of one lead line ``path:a-b  symbol  (why)``."""
    m = _LEAD_RX.match(line)
    assert m, line
    return m.group(1), m.group(5)


def _two_questions() -> dict:
    """Two sub-questions, nine claims, three of them answers (c1 and c2 answer q1, c7 answers q2)."""
    res = _result()
    res["claims"] += [
        _claim("c7", "`get_repo()` calls `OrderRepository` (orders/api.py:12)"),
        _claim("c8", "`fetch_order()` calls `.get()` (orders/service.py:26)", "strong_inference"),
        _claim("c9", "`test_place_and_fetch_roundtrip()` calls `place_order()` (tests/test_service.py:9)"),
    ]
    res["subquestions"].append({"id": "q2", "intent": "callers", "text": "who builds the repository?",
                                "claim_ids": ["c7", "c8", "c9"], "status": "met", "answer_claim_ids": ["c7"]})
    return res


def test_lead_view_keeps_the_answer_claims_whole_and_the_rest_as_lines():
    res = _two_questions()
    out = av.lead_view(res)
    assert list(out)[:3] == ["status", "understood_as", "snapshot"] and out["analysis_id"] == "ana_1"
    assert out["snapshot"] == {"id": "snp_1", "commit": "0123456789abcdef"}
    by_id = {c["id"]: c for c in res["claims"]}
    assert [s["id"] for s in out["subquestions"]] == ["q1", "q2"]
    q1, q2 = out["subquestions"]
    assert set(q1) == {"id", "intent", "status", "answers"} and q1["status"] == "met_with_inference"
    assert q1["answers"] == [av.lean_claim(by_id["c1"]), av.lean_claim(by_id["c2"])]  # whole, as lean_claim keeps them
    assert q2["answers"] == [av.lean_claim(by_id["c7"])]
    assert q1["answers"][1]["evidence"] == ["source_code:orders/service.py:22", "qualifies:graph_edge:x -[calls]-> y"]
    # the other claims: one line each, `id status text`, at most six, in the result's order
    assert [ln.split(" ")[0] for ln in out["context"]] == ["c3", "c4", "c5", "c6", "c8", "c9"]
    assert out["context"][0] == "c3 statically_verified `compute_total()` calls `apply_discount()` (orders/pricing.py:8)"
    assert out["unknowns"] == res["unknowns"]
    for gone in ("passages", "plan_check", "critique", "steps", "usage", "claims", "question", "intents",
                 "claims_in_passages", "truncated", "truncation"):
        assert gone not in out, gone
    assert isinstance(out["coverage"], str) and "snp_1" in out["coverage"]
    assert "project_query" in out["coverage"] and "order" in out["coverage"]  # the way to the passages


def test_leads_order_answer_files_first_and_noise_paths_last():
    res = _result()
    res["claims"] = [
        _claim("c1", "`save()` is defined at src/a.py:10-20"),                       # answer: a source file
        _claim("c2", "`test_save()` calls `save()` (tests/test_a.py:5-6)"),         # answer: a test file
        _claim("c3", "`load()` is defined at src/b.py:1-3"),                          # context
    ]
    res["subquestions"][0]["answer_claim_ids"] = ["c1", "c2"]
    res["plan_check"]["links"] = [{"mention": "m1", "text": "saved", "status": "linked", "at": "docs/x.md:1-2",
                                   "label": "x.md"},
                                  {"mention": "m2", "text": "weak", "status": "weak", "at": "src/weak.py:1-2"}]
    res["passages"] = ["## src/c.py:7-9 helper", "7 def helper():", "8     return 1", "9 ",
                       "src/d.py:3-4 def other()", "tests/test_c.py:1-2 def test_c()"]
    leads = av.leads_for(res)
    paths = [_lead(ln)[0] for ln in leads]
    assert leads[0] == "src/a.py:10-20  save  (answer)"
    # the answers' files first, whatever their path (the test file after the source file among them), then the
    # claim's, then the passages'
    assert paths[:5] == ["src/a.py", "tests/test_a.py", "src/b.py", "src/c.py", "src/d.py"]
    assert "src/weak.py" not in paths                                      # a weak link is no lead
    assert paths[-2:] == ["docs/x.md", "tests/test_c.py"]                  # of the rest: doc paths after source
    assert "docs/x.md:1-2  x.md  (linked)" in leads and "src/c.py:7-9  helper  (passage)" in leads  # paths, tests last
    assert {_lead(ln)[1] for ln in leads} == {"answer", "claim", "linked", "passage"}
    # one lead per file, at most eight: the cap takes the passages' files, never an answer's (a test path too)
    res["passages"] += [f"src/p{i}.py:1-2 def p{i}()" for i in range(12)]
    many = av.leads_for(res)
    assert len(many) == 8 and len({_lead(ln)[0] for ln in many}) == 8
    assert "tests/test_a.py" in [_lead(ln)[0] for ln in many]
    assert len(av.leads_for(res, limit=3)) == 3
    assert [_lead(ln) for ln in av.leads_for(res, limit=1)] == [("src/a.py", "answer"), ("tests/test_a.py", "answer")]
    assert av.leads_for(_result(claims=[], passages=[], plan_check={"links": []})) == []


def _wide() -> dict:
    """Forty claims of 300 characters, each citing its own file; the first three answer the question."""
    res = _result(critique=[], unknowns=[])
    res["claims"] = [_claim(f"c{i}", f"`fn_{i}()` " + f"does thing {i} " * 30 + f"(src/m{i}.py:{i + 1}-{i + 4})")
                     for i in range(40)]
    res["subquestions"][0]["answer_claim_ids"] = ["c0", "c1", "c2"]
    res["subquestions"][0]["claim_ids"] = [f"c{i}" for i in range(40)]
    return res


def test_lead_view_never_exceeds_its_budget_and_never_sets_truncated():
    res = _wide()
    full = av.lead_view(res, budget=10 ** 6)
    assert len(full["context"]) == 6 and len(full["leads"]) == 8
    out = av.lead_view(res)
    assert _size(out) <= 2500 and "truncated" not in out and "truncation" not in out
    assert out["subquestions"][0]["answers"] == full["subquestions"][0]["answers"]  # answer claims never cut
    assert len(out.get("context") or []) < 6                                        # context lines go first ...
    assert [_lead(ln)[0] for ln in out["leads"]][:3] == ["src/m0.py", "src/m1.py", "src/m2.py"]
    tight = av.lead_view(res, budget=2000)
    assert _size(tight) <= 2000 and "context" not in tight                          # ... then the other leads ...
    assert [_lead(ln) for ln in tight["leads"]] == [("src/m0.py", "answer"), ("src/m1.py", "answer"),
                                                    ("src/m2.py", "answer")]        # ... never the answers' files
    assert tight["subquestions"][0]["answers"] == full["subquestions"][0]["answers"]
    assert "context claim" in tight["coverage"]                                     # what was cut is counted


def test_lead_view_keeps_clarifications_and_errors_whole():
    clar = [{"id": f"c-{i}", "kind": "entity", "question_en": f"which {i}? " + "x" * 330,
             "options": [{"value": "v1", "label": "the old one"}]} for i in range(4)]
    res = _result(status="needs_clarification", subquestions=[], claims=[], clarifications=clar,
                  passages=[f"src/p{i}.py:1-2 def p{i}()" for i in range(30)])
    out = av.lead_view(res)
    assert out["status"] == "needs_clarification" and out["clarifications"] == clar
    assert _size(out) <= 2500 and "truncated" not in out
    assert 0 < len(out["leads"]) < 8 and "left out" in out["coverage"]  # the budget took leads, not a clarification
    bad = _result(status="invalid_plan", subquestions=[], claims=[], passages=[],
                  errors=[{"at": "/language", "msg": "unknown language " + "y" * 300, "fix": "use tr or en"}] * 4)
    out = av.lead_view(bad)
    assert out["status"] == "invalid_plan" and out["errors"] == bad["errors"] and "truncated" not in out
    fb = {"drafted_plan_id": "qpl_0", "why": "the plan drafted for the question failed its own checks", "errors": ["e"]}
    out = av.lead_view(_result(plan_fallback=fb, plan_source="host", usage={"exhausted": "time budget 60.0s spent"}))
    assert out["plan_fallback"] == fb and out["plan_id"] == "qpl_1" and out["budget_exhausted"] == "time budget 60.0s spent"


def test_a_why_result_with_twenty_lead_commits_fits_and_keeps_both_ends():
    """The why handler's unknown lists the commits that changed the lines without stating a reason (D186): under the
    budget the list keeps its newest and oldest commits and says how many in between it left out."""
    commits = [f"{i:07x}aaa {2026 - i // 12}-{12 - i % 12:02d}-01 " + f"subject of commit {i} " * 3 for i in range(20)]
    unknown = {"question": "why does save commit twice?", "sub_question": "q1", "commits": commits,
               "why": f"the reason was not found: {len(commits)} commit(s) changed these lines and none states a "
                      "reason about it in its message; no decision record explains it",
               "next_step": "open a commit with `git show <sha>`; `history_search` with the symbol lists every commit"}
    res = _result(critique=[], unknowns=[unknown], passages=[])
    res["claims"] = [
        _claim("c1", "`save()` lines 15-20 were changed in 0000000aaa (2026-12-01): subject of commit 0",
               "primary_source_verified", evidence=["supports:git_history:commit 0000000aaa orders/repository.py"]),
        _claim("c2", "Decision record docs/adr/0001-sqlite-persistence.md (status: accepted) explains it: We persist "
               "orders in SQLite through `OrderRepository` only. No other module", "primary_source_verified",
               evidence=["supports:design_doc:docs/adr/0001-sqlite-persistence.md:3-7"]),
        *[_claim(f"c{i}", f"`fn_{i}()` calls `save()` (orders/m{i}.py:{i})") for i in range(3, 13)],
    ]
    res["subquestions"][0].update(answer_claim_ids=["c1", "c2"], claim_ids=[c["id"] for c in res["claims"]])
    out = av.lead_view(res)
    assert _size(out) <= 2500 and "truncated" not in out
    (u,) = out["unknowns"]
    assert u["question"] == unknown["question"] and u["why"] == unknown["why"] and u["next_step"] == unknown["next_step"]
    kept = u["commits"]
    assert kept[:3] == commits[:3] and kept[-3:] == commits[-3:] and len(kept) == 7  # three at each end ...
    assert "14 more" in kept[3] and "history_search" in kept[3]                     # ... and the count between
    assert res["unknowns"][0]["commits"] == commits  # the result dict is not changed
    # the list is cut only when the context lines and the other leads are already gone; the answers' files stay
    # (the history claim's path and lines, then the record: a doc path, not cut by the cap of eight either)
    assert "context" not in out
    assert out["leads"] == ["orders/repository.py:15-20  save  (answer)",
                            "docs/adr/0001-sqlite-persistence.md:3-7  OrderRepository  (answer)"]
    assert av.lead_view(res, budget=10 ** 6)["unknowns"] == [unknown]
    tighter = av.lead_view(res, budget=_size(out) - 100)  # both ends only, before anything that answers
    kept = tighter["unknowns"][0]["commits"]
    assert kept[0] == commits[0] and kept[-1] == commits[-1] and len(kept) == 3 and "18 more" in kept[1]
    assert tighter["subquestions"] == out["subquestions"] and _size(tighter) <= _size(out) - 100


def test_an_answer_in_a_doc_path_is_the_first_lead_and_show_lead_reads_it():
    """A why question answered by a decision record: its file is the first lead whatever its path, the cap of eight
    takes the context claims' source files instead, and show="lead" reads the record's lines."""
    res = _result(critique=[], unknowns=[], passages=[])
    res["plan_check"]["links"] = []
    res["claims"] = [
        _claim("c1", "Decision record docs/adr/0001-sqlite-persistence.md (status: accepted) explains it: We persist "
               "orders in SQLite through `OrderRepository` only", "primary_source_verified",
               evidence=["supports:design_doc:docs/adr/0001-sqlite-persistence.md:3-7"]),
        *[_claim(f"c{i}", f"`fn_{i}()` calls `save()` (orders/m{i}.py:{i})") for i in range(2, 11)],
    ]
    res["subquestions"][0].update(answer_claim_ids=["c1"], claim_ids=[c["id"] for c in res["claims"]])

    def read(path: str, start: int, end: int) -> str:
        return "\n".join(f"line {i} of {path}" for i in range(start, end + 1))

    out = av.lead_view(res, show="lead", read=read)
    assert out["leads"][0] == "docs/adr/0001-sqlite-persistence.md:3-7  OrderRepository  (answer)"
    assert [_lead(ln) for ln in out["leads"][1:]] == [(f"orders/m{i}.py", "claim") for i in range(2, 9)]
    assert out["lead_lines"]["path"] == "docs/adr/0001-sqlite-persistence.md"
    assert (out["lead_lines"]["start"], out["lead_lines"]["end"]) == (3, 7)
    assert out["lead_lines"]["text"].startswith("3 line 3 of docs/adr/")


def test_show_lead_adds_the_rank_one_lines_within_4500_chars():
    res = _two_questions()
    seen = []

    def read(path: str, start: int, end: int) -> str | None:
        seen.append((path, start, end))
        return "\n".join("" if i % 7 == 3 else f"line {i} of {path}" for i in range(start, end + 1))  # 24, 31 ... blank

    out = av.lead_view(res, show="lead", read=read)
    first = _lead(out["leads"][0])[0]
    assert first == "orders/service.py" and out["lead_lines"]["path"] == first
    # the narrowest span the result cites in that file (c1 cites line 21, c2 line 22, the plan link 19-22)
    assert (out["lead_lines"]["start"], out["lead_lines"]["end"]) == (21, 21) and seen == [("orders/service.py", 21, 21)]
    assert out["lead_lines"]["text"] == "21 line 21 of orders/service.py"
    assert list(out)[-1] == "lead_lines" and "lead_lines" not in av.lead_view(res, read=read)
    # a long span: at most 60 lines, numbered, blank lines left out, and the whole response under its budget
    res["claims"][0]["text"] = "`place_order()` is defined at orders/service.py:19-300"
    res["claims"][0]["evidence"] = ["supports:source_code:orders/service.py:19-300"]
    res["claims"][1]["text"] = "`place_order()` -> `.save()` reaches the database"
    res["claims"][1]["evidence"] = []
    res["plan_check"]["links"] = []
    out = av.lead_view(res, show="lead", read=read)
    ll = out["lead_lines"]
    assert (ll["start"], ll["end"]) == (19, 78) and ll["text"].startswith("19 line 19 of") and "\n78 line 78" in ll["text"]
    assert "\n24 " not in ll["text"] and "\n25 line 25" in ll["text"] and _size(out) <= 4500  # blank lines left out
    tight = av.lead_view(res, show="lead", read=read, lead_budget=_size(out) - 200)
    assert _size(tight) <= _size(out) - 200 and tight["lead_lines"]["end"] < 78 and tight["lead_lines"]["start"] == 19
    # a file that cannot be read: no lines, and the coverage says so
    gone = av.lead_view(res, show="lead", read=lambda p, a, b: None)
    assert "lead_lines" not in gone and "orders/service.py" in gone["coverage"] and "not read" in gone["coverage"]
    # an answer that cites a file without lines (a commit's path) reads the lines another claim cites in that file
    res["claims"][0]["text"] = "`place_order()` was changed in 0000000aaa (2026-12-01): init"
    res["claims"][0]["evidence"] = ["supports:git_history:commit 0000000aaa orders/service.py"]
    out = av.lead_view(res, show="lead", read=read)
    assert out["leads"][0] == "orders/service.py:26  place_order  (answer)"  # the first lines seen for the file
    assert (out["lead_lines"]["start"], out["lead_lines"]["end"]) == (26, 26)   # c8's `.get()` call site
    with pytest.raises(ValueError):
        av.lead_view(res, show="passages")


def test_lead_view_coverage_names_the_refresh_state():
    skipped = {"skipped": "estimated 120.0 s", "stale_count": 3, "stale_files": ["a.py", "b.py", "c.py"],
               "background_update": "started (pid 4242)"}
    cov = av.lead_view(_result(index_refresh=skipped))["coverage"]
    assert "3 changed file(s)" in cov and "estimated 120.0 s" in cov and "started (pid 4242)" in cov
    assert "re-indexed 2" in av.lead_view(_result(index_refresh={"ran": True, "changed_count": 2}))["coverage"]
    err = "index could not be refreshed (boom); the graph describes an older tree"
    cov = av.lead_view(_result(index_refresh={"error": err}, index_refresh_error=err))["coverage"]
    assert "boom" in cov
    assert "index current" in av.lead_view(_result(index_refresh={"changed_count": 0}))["coverage"]
