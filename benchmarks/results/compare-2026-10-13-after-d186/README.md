# The eight public sets after D186 (Verinoda Lean, waves 1 and 2 merged), against the 2026-10-02 after-fix baseline

Why: D186 changed the analysis engine's why/when handler and verdicts (D185's fixes), removed the upstream Graphify
CLI surface and the LLM layer from `verinoda/project_index`, moved `graspologic-native` to an extra (this machine's
venv still has it, so Leiden clustered here), and routed every git call through `verinoda.gitexec`. The no-model
benchmark that produces the Graphify comparison was run again on the merged tree (commit f34a223, the merge of plan
Task 3), the same flags as the baseline and as `compare-2026-10-12-branch/`: `--llm none`, `--repeat 1`, no
`--graphify-cmd`.

Result: **no fact lost, no fact gained**, per question, on all eight sets: `verinoda_retrieve_text` 284/319 ->
284/319, `verinoda_analyze` 285/319 -> 285/319. Tokens per question (chars/4): retrieve_text identical on every set;
analyze lower on orders_app (1,450 -> 1,429), orders_app_tr (1,492 -> 1,471), forge_mod (2,128 -> 2,126),
graphify_core (2,031 -> 2,021), graphify_core_tr (2,027 -> 2,010), verinoda_user_tr (1,741 -> 1,730), equal on
glow_mod and heldout_repoatlas; higher on none.

Files: `<set>.json` (schema 3 result per set), `<set>.log`, `run_all.sh` (the commands, `<OUT>` was this folder's
scratch copy), `run_all.log` (start and end lines with the wall time per set: 6-52 s).

Measured on: Windows 11, Python 3.12.0, git 2.53.0, 6 CPUs, with an integration test run going on the same machine
(timings are not compared). Not measured: the sets with Louvain clustering (a venv without graspologic-native); the
sets through the MCP lead shape (the benchmark calls the engine in-process and renders the CLI text, by design).
