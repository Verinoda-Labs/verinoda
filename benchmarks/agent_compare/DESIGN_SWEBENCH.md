# SWE-bench Lite: Claude Code with Verinoda Symbiosis against Claude Code alone (pre-registration, 2026-10-10)

Written before any session ran. The question: on real SWE-bench tasks, does a Claude Code agent that is made to use
Verinoda Symbiosis produce better patches than the same agent without it?

## Tasks

SWE-bench Lite (`SWE-bench/SWE-bench_Lite`, 300 instances, the official dataset of github.com/SWE-bench/SWE-bench).
Instances are ordered by `sha256("20261010:" + instance_id)` and the first N are the sample; the order is fixed now.
The first 4 of the order are a pilot that validates the harness; they stay in the sample (no instance is dropped or
replaced after it was seen). N is set by the budget and written in the results before the scoring.

## Arms

Real headless Claude Code sessions (`claude -p`), the same model pinned in both (`claude-sonnet-5-5`), the same tools
(`Bash Read Glob Grep Edit Write`; no network lookup is asked for), user settings, plugins, skills and MCP servers not
loaded (`--setting-sources project,local --strict-mcp-config`), the user's own `verinoda` command off `PATH`. Every
session works in its own checkout of the repository at the instance's `base_commit`, and is asked to fix the issue
(the instance's `problem_statement`, verbatim) by editing the source; tests are not to be edited.

- `none`: original Claude Code, nothing installed.
- `verinoda_guided`: `verinoda setup . --agents claude` (index, project skill, MCP server loaded with `--mcp-config`) and
  the verinoda-live mod with its `auto` setting at `nudge`; and, because the earlier studies found that the agent never
  called Verinoda by itself (0 of 286 sessions, `SYMBIOSIS.md`), a paragraph after the shared task text tells it to use
  it: start with `analyze` / `project_query` to find the relevant code, and run `code_check` on the Python files it
  changed. The arm measures Verinoda **used**, not Verinoda **offered**. Each session records how many calls to
  Verinoda's tools it made; a session of this arm with none is reported as such and kept in the result (intention to
  treat), with a secondary comparison on the sessions that did use it.

## Measures

The official measure, the share of instances **resolved** (the instance's `FAIL_TO_PASS` tests pass and its
`PASS_TO_PASS` tests still pass), needs the SWE-bench Docker evaluation (`python -m swebench.harness.run_evaluation`),
about 120 GB of disk and Linux containers. This machine has no Docker, so:

1. Each arm's patches are written as `predictions-<arm>.jsonl` in the SWE-bench format; the resolved share is
   **measured by running that evaluation on a machine or cloud runner that has Docker** (`SWEBENCH_EVAL.md`: `sb-cli`,
   Modal or a Linux VM) and is "not measured" until then. The study is not complete without it.
2. Measured here without Docker, per instance and arm: whether the patch is non-empty and applies to `base_commit`
   (`git apply --check`); the files it changes against the files the gold patch changes (any overlap, all gold files
   covered, extra files); the patch size; and the cost: turns, input and output tokens, dollars and seconds of the
   session, and the calls to Verinoda's tools. These are proxies; file overlap is not correctness.

Paired comparison per instance, bootstrap 95 % interval over instances for differences; with the sample size N that
the budget allows, a difference smaller than the interval is reported as no measured difference.

## Limits fixed now

- The repositories' dependencies are **not installed**: an agent cannot run a project's tests (old Django on Python 3.12,
  and so on). This holds for both arms; the published SWE-bench agents ran in containers where tests run. Absolute
  numbers are therefore not comparable with the leaderboard; only the paired difference is meaningful.
- A model that has seen SWE-bench may know some of these fixes; both arms share that.
- The `verinoda_guided` instruction is a manual steer by the person who asked for the study, and the tool is the
  author's own; nothing here is independent of Verinoda's authors.
- One session per instance and arm; no repeats, so the agent's own run-to-run variation is inside the noise.

## Pilot (2026-10-10)

The first 4 instances of the order (sphinx-8801, django-16873, sympy-23262, sphinx-7738), one session per instance and arm.
The harness's first runs were discarded and rerun: the machine's Git converted line endings (`autocrlf`), which made the
patches not apply, and the Verinoda arm, told only to use Verinoda, called `analyze` in none of its sessions. The
instruction is now a three-step protocol (load the tools, `analyze` before any search or read, `code_check` after each
edit); with it every Verinoda-arm session called `analyze` first and `code_check` after editing. In the pilot, both arms
changed the gold file in 4 of 4 instances and every patch applies to the base commit; the Verinoda arm cost about 2.5 times
more per session ($0.42 against $0.17 for four) and took 24-90 s against 10-24 s. Four easy instances show no difference
in either direction, and the resolved share was not measured.

## Result (2026-10-10)

The 100-instance run is in `benchmarks/results/swebench-lite-100-2026-10-10/` (README, `summary.json`, the sessions and the
predictions). The proxies show the Verinoda arm used Verinoda in all 100 sessions, at about 60 % more dollars and 2.3 more
turns per instance, with no visible difference in the patches' files (90 of 100 pairs changed the same files; the gold file was
covered in 92 against 90).

**Resolved share (official SWE-bench evaluation in Docker, 2026-10-10, `docs/DESIGN.md` D184):** 72 of 100 in each arm; 66
resolved in both, 6 in the plain arm only, 6 in the Verinoda arm only, 22 in neither; paired difference 0.00, bootstrap 95 %
interval -0.07 to 0.07, exact McNemar p = 1.0. All 100 instances completed in both arms. No measured difference: a difference
smaller than about 7 points is not ruled out. Reports and per-instance results are beside the predictions.
