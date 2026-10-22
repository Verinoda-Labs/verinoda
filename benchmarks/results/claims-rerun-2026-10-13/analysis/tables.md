## Verinoda calls and ToolSearch calls per arm (all sessions)

| arm | sessions | errored | with a Verinoda call | Verinoda calls | ToolSearch calls | Verinoda result chars |
|---|---|---|---|---|---|---|
| none | 24 | 0 | 0 | 0 | 0 | 0 |
| verinoda_guided | 39 | 0 | 37 | 37 | 0 | 110763 |

## First tool of each session, per arm

- none: Grep 24
- verinoda_guided: mcp__verinoda__analyze 37, Grep 2

## Tool use per arm (all valid sessions): sessions by tool

- none: Grep 24, Bash 16, Read 16
- verinoda_guided: mcp__verinoda__analyze 37, Grep 35, Bash 27, Read 15

## Per arm, cost sample (24 tasks, repeat 1)

| per session | plain mean | plain median | Verinoda mean | Verinoda median |
|---|---|---|---|---|
| cost_usd | 0.0576 | 0.0561 | 0.0633 | 0.0643 |
| model_calls | 3.50 | 3.00 | 3.17 | 3.00 |
| own_tool_model_calls | 2.50 | 2.00 | 2.00 | 2.00 |
| n_tool_calls | 3.42 | 3.00 | 3.42 | 3.00 |
| n_verinoda_calls | 0.00 | 0.00 | 0.92 | 1.00 |
| num_turns | 4.42 | 4.00 | 4.42 | 4.00 |
| cache_write_tokens | 9307 | 8720 | 11059 | 10920 |
| first_call_cache_write_tokens | 6741 | 6242 | 7835 | 7335 |
| cache_read_tokens | 75990 | 71140 | 74235 | 69926 |
| uncached_input_tokens | 7 | 6 | 6 | 6 |
| output_tokens | 1271 | 1244 | 1160 | 1148 |
| verinoda_result_chars | 0 | 0 | 3136 | 2484 |
| own_result_chars | 4623 | 3724 | 2974 | 2918 |
| answer_chars | 2077 | 1948 | 1862 | 1818 |
| seconds | 16 | 16 | 16 | 16 |

sessions: plain 24, Verinoda 24; with a Verinoda call: 0 and 22

## Paired differences, Verinoda minus plain, 24 pairs, bootstrap 95 % (10,000 resamples, seed 20261013)

| measure | plain mean | Verinoda mean | difference | 95 % interval | pairs Verinoda higher / equal / lower |
|---|---|---|---|---|---|
| cost_usd | 0.0576 | 0.0633 | 0.0057 | 0.0023 to 0.0085 | 21 / 0 / 3 |
| model_calls | 3.50 | 3.17 | -0.33 | -0.62 to -0.04 | 2 / 14 / 8 |
| own_tool_model_calls | 2.50 | 2.00 | -0.50 | -0.83 to -0.17 | 1 / 14 / 9 |
| n_verinoda_calls | 0.00 | 0.92 | 0.92 | 0.79 to 1.00 | 22 / 2 / 0 |
| cache_write_tokens | 9307 | 11059 | 1752 | 1009 to 2331 | 22 / 0 / 2 |
| first_call_cache_write_tokens | 6741 | 7835 | 1095 | 1093 to 1097 | 24 / 0 / 0 |
| cache_read_tokens | 75990 | 74235 | -1756 | -9603 to 5734 | 16 / 0 / 8 |
| uncached_input_tokens | 7 | 6 | -1 | -1 to -0 | 2 / 14 / 8 |
| output_tokens | 1271 | 1160 | -111 | -192 to -27 | 8 / 0 / 16 |
| verinoda_result_chars | 0 | 3136 | 3136 | 2267 to 4204 | 22 / 2 / 0 |
| own_result_chars | 4623 | 2974 | -1650 | -3228 to -525 | 7 / 0 / 17 |
| answer_chars | 2077 | 1862 | -216 | -348 to -76 | 7 / 0 / 17 |
| seconds | 16 | 16 | 1 | -1 to 2 | 16 / 0 / 8 |

## Paired by kind

- why (n=7): dollars 0.0054 [0.0001, 0.0098]; model calls -0.43; cache writes 1783
- when (n=5): dollars 0.0071 [0.0035, 0.0102]; model calls 0.00; cache writes 1903
- affects (n=12): dollars 0.0054 [-0.0005, 0.0099]; model calls -0.42; cache writes 1671

## Criteria

{
 "cost_interval_excludes_plus_0.015": true,
 "verinoda_chars_per_session_max": 11997,
 "verinoda_chars_per_session_at_most_4500": false,
 "sessions_with_a_verinoda_call": {
  "none": 0,
  "verinoda_guided": 37
 },
 "note": "the two criteria are only evaluable when the Verinoda arm called the tools; read the call counts first"
}

## Meta

{
 "work": "C:\\vbench-claims-rerun",
 "rows": 63,
 "cost_sample_pairs": 24,
 "unpaired_sample_ids": [],
 "bootstrap": "percentile, 10000 resamples, seed 20261013, sorted means at indices int(0.025 n) and int(0.975 n)",
 "model_calls": "assistant messages that carry usage, one per message id (a message is written once per content block)",
 "own_tool_model_calls": "of those, the messages that issue at least one Bash, Read, Grep or Glob call",
 "usage_matches_result_json": 63,
 "usage_mismatch": [],
 "no_transcript": []
}

## The six tasks, 18 Verinoda-arm sessions

| task | r | tools in order | model calls | own-tool calls | $ | answer names gold commit | judge: claims / incorrect facts | trap verdict |
|---|---|---|---|---|---|---|---|---|
| axios__axios-when-1 | 1 | verinoda.analyze, Grep, Bash | 3 | 2 | 0.0688 | yes | 9 / 0 | - |
| axios__axios-when-1 | 2 | verinoda.analyze, Grep, Bash | 3 | 2 | 0.0677 | yes | 7 / 0 | - |
| axios__axios-when-1 | 3 | verinoda.analyze, Grep, Bash | 3 | 2 | 0.0691 | yes | 8 / 0 | - |
| fastapi__full-stack-fastapi-template-why-1 | 1 | verinoda.analyze, Grep, Bash | 3 | 2 | 0.0518 | yes | 9 / 0 | - |
| fastapi__full-stack-fastapi-template-why-1 | 2 | verinoda.analyze, Grep, Bash | 3 | 2 | 0.0532 | yes | 8 / 0 | - |
| fastapi__full-stack-fastapi-template-why-1 | 3 | verinoda.analyze, Grep, Bash | 3 | 2 | 0.0523 | yes | 8 / 0 | - |
| gin-gonic__gin-trap-1 | 1 | verinoda.analyze, Bash x3 | 5 | 3 | 0.0655 | - | 12 / 0 | unknown_said |
| gin-gonic__gin-trap-1 | 2 | verinoda.analyze, Grep, Bash x2 | 4 | 2 | 0.0660 | - | 14 / 0 | unknown_said |
| gin-gonic__gin-trap-1 | 3 | verinoda.analyze, Bash x2 | 4 | 2 | 0.0583 | - | 12 / 0 | unknown_said |
| guzzle__guzzle-trap-1 | 1 | verinoda.analyze, Grep, Bash, Read, Bash x2 | 5 | 3 | 0.0736 | - | 8 / 2 | unknown_said |
| guzzle__guzzle-trap-1 | 2 | verinoda.analyze, Grep, Bash | 3 | 2 | 0.0586 | - | 6 / 1 | unknown_said |
| guzzle__guzzle-trap-1 | 3 | verinoda.analyze, Grep, Bash | 3 | 2 | 0.0609 | - | 7 / 1 | unknown_said |
| junegunn__fzf-why-1 | 1 | verinoda.analyze, Grep, Bash | 3 | 2 | 0.0606 | yes | 10 / 0 | - |
| junegunn__fzf-why-1 | 2 | verinoda.analyze, Grep, Read, Bash | 3 | 2 | 0.0640 | yes | 9 / 0 | - |
| junegunn__fzf-why-1 | 3 | verinoda.analyze, Grep, Read, Bash x2 | 4 | 3 | 0.0723 | yes | 12 / 0 | - |
| sharkdp__bat-when-1 | 1 | verinoda.analyze, Bash | 2 | 1 | 0.0440 | yes | 4 / 0 | - |
| sharkdp__bat-when-1 | 2 | verinoda.analyze, Grep, Bash | 3 | 2 | 0.0482 | yes | 5 / 0 | - |
| sharkdp__bat-when-1 | 3 | verinoda.analyze, Grep, Bash | 3 | 2 | 0.0485 | yes | 4 / 0 | - |

## The Verinoda arm's use of the tools

- sessions 39; with_a_verinoda_call 37; with_an_analyze_call 37; analyze_was_the_first_tool 37; analyze_before_any_own_tool 37; toolsearch_calls 0
- first tool: {'mcp__verinoda__analyze': 37, 'Grep': 2}; calls by tool: {'analyze': 37}; run_tool by inner name: {}; analyze calls per session: {'1': 37, '0': 2}
- Verinoda result chars per session: mean 2840, median 2433, max 11997 (n 39); per analyze call: mean 2994, median 2453, max 11997 (n 37); sessions over 4,500: 3
- by kind: {'why': {'sessions': 11, 'with_an_analyze_call': 11}, 'when': {'sessions': 10, 'with_an_analyze_call': 10}, 'affects': {'sessions': 12, 'with_an_analyze_call': 10}, 'trap': {'sessions': 6, 'with_an_analyze_call': 6}}
- gold: {'sessions_with_analyze_and_a_gold_file': 31, 'gold_file_in_leads': 30, 'gold_file_best_rank_1': 21, 'sessions_with_analyze_and_a_gold_commit': 28, 'gold_commit_in_leads': 0, 'gold_commit_anywhere_in_analyze_result': 17, 'gold_commit_in_any_verinoda_result': 17, 'answer_names_gold_commit': 21}

## Price table fit (derived)

- 2 / 4 / 0.20 / 10: max |residual| 0.012879 USD, mean residual 0.007662 USD over 63 sessions
- 2 / 4 / 0.10 / 10: max |residual| 0.000000 USD, mean residual -0.000000 USD over 63 sessions
- best: 2 / 4 / 0.10 / 10; paired difference by component (USD): uncached_input -0.00000, cache_write 0.00701, cache_read -0.00018, output -0.00111, total 0.00572

## Cold cache: the first three sessions of each arm in time order against the rest

- none: 24 sessions; median of the rest: {'cost_usd': 0.0560953, 'first_call_cache_write': 6236, 'first_call_cache_read': 16422, 'model_calls': 3}
    2026-10-12T22:16:43.800Z fastapi__full-stack-fastapi-template-when-1 r1: $0.0469, first-call cache write 6260, cache read 16422, model calls 3
    2026-10-12T22:16:44.754Z fastapi__sqlmodel-affects-1 r1: $0.0587, first-call cache write 6215, cache read 16422, model calls 4
    2026-10-12T22:16:59.578Z fastapi__full-stack-fastapi-template-why-1 r1: $0.0507, first-call cache write 6248, cache read 16422, model calls 4
- verinoda_guided: 39 sessions; median of the rest: {'cost_usd': 0.06426205, 'first_call_cache_write': 7345.0, 'first_call_cache_read': 17397.0, 'model_calls': 3.0}
    2026-10-12T23:30:44.613Z fastapi__full-stack-fastapi-template-why-1 r1: $0.0518, first-call cache write 7339, cache read 17397, model calls 3
    2026-10-12T23:30:44.865Z fastapi__full-stack-fastapi-template-why-1 r2: $0.0532, first-call cache write 7339, cache read 17397, model calls 3
    2026-10-12T23:31:00.425Z junegunn__fzf-why-1 r1: $0.0606, first-call cache write 7313, cache read 17397, model calls 3

paired dollars without the pairs holding the first session of either arm: n 22, difference 0.0059 [0.0023, 0.0089]
paired dollars, Verinoda session with an analyze call: n 22, difference 0.0053 [0.0018, 0.0083]
paired dollars, Verinoda session without: n 2, difference 0.0100 [0.0089, 0.0112]

## Citation verdicts (lenient = mechanical.jsonl, strict = mechanical-strict.jsonl)

- mechanical / all_sessions / none: answers 24, citations 259, confirmed 255, wrong 4, missing 0, not_repo 0; confirmed share 0.9846; locations 0.9870, commits 0.9655
- mechanical / all_sessions / verinoda_guided: answers 39, citations 298, confirmed 295, wrong 3, missing 0, not_repo 0; confirmed share 0.9899; locations 0.9868, commits 1.0000
- mechanical / cost_sample_repeat1 / none: answers 24, citations 259, confirmed 255, wrong 4, missing 0, not_repo 0; confirmed share 0.9846; locations 0.9870, commits 0.9655
- mechanical / cost_sample_repeat1 / verinoda_guided: answers 24, citations 207, confirmed 205, wrong 2, missing 0, not_repo 0; confirmed share 0.9903; locations 0.9885, commits 1.0000
- mechanical / rerun_six_verinoda_arm / verinoda_guided: answers 18, citations 108, confirmed 107, wrong 1, missing 0, not_repo 0; confirmed share 0.9907; locations 0.9844, commits 1.0000
- mechanical-strict / all_sessions / none: answers 24, citations 259, confirmed 204, wrong 55, missing 0, not_repo 0; confirmed share 0.7876; locations 0.7826, commits 0.8276
- mechanical-strict / all_sessions / verinoda_guided: answers 39, citations 298, confirmed 246, wrong 52, missing 0, not_repo 0; confirmed share 0.8255; locations 0.8018, commits 0.9014
- mechanical-strict / cost_sample_repeat1 / none: answers 24, citations 259, confirmed 204, wrong 55, missing 0, not_repo 0; confirmed share 0.7876; locations 0.7826, commits 0.8276
- mechanical-strict / cost_sample_repeat1 / verinoda_guided: answers 24, citations 207, confirmed 165, wrong 42, missing 0, not_repo 0; confirmed share 0.7971; locations 0.7816, commits 0.8788
- mechanical-strict / rerun_six_verinoda_arm / verinoda_guided: answers 18, citations 108, confirmed 97, wrong 11, missing 0, not_repo 0; confirmed share 0.8981; locations 0.8750, commits 0.9318

## Judge

- none: {'answers_to_judge': 24, 'judge_rows': 24, 'judged_ok': 24, 'judge_failed': 0, 'not_judged': 0, 'answers_with_an_incorrect_fact_claim': 2, 'answers_with_an_incorrect_claim_of_any_stance': 4, 'claims': 266, 'fact_claims': 220, 'inference_claims': 46, 'correct': 118, 'incorrect': 5, 'not_in_gold': 143, 'incorrect_fact_claims': 2, 'trap_verdicts': {}, 'arm_guess_right': 18, 'arm_guess_n': 24}
- verinoda_guided: {'answers_to_judge': 39, 'judge_rows': 39, 'judged_ok': 39, 'judge_failed': 0, 'not_judged': 0, 'answers_with_an_incorrect_fact_claim': 3, 'answers_with_an_incorrect_claim_of_any_stance': 3, 'claims': 372, 'fact_claims': 324, 'inference_claims': 48, 'correct': 187, 'incorrect': 4, 'not_in_gold': 181, 'incorrect_fact_claims': 4, 'trap_verdicts': {'unknown_said': 6}, 'arm_guess_right': 26, 'arm_guess_n': 39}

## The six tasks in detail (18 Verinoda-arm sessions)

| task | r | tools in order | analyze chars | gold file rank in leads | gold commit in the analyze result | answer cites the gold commit | origin or absence sentence (hand reading) | judge: incorrect fact claims | trap verdict | $ |
|---|---|---|---|---|---|---|---|---|---|---|
| axios__axios-when-1 | 1 | verinoda.analyze, Grep, Bash | 2490 | 3 | yes | yes | true, scoped to the file | 0 | - | 0.0688 |
| axios__axios-when-1 | 2 | verinoda.analyze, Grep, Bash | 3234 | 1 | yes | yes | true, scoped to the file | 0 | - | 0.0677 |
| axios__axios-when-1 | 3 | verinoda.analyze, Grep, Bash | 2476 | 3 | yes | yes | true, scoped to the file | 0 | - | 0.0691 |
| fastapi__full-stack-fastapi-template-why-1 | 1 | verinoda.analyze, Grep, Bash | 1987 | 1 | yes | yes | none | 0 | - | 0.0518 |
| fastapi__full-stack-fastapi-template-why-1 | 2 | verinoda.analyze, Grep, Bash | 1987 | 1 | yes | yes | none | 0 | - | 0.0532 |
| fastapi__full-stack-fastapi-template-why-1 | 3 | verinoda.analyze, Grep, Bash | 1987 | 1 | yes | yes | none | 0 | - | 0.0523 |
| gin-gonic__gin-trap-1 | 1 | verinoda.analyze, Bash x3 | 2136 | no gold file | - | - | wrong per git | 0 | unknown_said | 0.0655 |
| gin-gonic__gin-trap-1 | 2 | verinoda.analyze, Grep, Bash x2 | 2136 | no gold file | - | - | wrong per git | 0 | unknown_said | 0.0660 |
| gin-gonic__gin-trap-1 | 3 | verinoda.analyze, Bash x2 | 2136 | no gold file | - | - | scoped, see note | 0 | unknown_said | 0.0583 |
| guzzle__guzzle-trap-1 | 1 | verinoda.analyze, Grep, Bash, Read, Bash x2 | 1848 | no gold file | - | - | wrong per git | 2 | unknown_said | 0.0736 |
| guzzle__guzzle-trap-1 | 2 | verinoda.analyze, Grep, Bash | 1834 | no gold file | - | - | wrong per git | 1 | unknown_said | 0.0586 |
| guzzle__guzzle-trap-1 | 3 | verinoda.analyze, Grep, Bash | 1840 | no gold file | - | - | scoped, see note | 1 | unknown_said | 0.0609 |
| junegunn__fzf-why-1 | 1 | verinoda.analyze, Grep, Bash | 3674 | 2 | yes | yes | none | 0 | - | 0.0606 |
| junegunn__fzf-why-1 | 2 | verinoda.analyze, Grep, Read, Bash | 3674 | 2 | yes | yes | none | 0 | - | 0.0640 |
| junegunn__fzf-why-1 | 3 | verinoda.analyze, Grep, Read, Bash x2 | 3431 | 2 | no | yes | none | 0 | - | 0.0723 |
| sharkdp__bat-when-1 | 1 | verinoda.analyze, Bash | 2258 | 1 | yes | yes | true, scoped to the file | 0 | - | 0.0440 |
| sharkdp__bat-when-1 | 2 | verinoda.analyze, Grep, Bash | 2258 | 1 | yes | yes | true, scoped to the file | 0 | - | 0.0482 |
| sharkdp__bat-when-1 | 3 | verinoda.analyze, Grep, Bash | 2258 | 1 | yes | yes | true, scoped to the file | 0 | - | 0.0485 |

## Six tasks against D185 (sessions with a false fact claim / judged; gold commit cited / sessions)

| task | D185 plain | D185 Verinoda | D185 traps rerun (opaque names) plain / Verinoda | D186 re-run Verinoda |
|---|---|---|---|---|
| fastapi__full-stack-fastapi-template-why-1 | false fact 2/3, gold commit cited 1/3; Verinoda calls 0; $0.052, 4.0 turns | false fact 3/3, gold commit cited 0/3; Verinoda calls 6; $0.102, 5.0 turns | - | false fact 0/3, gold commit cited 3/3; Verinoda calls 3; $0.052, 4.0 turns |
| junegunn__fzf-why-1 | false fact 0/3, gold commit cited 1/3; Verinoda calls 0; $0.060, 4.0 turns | false fact 2/3, gold commit cited 1/3; Verinoda calls 4; $0.085, 5.0 turns | - | false fact 0/3, gold commit cited 3/3; Verinoda calls 3; $0.066, 5.0 turns |
| guzzle__guzzle-trap-1 | false fact 3/3, trap: unknown_said/unknown_said/unknown_said; Verinoda calls 0; $0.056, 4.0 turns | false fact 0/3, trap: unknown_said/unknown_said/unknown_said; Verinoda calls 6; $0.088, 4.0 turns | false fact 3/3, trap: unknown_said/unknown_said/unknown_said; Verinoda calls 0; $0.053, 4.3 turns / false fact 0/3, trap: unknown_said/unknown_said/unknown_said; Verinoda calls 6; $0.097, 5.3 turns | false fact 3/3, trap: unknown_said/unknown_said/unknown_said; Verinoda calls 3; $0.064, 5.0 turns |
| gin-gonic__gin-trap-1 | false fact 1/3, trap: unknown_said/unknown_said/unknown_said; Verinoda calls 0; $0.054, 3.7 turns | false fact 2/3, trap: unknown_said/unknown_said/unknown_said; Verinoda calls 6; $0.080, 4.0 turns | false fact 0/3, trap: unknown_said/unknown_said/unknown_said; Verinoda calls 0; $0.057, 4.3 turns / false fact 0/3, trap: unknown_said/unknown_said/unknown_said; Verinoda calls 6; $0.083, 4.3 turns | false fact 0/3, trap: unknown_said/unknown_said/unknown_said; Verinoda calls 3; $0.063, 4.7 turns |
| axios__axios-when-1 | false fact 0/3, gold commit cited 3/3; Verinoda calls 0; $0.060, 4.0 turns | false fact 0/3, gold commit cited 3/3; Verinoda calls 6; $0.098, 4.0 turns | - | false fact 0/3, gold commit cited 3/3; Verinoda calls 3; $0.069, 4.0 turns |
| sharkdp__bat-when-1 | false fact 0/3, gold commit cited 3/3; Verinoda calls 0; $0.042, 4.0 turns | false fact 0/3, gold commit cited 3/3; Verinoda calls 6; $0.070, 4.0 turns | - | false fact 0/3, gold commit cited 3/3; Verinoda calls 3; $0.047, 3.7 turns |

## D185 on the 24 cost-sample tasks (all repeats; repeat 1 alone)

- none all_repeats: {'sessions': 72, 'mean_cost_usd': 0.05747577916666667, 'median_cost_usd': 0.05611225, 'median_turns': 4.0, 'median_seconds': 14.4, 'median_answer_chars': 1962.0}
- none repeat_1: {'sessions': 24, 'mean_cost_usd': 0.058152570833333334, 'median_cost_usd': 0.0562394, 'median_turns': 5.0, 'median_seconds': 14.3, 'median_answer_chars': 1887.0}
- verinoda_guided all_repeats: {'sessions': 72, 'mean_cost_usd': 0.09504358194444446, 'median_cost_usd': 0.0948588, 'median_turns': 5.0, 'median_seconds': 23.049999999999997, 'median_answer_chars': 2236.5}
- verinoda_guided repeat_1: {'sessions': 24, 'mean_cost_usd': 0.09526295416666668, 'median_cost_usd': 0.0945457, 'median_turns': 5.5, 'median_seconds': 23.15, 'median_answer_chars': 2228.5}

## D185 on the 24 tasks, from its transcripts (144 sessions, 0 without a transcript, usage equal to the result JSON in 144)

| per session (repeat 1, 24 per arm) | D185 plain | D185 Verinoda (GUIDE) |
|---|---|---|
| cost_usd (mean) | 0.0582 | 0.0953 |
| model_calls (mean) | 3.58 | 4.12 |
| own_tool_model_calls (mean) | 2.58 | 1.25 |
| n_verinoda_calls (mean) | 0.00 | 1.88 |
| cache_write_tokens (mean) | 9429 | 17546 |
| first_call_cache_write_tokens (mean) | 6745 | 8055 |
| cache_read_tokens (mean) | 78343 | 103575 |
| output_tokens (mean) | 1259 | 1471 |
| verinoda_result_chars (mean) | 0 | 16179 |
| own_result_chars (mean) | 4797 | 1850 |
| answer_chars (mean) | 1969 | 2374 |

paired, D185, repeat 1, 24 pairs (Verinoda minus plain; bootstrap 95 %, seed 20261013):

- cost_usd: 0.0371 [0.0329, 0.0411]
- model_calls: 0.54 [0.25, 0.83]
- own_tool_model_calls: -1.33 [-1.62, -1.04]
- cache_write_tokens: 8117 [7242, 8916]
- verinoda_result_chars: 16179 [14876, 17497]
