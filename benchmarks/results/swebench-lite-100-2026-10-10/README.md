# SWE-bench Lite, 100 instances: Claude Code alone against Claude Code with Verinoda Symbiosis (2026-10-10)

Pre-registered in `benchmarks/agent_compare/DESIGN_SWEBENCH.md` (the first 100 instances of its fixed order; the 4-instance pilot
is among them). One headless `claude -p` session per instance and arm, `claude-sonnet-5-5`, the same tools; the arm
`verinoda_guided` has Verinoda's index, MCP server, the verinoda-live mod and a three-step protocol in its prompt (load the tools,
`analyze` before any search, `code_check` after each edit). Harness `swebench_prepare.py`, `swebench_run.py`, scorer
`swebench_score.py`; files here: `results.jsonl` (one row per session, with the patch), `predictions-*.jsonl` (SWE-bench format),
`tasks.json`, `builds.json` (index set-up times), `config.json`, `summary.json`. The official evaluation (below):
`report-none.json`, `report-guided.json` (the harness's reports, with `resolved_ids` and `completed_ids`),
`per-instance-*.jsonl` (one row per instance: resolved, patch applied, `FAIL_TO_PASS` / `PASS_TO_PASS` passed and failed, the
failing tests, the image's source) and `resolved-comparison.json` (`benchmarks/agent_compare/swebench_compare.py`).

## Resolved share: the official SWE-bench evaluation (2026-10-10)

Both prediction files, unchanged, through the official harness in Docker (`SWEBENCH_DOCKER_TALIMAT.md`). All 100 instances
completed in both arms; no errors, no infrastructure failures, no empty patches, and the harness applied all 200 patches
(it falls back to `patch --fuzz` when `git apply` fails, so `sympy__sympy-15346` of the Verinoda arm, which did not apply with
`git apply --check` below, applied here and was resolved, as in the plain arm).

| | plain (`none`) | with Verinoda (`verinoda_guided`) |
|---|---|---|
| Resolved | **72 / 100** | **72 / 100** |
| Resolved in both arms | 66 | 66 |
| Resolved in this arm only | 6 | 6 |
| Resolved in neither | 22 | 22 |
| Completed / not completed | 100 / 0 | 100 / 0 |
| Ambiguous failure (counted unresolved) | `pytest-dev__pytest-8906` (no tests collected) | the same |

Paired difference (Verinoda minus plain): **0.00, bootstrap 95 % interval -0.07 to 0.07**, exact McNemar p = 1.0 (6 against 6
discordant instances). **No measured difference**: at 100 instances a difference smaller than about 7 points cannot be told from
chance, so this does not show that the arms are equal. Resolved by the plain arm only: `astropy__astropy-14182`,
`django__django-13158`, `django__django-13768`, `django__django-16379`, `matplotlib__matplotlib-26020`, `sympy__sympy-18087`; by
the Verinoda arm only: `django__django-11564`, `django__django-14730`, `matplotlib__matplotlib-22835`, `mwaskom__seaborn-2848`,
`scikit-learn__scikit-learn-25500`, `sympy__sympy-19007`.

| Repository | instances | resolved, plain | resolved, Verinoda |
|---|---|---|---|
| django | 35 | 28 | 27 |
| sympy | 32 | 20 | 20 |
| scikit-learn | 10 | 8 | 9 |
| sphinx-doc | 8 | 5 | 5 |
| pytest-dev | 5 | 4 | 4 |
| matplotlib | 4 | 3 | 3 |
| mwaskom (seaborn) | 2 | 1 | 2 |
| psf (requests) | 2 | 2 | 2 |
| astropy | 1 | 1 | 0 |
| pydata (xarray) | 1 | 0 | 0 |

No project's dependencies were installed while the agents worked, so neither agent could run a project's tests; the absolute
share (72 %) is **not comparable with the leaderboard**. Only the paired difference is meaningful.

**How it was run.** SWE-bench harness `swebench` 5.0.2 (github.com/SWE-bench/SWE-bench at `02e7a74`, 2026-09-02) with
`--task-repo` (github.com/SWE-bench/swe-bench-tasks at `3d07b46`, 2026-08-16; `swebench dataset check` passed), dataset
`SWE-bench/SWE-bench_Lite`, split `test`, `-j 4`, per-instance timeout 1800 s, run ids `swe100-none` and `swe100-guided`; the set-up
was first validated with the gold patch of `sympy__sympy-20590` (1 / 1 resolved). Machine: Windows 11 Home 10.0.26200, AMD Ryzen
9 5900HS (8 cores, 16 threads), 31.4 GB RAM; the harness ran in WSL2 Ubuntu 24.04 (kernel 6.18.40.1, 16 GB RAM and 12 CPUs given
to it) with Docker Engine 29.9.0; 2026-10-10, about 3.5 hours for both arms. The harness builds each instance image from the task
repository and, when a build fails, uses the image published on Docker Hub. Builds failed only on cloning the project from
GitHub (`could not read Username for 'https://github.com'`: anonymous clones were refused intermittently under parallel load),
so 53 instance images of the plain arm and 45 of the Verinoda arm are the published ones (column `image` of
`per-instance-*.jsonl`). The image source differs between the arms in 8 instances (`django__django-14915`, `-14997`, `-14999`,
`-15789`, `sympy__sympy-13480`, `-13647`, `-13895`, `-13915`: published for the plain arm, built for the Verinoda arm); none of
them is among the 12 discordant instances, and all 8 have the same outcome in both arms. The harness's report counts
2,294 "total instances" because the task repository holds all of SWE-bench; only the 100 instances with predictions were
evaluated (`submitted_instances` 100). A first attempt with `-j 8` was stopped part-way by the machine's memory and restarted
with the same run ids before any instance was evaluated.

## What was measured before the evaluation: proxies and cost (100 instances, both arms each)

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
tokens and 2.3 more turns per instance, in 98 of 100 instances, and nothing in the proxies shows a better patch. The official
evaluation (above) agrees: both arms resolved 72 of 100, 6 instances each that the other did not, so the extra cost bought no
measured gain in resolved instances on this sample.

Seconds are not a clean comparison: the plain arm ran 3 sessions at once and the Verinoda arm 2, on one machine.

## Limits

One session per instance and arm (the agent's own variation is inside every difference); the sample is the first 100 of a seeded
order, 35 of them django and 32 sympy; the Verinoda arm's protocol is a manual steer and the tool is its authors' own; a model
may know SWE-bench's fixes (both arms share that). The harness's first two pilot runs (line-ending and instruction problems)
were discarded; their sessions are not in `results.jsonl`.
