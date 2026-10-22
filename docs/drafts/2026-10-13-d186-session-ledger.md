# D186 session ledger (2026-10-12 to 2026-10-13), as kept during the session

The working notes of the session that built the Verinoda Lean redesign, copied as they were: decisions
(`Ruling: what - why - cost if wrong`; the format was not kept in every entry), measurements, and what was pending
at each step. Read it as a record, not as the current state: the closing `## Pending` list is the one written at
the start of the session (all of it was done); the current to-dos are `docs/BACKLOG.md` sections 22 and 23.
Session-local names (the scratchpad, `tool-results/`, `.claude/worktrees/`, workflow and agent ids, the work
folder `C:/vbench-claims-rerun`) do not exist in the repository; the results they name are under
`benchmarks/results/` with the dates given, except `verdict-audit-2026-10-12/`, a planned name: the folder is
`verdict-audit-2026-10-13/`. `docs/CALISMA-NOTLARI.md` is the digest; `docs/DESIGN.md` 158 is the record.

---

# Redesign ledger — branch symbiosis-redesign-2026-10-12 (cut from benchmark-bulgulari-2026-10-11 @ feae584)

Goal (user, 2026-10-12): beat graphify AND tool-less Claude on accuracy AND cost; may delete files / change
architecture; cybersecurity care; decisions delegated to me; no more measurement studies (only cheap re-runs).

Honest target (advisor, agreed): graphify is already beaten on every measurable axis (no-model: 284/319 vs 67/319
facts; agent loops: both zero). Plain Claude is at ceiling on accuracy for measured task types. Achievable target:
EQUAL accuracy, STRICTLY LOWER cost per session, plus the one measured win (history across renames/paths).

## Measured cost anatomy (D185 transcripts, 240 sessions, mean per session)
- API calls 3.70 -> 3.98; cache_creation 9,411 -> 17,542 tokens (+8,130); cache_read 81,692 -> 99,082 (+17,390);
  output 1,229 -> 1,378; reported cost 0.058 -> 0.094 USD.
- Modelled at list prices the gap is cache WRITES (+0.030 of +0.036): bytes Verinoda returns, written once, re-read
  each later turn. Verinoda tool output median 16,073 chars/session (~4k tokens); plain arm's own tool output
  3,838 chars; Verinoda arm's own output 1,110 chars.
- First API call: cache_creation 6,848 vs 8,157 (+1,309 tokens fixed: GUIDE + mod/plugin injection + deferred names).
- ToolSearch payload not captured as tool_result text (schema injected elsewhere) — size unknown, reader 'cost' measures from code.
- Levers, in order: output bytes per call (16k chars -> target < 4k), fixed injection (+1.3k tokens), the extra
  ToolSearch turn, the duplicated commits+claims lists in history_search.

## Fixes shipped
- F1 (commit 1): cap_response keeps both ends of a commit list and names dropped commits "sha date" (tests
  test_cap_response_keeps_both_ends_of_a_commit_list_and_names_the_dropped RED->GREEN; real fastapi copy: 546dc8b kept).

- F2 (commit 2): why-handler reads WHY_COMMITS=20, claims <=3 commits that state a reason AND share a topic word
  (stem equality; subject's own name excluded; "for security" added to _REASON); others are leads in an unknown
  ("sha date subject", next_step: git show / history_search); gate uses gate["why_topic"] and carries
  gate["why_leads"]; overall_status() -> answered/partly_answered/unanswered (DONE_STATUSES); CLI exit 0 for all.
  Tests: test_a_commit_states_the_reason_asked_about_only_with_the_questions_words,
  test_a_why_reads_past_the_three_newest_commits_and_ties_the_reason_to_the_question,
  test_a_why_with_no_stated_reason_is_unanswered_and_lists_the_commits_as_leads, test_overall_status_follows_the_sub_questions.
  Real fastapi copy: analyze -> answered, met, single claim 546dc8b, 10.5k chars.
  Pitfalls found: word_in prefix match ("read" ~ "readthedocs"); gate subjects include all linked nodes (so the
  topic words come from the handler via the gate record, not recomputed).

## Open fixes
- F3: folded into F1/F2 (dropped names and leads are the pointer).
- Surface text: GUIDE/skill must name primary_source_verified, say Verinoda is a lead, say what to do on truncated.
- Docs: D186 section in docs/DESIGN.md, UPGRADING note, OZELLIKLER 3 lines — at the end of the redesign.

## Rulings
- R1: start the three measured fixes before the design is done (advisor): bounded, measured, hours; cost if wrong: rework if the design removes history_search's shape.
- R2: branch sits on the unmerged study branch; do not push without asking.

## Design
- Understand workflow wf_a56e79b2-9df done (10 readers; maps in tool-results/ba48rr13y.txt + scratchpad/readers_last3.txt).
- Spec written: docs/drafts/2026-10-12-verinoda-lean-design.md (D186). Critique workflow wf_ed056517-695 (3 critics) running.
- Commit 3 (00c89b7): weak claims not answers; dated-document note needs a document.
- SWE-bench cost decomposition (fitted prices $2/$4/$0.20/$10 per Mtok): +$0.0494/session = writes 68%, reads 26%,
  output 6%; parity needs: no ToolSearch turn, code_check as silent hook, analyze <= 2.5k chars, leads precise enough
  to displace >= 2 own calls.

- Commit 4 (c5829bd): own files / Verinoda-only .mcp.json not a change; no refresh when nothing changed (analyze
  on the fastapi copy 5.7 s -> ~1 s). Known gap (advisor): a removed own file still counts (marker check on a
  missing file) — D186 "not done".
- Commit 5 (36b8e43): spec draft committed; branch pushed to origin (user asked for GitHub uploads twice today).
- Offline re-rank check (scratchpad/rerank.py): §4.1 order -> gold rank1 31->60, top3 46->76, top8 71->86 of 100.
- tool.describe can target mcp__server__tool and set isDeferred:false and rewrite descriptions (d.ts 12119-12170).
- Advisor plan order: (a) mod tool.describe + HIGH .venv fix [verify with one claude -p session]; (b) analyze lean
  shape [hold until the accuracy critic says whether verinoda.benchmark goes through the lean view]; (c) history flat
  rows + §4.3; (d) change_review trim + text; (e) security helpers; (f) deletions in a parallel worktree; (g) docs.
  Assist deletion and the new tool.describe hook in the same commit (register.tsx:893 is the only existing hook).

- Mod prototype (uncommitted): tool.describe hook lists mcp__verinoda__{analyze,project_query,run_tool} in front
  (features.test.ts new test RED->GREEN, 125 pass, tsc clean, validate passed).
- Empirical check, fastapi why-1 copy, STANCE only (no GUIDE): with plugin (tools in front) the model called NO
  Verinoda tool (Grep, Read, Read, Bash), 5 turns, $0.123 (first call wrote the whole 24.6k system prompt to cache:
  cold cache, not a steady-state cost); without plugin: same tool path, $0.058. => tools-in-front is necessary but
  not sufficient; the design needs a short conditional call rule (prompt.compose, when the MCP server is connected):
  "for a why/when/affects/how question call mcp__verinoda__analyze once, then verify with your own git/grep; a
  question one grep answers needs no call".

- Session C (plugin + one-paragraph call rule appended to the prompt, r1 copy): tools analyze -> Grep -> Bash(git show
  546dc8b); 4 turns; $0.066; answer cites 546dc8b "for security", inference marked, no absence assertion. Writes
  7,278+4,889+337 = 12,504 (B: 9,687); reads 71.9k (B: 65.1k). Verinoda output 10,355 chars (not yet lean). n=1.
  Sessions A/B (no rule) both asserted "history gives no reason" after `git log -S` -> 8558cf0. Scratchpad sess{A,B,C}.json.

- Critique workflow wf_ed056517-695 done: cost "does_not_reach_target" (strictly cheaper unreachable by replacing
  search; modelled 1.1-1.2x), accuracy "with changes" (invariant: analyze dict + render_text unchanged; when-question
  regression found -> fixed ca1f8d3; history rules split; verdict audit baseline 15/22), safety "with changes"
  (detect.py/export.py top-level imports; tests_upstream 66 files; port tool; extras; gitexec funnel; contained_path
  lexical-first; mod cwd-first lookup; no -P).
- Commit 7 (ca1f8d3): when-questions claim topic commits else newest, no reason gate; shares_topic().
- Commit 8: spec revised (honest target: equal accuracy, cost inside plain's interval, history win; §4.1b experiment).
- Subagent launched: eight-set no-model benchmark on the branch vs compare-2026-10-02/after-fix (scratchpad/bench-branch/).

- Plan committed (4832c0f): docs/drafts/2026-10-12-verinoda-lean-plan.md — 8 tasks, 3 waves.
- Wave 1 workflow wf_77d39ded-a45 launched: tasks 1 (mod), 2 (analyze lean), 5 (security helpers), 6 (deletions),
  each implementer in a worktree -> fresh reviewer -> one fix pass. Merge plan: merge each task branch into
  symbiosis-redesign-2026-10-12 with --no-ff, resolve server.py (tasks 2/5) and cli.py (tasks 1/6) conflicts, run the
  affected tests after each merge; then wave 2 (tasks 3, 4) with the same script shape; then wave 3 (7 docs, 8 runs).
- Eight-set benchmark on the branch at c678d46: no fact lost/gained (284/319, 285/319); analyze tokens -9..-87 on 14 of
  86 questions. Stored as benchmarks/results/compare-2026-10-12-branch/ (commit fd1abd1, pushed). Task 8 repeats it
  after D186 using run_all.sh there.

- Task 8 harness prep done inline (0a6cf78 + fix): guide_text, --tasks/--repeats/--arms, claims_mech_strict.py.
  Strict baseline on D185 answers: plain 905/216/6 (0.803 confirmed), Verinoda 1047/254/20 (0.793); lenient 0.975/0.958.

- Wave 1 done (wf_77d39ded-a45): tasks 1, 2, 5, 6 merged with --no-ff (f5f6f72, 5f720b0, 7b161cd, 2235ee7), no
  conflicts; mod checks pass on the merged tree (84 tests, tsc, validate). Task 5's fix pass failed (usage limit):
  its two important findings fixed by me in 583e673 (file-URL share, evidence root on a share) plus the ", so" reason
  cue (test_history's why-question regression from 6036da0). Worktrees still exist under .claude/worktrees (clean up
  after wave 3). Task 6 review minors left: GENEL-BAKIS mentions `verinoda index`, BENCHMARKS.md `pip install anthropic`
  (Task 7). Task 1 minors: graph-state `state` not parsed by the mod (no_index), relative `cli` setting, freshness
  record=False, stale improve-pane comment. Task 2 minors: `_lead_lines` ad-hoc containment (route through
  contained_path now that Task 5 landed), coverage sentence on plan_json-only, over-budget note.
- Integration test run on the merged tree (31 files): 1,084 passed, 2 failed = the pre-existing SKILL length tests
  (Task 4 fixes), 1 skipped, 14:17.
- Wave 2 launched (tasks 3 strong model, 4 sonnet) with worktrees cut from the merged tip.

- Session D (merged tree, mod's own rule section, stance-only prompt, fastapi r3 copy): tools analyze -> Grep -> Bash ->
  Read; 3 API calls; Verinoda output 1,987 chars (was 10,355); answer cites 546dc8b "for security", inference marked;
  $0.124 with a cold prompt cache (24.9k tokens written at call 1); rule section present in the transcript.

- Minors fixed (commit after 583e673): _lead_lines via contained_path (junction test), graph-state record=False, mod
  no_index state. Deferred minors (final report): relative `cli` setting accepted as a path; improve-pane.tsx stale
  comment; GENEL-BAKIS `verinoda index` mentions and BENCHMARKS.md `pip install anthropic` (Task 7); `:` anywhere
  rejected by escapes_lexically (POSIX name with a colon never indexed; document); daemon tests need the worktree's
  package on the child's path; ARCHITECTURE locate_daemon row (Task 5 review minor - check whether fixed).

- Verdict audit after wave 1 (merged tree, 7fc52be): all 39 cases, wrong_met 1 (forge-maxheat-declared), above_ceiling 0,
  controls kept 15/22, the same seven lost controls as the HEAD baseline -> no regression. JSON:
  scratchpad/verdict-after-wave1.json (Task 8 copies it into benchmarks/results/verdict-audit-2026-10-12/).

- Wave 2 done (wf_19225926-c2b): Task 3 (3 commits, fix pass done: first_appearance labelled; a7df657 same-second
  commits) and Task 4 (1 commit, approved; trailer amended to Fable before merge) merged with --no-ff (4b76bfa,
  f34a223), no conflicts. Task 3 deviations: history_search budget 2,989 chars for 14 real rows (plan's 2,000 was
  unrealistic: a row is ~100 chars) -> Task 7 restates the budget as measured; when-lead fires only for "when was X
  added/introduced/created". Minors deferred: _run(lock=False) symbol-mode _graph() outside the lock; _pathspec
  absolute path message; quoted cut independent of rows past the cap; agent_RULES.md still old sentence; run_tool
  catalog hides argument values (Task 8 counts invalid_argument errors).
- Integration tests (20 files) + verdict audit after wave 2: background (merged2-tests.log, verdict-after-wave2.json).

- Verdict audit after wave 2: identical to baseline (1/39, 0, 15/22, same seven lost). JSON scratchpad/verdict-after-wave2.json.
- Wave 3a launched: Task 7 docs on sonnet (write -> review -> fix), with the measured-facts list in the prompt and a
  TASK8 placeholder for the re-run numbers. Task 8 runs start after the wave-2 integration tests finish.

- Wave-2 integration tests: 823 passed, 1 skipped, exit 0 (20 files, 7:35). Eight sets after D186 (f34a223): no
  fact lost/gained; stored benchmarks/results/compare-2026-10-13-after-d186/ (68b2133). Before-D186 verdict audit
  running in a detached worktree at feae584 (.claude/worktrees/before-d186) -> scratchpad/verdict-before-d186.json.
- Task 8 driver (sonnet) launched: D185 re-run 6 tasks x 3 (Verinoda arm) + 24-pair cost sample, judge, strict check,
  results folder benchmarks/results/claims-rerun-2026-10-13/ (uncommitted; I commit after checking).

- Before-D186 audit (feae584) vs after-wave2: summary identical, all 39 rows same verdict/wrong_met/above_ceiling/
  sub-question statuses; 12 rows' answer text shorter (5 why rows lost the "changed in <sha>" line -> now in the
  unknown; 7 locate/callers rows lost definition/text-match/call lines that did not answer). after-wave1 ==
  after-wave2 minus seconds. Folder benchmarks/results/verdict-audit-2026-10-13/ (README + 3 JSONs) committed.
  Docs workflow wf_1135bc68-ca7 still in its write stage (worktree wf_1135bc68-ca7-1, locked).

- FINDING (01:25): Task 8 runs done (63 rows: none 24, verinoda_guided 39, exit 0, $3.83) but verinoda_calls = 0 in
  all 39 Verinoda rows; first tool Grep in 38, Bash in 1; ToolSearch 0. Debug log (probe p1): the tool.describe pin
  WORKS (isDeferred true -> false for the 3 core tools before the first API request; "0/19 deferred tools included");
  my probe e1: the model lists analyze/project_query/run_tool in its callable list AND the engine's deferred_tools_delta
  reminder also names them (contradiction). The rule section is in the system prompt in 39/39. So the model has the tools
  and the rule and still greps: the D186 §4.6 "one-paragraph rule" rested on n=1 (Session D). register.tsx:33-37
  comment and the spec/plan claims must be corrected. Candidate causes: the rule's escape clause ("a question one grep
  answers needs no call"), the deferred-list contradiction, rule in system prompt vs D185's user-turn GUIDE+nudge (120/120).
  Experiment: mod copy B (imperative rule, no escape clause, "not behind ToolSearch") via scratchpad/probe_rule.py on
  fastapi why-1, fzf why-1, guzzle trap-1; C = user-turn nudge via prompt.submit context if B fails.
  Subagent paused; judge.jsonl (27 rows) + mechanical.jsonl (63) exist in the work folder; 39 Verinoda rows must be moved
  aside before any re-run; the 24 none rows stay. Final review workflow wf_71fc39cc-feb running (5 dims, fable).

- Call-rate probes (scratchpad/probe_rule.py, mod copies under scratchpad/mods, copies under C:/vbench-claims-rerun/probe):
  B (imperative rule, no escape clause, "not behind ToolSearch"): 3/6 analyze first (fastapi why, guzzle trap, gin trap
  yes; fzf why, bat when, axios when no: the when-questions go straight to `git log -S`, both right). C (original rule +
  prompt.submit context nudge): nudge text absent from all 3 transcripts -> prompt.submit does not fire for a `-p` prompt;
  C = baseline (1/3 by chance). Unused-mod overhead from the 24 zero-call pairs: +$0.0070/session (95% [0.002, 0.014]),
  input tokens 85.3k -> 93.7k. B2 = B + prompt.attachment rewrite dropping the 3 pinned names from the engine's
  deferred_tools_delta reminder (which says a direct call fails: false for them) -> running on 6 tasks. B3 ready = B2 +
  "your first tool call is analyze" wording + an analyze description rewrite (tool.describe).

- Probe results: B 3/6, B2 (reminder fix) 4/6, B3 (+ "first tool call" wording + analyze description) 5/6 (miss: axios
  when, answered right with git log -S). B2's reminder rewrite verified: the model's deferred list no longer names the
  three (probe e2). Fix implemented TDD in worktree .claude/worktrees/callrule (branch callrule-d186, commit 380e6a0):
  mod CALL_RULE (B3 text, ~633 chars) + prompt.attachment hook for deferred_tools_delta + comments/README/AGENTS facts;
  server STATUS_RULE last sentence "On a why, when, which-commit or what-does-it-affect question, call analyze first:
  Grep, Read and git come after it." (skills copied; core instructions 1,734, limit 1,700 -> 1,800); analyze description
  "Start here for ..." (menu 4,099 -> 4,178 < 4,200); spec §3/§4.6 corrected. Tests: mod 86/86, test_mcp 85, test_agents
  75, lint equal, tsc, validate. Ruling: merge after the review workflow's mod reviewer finishes (it reads HEAD files).
  Product-config probe (worktree mod + PYTHONPATH=worktree server) running on the 6 tasks.
  Cost note: probe costs are confounded by the cache (B3's 6 concurrent cold sessions $0.12-0.14 vs B2 $0.03-0.05).
- Product-config probe (worktree mod + worktree server, 380e6a0): 6/6 analyze first (both when-questions included);
  transcripts carry the new description and the new STATUS_RULE sentence. Cold-cache costs again ($0.12-0.14).

- Call-rule fix merged into the branch (320c0b0; pushed). Docs workflow wf_1135bc68-ca7 done (write, review
  "fix_then_approve", fix): three commits rebuilt with the Fable trailer (02aaadf, 63e0a61, 22150ef), merged 7869d53
  (conflict: mod AGENTS.md test count -> 86). Then 72c5e05: DESIGN 158 / BULGULARI 5.2 / OZELLIKLER 158 / UPGRADING tell
  the zero-call finding and the fix; agent_RULES.md carries the new STATUS_RULE sentence (test_more_agents pin green:
  134 passed + 59 passed). Pushed. Worktrees left: before-d186 only.
- Subagent split the work folder: results.jsonl = 24 none rows; superseded-zero-call/ holds the 39 Verinoda rows,
  judge.jsonl (27), mechanical.jsonl, logs, README, split-manifest; usage/ files being moved there too. Dry check: the
  two commands would run exactly the 39 Verinoda sessions. Copies reused (indexed at 68b2133). Waiting for GO.
- Review workflow wf_71fc39cc-feb: all 5 reviewers done (packaging 2, mcp 4, engine 5, mod 4, security 4 findings);
  skeptics running (4 verdicts so far, all Minor by effect). Then: re-grade, one fix pass (TDD), GO.
- Docs workflow notes to carry into the final report: escapes_lexically rejects every ':' (recorded as a known gap in
  DESIGN 158.4 + UPGRADING); stale facts left: root AGENTS.md ("six tests fail", D1..D174), OZELLIKLER intro "148 sections",
  ARCHITECTURE line 9 "D1-D40", BENCHMARKS.md no D186 section; TASK8 placeholder in DESIGN 158.3; BULGULARI 5.2/5.3 to get
  the re-run numbers.

- FIX PASS (uncommitted, tests green per file, TDD RED->GREEN each): (1) analysis why-unknown says the WHY_COMMITS
  window when capped (+ gate note marker why_more); (2) symbol_history scope "the file's renames followed, not lines
  moved in from another file" + `-c diff.renames=true` on the -L call (test with GIT_CONFIG diff.renames=false);
  (3) paths.work_tree_top: None when the repo config sets core.worktree (Critical, my probe confirmed);
  (4) history._pathspec refuses absolute/drive/UNC/`..` lexically (':' allowed under --literal-pathspecs), _one_file
  via contained_path; (5) gitexec.untrusted_config_risk reads config.worktree when extensions.worktreeConfig;
  (6) _stem: undouble bdgkmnprtv, e-strip at len>3, -ied/-ies -> y (moved/move, copied/copy, entries/entry);
  (7) a mention-only decision document no longer sets found (leads + path-free search stay); (8) index_reads: a
  modified .mcp.json unchanged only when its config_digest equals the recorded one; (9) history_search symbol mode
  resolves the name + notes spans under the lock, git read outside; _run(lock=False) no longer calls _note_spans;
  (10) SYMBIOSIS.md rows: nudge/guard rows replaced by the call rule + check rows, settings line, 86 tests, Turkish.
  Deferred minors to list: a sub-question judged met_with_inference on a claim the critique later lowers to
  weak_inference keeps its status (seen in the mention test); `cli` setting with .exe extension never found;
  scip_reader docstring names a deleted file; ruff I001 import order in server.py (pre-existing per lint equality);
  `more: true` text/compare modes carry no next call (Minor by effect); quoted cut; when-fallback marker (2010).
  Security verdicts: paths 475 Critical confirmed, history 172 Critical confirmed, history 540 Important confirmed (fixed:
  --relative before --end-of-options + sub-project test), gitexec 219 pending. core.worktree added as a refusal key.
  Eleven test files: 518 passed, 1 skipped. Committed as the fix pass (see git log) and pushed.

- Final review wf_71fc39cc-feb DONE (24 agents): 18 confirmed (4 security: 2 Critical + 2 Important; engine 4 Important
  + 1 Minor; mcp 2 Important + 2 Minor; packaging 2 Minor; mod 1 Important (SYMBIOSIS.md) + 2 Minor), 1 refuted
  (register.tsx:43 rule vs STATUS_RULE status sets: by design). All Critical/Important fixed in 575b2a5 (TDD) + SYMBIOSIS.md.
  Review Focus: items 1,3,4,5 pinned; item 2 "partly" (the analyze time-out test asserts status in DONE_STATUSES, no
  error; the leads-kept part is read, not pinned) -> deferred minor.
  Rulings on the "declined to judge" lists: security 1-2 closed by the fix (core.worktree refusal key; config.worktree
  read); security 3 read_context/grep_context: read_context's path is the file the agent already opened (for_file resolves
  then rejects outside paths; the resolve adds no exposure beyond the agent's own Read), grep_context takes no path ->
  stands, no change (cost if wrong: a resolve of a path the agent already touched). Engine: states_reason cue looseness
  -> heuristic, documented in 158.4, stands; the refresh early return never reaching an outdated extraction stamp ->
  deferred minor (verinoda update / index_update rebuild; check the UPGRADING "run update after upgrading" line);
  ANALYZE_KEEP lacks subquestions above the 12k cap -> unreachable (lead_view <= 2,500/4,500 by construction, test
  pins it), stands; overall_status counts met_with_inference answered on a claim the critique later lowers -> deferred
  minor. MCP: race frequency measured by the skeptic (0.2-0.3%) and fixed; -L renames on other git versions -> pinned
  diff.renames=true, stands; unlocked freshness.check -> now under the lock in symbol mode (text mode never calls it),
  closed; hub server -> same per-project lock, stands. Packaging: Louvain headline -> backlog row (stands);
  UPSTREAM.md 3813 vs 3811 collected -> deferred minor (docs count in this venv without tree-sitter-hcl);
  tests_upstream not re-run by the reviewer -> noted. Mod: relative PATH entries on POSIX -> deferred minor (fromPath
  stats relative to the engine's cwd, the run uses cwd=home: a mismatch, not a repository execution); two sessions one
  repo -> build lock waits, documented, stands; tool.describe in the real host -> verified by the debug-log probe,
  closed; graph-state maps 'atlas.db unreadable' to no_index -> deferred minor; a UNC `cli` setting refused silently
  -> deferred minor.
- Verdict audit after the fix pass (575b2a5): identical grades/answers to wave 2; orders-why-commit gains the leads
  unknown (intended). Stored as after-review-575b2a5.json + README line (uncommitted). Eight-set rerun on 575b2a5
  running into scratchpad/bench-after-review (first attempt failed on the OUT path, nothing ran).
- Subagent given GO at 575b2a5 (re-run 39 Verinoda sessions, judge all 63, strict, analysis, results folder).

- Re-run done (575b2a5): 37/39 analyze first; 24 pairs 1.10x (+$0.0057 [+0.0023, +0.0085]); fastapi/fzf gold cited 3/3;
  guzzle trap 3/3 false (b58db450; the model's own git log -S overrode the path-free lead); gin: judge 0, hand reading
  31323f6 as "first". Results folder committed 09a762a (+ probes/ and superseded-zero-call/ appendices); eight sets after
  the fix pass committed 32c5ae3 (no fact lost/gained); verdict audit after review 3c3a47f; docs filled (DESIGN 158.3,
  BULGULARI 5.2-5.4, OZELLIKLER 158, BACKLOG 22.8/22.9). before-d186 worktree removed. Branch pushed.

## Pending
- Understand workflow wf_a56e79b2-9df (10 readers) -> design panel workflow -> spec (docs/drafts/2026-10-12-...) -> plan -> implement -> security gate -> re-run 6+3 sessions + 10/arm cost sample.
