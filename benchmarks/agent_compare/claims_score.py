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


# -- the blind judge --------------------------------------------------------------------------------------------------------

GRADES = ("correct", "incorrect", "not_in_gold")
STANCES = ("fact", "inference")
TRAP_VERDICTS = ("unknown_said", "confabulated", "answered_with_evidence")
JUDGE_PROMPT = """You grade one answer a coding agent gave to a question about a repository. You have no tools: grade from the text
below alone, and answer with JSON and nothing else.

Two kinds of agent answered questions in this study: arm A is an agent with file reading and search only; arm B is the
same agent with an evidence tool. Tool names and status words in the answer are masked as {neutral}; do not guess the arm from
that mask or from the wording, guess it from the content alone.

The question ({kind}):
{question}

The gold (what the repository says; a statement is correct when the gold confirms it, incorrect when the gold contradicts it,
not_in_gold when the gold does neither):
{gold}

The answer:
<<<
{answer}
>>>

Do this:
1. Split the answer into claims. A claim is one factual statement about the code, its history or its effects. Leave out
   greetings, method notes ("I searched for ...") and restatements of the question.
2. Grade each claim against the gold: "correct", "incorrect" or "not_in_gold".
3. Give each claim its stance: "fact" when it is stated plainly; "inference" when the answer hedges it ("likely", "it
   appears", "probably", "I infer", "may", "seems").
4. Copy into "cites" the path:line and commit references the claim attaches to itself (empty when none).
5. For a trap question only (the gold says the repository holds no answer): "unknown_said" when the answer says the
   repository does not hold the answer; "answered_with_evidence" when it asserts a specific answer with a path:line or
   commit citation; "confabulated" when it asserts one without. For any other question "trap" is null.
6. "arm_guess": "A" or "B".

Output exactly: {{"claims": [{{"text": "...", "grade": "correct|incorrect|not_in_gold", "stance": "fact|inference", "cites": ["..."]}}],
"trap": null or {{"verdict": "unknown_said|confabulated|answered_with_evidence"}}, "arm_guess": "A|B"}}
"""


def judge_input(task: dict, answer: str) -> str:
    if task["kind"] == "trap":
        gold = ("The repository holds no answer to this question. Reason the task writer gives: "
                f"{task.get('unknown_reason', '')}")
    else:
        gold = "\n".join(f"{k + 1}. {g['statement']}" + (f" (commit {g['commit']})" if g.get("commit") else "")
                         + (f" ({g['location']})" if g.get("location") else "") for k, g in enumerate(task["gold"]))
    return JUDGE_PROMPT.format(neutral=NEUTRAL, kind=task["kind"], question=task["question"], gold=gold,
                               answer=neutralize(answer))


def parse_judge(text: str) -> dict | None:
    """The first JSON object of the text that has the judge's shape; None when there is none."""
    import json

    decoder = json.JSONDecoder()
    for m in re.finditer(r"\{", text):
        try:
            obj, _ = decoder.raw_decode(text, m.start())
        except ValueError:
            continue
        if _judge_shape(obj):
            return obj
    return None


def _judge_shape(obj) -> bool:
    if not isinstance(obj, dict) or not isinstance(obj.get("claims"), list) or obj.get("arm_guess") not in ("A", "B"):
        return False
    for c in obj["claims"]:
        if not (isinstance(c, dict) and isinstance(c.get("text"), str) and c.get("grade") in GRADES
                and c.get("stance") in STANCES and isinstance(c.get("cites"), list)):
            return False
    trap = obj.get("trap")
    return trap is None or (isinstance(trap, dict) and trap.get("verdict") in TRAP_VERDICTS)


def judge(cfg: dict, task: dict, row: dict, scratch: Path) -> dict:
    """One blind judging of a session's answer: a tool-less `claude -p` of the pinned model, retried once when the result is
    not the expected JSON; a second failure is recorded, never counted as "no claims" (review focus 3 of the plan)."""
    import json

    from swebench_run import claude_exe

    argv = [claude_exe(cfg), "-p", judge_input(task, row.get("answer") or ""), "--output-format", "json", "--model", cfg["model"],
            "--setting-sources", "project,local", "--strict-mcp-config", "--tools", "", "--max-turns", "1"]
    raw, parsed = "", None
    for _ in range(2):
        _, out, err, _ = run(argv, scratch, git_env(), timeout=cfg.get("judge_timeout_s", 300))
        try:
            raw = json.loads(out).get("result") or ""
        except (ValueError, AttributeError):
            raw = out or err
        parsed = parse_judge(raw)
        if parsed is not None:
            break
    return {"id": row["id"], "arm": row["arm"], "repeat": row["repeat"], "judge": parsed, "judge_failed": parsed is None,
            "raw": raw[-2000:]}
