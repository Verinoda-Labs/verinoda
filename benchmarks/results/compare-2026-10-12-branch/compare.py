"""compare.md: the branch rerun (this folder) against benchmarks/results/compare-2026-10-02/after-fix, fact by fact.

Per set and per approach (verinoda_retrieve_text, verinoda_analyze): facts found now vs baseline, tokens per
question, and for every question whose found-fact set differs the ids lost and gained. The per-question diff is
also cross-checked against the harness's own ``fact_changes`` (verinoda.benchmark.report).

    .venv/Scripts/python.exe compare.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path("C:/Users/ozcin/Desktop/verinoda-symbiosis")
BASE = REPO / "benchmarks/results/compare-2026-10-02/after-fix"
SETS = ("orders_app", "orders_app_tr", "glow_mod", "forge_mod", "graphify_core", "graphify_core_tr",
        "heldout_repoatlas", "verinoda_user_tr")
APPROACHES = ("verinoda_retrieve_text", "verinoda_analyze")

sys.path.insert(0, str(REPO))
from verinoda.benchmark.report import fact_changes  # noqa: E402


def load(p: Path) -> dict | None:
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def per_question(res: dict, ap: str) -> dict[str, dict]:
    out = {}
    for q in res.get("questions") or []:
        slot = (q.get("approaches") or {}).get(ap) or {}
        score = slot.get("score") or {}
        facts = score.get("facts") or {}
        out[q["id"]] = {"found": set(facts.get("found") or []), "tokens": score.get("tokens"),
                        "error": slot.get("error"), "has_score": bool(score)}
    return out


def fmt_ids(ids) -> str:
    return ", ".join(f"`{x}`" for x in sorted(ids)) if ids else "-"


def main() -> None:
    lines = ["# Branch rerun against the after-fix baseline, fact by fact", ""]
    run_log = (HERE / "run_all.log").read_text(encoding="utf-8") if (HERE / "run_all.log").exists() else ""
    totals = {ap: {"base_found": 0, "now_found": 0, "total": 0, "base_tok": 0.0, "now_tok": 0.0, "nq": 0}
              for ap in APPROACHES}
    all_lost: list[str] = []
    all_gained: list[str] = []
    not_run: list[str] = []
    cross_check_failures: list[str] = []
    env_rows = []
    corpus_rows = []
    set_rows = []
    diff_sections = []
    token_sections = []

    for s in SETS:
        base = load(BASE / f"{s}.json")
        now = load(HERE / f"{s}.json")
        if base is None:
            not_run.append(f"{s}: no baseline file {BASE / (s + '.json')}")
            continue
        if now is None or now.get("status") != "ok":
            why = "no result file written" if now is None else f"status {now.get('status')!r}"
            if now is not None and now.get("status") == "gold_invalid":
                why += f"; gold_validation failures: {json.dumps(now.get('gold_validation', {}).get('failures'))}"
            m = re.search(rf"END {re.escape(s)} rc=(\d+) seconds=(\d+)", run_log)
            if m:
                why += f" (exit code {m.group(1)}, {m.group(2)} s)"
            not_run.append(f"{s}: {why}")
            continue
        be, ne = base.get("environment", {}), now.get("environment", {})
        env_rows.append((s, be.get("python"), ne.get("python"), str(be.get("verinoda_source_commit"))[:7],
                         str(ne.get("verinoda_source_commit"))[:7], ne.get("date_utc")))
        bc, nc = base.get("corpus", {}), now.get("corpus", {})
        corpus_rows.append((s, f"{bc.get('file_count')} / {nc.get('file_count')}", f"{bc.get('bytes')} / {nc.get('bytes')}",
                            f"{str(bc.get('source_commit'))[:8]} / {str(nc.get('source_commit'))[:8]}",
                            f"{bc.get('snapshot')} / {nc.get('snapshot')}",
                            f"{base.get('gold_validation', {}).get('facts_checked')} / "
                            f"{now.get('gold_validation', {}).get('facts_checked')}",
                            # the examples/* corpora are this repository's working tree, so their source commit is
                            # the running checkout (5999912 then, the branch head now); files and bytes are the check
                            "same files/bytes" if (bc.get("file_count"), bc.get("bytes")) ==
                            (nc.get("file_count"), nc.get("bytes")) else "DIFFERENT"))
        harness = fact_changes(base, now)
        for ap in APPROACHES:
            bs, ns = base["summary"][ap], now["summary"][ap]
            nq = ns["questions"]
            set_rows.append((s, ap, f"{bs['facts_found']}/{bs['facts_total']}", f"{ns['facts_found']}/{ns['facts_total']}",
                             f"{ns['facts_found'] - bs['facts_found']:+d}", f"{bs['tokens_mean']:.1f}",
                             f"{ns['tokens_mean']:.1f}", f"{ns['tokens_mean'] - bs['tokens_mean']:+.1f}",
                             f"{bs.get('errors', 0)} / {ns.get('errors', 0)}"))
            t = totals[ap]
            t["base_found"] += bs["facts_found"]
            t["now_found"] += ns["facts_found"]
            t["total"] += ns["facts_total"]
            t["base_tok"] += bs["tokens_mean"] * bs["questions"]
            t["now_tok"] += ns["tokens_mean"] * nq
            t["nq"] += nq
            bq, nq_ = per_question(base, ap), per_question(now, ap)
            my_lost, my_gained = [], []
            for qid in sorted(set(bq) | set(nq_)):
                b, n = bq.get(qid), nq_.get(qid)
                if b is None or n is None:
                    diff_sections.append(f"- {s} / {ap} / {qid}: present only in "
                                         f"{'baseline' if n is None else 'rerun'}")
                    continue
                lost, gained = b["found"] - n["found"], n["found"] - b["found"]
                note = ""
                if n["error"] or not n["has_score"]:
                    note = f" (rerun record: error={n['error']!r}, scored={n['has_score']})"
                if lost or gained or note:
                    diff_sections.append(f"- {s} / {ap} / **{qid}**: lost {fmt_ids(lost)}; gained {fmt_ids(gained)}{note}")
                my_lost += [f"{qid}/{x}" for x in sorted(lost)]
                my_gained += [f"{qid}/{x}" for x in sorted(gained)]
                token_sections.append((s, ap, qid, b["tokens"], n["tokens"],
                                       (n["tokens"] or 0) - (b["tokens"] or 0) if b["tokens"] is not None
                                       and n["tokens"] is not None else None))
            all_lost += [f"{s} / {ap} / {x}" for x in my_lost]
            all_gained += [f"{s} / {ap} / {x}" for x in my_gained]
            h = harness.get(ap, {"lost_found": [], "gained_found": []})
            if sorted(h["lost_found"]) != sorted(my_lost) or sorted(h["gained_found"]) != sorted(my_gained):
                cross_check_failures.append(f"{s} / {ap}: harness lost={h['lost_found']} gained={h['gained_found']}; "
                                            f"this script lost={my_lost} gained={my_gained}")

    lines += ["Baseline: `benchmarks/results/compare-2026-10-02/after-fix/<set>.json` (Verinoda at 5999912, Python "
              "3.13.14, `--repeat 1`, `--llm none`, no `--graphify-cmd`). Rerun: this folder, same flags, on branch "
              "`symbiosis-redesign-2026-10-12` (see the environment table for the commit). Facts: `summary.<approach>."
              "facts_found` / `facts_total`; per question: `approaches.<approach>.score.facts.found`. Tokens: chars/4 "
              "(`summary.<approach>.tokens_mean`, `score.tokens`).", ""]

    lines += ["## Environment", "", "| set | python baseline / now | verinoda commit baseline / now | run date (UTC) now |",
              "|---|---|---|---|"]
    for s, bp, np_, bcm, ncm, d in env_rows:
        lines.append(f"| {s} | {bp} / {np_} | {bcm} / {ncm} | {d} |")
    pkg = sorted({json.dumps((load(HERE / f"{s}.json") or {}).get("environment", {}).get("verinoda_package_changes_vs_commit"))
                  for s, *_ in env_rows})
    be0 = (load(BASE / "graphify_core.json") or {}).get("environment", {})
    ne0 = (load(HERE / "graphify_core.json") or {}).get("environment", {})
    lines += ["", f"`environment.verinoda_package_changes_vs_commit` in every rerun file: {', '.join(pkg)} (the measured "
              "package is the committed code of the recorded commit, no uncommitted change). The four analyze commits the "
              "review is about (6036da0, 00c89b7, c5829bd, ca1f8d3) are ancestors of the measured commit c678d46 "
              "(`git merge-base --is-ancestor`, each yes). Vendored Graphify renderer 20a20d30 in both.", "",
              "Machine fields (`environment`, baseline / now): "
              f"os {be0.get('os')} / {ne0.get('os')}; processor {be0.get('processor')} / {ne0.get('processor')}; "
              f"cpu_count {be0.get('cpu_count')} / {ne0.get('cpu_count')}; git {be0.get('git')} / {ne0.get('git')}. "
              "The baseline README records other benchmarks running at the same time as it. Timings are not compared here.", "",
              "Repository state: `git status --short` before the rerun showed no change (HEAD c678d46). "
              "`docs/drafts/2026-10-12-verinoda-lean-plan.md` has mtime 2026-10-12T16:39:36Z (while heldout_repoatlas was "
              "running); it was untracked (`??`) at the first status check after the rerun and committed as 4832c0f "
              "(219 insertions, that file only, no code) by the second check, when the status was clean. The harness "
              "writes nothing under `docs/`; the rerun changed no tracked file."]

    lines += ["", "## Corpus check (baseline / now)", "",
              "| set | files | bytes | source commit | snapshot | gold facts checked | corpus |", "|---|---|---|---|---|---|---|"]
    for row in corpus_rows:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")

    lines += ["", "## Facts found and tokens per question, per set and approach", "",
              "| set | approach | facts baseline | facts now | delta | tokens/q baseline | tokens/q now | delta | errors baseline / now |",
              "|---|---|---|---|---|---|---|---|---|"]
    for row in set_rows:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    lines += ["", "### Totals over the sets that ran", "",
              "| approach | facts baseline | facts now | tokens/q baseline | tokens/q now |", "|---|---|---|---|---|"]
    for ap, t in totals.items():
        if t["nq"]:
            lines.append(f"| {ap} | {t['base_found']}/{t['total']} | {t['now_found']}/{t['total']} | "
                         f"{t['base_tok'] / t['nq']:.1f} | {t['now_tok'] / t['nq']:.1f} |")

    lines += ["", "## Questions whose found-fact set differs", ""]
    lines += diff_sections or ["None: every question of every set that ran has the same found-fact set as the baseline, "
                               "for both approaches."]

    changed = [t for t in token_sections if t[5] != 0]
    lines += ["", "## Tokens per question (baseline -> now)", "",
              f"{len(token_sections)} question/approach records compared; {len(token_sections) - len(changed)} have the "
              f"same token count as the baseline. The {len(changed)} that differ:", "",
              "| set | approach | question | tokens baseline | tokens now | delta |", "|---|---|---|---|---|---|"]
    for s, ap, qid, bt, nt, d in changed:
        lines.append(f"| {s} | {ap} | {qid} | {bt} | {nt} | {'n/a' if d is None else f'{d:+d}'} |")
    for ap in APPROACHES:
        n_ap = [t for t in token_sections if t[1] == ap]
        ch = [t for t in changed if t[1] == ap]
        lines.append("")
        lines.append(f"- {ap}: {len(ch)} of {len(n_ap)} questions differ; per-set means in the table above.")

    lines += ["", "## Cross-check against the harness's `fact_changes`", ""]
    lines += ([f"- {x}" for x in cross_check_failures] or
              ["Agrees for every set and approach that ran (lost and gained `question/fact` ids identical)."])

    lines += ["", "## Verdict", ""]
    if all_lost:
        lines += ["Facts lost (set / approach / question/fact):"] + [f"- {x}" for x in all_lost]
    else:
        lines.append("**No fact lost** on the sets that ran, for either approach.")
    if all_gained:
        lines += ["", "Facts gained:"] + [f"- {x}" for x in all_gained]
    else:
        lines.append("No fact gained.")
    lines += ["", "Sets not run or not compared:"]
    lines += [f"- {x}" for x in not_run] or ["- none: all eight sets ran with status `ok`."]

    lines += ["", "## Commands run", "", "From `run_all.sh` (run from the repository root, `.venv/Scripts/python.exe`):", "", "```"]
    for m in re.finditer(r"START (\S+): (.*)", run_log):
        lines.append(m.group(2))
    lines += ["```", "", "Timing and exit codes (`run_all.log`):", "", "```"]
    lines += [ln for ln in run_log.splitlines() if " END " in ln or "ALL DONE" in ln or "branch=" in ln or ln.startswith("python")]
    lines += ["```", "", "Comparison (from the repository root; `<OUT>` is this folder):", "", "```"]
    lines += [f"python -m verinoda.benchmark compare benchmarks/results/compare-2026-10-02/after-fix/{s}.json "
              f"<OUT>/{s}.json > <OUT>/compare-{s}.txt" for s in SETS]
    lines += ["python <OUT>/compare.py   # this file: compare.md, cross-checked against verinoda.benchmark.report.fact_changes",
              "```", ""]
    (HERE / "compare.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
