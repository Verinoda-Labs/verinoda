"""The strict mechanical citation check for the D186 re-runs (the plan's Task 8).

The first run's check (claims_score.check_citation) kept 77 of 150 location citations moved by 60 lines and 65 of 120
swapped commits "confirmed" (claims-2026-10-11/README.md): a substring of a neighbouring name within a few lines of the
cited one, or the question's own identifiers, were enough. This check reads the cited lines only, matches identifiers as
whole words, takes no identifiers from the question, and requires a quoted commit subject to be the commit's. It writes
its own file (``mechanical-strict.jsonl``); the measured files of the first run are scored by claims_score.py and are not
touched.

    python benchmarks/agent_compare/claims_mech_strict.py WORK_DIR
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from claims_score import TOOL_PATHS, _candidates, _sentence_around, citations, identifiers
from guard_run import git_env, run

_QUOTED = re.compile(r'["“„]([^"”“]{6,120})["”]')


def _word_in(ident: str, text: str) -> bool:
    return re.search(rf"(?<![A-Za-z0-9_]){re.escape(ident)}(?![A-Za-z0-9_])", text) is not None


def _lines_verdict(file: Path, cit: dict, ids: list[str]) -> str:
    if not file.is_file():
        return "missing"
    lines = file.read_text(encoding="utf-8", errors="replace").splitlines()
    line, end = cit["line"], cit["end"] or cit["line"]
    if line < 1 or line > len(lines):
        return "missing"
    cited = "\n".join(lines[line - 1:min(len(lines), end)])
    return "confirmed" if any(_word_in(i, cited) for i in ids) else "wrong"


def check_citation_strict(cit: dict, claim: str, copy: Path) -> str:
    """``confirmed``, ``wrong``, ``missing`` or ``not_repo`` as claims_score.check_citation, under the strict rules."""
    ids = identifiers(claim)
    if cit["kind"] == "location":
        path = cit["path"] or ""
        if any(path.startswith(p.rstrip("/")) or f"/{p}" in f"/{path}" for p in TOOL_PATHS):
            return "not_repo"
        verdicts = [_lines_verdict(copy / p, cit, ids) for p in _candidates(copy, path)]
        for v in ("confirmed", "wrong"):
            if v in verdicts:
                return v
        return "missing"
    h = cit["hash"] or ""
    if len(h) < 7:
        return "missing"
    rc, kind, _, _ = run(["git", "cat-file", "-t", h], copy, git_env())
    if rc != 0 or kind.strip() != "commit":
        return "missing"
    _, shown, _, _ = run(["git", "show", "--stat", "-p", "--format=%ad%n%H%n%h%n%B", "--date=short", h], copy, git_env())
    shown = shown[:400_000]
    years = re.findall(r"\b(20\d\d|19\d\d)\b", claim)
    if years and not any(shown.startswith(y) for y in years):
        return "wrong"
    message = shown.split("\ndiff --git ", 1)[0].lower()
    for quoted in _QUOTED.findall(claim):  # a subject the claim quotes must be this commit's
        if quoted.strip().lower() not in message:
            return "wrong"
    return "confirmed" if any(_word_in(i, shown) for i in ids) else "wrong"


def mechanical_strict(row: dict, copy: Path) -> dict:
    text = row.get("answer") or ""
    return {"id": row["id"], "arm": row["arm"], "repeat": row["repeat"], "check": "strict",
            "citations": [{**c, "verdict": check_citation_strict(c, _sentence_around(text, c["raw"]), copy)}
                          for c in citations(text)]}


def main() -> int:
    work = Path(sys.argv[1])
    rows = [json.loads(x) for x in (work / "results.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    from claims_tasks import copy_dir

    out = [mechanical_strict(r, copy_dir(work, r["id"], r["arm"], r["repeat"])) for r in rows]
    (work / "mechanical-strict.jsonl").write_text("".join(json.dumps(m, ensure_ascii=False) + "\n" for m in out),
                                                  encoding="utf-8")
    by_arm: dict[str, dict[str, int]] = {}
    for m in out:
        for c in m["citations"]:
            by_arm.setdefault(m["arm"], {})[c["verdict"]] = by_arm.setdefault(m["arm"], {}).get(c["verdict"], 0) + 1
    print(json.dumps(by_arm, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
