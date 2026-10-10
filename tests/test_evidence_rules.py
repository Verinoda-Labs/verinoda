"""Evidence rules that can only lower a status (verinoda/evidence_rules.py, D182), on `verinoda relations`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from verinoda import cli, evidence_rules, relations


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")


def _rules(root: Path, rules) -> None:
    _write(root, ".verinoda/config.json", json.dumps({"corpus": {"topics": "topics.txt"},
                                                      "evidence": {"rules": rules}}))


@pytest.fixture
def corpus(tmp_path):
    root = tmp_path / "kb"
    _write(root, "topics.txt", "Hücre\nDoku\nOrgan\nMitoz\nMayoz\n")
    # Hücre -> Doku: one sentence naming both; Doku -> Organ: only through the file's own topic ("bu konu")
    _write(root, "konular/doku.md", "# Doku\n\nDoku konusundan önce Hücre konusu öğrenilmelidir. Bu konu, organ "
                                    "konusunun ön koşuludur.\n")
    _write(root, "konular/mitoz.md", "# Mitoz\n\nMitoz ve mayoz ortak kavramlara sahiptir.\n")
    return root


def _rows(res):
    return {(r["from"], r["to"]): r for r in res["relations"]}


def test_a_product_rule_lowers_what_it_does_not_accept_and_nothing_else(corpus, capsys):
    # the field test's product: an edge is proven only when one sentence names both topics
    _rules(corpus, [{"name": "both-named", "applies_to": "relations", "require": "both_named", "else": "unknown"}])
    rows = _rows(relations.find(corpus))
    assert rows[("Hücre", "Doku")]["status"] == "strong_inference" and "lowered_by" not in rows[("Hücre", "Doku")]
    assert rows[("Doku", "Organ")]["status"] == "unknown" and rows[("Doku", "Organ")]["lowered_by"] == ["both-named"]
    raw = _rows(relations.find(corpus, rules=False))
    assert raw[("Doku", "Organ")]["status"] == "weak_inference" and "lowered_by" not in raw[("Doku", "Organ")]
    capsys.readouterr()
    assert cli.main(["relations", "--repo", str(corpus)]) == 0
    out = capsys.readouterr().out
    assert "lowered by both-named" in out and "evidence rules applied (they only lower): both-named" in out


def test_a_rule_never_raises_a_status(corpus):
    _rules(corpus, [{"name": "lenient", "require": {"min_sources": 5}, "else": "strong_inference"}])
    rows = _rows(relations.find(corpus))
    assert rows[("Doku", "Organ")]["status"] == "weak_inference"   # below the cap already: left as it was
    assert all("lowered_by" not in r for r in rows.values())


def test_conditions_kinds_and_several_rules(corpus):
    _rules(corpus, [
        {"name": "two-sources", "require": {"min_sources": 2}, "else": "weak_inference", "kinds": ["prerequisite"]},
        {"name": "directed", "require": ["direction_known", "no_conflict"], "else": "unknown"},
    ])
    res = relations.find(corpus)
    rows = _rows(res)
    assert rows[("Hücre", "Doku")]["status"] == "weak_inference" and rows[("Hücre", "Doku")]["lowered_by"] == \
        ["two-sources"]
    shared = next(r for r in res["relations"] if r["kind"] == "shared")
    assert shared["status"] == "unknown" and shared["lowered_by"] == ["directed"]   # kinds kept it from two-sources
    assert res["evidence_rules"] == ["two-sources", "directed"]


@pytest.mark.parametrize("rule,error", [
    ({"name": "verify", "require": "both_named", "else": "statically_verified"}, "may only lower"),
    ({"name": "odd", "require": "seen_twice", "else": "weak_inference"}, "unknown condition"),
    ({"name": "claims", "applies_to": "claims", "require": "both_named", "else": "weak_inference"}, "stage B"),
    ({"require": "both_named", "else": "weak_inference"}, "needs a name"),
    ({"name": "cap", "require": "both_named", "else": "maybe"}, "one of"),
    ({"name": "n", "require": {"min_sources": 0}, "else": "weak_inference"}, "unknown condition"),
])
def test_a_broken_rule_is_reported_and_never_applied(corpus, capsys, rule, error):
    _rules(corpus, [rule])
    res = relations.find(corpus)
    assert "evidence_rules" not in res and len(res["rule_errors"]) == 1 and error in res["rule_errors"][0]
    assert _rows(res)[("Hücre", "Doku")]["status"] == "strong_inference"
    capsys.readouterr()
    assert cli.main(["relations", "--repo", str(corpus)]) == 0   # never fatal
    assert "warning: evidence rule not applied:" in capsys.readouterr().err


def test_load_reads_nothing_from_a_config_without_rules():
    assert evidence_rules.load({}) == ([], [])
    assert evidence_rules.load({"evidence": {"rules": "both_named"}})[1] == ["evidence.rules must be a list of rules"]
