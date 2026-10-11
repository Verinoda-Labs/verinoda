# False claims on why / when / what-it-affects questions: Claude Code alone against Claude Code with Verinoda (2026-10-11)

Pre-registered in `benchmarks/agent_compare/DESIGN_CLAIMS.md` (with its dated amendments, all written before the sessions they
touch). 40 tasks over the ten pinned real-world repositories of `benchmarks/realworld/manifest.json` (8 `why`, 8 `when`,
14 `affects`, 10 traps whose answer the repository does not hold), written from git by headless `claude-opus-5-5` sessions
without Verinoda and checked by a second agent (`benchmarks/agent_compare/claims_tasks.json`, `claims_tasks_check.json`,
committed before the first session). Two arms, 3 repeats, `claude-sonnet-5-5`, the same tools (`Bash Read Glob Grep`) and
the **same cite-or-say-unknown stance** in both; the Verinoda arm has the index, the MCP server, the verinoda-live mod and
a paragraph that loads and uses the tools first. Harness `claims_run.py`, scorer `claims_score.py` (mechanical citation
check, blind judge of the same model, paired bootstrap over tasks, seed 20261011).

Files: `config.json`, `tasks.json`, `results.jsonl` (one row per session with the full answer; the 16 pilot rows carry
`pilot: true`), `mechanical.jsonl` (every citation with its verdict), `judge.jsonl` (the judge's claims, grades, trap
verdicts and arm guesses), `summary.json` (every table below; `per_task` holds the task-level values), `summary-pilot.json`
(the same on the 16 pilot sessions), `hand_check.json` / `hand_check.md` (the 40 claims for the person, no arm) and
`hand_check_key.json` (the arms), `usage/` (the Verinoda arm's per-call usage logs, D178), `logs/`.

## What ran

240 sessions (120 per arm), all completed: no session error, no network lookup detected, every Verinoda-arm session called
`analyze` (120 of 120) and 118 called `run_tool` (`history_search` 79, `change_review` 39), 3 `project_query`. Claude Code
2.1.296 (the harness's own version read failed; the CLI was read by hand at the time), model `claude-sonnet-5-5` in both
arms and in the judge. The judge parsed 240 of 240 answers into 2,592 claims. Session cost: plain 6.97 USD, Verinoda 11.26 USD.

## Primary measures (paired per task, a task's value the mean over its 3 repeats; bootstrap 95 % over tasks)

| | plain (`none`) | with Verinoda (`verinoda_guided`) | difference | 95 % interval | claim |
|---|---|---|---|---|---|
| Answerable tasks (30): share of answers with at least one **false fact claim** | 0.044 (4 of 90 answers) | 0.056 (5 of 90) | +0.011 | -0.044 to +0.078 | no |
| Traps (10): share of answers that **confabulated** | 0.000 (0 of 30) | 0.000 (0 of 30) | 0.000 | 0 to 0 | no |

**No measured difference.** On the traps nothing is measured between the arms because nothing happened in either: all 60
trap answers said the repository holds no answer. No trap was reclassified (`writer_errors` empty).

**What the interval can rule out.** The pre-registered N rule read the pilot's plain-arm rate (0.25, 2 of 8 answers) and
kept N at 40; the main run's plain-arm rate is 0.044. A halving of that rate is a difference of -0.022, well inside the
interval, so this result is weak evidence against a real effect on answerable tasks, not evidence of none. Applied to the
main rate, the spec's own rule would have grown N.

## Secondary measures

| | plain | with Verinoda | difference | 95 % interval |
|---|---|---|---|---|
| Answers with a false claim marked as an inference (30 tasks) | 0.000 | 0.022 | +0.022 | 0 to +0.067 |
| Incorrect fact claims over fact claims (30 tasks) | 0.0068 | 0.0098 | +0.0031 | -0.0037 to +0.0119 |
| Correct claims with no confirmed citation, over correct claims (30 tasks) | 0.180 | 0.145 | -0.035 | -0.078 to +0.010 |
| Claims marked as inference, over claims (40 tasks) | 0.156 | 0.158 | +0.002 | -0.025 to +0.030 |

None reaches a claim. The uncited share is the one that leans the tool's way and the one the failed blinding (below) could
touch.

By kind (the primary measure of the kind; descriptive, 8 to 14 tasks each):

| kind | n | plain | with Verinoda | difference | 95 % interval | the spec's expectation |
|---|---|---|---|---|---|---|
| `why` | 8 | 0.083 | 0.208 | +0.125 | 0 to +0.292 | small headroom: git is open to both arms |
| `when` | 8 | 0.000 | 0.000 | 0.000 | 0 to 0 | small headroom |
| `affects` | 14 | 0.048 | 0.000 | -0.048 | -0.119 to 0 | where a difference was expected |
| trap | 10 | 0.000 | 0.000 | 0.000 | 0 to 0 | - |

`affects` leans the expected way and does not reach a claim; `why` leans the other way and does not reach one either.

## What the false facts were

12 claims in 9 answers were graded an incorrect fact. 7 of the 12 (both arms, every repeat of
`fastapi__full-stack-fastapi-template-why-1`) assert an **absence**: "the repository states no rationale for reading the
password from the body". The rationale exists: commit `546dc8b` (2019-05-28, "Update login.py to receive password as body
... for security"), an ancestor of the pinned sha, at the file's pre-move path; `git log -S` on the current path misses it,
and both arms (Verinoda's `history_search` included) stopped there and stated the negative as a fact. The Verinoda arm's two
other `why` false facts (`junegunn__fzf-why-1`, repeats 2 and 3) have the same shape: a search returned nothing and the
answer asserted that nothing exists. The plain arm's other two are an `affects` claim that over-reaches ("all seven call
sites and the test would need updating") and one that under-counts callers. So the stance both arms carry stops positive
confabulation (no trap was answered, no invented commit) and does not stop a confident negative.

## Blinding: failed, and the channel is known

The judge guessed the arm right in 72 % of answers (173 of 240; 95 % interval 0.66 to 0.78, which excludes 0.5): it said
"B" (the tool arm) for 109 of 120 Verinoda answers and for 56 of 120 plain ones. The channel is the mask itself: tool names
and status words are replaced by `[tool]`, and a Verinoda answer carries 4.06 masks on average (114 of 120 answers have at
least one) against 0.12 for a plain answer (3 of 120). The neutralization hides what the tool said and shows that a tool
was used. The judge was told arm B has an evidence tool, so it could expect citations from B; that touches the uncited
share (secondary) more than the primary measure, where the null is symmetric. The result is reported with this caveat, as
the spec says, not discarded.

## Mechanical citation check

2,448 citations (`path:line`, `path:a-b`, commit hashes) in the 240 answers; plain 1,099 confirmed / 22 wrong / 6 missing,
Verinoda 1,266 / 35 / 20. The check was loosened twice after the pilot, both times as a property of the scorer and before
the main run's scoring (identifiers read out of backticked spans, the question's own names counted, a commit's diff
searched, bare and partial paths resolved to the tracked files that end with them; `DESIGN_CLAIMS.md`, amendments of
2026-10-11); the pilot's first matcher had graded 8 of 8 sampled correct citations `wrong`. Of the 83 citations still not
confirmed, a hand sample of 12 is about half genuine (a line number of an older commit, an elided `.../` path, a path the
file had before it moved) and half prose claims the identifier match cannot see. This feeds the secondary uncited share only.

## Cost and behaviour

| per session | plain | with Verinoda |
|---|---|---|
| median dollars | 0.056 | 0.093 (1.66x) |
| total dollars | 6.97 | 11.26 |
| median seconds | 15.0 | 22.5 |
| median turns | 5 | 5 |
| input tokens, total | 10.9 M | 14.0 M |
| output tokens, total | 148 k | 165 k |
| answer length, median characters | 1,755 | 2,091 |
| citations per answer, median | 8 | 11 |
| claims per answer (the judge's split), mean | 10.5 | 11.1 |

Per Verinoda call (`usage/`, D178; tokens are characters / 4, the log's estimate): `analyze` 120 calls, 1.29 M result
characters (about 2,700 estimated tokens per call); `history_search` 79 calls, 383 k; `change_review` 39 calls, 251 k;
`project_query` 3 calls, 17 k. The log also holds the mod's and the server's own CLI work, not agent calls: `check` 120
(the mod's guard), `mcp` 120 (the server's lifetime), `update` 5.

Writing and checking the 40 tasks cost 6.64 USD (ten writers and their checkers) plus 1.77 USD for the first repository's
trial that led to the amendment on traps and gold size. The judge's 240 sessions ran in the same account; their cost was not
read out separately.

## Pilot

The first 8 tasks of the fixed order, 2 arms, 1 repeat (`summary-pilot.json`, `logs/pilot.log`): no error, no network
lookup; plain false-fact share 0.25 (2 of 8), Verinoda 0.125 (1 of 8), difference -0.125 [-0.375, 0]; blinding 0.69
[0.44, 0.88]. The N rule read the 0.25 and kept 40. The 16 sessions are in the sample.

## Hand check

**Not measured yet.** The person's grading of the 40 claims in `hand_check.md` (20 per arm, drawn blind, seed 20261011) is
pending; the disagreement rate with the judge goes here when it is in, and the spec stops the report above 20 % until the
judge prompt is revised and every answer re-graded. Until then the judge's grades are the only grades.

## Not measured

- **The stance against the tool.** Both arms carry the cite-or-say-unknown instruction by design, so the study cannot say
  whether the low false-fact rate (4 to 6 %) and the zero confabulation on traps come from the instruction or would hold
  without it. One more arm (plain, no stance, the 10 traps x 3 repeats, about 2 USD) would answer that; it was not run.
- Verinoda offered without the guiding paragraph (measured five times before: never used).
- Whether a person reading the answers trusts them more or reviews them faster.
- A difference smaller than about 0.04 on answerable tasks (the interval's width), and any effect on code the agent writes.
- Languages the ten repositories do not cover; repositories over 1,000 files; a judge of another model family.
