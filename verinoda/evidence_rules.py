"""Evidence rules a user gives, which can only lower a status (D182).

A product may count a relation as proven only on its own terms ("one sentence names both topics"); Verinoda's
status knows nothing of them. ``evidence.rules`` in ``.verinoda/config.json`` (or the user's config) states such
terms; a relation that does not meet a rule's ``require`` gets at most the rule's ``else`` status::

    "evidence": {"rules": [
      {"name": "both-named-in-one-sentence", "applies_to": "relations", "require": "both_named",
       "else": "weak_inference"},
      {"name": "two-sources", "require": {"min_sources": 2}, "else": "weak_inference", "kinds": ["prerequisite"]}
    ]}

``require``: ``both_named`` (a source sentence names both topics: not only the file's own topic), ``direction_known``
(not a ``shared`` relation), ``no_conflict``, ``{"min_sources": N}``, or a list of them (all must hold). ``else``:
``strong_inference``, ``weak_inference`` or ``unknown``. A rule never raises a status: one that names a verified status,
an unknown condition or another target is a rule error, reported with the result and never applied. Rules apply to
``verinoda relations`` (D181); ``analyze`` claims are stage B of backlog 20.1.

Not among the settings that need the user's trust (``paths.PROTECTED_SETTINGS``): a rule a cloned repository ships
can only make its answers more cautious.
"""

from __future__ import annotations

from dataclasses import dataclass, field

STATUS_RANK = {"strong_inference": 2, "weak_inference": 1, "unknown": 0}
VERIFIED = ("observed", "experiment_verified", "statically_verified", "primary_source_verified")
CONDITIONS = ("both_named", "direction_known", "no_conflict", "min_sources")
TARGETS = ("relations",)


@dataclass
class Rule:
    name: str
    require: list[tuple[str, int]]
    cap: str
    kinds: tuple[str, ...] = ()
    errors: list[str] = field(default_factory=list)


def _conditions(raw) -> list[tuple[str, int]]:
    items = raw if isinstance(raw, list) else [raw]
    out = []
    for c in items:
        if isinstance(c, str) and c in CONDITIONS and c != "min_sources":
            out.append((c, 0))
        elif isinstance(c, dict) and set(c) == {"min_sources"} and isinstance(c["min_sources"], int) \
                and not isinstance(c["min_sources"], bool) and c["min_sources"] >= 1:
            out.append(("min_sources", c["min_sources"]))
        else:
            raise ValueError(f"unknown condition {c!r} (both_named, direction_known, no_conflict, "
                             '{"min_sources": N})')
    if not out:
        raise ValueError("no condition in require")
    return out


def load(cfg: dict) -> tuple[list[Rule], list[str]]:
    """The valid rules of a config and the errors of the others (never raises)."""
    raw = (cfg.get("evidence") or {}).get("rules") if isinstance(cfg.get("evidence"), dict) else None
    if raw is None:
        return [], []
    if not isinstance(raw, list):
        return [], ["evidence.rules must be a list of rules"]
    rules, errors = [], []
    for k, r in enumerate(raw):
        label = r.get("name") if isinstance(r, dict) and isinstance(r.get("name"), str) else f"rule {k + 1}"
        try:
            if not isinstance(r, dict):
                raise TypeError("a rule is an object")
            if not isinstance(r.get("name"), str) or not r["name"].strip():
                raise ValueError("a rule needs a name")
            target = r.get("applies_to", "relations")
            if target not in TARGETS:
                raise ValueError(f"applies_to {target!r}: rules apply to relations only (analyze claims are stage B)")
            cap = r.get("else")
            if cap in VERIFIED:
                raise ValueError(f"else {cap!r}: a rule may only lower a status, never verify one")
            if cap not in STATUS_RANK:
                raise ValueError(f"else {cap!r}: one of {', '.join(STATUS_RANK)}")
            kinds = r.get("kinds") or ()
            if not isinstance(kinds, (list, tuple)) or not all(isinstance(x, str) for x in kinds):
                raise TypeError("kinds must be a list of relation kinds")
            rules.append(Rule(r["name"].strip(), _conditions(r.get("require")), cap, tuple(kinds)))
        except (ValueError, TypeError) as exc:
            errors.append(f"{label}: {exc}")
    return rules, errors


def _holds(cond: str, n: int, row: dict) -> bool:
    if cond == "both_named":
        return any(not e.get("implicit") for e in row["evidence"])
    if cond == "direction_known":
        return row["kind"] != "shared"
    if cond == "no_conflict":
        return not row.get("conflict")
    return row["sources"] >= n


def apply(rows: list[dict], rules: list[Rule]) -> None:
    """Lower each row a rule's conditions fail on to the rule's cap (in place); ``lowered_by`` names the rules."""
    for row in rows:
        for rule in rules:
            if rule.kinds and row["kind"] not in rule.kinds:
                continue
            if all(_holds(c, n, row) for c, n in rule.require):
                continue
            if STATUS_RANK[rule.cap] < STATUS_RANK[row["status"]]:
                row["status"] = rule.cap
                row.setdefault("lowered_by", []).append(rule.name)
