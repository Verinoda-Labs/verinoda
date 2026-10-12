# D186 verification runs on the claims study: the Verinoda arm with the call rule, six tasks and a 24-pair cost sample (2026-10-13)

Plan Task 8, steps 5 and 6 (`docs/drafts/2026-10-12-verinoda-lean-plan.md`; spec `docs/drafts/2026-10-12-verinoda-lean-design.md`
section 8, items 3 and 4). Two small runs on the pinned repositories of the D185 study, with the D185 harness
(`benchmarks/agent_compare/claims_run.py`, `claims_score.py`, `claims_tasks.json`) and one new scorer file
(`claims_mech_strict.py`): the **Verinoda arm only on six D185 tasks, 3 repeats** (18 sessions), and a **cost sample of 24
answerable D185 tasks, 1 repeat, both arms** (48 sessions: the 24 plain ones had been run earlier the same day and are reused,
the 24 Verinoda ones are from this run, three of them the same sessions as in the six-task part). `claude-sonnet-5-5`, Claude Code
2.1.296. This is the cheap re-run the design asked for, not a new study: nothing here is a pre-registered measure.

**What is compared.** Two configurations, not two versions of one thing. The **D185 configuration**: the GUIDE paragraph in the
user prompt (load the tools with ToolSearch first and use them before Grep), the mod with `auto: nudge`, the earlier `analyze`.
The **D186 configuration**: no GUIDE (the Verinoda arm's prompt is the stance only), the mod's call rule in the system prompt
naming `analyze` as the first tool call, the server's core tools in front of the model, the lean `analyze` result, the code at
`575b2a5`. Everything that differs between them differs together, so this run cannot say which change did what, and nothing
below says that the code change produced a result. The plain-Claude arm is the same configuration in both runs.

## In short

- 63 sessions (24 plain, 39 Verinoda), **0 session errors**, no network lookup, all Claude Code 2.1.296. The judge parsed 63 of 63
  answers. Session cost as the CLI reports it: plain 1.38 USD, Verinoda 2.42 USD.
- **Tool use.** 37 of the 39 Verinoda sessions called `analyze` exactly once, and in all 37 it was the first tool of the session.
  The two that did not (`junegunn__fzf-affects-1`, `expressjs__express-affects-1`, both what-does-it-affect questions) went to
  Grep first and used no Verinoda tool. No other Verinoda tool was called (`run_tool`, `project_query`: 0), ToolSearch 0.
  The 39 sessions of the earlier run, with the rule as it was before the fix, made no Verinoda call at all (appendix below).
- **Cost, 24 pairs (Verinoda minus plain, same task, repeat 1).** Plain 0.0576 USD per session, Verinoda 0.0633 (1.10x). Paired
  difference **+0.0057 USD, bootstrap 95 % interval +0.0023 to +0.0085** (10,000 resamples, seed 20261013). The interval excludes
  the design's line of +0.015 and excludes zero. Model calls per session 3.50 and 3.17 (difference -0.33, interval -0.62 to
  -0.04); cache-write tokens 9,307 and 11,059 (+1,752, +1,009 to +2,331). The D185 configuration on the same 24 tasks:
  0.0582 and 0.0953 USD (1.64x), paired +0.0371 USD (+0.0329 to +0.0411).
- **Verinoda output** the model received: mean 3,136 characters per session in the 24 pairs (median 2,484; 39 sessions: mean
  2,840, median 2,433); 3 of the 39 sessions are above the design's 4,500 (8,093, 6,905 and 11,997, all what-does-it-affect
  questions). D185: 16,179 per session on the same tasks.
- **The six tasks.** `fastapi__...-why-1`: the gold commit `546dc8b` is cited in 3 of 3 answers and none asserts that no reason
  exists (D185: Verinoda arm 0 of 3 cited, 3 of 3 false facts; plain 1 of 3 cited, 2 of 3 false facts). `junegunn__fzf-why-1`:
  `1578b7c3` cited in 3 of 3 (D185: 1 of 3 in each arm). `axios__axios-when-1` and `sharkdp__bat-when-1`: correct in 3 of 3,
  as in D185. **`guzzle__guzzle-trap-1`: 3 of 3 answers name `b58db450` as the earliest commit of the string** (the oldest is
  `91f1e347`, which all three `analyze` results listed as the path-free first appearance of `MessageFormatter`) and the judge counts
  3 of 3 with an incorrect fact claim: the same as D185's plain arm (3 of 3), against 0 of 3 in D185's Verinoda arm.
  `gin-gonic__gin-trap-1`: the judge found no incorrect claim, but by my reading and by git 3 of 3 answers name `31323f6` as where
  the constant was added (2 say "first") when the history starts at `15216a0`; no Verinoda result named `15216a0`.
- Not measured: see the section of that name. In particular the effect of any single change, accuracy parity, the `show="lead"`
  variant of section 4.1b, and what the model saw of the corrected deferred-tools reminder.

## What ran

Work folder `C:/vbench-claims-rerun` (outside the repository). Times are local (UTC+3); the transcripts' time stamps in
`analysis/analysis.json` are UTC. Commands from the repository root with its `.venv` Python; `<24 ids>` is the list below.

| step | command (flags after the config path) | time | exit |
|---|---|---|---|
| plain arm, 24 sessions | `claims_run.py config.json --arms none,verinoda_guided --repeats 1 --tasks <24 ids>` (the first run of this command, 2026-10-13 01:16 to 01:22, ran these 24 plain sessions and 21 Verinoda ones; the Verinoda ones are the set-aside run, appendix) | 01:16 to 01:22 | 0 |
| 1. the D185 re-run | `claims_run.py config.json --arms verinoda_guided --repeats 3 --tasks fastapi__full-stack-fastapi-template-why-1,junegunn__fzf-why-1,guzzle__guzzle-trap-1,gin-gonic__gin-trap-1,axios__axios-when-1,sharkdp__bat-when-1` | 02:30 to 02:33 | 0 |
| 2. the cost sample | `claims_run.py config.json --arms none,verinoda_guided --repeats 1 --tasks <24 ids>` (21 new sessions; the 24 plain rows were present and skipped) | 02:33 to 02:37 | 0 |
| 3. scoring | `claims_score.py C:/vbench-claims-rerun --judge --judge-workers 4`, then `claims_mech_strict.py C:/vbench-claims-rerun` | 02:37 to 02:40 | 0, 0 |
| 4. analysis | `analysis/analyze_sessions.py`, `compare_d185.py`, `make_tables.py` (this folder) | | |

The 24 ids (the first 24 answerable ids of `claims_tasks.order()`): `fastapi__sqlmodel-affects-1`,
`fastapi__full-stack-fastapi-template-when-1`, `fastapi__full-stack-fastapi-template-why-1`, `gin-gonic__gin-affects-1`,
`guzzle__guzzle-affects-2`, `gin-gonic__gin-why-1`, `junegunn__fzf-affects-1`, `fastapi__sqlmodel-why-1`, `junegunn__fzf-why-1`,
`Graphify-Labs__graphify-why-1`, `sharkdp__bat-affects-1`, `expressjs__express-why-1`, `fastapi__full-stack-fastapi-template-affects-1`,
`junegunn__fzf-when-1`, `Graphify-Labs__graphify-affects-1`, `sharkdp__bat-why-1`, `expressjs__express-affects-1`,
`fastapi__sqlmodel-when-1`, `expressjs__express-when-1`, `google__gson-affects-2`, `google__gson-affects-3`, `axios__axios-affects-1`,
`guzzle__guzzle-affects-1`, `axios__axios-when-1`. Three of them (`fastapi__...-why-1`, `junegunn__fzf-why-1`, `axios__axios-when-1`)
are also among the six, so their Verinoda repeat 1 is the same session in both parts: 18 + 21 = 39 Verinoda sessions.

**Configuration** (`config.json`, as run): model `claude-sonnet-5-5`; tools `Bash Read Glob Grep` in both arms plus `mcp__verinoda`
in the Verinoda arm; `max_turns` 40; the Verinoda arm's prompt carries the stance only (`"guide_text": ""`), so the only Verinoda
text in front of the model is the mod's call rule (a `prompt.compose` section), the server's instructions and the skill listing;
`mod_options` empty; `--setting-sources project,local --strict-mcp-config`; two sessions at a time per arm. **Code**: branch
`symbiosis-redesign-2026-10-12` at `575b2a5` (full hash `575b2a50ad84a0e680d7f711c2007ddba0d0207a`), working tree clean when step 1
started (`logs/final-run.started`). Between the set-aside run's commit `68b2133` and `575b2a5` the files that changed in
`verinoda/` and `claude-mods/` are the mod (`register.tsx`, `improve-pane.tsx`, its tests and docs), the skill and rules templates,
`analysis.py`, `gitexec.py`, `history.py`, `mcp/server.py`, `paths.py` and `verdict_gate.py`; the harness (`benchmarks/agent_compare/`)
is unchanged.

**The Verinoda-arm working copies were indexed once, at `68b2133`, and reused.** Each session has its own shared clone
(`copies/<hash>/verinoda_guided/r<n>`); the 39 of the set-aside run were kept, so `verinoda setup` ran again on each at `575b2a5`
(an incremental update: `setup_seconds` median 4.7 s against 10.5 s in the set-aside run) and rewrote each copy's
`.claude/skills/verinoda/SKILL.md` from the current template (all 39 carry the new wording). The index code is unchanged between
the two commits by the coordinator's note; I did not diff the index state itself. The plain-arm rows come from the 01:16 run,
about 70 minutes before the Verinoda rows of this run, and were not rerun (see "Confounds").

## Tool use in the Verinoda arm

| | sessions | with an `analyze` call | `analyze` was the first tool | no Verinoda call |
|---|---|---|---|---|
| all | 39 | 37 | 37 | 2 |
| `why` | 11 | 11 | 11 | 0 |
| `when` | 10 | 10 | 10 | 0 |
| trap | 6 | 6 | 6 | 0 |
| `affects` | 12 | 10 | 10 | 2 |

Every `analyze` call had only the `question` argument (no `show`), one call per session, 2.1 s on average on the server side
(median 1.7, maximum 7.2; the usage log). The first tool of the plain arm was Grep in 24 of 24 sessions. The result is the lean
JSON (status, `understood_as`, claims with evidence, `leads`, `unknowns`, `context`, `coverage`): 2,994 characters per call on
average (median 2,453, maximum 11,997, just under the server's 12,000-character response cap; the lean view's own budget for the
parts it may cut is 2,500). The three results above 4,500 characters are what-does-it-affect answers whose answer claims list many
sites (their `subquestions` part is 6,061 to 10,257 characters; two of the three carry `truncated: true`). After the call the model
ran its own Grep, Read or Bash in every one of the 37 sessions, as the rule asks (own-tool model calls per session 2.05).

Where the task's gold sits in the `analyze` results (sessions that called it, with a gold file or commit):

| | sessions | result |
|---|---|---|
| gold file in `leads` | 31 | 30; rank 1 in 21 |
| gold commit anywhere in the `analyze` result | 28 | 17 |
| the answer names the gold commit | 28 | 21 |

`leads` hold `path:lines  symbol  (why)` strings, never a commit, so a gold commit is never "in `leads`" (0 of 28); where the
result carried it, it was elsewhere in the result (a claim's text or evidence, an unknown's commit list). Per session:
`analysis/analysis.json` (`verinoda_arm.gold_detail`).

The two sessions without a call: `junegunn__fzf-affects-1` (Grep, Read, Read, Grep, Bash; 0.0697 USD) and
`expressjs__express-affects-1` (Grep, Read, Read, Grep; 0.0588 USD). No assistant text block of either mentions Verinoda; the
thinking blocks of this CLI are empty in the transcripts, so why they skipped it is not known.

## The six D185 tasks (Verinoda arm, 3 repeats)

D185 columns are the first run's own sessions (`claims-2026-10-11`, read only, judge rows as written there); false fact =
answers with at least one claim the judge graded an incorrect fact, out of 3. The first run's traps were also rerun with opaque
copy names (as this run's copies are); both are shown.

| task | D185 plain | D185 Verinoda (GUIDE) | D186 Verinoda (call rule) |
|---|---|---|---|
| `fastapi__full-stack-fastapi-template-why-1` | false fact 2/3, gold commit cited 1/3 | false fact 3/3, cited 0/3; 6 Verinoda calls | false fact 0/3, cited 3/3; 3 calls, 0.052 USD |
| `junegunn__fzf-why-1` | 0/3, cited 1/3 | 2/3, cited 1/3; 4 calls | 0/3, cited 3/3; 3 calls, 0.066 USD |
| `guzzle__guzzle-trap-1` | 3/3 (opaque rerun 3/3) | 0/3 (opaque rerun 0/3); 6 calls | **3/3**; 3 calls, 0.064 USD |
| `gin-gonic__gin-trap-1` | 1/3 (opaque rerun 0/3) | 2/3 (opaque rerun 0/3); 6 calls | 0/3 by the judge; 3 calls, 0.063 USD |
| `axios__axios-when-1` | 0/3, cited 3/3 | 0/3, cited 3/3; 6 calls | 0/3, cited 3/3; 3 calls, 0.069 USD |
| `sharkdp__bat-when-1` | 0/3, cited 3/3 | 0/3, cited 3/3; 6 calls | 0/3, cited 3/3; 3 calls, 0.047 USD |

All six trap sessions were judged `unknown_said` (the answers say the repository does not hold the reason); so were the D185
sessions of these two traps. The D185 README's attributions are reproduced by these counts (fastapi: plain
repeats 1 and 2 and every Verinoda repeat; fzf: Verinoda repeats 2 and 3; guzzle: plain repeats 1 to 3; gin: plain repeat 1,
Verinoda repeats 1 and 2).

What the design expected (section 8, item 3) against what the sessions did, one task at a time; the sentences are quoted in
`analysis/hand_reading_six.json` (my reading, not the judge's):

| task | expected | observed |
|---|---|---|
| fastapi why-1 | `546dc8b` in the answer, no absence assertion | `546dc8b` with its stated reason ("from a query parameter to a body parameter for security") in 3 of 3; no sentence asserts that no reason exists; the nearest negatives are scoped ("The commit message does not spell out the specific risk.") and true. The `analyze` result carried `546dc8b` (a claim, `primary_source_verified`) in 3 of 3; the model then ran Grep and `git show 546dc8b` |
| fzf why-1 | none stated | `1578b7c3` with the reason (EINTR counted against a 100-iteration limit, Fatal event, exit status 2, only the cancellable path) in 3 of 3; the gold file `src/tui/light_unix.go` was lead 2 in the three results, the commit in 2 of 3 results |
| guzzle trap-1 | no "first appears in `b58db450`" | **not met.** 3 of 3 answers say `b58db450` is where the string was added or the earliest commit that adds it: r1 "The identical string was added in commit `b58db450` ... It was in the file's first version, and I found no earlier or later change to it."; r2 "`git log -S'>>>>>>>>'` over the formatter files shows `b58db450` ... as the earliest commit that adds the `>>>>>>>>` string."; r3 the same scoped to two paths ("I ran `git log -S` on those two files only, so I didn't check other paths."). Git: the string is added or removed by five commits, the oldest `91f1e347` (2012-09-09). All three `analyze` results listed `91f1e347` as the path-free "first appearance of `MessageFormatter`"; one answer (r2) named it next to `b58db450` without reconciling the two. All three answers also said the reason is unknown, which is right. Judge: 2, 1 and 1 incorrect fact claims |
| gin trap-1 | the general rule of 4.3 names `15216a0` as a lead | **not observed.** The `analyze` results listed `8f30478` as the first appearance of `abortIndex` (the rename); `15216a0` is in no Verinoda result and in no answer. The sessions then ran their own git: 3 of 3 answers name `31323f6` ("AbortIndex is missing", 2015-03-26) as where `AbortIndex = math.MaxInt8 / 2` was added, r1 and r2 as "first added". Git: `15216a0` (the initial commit) has the text; `31323f6` put back what `aa9fad5` had removed. The judge graded no claim incorrect, so the judge and my reading differ here. All three said the reason is unknown, which is right |
| axios when-1 | the one when task the term rule can fix | 3 of 3 correct (`39955a6`, 2026-08-04, `lib/helpers/HttpStatusCode.js:53`), as in D185 in both arms: nothing to fix was visible |
| bat when-1 | must stay as today | stayed: `1838e25d`, 2025-10-08, `Cargo.toml:35` in 3 of 3; the second gold statement, the reason, is not given in any of the three |

The 18 sessions in one table (tool order, what the `analyze` result held of the gold, the answer, the judge): `analysis/tables.md`,
section "The six tasks in detail".

## The cost sample (24 pairs)

Per session, repeat 1, 24 tasks, both arms; the Verinoda row of three tasks is the session of the six-task part.

| per session | plain mean | plain median | Verinoda mean | Verinoda median |
|---|---|---|---|---|
| dollars (CLI `total_cost_usd`) | 0.0576 | 0.0561 | 0.0633 | 0.0643 |
| model calls | 3.50 | 3 | 3.17 | 3 |
| own-tool model calls (Bash, Read, Grep, Glob) | 2.50 | 2 | 2.00 | 2 |
| tool calls | 3.42 | 3 | 3.42 | 3 |
| Verinoda calls | 0 | 0 | 0.92 | 1 |
| cache-write tokens | 9,307 | 8,720 | 11,059 | 10,920 |
| first model call's cache write | 6,741 | 6,242 | 7,835 | 7,335 |
| cache-read tokens | 75,990 | 71,140 | 74,235 | 69,926 |
| output tokens | 1,271 | 1,244 | 1,160 | 1,148 |
| Verinoda result characters | 0 | 0 | 3,136 | 2,484 |
| own-tool result characters | 4,623 | 3,724 | 2,974 | 2,918 |
| answer characters | 2,077 | 1,948 | 1,862 | 1,818 |
| seconds | 16 | 16 | 16 | 16 |

Paired differences, Verinoda minus plain (24 pairs; percentile bootstrap, 10,000 resamples, seed 20261013, the rule of
`swebench_score.boot`):

| measure | difference | 95 % interval | pairs Verinoda higher / equal / lower |
|---|---|---|---|
| dollars | **+0.0057** | +0.0023 to +0.0085 | 21 / 0 / 3 |
| model calls | -0.33 | -0.62 to -0.04 | 2 / 14 / 8 |
| own-tool model calls | -0.50 | -0.83 to -0.17 | 1 / 14 / 9 |
| cache-write tokens | +1,752 | +1,009 to +2,331 | 22 / 0 / 2 |
| first model call's cache write | +1,095 | +1,093 to +1,097 | 24 / 0 / 0 |
| cache-read tokens | -1,756 | -9,603 to +5,734 | 16 / 0 / 8 |
| output tokens | -111 | -192 to -27 | 8 / 0 / 16 |
| Verinoda result characters | +3,136 | +2,267 to +4,204 | 22 / 2 / 0 |
| own-tool result characters | -1,650 | -3,228 to -525 | 7 / 0 / 17 |
| answer characters | -216 | -348 to -76 | 7 / 0 / 17 |

By kind (descriptive): `why` (7 pairs) +0.0054 (+0.0001 to +0.0098); `when` (5) +0.0071 (+0.0035 to +0.0102); `affects` (12)
+0.0054 (-0.0005 to +0.0099). The median paired difference is +0.0077; the 3 pairs where Verinoda was cheaper are -0.0193,
-0.0083 and -0.0079. Pairs where the Verinoda session called `analyze` (22): +0.0053 (+0.0018 to +0.0083); the two pairs where
it did not: +0.0089 and +0.0112 (two numbers, no interval).

**Where the dollars go.** The price table 2 / 4 / 0.10 / 10 USD per million tokens (uncached input, cache write, cache read,
output; the design's table with the D185 cache-read price) reproduces the CLI's dollars in all 63 sessions with zero residual
(the 0.20 cache-read table does not: largest residual 0.0129 USD). Under it the paired +0.0057 is cache writes +0.0070, output
-0.0011, cache reads -0.0002, uncached input 0. The fixed context (rule, server instructions, skill listing, three tool schemas) is
+1,095 cache-written tokens at the first model call of every session (the interval is 4 tokens wide: it is the same in every
pair), +0.0044 USD, plus about 975 more cache-read tokens there. The remaining +657 written tokens come after the first call: what
the `analyze` result and the later turns write, net of the smaller own-tool results (an attribution by construction, not a
separate measure).

**Against D185 on the same 24 tasks** (its own sessions, repeat 1, 24 per arm, read from its transcripts, 144 of 144 present and
equal to the result JSON's usage):

| per session | D185 plain | D185 Verinoda (GUIDE) | D186 plain | D186 Verinoda (call rule) |
|---|---|---|---|---|
| dollars | 0.0582 | 0.0953 | 0.0576 | 0.0633 |
| model calls | 3.58 | 4.12 | 3.50 | 3.17 |
| own-tool model calls | 2.58 | 1.25 | 2.50 | 2.00 |
| Verinoda calls | 0 | 1.88 | 0 | 0.92 |
| cache-write tokens | 9,429 | 17,546 | 9,307 | 11,059 |
| Verinoda result characters | 0 | 16,179 | 0 | 3,136 |
| own-tool result characters | 4,797 | 1,850 | 4,623 | 2,974 |
| answer characters | 1,969 | 2,374 | 2,077 | 1,862 |

D185 paired (Verinoda minus plain): dollars +0.0371 (+0.0329 to +0.0411), model calls +0.54 (+0.25 to +0.83), own-tool model
calls -1.33 (-1.62 to -1.04), cache writes +8,117 (+7,242 to +8,916). The two plain arms agree within 1.1 % in dollars (0.0582 and
0.0576 on the same tasks, two days apart).

The design's lines (section 8, item 4): *the interval excludes +0.015*: yes, its upper end is +0.0085. *Verinoda output at most
4,500 characters per session*: true of the mean and the median (3,136 and 2,484 in the pairs; 2,840 and 2,433 over all 39), not of 3
sessions (above). *Own model calls at most plain minus 1.5* belongs to the `show="lead"` variant of 4.1b, which was not run (no call
had a `show` argument): the observed difference with the default `analyze` is -0.50, not -1.5.

## Judge, citations, blinding

The blind judge (`claims_score.py`, unchanged) ran once over all 63 answers: 63 parsed, 0 failed (24 of 24 plain, 39 of 39
Verinoda).

| | plain (24 answers) | Verinoda (39 answers) |
|---|---|---|
| answers with at least one incorrect fact claim | 2 | 3 (all three the guzzle trap) |
| claims (fact / inference) | 266 (220 / 46) | 372 (324 / 48) |
| correct / incorrect / not in gold | 118 / 5 / 143 | 187 / 4 / 181 |
| trap verdicts | none in this arm | `unknown_said` 6 of 6 |

The plain arm's two: `fastapi__...-why-1` ("The repository does not state the reason the password is in the body rather than the
query string; no comment, docstring or commit message explains it.", the D185 failure) and `expressjs__express-why-1`. The paired
summary (`summary.json`, 24 tasks): answerable false-fact share plain 0.083, Verinoda 0.000, difference -0.083 (-0.208 to 0.000),
no claim; the trap measure is empty (no plain trap session here). Of the secondary measures only the share of claims marked as
inference reaches a claim (0.170 plain, 0.119 Verinoda, -0.052, -0.081 to -0.023); it is one of four, unplanned for this sample,
and not adjusted. With 24 tasks and 2 false-fact answers in the plain arm none of this can show a difference or its absence.

**Citations** (mechanical check of every `path:line` and commit hash against the session's own copy):

| | plain | Verinoda | Verinoda, the six tasks |
|---|---|---|---|
| citations | 259 | 298 | 108 |
| lenient (`claims_score.py`): confirmed / wrong | 255 / 4 (98.5 %) | 295 / 3 (99.0 %) | 107 / 1 (99.1 %) |
| strict (`claims_mech_strict.py`): confirmed / wrong | 204 / 55 (78.8 %) | 246 / 52 (82.6 %) | 97 / 11 (89.8 %) |

No citation was `missing` or `not_repo` in either check. The D185 lenient shares were 97.5 % (plain) and 95.8 % (Verinoda); the
strict check was not run on the D185 answers, so its figures have no earlier counterpart. The lenient check is the upper bound the
D185 README describes; the strict one reads only the cited lines and whole words, and its `wrong` verdicts were not hand-checked
here, so they are not a count of false citations.

**Blinding failed again**: the judge guessed the arm right in 44 of 63 answers (69.8 %, interval 58.7 % to 81.0 %; D185 72 %).
16 of the 39 Verinoda answers carry a `[tool]` mask (0.74 per answer; D185 4.06) against 0 of 24 plain; the answers differ in
length and form as well. The hand check of 40 judged claims (`hand_check.md`, no arm) is not done.

## Confounds and checks

- **Different windows.** The plain rows were run at 01:16 to 01:22, the Verinoda rows at 02:30 to 02:38 on the same day. The plain
  arm needs no code, and the D185 plain arm, two days earlier, agrees with it within 1.1 % in dollars, but a drift between windows
  is not separable in this sample. A fresh plain arm in the Verinoda window would remove the question (about 1.4 USD, not run).
- **Cold prompt cache.** The first session of each arm in time order was not the dearest: plain 0.0469 USD (median of the rest
  0.0561), Verinoda 0.0518 (0.0643); the first model call of the first session already read 16,422 (plain) and 17,397 (Verinoda)
  cached tokens, which is also the median over the later sessions' first calls. The paired dollars without the pairs that hold the first session of either arm: +0.0059
  (+0.0023 to +0.0089). No cold-cache effect shows.
- **Transcript totals.** The summed usage of every session's transcript equals the result JSON's input and output tokens in 63 of 63
  sessions (D185's 144 of 144 as well); the transcript chars of `analyze` results equal the usage log's in 37 of 37.
- **The reminder.** The transcripts record the engine's `deferred_tools_delta` attachment, which still names the five Verinoda
  tools in all 39 sessions; the mod's `prompt.attachment` hook changes what the model sees, not the record. Whether the model saw the
  corrected reminder is therefore not readable here. What it did is: it called `analyze` first in 37 of 39.
- **Same prompt, three repeats.** The 18 sessions of the six tasks are 6 questions asked 3 times; the model's own question to
  `analyze` differed from the task's wording (it sometimes put identifiers into it, e.g. `abortIndex = math.MaxInt8 / 2`), which is
  what the gin lead followed.

## Not measured

- The effect of any single change (the rule's wording, the corrected reminder, the `analyze` description, the lean result, the
  GUIDE's removal). Only the two configurations are compared, once.
- Accuracy parity or a difference: 30 tasks, one repeat for 21 of them, 2 false-fact answers in the plain arm.
- The `show="lead"` variant of 4.1b (no call used it) and any second 24-pair sample.
- Whether the first-tool rate (37 of 39) holds on other repositories, other question kinds or another model; the two misses were
  both what-does-it-affect questions.
- What the model saw of the corrected deferred-tools reminder (above).
- Cost on SWE-bench-style tasks (the design's cost model input; not re-run), and any run on code the agent writes.
- A hand check of the judge's grades and of the strict check's `wrong` verdicts (the person's `hand_check.md` is blank).
- A plain arm in the same window as the Verinoda arm (above); an interval on the 1.10x ratio itself.
- The verdict audit and the eight no-model sets of the same plan task: other folders.

## Appendix: the set-aside run (`superseded-zero-call/`)

The first D186 run of the Verinoda arm (the same two commands, 2026-10-13 01:07 to 01:22, code at `68b2133`, the mod's rule as it
was before the fix) is measured data of the configuration before the rule fix: **39 Verinoda sessions, 0 Verinoda calls**, the
first tool Grep in 38 and Bash in 1, no ToolSearch call, no session error; the rule and the server's instructions were in the
context, and the three core tools were in the model's callable list (debug log of probe p1: `tool.describe mcp__verinoda__analyze:
a hook set isDeferred true -> false` for the three, `Dynamic tool loading: 0/19 deferred tools included`; probe p2: the model named
the three among its callable functions; both in `analysis/` here, p1 as an excerpt). The folder holds those 39 rows, their usage
logs, the 27 judge rows made before the scoring was stopped, the mechanical check, the logs, the config and its own README. It is
not part of the comparison above. The message of `380e6a0` (merged in `320c0b0`) names two causes: the rule's last sentence ("A
question one grep or one file read answers needs no Verinoda call.") and the engine's reminder of the tools behind ToolSearch,
composed before the `tool.describe` answers apply, which named the three pinned tools; it changed the rule, the reminder and
the `analyze` description, and reports its own probes on the six tasks (one session each), which are not in this folder. The 24
plain rows of this folder are the plain rows of that first run.

## Files

| file | what |
|---|---|
| `config.json`, `tasks.json` | the config as run; the 40 tasks as the harness wrote them |
| `results.jsonl` | 63 rows, one per session with the full answer: 24 plain (01:16 run) and 39 Verinoda (this run) |
| `judge.jsonl`, `mechanical.jsonl`, `mechanical-strict.jsonl` | the judge's claims, grades, trap verdicts and arm guesses; every citation with the lenient verdict; with the strict verdict |
| `summary.json` | `claims_score.py`'s paired summary and cost block |
| `hand_check.json`, `hand_check.md`, `hand_check_key.json` | the 40 claims for the person (no arm) and the key; not graded |
| `usage/` | the 39 Verinoda sessions' usage logs of this run (the mod's `graph-state`, the server's `mcp`, and `analyze`) |
| `logs/` | the harness and scoring logs of this run, with the code state and start times |
| `analysis/` | `analyze_sessions.py` (per session: tool order, Verinoda calls, model calls, tokens, characters, `analyze` leads and gold ranks; per arm; the paired bootstrap), `compare_d185.py` (the D185 side), `make_tables.py`, their outputs `analysis.json`, `d185-comparison.json`, `tables.md`, the hand reading `hand_reading_six.json`, the dry check `dry_plan.py` / `dry-plan.json` (taken before the run: what the two commands would run), the scripts that set the first run aside (`split_superseded.py`, `move_usage.py`), the one that built this folder (`assemble_results.py`) and the probe (`probe_deferral.py`, `probe_prompt_tools.txt`, `probe-p1-debug-excerpt.log`) |
| `superseded-zero-call/` | the appendix, with its own README (paths in it are explained at its top) |

The scripts read the sessions' transcripts from `~/.claude/projects/` and default to the paths of this machine; the per-session
numbers they computed are in `analysis/analysis.json`, so the tables do not depend on the transcripts surviving.
