"""Score the false-claims study (DESIGN_CLAIMS.md): the mechanical check of every citation an answer carries, the blind judge
that splits an answer into claims and grades them against the gold, and the paired summary with the decision rule.

    python benchmarks/agent_compare/claims_score.py WORK_DIR [--judge] [--config CONFIG.json]

Reads ``WORK/results.jsonl`` and ``WORK/tasks.json``; writes ``WORK/mechanical.jsonl``, with ``--judge`` ``WORK/judge.jsonl``
(resumable: a session already judged is not judged again), then ``WORK/summary.json``, ``WORK/hand_check.json`` (40 claims,
no arm) and ``WORK/hand_check_key.json`` (the arms). Differences are paired per task (the Verinoda arm minus the plain arm,
a task's value the mean over its repeats) with a bootstrap 95 % interval over tasks (seed 20261011, 10,000 resamples); a
claim only when the interval excludes zero.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from guard_run import git_env, run

PLAIN, GUIDED = "none", "verinoda_guided"
SEED = 20261011
# a citation into the tool's own files is not evidence of the repository (review focus 1 of the plan)
TOOL_PATHS = (".verinoda/", "atlas.db", ".claude/", ".mcp.json")
NEUTRAL = "[tool]"
# longest alternatives first, so that `mcp__verinoda__analyze` is one token and not two
_TOOL_WORDS = re.compile(r"mcp__verinoda__\w+|statically_verified|strong_inference|weak_inference|project_query|history_search|"
                         r"change_review|code_check|run_tool|verinoda|analyze", re.IGNORECASE)
_LOCATION = re.compile(r"(?P<path>[\w./\\-]+\.\w{1,10}):(?P<line>\d+)(?:-(?P<end>\d+))?")
_HASH = re.compile(r"\b[0-9a-f]{7,40}\b")
_STOPWORDS = {"this", "that", "with", "from", "into", "when", "where", "which", "while", "there", "their", "these", "those",
              "then", "than", "have", "been", "were", "will", "would", "could", "should", "also", "only", "because", "about",
              "after", "before", "added", "removed", "changed", "function", "file", "files", "line", "lines", "commit",
              "repository", "code", "default", "value", "called", "calls", "does", "used", "uses", "using", "likely", "appears"}


def citations(text: str) -> list[dict]:
    """Every `path:line`, `path:a-b` and commit hash an answer carries; paths with backslashes or a leading `./` normalized."""
    out: list[dict] = []
    for m in _LOCATION.finditer(text):
        path = m.group("path").replace("\\", "/")
        while path.startswith("./"):
            path = path[2:]
        out.append({"kind": "location", "raw": m.group(0), "path": path, "line": int(m.group("line")),
                    "end": int(m.group("end")) if m.group("end") else None, "hash": None})
    spans = [(m.start(), m.end()) for m in _LOCATION.finditer(text)]
    for m in _HASH.finditer(text):
        if m.group(0).isdigit() or any(a <= m.start() < b for a, b in spans):
            continue
        out.append({"kind": "commit", "raw": m.group(0), "path": None, "line": None, "end": None, "hash": m.group(0)})
    return out


def identifiers(claim: str) -> list[str]:
    """What of the claim should be found at the cited place: backticked spans first, else identifier-like words."""
    quoted = [q.strip() for q in re.findall(r"`([^`]+)`", claim) if q.strip()]
    if quoted:
        return quoted
    return [w for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", claim) if w.lower() not in _STOPWORDS]


def check_citation(cit: dict, claim: str, copy: Path) -> str:
    """``confirmed`` (the cited place holds something of the claim), ``wrong`` (exists, does not), ``missing`` (no such line
    or commit), ``not_repo`` (one of the tool's own files)."""
    if cit["kind"] == "location":
        path = cit["path"] or ""
        if any(path.startswith(p.rstrip("/")) or f"/{p}" in f"/{path}" for p in TOOL_PATHS):
            return "not_repo"
        file = copy / path
        if not file.is_file():
            return "missing"
        lines = file.read_text(encoding="utf-8", errors="replace").splitlines()
        line, end = cit["line"], cit["end"] or cit["line"]
        if line < 1 or line > len(lines):
            return "missing"
        window = "\n".join(lines[max(0, line - 4):min(len(lines), end + 3)])
        return "confirmed" if any(i in window for i in identifiers(claim)) else "wrong"
    h = cit["hash"] or ""
    if len(h) < 7:
        return "missing"
    rc, kind, _, _ = run(["git", "cat-file", "-t", h], copy, git_env())
    if rc != 0 or kind.strip() != "commit":
        return "missing"
    _, shown, _, _ = run(["git", "show", "--stat", "--format=%ad%n%B", "--date=short", h], copy, git_env())
    years = re.findall(r"\b(20\d\d|19\d\d)\b", claim)
    if years and not any(shown.startswith(y) for y in years):
        return "wrong"
    return "confirmed" if any(i in shown for i in identifiers(claim)) else "wrong"


def neutralize(text: str) -> str:
    """The answer as the judge sees it: the tool's names and status words masked, so the arm is not readable from the style."""
    return _TOOL_WORDS.sub(NEUTRAL, text)
