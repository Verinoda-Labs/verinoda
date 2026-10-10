# SWE-bench Lite, 100 instances: Claude Code alone against Claude Code with Verinoda Symbiosis (2026-10-10)

Pre-registered in `benchmarks/agent_compare/DESIGN_SWEBENCH.md` (the first 100 instances of its fixed order; the 4-instance pilot
is among them). One headless `claude -p` session per instance and arm, `claude-sonnet-5-5`, the same tools; the arm
`verinoda_guided` has Verinoda's index, MCP server, the verinoda-live mod and a three-step protocol in its prompt (load the tools,
`analyze` before any search, `code_check` after each edit). Harness `swebench_prepare.py`, `swebench_run.py`, scorer
`swebench_score.py`; files here: `results.jsonl` (one row per session, with the patch), `predictions-*.jsonl` (SWE-bench format),
`tasks.json`, `builds.json` (index set-up times), `config.json`, `summary.json`.

## The resolved share was NOT measured

The study's main measure needs the official evaluation (Docker images or `sb-cli`, `benchmarks/agent_compare/SWEBENCH_EVAL.md`),
which the machine that ran it cannot do. **Nothing below says which arm solved more instances.** The numbers are proxies and
costs. No project's dependencies were installed, so neither agent could run a project's tests; absolute results are not
comparable with the leaderboard.

## What was measured (100 instances, both arms each)

| | plain (`none`) | with Verinoda (`verinoda_guided`) |
|---|---|---|
| Patch not empty | 100 | 100 |
| Patch applies to the base commit | 100 | 99 (`sympy__sympy-15346` does not) |
| Patch touches the gold patch's file(s) | 90 | 92 |
| Patch with extra files | 13 | 9 |
| Test files edited | 0 | 0 |
| Session errors | 0 | 0 |
| Verinoda tools called | - | `analyze` 100, `code_check` 98, before any code tool 100 |
| Cost, total | $7.94 | $12.88 |
| Input tokens, total | 13.1 M | 20.3 M |
| Median turns / seconds | 5 / 36 | 7 / 91 |

Paired per instance (Verinoda arm minus plain arm, bootstrap 95 % interval over the 100 instances):

| | mean difference | interval | more / same / less in the Verinoda arm |
|---|---|---|---|
| Dollars | +0.049 | 0.043 to 0.056 | 98 / 0 / 2 |
| Turns | +2.3 | 1.9 to 2.7 | 89 / 4 / 7 |
| Input tokens | +71,600 | 56,800 to 85,300 | 96 / 0 / 4 |
| Seconds | +44.5 | 28.7 to 60.4 | 80 / 0 / 20 |
| Patch lines | +1.3 | -0.3 to 3.0 | 35 / 43 / 22 |
| Extra files | -0.04 | -0.10 to 0.01 | 2 / 92 / 6 |

The patches: 90 of 100 pairs changed the same set of files, 31 are identical. The gold patch's files were covered by the Verinoda
arm and not by the plain one in 4 instances and the other way round in 2 (6 differ: `sympy__sympy-18087`, `-13031`, `-13915`,
`-15346`, `scikit-learn__scikit-learn-25500`, `mwaskom__seaborn-2848`); at 6 differing pairs this is no difference one can
distinguish from chance. Covering a gold file is not correctness.

**Read:** Verinoda is used in every session of its arm (the protocol works), it costs about 60 % more dollars, 55 % more input
tokens and 2.3 more turns per instance, in 98 of 100 instances, and nothing in the proxies shows a better patch. Whether its
patches resolve more instances is unknown until the evaluation is run.

Seconds are not a clean comparison: the plain arm ran 3 sessions at once and the Verinoda arm 2, on one machine.

## Limits

One session per instance and arm (the agent's own variation is inside every difference); the sample is the first 100 of a seeded
order, 35 of them django and 32 sympy; the Verinoda arm's protocol is a manual steer and the tool is its authors' own; a model
may know SWE-bench's fixes (both arms share that). The harness's first two pilot runs (line-ending and instruction problems)
were discarded; their sessions are not in `results.jsonl`.
