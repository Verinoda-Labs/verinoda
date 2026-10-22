# Verinoda Lean: the redesign for equal accuracy at a cost near plain Claude (D186)

Date: 2026-10-12, revised the same day after three independent critiques (cost, accuracy, security and deletion
safety). Branch `symbiosis-redesign-2026-10-12`. Status: approved design, to plan.

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
  states the absence or the wrong origin as a fact (7 of 12 false facts on answerable D185 tasks are one absence
  assertion; the guzzle trap: plain wrong 3/3 per the README; the three Verinoda transcripts show the path-free
  history naming the older commit, a transcript observation, not a scored measure).
- Cost: Verinoda saved tokens at equal facts on small corpora (0.84x input [0.78-0.91]), did not replicate on real
  repositories (1.14x: one more sequential model call per session), and every guided-protocol study cost more
  (SWE-bench 1.62x dollars, D185 1.66x).

What the cost model (§2) allows, after the critique: a tool that replaces the agent's **search** can at best
displace the search calls the plain agent makes (1.31 model calls per SWE-bench session, 0.89 per D185 session),
and that is less than one Verinoda call costs with its result. So the honest target is:

> **Equal accuracy everywhere it was measured; dollars per session inside the paired interval of tool-less Claude
> Code (modelled 1.1-1.2x at today's displacement, down from 1.62-1.66x; parity only if the analyze result
> displaces a Read as well, which §4.1b tests); and correct history where git is blind (renames, moves,
> path-restricted searches), made systematic.** A change that adds output without a cost argument fails this
> document. "Strictly cheaper than plain Claude" is not promised: the data says it is not reachable by replacing
> search, and the one mechanism that could reach it (§4.1b) is an experiment with a stop rule, not a plan.

## 2. The cost model the design must satisfy

Prices are Claude Code's reported `total_cost_usd`, not an invoice: $2 / $4 / $0.20 / $10 per million tokens
(uncached input, cache write, cache read, output) fit the SWE-bench run with zero residual; the D185 run fits the
same table with cache reads at $0.10. Per-call figures below use the SWE-bench table; they are about half on D185.
Verinoda's JSON tokenizes at about 0.4 tokens per character (2.3-2.6 chars per token measured), not 0.25.

From the 200 SWE-bench Lite transcripts (D184), per session, mean:

| | plain | Verinoda | difference |
|---|---|---|---|
| dollars | 0.0794 | 0.1288 | +0.0494 |
| model calls | 4.89 | 6.56 | +1.67 |
| cache writes (new context) | 9,948 | 18,380 | +8,432 tokens |
| cache reads | 121k | 184k | +63k tokens |
| own-tool model calls | 3.89 (1.31 search-only) | 3.15 | 0.74 displaced |

Of the +$4.95 over 100 instances: cache writes +$3.37 (68%), cache reads +$1.26 (26%), output +$0.31 (6%). What
entered context: analyze 10,368 chars per call (4,480 tokens written; 23/100 cut at the 12,000-char cap),
code_check 3,765 chars, the ToolSearch schema load 1,209 tokens, the fixed text +1,362 tokens at the first call
(+$0.007 per session with its re-reads). D185 (240 transcripts) has the same shape: plain 2.70 own-tool model calls
(0.89 search-only), Verinoda 1.00 (1.70 displaced); Verinoda output 16,209 chars per session as the model saw it.

What each change is worth, at these prices (SWE-bench; D185 about half):

| change | per session |
|---|---|
| no ToolSearch turn (schemas stay in context, in front) | -$0.006 (isolated session) to -$0.009 (warm prefix) |
| code_check off by default (40/99 were a call of their own, 59 bundled with an edit) | -$0.009 |
| analyze output 10,368 -> 2,500 chars | -$0.017 (write) and smaller re-reads |
| nudge and skill listing cut | -$0.003 |
| remaining fixed text (instructions, two deferred names, skill line, the rule, in-front schemas) | +$0.006 |
| the analyze call with a 2,500-char result | +$0.011 (4,000 chars: +$0.0145) |
| a displaced own model call | -$0.0116 (D185: -$0.0074) |

Modelled result at today's displacement (0.74 on SWE-bench, 1.70 on D185): plain +$0.009 to +$0.012 on SWE-bench
(1.11-1.15x), plain +$0.006 to +$0.011 on D185 (1.10-1.19x). Parity on SWE-bench needs 1.49 displaced model calls
with a 2,500-char result; the plain agent has 1.31 search-only calls to displace. Parity therefore needs analyze to
displace a Read (§4.1b), or it is not reached. These numbers are modelled, not measured; §8 says what the re-runs
can resolve.

## 3. What is already done on this branch (b1da5ef, 6036da0, 00c89b7, c5829bd, c447343, ca1f8d3)

- `cap_response` keeps both ends of a commit list and names every dropped commit as `sha date` (the D185 gold
  commit was position 11 of 14 and was cut silently).
- A why-question reads 20 commits of the symbol's lines (`git log -L`, one call); a commit becomes a claim only
  when its message states a reason and shares a topic word with the question (stem for stem, the subject's own
  name excluded); the others are leads, one line each, in an unknown whose next step names `git show` and
  `history_search`. A when-question (intent `history`, the same handler) claims the commits about the question's
  words, else the newest, with no reason asked (the review found the reason gate had reached when-questions on the
  branch; fixed in ca1f8d3; the when-handler stays shared, see §4.3).
- The top-level status is derived from the sub-questions: `answered`, `partly_answered`, `unanswered` (it was the
  literal "answered" in 220 of 220 study calls). A claim the verdict gate set aside is not listed as an answer; the
  "documents state intent" note needs a document.
- Verinoda's own files and a `.mcp.json` holding only its server are not a change for the index; nothing changed
  means no refresh (analyze on the study copy about 1 s instead of 5-6; the 108/120 and 90/100 refresh counts come
  from the local transcripts, not from a committed result).
- The mod lists `mcp__verinoda__analyze`, `project_query` and `run_tool` in front of the model (`tool.describe`,
  `isDeferred: false`; the debug log of a headless session shows the three moved before the first API request).
  Listing alone did not make the model call them (one session, no rule: Grep, Read, Read, Bash), and neither did the
  first call rule: one headless session with it called analyze first and cited 546dc8b, but the D186 re-run (39
  headless sessions, Verinoda arm, that rule in the system prompt, the tools in front) saw no Verinoda call at all
  (first tool Grep in 38, Bash in 1). Two causes were found: the rule's way out ("a question one grep or one file
  read answers needs no Verinoda call"), and the engine's reminder of the tools behind ToolSearch, composed before
  the `tool.describe` answers apply, which named the three pinned tools and said a direct call fails. Probes on six
  re-run tasks, one session each: the rule without the way out, 3 of 6 calls; plus the reminder corrected, 4 of 6;
  plus "your first tool call is analyze" in the rule and an analyze description that says so, 5 of 6 (the miss a
  when-question the model answered with `git log -S`, rightly). The host caches the `tool.describe` answers for the
  session (a tool that appears later is not re-placed), because moving a tool into the array invalidates the cached
  prefix (about 16k tokens, about $0.065).
- On the real fastapi copy analyze answers the why question with the gold commit alone (verdict audit at HEAD:
  wrong_met 1/39 `forge-maxheat-declared`, above_ceiling 0, controls kept 15/22, the same as before the branch; the
  four JS/Java callers controls have been met_with_inference since D31, DESIGN.md:62 still says 19/22).

## 4. The design

### 4.1 `analyze` over MCP returns leads, not an investigation

Invariant: `analysis.analyze`'s result dict and `analysis_view.render_text` are unchanged by this section; the new
shape is built in `verinoda/mcp/server.py` from that dict. The no-model benchmark (`python -m verinoda.benchmark
run`, in-process analyze + `render_text`) and ContextBench (the CLI `verinoda analyze`) never see the MCP shape.

Today's MCP response is 10,400-11,200 chars: passages 46% (the same text `project_query` returns), claims 34%
(8.8 claims per call, of which the sub-questions name 1-3 as answers), the rest plan check, critique, steps,
refresh prose. The model reads it as the whole investigation (own tool calls 3.6 to 1.2 per session on D185; 15 of
100 SWE-bench sessions edited with no Read at all; both from the local transcripts).

The new response, in this order, at most 2,500 chars (about 1,000 tokens), cut by its own builder, never by the
generic compactor (`truncated` is never set on it):

1. `status` (answered / partly_answered / unanswered) and `understood_as`, one line each.
2. Per sub-question: its status and its **answer claims in full** (text, status, evidence locators).
3. `leads`: at most 8 locations, each one line `path:a-b  symbol  (why it is here)`, ordered: the files of the
   sub-questions' answer claims first, then the other claims' files, then the plan's linked mentions, then the
   passages' files; test, example, gallery, doc, generated and vendored paths after source paths. Checked offline
   on the 100 SWE-bench analyze outputs (scratchpad `rerank.py`, gold files from results.jsonl): the gold file is
   at rank 1 in 31 of 100 in the order the model reads today, 60 of 100 under this order; top 3: 46 against 76;
   top 8: 71 against 86; absent 8 against 11. Not measured: whether the model's first Read follows rank 1.
4. `unknowns` with their next steps (the why leads list of §3 lives here).
5. `context`: the other claims as one line each, `id status text`, at most 6; `claim_inspect` gives the rest.
6. One line of `coverage`: what was searched and what was not (snapshot, stale files, refresh skipped), and
   `project_query <names>` named as the way to the passages.

Cut order inside the builder when the budget is hit: context lines first, then leads beyond the sub-question
subjects, answer claims never. Dropped from the MCP response (kept in `--json` on the CLI and in the dict):
passages, plan_check links, critique, steps, usage, the refresh prose beyond one line.

Tests to replace, with the invariants that replace them: tests/test_mcp.py:840 (`{"claims","passages",
"plan_check","status"}`), :850 (`claims_in_passages`), :955-985 (the passages cut order), :1524-1575
(`cap_response` with `plan_check.links` and `passages`), and `ANALYZE_FIRST_CUT` (server.py:151). New invariants:
every answer claim listed in full; leads at most 8 with the subjects first; the response at most 2,500 chars with
`truncated` never set by the generic cap; `project_query <names>` named when passages are omitted.

### 4.1b The Read-displacing variant (an experiment with a stop rule, off by default)

Parity (§2) needs analyze to save the model a Read, not only a search. Variant `analyze(..., show="lead")`: the
response of §4.1 plus the numbered lines of the rank-1 lead's narrowest span (at most 60 lines, about 2,000 chars),
inside a 4,500-char budget. Measured by §8.3 with own model calls per arm as the primary measure. Stop rule: if the
Verinoda arm's own model calls are not at least 1.5 below the plain arm's on the sample, the variant stays off and
the design's cost claim is the 1.1-1.2x of §2. Round 3 of agent-compare (search results attached up front) lost
facts (207 against 212), so the variant is never injected; it is returned to a call the model made.

### 4.2 `history_search` returns one flat list

Every commit is emitted once as a row `sha date author subject`, newest first, all of them up to the limit
(default 30, max 100). Bodies (the quoted message) are attached only to the first K and the last K rows (K = 3)
and to any row whose message states a reason (the §3 rule); the `claims` list that repeated every commit is
removed; a claim is the row. The response says in one line which paths and moves were searched and which were
not. A cut, if any, keeps both ends and names the dropped rows (shipped). The tool's own limit is reported as
`more: true` with the next call's arguments; the compactor's cut keeps its own key. Budget: at most 2,000 chars
for 30 rows (a 14-commit history is about 1,400 chars of rows plus six bodies; today 28,725 chars of JSON for
5,361 chars of git output, per the usage logs; not re-measured).

### 4.3 History where git is blind

Two classes, two mechanisms, verified on the study clones by the review:

- **Text born in another file (the guzzle class).** The path-bound first event creates the file (`--- /dev/null`,
  which `_parse_patches` must record as `new_file`; today it discards the line). Then the first-appearance claim
  carries the uncertainty "created at this path; the text may have lived in another file", a path-free search
  runs oldest first (`git log -S<text> --format=%H%x1f%aI | tail -1`, then `git show -U0` of that one commit; 0.2
  to 2.7 s on the ten study clones; never the newest-first `-n201` read, which cuts the oldest), and the claim
  returns to `primary_source_verified` with scope "path-free" when the oldest commit is the same one. A project's
  first commit also creates the file; the path-free run returns the same commit and the status is restored.
- **A one-for-one change inside a moved file (the fastapi class).** `-S` is blind to it with or without a path
  (546dc8b is in none of the 22 `git log -Snew_password` commits). It is reached by `git log -L` (shipped: rank 11
  of 14 inside WHY_COMMITS=20) and by `--follow -G` (0.078 s on the clone). Regex mode and `commits(diff=...)`
  with exactly one file path pass `--follow` and drop `--no-renames`; text mode does the same when exactly one
  file path is given (the move commit then shows no occurrence change and drops out); a folder path keeps today's
  behaviour. Measured by the review: `--follow` adds at most 0.05 s per call on histories up to 6,100 commits.
- **The general rule for any path-bound text search.** Also read the path-free oldest commit; when it is older
  than the path-bound first event, state it in the claim's uncertainty and as a lead ("the text existed earlier at
  another path: sha date subject"). This is the only rule that touches gin trap-1 (its path-bound first event is a
  modification; the true origin 15216a0 added the text in another file).
- **A why-question whose symbol history yields no reason-stating commit** also runs the path-free text search on
  the question's code term, and its first-appearance commit joins the leads.
- **When-questions.** The handler stays shared (§3) with no reason asked. A code term named in the question (a
  backticked token, a snake_case or camelCase identifier) gets its first appearance as a **lead, never the
  answer**: "first appearance of `term`: sha date subject (path-free)". It is read oldest first only for "when was
  X added / introduced" where X is the term itself. The rule never fires on a plain word or a dotted expression.
  Against the eight D185 when tasks it fires on one (axios, where the oldest is the gold); on four others the
  term's first appearance predates the asked-about change by 7-16 years, which is why it is a lead. The gate's
  `history` rule is not extended to diffs (text_history commits carry the term by construction; `-L` commits would
  need a patch read each).
- Every history unknown states its scope: what was searched, what was not, how many commits were dropped.
- Timeouts: `VERINODA_MCP_GIT_TIMEOUT`, default 60 s for `-S`, `-G` and `-L`, 20 s for `rev-parse` and `ls-files`;
  on expiry the tool returns `status: partial` with `timed_out: true`, what was searched and the next call's
  arguments, never a bare error; the automatic path-free search degrades the claim to `strong_inference` with
  "path-free search timed out" instead of failing the call. `history_search` runs outside the server's global lock
  (it only reads git and the loaded graph). The 60 s value is not measured on a 50k-commit repository.

### 4.4 `change_review` and `code_check` on the MCP side

- `change_review`'s MCP response drops `concerns_checked` and `reviewers` and compresses `coverage` to one line
  (they were 56% of its 6,439 chars per the usage logs); the CLI `--json` keeps them.
- `code_check` stays an MCP tool; the mod no longer tells the model to call it after every edit (§4.6). On the
  SWE-bench run it found an absent name in 3 of 99 calls, none acted on; one parse-break catch.

### 4.5 Freshness: the index is not stale because of its own files (shipped)

Excluded by name, not by type: the files `verinoda setup` and the mod write (`.mcp.json` holding only Verinoda's
server, `.claude/`, `.verinoda/`, the marked skill files), kept out of stale detection; a tracked `.mcp.json` the
user edits is still indexed as JSON. Known gap: a removed own file still counts as a change (the marker check runs
on a file that is gone); rare, recorded as not done.

### 4.6 The mod becomes two behaviours and the agent-facing text becomes one rule

The mod keeps exactly what has a measured basis or a security need:

1. **Tools in front** (shipped, §3). The hook matches the server named `verinoda` in the user's `.mcp.json`.
2. **The call rule.** A `prompt.compose` section of about 630 chars when the Verinoda MCP server is connected,
   naming the first tool call: "Your first tool call on a question that asks why something is the way it is, when
   or in which commit it changed, or what a change affects is `mcp__verinoda__analyze` with the question; Grep, Read
   and git come after it. It is in your tool list, not behind ToolSearch. It answers from the git history and the
   code graph with a verdict, claims and leads that carry file:line and commit hashes; `statically_verified` and
   `primary_source_verified` claims are verified, `strong_inference` and below are not. Confirm its lead with one
   git or grep check of your own before stating 'no such change', 'first added in' or why something changed." The
   first wording ("call analyze once ... a question one grep or one file read answers needs no Verinoda call") got
   no call in 39 of 39 re-run sessions (§3); the server's status rule and the analyze description say the same
   thing as this section, and the mod takes the three pinned names out of the engine's reminder of deferred tools.
   The rule asks for one own check: that lowers displacement by about one call on history questions and is priced
   in §2's 1.1-1.2x.
3. **Freshness.** `verinoda update --fast` at the end of a turn that edited indexed files, in the background, with a
   status line (a stale index cost 1.18-1.23x input on 305-950-file repositories; fresh brought it back). Runs
   only in a project the user has trusted (`verinoda trust --list`) or whose root is the session's cwd or an
   ancestor the user opened; a hostile repository's `.verinoda` folder must not make the mod run anything.

Deleted: the `search` auto-context mode (lost facts: 207 against 212, 1.29x output), the `nudge` mode (no gain on
real repositories; 0 of 206 sessions used Verinoda with it; fired once per D185 session, 875 chars, and told the
model to run the CLI while the guide said the opposite), the assist features (`inject`, `coupled`, `gate`, `tool`,
`prompt`: development-set numbers only, the confirmatory run has no result file, and `gate` denies the model's own
first search), the session-start `check --stdin` warm-up, the locate daemon start and its Read/Grep/Glob/shell
hooks, the commit-review guard on every git shell command. The check-after-edit becomes opt-in (`check: true`): 0
notes in 65 edits in the guard study; when on, it is a hook that writes nothing unless a name is absent, a type
mismatches or the file no longer parses. The `tool.describe` hook for the assist tools goes in the same commit
that adds nothing new: the MCP-tool hook already exists (c447343), so the mechanism never disappears.
Kept untouched: the improvement checklist pane, the language pane and the mascot (person-facing, no token cost by
default, the owner's recent work).

Security of the mod (HIGH, from the review): the mod never resolves `verinoda` or `python` from the opened
repository's `.venv`; at session start it resolves `verinoda` and `git` once to absolute paths from `PATH` with a
lookup whose working directory is outside the repository (the user's home), caches them, and refuses a result that
lies inside the repository root (Windows searches the child's working directory before `PATH`; whether
`$.process.run` does is unverified, so the refusal is the guard). The graph-state python probe is replaced by a CLI
subcommand (`verinoda graph-state --json --repo R`) so the mod needs no python at all (`-P` would break Python
3.10, which pyproject allows; `-I` alone breaks user-site installs). A Windows test puts a fake `verinoda.exe` in
the repository root and checks it is not run.

The text: the one status rule above, in the server instructions tail and in a SKILL of at most 60 lines, with
the same sentence about `truncated: true` / `more: true` ("proves no absence; narrow the call or check with
git/grep yourself"). The run_tool description loses its examples and repeated prose (about 40%). The study GUIDE
strings are measured artefacts and are not edited; a future arm copies the rule above.

### 4.7 Security fixes in the package (a gate before anything is merged)

- **One git funnel.** `verinoda.gitexec.run` is the only place that builds a git argv; `snapshot.git`,
  `research._git`, `references.gitref.run_git`, `locate._GIT`, `hotspots._GIT` and `treestate._GIT_SAFE` delegate
  to it. It carries `--no-optional-locks -c core.fsmonitor=false -c core.quotepath=off` and `GIT_OPTIONAL_LOCKS=0`;
  callers that need locks or the real config (`update-index --refresh`, `core.hooksPath`) opt out explicitly.
  Before `status`, `diff`, `diff-index` or `update-index` in a repository the user has not trusted (`verinoda
  trust`), it reads `.git/config` and ignores the repository's local config (or refuses) when it carries
  `core.fsmonitor`, `filter.*`, `diff.*.command`, `diff.*.textconv`, `core.sshCommand` or `include.*`: the
  fsmonitor flag alone closes one of several command vectors (a `.gitattributes` `filter=` line is another; known
  git behaviour, not executed here). The guard test greps for `"git"` as the first element of any list or tuple
  and for `Popen`/`run`/`check_output` outside `gitexec`, excluding `benchmark/` and fixtures. `status` latency
  with `--no-optional-locks` on a stale-stat tree is not measured.
- **Path containment at the sources.** `verinoda.paths.contained_path(root, rel)` rejects lexically first, with
  `PureWindowsPath` on every OS (drive, anchor, a leading `\\` or `//`, `\\?\`, `\\.\`, a `:` stream suffix, `..`),
  and only then joins and resolves (resolving a UNC path first would itself open the SMB connection). It is applied
  once at the sources, so every `g.root / f` is safe by construction: `index.load()` drops or flags nodes whose
  `source_file` is absolute or escapes; the search and atlas readers (`search_index._read_lines`,
  `entail._file_text/_root`, `question_plan._file_lines`, `Graph.span`, `relations`, `sentences`, `precise`,
  `evidence.check_source`, `evidence_inspect`, `research._read_lines`, `history._head_lines`) go through it. The
  root allowlist for recorded evidence: the resolved repository; the project's git work-tree top (CODEOWNERS
  evidence of a subfolder project records it, ownership.py:561); `research_dir(repo)` and its children, checked
  after resolving; reference entries only when they resolve inside the repository. Roots are never taken from
  unprotected repository config (`index.reference` is not protected). A root that is a symlink or junction to a
  target outside those roots is `gone`. `evidence_inspect` omits `root` and `file_exists` for rejected evidence.
  Tests: a symlinked root is `gone`; ownership evidence in a subfolder project stays verifiable; a grep test for
  `Path(... meta ... root ...)` joins outside the helper.
- `history.py`: `--literal-pathspecs` on calls that take a user path (defence in depth: tests pass only prefixes,
  and `freshness.py` and `history.py:264` already use it; the tool description says `path` is a literal file or
  folder prefix, not a glob); `--end-of-options` before revisions (git 2.24 or later, which guards.py already
  relies on); the `rev` of `symbol_commits` validated with `_rev` (defence in depth: it is set only internally).
- The locate daemon's state (port, token) lives in the user config dir keyed by the repository's real path, never
  inside the repository.
- Decision records written over MCP are `agent_asserted` until the CLI confirms them.
- Reference fetches (full profile): `-c protocol.allow=never -c protocol.https.allow=always -c
  protocol.ssh.allow=always -c http.followRedirects=false`, `--` before the source, and a best-effort private-host
  check (DNS rebinding is not closed unless the connection is pinned; said so in the tool description).
- Deferred with a note in BACKLOG: an owner stamp for `.verinoda` (foreign index detection; migration cost for
  copied indexes) and read-only queries by default (the stale-index in-memory rebuild latency is not measured).

### 4.8 Deletions and dependency cuts (each with a measured or security reason, and the edits they force)

- **The upstream Graphify CLI surface** inside `verinoda/project_index` and the `verinoda index -- ...`
  pass-through: 18 modules (cli, __main__, install, hooks, tree_html, diagnostics, wiki, scip_ingest,
  semantic_cleanup, affected, cross_repo_calls, cross_repo_types, multigraph_compat, global_graph, pg_introspect,
  benchmark, cargo_introspect, manifest; `exporters/__init__.py` stays with `exporters/html.py` and `base.py`,
  which index.py and watch.py import) and the 126 shipped skill Markdown files. Reachable by no tool and no
  measured result. Forced edits: pyproject package-data to `["UPSTREAM_COMMIT"]` (doctor.py and the benchmark
  runner read it); tests/test_packaging.py MUST_SHIP and the skill-file counts; tests/test_cli.py pass-through and
  blocklist cases and the help line; tests/test_docs.py's `UPSTREAM_BLOCKED` test; `project_index/__init__.py:21`
  (`to_wiki`); `doctor.py:22`; `cli.py` `UPSTREAM_BLOCKED`, `UPSTREAM_HOME_WRITERS`, `cmd_index` and the subparser;
  README's Commands row; ARCHITECTURE rows; UPSTREAM.md's inventory.
- **The LLM, PR and media layer** of `project_index`: `llm.py`, `prs.py`, `transcribe.py`, `google_workspace.py`,
  `exporters/graphdb.py`, the LLM tiebreak of `dedup.py` (`_llm_tiebreak`, `dedup_llm_backend`), the PR views and
  the second MCP/HTTP server of `serve.py` (lines 1795-2689: `_build_server`, `serve`, `serve_http`,
  `_ApiKeyMiddleware`, `_main`; the query helpers above them stay, index.py:1268 and retrieval.py:144 use them),
  `ingest.py`'s tweet, arXiv and web fetchers (`OUTCOMES` moves out first; `reflect.py` imports it),
  `callflow_html.py` together with the `watch.py:2228-2243` block that imports it. Forced edits, or every scan
  fails: `detect.py:17-21` loses the google_workspace import and its three use sites (`.gdoc/.gsheet/.gslides`
  shortcut files stop being converted); `export.py:26` loses the graphdb import. Acceptance: `python -c "import
  verinoda.project_index.export, verinoda.project_index.detect, verinoda.project_index.watch"` succeeds;
  tests/test_index.py and tests/test_detect_git.py pass. Extras: kimi, ollama, bedrock, anthropic, gemini,
  openai, video, neo4j, falkordb, postgres, google and the markdownify line of pdf go; a `benchmark = ["tiktoken",
  "anthropic"]` extra is added (the harness's exact token counts and its critique eval need them; `all` includes
  it; doctor.py's hint and the benchmark README say so). Every edited vendored file gets a `Verinoda patch`
  comment and a line in UPSTREAM.md, as NOTICE requires; LICENSE, LICENSE-MIT and NOTICE stay in `license-files`.
- **The ported upstream test suite and the port tool.** `tests_upstream/` (295 files; 66 import deleted modules,
  and its `conftest.py` autouse fixture imports `llm.py`, so every remaining test would error at setup): the
  files that import deleted modules are deleted, the fixture loses the import, the CI `upstream` job
  (.github/workflows/ci.yml:92-102) runs what remains. `tools/port_upstream.py` re-copies upstream whole (it
  would recreate every deleted file): it gets a `DELETED` list applied after the copy, and UPGRADING.md and
  UPSTREAM.md say the sync now deletes them; `tools/skillgen/` (about 180 dead skill blobs) is retired.
  UPSTREAM.md's test table and README.md:42 are corrected to "not re-run".
- **`graspologic-native` leaves the mandatory dependencies**: a `leiden = ["graspologic-native>=1.3.1,<2"]` extra
  for all Python versions (today's `leiden` extra holds the full `graspologic` below 3.13, which is not the same
  thing), `all` updated, tests_upstream/test_backend_extras.py updated. 107 MB of scipy that is never imported
  leaves the default install (about 293 to 185 MB); `cluster.py` falls back to networkx Louvain. Not measured:
  the eight-set headline with Louvain (every result so far ran with Leiden), the clustering time on large graphs
  (3.4 s against 1.0 s on this repository is the pyproject comment, not a re-measurement); `_code_stamp` hashes
  the graspologic-native version, so existing indexes re-cluster once after the upgrade (UPGRADING note). Gate:
  `pytest tests` in a venv without graspologic-native before merging, result recorded.
- Kept, with the reason: the Minecraft/JVM family (115 of the 284 facts in the Graphify comparison), `ui` (no
  default cost; the only graph viewer), the lab tools behind `--profile full` (zero agent exposure, but a split is
  weeks of work; BACKLOG), the benchmark package (reproducibility of the headline), the grammar set (needs a
  corpus check before cutting; BACKLOG).

### 4.9 What is deliberately not built

- A project brain / session-start card: no study spans two sessions or a compaction, and the one measured
  up-front injection lost facts (207 against 212). Recorded as a two-session study design in BACKLOG, not code.
- More file-recall studies on small repositories, more guided-protocol variants: measured at the ceiling.
- A broader when-rule: on four of the eight D185 when tasks the term's first appearance predates the asked-about
  change by years; a loose rule would manufacture the false-history class on a kind that had zero false facts.

## 5. Interfaces that change

- MCP `analyze`: new response shape (§4.1); `status` values `answered | partly_answered | unanswered` (shipped);
  optional `show="lead"` (§4.1b, off by default).
- MCP `history_search`: `commits` rows (+ `quoted` on K rows), `scope`, `more`; no `claims` list in symbol mode.
- MCP `change_review`: without `concerns_checked`, `reviewers`; `coverage` one line.
- Mod settings: `auto` (`off | nudge | search`) and the assist keys disappear; `check` default off; the call rule
  section appears when the server is connected.
- CLI: `verinoda index` removed; `verinoda graph-state --json` added; `--json` outputs unchanged except where the
  module is deleted.
- Python: `verinoda.gitexec.run`, `verinoda.paths.contained_path` (new), `history._parse_patches` records
  `new_file`, `analysis.overall_status` and `verdict_gate.states_reason / shares_topic` (shipped).

## 6. Documentation

One DESIGN.md section (D186) with why, decisions, measured, not done, tests, and the numbers of §2-§3 copied in
with their source (the transcript scripts are session-local; the results folders hold no cost table); UPGRADING
note (the re-cluster, the removed command, the extras); OZELLIKLER three lines; ARCHITECTURE rows (removed
modules, `gitexec.py`, `contained_path`); BACKLOG rows for the deferred items (lab split, grammars, owner stamp,
read-only queries, two-session study, Louvain headline re-measurement); README, UPSTREAM.md, BENCHMARK-BULGULARI
§5 rewritten; DESIGN.md:62's 19/22 corrected to the audit at HEAD.

## 7. Risks named by the reviews, and the answer

- The cost claim: modelled, not measured; stated as 1.1-1.2x with the mechanism that could reach parity as an
  experiment (§4.1b) and a stop rule.
- Smaller analyze output may drop the file the model needed: the lead ranking keeps the answer claims' files
  first (gold at rank 1: 31 to 60 of 100 offline); §8 measures gold-in-leads and the model's first Read.
- Fewer "answered" words may make the model ignore the tool: intended for unanswered questions; §8 counts own
  model calls per arm.
- Deleting `nudge` loses the one measured small-corpus saving: it did not replicate on real repositories and the
  call rule plus tools-in-front replaces its delivery role.
- Louvain instead of Leiden changes the code path under the headline: gate in §4.8.
- The heuristic reason test can leave an explaining commit as a lead: the lead list names it; the model opens it.

## 8. Verification (cheap re-runs, no new study)

1. Unit and integration tests per task (TDD), the affected test files green, lint unchanged per file; the full
   suite once before merge in a venv without graspologic-native. Verdict audit (`verinoda benchmark verdict-audit
   --split all`) before and after: baseline at HEAD wrong_met 1/39 (`forge-maxheat-declared`), above_ceiling 0,
   controls kept 15/22; equal or better after.
2. The eight-set no-model benchmark (`python -m verinoda.benchmark run --repeat 1` per set), fact by fact against
   compare-2026-10-02/after-fix (query 284, analyze 285 of 319): once now for the commits already on the branch
   (six why-questions sit in the sets), once after D186; a lost fact is listed by id. ContextBench's analyze arm on
   the 40-instance sample only if `render_text` changes (it does not, by the §4.1 invariant).
3. The D185 harness re-run on the tasks the design names, as a new dated results folder with its own config and
   the call rule in place of the GUIDE: fastapi why-1 (546dc8b in the answer, no absence assertion), fzf why-1,
   guzzle trap-1 (no "first appears in b58db450"), gin trap-1 (the general rule of §4.3 names 15216a0 as a lead),
   axios when-1 (the one when task the term rule can fix), bat when-1 (the one a loose rule would break; must stay
   as today); 3 repeats, Verinoda arm; 18 sessions, under $2. Per session: the gold file's rank in `leads`, the
   gold commit in the answer claims, own model calls, Verinoda chars, and the mechanical citation check re-run with
   word boundaries and no question identifiers on these answers only (a new scorer file; the measured files
   untouched; the Verinoda arm's baseline is 95.8% confirmed, a change under about 3 points is not detectable).
4. The cost sample: 24 answerable D185 tasks x 1 repeat x 2 arms (48 sessions, about $3.60): the paired mean
   dollar difference with its bootstrap interval (expected half-width about ±$0.005), own model calls per arm,
   Verinoda chars per session, cache-write tokens per arm. Success for the design: the interval excludes +$0.015
   (the modelled 1.1-1.2x holds) and Verinoda output is at most 4,500 chars per session. Success for §4.1b: own
   model calls at most plain minus 1.5; otherwise the variant stays off. A 10-pair sample cannot see a $0.008
   difference and is not run.
5. SWE-bench is not re-run now (about $25 and 7 h of Docker per repeat); its cost model is the design input.
