# SWE-bench Lite dev set, 100 instances: how far the legitimate levers go, and what the rest needs (2026-10-24)

Pre-registered in `benchmarks/agent_compare/DESIGN_SWEBENCH_CEILING.md`. Amendments 2-11 are each dated and were written
before the results they govern.

**The question (2026-10-24).** How does Verinoda reach 100/100 on the 100 dev instances of D184's SWE-bench Lite order?
In the official evaluation both arms scored 72/100 there.

**How the study answers it.**
- It measures the legitimate levers in a fixed order: the environment and the prompt, then the model, then more attempts
  with a selector that never sees the hidden tests.
- Then labelled diagnostics give what the benchmark withholds: first the issue's hints, then the test patch.
- It also measures how much of the upstream fix the models write from memory.

**The grades.** Every grade here is local, made on Windows with the calibrated grade of `swebench_localeval.py`. A test
that fails with the gold patch in this environment is left out. D184's 200 patches graded this way agree with the official
grade on 99 and 98 of 100. The grades are final: amendment 2's regrade ran on a quiet machine (2026-10-25, 01:04-03:13).
It graded 229 rows again and changed 4 to resolved.

**Files.** Logs, transcripts and gold patches are not included.
- `runs/<run>/`, one folder per run (`-r1`: the re-runs of amendments 6 and 9):
  - `results.jsonl`: one row per session, with its patch, cost, turns and seconds. `results-limit.jsonl` holds the rows
    the usage limit ended (amendment 9).
  - the grades: `eval-<arm>.jsonl` and `eval-<arm>-regrade.jsonl`.
  - the predictions: `preds-<arm>.jsonl` and `predictions-<arm>.jsonl`.
  - the session configs: model, mod options, limits.
  - the leak scan (`leakscan-*.txt`) and, for the last scan, what the filter left (`leakfilter-*.txt`).
- `runs/c3-att-1..3/`: the attempts merged after their re-runs, which is what the selector read.
- `runs/c3-select/`: the selection, with the quiet-machine repeat of the plain arm's.
- `runs/d184-*.jsonl` and `runs/gold-dev*.jsonl`: local grades of D184's patches (the agreement check) and of the gold
  patches (the calibration). They hold grades only.
- `closedbook/<model>.jsonl`: the closed-book probe's replies.
- `crosstab.csv`: one row per instance, with the leaderboard, OpenAI's annotations and every attempt's grade.
- `leak-review.md`: every flagged tool call, read by hand, and the scheduling log.
- `not-counted.json`: the sessions left out, each with its reason.
- `diag-ids.json`: the diagnostics' lists as the orchestrator read them.
- outputs of the scripts:
  - `report.txt` and `report.md` (`report.py`);
  - `c3-score.txt` (`c3_score.py`) and `c3-pair.txt` (`c3_pair.py`);
  - `cost.txt` (`cost_total.py`);
  - `c2-*.txt` (`c2_check.py`).
- `scripts/`: the scripts that ran: the orchestrator, grading, selection and reports. The harness itself is in
  `benchmarks/agent_compare/` (`swebench_*.py`). The scripts carry this machine's paths.

## The answer in short

No legitimate single attempt gets there.

**The model moves the count; Verinoda does not.**
- The model moves the resolved count from 73 (Sonnet 5.5) to 84-85 (Opus 5.5) and to 87 (Fable 5.1, plain arm).
- Three Opus attempts with the selector give 82 plain and 86 with Verinoda. The selector picks no better than the first
  attempt alone (84 and 85).
- No pre-registered comparison of Verinoda's arm with the plain arm is distinguishable from zero.
- In the three Opus attempts Verinoda's arm was ahead by 1, 4 and 4 (McNemar p 1.0, 0.22, 0.13), and its selected patches
  by 4 (p 0.29).

**What no attempt reaches.**
- Over every attempt of the study, 97 of the 100 instances are resolved at least once. That is an oracle over attempts,
  not a score, and it counts D184's official grades (94 on the local grades alone).
- The 84 Lite leaderboard submissions collected on 2026-10-23 reach 82 together.
- None of the 3 instances left was resolved by any submission either: sympy-11870, sympy-14308 and sphinx-7686.
  - In each of them the hidden tests demand behaviour the issue does not ask for.
  - Fable 5.1 is given only the repository's name, the base commit and the issue (no file, no tool, one reply). It writes
    the upstream fix of 2 of the 3 verbatim.

**With what the benchmark withholds** (diagnostics, never a score):
- the issue's hints reached sympy-11870 in one of its two sessions;
- the test patch reached sphinx-7686 in both;
- sympy-14308 was reached by nothing. Its test-patch sessions were never run, a gap described under Diagnostics.

**Repeated attempts also reached one instance without memory.** sympy-13146 was also unsolved by every leaderboard
submission. Four Opus sessions of C3's later attempts resolved it, three of them in a file the upstream fix does not touch.

What is left takes memory of the fix or the information the benchmark withholds. Memory of the fix is contamination, not
problem solving, and it is the reason OpenAI retired SWE-bench Verified on 2026-02-23.

## Conditions and results

| condition | model | plain | Verinoda | cost per session (plain / Verinoda) | seconds per session |
|---|---|---|---|---|---|
| D184 (official, 2026-10-10) | Sonnet 5.5 | 72/100 | 72/100 | | |
| C0: D184's harness again (34 instances) | Sonnet 5.5 | 6/33 | 7/31 | 0.09 / 0.15 $ | 44 / 247 |
| C1: the environment and a reproduce-and-test prompt | Sonnet 5.5 | 73/99 | 73/99 | 0.09 / 0.12 $ | 198 / 248 |
| C4: the model (C3's attempt 1) | Opus 5.5 | 84/99 | 85/99 | 0.20 / 0.28 $ | 135 / 162 |
| C4: the model | Fable 5.1 | 87/99 | 34/37 (38 instances) | 0.86 / 1.03 $ | 207 / 250 |
| C3: attempt 2 | Opus 5.5 | 84/99 | 88/99 | 0.20 / 0.27 $ | 104 / 173 |
| C3: attempt 3 | Opus 5.5 | 83/99 | 87/99 | 0.19 / 0.26 $ | 92 / 167 |
| C3: 3 attempts, the selector | Opus 5.5 | 82/99 | 86/99 | | |
| C3: pass@3 (diagnostic) | Opus 5.5 | 86/100 | 92/100 | | |

- **99 graded of 100:** django-13658 cannot be graded here (amendment 8: its admin_scripts tests fail with the gold patch
  in this environment).
- **C0** repeats D184's harness on 34 instances (its noise floor). Its sessions had no environment to run code in.
- **Fable's Verinoda arm** has 38 sessions: the account's usage limit ended the rest (amendment 9), and the user stopped
  that arm on cost.
- **The selector** chose plain patches from attempts 1/2/3 61, 26 and 13 times, and Verinoda's arm's 63, 22 and 15 times.
  Against the first attempt alone it gives -2 plain (discordant 3/1, p 0.63) and +1 with Verinoda (2/3, p 1.0).
- **The held-out run** (instances 101-200) was cancelled before any of its sessions ran (amendment 11). The user moved the
  work to a test without recall, on a repository the models have not seen (the own-repository study, `DESIGN_OWNREPO.md`).

## Verinoda's arm against the plain arm

Paired per instance, Verinoda's arm minus the plain arm:

| comparison | n | plain vs Verinoda | discordant (plain only / Verinoda only) | difference [95 %] | McNemar p |
|---|---|---|---|---|---|
| C0 | 31 | 5 vs 7 | 2/4 | +0.065 [-0.097, +0.226] | 0.69 |
| C1 Sonnet | 99 | 73 vs 73 | 3/3 | +0.000 [-0.051, +0.051] | 1.00 |
| C4 Opus (attempt 1) | 99 | 84 vs 85 | 3/4 | +0.010 [-0.040, +0.061] | 1.00 |
| C4 Fable | 37 | 35 vs 34 | 1/0 | -0.027 [-0.081, +0.000] | 1.00 |
| C3 attempt 2 (Opus) | 99 | 84 vs 88 | 1/5 | +0.040 [+0.000, +0.091] | 0.22 |
| C3 attempt 3 (Opus) | 99 | 83 vs 87 | 0/4 | +0.040 [+0.010, +0.081] | 0.13 |
| C3 selected (Opus) | 99 | 82 vs 86 | 2/6 | +0.040 [-0.010, +0.101] | 0.29 |

**No exact test is significant.**
- In all three Opus attempts and in the selection, Verinoda's arm is ahead.
- Attempt 3's interval excludes zero while its exact test does not.
- The attempts share their 99 instances, so they are not independent tests. A test pooled over them was not
  pre-registered, and none is made.
- What the numbers support: with Opus, Verinoda's arm was never behind, by up to 4 instances in 99. It cost 0.07 $ and
  27-75 s more per session.

**Verinoda's part in the Verinoda arm was one `analyze` and one `code_check` per session.**

| run | `analyze` calls | unanswered | of them, 60-second budget spent | other answers that spent the budget |
|---|---|---|---|---|
| C4 Opus | 100 | 37 | 8 | not counted |
| C3 attempt 2 | 93 (one per session) | 42 | 18 | 3 |
| C3 attempt 3 | 98 (one per session) | 36 | 12 | 2 |

**C2 (amendment 5): did a Verinoda defect change an outcome?** The question was asked of every instance the plain arm
resolved and Verinoda's arm did not.
- C3 attempt 3 has no such instance.
- C3 attempt 2 has one, sympy-16281:
  - its only `analyze` call spent the budget unanswered;
  - the session went on and wrote a patch that fails the hidden tests.
  - Nothing ties the failure to the call, so no C2 run was made.

**One defect seen in the runs is fixed in the product (D192), not here:** code_check ignored the activated environment.

**A second defect was found after the runs, in C1's transcripts (2026-10-25). The harness set it off.** These
repositories do not ignore `.mcp.json`. The steps:
1. `verinoda setup` writes `.mcp.json` before it scans, so the graph had the file's node.
2. The runner then added `.mcp.json` to `.git/info/exclude`.
3. The file's leaving the listing counted as a removed graph file.

What it did:
- **Count:** 93 of C1's 98 guided first `analyze` calls said the index predated `.mcp.json` and was not refreshed.
- **Background build:** in all 93 the server started a whole graph build beside the session. The skipped build had taken
  23 to 1413 s, median 236 s.
- **The other 5:** small repositories, where by the rule the rebuild ran inside the call.
- **The answers:** the stale index differed from the tree only in `.mcp.json`, so they read the same code.
- **Not measured:** the defect's share of the first calls' time (C1 median 31.6 s, up to 290 s, under load), and its
  effect on resolved instances (the arms do not differ).
- **The other runs, counted the same way:**

  | run | first calls with the note |
  |---|---|
  | C0 | 32 of 33 |
  | C4 Opus | 95 of 100 |
  | C4 Fable | 36 of 38 |
  | C3 attempt 2 | 88 of 93 |
  | C3 attempt 3 | 93 of 98 |
  | diagnostics | 6 of 6 |
  | re-runs | 12 of 12 |

  - **In all:** 455 of the study's 478 guided first calls.
  - **Every first call without the note** was in requests, seaborn or xarray.
- **The fix** is D196 in the product, not here.

## The oracle and the instances no attempt resolves

Over every attempt (D184's official grades, C0, C1, C4 and C3), 97 of the 100 instances are resolved at least once.
- **On the local grades alone, 94.** Three instances were resolved only in D184:
  - django-13658, which cannot be graded here;
  - sympy-14317 and sympy-16988, which no later session resolved and the test-patch diagnostic did.
- **The 3 left:**

| instance | leaderboard | class | what the hidden test demands | diagnostics | closed-book recall (Sonnet / Opus / Fable) |
|---|---|---|---|---|---|
| sympy-11870 | 0/84 | H (read as B before its hints session) | `sinc(x).rewrite(sin)` == a Piecewise; the issue asks only that `trigsimp` give `sin(k)` | hints: Verinoda's arm resolved it, the plain arm did not | 0.00 / 0.20 / 0.00 |
| sympy-14308 | 0/84 | B | the upper-middle row for a 4-row scalar and a double space from the gold's layout code | hints: neither arm; test patch: not run (the gap below) | 0.00 / 0.00 / 1.00 |
| sphinx-7686 | 0/84 | B | `members` honouring `autodoc-skip-member`; the issue asks only to leave out imported members | test patch: both arms (it has no hints) | 0.12 / 0.17 / 1.00 |

B: the hidden test demands behaviour neither the issue nor the code determines. H: the issue's hints help.

**sympy-13146** (0/84 on the leaderboard, H) was one of the four left before C3's later attempts were graded.
- **Who resolved it:** attempts 2 and 3 resolved it in both arms, 4 of C3's 6 sessions of it. C4 Opus (attempt 1), C4
  Fable and C1 did not.
- **The patches:**
  - three of the four change `sympy/core/basic.py`, a file the upstream fix does not touch (recall 0.00);
  - the fourth changes `sympy/core/operations.py` as upstream does (recall 0.50).
- **Not from memory:** these are fixes written from the code. Opus's closed-book recall for it is 0.00.
- **Its hints sessions** resolved it in neither arm. By amendment 10, an instance a later session resolves leaves the lists,
  and its diagnostic sessions are reported apart.
- Graded locally only, like every grade here.

## Memory

**Amendment 7's measure.** Take the gold patch's added lines in non-test files, leaving out those the issue holds. The
measure is the share of them that a patch also writes; "verbatim" means 0.9 or more.

**The closed-book probe.** One call per model and instance, with the repository's name, the base commit and the issue only:
no tool, no file, one reply. On the 99 instances every model answered:

| model | verbatim, closed-book | mean recall, closed-book | verbatim, plain-arm sessions with the repository |
|---|---|---|---|
| Fable | 67 | 0.81 | 56 |
| Opus | 43 | 0.65 | 50 |
| Sonnet | 38 | 0.52 | 24 |

C3's selected resolved patches have a mean recall of 0.75 (50 verbatim) in the plain arm and 0.79 (52 verbatim) in
Verinoda's arm.

## Diagnostics (outside the benchmark's rules, never a score)

Amendments 5 and 10 define two stages:
- **Hints stage:** the issue's comments from before the fix are added to the prompt.
- **Tests stage:** the test patch is applied and the FAIL_TO_PASS tests are named.

The lists were taken at 15:38 on 2026-10-24 from what was graded then.

| stage | instances | plain | Verinoda |
|---|---|---|---|
| hints | sympy-11870, sympy-13146, sympy-14308 | 0/3 | 1/3 (sympy-11870) |
| tests | sympy-14317, sympy-16988, sphinx-7686 | 3/3 | 3/3 |

**A gap: sympy-14308 had no tests-stage sessions.**
- Amendment 10 also puts in the tests stage each hints instance that its hints sessions leave unresolved in both arms. That
  covers sympy-14308, and sympy-13146 until C3 resolved it.
- The list file (`diag-ids.json`) was not updated after 15:40, so no tests-stage session of sympy-14308 ran.
- Whether the test patch reaches sympy-14308 is not measured.

## What happened along the way

- **PATH lost at login.** Claude Code on Windows takes a session's PATH from a login shell with a 10-second limit. Under this
  machine's load a login shell sometimes took longer, and the session's Bash found no command.
  - This hit 5-6 % of sessions per arm.
  - Each such session was run again (amendment 6).
  - Each run reports its count and a line leaving them out (`report.txt`, "flagged" and "sensitivity").
- **Usage limit.** 12:33-13:00 the subscription's 5-hour usage limit was reached, and 66 sessions ended at once or mid-way.
  - They are not counted and were run again, except Fable's Verinoda arm (amendment 9).
  - Since then the orchestrator reads `/usage` before it starts a runner.
- **Shadow copies.** At 09:16 Windows deleted volume C:'s shadow copies (the System Restore points), when the shadow storage
  could not grow under the study's writes. No study file was on it.
- **The leak scan** found no leak. It flags every tool call outside the session's copy or at what the study withholds, and
  every flagged call is in `leak-review.md`; the last scan was on 2026-10-25 at 03:16.

## Cost

These are Claude Code's own cost figures (`cost_usd` per session; on a subscription they are usage, not dollars). Every
session row is counted, re-runs and the rows the usage limit ended included. The total is 337.12 $:

| part | cost |
|---|---|
| C4 Fable | 132.64 $ |
| C3 attempts 2 and 3 | 92.96 $ |
| C4 Opus | 49.92 $ |
| closed-book probe (299 replies) | 24.78 $ |
| C1 Sonnet | 21.74 $ |
| C0 (both repeats) | 10.95 $ |
| diagnostics | 4.12 $ |

## Limits

- **Local grades, not official ones.** The grades are local on Windows, not the official Linux images. The agreement check
  measures by how much they can differ (99 and 98 of 100).
- **100 dev instances.** Differences of a few instances are within noise (paired intervals in `report.txt`).
- **Memory.** The models may have seen these fixes in training. The closed-book probe measures it, and nothing here
  removes it.
  - A claim free of recall needs tasks fixed after the models' training data (SWE-bench-Live, SWE-rebench). This study has
    none.
  - The user's own-repository study is the test without recall.
