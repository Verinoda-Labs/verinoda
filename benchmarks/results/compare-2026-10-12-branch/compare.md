# Branch rerun against the after-fix baseline, fact by fact

Baseline: `benchmarks/results/compare-2026-10-02/after-fix/<set>.json` (Verinoda at 5999912, Python 3.13.14, `--repeat 1`, `--llm none`, no `--graphify-cmd`). Rerun: this folder, same flags, on branch `symbiosis-redesign-2026-10-12` (see the environment table for the commit). Facts: `summary.<approach>.facts_found` / `facts_total`; per question: `approaches.<approach>.score.facts.found`. Tokens: chars/4 (`summary.<approach>.tokens_mean`, `score.tokens`).

## Environment

| set | python baseline / now | verinoda commit baseline / now | run date (UTC) now |
|---|---|---|---|
| orders_app | 3.13.14 / 3.12.0 | 5999912 / c678d46 | 2026-10-12T16:37:22+00:00 |
| orders_app_tr | 3.13.14 / 3.12.0 | 5999912 / c678d46 | 2026-10-12T16:37:27+00:00 |
| glow_mod | 3.13.14 / 3.12.0 | 5999912 / c678d46 | 2026-10-12T16:37:33+00:00 |
| forge_mod | 3.13.14 / 3.12.0 | 5999912 / c678d46 | 2026-10-12T16:37:41+00:00 |
| graphify_core | 3.13.14 / 3.12.0 | 5999912 / c678d46 | 2026-10-12T16:37:53+00:00 |
| graphify_core_tr | 3.13.14 / 3.12.0 | 5999912 / c678d46 | 2026-10-12T16:38:38+00:00 |
| heldout_repoatlas | 3.13.14 / 3.12.0 | 5999912 / c678d46 | 2026-10-12T16:39:22+00:00 |
| verinoda_user_tr | 3.13.14 / 3.12.0 | 5999912 / c678d46 | 2026-10-12T16:39:51+00:00 |

`environment.verinoda_package_changes_vs_commit` in every rerun file: [] (the measured package is the committed code of the recorded commit, no uncommitted change). The four analyze commits the review is about (6036da0, 00c89b7, c5829bd, ca1f8d3) are ancestors of the measured commit c678d46 (`git merge-base --is-ancestor`, each yes). Vendored Graphify renderer 20a20d30 in both.

Machine fields (`environment`, baseline / now): os Windows-11-10.0.26200-SP0 / Windows-11-10.0.26200-SP0; processor AMD64 Family 25 Model 80 Stepping 0, AuthenticAMD / AMD64 Family 25 Model 97 Stepping 2, AuthenticAMD; cpu_count 16 / 6; git git version 2.54.0.windows.1 / git version 2.53.0.windows.1. The baseline README records other benchmarks running at the same time as it. Timings are not compared here.

Repository state: `git status --short` before the rerun showed no change (HEAD c678d46). `docs/drafts/2026-10-12-verinoda-lean-plan.md` has mtime 2026-10-12T16:39:36Z (while heldout_repoatlas was running); it was untracked (`??`) at the first status check after the rerun and committed as 4832c0f (219 insertions, that file only, no code) by the second check, when the status was clean. The harness writes nothing under `docs/`; the rerun changed no tracked file.

## Corpus check (baseline / now)

| set | files | bytes | source commit | snapshot | gold facts checked | corpus |
|---|---|---|---|---|---|---|
| orders_app | 11 / 11 | 4724 / 4724 | 5999912d / c678d461 | working tree (tracked + untracked, not ignored) / working tree (tracked + untracked, not ignored) | 32 / 32 | same files/bytes |
| orders_app_tr | 11 / 11 | 4724 / 4724 | 5999912d / c678d461 | working tree (tracked + untracked, not ignored) / working tree (tracked + untracked, not ignored) | 32 / 32 | same files/bytes |
| glow_mod | 37 / 37 | 33709 / 33709 | 5999912d / c678d461 | working tree (tracked + untracked, not ignored) / working tree (tracked + untracked, not ignored) | 50 / 50 | same files/bytes |
| forge_mod | 55 / 55 | 53429 / 53429 | 5999912d / c678d461 | working tree (tracked + untracked, not ignored) / working tree (tracked + untracked, not ignored) | 68 / 68 | same files/bytes |
| graphify_core | 226 / 226 | 4679630 / 4679630 | 20a20d30 / 20a20d30 | working tree (tracked + untracked, not ignored) / working tree (tracked + untracked, not ignored) | 37 / 37 | same files/bytes |
| graphify_core_tr | 226 / 226 | 4679630 / 4679630 | 20a20d30 / 20a20d30 | working tree (tracked + untracked, not ignored) / working tree (tracked + untracked, not ignored) | 37 / 37 | same files/bytes |
| heldout_repoatlas | 106 / 106 | 2189328 / 2189328 | 5999912d / c678d461 | working tree (tracked + untracked, not ignored) / working tree (tracked + untracked, not ignored) | 33 / 33 | same files/bytes |
| verinoda_user_tr | 78 / 78 | 2132839 / 2132839 | 3bd1b94a / 3bd1b94a | git archive 3bd1b94a5cfcd8689d423bcb0dafa06974f8769f / git archive 3bd1b94a5cfcd8689d423bcb0dafa06974f8769f | 30 / 30 | same files/bytes |

## Facts found and tokens per question, per set and approach

| set | approach | facts baseline | facts now | delta | tokens/q baseline | tokens/q now | delta | errors baseline / now |
|---|---|---|---|---|---|---|---|---|
| orders_app | verinoda_retrieve_text | 32/32 | 32/32 | +0 | 846.0 | 846.0 | +0.0 | 0 / 0 |
| orders_app | verinoda_analyze | 32/32 | 32/32 | +0 | 1449.7 | 1429.1 | -20.6 | 0 / 0 |
| orders_app_tr | verinoda_retrieve_text | 32/32 | 32/32 | +0 | 843.2 | 843.2 | +0.0 | 0 / 0 |
| orders_app_tr | verinoda_analyze | 32/32 | 32/32 | +0 | 1491.5 | 1470.8 | -20.7 | 0 / 0 |
| glow_mod | verinoda_retrieve_text | 48/50 | 48/50 | +0 | 1484.5 | 1484.5 | +0.0 | 0 / 0 |
| glow_mod | verinoda_analyze | 48/50 | 48/50 | +0 | 2157.3 | 2156.6 | -0.7 | 0 / 0 |
| forge_mod | verinoda_retrieve_text | 67/68 | 67/68 | +0 | 1461.1 | 1461.1 | +0.0 | 0 / 0 |
| forge_mod | verinoda_analyze | 67/68 | 67/68 | +0 | 2128.1 | 2125.9 | -2.2 | 0 / 0 |
| graphify_core | verinoda_retrieve_text | 36/37 | 36/37 | +0 | 1473.1 | 1473.1 | +0.0 | 0 / 0 |
| graphify_core | verinoda_analyze | 36/37 | 36/37 | +0 | 2031.0 | 2021.4 | -9.6 | 0 / 0 |
| graphify_core_tr | verinoda_retrieve_text | 31/37 | 31/37 | +0 | 1431.0 | 1431.0 | +0.0 | 0 / 0 |
| graphify_core_tr | verinoda_analyze | 31/37 | 31/37 | +0 | 2026.8 | 2010.4 | -16.4 | 0 / 0 |
| heldout_repoatlas | verinoda_retrieve_text | 25/33 | 25/33 | +0 | 1431.4 | 1431.4 | +0.0 | 0 / 0 |
| heldout_repoatlas | verinoda_analyze | 26/33 | 26/33 | +0 | 1956.1 | 1956.1 | +0.0 | 0 / 0 |
| verinoda_user_tr | verinoda_retrieve_text | 13/30 | 13/30 | +0 | 1432.8 | 1432.8 | +0.0 | 0 / 0 |
| verinoda_user_tr | verinoda_analyze | 13/30 | 13/30 | +0 | 1740.8 | 1730.2 | -10.6 | 0 / 0 |

### Totals over the sets that ran

| approach | facts baseline | facts now | tokens/q baseline | tokens/q now |
|---|---|---|---|---|
| verinoda_retrieve_text | 284/319 | 284/319 | 1312.9 | 1312.9 |
| verinoda_analyze | 285/319 | 285/319 | 1889.1 | 1879.7 |

## Questions whose found-fact set differs

None: every question of every set that ran has the same found-fact set as the baseline, for both approaches.

## Tokens per question (baseline -> now)

172 question/approach records compared; 158 have the same token count as the baseline. The 14 that differ:

| set | approach | question | tokens baseline | tokens now | delta |
|---|---|---|---|---|---|
| orders_app | verinoda_analyze | q05 | 1301 | 1237 | -64 |
| orders_app | verinoda_analyze | q07 | 992 | 922 | -70 |
| orders_app | verinoda_analyze | q09 | 1354 | 1282 | -72 |
| orders_app_tr | verinoda_analyze | q05 | 1490 | 1426 | -64 |
| orders_app_tr | verinoda_analyze | q07 | 1241 | 1170 | -71 |
| orders_app_tr | verinoda_analyze | q09 | 1425 | 1353 | -72 |
| glow_mod | verinoda_analyze | q05 | 2146 | 2137 | -9 |
| forge_mod | verinoda_analyze | q03 | 2039 | 2009 | -30 |
| graphify_core | verinoda_analyze | g06 | 1831 | 1745 | -86 |
| graphify_core_tr | verinoda_analyze | g02 | 2049 | 2040 | -9 |
| graphify_core_tr | verinoda_analyze | g05 | 2346 | 2295 | -51 |
| graphify_core_tr | verinoda_analyze | g06 | 1747 | 1660 | -87 |
| verinoda_user_tr | verinoda_analyze | u08 | 1638 | 1596 | -42 |
| verinoda_user_tr | verinoda_analyze | u09 | 1873 | 1788 | -85 |

- verinoda_retrieve_text: 0 of 86 questions differ; per-set means in the table above.

- verinoda_analyze: 14 of 86 questions differ; per-set means in the table above.

## Cross-check against the harness's `fact_changes`

Agrees for every set and approach that ran (lost and gained `question/fact` ids identical).

## Verdict

**No fact lost** on the sets that ran, for either approach.
No fact gained.

Sets not run or not compared:
- none: all eight sets ran with status `ok`.

## Commands run

From `run_all.sh` (run from the repository root, `.venv/Scripts/python.exe`):

```
python -m verinoda.benchmark run --repo examples/orders_app --questions verinoda/benchmark/questions/orders_app.json --out C:/Users/ozcin/AppData/Local/Temp/claude/C--Users-ozcin-Desktop-verinoda-symbiosis/5da6b32a-3f88-419e-8ce7-aa28c22daf16/scratchpad/bench-branch/orders_app.json --llm none --repeat 1
python -m verinoda.benchmark run --repo examples/orders_app --questions verinoda/benchmark/questions/orders_app_tr.json --out C:/Users/ozcin/AppData/Local/Temp/claude/C--Users-ozcin-Desktop-verinoda-symbiosis/5da6b32a-3f88-419e-8ce7-aa28c22daf16/scratchpad/bench-branch/orders_app_tr.json --llm none --repeat 1
python -m verinoda.benchmark run --repo examples/glow_mod --questions verinoda/benchmark/questions/glow_mod.json --out C:/Users/ozcin/AppData/Local/Temp/claude/C--Users-ozcin-Desktop-verinoda-symbiosis/5da6b32a-3f88-419e-8ce7-aa28c22daf16/scratchpad/bench-branch/glow_mod.json --llm none --repeat 1
python -m verinoda.benchmark run --repo examples/forge_mod --questions verinoda/benchmark/questions/forge_mod.json --out C:/Users/ozcin/AppData/Local/Temp/claude/C--Users-ozcin-Desktop-verinoda-symbiosis/5da6b32a-3f88-419e-8ce7-aa28c22daf16/scratchpad/bench-branch/forge_mod.json --llm none --repeat 1
python -m verinoda.benchmark run --repo C:/Users/ozcin/Desktop/RepoAtlas/upstream-graphify --questions verinoda/benchmark/questions/graphify_core.json --out C:/Users/ozcin/AppData/Local/Temp/claude/C--Users-ozcin-Desktop-verinoda-symbiosis/5da6b32a-3f88-419e-8ce7-aa28c22daf16/scratchpad/bench-branch/graphify_core.json --llm none --repeat 1
python -m verinoda.benchmark run --repo C:/Users/ozcin/Desktop/RepoAtlas/upstream-graphify --questions verinoda/benchmark/questions/graphify_core_tr.json --out C:/Users/ozcin/AppData/Local/Temp/claude/C--Users-ozcin-Desktop-verinoda-symbiosis/5da6b32a-3f88-419e-8ce7-aa28c22daf16/scratchpad/bench-branch/graphify_core_tr.json --llm none --repeat 1
python -m verinoda.benchmark run --repo benchmarks/corpora/heldout_repoatlas_7371990 --questions verinoda/benchmark/questions/heldout_repoatlas.json --out C:/Users/ozcin/AppData/Local/Temp/claude/C--Users-ozcin-Desktop-verinoda-symbiosis/5da6b32a-3f88-419e-8ce7-aa28c22daf16/scratchpad/bench-branch/heldout_repoatlas.json --llm none --repeat 1
python -m verinoda.benchmark run --repo . --at 3bd1b94a5cfcd8689d423bcb0dafa06974f8769f --questions verinoda/benchmark/questions/verinoda_user_tr.json --out C:/Users/ozcin/AppData/Local/Temp/claude/C--Users-ozcin-Desktop-verinoda-symbiosis/5da6b32a-3f88-419e-8ce7-aa28c22daf16/scratchpad/bench-branch/verinoda_user_tr.json --llm none --repeat 1
```

Timing and exit codes (`run_all.log`):

```
[2026-10-12T16:37:21Z] branch=symbiosis-redesign-2026-10-12 head=c678d4610991b6f4e2f9154e79818753e4ff2ea2
python 3.12.0
[2026-10-12T16:37:27Z] END orders_app rc=0 seconds=6
[2026-10-12T16:37:33Z] END orders_app_tr rc=0 seconds=6
[2026-10-12T16:37:40Z] END glow_mod rc=0 seconds=7
[2026-10-12T16:37:49Z] END forge_mod rc=0 seconds=9
[2026-10-12T16:38:35Z] END graphify_core rc=0 seconds=46
[2026-10-12T16:39:20Z] END graphify_core_tr rc=0 seconds=45
[2026-10-12T16:39:49Z] END heldout_repoatlas rc=0 seconds=29
[2026-10-12T16:40:21Z] END verinoda_user_tr rc=0 seconds=32
[2026-10-12T16:40:21Z] ALL DONE
```

Comparison (from the repository root; `<OUT>` is this folder):

```
python -m verinoda.benchmark compare benchmarks/results/compare-2026-10-02/after-fix/orders_app.json <OUT>/orders_app.json > <OUT>/compare-orders_app.txt
python -m verinoda.benchmark compare benchmarks/results/compare-2026-10-02/after-fix/orders_app_tr.json <OUT>/orders_app_tr.json > <OUT>/compare-orders_app_tr.txt
python -m verinoda.benchmark compare benchmarks/results/compare-2026-10-02/after-fix/glow_mod.json <OUT>/glow_mod.json > <OUT>/compare-glow_mod.txt
python -m verinoda.benchmark compare benchmarks/results/compare-2026-10-02/after-fix/forge_mod.json <OUT>/forge_mod.json > <OUT>/compare-forge_mod.txt
python -m verinoda.benchmark compare benchmarks/results/compare-2026-10-02/after-fix/graphify_core.json <OUT>/graphify_core.json > <OUT>/compare-graphify_core.txt
python -m verinoda.benchmark compare benchmarks/results/compare-2026-10-02/after-fix/graphify_core_tr.json <OUT>/graphify_core_tr.json > <OUT>/compare-graphify_core_tr.txt
python -m verinoda.benchmark compare benchmarks/results/compare-2026-10-02/after-fix/heldout_repoatlas.json <OUT>/heldout_repoatlas.json > <OUT>/compare-heldout_repoatlas.txt
python -m verinoda.benchmark compare benchmarks/results/compare-2026-10-02/after-fix/verinoda_user_tr.json <OUT>/verinoda_user_tr.json > <OUT>/compare-verinoda_user_tr.txt
python <OUT>/compare.py   # this file: compare.md, cross-checked against verinoda.benchmark.report.fact_changes
```
