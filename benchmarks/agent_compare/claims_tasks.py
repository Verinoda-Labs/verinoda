"""The tasks of the false-claims study (DESIGN_CLAIMS.md): their format, the fixed order, the checks on a written task,
and the prompts of the agents that write and check them.

    python benchmarks/agent_compare/claims_tasks.py TASKS.json          # validate, print the order and the pilot ids

A task is one JSON object: ``id`` (``<owner>__<name>-<kind>-<n>``), ``repo``, ``sha``, ``kind`` (why, when, affects,
trap), ``question``, ``gold`` (statements with a ``commit`` or a ``location``; a trap's is the one word ``unknown``),
``gold_sources`` (the git and search commands that produced the gold), ``gold_files`` (affects only) and
``unknown_reason`` (trap only). The 40 tasks live in ``claims_tasks.json`` beside this file, committed before the
first session.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

KINDS = {"why": 8, "when": 8, "affects": 14, "trap": 10}
SEED = "20261011:"
MANIFEST = Path(__file__).resolve().parents[1] / "realworld" / "manifest.json"
REPOS: list[str] = [r["name"] for r in json.loads(MANIFEST.read_text(encoding="utf-8"))["repos"]]
TRAP_GOLD = [{"statement": "unknown", "commit": None, "location": None}]
_HEX = re.compile(r"^[0-9a-f]{7,40}$")


def order(ids: list[str]) -> list[str]:
    """The study's order: by the hash of the seeded id, so it is fixed when the tasks are and no one chooses it."""
    return sorted(ids, key=lambda i: hashlib.sha256((SEED + i).encode("utf-8")).hexdigest())


def _text(x) -> bool:
    return isinstance(x, str) and bool(x.strip())


def validate(tasks: list[dict]) -> list[str]:
    """Every problem with the set, one string each; an empty list means the set is what the spec fixes."""
    problems: list[str] = []
    if len(tasks) != sum(KINDS.values()):
        problems.append(f"40 tasks expected, {len(tasks)} given")
    seen: set[str] = set()
    for t in tasks:
        if t.get("id") in seen:
            problems.append(f"repeated id {t.get('id')}")
        seen.add(t.get("id"))
    per_repo: dict[str, int] = {}
    per_kind: dict[str, int] = {}
    for t in tasks:
        per_repo[t.get("repo")] = per_repo.get(t.get("repo"), 0) + 1
        per_kind[t.get("kind")] = per_kind.get(t.get("kind"), 0) + 1
    for repo in REPOS:
        if per_repo.get(repo, 0) != 4:
            problems.append(f"{repo}: {per_repo.get(repo, 0)} tasks, 4 expected")
    for repo in set(per_repo) - set(REPOS):
        problems.append(f"{repo}: not a repository of the manifest")
    for kind, n in KINDS.items():
        if per_kind.get(kind, 0) != n:
            problems.append(f"{kind}: {per_kind.get(kind, 0)} tasks, {n} expected")
    for t in tasks:
        tid = t.get("id", "?")
        for field in ("id", "repo", "sha", "kind", "question"):
            if not _text(t.get(field)):
                problems.append(f"{tid}: {field} missing")
        if t.get("kind") not in KINDS:
            problems.append(f"{tid}: kind {t.get('kind')!r} is none of {sorted(KINDS)}")
        if not re.fullmatch(r"[0-9a-f]{40}", str(t.get("sha", ""))):
            problems.append(f"{tid}: sha is not 40 hex characters")
        if _text(t.get("question")) and not t["question"].rstrip().endswith("?"):
            problems.append(f"{tid}: the question does not end with ?")
        if not (isinstance(t.get("gold_sources"), list) and t["gold_sources"] and all(_text(s) for s in t["gold_sources"])):
            problems.append(f"{tid}: gold_sources missing")
        gold = t.get("gold")
        if not (isinstance(gold, list) and gold and all(isinstance(g, dict) for g in gold)):
            problems.append(f"{tid}: gold missing")
            continue
        if t.get("kind") == "trap":
            if gold != TRAP_GOLD:
                problems.append(f"{tid}: a trap's gold is exactly {TRAP_GOLD}")
            if not _text(t.get("unknown_reason")):
                problems.append(f"{tid}: unknown_reason missing")
        else:
            for k, g in enumerate(gold):
                if not _text(g.get("statement")):
                    problems.append(f"{tid}: gold {k} has no statement")
                has_commit = _text(g.get("commit")) and _HEX.match(g["commit"])
                has_location = _text(g.get("location")) and re.fullmatch(r".+:\d+(-\d+)?", g["location"])
                if not (has_commit or has_location):
                    problems.append(f"{tid}: gold {k} needs a commit or location")
        if t.get("kind") == "affects" and not (isinstance(t.get("gold_files"), list) and t["gold_files"]
                                               and all(_text(f) for f in t["gold_files"])):
            problems.append(f"{tid}: gold_files missing (an affects task names the files)")
    return problems


def load_tasks(path: Path) -> list[dict]:
    """The tasks of a ``{"tasks": [...]}`` file, validated; the problems are the error when there are any."""
    tasks = json.loads(path.read_text(encoding="utf-8"))["tasks"]
    problems = validate(tasks)
    if problems:
        raise ValueError("\n".join(problems))
    return tasks


def main() -> int:
    tasks = load_tasks(Path(sys.argv[1]))
    ids = order([t["id"] for t in tasks])
    print(json.dumps({"order": ids, "pilot_ids": ids[:8]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
