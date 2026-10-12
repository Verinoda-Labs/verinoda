"""The six re-run tasks, session by session, and the 24 cost-sample tasks in total: the D185 first run (read only, from
benchmarks/results/claims-2026-10-11 and its traps-opaque/ rerun) next to this re-run.

    python compare_d185.py WORK_DIR D185_RESULTS_DIR OUT.json

Per session: the answer cites the gold commit (hash prefix match, 7 characters or more), the judge's count of claims graded an
incorrect fact, the judge's trap verdict (the two traps), the cost, the model turns and the Verinoda calls. The D185 folder is
only read. Pilot rows count (fastapi why-1's first repeat is one of them). The two configurations differ in more than the code: D185
gave the Verinoda arm the GUIDE paragraph in the user prompt and the mod with the nudge; the re-run gives the stance only and the
mod's call rule (see the README), so a difference between the columns is a difference between configurations.
"""

from __future__ import annotations

import json
import re
import statistics
import sys
from pathlib import Path

SIX = ["fastapi__full-stack-fastapi-template-why-1", "junegunn__fzf-why-1", "guzzle__guzzle-trap-1", "gin-gonic__gin-trap-1",
       "axios__axios-when-1", "sharkdp__bat-when-1"]
TRAPS = ["guzzle__guzzle-trap-1", "gin-gonic__gin-trap-1"]
HASH = re.compile(r"\b[0-9a-f]{7,40}\b")
PLAIN, GUIDED = "none", "verinoda_guided"


def jl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []


def names(answer: str, commits: list[str]) -> list[str]:
    toks = [t for t in HASH.findall(answer.lower()) if not t.isdigit()]
    return [c for c in commits if any(len(t) >= 7 and (c.startswith(t) or t.startswith(c)) for t in toks)]


def sessions(folder: Path, tasks: dict, label: str, only: list[str]) -> list[dict]:
    rows = [r for r in jl(folder / "results.jsonl") if r["id"] in only]
    judged = {(j["id"], j["arm"], j["repeat"]): j for j in jl(folder / "judge.jsonl")}
    out = []
    for r in rows:
        t = tasks[r["id"]]
        commits = [g["commit"].lower() for g in t["gold"] if g.get("commit")]
        j = (judged.get((r["id"], r["arm"], r["repeat"])) or {}).get("judge")
        bad = [c for c in (j or {}).get("claims", []) if c["grade"] == "incorrect"]
        out.append({"run": label, "id": r["id"], "arm": r["arm"], "repeat": r["repeat"], "kind": t["kind"], "pilot": bool(r.get("pilot")),
                    "cites_gold_commit": names(r.get("answer") or "", commits) if commits else None,
                    "incorrect_claims": len(bad), "incorrect_fact_claims": sum(c["stance"] == "fact" for c in bad),
                    "false_fact": int(any(c["stance"] == "fact" for c in bad)) if j else None,
                    "trap_verdict": ((j or {}).get("trap") or {}).get("verdict") if t["kind"] == "trap" else None,
                    "cost_usd": r.get("cost_usd"), "num_turns": r.get("num_turns"), "verinoda_calls": r.get("verinoda_calls"),
                    "is_error": r.get("is_error")})
    return sorted(out, key=lambda x: (only.index(x["id"]), x["arm"], x["repeat"]))


def cell(sess: list[dict], tid: str, arm: str, kind: str) -> dict:
    s = [x for x in sess if x["id"] == tid and x["arm"] == arm]
    return {"sessions": len(s), "false_fact": sum(x["false_fact"] or 0 for x in s),
            "judged": sum(x["false_fact"] is not None for x in s),
            "cites_gold_commit": (sum(bool(x["cites_gold_commit"]) for x in s) if s and s[0]["cites_gold_commit"] is not None else None),
            "trap_verdicts": [x["trap_verdict"] for x in s] if kind == "trap" else None,
            "verinoda_calls": sum(x["verinoda_calls"] or 0 for x in s),
            "mean_cost_usd": sum(x["cost_usd"] or 0 for x in s) / len(s) if s else None,
            "mean_turns": sum(x["num_turns"] or 0 for x in s) / len(s) if s else None}


def cost_on(rows: list[dict], ids: list[str], arm: str, repeat: int | None = None) -> dict:
    r = [x for x in rows if x["id"] in ids and x["arm"] == arm and not x.get("is_error") and (repeat is None or x["repeat"] == repeat)]
    c = [x["cost_usd"] for x in r]
    return {"sessions": len(r), "mean_cost_usd": sum(c) / len(c) if c else None, "median_cost_usd": statistics.median(c) if c else None,
            "median_turns": statistics.median([x["num_turns"] for x in r]) if r else None,
            "median_seconds": statistics.median([x["seconds"] for x in r]) if r else None,
            "median_answer_chars": statistics.median([len(x.get("answer") or "") for x in r]) if r else None}


def main() -> int:
    work, d185, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    tasks = {t["id"]: t for t in json.loads((work / "tasks.json").read_text(encoding="utf-8"))["tasks"]}
    first = sessions(d185, tasks, "D185", SIX)
    opaque = sessions(d185 / "traps-opaque", tasks, "D185-traps-opaque", TRAPS)
    rerun = [r for r in sessions(work, tasks, "rerun", SIX) if r["arm"] == GUIDED]
    res: dict = {"D185": first, "D185_traps_opaque": opaque, "rerun": rerun, "table": []}
    for tid in SIX:
        kind = tasks[tid]["kind"]
        row = {"id": tid, "kind": kind, "d185_plain": cell(first, tid, PLAIN, kind), "d185_verinoda": cell(first, tid, GUIDED, kind),
               "rerun_verinoda": cell(rerun, tid, GUIDED, kind)}
        if tid in TRAPS:
            row["d185_opaque_plain"] = cell(opaque, tid, PLAIN, kind)
            row["d185_opaque_verinoda"] = cell(opaque, tid, GUIDED, kind)
        res["table"].append(row)
    # the 24 cost-sample tasks in the D185 run (all three repeats, and repeat 1 alone), per arm: dollars and turns
    sys.path.insert(0, str(Path(r"C:\Users\ozcin\Desktop\verinoda-symbiosis") / "benchmarks" / "agent_compare"))
    from claims_tasks import order

    ids = order(list(tasks))
    sample = [i for i in ids if tasks[i]["kind"] != "trap"][:24]
    d_rows = jl(d185 / "results.jsonl")
    res["d185_cost_on_the_24_sample_tasks"] = {arm: {"all_repeats": cost_on(d_rows, sample, arm), "repeat_1": cost_on(d_rows, sample, arm, 1)}
                                               for arm in (PLAIN, GUIDED)}
    # the same 24 tasks in the D185 run read from its session transcripts (still on disk), with the metrics of analyze_sessions.py
    import analyze_sessions as A

    ses = []
    for r in d_rows:
        if r["id"] in sample:
            s = A.analyze_session(r, tasks[r["id"]], None, None, None)
            s["in_cost_sample"] = r["repeat"] == 1
            ses.append(s)
    by = {(s["id"], s["arm"]): s for s in ses if s["in_cost_sample"] and not s["is_error"]}
    pairs = [(by[(i, PLAIN)], by[(i, GUIDED)]) for i in sample if (i, PLAIN) in by and (i, GUIDED) in by]
    res["d185_transcript_stats_on_the_24_sample_tasks"] = {
        "sessions": len(ses), "missing_transcripts": sum(s.get("transcript") is None for s in ses),
        "usage_matches_result_json": sum(bool(s.get("usage_matches_result_json")) for s in ses),
        "all_repeats": A.per_arm(ses), "repeat_1": A.per_arm([s for s in ses if s["in_cost_sample"]]), "paired_repeat_1": A.paired(pairs)}
    out.write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for row in res["table"]:
        print(row["id"], row["kind"])
        for key in ("d185_plain", "d185_verinoda", "d185_opaque_plain", "d185_opaque_verinoda", "rerun_verinoda"):
            if key in row:
                print("   ", key, row[key])
    print(json.dumps(res["d185_cost_on_the_24_sample_tasks"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
