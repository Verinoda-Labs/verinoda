# SWE-bench Lite pilot: Claude Code with and without Verinoda (2026-10-10)

Four instances (sphinx-doc__sphinx-8801, django__django-16873, sympy__sympy-23262, sphinx-doc__sphinx-7738), one session
per instance and arm, `claude-sonnet-5-5`; the design is `benchmarks/agent_compare/DESIGN_SWEBENCH.md`, the harness
`swebench_prepare.py` and `swebench_run.py`. `results.jsonl` is one row per session (patch, files, gold overlap, cost, turns,
Verinoda tool calls), `predictions-*.jsonl` are in SWE-bench's format, `builds.json` the index set-up times.

**The resolved share was not measured** (no Docker on the machine that ran this): the predictions have to be evaluated with
the official harness, see `benchmarks/agent_compare/SWEBENCH_EVAL.md`. What the rows show: all 8 patches apply to the base
commit and change the gold patch's file; the Verinoda arm called `analyze` first and `code_check` after editing in all 4
sessions, cost $0.42 against $0.17 and took 24-90 s against 10-24 s. Four easy instances show no difference in quality.
The harness's first two runs (line-ending and instruction problems, see the design's pilot section) are not included.
`results.jsonl` holds session ids and the model's one-sentence replies; the dataset text in `tasks.json` is SWE-bench's.
