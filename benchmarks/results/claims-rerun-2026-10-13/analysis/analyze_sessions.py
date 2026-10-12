"""Per-session and per-arm analysis of the D186 verification sessions (plan Task 8, step 4), from the session transcripts.

    python analyze_sessions.py WORK_DIR [--out analysis.json] [--repo REPO_ROOT]

Reads WORK/results.jsonl (one row per session), WORK/tasks.json, WORK/judge.jsonl and WORK/mechanical-strict.jsonl when they
exist, and each session's transcript (~/.claude/projects/*/<session_id>.jsonl). Writes one JSON file with

* ``per_session``: the tool-call sequence, the Verinoda calls, the number of model calls (assistant messages that carry usage,
  one per message id), the summed token fields, the characters of Verinoda tool results and of the agent's own tool results,
  for a Verinoda call to ``analyze`` its ``leads`` and where the task's gold file and gold commit sit in them, and whether the
  gold commit is in the answer;
* ``per_arm``: means and medians over the 24-task cost sample (repeat 1, both arms) and over all valid sessions;
* ``paired_cost_sample``: the paired (Verinoda minus plain) differences of dollars, model calls, own-tool model calls and
  token fields over the 24 pairs, each with a 10,000-resample bootstrap 95 % interval (seed 20261013, the percentile rule of
  swebench_score.boot);
* ``six_tasks``: the re-run's 18 sessions, one row each;
* ``verinoda_arm``: which tools the Verinoda arm called, what came first, the characters of Verinoda output per session and per
  ``analyze`` call, and where the gold file and the gold commit sit in the ``analyze`` results;
* ``cold_cache``, ``paired_cost_sample_without_first_sessions``, ``pairs_by_analyze_call``: checks on the paired dollars;
* ``citations`` (lenient and strict check per arm) and ``judge`` (judge rows, claims and trap verdicts per arm).

Nothing here is a measured file of an earlier run; it only reads. A number that cannot be computed (no analyze call, no
transcript) is ``null`` with the reason in ``notes``, never 0.
"""

from __future__ import annotations

import json
import random
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

PLAIN, GUIDED = "none", "verinoda_guided"
SEED = 20261013
N_BOOT = 10_000
OWN_TOOLS = ("Bash", "Read", "Grep", "Glob")
SIX = ["fastapi__full-stack-fastapi-template-why-1", "junegunn__fzf-why-1", "guzzle__guzzle-trap-1", "gin-gonic__gin-trap-1",
       "axios__axios-when-1", "sharkdp__bat-when-1"]
USAGE_FIELDS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
# the oldest commit named in each trap's ``unknown_reason`` (claims_tasks.json): gin "arrived in the initial commit 15216a0", guzzle
# "the oldest commit is 91f1e347"
TRAP_ORIGIN = {"gin-gonic__gin-trap-1": "15216a0", "guzzle__guzzle-trap-1": "91f1e347"}
HASH = re.compile(r"\b[0-9a-f]{7,40}\b")
MENTION = re.compile(r"verinoda|analyze|mcp__", re.IGNORECASE)

# Candidate sentences for the hand reading of the six tasks' answers; the regexes only find, a person reads.
ABSENCE = [r"\bno (such |recorded |documented |stated |explicit |written |known )?(change|commit|rationale|reason|explanation|"
           r"justification|comment|docstring|message|record|mention|history|evidence|note|discussion)s?\b",
           r"\b(does|do|did) not (give|state|say|explain|record|document|mention|contain|provide|hold|carry)\b",
           r"\b(doesn't|don't|didn't) (give|state|say|explain|record|document|mention|contain|provide|hold|carry)\b",
           r"\bnone of (these|those|the) (commits|messages)\b", r"\bnothing (in|that|records|explains|states|says|else)\b",
           r"\b(found|find|saw|see) (no|nothing|none)\b", r"\b(not|n't) (find|found)\b", r"\bnever (explain|state|say|document|mention|record)",
           r"\bnot (documented|explained|recorded|stated|mentioned|given|stated)\b", r"\bunknown\b", r"\bnot present\b",
           r"\bno answer\b", r"\bdoes not hold\b"]
FIRST = [r"\bfirst (appears|appeared|introduced|added|present|seen|shows|show)\b", r"\b(introduced|added|created|originated) (in|by|with|at)\b",
         r"\boldest\b", r"\bearliest\b", r"\bpredates?\b", r"\bgoes back\b", r"\bnewest\b", r"\bearlier\b"]


# -- transcripts -----------------------------------------------------------------------------------------------------------

def find_transcript(session_id: str) -> Path | None:
    hits = list((Path.home() / ".claude" / "projects").glob(f"*/{session_id}.jsonl")) if session_id else []
    return hits[0] if hits else None


def result_chars(content) -> int:
    """The characters of one tool_result as the model received them: a string's length, or the text of its blocks."""
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return sum(len(b.get("text") or "") if isinstance(b, dict) and b.get("type") == "text" else len(json.dumps(b, ensure_ascii=False))
                   for b in content)
    return len(json.dumps(content, ensure_ascii=False)) if content is not None else 0


def result_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text") or "" for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def parse_transcript(path: Path) -> dict:
    """What a transcript shows: per assistant message id the usage (the largest of each field over its entries: a message is
    written once per content block), its tool_use blocks, and per tool_use id the result."""
    msgs: dict[str, dict] = {}
    names: dict[str, str] = {}
    inputs: dict[str, dict] = {}
    results: dict[str, dict] = {}
    sequence: list[str] = []
    texts: list[tuple[str, str]] = []
    cost_state = None
    atts: list[dict] = []
    stamps: list[str] = []
    for n, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines()):
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("timestamp"):
            stamps.append(e["timestamp"])
        if e.get("type") == "cost-state":
            cost_state = e
        if isinstance(e.get("attachment"), dict):
            atts.append(e["attachment"])
        m = e.get("message") or {}
        c = m.get("content")
        if m.get("role") == "assistant" and m.get("model") != "<synthetic>":
            mid = m.get("id") or e.get("uuid") or f"line{n}"
            rec = msgs.setdefault(mid, {"usage": dict.fromkeys(USAGE_FIELDS, 0), "has_usage": False, "tool_uses": [], "order": n})
            u = m.get("usage") or {}
            if u:
                rec["has_usage"] = True
            for k in USAGE_FIELDS:
                rec["usage"][k] = max(rec["usage"][k], int(u.get(k) or 0))
            for x in c if isinstance(c, list) else []:
                kind = x.get("type")
                if kind == "tool_use":
                    names[x["id"]] = x["name"]
                    inputs[x["id"]] = x.get("input") or {}
                    rec["tool_uses"].append(x["id"])
                    sequence.append(x["name"])
                elif kind in ("text", "thinking"):
                    texts.append((kind, x.get("text") if kind == "text" else x.get("thinking") or ""))
        elif m.get("role") == "user" and isinstance(c, list):
            for x in c:
                if x.get("type") == "tool_result":
                    results[x.get("tool_use_id")] = {"chars": result_chars(x.get("content")), "text": result_text(x.get("content")),
                                                     "is_error": bool(x.get("is_error"))}
    return {"msgs": msgs, "names": names, "inputs": inputs, "results": results, "sequence": sequence, "texts": texts,
            "cost_state": cost_state, "attachments": atts, "ts_first": min(stamps) if stamps else None,
            "ts_last": max(stamps) if stamps else None}


# the two wordings of the mod's call rule: the one of 68b2133 (zero-call run) and the one of 380e6a0 on (the re-run)
RULE_PHRASES = {"old (68b2133)": "call `mcp__verinoda__analyze` once", "new (380e6a0 on)": "Your first tool call on a question that asks why"}
RULE_PHRASE = RULE_PHRASES["old (68b2133)"]


def setup_facts(atts: list[dict]) -> dict:
    """What the session's context held, from the attachments the engine recorded before and at the first request: the call rule
    in the system prompt, the server's instructions, and the deferred-tools list (rendered before the mod's tool.describe pin)."""
    snaps = [a for a in atts if a.get("type") == "prompt_snapshot"]
    deferred = [n for a in atts if a.get("type") == "deferred_tools_delta" for n in a.get("addedNames") or []]
    blob = json.dumps([a.get("systemPrompt") for a in snaps], ensure_ascii=False)
    kinds = [k for k, phrase in RULE_PHRASES.items() if phrase in blob]
    return {"rule_in_system_prompt": bool(kinds), "rule_wording": kinds[0] if len(kinds) == 1 else (kinds or None),
            "prompt_snapshots": len(snaps),
            "mcp_instructions_present": any("verinoda" in "".join(a.get("addedNames") or []) for a in atts if a.get("type") == "mcp_instructions_delta"),
            "deferred_delta_names_verinoda_tools": sorted(n for n in deferred if n.startswith("mcp__verinoda__")),
            "deferred_delta_total": len(deferred)}


def short_args(inp: dict, limit: int = 160) -> str:
    return json.dumps(inp, ensure_ascii=False)[:limit]


# -- gold ------------------------------------------------------------------------------------------------------------------

def gold_files(task: dict) -> list[str]:
    out = []
    for g in task.get("gold") or []:
        loc = g.get("location")
        if loc:
            p = re.sub(r":\d+(-\d+)?$", "", loc)
            if p not in out:
                out.append(p)
    return out


def gold_commits(task: dict) -> list[str]:
    return [g["commit"].lower() for g in task.get("gold") or [] if g.get("commit")]


def commit_tokens(text: str) -> list[str]:
    return [t for t in HASH.findall(text.lower()) if not t.isdigit()]


def commit_match(token: str, full: str) -> bool:
    return len(token) >= 7 and (full.startswith(token) or token.startswith(full))


def commits_in(text: str, commits: list[str]) -> list[str]:
    toks = commit_tokens(text)
    return [c for c in commits if any(commit_match(t, c) for t in toks)]


def reason_commits(task: dict) -> list[str]:
    """A trap has no gold commit; the writer's reason names the commits it checked."""
    return list(dict.fromkeys(re.findall(r"\b[0-9a-f]{7,8}\b", task.get("unknown_reason") or "")))


# -- one session ------------------------------------------------------------------------------------------------------------

def analyze_result(text: str, task: dict) -> dict:
    """An ``analyze`` result (the lean view: leads, unknowns, facts, context ...) against the task's gold."""
    try:
        res = json.loads(text)
    except ValueError:
        return {"parsed": False, "leads": None}
    leads = [x for x in res.get("leads") or [] if isinstance(x, str)]
    files, commits = gold_files(task), gold_commits(task)

    def rank_of(pred) -> int | None:
        for i, ln in enumerate(leads, 1):
            if pred(ln):
                return i
        return None

    file_ranks = {f: rank_of(lambda ln, f=f: ln.split("  ")[0].split(":")[0] == f) for f in files}
    commit_ranks = {c: rank_of(lambda ln, c=c: bool(commits_in(ln, [c]))) for c in commits}
    whole = json.dumps({k: v for k, v in res.items() if k != "leads"}, ensure_ascii=False)
    return {"parsed": True, "status": res.get("status"), "n_leads": len(leads), "leads": leads, "gold_file_rank": file_ranks,
            "gold_commit_rank_in_leads": commit_ranks,
            "gold_commit_elsewhere_in_result": {c: bool(commits_in(whole, [c])) for c in commits},
            "result_chars": len(text), "keys": sorted(res)}


def sentences(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        for s in re.split(r"(?<=[.!?])\s+(?=[A-Z`*\"(])", line):
            if s.strip():
                out.append(s.strip())
    return out


def candidate_sentences(answer: str) -> dict:
    a = [re.compile(p, re.IGNORECASE) for p in ABSENCE]
    f = [re.compile(p, re.IGNORECASE) for p in FIRST]
    return {"absence": [s for s in sentences(answer) if any(p.search(s) for p in a)],
            "origin": [s for s in sentences(answer) if any(p.search(s) for p in f)]}


def analyze_session(row: dict, task: dict, judged: dict | None, strict: dict | None, usage_dir: Path | None = None) -> dict:
    out: dict = {"id": row["id"], "arm": row["arm"], "repeat": row["repeat"], "kind": row["kind"], "session_id": row.get("session_id"),
                 "is_error": bool(row.get("is_error")), "subtype": row.get("subtype"), "cost_usd": row.get("cost_usd"),
                 "num_turns": row.get("num_turns"), "seconds": row.get("seconds"), "answer_chars": len(row.get("answer") or ""),
                 "notes": []}
    tp = find_transcript(row.get("session_id") or "")
    out["transcript"] = str(tp) if tp else None
    if tp is None:
        out["notes"].append("no transcript: nothing below the first block can be computed")
        return out
    t = parse_transcript(tp)
    msgs = {k: v for k, v in t["msgs"].items() if v["has_usage"]}
    sums = {k: sum(v["usage"][k] for v in msgs.values()) for k in USAGE_FIELDS}
    ordered = sorted(msgs.values(), key=lambda v: v["order"])
    first_use = ordered[0]["usage"] if ordered else {}
    seq = t["sequence"]
    first_own = next((i for i, n in enumerate(seq) if n in OWN_TOOLS), None)
    first_analyze = next((i for i, n in enumerate(seq) if n == "mcp__verinoda__analyze"), None)
    out.update({"ts_first": t["ts_first"], "ts_last": t["ts_last"], "first_tool": seq[0] if seq else None,
                "analyze_first": bool(seq) and seq[0] == "mcp__verinoda__analyze",
                "analyze_before_any_own_tool": first_analyze is not None and (first_own is None or first_analyze < first_own),
                "first_call_cache_write": first_use.get("cache_creation_input_tokens"),
                "first_call_cache_read": first_use.get("cache_read_input_tokens")})
    own_msgs = [v for v in msgs.values() if any(t["names"][i] in OWN_TOOLS for i in v["tool_uses"])]
    search_only = [v for v in own_msgs if all(t["names"][i] in ("Grep", "Glob") for i in v["tool_uses"])]
    verinoda_ids = [i for i, n in t["names"].items() if n.startswith("mcp__verinoda__")]
    own_ids = [i for i, n in t["names"].items() if n in OWN_TOOLS]
    search_ids = [i for i, n in t["names"].items() if n == "ToolSearch"]
    out.update({
        "tool_sequence": t["sequence"], "n_tool_calls": len(t["sequence"]),
        "verinoda_calls": [{"tool": t["names"][i], "args": short_args(t["inputs"][i]),
                            "result_chars": (t["results"].get(i) or {}).get("chars"), "is_error": (t["results"].get(i) or {}).get("is_error")}
                           for i in verinoda_ids],
        "n_verinoda_calls": len(verinoda_ids), "n_toolsearch_calls": len(search_ids),
        "model_calls": len(msgs), "own_tool_model_calls": len(own_msgs), "search_only_model_calls": len(search_only),
        "tokens": {"uncached_input": sums["input_tokens"], "cache_write": sums["cache_creation_input_tokens"],
                   "cache_read": sums["cache_read_input_tokens"], "output": sums["output_tokens"]},
        "verinoda_result_chars": sum((t["results"].get(i) or {}).get("chars", 0) for i in verinoda_ids),
        "own_result_chars": sum((t["results"].get(i) or {}).get("chars", 0) for i in own_ids),
        "toolsearch_result_chars": sum((t["results"].get(i) or {}).get("chars", 0) for i in search_ids),
    })
    # the transcript's usage must equal the result JSON's: the harness stored the sum of the three input fields and the output
    in_sum = sums["input_tokens"] + sums["cache_creation_input_tokens"] + sums["cache_read_input_tokens"]
    out["usage_matches_result_json"] = (in_sum == row.get("input_tokens") and sums["output_tokens"] == row.get("output_tokens"))
    cs = (t["cost_state"] or {}).get("totalCostUSD")
    out["cost_state_usd"] = cs
    out["setup"] = setup_facts(t["attachments"])
    log = usage_dir / f"{row['id']}-{row['arm']}-r{row['repeat']}.jsonl" if usage_dir else None
    if log is not None and log.is_file():
        names_in_log: dict[str, int] = {}
        agent_calls: list[dict] = []
        for ln in log.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                rec = json.loads(ln)
            except ValueError:
                continue
            nm = rec.get("name", "?")
            names_in_log[nm] = names_in_log.get(nm, 0) + 1
            if rec.get("surface") == "mcp" or nm in ("analyze", "project_query", "run_tool", "code_check", "index_update"):
                agent_calls.append({"name": nm, "result_chars": rec.get("result_chars"), "seconds": rec.get("seconds")})
        out["usage_log_names"] = names_in_log
        out["usage_log_tool_calls"] = agent_calls
    # the model's own words about the tool: any assistant text or thinking block that names it
    out["mentions_in_assistant_blocks"] = [(k, s[:240]) for k, s in t["texts"] if s and MENTION.search(s)]
    out["thinking_blocks"] = sum(k == "thinking" for k, _ in t["texts"])
    out["thinking_blocks_nonempty"] = sum(k == "thinking" and bool(s.strip()) for k, s in t["texts"])
    # Verinoda-arm gold checks
    answer = row.get("answer") or ""
    gc, gf = gold_commits(task), gold_files(task)
    out["gold_commits"], out["gold_files"] = gc, gf
    out["answer_names_gold_commit"] = commits_in(answer, gc) if gc else None
    if judged and judged.get("judge"):
        cites = " ".join(c for cl in judged["judge"]["claims"] for c in cl.get("cites") or [])
        out["gold_commit_in_claim_cites"] = commits_in(cites, gc) if gc else None
    else:
        out["gold_commit_in_claim_cites"] = None
    out["answer_names_gold_file"] = [f for f in gf if f in answer or f.split("/")[-1] in answer] if gf else None
    if task["kind"] == "trap":
        out["trap_reason_commits_named_in_answer"] = commits_in(answer, reason_commits(task))
    analyze_calls = [i for i in verinoda_ids if t["names"][i] == "mcp__verinoda__analyze"]
    if row["arm"] == GUIDED:
        if analyze_calls:
            out["analyze"] = [{**analyze_result((t["results"].get(i) or {}).get("text", ""), task), "args": short_args(t["inputs"][i])}
                              for i in analyze_calls]
        else:
            out["analyze"] = None
            out["notes"].append("no analyze call: no leads list, so the gold file's and the gold commit's rank in it cannot be computed")
        whole = "\n".join((t["results"].get(i) or {}).get("text", "") for i in verinoda_ids)
        out["gold_commit_in_any_verinoda_result"] = commits_in(whole, gc) if (gc and verinoda_ids) else (None if not verinoda_ids else [])
        origin = TRAP_ORIGIN.get(row["id"])
        if origin:  # a trap has no gold commit; the oldest commit of its writer's reason is the one a "first appears in" claim should name
            out["trap_origin_commit"] = origin
            out["verinoda_results_name_trap_origin"] = bool(commits_in(whole, [origin])) if verinoda_ids else None
            out["answer_names_trap_origin"] = bool(commits_in(answer, [origin]))
    out.update({"candidates": candidate_sentences(answer)})
    if judged:
        j = judged.get("judge")
        out["judge"] = None if not j else {"claims": len(j["claims"]), "arm_guess": j["arm_guess"], "trap": j.get("trap"),
                                          "incorrect": [{"text": c["text"], "stance": c["stance"]} for c in j["claims"]
                                                        if c["grade"] == "incorrect"],
                                          "facts": sum(c["stance"] == "fact" for c in j["claims"]),
                                          "inference": sum(c["stance"] == "inference" for c in j["claims"])}
        out["judge_failed"] = bool(judged.get("judge_failed"))
    if strict:
        v = [c["verdict"] for c in strict["citations"]]
        out["strict_citations"] = {k: v.count(k) for k in ("confirmed", "wrong", "missing", "not_repo")} | {"total": len(v)}
    return out


# -- statistics ------------------------------------------------------------------------------------------------------------

def boot(diffs: list[float], n: int = N_BOOT, seed: int = SEED) -> tuple[float, float, float]:
    """The mean and its percentile bootstrap 95 % interval (swebench_score.boot's rule: sorted means, indices 2.5 % and 97.5 %)."""
    rnd = random.Random(seed)
    k = len(diffs)
    means = sorted(sum(rnd.choices(diffs, k=k)) / k for _ in range(n))
    return sum(diffs) / k, means[int(0.025 * n)], means[int(0.975 * n)]


def central(xs: list[float]) -> dict:
    xs = [x for x in xs if x is not None]
    if not xs:
        return {"n": 0, "mean": None, "median": None, "min": None, "max": None}
    return {"n": len(xs), "mean": sum(xs) / len(xs), "median": statistics.median(xs), "min": min(xs), "max": max(xs)}


METRICS = {"cost_usd": lambda s: s.get("cost_usd"), "model_calls": lambda s: s.get("model_calls"),
           "own_tool_model_calls": lambda s: s.get("own_tool_model_calls"), "n_tool_calls": lambda s: s.get("n_tool_calls"),
           "num_turns": lambda s: s.get("num_turns"),
           "cache_write_tokens": lambda s: (s.get("tokens") or {}).get("cache_write"),
           "cache_read_tokens": lambda s: (s.get("tokens") or {}).get("cache_read"),
           "uncached_input_tokens": lambda s: (s.get("tokens") or {}).get("uncached_input"),
           "output_tokens": lambda s: (s.get("tokens") or {}).get("output"),
           "verinoda_result_chars": lambda s: s.get("verinoda_result_chars"),
           "n_verinoda_calls": lambda s: s.get("n_verinoda_calls"),
           "first_call_cache_write_tokens": lambda s: s.get("first_call_cache_write"),
           "own_result_chars": lambda s: s.get("own_result_chars"), "answer_chars": lambda s: s.get("answer_chars"),
           "seconds": lambda s: s.get("seconds")}


def per_arm(sessions: list[dict]) -> dict:
    return {arm: {m: central([f(s) for s in sessions if s["arm"] == arm and not s["is_error"]]) for m, f in METRICS.items()}
            | {"sessions": sum(s["arm"] == arm and not s["is_error"] for s in sessions),
               "sessions_with_a_verinoda_call": sum(s["arm"] == arm and (s.get("n_verinoda_calls") or 0) > 0 for s in sessions)}
            for arm in (PLAIN, GUIDED)}


def paired(pairs: list[tuple[dict, dict]]) -> dict:
    out: dict = {"n_pairs": len(pairs), "seed": SEED, "resamples": N_BOOT}
    for m, f in METRICS.items():
        d = [f(g) - f(p) for p, g in pairs if f(p) is not None and f(g) is not None]
        if not d:
            continue
        mean, lo, hi = boot(d)
        out[m] = {"plain_mean": sum(f(p) for p, _ in pairs) / len(pairs), "verinoda_mean": sum(f(g) for _, g in pairs) / len(pairs),
                  "mean_difference": mean, "ci95": [lo, hi], "pairs_where_verinoda_is_higher": sum(x > 0 for x in d),
                  "pairs_equal": sum(x == 0 for x in d), "n": len(d)}
    return out


# the price tables of the design (docs/drafts/2026-10-12-verinoda-lean-design.md section 2), dollars per million tokens: uncached input,
# cache write, cache read, output; the D185 run fitted the second
PRICES = {"2 / 4 / 0.20 / 10": (2.0, 4.0, 0.20, 10.0), "2 / 4 / 0.10 / 10": (2.0, 4.0, 0.10, 10.0)}
COMPONENTS = ("uncached_input", "cache_write", "cache_read", "output")


def priced(s: dict, table: tuple) -> dict:
    t = s["tokens"]
    parts = {c: t[c] * p / 1e6 for c, p in zip(COMPONENTS, table)}
    return {**parts, "total": sum(parts.values())}


def price_fit(sessions: list[dict], pairs: list[tuple[dict, dict]]) -> dict:
    """How well a price table reproduces the CLI's reported dollars from the transcript's token fields, and, for the table that fits
    best, the paired difference split into its four components (derived numbers: the CLI's own ``cost_usd`` is the measure)."""
    ok = [s for s in sessions if s.get("tokens") and s.get("cost_usd") is not None and not s["is_error"]]
    fit = {}
    for name, tab in PRICES.items():
        res = [priced(s, tab)["total"] - s["cost_usd"] for s in ok]
        fit[name] = {"n": len(res), "max_abs_residual_usd": max(abs(x) for x in res), "mean_residual_usd": sum(res) / len(res)}
    best = min(fit, key=lambda k: fit[k]["max_abs_residual_usd"])
    comp = {}
    if pairs:
        for c in (*COMPONENTS, "total"):
            d = [priced(g, PRICES[best])[c] - priced(p, PRICES[best])[c] for p, g in pairs]
            comp[c] = sum(d) / len(d)
    return {"tables": fit, "best_table": best, "paired_difference_by_component_usd": comp}


def verinoda_arm(sessions: list[dict]) -> dict:
    """The Verinoda arm's use of the tools: which sessions called which tool, what came first, how much Verinoda output the model
    received, and, for the sessions that called ``analyze``, where the task's gold file and gold commit sit in its result."""
    g = [s for s in sessions if s["arm"] == GUIDED and not s["is_error"]]
    calls = Counter(c["tool"].removeprefix("mcp__verinoda__") for s in g for c in s.get("verinoda_calls") or [])
    inner = Counter()
    for s in g:
        for c in s.get("verinoda_calls") or []:
            if c["tool"] == "mcp__verinoda__run_tool":
                m = re.search(r'"name":\s*"(\w+)"', c["args"])
                inner[m.group(1) if m else "?"] += 1
    chars = [s.get("verinoda_result_chars") for s in g]
    analyze_chars = [a["result_chars"] for s in g for a in s.get("analyze") or [] if a.get("result_chars")]
    detail = []
    for s in g:
        if not s.get("analyze"):
            continue
        gf, gc = s.get("gold_files") or [], s.get("gold_commits") or []

        def best(key: str) -> int | None:
            ranks = [r for a in s["analyze"] for r in (a.get(key) or {}).values() if r is not None]
            return min(ranks) if ranks else None

        detail.append({"id": s["id"], "repeat": s["repeat"], "kind": s["kind"], "analyze_calls": len(s["analyze"]),
                       "n_leads": [a.get("n_leads") for a in s["analyze"]], "result_chars": [a.get("result_chars") for a in s["analyze"]],
                       "gold_files": gf, "gold_file_best_rank_in_leads": best("gold_file_rank") if gf else "no gold file",
                       "gold_commits": gc, "gold_commit_best_rank_in_leads": best("gold_commit_rank_in_leads") if gc else "no gold commit",
                       "gold_commit_elsewhere_in_analyze_result": (any(v for a in s["analyze"] for v in (a.get("gold_commit_elsewhere_in_result") or {}).values())
                                                                   if gc else None),
                       "gold_commit_in_any_verinoda_result": bool(s.get("gold_commit_in_any_verinoda_result")) if gc else None,
                       "answer_names_gold_commit": bool(s.get("answer_names_gold_commit")) if gc else None})
    with_gf = [d for d in detail if d["gold_files"]]
    with_gc = [d for d in detail if d["gold_commits"]]
    return {
        "sessions": len(g), "with_a_verinoda_call": sum(bool(s.get("n_verinoda_calls")) for s in g),
        "with_an_analyze_call": sum(bool(s.get("analyze")) for s in g),
        "analyze_was_the_first_tool": sum(bool(s.get("analyze_first")) for s in g),
        "analyze_before_any_own_tool": sum(bool(s.get("analyze_before_any_own_tool")) for s in g),
        "first_tool": dict(Counter(s.get("first_tool") for s in g)), "calls_by_tool": dict(calls), "run_tool_by_inner_name": dict(inner),
        "analyze_calls_per_session": dict(Counter(len(s.get("analyze") or []) for s in g)),
        "toolsearch_calls": sum(s.get("n_toolsearch_calls") or 0 for s in g),
        "verinoda_result_chars_per_session": central(chars), "analyze_result_chars_per_call": central(analyze_chars),
        "sessions_over_4500_chars": [[s["id"], s["repeat"], s["verinoda_result_chars"]] for s in g if (s.get("verinoda_result_chars") or 0) > 4500],
        "by_kind": {k: {"sessions": sum(s["kind"] == k for s in g), "with_an_analyze_call": sum(s["kind"] == k and bool(s.get("analyze")) for s in g)}
                    for k in ("why", "when", "affects", "trap")},
        "gold": {"sessions_with_analyze_and_a_gold_file": len(with_gf),
                 "gold_file_in_leads": sum(d["gold_file_best_rank_in_leads"] is not None for d in with_gf),
                 "gold_file_best_rank_1": sum(d["gold_file_best_rank_in_leads"] == 1 for d in with_gf),
                 "sessions_with_analyze_and_a_gold_commit": len(with_gc),
                 "gold_commit_in_leads": sum(d["gold_commit_best_rank_in_leads"] is not None for d in with_gc),
                 "gold_commit_anywhere_in_analyze_result": sum(bool(d["gold_commit_elsewhere_in_analyze_result"]) for d in with_gc),
                 "gold_commit_in_any_verinoda_result": sum(bool(d["gold_commit_in_any_verinoda_result"]) for d in with_gc),
                 "answer_names_gold_commit": sum(bool(d["answer_names_gold_commit"]) for d in with_gc)},
        "gold_detail": detail}


def cold_first_sessions(sessions: list[dict], k: int = 1) -> list[dict]:
    out = []
    for arm in (PLAIN, GUIDED):
        a = sorted((s for s in sessions if s["arm"] == arm and s.get("ts_first") and not s["is_error"]), key=lambda s: s["ts_first"])
        out += a[:k]
    return out


def cold_cache(sessions: list[dict]) -> dict:
    """The first three sessions of each arm in time order against the rest: a cold prompt cache shows in the first call's cache write
    and in the dollars of the first session."""
    out: dict = {}
    for arm in (PLAIN, GUIDED):
        a = sorted((s for s in sessions if s["arm"] == arm and s.get("ts_first") and not s["is_error"]), key=lambda s: s["ts_first"])
        rest = a[3:]

        def med(key: str):
            xs = [s.get(key) for s in rest if s.get(key) is not None]
            return statistics.median(xs) if xs else None

        out[arm] = {"sessions": len(a), "first_three": [{k: s.get(k) for k in ("id", "repeat", "ts_first", "cost_usd", "first_call_cache_write",
                                                                                "first_call_cache_read", "model_calls")} for s in a[:3]],
                    "median_of_the_rest": {k: med(k) for k in ("cost_usd", "first_call_cache_write", "first_call_cache_read", "model_calls")}}
    return out


def citation_rates(work: Path, sample_ids: list[str]) -> dict:
    """Citation verdicts per arm from claims_score's lenient check (mechanical.jsonl) and the strict check (mechanical-strict.jsonl)."""
    out: dict = {}
    sets = {"all_sessions": lambda m: True, "cost_sample_repeat1": lambda m: m["id"] in sample_ids and m["repeat"] == 1,
            "rerun_six_verinoda_arm": lambda m: m["id"] in SIX and m["arm"] == GUIDED}
    for name in ("mechanical", "mechanical-strict"):
        p = work / f"{name}.jsonl"
        if not p.exists():
            continue
        ms = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
        out[name] = {}
        for label, pred in sets.items():
            by: dict[str, Counter] = {}
            for m in ms:
                if not pred(m):
                    continue
                d = by.setdefault(m["arm"], Counter())
                d["answers"] += 1
                for c in m["citations"]:
                    d["citations"] += 1
                    d[c["verdict"]] += 1
                    d[f"{c['kind']}:{c['verdict']}"] += 1
                    d[f"{c['kind']}:total"] += 1
            out[name][label] = {arm: {**dict(d), "confirmed_share": (d["confirmed"] / d["citations"]) if d["citations"] else None,
                                      "location_confirmed_share": (d["location:confirmed"] / d["location:total"]) if d["location:total"] else None,
                                      "commit_confirmed_share": (d["commit:confirmed"] / d["commit:total"]) if d["commit:total"] else None}
                                for arm, d in by.items()}
    return out


ARM_LETTER = {PLAIN: "A", GUIDED: "B"}


def judge_counts(judge_rows: list[dict], result_rows: list[dict]) -> dict:
    """The blind judge's rows per arm: parsed or failed, answers with an incorrect claim, the claims by grade, the trap verdicts and
    how often the judge guessed the arm right."""
    valid = Counter(r["arm"] for r in result_rows if not r.get("is_error") and (r.get("answer") or "").strip())
    out: dict = {}
    for arm in (PLAIN, GUIDED):
        js = [j for j in judge_rows if j["arm"] == arm]
        ok = [j for j in js if not j.get("judge_failed") and j.get("judge")]
        claims = [c for j in ok for c in j["judge"]["claims"]]
        out[arm] = {
            "answers_to_judge": valid[arm], "judge_rows": len(js), "judged_ok": len(ok), "judge_failed": len(js) - len(ok),
            "not_judged": valid[arm] - len(js),
            "answers_with_an_incorrect_fact_claim": sum(any(c["grade"] == "incorrect" and c["stance"] == "fact" for c in j["judge"]["claims"]) for j in ok),
            "answers_with_an_incorrect_claim_of_any_stance": sum(any(c["grade"] == "incorrect" for c in j["judge"]["claims"]) for j in ok),
            "claims": len(claims), "fact_claims": sum(c["stance"] == "fact" for c in claims), "inference_claims": sum(c["stance"] == "inference" for c in claims),
            "correct": sum(c["grade"] == "correct" for c in claims), "incorrect": sum(c["grade"] == "incorrect" for c in claims),
            "not_in_gold": sum(c["grade"] == "not_in_gold" for c in claims),
            "incorrect_fact_claims": sum(c["grade"] == "incorrect" and c["stance"] == "fact" for c in claims),
            "trap_verdicts": dict(Counter((j["judge"].get("trap") or {}).get("verdict") for j in ok if j["judge"].get("trap"))),
            "arm_guess_right": sum(j["judge"]["arm_guess"] == ARM_LETTER[arm] for j in ok), "arm_guess_n": len(ok)}
    return out


def main() -> int:
    work = Path(sys.argv[1])
    out_path = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else work / "analysis" / "analysis.json"
    repo = Path(sys.argv[sys.argv.index("--repo") + 1]) if "--repo" in sys.argv else Path(r"C:\Users\ozcin\Desktop\verinoda-symbiosis")
    sys.path.insert(0, str(repo / "benchmarks" / "agent_compare"))
    from claims_tasks import order

    def jl(name: str) -> list[dict]:
        p = work / name
        return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []

    tasks = {t["id"]: t for t in json.loads((work / "tasks.json").read_text(encoding="utf-8"))["tasks"]}
    rows = jl("results.jsonl")
    judged = {(j["id"], j["arm"], j["repeat"]): j for j in jl("judge.jsonl") if not j.get("judge_failed")}
    strict = {(m["id"], m["arm"], m["repeat"]): m for m in jl("mechanical-strict.jsonl")}
    ids = order(list(tasks))
    sample_ids = [i for i in ids if tasks[i]["kind"] != "trap"][:24]
    sessions = []
    for r in rows:
        k = (r["id"], r["arm"], r["repeat"])
        s = analyze_session(r, tasks[r["id"]], judged.get(k), strict.get(k), work / "usage")
        s["in_cost_sample"] = r["id"] in sample_ids and r["repeat"] == 1
        s["in_rerun_six"] = r["id"] in SIX and r["arm"] == GUIDED
        sessions.append(s)
    by = {(s["id"], s["arm"], s["repeat"]): s for s in sessions}
    pairs = [(by[(i, PLAIN, 1)], by[(i, GUIDED, 1)]) for i in sample_ids
             if (i, PLAIN, 1) in by and (i, GUIDED, 1) in by and not by[(i, PLAIN, 1)]["is_error"] and not by[(i, GUIDED, 1)]["is_error"]]
    res: dict = {
        "meta": {"work": str(work), "rows": len(rows), "cost_sample_ids": sample_ids,
                 "cost_sample_pairs": len(pairs), "unpaired_sample_ids": [i for i in sample_ids if i not in {p["id"] for p, _ in pairs}],
                 "bootstrap": f"percentile, {N_BOOT} resamples, seed {SEED}, sorted means at indices int(0.025 n) and int(0.975 n)",
                 "model_calls": "assistant messages that carry usage, one per message id (a message is written once per content block)",
                 "own_tool_model_calls": "of those, the messages that issue at least one Bash, Read, Grep or Glob call",
                 "usage_matches_result_json": sum(bool(s.get("usage_matches_result_json")) for s in sessions),
                 "usage_mismatch": [[s["id"], s["arm"], s["repeat"]] for s in sessions if s.get("usage_matches_result_json") is False],
                 "no_transcript": [[s["id"], s["arm"], s["repeat"]] for s in sessions if s.get("transcript") is None]},
        "per_session": sessions,
        "per_arm_cost_sample": per_arm([s for s in sessions if s["in_cost_sample"]]),
        "per_arm_all_valid_sessions": per_arm(sessions),
        "paired_cost_sample": paired(pairs),
    }
    kinds = {}
    for kind in ("why", "when", "affects"):
        sub = [(p, g) for p, g in pairs if p["kind"] == kind]
        if sub:
            kinds[kind] = {m: v for m, v in paired(sub).items() if m in ("n_pairs", "cost_usd", "model_calls", "cache_write_tokens")}
    res["paired_cost_sample_by_kind"] = kinds
    res["criteria"] = {
        "cost_interval_excludes_plus_0.015": (res["paired_cost_sample"].get("cost_usd") or {}).get("ci95", [0, 1])[1] < 0.015 if pairs else None,
        "verinoda_chars_per_session_max": max([s["verinoda_result_chars"] for s in sessions if s["arm"] == GUIDED and s.get("verinoda_result_chars") is not None],
                                               default=None),
        "verinoda_chars_per_session_at_most_4500": None,
        "sessions_with_a_verinoda_call": {a: sum(s["arm"] == a and (s.get("n_verinoda_calls") or 0) > 0 for s in sessions) for a in (PLAIN, GUIDED)},
        "note": "the two criteria are only evaluable when the Verinoda arm called the tools; read the call counts first"}
    mx = res["criteria"]["verinoda_chars_per_session_max"]
    res["criteria"]["verinoda_chars_per_session_at_most_4500"] = None if mx is None else mx <= 4500
    res["six_tasks"] = [s for s in sessions if s["in_rerun_six"]]
    res["verinoda_arm"] = verinoda_arm(sessions)
    res["cold_cache"] = cold_cache(sessions)
    res["pairs_by_analyze_call"] = {
        "with_an_analyze_call": paired([(p, g) for p, g in pairs if g.get("analyze")]) if any(g.get("analyze") for _, g in pairs) else None,
        "without": paired([(p, g) for p, g in pairs if not g.get("analyze")]) if any(not g.get("analyze") for _, g in pairs) else None}
    first_ids = {s["session_id"] for s in cold_first_sessions(sessions)}
    res["paired_cost_sample_without_first_sessions"] = paired([(p, g) for p, g in pairs
                                                               if p["session_id"] not in first_ids and g["session_id"] not in first_ids])
    res["price_fit"] = price_fit(sessions, pairs)
    res["citations"] = citation_rates(work, sample_ids)
    res["judge"] = judge_counts(jl("judge.jsonl"), rows)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(rows), "pairs": len(pairs), "per_arm_cost_sample": {a: {m: v["mean"] for m, v in d.items() if isinstance(v, dict) and m in ("cost_usd", "model_calls", "cache_write_tokens")} for a, d in res["per_arm_cost_sample"].items()},
                      "paired": {m: res["paired_cost_sample"][m]["mean_difference"] for m in ("cost_usd", "model_calls", "cache_write_tokens") if m in res["paired_cost_sample"]},
                      "verinoda_arm": {k: res["verinoda_arm"][k] for k in ("sessions", "with_a_verinoda_call", "with_an_analyze_call", "analyze_was_the_first_tool", "first_tool")},
                      "criteria": res["criteria"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
