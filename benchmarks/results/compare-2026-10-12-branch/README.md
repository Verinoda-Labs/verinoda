# The eight public sets on the redesign branch at c678d46, against the 2026-10-02 after-fix baseline

Why: the branch `symbiosis-redesign-2026-10-12` changed `verinoda.analysis.analyze` (the why/when handler reads 20
commits and claims only reason-stating commits, the top-level status is derived from the sub-questions, weak claims
leave the answer list, Verinoda's own files are not index changes: commits 6036da0, 00c89b7, c5829bd, ca1f8d3), and
six why-questions sit in the eight sets. The design review (D186) asked for the no-model headline to be re-measured
before anything else changed. No model is in the loop; `--llm none`, `--repeat 1`, no `--graphify-cmd`.

Result: **no fact lost, no fact gained** for `verinoda_retrieve_text` (284/319 -> 284/319) and `verinoda_analyze`
(285/319 -> 285/319), per question, on all eight sets (the harness's own `fact_changes` agrees). Tokens per question:
retrieve_text identical on all 86 questions; analyze identical on 72, lower on 14 (-9 to -87 tokens, chars/4), higher
on none; mean 1,889.1 -> 1,879.7.

Files: `<set>.json` (schema 3 result per set), `<set>.log`, `compare-<set>.txt` (`python -m verinoda.benchmark
compare` against the baseline), `compare.md` (every table: environment, corpus check, facts and tokens per set and
approach, the 14 token deltas, cross-check, commands), `compare.py` (its generator), `run_all.sh`, `run_all.log`.

Measured on: Windows 11, Python 3.12.0 (baseline 3.13.14), git 2.53.0, 6 CPUs; corpora byte-identical to the
baseline (file counts and bytes in `compare.md`); graphify_core from the local upstream checkout at 20a20d30.
Timings are not compared (different machine state). The run was made by a delegated session with the commands in
`run_all.sh`; `compare.md`'s note about `docs/drafts/2026-10-12-verinoda-lean-plan.md` describes a file the main
session committed (4832c0f) while the run was going; the harness writes nothing under `docs/`.

Not measured: the sets after the rest of D186 ships (that run is Task 8 of the plan); Louvain clustering (this run
used Leiden via graspologic-native, as the baseline did).
