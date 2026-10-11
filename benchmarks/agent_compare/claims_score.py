"""Score the false-claims study (DESIGN_CLAIMS.md): the mechanical check of every citation an answer carries, the blind judge
that splits an answer into claims and grades them against the gold, and the paired summary with the decision rule.

    python benchmarks/agent_compare/claims_score.py WORK_DIR [--judge] [--judge-workers 4] [--config CONFIG.json]

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
# a citation into the tool's own files is not evidence of the repository (D185, the plan's review focus)
TOOL_PATHS = (".verinoda/", "atlas.db", ".claude/", ".mcp.json")
NEUTRAL = "[tool]"
# longest alternatives first, so that `mcp__verinoda__analyze` is one token and not two
_TOOL_WORDS = re.compile(r"mcp__verinoda__\w+|statically_verified|strong_inference|weak_inference|project_query|history_search|"
                         r"change_review|code_check|run_tool|verinoda|analyze", re.IGNORECASE)
# the extension starts with a letter: `127.0.0.1:1234` is a host and a port, not a file and a line
_LOCATION = re.compile(r"(?P<path>[\w./\\-]+\.[A-Za-z]\w{0,9}):(?P<line>\d+)(?:-(?P<end>\d+))?")
_TRACKED: dict[str, list[str]] = {}
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


_EXTENSIONS = {"go", "py", "js", "ts", "tsx", "rs", "php", "java", "md", "json", "toml", "yaml", "yml", "txt", "html", "css"}


def identifiers(claim: str) -> list[str]:
    """What of the claim should be found at the cited place: the identifier-like tokens of its backticked spans (a span is
    split, so `A.__init__` or `&x[0] == y()` yields its names) and of its plain words; a hash, a number, a file extension
    and a common English word are not identifiers. The pilot's matcher took each backticked span whole and graded 8 of 8
    sampled correct citations `wrong`."""
    out: list[str] = []
    for span in re.findall(r"`([^`]+)`", claim):
        out += re.findall(r"[A-Za-z_][A-Za-z0-9_]*", span)
    out += re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", re.sub(r"`[^`]+`", " ", claim))
    seen: list[str] = []
    for w in out:
        if (len(w) < 3 or w.lower() in _STOPWORDS or w.lower() in _EXTENSIONS or w.isdigit()
                or re.fullmatch(r"[0-9a-f]{7,40}", w) or w in seen):
            continue
        seen.append(w)
    return seen


def _candidates(copy: Path, path: str) -> list[str]:
    """The files a cited path may mean: the path itself; or, for a bare name or a partial path an answer uses after naming
    the file once in full ("`sqlmodel/main.py` ... at main.py:565", "stream/JsonReader.java:1831"), every tracked file that
    ends with it."""
    if (copy / path).is_file():
        return [path]
    key = str(copy)
    if key not in _TRACKED:
        _, out, _, _ = run(["git", "ls-files"], copy, git_env(), timeout=120)
        _TRACKED[key] = out.splitlines()
    return [f for f in _TRACKED[key] if f == path or f.endswith("/" + path.lstrip("/"))]


def _location_verdict(file: Path, cit: dict, ids: list[str]) -> str:
    if not file.is_file():
        return "missing"
    lines = file.read_text(encoding="utf-8", errors="replace").splitlines()
    line, end = cit["line"], cit["end"] or cit["line"]
    if line < 1 or line > len(lines):
        return "missing"
    window = "\n".join(lines[max(0, line - 4):min(len(lines), end + 3)])
    return "confirmed" if any(i in window for i in ids) else "wrong"


def check_citation(cit: dict, claim: str, copy: Path, extra: list[str] | tuple[str, ...] = ()) -> str:
    """``confirmed`` (the cited place holds something of the claim, or of ``extra``: the question's own identifiers, for a
    claim like "it is called here"), ``wrong`` (exists, does not), ``missing`` (no such line or commit), ``not_repo`` (one of
    the tool's own files)."""
    if cit["kind"] == "location":
        path = cit["path"] or ""
        if any(path.startswith(p.rstrip("/")) or f"/{p}" in f"/{path}" for p in TOOL_PATHS):
            return "not_repo"
        verdicts = [_location_verdict(copy / p, cit, [*identifiers(claim), *extra]) for p in _candidates(copy, path)]
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
    # the date first (the year check reads it), then the message and the patch: a claim about a commit may name what the
    # commit's diff holds ("the commit introduced `func X`"), not only its message
    _, shown, _, _ = run(["git", "show", "--stat", "-p", "--format=%ad%n%H%n%h%n%B", "--date=short", h], copy, git_env())
    shown = shown[:400_000]
    years = re.findall(r"\b(20\d\d|19\d\d)\b", claim)
    if years and not any(shown.startswith(y) for y in years):
        return "wrong"
    return "confirmed" if any(i in shown for i in [*identifiers(claim), *extra]) else "wrong"


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
    not the expected JSON; a second failure is recorded, never counted as "no claims" (D185)."""
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


# -- the summary and the decision rule --------------------------------------------------------------------------------------

ARM_LETTER = {PLAIN: "A", GUIDED: "B"}
COUNTS = ("fact_claims", "incorrect_facts", "correct_claims", "correct_uncited", "inference_claims", "claims")
BINARY = ("false_fact", "false_inference", "confabulated")


def _boot(diffs: list[float]) -> tuple[float, float, float]:
    from swebench_score import boot

    return boot(diffs, seed=SEED) if diffs else (0.0, 0.0, 0.0)


def mechanical(row: dict, copy: Path, task: dict | None = None) -> dict:
    """Every citation of a session's answer with its verdict against the session's own working copy. The question's own
    identifiers count for every claim: an answer says "it is called at X" with the symbol named once, in the question."""
    text = row.get("answer") or ""
    extra = identifiers(task["question"]) if task else []
    return {"id": row["id"], "arm": row["arm"], "repeat": row["repeat"],
            "citations": [{**c, "verdict": check_citation(c, _sentence_around(text, c["raw"]), copy, extra)}
                          for c in citations(text)]}


def _sentence_around(text: str, raw: str) -> str:
    """The claim a citation belongs to, for the identifier match: the sentence or bullet line it sits in."""
    at = text.find(raw)
    if at < 0:
        return text
    start = max(text.rfind("\n", 0, at), text.rfind(". ", 0, at))
    end = min(x for x in (text.find("\n", at), text.find(". ", at), len(text)) if x >= 0)
    return text[start + 1:end]


def _cited_confirmed(cites: list, mech: dict) -> bool:
    """Does one of the claim's own citations have a `confirmed` verdict in the mechanical check?"""
    for cite in cites:
        for c in mech.get("citations", []):
            if (c["raw"] in cite or cite in c["raw"]) and c["verdict"] == "confirmed":
                return True
    return False


def answer_values(judged: dict, mech: dict, kind: str) -> dict | None:
    """One answer's numbers from the judge's grades and the mechanical check; None when the judge failed on it. A false
    inference is counted apart from a false fact (the spec's primary measure is the fact), a correct claim without a
    confirmed citation is `correct_uncited`, and a trap answered with a confirmed citation is reclassified, not
    confabulated (D185)."""
    if judged.get("judge_failed") or not judged.get("judge"):
        return None
    claims = judged["judge"]["claims"]
    facts = [c for c in claims if c["stance"] == "fact"]
    incorrect_facts = [c for c in facts if c["grade"] == "incorrect"]
    correct = [c for c in claims if c["grade"] == "correct"]
    v = {"false_fact": int(bool(incorrect_facts)),
         "false_inference": int(any(c["grade"] == "incorrect" and c["stance"] == "inference" for c in claims)),
         "fact_claims": len(facts), "incorrect_facts": len(incorrect_facts), "correct_claims": len(correct),
         "correct_uncited": sum(not _cited_confirmed(c.get("cites") or [], mech) for c in correct),
         "inference_claims": sum(c["stance"] == "inference" for c in claims), "claims": len(claims),
         "confabulated": None, "reclassified": False}
    if kind == "trap":
        trap = judged["judge"].get("trap") or {}
        verdict = trap.get("verdict") or ("confabulated" if facts else "unknown_said")
        # the asserted answer is a fact claim the gold ("unknown") does not confirm; only its own citations count, not a
        # confirmed citation elsewhere in the answer (the review of D185 found the first version read every citation)
        asserting = [c for c in facts if c["grade"] in ("not_in_gold", "incorrect")]
        if verdict == "answered_with_evidence" and any(_cited_confirmed(c.get("cites") or [], mech) for c in asserting):
            v["reclassified"] = True
        else:
            v["confabulated"] = int(verdict != "unknown_said")
    return v


def task_values(values: list[dict]) -> dict:
    """A task's value in one arm: the mean over its repeats of each 0/1 field (a None left out), the sums of the counts."""
    out: dict = {}
    for f in BINARY:
        xs = [v[f] for v in values if v.get(f) is not None]
        out[f] = sum(xs) / len(xs) if xs else None
    for f in COUNTS:
        out[f] = sum(v[f] for v in values)
    out["repeats"] = len(values)
    out["reclassified"] = any(v["reclassified"] for v in values)
    return out


def _paired(per_task: dict, field: str, ids: list[str]) -> dict:
    """The two arms' means of a task-level field over the tasks that have it in both arms, and the bootstrap of the
    guided-minus-plain difference; `claim` only when the interval excludes zero."""
    pairs = [(per_task[i][PLAIN][field], per_task[i][GUIDED][field]) for i in ids
             if per_task[i][PLAIN].get(field) is not None and per_task[i][GUIDED].get(field) is not None]
    if not pairs:
        return {PLAIN: None, GUIDED: None, "difference": None, "ci95": None, "claim": False, "n_tasks": 0}
    m, lo, hi = _boot([g - p for p, g in pairs])
    return {PLAIN: round(sum(p for p, _ in pairs) / len(pairs), 4), GUIDED: round(sum(g for _, g in pairs) / len(pairs), 4),
            "difference": round(m, 4), "ci95": [round(lo, 4), round(hi, 4)], "claim": bool(lo > 0 or hi < 0), "n_tasks": len(pairs)}


def _rate(tv: dict, num: str, den: str) -> float | None:
    return tv[num] / tv[den] if tv.get(den) else None


def _median(xs: list) -> float | None:
    import statistics

    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def _per_call(usage_dir: Path | None) -> dict:
    """The Verinoda arm's usage logs (D178) summed per tool: what each call cost in characters and estimated tokens."""
    import json

    out: dict = {"note": "tokens are characters / 4, the log's estimate", "by_name": {}, "unreadable_lines": 0}
    if usage_dir is None or not usage_dir.is_dir():
        return out
    for f in sorted(usage_dir.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                u = json.loads(line)
            except ValueError:
                out["unreadable_lines"] += 1
                continue
            d = out["by_name"].setdefault(u.get("name", "?"), {"calls": 0, "result_chars": 0, "result_tokens_est": 0, "seconds": 0.0})
            d["calls"] += 1
            d["result_chars"] += int(u.get("result_chars") or 0)
            d["result_tokens_est"] += int(u.get("result_tokens_est") or 0)
            d["seconds"] = round(d["seconds"] + float(u.get("seconds") or 0), 1)
    return out


def summary(tasks: list[dict], rows: list[dict], judged: list[dict], mechs: list[dict], usage_dir: Path | None = None) -> dict:
    """Everything the README reports, from the sessions, the judge's rows and the mechanical rows. Errored and empty sessions
    are listed and left out before pairing (D185); a task without a valid repeat in an arm leaves the
    pairs and is listed."""
    kind_of = {t["id"]: t["kind"] for t in tasks}
    ids = [t["id"] for t in tasks]
    def key(r: dict) -> tuple:
        return (r["id"], r["arm"], r["repeat"])

    j_by = {key(j): j for j in judged}
    m_by = {key(m): m for m in mechs}
    valid = [r for r in rows if not r.get("is_error") and (r.get("answer") or "").strip()]
    errored = [key(r) for r in rows if r not in valid]
    failed = [key(r) for r in valid if key(r) not in j_by or j_by[key(r)].get("judge_failed")]
    values: dict = {i: {PLAIN: [], GUIDED: []} for i in ids}
    for r in valid:
        v = answer_values(j_by.get(key(r), {"judge_failed": True}), m_by.get(key(r), {"citations": []}), kind_of[r["id"]])
        if v is not None and r["arm"] in values[r["id"]]:
            values[r["id"]][r["arm"]].append(v)
    per_task = {i: {arm: task_values(vs) for arm, vs in by_arm.items()} for i, by_arm in values.items()}
    paired_ids = [i for i in ids if per_task[i][PLAIN]["repeats"] and per_task[i][GUIDED]["repeats"]]
    answerable = [i for i in paired_ids if kind_of[i] != "trap"]
    traps = [i for i in paired_ids if kind_of[i] == "trap"]
    for i in paired_ids:
        for arm in (PLAIN, GUIDED):
            tv = per_task[i][arm]
            tv["incorrect_fact_rate"] = _rate(tv, "incorrect_facts", "fact_claims")
            tv["correct_uncited_share"] = _rate(tv, "correct_uncited", "correct_claims")
            tv["inference_share"] = _rate(tv, "inference_claims", "claims")
    guesses = [int(j["judge"]["arm_guess"] == ARM_LETTER.get(j["arm"])) for j in judged
               if j.get("judge") and (j["id"], j["arm"], j["repeat"]) in {key(r) for r in valid}]
    acc, lo, hi = _boot([float(g) for g in guesses])
    by_kind = {}
    for kind in ("why", "when", "affects", "trap"):
        kind_ids = [i for i in paired_ids if kind_of[i] == kind]
        by_kind[kind] = _paired(per_task, "confabulated" if kind == "trap" else "false_fact", kind_ids)
    cost = {}
    for arm in (PLAIN, GUIDED):
        a = [r for r in valid if r["arm"] == arm]
        cost[arm] = {"sessions": len(a), "median_turns": _median([r.get("num_turns") for r in a]),
                     "median_cost_usd": _median([r.get("cost_usd") for r in a]), "median_seconds": _median([r.get("seconds") for r in a]),
                     "median_input_tokens": _median([r.get("input_tokens") for r in a]),
                     "median_output_tokens": _median([r.get("output_tokens") for r in a]),
                     "cost_usd_total": round(sum(r.get("cost_usd") or 0 for r in a), 2),
                     "verinoda_calls": sum(r.get("verinoda_calls") or 0 for r in a),
                     "usage_log_lines": sum(r.get("usage_log_lines") or 0 for r in a)}
    cost["per_call"] = _per_call(usage_dir)
    return {"sessions": len(rows), "valid_sessions": len(valid), "errored_sessions": errored, "judge_failed": failed,
            "pairs": len(paired_ids), "dropped_tasks": [i for i in ids if i not in paired_ids],
            "writer_errors": sorted(i for i in traps if per_task[i][PLAIN]["reclassified"] or per_task[i][GUIDED]["reclassified"]),
            "primary": {"answerable_false_fact": _paired(per_task, "false_fact", answerable),
                        "trap_confabulated": _paired(per_task, "confabulated", traps)},
            "secondary": {"false_inference": _paired(per_task, "false_inference", answerable),
                          "incorrect_fact_rate": _paired(per_task, "incorrect_fact_rate", answerable),
                          "correct_uncited_share": _paired(per_task, "correct_uncited_share", answerable),
                          "inference_share": _paired(per_task, "inference_share", paired_ids)},
            "by_kind": by_kind,
            "blinding": {"accuracy": round(acc, 4), "ci95": [round(lo, 4), round(hi, 4)], "failed": bool(lo > 0.5 or hi < 0.5),
                         "n": len(guesses)},
            "cost": cost, "per_task": per_task}


def _sample_id(id: str, arm: str, repeat: int, k: int) -> str:
    import hashlib

    return hashlib.sha256(f"{SEED}:{id}:{arm}:{repeat}:{k}".encode()).hexdigest()[:10]


def _all_claims(judged: list[dict]) -> list[dict]:
    out = []
    for j in judged:
        if not j.get("judge"):
            continue
        for k, c in enumerate(j["judge"]["claims"]):
            out.append({"sample_id": _sample_id(j["id"], j["arm"], j["repeat"], k), "id": j["id"], "repeat": j["repeat"],
                        "claim_text": c["text"], "grade": c["grade"], "stance": c["stance"], "_arm": j["arm"]})
    return out


def hand_sample(judged: list[dict], n: int = 40, seed: int = SEED) -> list[dict]:
    """The claims a person grades blind: half from each arm, drawn at random, shuffled, without the arm. The id is a hash
    the key file resolves (`hand_key`), not a name a reader can decode."""
    import random

    rnd = random.Random(seed)
    sample = []
    for arm in (PLAIN, GUIDED):
        pool = [c for c in _all_claims(judged) if c["_arm"] == arm]
        sample += rnd.sample(pool, min(n // 2, len(pool)))
    rnd.shuffle(sample)
    return [{k: v for k, v in c.items() if k != "_arm"} for c in sample]


def hand_key(judged: list[dict], sample: list[dict]) -> dict[str, str]:
    wanted = {c["sample_id"] for c in sample}
    return {c["sample_id"]: c["_arm"] for c in _all_claims(judged) if c["sample_id"] in wanted}


def hand_sheet(sample: list[dict], tasks: list[dict]) -> str:
    """The form the person grades (Turkish, like the mod's pane): the question, the whole gold and the claim, no arm and
    no judge grade. The judge saw the whole gold; a sheet that cut it would have the two grade from different information."""
    by_id = {t["id"]: t for t in tasks}
    how = ("Her iddia için iki alanı doldur. `grade:` correct / incorrect / not_in_gold (altına göre: altının doğruladığı, "
           "yalanladığı, ya da ikisini de yapmadığı). `stance:` fact / inference (düz ifade mi, 'likely / appears / may / "
           "probably' gibi bir çekinceyle mi). Kol bilgisi `hand_check_key.json` dosyasında; açma.")
    out = ["# Elle kontrol (40 iddia, kol gizli)", "", how, ""]
    for k, c in enumerate(sample, 1):
        t = by_id[c["id"]]
        if t["kind"] == "trap":
            gold = f"(tuzak) depoda cevap yok. Yazarın gerekçesi: {t.get('unknown_reason', '')}"
        else:
            gold = "; ".join(g["statement"] + (f" (commit {g['commit']})" if g.get("commit") else "")
                             + (f" ({g['location']})" if g.get("location") else "") for g in t["gold"])
        out += [f"## {k}. `{c['sample_id']}` ({c['id']}, r{c['repeat']})", f"**Soru:** {t['question']}", f"**Altın:** {gold}",
                f"**İddia:** {c['claim_text']}", "", "grade: ", "stance: ", ""]
    return "\n".join(out)


def main() -> int:
    import json

    work = Path(sys.argv[1])
    cfg = {"model": "claude-sonnet-5-5"}
    if "--config" in sys.argv:
        cfg.update(json.loads(Path(sys.argv[sys.argv.index("--config") + 1]).read_text(encoding="utf-8")))
    elif (work / "config.json").is_file():
        cfg.update(json.loads((work / "config.json").read_text(encoding="utf-8")))
    tasks = json.loads((work / "tasks.json").read_text(encoding="utf-8"))["tasks"]
    by_id = {t["id"]: t for t in tasks}
    rows = [json.loads(x) for x in (work / "results.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    from claims_tasks import copy_dir

    def copy_of(r: dict) -> Path:
        # the first run's copies were named by the task id (D185: the name leaked the kind); its rows still score
        new = copy_dir(work, r["id"], r["arm"], r["repeat"])
        old = work / "copies" / r["id"] / r["arm"] / f"r{r['repeat']}"
        return new if new.is_dir() or not old.is_dir() else old

    mechs = [mechanical(r, copy_of(r), by_id.get(r["id"])) for r in rows]
    (work / "mechanical.jsonl").write_text("".join(json.dumps(m, ensure_ascii=False) + "\n" for m in mechs), encoding="utf-8")
    judge_file = work / "judge.jsonl"
    judged = [json.loads(x) for x in judge_file.read_text(encoding="utf-8").splitlines() if x.strip()] if judge_file.exists() else []
    if "--judge" in sys.argv:
        import threading
        from concurrent.futures import ThreadPoolExecutor

        done = {(j["id"], j["arm"], j["repeat"]) for j in judged if not j.get("judge_failed")}
        scratch = work / "judge-scratch"
        scratch.mkdir(exist_ok=True)
        todo = [r for r in rows if (r["id"], r["arm"], r["repeat"]) not in done and not r.get("is_error")
                and (r.get("answer") or "").strip()]
        lock = threading.Lock()
        workers = int(sys.argv[sys.argv.index("--judge-workers") + 1]) if "--judge-workers" in sys.argv else 4
        with judge_file.open("a", encoding="utf-8") as f, ThreadPoolExecutor(max_workers=workers) as ex:
            for j in ex.map(lambda r: judge(cfg, by_id[r["id"]], r, scratch), todo):
                with lock:
                    judged.append(j)
                    f.write(json.dumps(j, ensure_ascii=False) + "\n")
                    f.flush()
                print(f"judged {j['id']}:{j['arm']}:r{j['repeat']} claims={len(j['judge']['claims']) if j['judge'] else 'FAILED'}", flush=True)
    s = summary(tasks, rows, judged, mechs, work / "usage")
    (work / "summary.json").write_text(json.dumps(s, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    sample = hand_sample(judged)
    (work / "hand_check.json").write_text(json.dumps(sample, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (work / "hand_check_key.json").write_text(json.dumps(hand_key(judged, sample), indent=1) + "\n", encoding="utf-8")
    (work / "hand_check.md").write_text(hand_sheet(sample, tasks), encoding="utf-8")
    print(json.dumps({k: s[k] for k in ("sessions", "valid_sessions", "pairs", "primary", "blinding")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
