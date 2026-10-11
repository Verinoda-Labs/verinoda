# False claims: Claude Code with Verinoda against Claude Code alone on why / when / what-it-affects questions (pre-registration, 2026-10-11)

Written before any task was written and before any session ran. Every earlier study of this folder measured whether
Verinoda helps the agent find files or resolve issues, and every one found no measurable difference: on those tasks the
agent alone is at the ceiling (`DESIGN_BIG.md`, `DESIGN_SEL4.md`, `DESIGN_ASSIST.md`, `DESIGN_SWEBENCH.md`). None of
them measured what Verinoda is for: claims that carry evidence and a status, and `unknown` where the evidence is missing.
This study asks that question directly.

**The question:** when a Claude Code agent is asked why a piece of code is the way it is, when it changed, or what a change
to it would affect, does using Verinoda lower the share of answers that state something false, and raise the share of
answers that say "unknown" where the repository holds no answer?

Either result is progress. A null result closes the agent-facing line of the product; a positive one is the first
measured reason for it.

## Tasks

40 tasks over the ten pinned open-source repositories of `benchmarks/realworld/manifest.json` (130-974 tracked files,
seven languages; chosen on 2026-10-01 before Verinoda had run on them), 4 per repository, at each repository's pinned
`sha`. The clones for this study are **full clones** (`git clone` with no depth, then `checkout --detach <sha>`): the
real-world run used shallow clones, which hold no history to ask about.

Four kinds, fixed now, with the number of tasks of each:

| kind | the question asks | gold | n |
|---|---|---|---|
| `why` | why a piece of code does what it does, or why it changed | the rationale in the commit message and pull request text of the commit that made it, with its hash | 8 |
| `when` | when a behaviour, name or value was added or removed, and by which change | the commit `git log -S` / `git log -L` names, with its hash and date | 8 |
| `affects` | what else would have to change, or would break, if a named piece of code were changed | the files the originating commit touched, and the callers of the symbol found by text search and the language's syntax (not by Verinoda) | 14 |
| `trap` | one of the three above, about a thing that exists, where the repository holds **no answer** | `unknown` | 10 |

`affects` has the most tasks because it is where an agent alone was measured to lose its recall (D174: at the ceiling on
single-file tasks, losing nearly all of it on multi-file ones). For `why` and `when` the gold comes from git, and git is
open to both arms (`git log -S`, `blame` through Bash), so the headroom there is expected to be small: **a null result on
`why` and `when` confirms this expectation; it is not a finding against the tool.** A difference on `affects` and on the
traps is the one this study is built to detect.

### How a task is written

One agent writes the tasks, one repository at a time, from the full clone, the manifest's tag and the commit history
alone. It runs `git log`, `git log -S`, `git log -L`, `git blame`, `git show`, text search and the language's parser.
**It never runs Verinoda**, never reads `atlas.db` and never reads this repository's documents about the ten
repositories (`benchmarks/realworld/gold/`, the earlier studies' questions). Network is not used: pull request and issue
text is taken only where the commit message quotes or carries it (squash merges, `Co-authored-by`, "Closes #N" with the
text in the body); a commit whose body holds no rationale is not a `why` task, it is a candidate trap.

Rules for the writer, as in `DESIGN_REALWORLD.md`: no file name, path, line number or symbol spelling the question does
not need (a symbol a developer would ask about by name may be named); no wording copied from the commit message. Each
task is a JSON object with `id`, `repo`, `kind`, `question`, `gold` (the statements a correct answer contains, each with
its source: a commit hash, a `path:line`, or both), `gold_sources` (the commands that produced the gold, so that it can be
re-derived), and for `affects` tasks the gold file list.

**Traps are not about things that do not exist.** A question about an absent function is answered by a grep that finds
nothing, in both arms; it measures nothing. A trap is a `why` whose commit message is "fix" or "update" with no body and
no pull request text; a `when` about a value whose history `git log -S` cannot find because the file was moved without
`--follow` finding it or because the value entered with the initial import; an `affects` about a symbol with no caller
and no test. The gold of a trap is the word `unknown` and the reason it is unknown (what the writer looked for and did not
find), so that the judge can tell a confabulated answer from a true one that the writer missed: a trap whose answer the
agent demonstrably finds (with a citation the mechanical check confirms) is reclassified as answerable at scoring time
and reported as a writer's error, not scored as a confabulation.

A second, independent agent checks every task: a leak (a location or a detail only the gold gives), a gold statement the
commands under `gold_sources` do not reproduce, a trap whose answer it can find in ten minutes. A flagged task is
rewritten once and checked again; one still flagged is replaced. The 40 tasks and their gold are committed under
`benchmarks/agent_compare/claims_tasks.json` **before the first session**, pilot included.

## Arms

Real headless Claude Code sessions (`claude -p`), the model pinned in both arms, `claude-sonnet-5-5` (the SWE-bench
study's model; three repeats stay affordable), the same tools (`Bash Read Glob Grep`), user settings, plugins, skills and
MCP servers not loaded (`--setting-sources project,local --strict-mcp-config`), the user's own `verinoda` command off
`PATH`, at most 40 turns. Every session works in its own copy of the repository at the pinned sha (`git clone --shared`
of the full clone, detached); the copies of a task's two arms are made from the same clone. Network lookups are forbidden
and detected (`big_run.py`'s `NETWORK` rule: a session that fetched is kept in the data and marked).

**Both arms get the same stance.** The instruction below is in every session of both arms, word for word, so that the
only difference between the arms is the tool. An instruction to cite and to say "unknown" may by itself lower false
claims; if it does, it does so in both arms and is not credited to Verinoda.

> Answer the question below about this repository. Every factual statement you make must carry its evidence: a
> `path:line` of this checkout, a commit's short hash, or both. When you infer something you did not see, mark the
> statement as an inference ("likely", "it appears") rather than stating it as a fact. When the repository does not
> hold the answer, say so plainly ("unknown") and say what you looked for; do not guess. Do not use the network. Answer
> in English, as a short list of statements, each with its evidence.

- `none`: original Claude Code, nothing installed.
- `verinoda_guided`: `verinoda setup . --agents claude` (index, project skill, MCP server loaded with `--mcp-config`),
  the verinoda-live mod with `auto` at `nudge`, `VERINODA_USAGE_LOG` set (per-call cost, D178, measured here for the
  first time), and one paragraph after the shared instruction, because the earlier studies found the agent never calls
  Verinoda on its own (0 of 286 sessions):

  > Use the Verinoda tools first: `analyze` with the question; for a question about when or why something changed,
  > `run_tool` with `history_search`; for a question about what a change would affect, `run_tool` with `change_review`
  > or the `impact` view. Verinoda answers with claims that carry a status: state as fact only what it marks
  > `statically_verified` or what you confirmed yourself in the files; report its `unknown`s as unknown.

  The arm measures Verinoda **used**, not offered. A session of this arm that made no Verinoda call is kept in the result
  (intention to treat) and counted; a secondary comparison uses the sessions that did call it.

Each task runs 3 times per arm: 40 tasks x 2 arms x 3 repeats = 240 sessions, the two arms of a repeat started together.
The repeats show the agent's own run-to-run variation, which the SWE-bench study (one session per instance) could not.

## Measures

The unit is the **claim**, not the sentence: sentence splitting works differently on the two arms' prose, and a longer
answer would inflate a sentence count. An answer is split into claims by the judge model (step 2 below), each claim a
single factual statement with the evidence the answer attached to it.

Scoring, per claim, in two steps:

1. **Mechanical check of the citation** (`claims_score.py`, no model): a `path:line` exists in the checkout and the line
   (within 3 lines) holds the thing the claim says is there (the name, value or text the claim quotes); a hash names a
   commit of the clone, and the claim's statement about it (its date, its message, its files) matches `git show`. Each
   citation is `confirmed`, `wrong` (exists, does not hold it) or `missing` (no such line or commit). A claim with no
   citation is `uncited`.
2. **Blind judge** (a separate `claude -p` session of the same model, no tools): it sees the task's question, its gold,
   and the answer's **final text only**, with tool names, tool call traces and the words `verinoda`, `analyze`,
   `statically_verified` and `strong_inference` replaced by a neutral token, so that the arm is not readable from the
   style. It splits the answer into claims and grades each against the gold: `correct`, `incorrect`, `not_in_gold`
   (neither confirmed nor contradicted by the gold), and whether the claim is stated as a **fact** or marked as an
   **inference**. For a trap it answers one question: did the answer say unknown (`unknown_said`), or did it assert an
   answer (`confabulated`)?

   The judge's blinding is checked: on every answer it is also asked which arm produced it. If it is right well above
   chance (the 95 % interval of its accuracy excludes 0.5), blinding failed and the report says so; the result is then
   reported with that caveat, not discarded.

**Primary measures** (paired per task, the mean over a task's 3 repeats as the task's value):

- On the 30 answerable tasks: the share of answers that contain **at least one claim graded `incorrect` and stated as a
  fact**. A false inference is counted separately and is not in the primary measure: marking uncertainty is the
  behaviour this study wants to see, and a scorer that punished it would measure the wrong thing.
- On the 10 traps: the share of answers that **confabulated**.

**Secondary measures:**

- `incorrect` fact claims over all fact claims (a rate; answer length matters here and it is reported with the count).
- The share of `correct` claims that are `uncited` or whose citation is `wrong` or `missing` (Verinoda's thesis: a true
  claim should carry its evidence).
- The share of claims marked as inference.
- Per kind (`why`, `when`, `affects`, traps), the primary measures.
- Cost: turns, input and output tokens, dollars and seconds per session, and in the Verinoda arm the per-call usage
  log (calls, result characters, estimated tokens).
- A hand check: 40 claims drawn at random from the judge's output (20 per arm, the drawer not knowing the arm) are graded
  by a person; the disagreement rate with the judge is reported. A disagreement above 20 % stops the report until the
  judge prompt is revised and every claim is re-graded (the revision is written down).

**Decision rule.** For each primary measure, the paired difference (`verinoda_guided` minus `none`) with a bootstrap 95 %
interval over tasks (10,000 resamples). A claim is made only when the interval excludes zero. A difference inside the
interval is "no measured difference", with the interval, never "no difference". The `why` + `when` and the `affects`
subsets are reported apart, with the expectation stated above.

## Pilot, and how N is fixed

The first 8 tasks of the order below run first, 2 arms x 1 repeat (16 sessions): the harness, the clone and setup steps,
the mechanical check and the judge are exercised, and the `none` arm's rate of answers with an incorrect fact claim is
read. **If `none` is below 10 % on the answerable pilot tasks, 30 answerable tasks cannot show a halving**; then, before
any further session and in writing (an amendment at the end of this file, dated), one of two rules is chosen: the
answerable set grows to 60 (6 per repository, the writer's rules unchanged), or the primary measure becomes the traps
alone and the trap set grows to 20. The pilot's tasks and sessions stay in the sample; nothing seen is dropped or
replaced.

Task order: the 40 ids sorted by `sha256("20261011:" + id)`, fixed when the tasks are committed.

## Limits fixed now

- The instruction of the `verinoda_guided` arm is a manual steer by Verinoda's authors, and the tool is theirs. The task
  writer and the checker are agents run by the same people, with the rules above as the only independence.
- The gold for `why` is a commit message. A commit message can be wrong or incomplete about its own rationale; the gold
  is "what the repository says", not ground truth about the authors' minds. An answer that contradicts the message with
  a confirmed citation to code is graded by the judge as `not_in_gold`, not `incorrect`, and such cases are listed.
- `affects` gold is callers by text and syntax plus the originating commit's files. It is a lower bound: a caller through
  reflection or a string is not in it, and an answer naming one is `not_in_gold`.
- The model may have seen these repositories in training; both arms share that, and it may make `why` and `when` easier
  than they would be on private code. A trap is the one place where prior knowledge works against the agent (it may
  "remember" a rationale the repository does not carry); this is part of what the traps measure.
- One judge model, the same family as the agents. A judge that shares the agents' blind spots grades a shared false
  belief as correct only when the gold also holds it, which it does not (the gold is git), so the risk is in `not_in_gold`
  grading, which is secondary.
- 40 tasks (30 + 10). Per kind, 8 to 14 tasks: a difference inside a kind reaches no claim unless it is large; the
  per-kind tables are descriptive.

## Files

- `benchmarks/agent_compare/DESIGN_CLAIMS.md`: this file. Amendments are appended, dated, never edited in place.
- `benchmarks/agent_compare/claims_tasks.json`: the 40 tasks with gold and `gold_sources`, committed before the first
  session.
- `benchmarks/agent_compare/claims_tasks.py`: the writer's and checker's helpers (the git commands that derive a gold,
  the leak checks, the order), and the prompts given to the writer and the checker, verbatim.
- `benchmarks/agent_compare/claims_run.py`: clones, setup per arm, the sessions (standard library, `claude -p` as a
  subprocess, as `swebench_run.py`), one JSONL line per session with the final answer text, the transcript path, the
  usage, the network mark and the Verinoda call count.
- `benchmarks/agent_compare/claims_score.py`: the mechanical citation check, the judge call and its prompt verbatim, the
  blinding check, the paired bootstrap, the per-kind tables, the hand-check sample drawer.
- `benchmarks/results/claims-2026-10-<dd>/`: `tasks.json` (a copy at run time), `sessions-<arm>.jsonl`, `judge.jsonl`,
  `mechanical.jsonl`, `hand_check.json`, `summary.json`, `README.md` with every table. Published whatever the result,
  the pilot first.

## What is not measured here

- Verinoda **offered** without the instruction (measured five times already: never used).
- Whether a person reading the answers trusts them more or reviews them faster.
- Any effect on code the agent writes; this study is questions only.
- Languages the ten repositories do not cover, and repositories over 1,000 files.

## Amendment 2026-10-11: the guided arm's paragraph loads the tools first (before any task was written)

The SWE-bench pilot (`DESIGN_SWEBENCH.md`) found that an arm told only to use Verinoda called `analyze` in none of its
sessions: a plugin's MCP tools are deferred behind ToolSearch in this Claude Code, and a tool the model must look up
first is not called. Its guide therefore opens with the loading step. This study's guide paragraph lacked it; it is
replaced, before any task was written and before any session ran, by the paragraph below. The stance paragraph and
everything else are unchanged.

> Load the Verinoda tools first: call ToolSearch with the query
> `select:mcp__verinoda__analyze,mcp__verinoda__project_query,mcp__verinoda__run_tool`. Then use them before Grep, Glob,
> Read or a shell search: `analyze` with the question; for a question about when or why something changed, `run_tool`
> with `history_search`; for a question about what a change would affect, `run_tool` with `change_review` or the `impact`
> view. Verinoda answers with claims that carry a status: state as fact only what it marks `statically_verified` or what
> you confirmed yourself in the files; report its `unknown`s as unknown.
