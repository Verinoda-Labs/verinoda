# Verinoda Lean: the redesign for equal accuracy at lower cost (D186)

Date: 2026-10-12. Branch `symbiosis-redesign-2026-10-12`. Status: draft for adversarial review, then plan.

## 1. The goal, and what the measurements allow

The owner's goal: Verinoda must beat both graphify and tool-less Claude Code on accuracy and on cost; files may be
deleted and the architecture changed; cybersecurity matters; no further measurement studies, only cheap re-runs.

What twelve agent studies (about 2,500 sessions) and the no-model benchmarks say:

- Graphify is beaten on every no-model axis (eight sets: query 284/319 facts at 1,313 tokens per question against
  Graphify 0.9.73 67/319 at 1,480; ContextBench cited file recall 0.570 against 0.404). In agent loops both tools
  are at zero against the plain agent. Graphify wins only standing-context size and index latency.
- The plain agent is at the ceiling on every accuracy measure tried: file recall 84-98% of gold, SWE-bench Lite
  72 = 72, false facts 4.4% of answers (D185). No tool moved accuracy outside its interval.
- The one task class where the plain agent is measured to fail is git history across a file move or a path
  restriction: `git log -S -- path` cannot see a one-for-one line change or a pre-move commit, and the model then
  states the absence or the wrong origin as a fact (7 of 12 false facts on answerable D185 tasks; the guzzle trap:
  plain wrong 3/3, Verinoda's path-free search right 3/3).
- Cost: Verinoda saved tokens at equal facts on small corpora (0.84x input [0.78-0.91]), did not replicate on real
  repositories (1.14x: one more sequential model call per session), and every guided-protocol study cost more
  (SWE-bench +60% dollars, D185 1.66x).

So the honest target is:

> **Equal accuracy everywhere it was measured, strictly lower dollars per session than tool-less Claude Code on
> repositories of 250-1,000 files, and correct history where git is blind (renames, moves, path-restricted
> searches), made systematic.** Any change that adds output without a cost argument fails this document.

## 2. The cost model the design must satisfy

From the 200 SWE-bench Lite transcripts (D184), with the harness's exact price table ($2 / $4 / $0.20 / $10 per
million tokens for uncached input, cache write, cache read, output; residual $0.00):

| per session (mean) | plain | Verinoda | difference |
|---|---|---|---|
| dollars | 0.0794 | 0.1288 | +0.0494 |
| model calls | 4.89 | 6.56 | +1.67 |
| cache writes (new context) | 9,948 | 18,380 | +8,432 tokens |
| cache reads | 121k | 184k | +63k tokens |

Of the +$4.95 over 100 instances: cache writes +$3.37 (68%), cache reads +$1.26 (26%), output +$0.31 (6%).
What entered context: analyze 10,495 chars median per call (23/100 cut at the 12,000-char cap), code_check 3,772
chars, the ToolSearch schema load 1,217 tokens, the guide paragraph. The per-call fixed overhead (instructions,
descriptions) is +1,155 tokens per call, about $0.0015 per session: not the lever. D185 (240 transcripts) has the
same shape: cache writes carry +$0.030 of the +$0.036 gap; Verinoda output 18,064 chars per session.

Each extra model call costs about $0.006-0.008 at a 24-35k context even with an empty result, so **output cuts
alone cannot reach parity while the call structure stays**. Parity needs three things at once:

1. No model call spent on loading tools (the ToolSearch turn): the core tools are listed in front.
2. No model call spent on a check that finds nothing (code_check: 96/99 calls found nothing): it runs as a hook
   that speaks only when it has a finding.
3. Each remaining Verinoda result small enough to cost less than the own tool calls it replaces: analyze under
   2,500 chars (it replaces a Grep of about 1,100 chars and part of a Read), history under 2,000 chars.

Arithmetic on the SWE-bench numbers: removing the ToolSearch call (-$0.011), the code_check call and result
(-$0.009) and 8,000 chars of analyze output (-$0.012) closes about $0.032 of the $0.049 gap; the analyze call
itself (+$0.007) must then displace at least two own calls to go below parity. It displaced 0.7 with the gold file
at rank 1 in only 25 of 100 answers; the lead ranking in §4.1 is what makes the bet winnable, and the re-run in
§8 is what checks it.

## 3. What is already done on this branch (commits b1da5ef, 6036da0, 00c89b7)

- `cap_response` keeps both ends of a commit list and names every dropped commit as `sha date` (the D185 gold
  commit was position 11 of 14 and was cut silently).
- A why-question reads 20 commits of the symbol's lines; a commit becomes a claim only when its message states a
  reason and shares a topic word with the question (stem for stem, the subject's own name excluded); the others are
  leads, one line each, in an unknown whose next step names `git show` and `history_search`.
- The top-level status is derived from the sub-questions: `answered`, `partly_answered`, `unanswered` (it was the
  literal "answered" in 220 of 220 study calls).
- A claim the verdict gate set aside is not listed as an answer; the "documents state intent" note needs a document.
- On the real fastapi copy the why question is now answered by the gold commit alone, in 10.5k chars.

## 4. The design

### 4.1 `analyze` returns leads, not an investigation (cost: -8,000 chars per call)

Today's MCP response is 10,400-11,200 chars: passages 46% (the same text `project_query` returns), claims 34%
(8.8 claims per call, of which the sub-questions name 1-3 as answers), the rest plan check, critique, steps,
refresh prose. The model reads it as the whole investigation (own tool calls 3.6 to 1.2 per session; 15 of 100
SWE-bench sessions edited with no Read at all).

The new response, in this order, capped at 4,000 chars by its own builder (never by the generic compactor):

1. `status` (answered / partly_answered / unanswered) and `understood_as`, one line each.
2. Per sub-question: its status and its **answer claims in full** (text, status, evidence locators).
3. `leads`: at most 8 locations, each one line `path:a-b  symbol  (why it is here)`, ordered: the sub-questions'
   subjects first, then callers and callees of the subjects, then everything else; test, example, gallery,
   generated and vendored paths after source paths. (Gold file at rank 1 in 25/100 SWE-bench answers today.)
4. `unknowns` with their next steps (the why leads list of §3 lives here).
5. `context`: the other claims as one line each, `id status text`, at most 10; `claim_inspect` gives the rest.
6. One line of `coverage`: what was searched and what was not (index snapshot, stale files, refresh skipped).

Dropped from the MCP response (kept in `--json` on the CLI): passages (the response says `project_query <names>`
returns them), plan_check links, critique, steps, the index-refresh prose beyond one line, usage.
Measured guard: the D185 citation confirmation rate (96.6% upper bound) must not fall in the re-run.

### 4.2 `history_search` returns one flat list (cost: 28,725 chars to about 3,000 for a 14-commit history)

Every commit is emitted once as a row `sha date author subject`, newest first, all of them up to the limit
(default 30, max 100). Bodies (the quoted message) are attached only to the first K and the last K rows (K = 3)
and to any row whose message states a reason (the §3 rule); the `claims` list that repeated every commit is
removed; a claim is the row. The response says in one line which paths and moves were searched and which were
not ("HEAD history of path only; pre-move paths not searched" or "path-free"). A cut, if any, keeps both ends and
names the dropped rows (already shipped). `truncated` from the tool's own limit is reported as `more: true` with
the next call's arguments; the compactor's cut keeps its own key.

### 4.3 History where git is blind (accuracy: the one measured win, made systematic)

- Text mode: when the first event of a path-bound `git log -S` adds the whole file at a new path (`--- /dev/null`
  in the parse), the "first appeared" claim is `strong_inference` with the uncertainty "the file was created by
  this commit (a move or a rename): searched without path", and the path-free search runs automatically; its
  result replaces the claim when it finds an earlier commit. This is the false "first appears in 8558cf0 / b58db450"
  class that both arms produced (7 of 12 answerable false facts and 8 trap claims in D185).
- Regex mode and `commits(diff=...)` with exactly one file path pass `--follow` (and not `--no-renames`); a folder
  path keeps today's behaviour.
- A why-question whose symbol history (git log -L) yields no reason-stating commit runs the path-free text search
  on the question's code term as well, and its first-appearance commit joins the leads.
- A when-question (intent `history`) whose text names a code term (a backticked or snake_case/camelCase token,
  or a quoted string) runs `text_history` on that term, path-free, and reads it oldest first when the question
  says start / first / introduce / add; the gate marks a history claim weak for intent `history` unless the
  commit's message or diff carries the term (6 of 24 D185 when-sessions were "met" on the wrong symbol's three
  newest commits).
- Every history unknown states its scope: what was searched, what was not, how many commits were dropped.

### 4.4 `change_review` and `code_check` on the MCP side

- `change_review`'s MCP response drops `concerns_checked` and `reviewers` and compresses `coverage` to one line
  (they were 56% of its 6,439 chars); the CLI `--json` keeps them.
- `code_check` stays an MCP tool, but the mod no longer tells the model to call it after every edit; see §4.6.

### 4.5 Freshness: the index is not stale because of its own files

`.mcp.json`, `.claude/`, `.verinoda/` and the other files the installer writes are not stale files: no analyze
refresh, no background update is spawned for them (90 of 100 SWE-bench calls and 108 of 120 D185 calls refreshed
for `.mcp.json`, 4 s of a 5.7 s median call). The refresh inside analyze stays for real code changes.

### 4.6 The mod becomes two behaviours, and the agent-facing text becomes one rule

The mod (`claude-mods/verinoda-live`) keeps exactly what has a measured basis or a security need:

1. **Tools in front.** `tool.describe` marks `mcp__verinoda__analyze`, `project_query` and `run_tool` as not
   deferred, so no ToolSearch turn is spent and the tools are callable without a prompt that mandates them
   (`locate` listed in front was called in 51 of 63 and 22 of 40 sessions; deferred, 0 of 286).
2. **Freshness.** `verinoda update --fast` at the end of a turn that edited indexed files, in the background,
   with a status line (a stale index cost 1.18-1.23x input on 305-950-file repositories; fresh brought it back).

Deleted: the `search` auto-context mode (lost facts: 207 against 212, 1.29x output), the `nudge` mode (no gain on
real repositories, 0 of 206 sessions used Verinoda with it, and it told the model to run the CLI while the MCP
guide said the opposite), the assist features (`inject`, `coupled`, `gate`, `tool`, `prompt`; development-set
numbers only, the confirmatory run has no result file, and `gate` denies the model's own first search), the
session-start `check --stdin` warm-up and the locate daemon start, the commit-review guard on every git shell
command. The check-after-edit becomes opt-in (`check: true`): 0 notes in 65 edits in the guard study; when on, it
is a hook that writes nothing unless a name is absent, a type mismatches or the file no longer parses.
Kept untouched: the improvement checklist pane, the language pane and the mascot (person-facing, no token cost by
default, the owner's recent work).

Security (HIGH): the mod never resolves `verinoda` or `python` from the opened repository's `.venv`; it uses the
user's configured paths or `PATH`, runs python with `-I -P`, and reads nothing from the project's store in
non-interactive sessions.

The text: one status rule, in the server instructions tail and in a SKILL of at most 60 lines:
"state as fact what carries `statically_verified`, `primary_source_verified`, `observed` or
`experiment_verified`; `strong_inference` and below are not facts; Verinoda output is a lead: before stating
'no such change', 'first added in' or why something changed, confirm with one git or grep check of your own;
`truncated: true` or `more: true` proves no absence; a question one grep answers needs no Verinoda call."
The run_tool description loses its examples and repeated prose (about 40%). The study GUIDE strings are measured
artefacts and are not edited; a future arm copies the rule above.

### 4.7 Security fixes in the package (gate before anything is merged)

- One `gitexec.run()` helper carries `--no-optional-locks -c core.fsmonitor=false -c core.quotepath=off` and
  `GIT_OPTIONAL_LOCKS=0`; every bare `["git", ...]` caller uses it (about 20 call sites in 14 files); a test greps
  for the pattern outside the helper. (MEDIUM: a crafted `.git/config` could run a command on `git status`.)
- One `contained_path(root, rel)` helper (resolve, `relative_to(root)`, reject absolute, `..`, UNC and device
  paths) used by `Graph.source`, `evidence.check_source`, `evidence_inspect`, `evidence.read_lines` callers,
  `research._read_lines` and `history._head_lines`; evidence whose recorded root is not the repo, the research
  dir or a configured reference root is reported `gone`. (MEDIUM: a shipped graph.json could read any local file;
  a UNC path leaks NTLM credentials on Windows.)
- `history.py`: `--literal-pathspecs` on calls that take a user path, `--end-of-options` before revisions, the
  `rev` of `symbol_commits` validated; a per-call git timeout of 20 s for the MCP history tool so a pathological
  regex cannot hold the server lock for 120 s.
- The locate daemon's state (port, token) lives in the user config dir keyed by the repository's real path, never
  inside the repository.
- Decision records written over MCP are `agent_asserted` until the CLI confirms them.
- Reference fetches (full profile) reject private, loopback and link-local hosts, restrict schemes to https and
  ssh, and pass `--` before the source.
- Deferred with a note: an owner stamp for `.verinoda` (foreign index detection; migration cost for copied
  indexes) and read-only queries by default (the stale-index in-memory rebuild latency is not measured).

### 4.8 Deletions and dependency cuts (the owner opened this door; each has a measured or security reason)

- The upstream Graphify CLI surface inside `verinoda/project_index` and the `verinoda index -- ...` pass-through:
  19 modules (12,533 lines: cli, install, hooks, wiki, tree_html, scip/pg/cargo ingest, cross-repo graph,
  diagnostics, benchmark, manifest) and the 126 shipped skill Markdown files (24,844 lines). Reachable by no tool
  and no measured result; a second brand's installer and `~/.graphify` writers that a block list exists only to
  stop. `NOTICE` stays accurate for what remains vendored.
- The LLM, PR and media layer of `project_index`: `llm.py`, `prs.py`, `transcribe.py`, `google_workspace.py`,
  `exporters/graphdb.py`, the LLM branch of `dedup.py`, the PR views of `serve.py`, and the kimi / ollama /
  bedrock / anthropic / gemini / openai / video / neo4j / falkordb / postgres extras (5,500 lines; outbound
  network and API-key reading code inside an indexer whose design says "no LLM"). `verinoda/benchmark/llm.py`
  (critique eval) is separate and stays.
- `graspologic-native` moves to the existing `leiden` extra: 107 MB of scipy never imported at runtime leaves the
  default install (about 293 to 185 MB); `cluster.py` already falls back to networkx Louvain.
- Kept, with the reason: the Minecraft/JVM family (115 of the 284 facts in the Graphify comparison), `ui` (no
  default cost; the only graph viewer), the lab tools behind `--profile full` (zero agent exposure, but a split
  is weeks of work; recorded in BACKLOG), the benchmark package (reproducibility of the headline), the grammar
  set (needs a corpus check before cutting; BACKLOG).

### 4.9 What is deliberately not built

- A project brain / session-start card: no study spans two sessions or a compaction, and the one measured
  up-front injection lost facts (207 against 212). Recorded as a two-session study design in BACKLOG, not code.
- More file-recall studies on small repositories, more guided-protocol variants: measured at the ceiling.

## 5. Interfaces that change

- MCP `analyze`: new response shape (§4.1); `status` values `answered | partly_answered | unanswered` (shipped).
- MCP `history_search`: `commits` rows (+ `quoted` on K rows), `scope`, `more`; no `claims` list in symbol mode.
- MCP `change_review`: without `concerns_checked`, `reviewers`; `coverage` one line.
- Mod settings: `auto` (`off | nudge | search`) and the assist keys disappear; `check` default off.
- CLI: `verinoda index` removed; `--json` outputs unchanged except where the module is deleted.
- Python: `verinoda.gitexec.run`, `verinoda.paths.contained_path` (new), `analysis.overall_status` (shipped).

## 6. Documentation

One DESIGN.md section (D186) with why, decisions, measured, not done, tests; UPGRADING note; OZELLIKLER three
lines; ARCHITECTURE rows for removed modules; BACKLOG rows for the deferred items (lab split, grammars, owner
stamp, read-only queries, two-session study); README and UPSTREAM.md trimmed; BENCHMARK-BULGULARI §5 rewritten.

## 7. Risks named by the readers, and the answer

- Smaller analyze output may drop the file the model needed: the lead ranking keeps the sub-question subjects
  first; the re-run measures gold-in-leads and citation confirmation.
- Fewer "answered" words may make the model ignore the tool: that is the intended effect for unanswered questions;
  the re-run counts own tool calls.
- Deleting `nudge` loses the one measured small-corpus saving: it did not replicate on real repositories and the
  tools-in-front mechanism replaces its delivery role.
- Louvain is slower than Leiden on a self-update (3.4 s against 1.0 s on this repository): acceptable for 107 MB.
- The heuristic reason test can leave an explaining commit as a lead: the lead list names it; the model opens it.

## 8. Verification (cheap re-runs, no new study)

1. Unit and integration tests per task (TDD), the affected test files green, lint unchanged per file.
2. The D185 harness re-run on the exact failing tasks with the new arm, as a new dated results folder
   (`claims-rerun-2026-10-xx/`, config recorded, GUIDE replaced by the one rule of §4.6 as a dated amendment):
   fastapi why-1, fzf why-1, guzzle trap-1, gin trap-1 (3 repeats, Verinoda arm; about 12 sessions, under $1.50).
   Success: no absence assertion about 546dc8b; no "first appears in b58db450"; traps still "unknown".
3. A mechanism sample: 10 answerable D185 tasks, 1 repeat, both arms (20 sessions, about $1.50). Twenty sessions
   cannot show "strictly lower dollars" (the none-against-none noise floor was 1.03 [0.95-1.11] on 57 questions);
   they can show the mechanisms the cost model rests on: Verinoda output at most 4,000 chars per session, model
   calls per session at most the plain arm's, cache-write tokens at most the plain arm's, and the own tool calls
   per session. The dollar claim stays "expected from the SWE-bench cost model, not measured at this N" until a
   paired run of the size of D184 or D185 is affordable.
4. SWE-bench is not re-run now (about $25 and 7 h of Docker per repeat); its cost model is the design input.
