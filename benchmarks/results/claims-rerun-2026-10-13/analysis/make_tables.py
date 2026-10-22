"""Markdown tables for the README, from analysis.json (analyze_sessions.py) and d185-comparison.json (compare_d185.py).

    python make_tables.py analysis.json d185-comparison.json [hand_reading_six.json]

Prints only; nothing is written. Every number in the README's tables is a line of this output.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

PLAIN, GUIDED = "none", "verinoda_guided"


def f(x, nd=4):
    return "-" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))


def seq(tools: list[str]) -> str:
    out = []
    for name in tools:
        short = name.replace("mcp__verinoda__", "verinoda.")
        if out and out[-1][0] == short:
            out[-1][1] += 1
        else:
            out.append([short, 1])
    return ", ".join(n if k == 1 else f"{n} x{k}" for n, k in out) or "-"


def yn(x):
    return "-" if x is None else ("yes" if x else "no")


def six_detail(a: dict, hand: dict) -> None:
    """The 18 re-run sessions in one table: the tool order, what the analyze result held of the gold, what the answer did, what the
    judge graded (the hand reading is the agent's, see hand_reading_six.json)."""
    by_gold = {(d["id"], d["repeat"]): d for d in a["verinoda_arm"]["gold_detail"]}
    by_hand = {(h["id"], h["repeat"]): h for h in hand["sessions"]}
    print("\n## The six tasks in detail (18 Verinoda-arm sessions)\n")
    print("| task | r | tools in order | analyze chars | gold file rank in leads | gold commit in the analyze result | answer cites the gold commit | "
          "origin or absence sentence (hand reading) | judge: incorrect fact claims | trap verdict | $ |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for s in sorted(a["six_tasks"], key=lambda x: (x["id"], x["repeat"])):
        g = by_gold.get((s["id"], s["repeat"])) or {}
        h = by_hand[(s["id"], s["repeat"])]
        j = s.get("judge") or {}
        bad = sum(c["stance"] == "fact" for c in j.get("incorrect", []))
        gr = g.get("gold_file_best_rank_in_leads")
        sent = "none" if not h["absence_or_origin_assertion"] else ("wrong per git" if h.get("origin_wrong_per_git") is True else
                                                                "true, scoped to the file" if h.get("origin_wrong_per_git") is False else "scoped, see note")
        print(f"| {s['id']} | {s['repeat']} | {seq(s.get('tool_sequence') or [])} | {(g.get('result_chars') or ['-'])[0]} | {gr if gr is not None else 'not in leads'} | "
              f"{yn(g.get('gold_commit_elsewhere_in_analyze_result'))} | {yn(h.get('cites_gold_commit'))} | {sent} | {bad} | "
              f"{((j.get('trap') or {}).get('verdict')) or '-'} | {f(s.get('cost_usd'))} |")


def extra(a: dict) -> None:
    """The sections added after the Verinoda arm made calls: its use of the tools, the cold-cache check, citations, the judge."""
    v = a.get("verinoda_arm")
    if v:
        print("\n## The Verinoda arm's use of the tools\n")
        keys = ("sessions", "with_a_verinoda_call", "with_an_analyze_call", "analyze_was_the_first_tool", "analyze_before_any_own_tool",
                "toolsearch_calls")
        print("- " + "; ".join(f"{k} {v[k]}" for k in keys))
        print(f"- first tool: {v['first_tool']}; calls by tool: {v['calls_by_tool']}; run_tool by inner name: {v['run_tool_by_inner_name']}; "
              f"analyze calls per session: {v['analyze_calls_per_session']}")
        c, ac = v["verinoda_result_chars_per_session"], v["analyze_result_chars_per_call"]
        print(f"- Verinoda result chars per session: mean {f(c['mean'], 0)}, median {f(c['median'], 0)}, max {f(c['max'], 0)} (n {c['n']}); "
              f"per analyze call: mean {f(ac['mean'], 0)}, median {f(ac['median'], 0)}, max {f(ac['max'], 0)} (n {ac['n']}); "
              f"sessions over 4,500: {len(v['sessions_over_4500_chars'])}")
        print(f"- by kind: {v['by_kind']}")
        print(f"- gold: {v['gold']}")
    pf = a.get("price_fit")
    if pf:
        print("\n## Price table fit (derived)\n")
        for name, d in pf["tables"].items():
            print(f"- {name}: max |residual| {d['max_abs_residual_usd']:.6f} USD, mean residual {d['mean_residual_usd']:.6f} USD over {d['n']} sessions")
        print(f"- best: {pf['best_table']}; paired difference by component (USD): "
              + ", ".join(f"{k} {v:.5f}" for k, v in pf["paired_difference_by_component_usd"].items()))
    print("\n## Cold cache: the first three sessions of each arm in time order against the rest\n")
    for arm, d in (a.get("cold_cache") or {}).items():
        print(f"- {arm}: {d['sessions']} sessions; median of the rest: {d['median_of_the_rest']}")
        for s in d["first_three"]:
            print(f"    {s['ts_first']} {s['id']} r{s['repeat']}: ${f(s['cost_usd'])}, first-call cache write {s['first_call_cache_write']}, "
                  f"cache read {s['first_call_cache_read']}, model calls {s['model_calls']}")
    if a.get("paired_cost_sample_without_first_sessions"):
        r = a["paired_cost_sample_without_first_sessions"]["cost_usd"]
        print(f"\npaired dollars without the pairs holding the first session of either arm: n {r['n']}, difference {f(r['mean_difference'])} "
              f"[{f(r['ci95'][0])}, {f(r['ci95'][1])}]")
    pb = a.get("pairs_by_analyze_call") or {}
    for k, r in pb.items():
        if r:
            c = r["cost_usd"]
            print(f"paired dollars, Verinoda session {k.replace('_', ' ')}: n {c['n']}, difference {f(c['mean_difference'])} [{f(c['ci95'][0])}, {f(c['ci95'][1])}]")
    print("\n## Citation verdicts (lenient = mechanical.jsonl, strict = mechanical-strict.jsonl)\n")
    for name, sets in (a.get("citations") or {}).items():
        for label, arms in sets.items():
            for arm, d in arms.items():
                print(f"- {name} / {label} / {arm}: answers {d.get('answers')}, citations {d.get('citations')}, confirmed {d.get('confirmed', 0)}, "
                      f"wrong {d.get('wrong', 0)}, missing {d.get('missing', 0)}, not_repo {d.get('not_repo', 0)}; confirmed share {f(d['confirmed_share'])}; "
                      f"locations {f(d['location_confirmed_share'])}, commits {f(d['commit_confirmed_share'])}")
    print("\n## Judge\n")
    for arm, d in (a.get("judge") or {}).items():
        print(f"- {arm}: {d}")


def main() -> int:
    a = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    d = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")) if len(sys.argv) > 2 else None
    ses = a["per_session"]
    print("## Verinoda calls and ToolSearch calls per arm (all sessions)\n")
    print("| arm | sessions | errored | with a Verinoda call | Verinoda calls | ToolSearch calls | Verinoda result chars |")
    print("|---|---|---|---|---|---|---|")
    for arm in (PLAIN, GUIDED):
        s = [x for x in ses if x["arm"] == arm]
        print(f"| {arm} | {len(s)} | {sum(x['is_error'] for x in s)} | {sum((x.get('n_verinoda_calls') or 0) > 0 for x in s)} | "
              f"{sum(x.get('n_verinoda_calls') or 0 for x in s)} | {sum(x.get('n_toolsearch_calls') or 0 for x in s)} | "
              f"{sum(x.get('verinoda_result_chars') or 0 for x in s)} |")
    print("\n## First tool of each session, per arm\n")
    for arm in (PLAIN, GUIDED):
        c = Counter((x.get("tool_sequence") or ["-"])[0] for x in ses if x["arm"] == arm)
        print(f"- {arm}: " + ", ".join(f"{k} {v}" for k, v in c.most_common()))
    print("\n## Tool use per arm (all valid sessions): sessions by tool\n")
    for arm in (PLAIN, GUIDED):
        c = Counter(t for x in ses if x["arm"] == arm for t in set(x.get("tool_sequence") or []))
        print(f"- {arm}: " + ", ".join(f"{k} {v}" for k, v in c.most_common()))
    print("\n## Per arm, cost sample (24 tasks, repeat 1)\n")
    pa = a["per_arm_cost_sample"]
    print("| per session | plain mean | plain median | Verinoda mean | Verinoda median |")
    print("|---|---|---|---|---|")
    for m in ("cost_usd", "model_calls", "own_tool_model_calls", "n_tool_calls", "n_verinoda_calls", "num_turns", "cache_write_tokens",
              "first_call_cache_write_tokens", "cache_read_tokens", "uncached_input_tokens", "output_tokens", "verinoda_result_chars",
              "own_result_chars", "answer_chars", "seconds"):
        p, g = pa[PLAIN][m], pa[GUIDED][m]
        nd = 4 if m == "cost_usd" else 2 if m in ("model_calls", "own_tool_model_calls", "n_tool_calls", "n_verinoda_calls", "num_turns") else 0
        print(f"| {m} | {f(p['mean'], nd)} | {f(p['median'], nd)} | {f(g['mean'], nd)} | {f(g['median'], nd)} |")
    print(f"\nsessions: plain {pa[PLAIN]['sessions']}, Verinoda {pa[GUIDED]['sessions']}; with a Verinoda call: "
          f"{pa[PLAIN]['sessions_with_a_verinoda_call']} and {pa[GUIDED]['sessions_with_a_verinoda_call']}")
    print("\n## Paired differences, Verinoda minus plain, 24 pairs, bootstrap 95 % (10,000 resamples, seed 20261013)\n")
    pr = a["paired_cost_sample"]
    print("| measure | plain mean | Verinoda mean | difference | 95 % interval | pairs Verinoda higher / equal / lower |")
    print("|---|---|---|---|---|---|")
    for m in ("cost_usd", "model_calls", "own_tool_model_calls", "n_verinoda_calls", "cache_write_tokens", "first_call_cache_write_tokens",
              "cache_read_tokens", "uncached_input_tokens", "output_tokens", "verinoda_result_chars", "own_result_chars", "answer_chars",
              "seconds"):
        if m not in pr:
            continue
        r = pr[m]
        nd = 4 if m == "cost_usd" else 2 if "calls" in m else 0
        hi, eq = r["pairs_where_verinoda_is_higher"], r["pairs_equal"]
        print(f"| {m} | {f(r['plain_mean'], nd)} | {f(r['verinoda_mean'], nd)} | {f(r['mean_difference'], nd)} | "
              f"{f(r['ci95'][0], nd)} to {f(r['ci95'][1], nd)} | {hi} / {eq} / {r['n'] - hi - eq} |")
    print("\n## Paired by kind\n")
    for kind, v in a["paired_cost_sample_by_kind"].items():
        c = v["cost_usd"]
        print(f"- {kind} (n={v['n_pairs']}): dollars {f(c['mean_difference'])} [{f(c['ci95'][0])}, {f(c['ci95'][1])}]; "
              f"model calls {f(v['model_calls']['mean_difference'], 2)}; cache writes {f(v['cache_write_tokens']['mean_difference'], 0)}")
    print("\n## Criteria\n")
    print(json.dumps(a["criteria"], indent=1))
    print("\n## Meta\n")
    print(json.dumps({k: v for k, v in a["meta"].items() if k != "cost_sample_ids"}, indent=1))
    print("\n## The six tasks, 18 Verinoda-arm sessions\n")
    print("| task | r | tools in order | model calls | own-tool calls | $ | answer names gold commit | judge: claims / incorrect facts | trap verdict |")
    print("|---|---|---|---|---|---|---|---|---|")
    for s in sorted(a["six_tasks"], key=lambda x: (x["id"], x["repeat"])):
        j = s.get("judge") or {}
        print(f"| {s['id']} | {s['repeat']} | {seq(s.get('tool_sequence') or [])} | {s.get('model_calls')} | {s.get('own_tool_model_calls')} | "
              f"{f(s.get('cost_usd'))} | {yn(s.get('answer_names_gold_commit'))} | {j.get('claims', '-')} / {len(j.get('incorrect', [])) if j else '-'} | "
              f"{((j.get('trap') or {}).get('verdict')) or '-'} |")
    extra(a)
    if len(sys.argv) > 3:
        six_detail(a, json.loads(Path(sys.argv[3]).read_text(encoding="utf-8")))
    if d:
        print("\n## Six tasks against D185 (sessions with a false fact claim / judged; gold commit cited / sessions)\n")
        print("| task | D185 plain | D185 Verinoda | D185 traps rerun (opaque names) plain / Verinoda | D186 re-run Verinoda |")
        print("|---|---|---|---|---|")

        def cell(x):
            if x is None:
                return "-"
            s = f"false fact {x['false_fact']}/{x['judged']}"
            if x["cites_gold_commit"] is not None:
                s += f", gold commit cited {x['cites_gold_commit']}/{x['sessions']}"
            if x["trap_verdicts"] is not None:
                s += ", trap: " + "/".join(str(v) for v in x["trap_verdicts"])
            return s + f"; Verinoda calls {x['verinoda_calls']}; ${x['mean_cost_usd']:.3f}, {x['mean_turns']:.1f} turns"

        for row in d["table"]:
            op = f"{cell(row.get('d185_opaque_plain'))} / {cell(row.get('d185_opaque_verinoda'))}" if "d185_opaque_plain" in row else "-"
            print(f"| {row['id']} | {cell(row['d185_plain'])} | {cell(row['d185_verinoda'])} | {op} | {cell(row['rerun_verinoda'])} |")
        print("\n## D185 on the 24 cost-sample tasks (all repeats; repeat 1 alone)\n")
        for arm, v in d["d185_cost_on_the_24_sample_tasks"].items():
            for k, c in v.items():
                print(f"- {arm} {k}: {c}")
        t = d.get("d185_transcript_stats_on_the_24_sample_tasks")
        if t:
            print(f"\n## D185 on the 24 tasks, from its transcripts ({t['sessions']} sessions, {t['missing_transcripts']} without a transcript, "
                  f"usage equal to the result JSON in {t['usage_matches_result_json']})\n")
            print("| per session (repeat 1, 24 per arm) | D185 plain | D185 Verinoda (GUIDE) |")
            print("|---|---|---|")
            r1 = t["repeat_1"]
            for m in ("cost_usd", "model_calls", "own_tool_model_calls", "n_verinoda_calls", "cache_write_tokens", "first_call_cache_write_tokens",
                      "cache_read_tokens", "output_tokens", "verinoda_result_chars", "own_result_chars", "answer_chars"):
                nd = 4 if m == "cost_usd" else 2 if m in ("model_calls", "own_tool_model_calls", "n_verinoda_calls") else 0
                print(f"| {m} (mean) | {f(r1[PLAIN][m]['mean'], nd)} | {f(r1[GUIDED][m]['mean'], nd)} |")
            print("\npaired, D185, repeat 1, 24 pairs (Verinoda minus plain; bootstrap 95 %, seed 20261013):\n")
            for m in ("cost_usd", "model_calls", "own_tool_model_calls", "cache_write_tokens", "verinoda_result_chars"):
                p = t["paired_repeat_1"][m]
                nd = 4 if m == "cost_usd" else 2 if "calls" in m else 0
                print(f"- {m}: {f(p['mean_difference'], nd)} [{f(p['ci95'][0], nd)}, {f(p['ci95'][1], nd)}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
