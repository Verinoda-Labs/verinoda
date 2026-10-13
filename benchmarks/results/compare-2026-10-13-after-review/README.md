# The eight public sets after the final review's fix pass (575b2a5), against the after-D186 run

Why: the final whole-branch review of D186 (`docs/DESIGN.md` 158.5) led to a fix pass that touched the analysis engine
(the why-unknown's window, a decision document that only names the symbol, the stemmer's inflections, the refresh
rule for a shrunk `.mcp.json`), history (`git log -L` with `diff.renames=true`, the symbol scope line, the path check,
the sub-project `git show`) and the server (symbol-mode `history_search` under the lock). The no-model benchmark that
produces the Graphify comparison was run again on the fixed tree (commit 575b2a5), the same flags as
`compare-2026-10-13-after-d186/` and the 2026-10-02 baseline: `--llm none`, `--repeat 1`, no `--graphify-cmd`.

Result: **no fact lost, no fact gained**, per question, on all eight sets against `compare-2026-10-13-after-d186/`:
`verinoda_retrieve_text` 284/319 -> 284/319, `verinoda_analyze` 285/319 -> 285/319. Tokens per question (chars/4):
identical on every set for both approaches, except `verinoda_analyze` on orders_app_tr, 1,471 -> 1,475 (the mean over
its questions; the fix pass changed the wording of a why-unknown). The comparison script is
`benchmarks/agent_compare/compare_sets.py` (fact ids per question and `score.tokens`, approach by approach); its output
is the three lines above. It does not read `score.sha256`, which differs on every `verinoda_analyze` row between the two
folders while `chars` differs on one: the hash covers text the comparison does not (not examined).

Files: `<set>.json` (schema 3 result per set), `<set>.log`, `run_all.sh` (the commands; `<OUT>` was this folder's
scratch copy), `run_all.log` (start and end lines with the wall time per set: 8-52 s).

Measured on: Windows 11, Python 3.12.0, git 2.53.0, 6 CPUs, with the D186 re-run's `claude -p` sessions running on
the same machine (timings are not compared). Not measured: the sets with Louvain clustering (a venv without
graspologic-native); the sets through the MCP lead shape (the benchmark calls the engine in-process and renders the
CLI text, by design).
