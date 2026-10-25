# History rewrite (2026-10-25)

Before 0.5.0 was published, the 171 commits on `main` after `6d83521` (the last commit then on GitHub) were rewritten
once, in a copy, with git-filter-repo 2.47.0. None of them had been pushed. The commits up to `6d83521` and every file
under `benchmarks/results/` are as they were.

## What changed

- In every text file outside `benchmarks/results/` and in the commit messages, text that named a private project of the
  maintainer, or that only the maintainer's machine knows, was replaced:
  - the names of a private game mod and of a private chat bot, and the bot's path (now `MyGame/bot/herald.js`);
  - the bot's identifiers in the D190 case and its tests, renamed together so the case reads the same (its function is
    now `relay()`, its map `talk`, its silent marker `[SUSKUN]`), and four commit hashes of the bot's repository (now
    `bot-c1` to `bot-c4`);
  - identifiers of the private mod in D194's table, D195's text and two tests (`tr.example`, `TaskQueue`,
    `boss-health`, `Boss`; D194's six question labels are now `q1` to `q6`);
  - the home folder in local paths (now `C:\Users\me`).
- The author and committer address of 169 commits is now the GitHub noreply address. Names, dates, parents and the
  order of the commits are unchanged, and the 18 merges are still merges.
- At the tip 17 files differ: `docs/DESIGN.md`, `docs/UPGRADING.md`, nine files under `docs/drafts/`,
  `tests/test_question_scope.py`, `tests/test_cards.py`, `tests/test_review.py`, and comments in `verinoda/analysis.py`,
  `verinoda/question_plan.py` and `verinoda/verdict_gate.py`. No line of code changed outside comments and tests.
- 40 commit messages differ: 8 by the replacements above, the rest because the hashes they cite are now the new ones.

## How it was checked

- Commit by commit (all 171): the parents map to the rewritten parents, the names and dates are equal, and the tree
  differs only in the 17 files above.
- Every blob and every message the rewrite produced (1,299 blobs, 171 messages) was searched for each replaced name:
  none is left. Local paths of the maintainer's machine remain in measured data under `benchmarks/results/` (129 files),
  which is never edited (`AGENTS.md`).
- The three renamed test files, `tests/test_question_scope.py`, `tests/test_cards.py` and `tests/test_review.py`:
  149 passed on a tree byte-equal to the rewritten tip in every changed file.

## What it means for a reader

- Every hash of a commit after `6d83521` changed. Hashes cited in files outside `benchmarks/results/` and in commit
  messages name the new commits. Hashes cited inside `benchmarks/results/` are the old ones: look them up in the table
  below. For example the SWE-bench ceiling study pins Verinoda at `a7e0c65`, now `432ac1f`, and the product test run of
  2026-10-25 ran at `898f55c`, now `e21fba4`. The code a result was measured with differs from its rewritten commit only
  in the renamed comments and test names above.
- `verinoda/data/tq_calibration.json` is valid only for the engine files it was measured with. Three of them changed in
  their comments, so a rewritten commit that changed them shows no measured cells in `tq` until its own audit is re-run.
  The tip's table was measured again after the rewrite (`benchmarks/results/tq-audit-2026-10-25-rewrite/`).
- The release repository (github.com/Verinoda-Labs/verinoda) had three commits that touched only `docs/BACKLOG.md`.
  They are joined by a merge that keeps this tree (`git merge -s ours`), so both repositories receive the same `main`.

## Türkçe özet

0.5.0 yayınlanmadan önce, GitHub'a henüz gönderilmemiş 171 commit bir kez yeniden yazıldı. Özel bir projeye ve bota ait
adlar, yerel yollar ve yazar adresi nötr karşılıklarla değiştirildi. `benchmarks/results/` altındaki ölçüm verisi ve
`6d83521`'e kadarki commit'ler aynı kaldı. Ölçüm verisinde geçen eski hash'lerin yeni karşılıkları aşağıdaki tabloda.

## Old and new hashes

| date | old | new | subject |
|---|---|---|---|
| 2026-10-11 | `48d95e776e` | `511f0bdd34` | Benchmark findings and known gaps, in one document (Turkish) |
| 2026-10-11 | `b537d080a2` | `c13685ad54` | False-claims study: pre-registration (DESIGN_CLAIMS.md) |
| 2026-10-11 | `944b4c3549` | `6af0fb3f45` | False-claims study: the guide loads the tools first (amendment), and the implementation plan |
| 2026-10-11 | `83ac9a7437` | `5017a89b44` | False-claims study: task format, fixed order and validation (DESIGN_CLAIMS.md) |
| 2026-10-11 | `721279daef` | `23a08de31d` | False-claims study: leak check, re-derivation and the writer's and checker's prompts |
| 2026-10-11 | `5c4942e5f2` | `90bbb0d574` | False-claims study: the runner, both arms' prompts verbatim from the spec, full clones and shared copies |
| 2026-10-11 | `b2cdfb0155` | `c688d1c0bb` | False-claims study: the mechanical citation check and the neutralized answer text |
| 2026-10-11 | `0640978738` | `813480ee77` | False-claims study: the blind judge, its prompt verbatim, its parse and retry |
| 2026-10-11 | `35692795ba` | `e9066065ff` | False-claims study: the summary, the decision rule, the blinding check and the blind hand-check sample |
| 2026-10-11 | `42ccd1f6a0` | `8c7df4d647` | False-claims study: single-branch clones at the tag, the sha checked against the manifest, isolated headless writers |
| 2026-10-11 | `cf9de64dd2` | `b85f6d763b` | False-claims study: a gold_sources program that is not installed is recorded, not raised |
| 2026-10-11 | `3989027df9` | `e993893042` | False-claims study: traps are why or when only, at most three gold statements, grep not rg (amendment after the gin trial) |
| 2026-10-11 | `abba420ec0` | `972af63065` | False-claims study: the writer prompt's gold-size rule as the test reads it |
| 2026-10-11 | `ca51e17376` | `1e4bddd5a2` | False-claims study: the 40 tasks and their gold, written from git without Verinoda, checked, committed before the first session |
| 2026-10-11 | `2551561a8d` | `3ef3716cff` | False-claims study: the mechanical check reads identifiers out of backticked spans, the question's own names and a commit's diff |
| 2026-10-11 | `610da5b9b2` | `8f39882aad` | False-claims study: amendment after the pilot (N stays 40; the mechanical check) |
| 2026-10-11 | `123a520755` | `262373a573` | False-claims study: a bare file name in a citation resolves to the tracked files of that name; a host and port is no citation |
| 2026-10-11 | `8360da23cf` | `67c24df475` | False-claims study: the judge runs four sessions at a time |
| 2026-10-11 | `8c7b66c888` | `ddd6b460b8` | False-claims study: a partial path in a citation resolves by suffix like a bare name |
| 2026-10-11 | `071f9063d0` | `9065b2f1de` | False-claims study, 40 tasks x 2 arms x 3 repeats: the result (D185) |
| 2026-10-11 | `661cc2ae1d` | `67d9840d1c` | False-claims study, after the review: opaque copy names, reclassification by the asserting claim's own citations, the sheet with the whole gold |
| 2026-10-12 | `acb13f2441` | `9e2071ea77` | False-claims study, after the whole-branch review: the task id in the prompt, the traps rerun, the check as an upper bound |
| 2026-10-12 | `feae5847f3` | `0f9a870f7d` | Two external reports on coding agents, under docs/raporlar |
| 2026-10-12 | `b1da5ef0d2` | `9e510e36dc` | MCP response cap: a commit list keeps both ends and names the commits it drops |
| 2026-10-12 | `6036da0996` | `8fbc92b564` | analyze: a why-question's status is its verdict, and a commit answers it only when its message states a reason about it |
| 2026-10-12 | `00c89b7cc1` | `52e59e605d` | analyze: a claim the gate set aside is not listed as an answer, and the dated-document note needs a document |
| 2026-10-12 | `c5829bd7d1` | `b220a498d1` | analyze: Verinoda's own files are not a change for the index, and nothing changed means no refresh |
| 2026-10-12 | `36b8e43d65` | `8b2475ef78` | Verinoda Lean: the redesign spec (D186 draft) for equal accuracy at lower cost |
| 2026-10-12 | `c4473430f4` | `8c75d1b6a5` | verinoda-live: the server's core tools are listed in front of the model, not behind ToolSearch |
| 2026-10-12 | `ca1f8d3e7c` | `1f290c0224` | analyze: a when-question is answered by the commits about it, whether or not they state a reason |
| 2026-10-12 | `c678d46109` | `2b3f6c208c` | Verinoda Lean spec, revised after three independent critiques |
| 2026-10-12 | `4832c0fa6a` | `3f9527e3aa` | Verinoda Lean: the implementation plan (eight tasks, three waves) |
| 2026-10-12 | `fd1abd1cf4` | `276343d88f` | results: the eight public sets on the redesign branch at 2b3f6c2 - no fact lost, no fact gained |
| 2026-10-12 | `0a6cf78189` | `f6a0dd8623` | claims harness: a guide text from the config, task/repeat/arm flags, and a strict citation check for the D186 re-runs |
| 2026-10-12 | `29d6dec260` | `c0b1545758` | claims_mech_strict: the first run's id-named copies still score |
| 2026-10-12 | `0022ee161c` | `cfe7d02df5` | claims harness: an empty guide text means no guide paragraph (the mod's own prompt section speaks) |
| 2026-10-12 | `9378fd71fa` | `dd37d38aa4` | analyze over MCP: a verdict, the answer claims whole, eight leads and six context lines, under 2,500 chars; show="lead" adds the first lead's lines |
| 2026-10-12 | `b230c70efb` | `b571e93fdc` | analyze over MCP: an answer's file is a lead whatever its path - first, and never dropped by the cap of eight |
| 2026-10-12 | `f5f6f72dfa` | `af53bbc69b` | Merge Task 2: analyze over MCP returns leads (worktree-wf_77d39ded-a45-2) |
| 2026-10-12 | `d04e60a671` | `16baa0aaca` | cli: graph-state reports the index lock and the files behind, so the mod needs no python |
| 2026-10-12 | `2bcde624a8` | `e8fdfe766b` | verinoda-live: tools in front, the call rule and freshness; search, nudge, assist, guard and the warm-up go; nothing runs from the repository |
| 2026-10-12 | `d2f3e38600` | `d5ccced271` | README: the graph-state command's row in the Commands table |
| 2026-10-12 | `316a12fc08` | `673a82e0f1` | verinoda-live: without Verinoda on PATH outside the project nothing runs (the bare-name fallback goes) |
| 2026-10-12 | `5f720b0662` | `b12ee085d5` | Merge Task 1: the mod keeps tools-in-front, the call rule and freshness; verinoda graph-state (worktree-wf_77d39ded-a45-1) |
| 2026-10-12 | `c9061dd008` | `51599c3132` | project_index: the upstream Graphify CLI surface and its skills leave the package |
| 2026-10-12 | `fa7a709139` | `645ae77713` | project_index: the LLM, PR and media layer leaves the package |
| 2026-10-12 | `d66096baaa` | `4e5cf98ad1` | incremental: the vendored-builder pin follows the D186 edits of build.py and export.py |
| 2026-10-12 | `f0753cd2ea` | `cba8467a78` | graspologic-native becomes the leiden extra; tiktoken and anthropic become the benchmark extra |
| 2026-10-12 | `87785fc460` | `942d46eb86` | UPSTREAM.md lists the sixteenth trimmed test file; the port script's test rule knows the removed re-exports |
| 2026-10-12 | `f4fb8670ca` | `bf0a1f5232` | port script: the test rule sees the names the kept modules lost, so three files it missed stay deleted on a re-sync |
| 2026-10-12 | `7b161cda1b` | `92917341e3` | Merge Task 6: the upstream Graphify CLI surface, the LLM layer and the scipy dependency leave the package (worktree-wf_77d39ded-a45-4) |
| 2026-10-12 | `9c8d54b39d` | `1bb23d90ac` | gitexec: one place runs git, with the safety flags, a time-out result and a refusal on a risky untrusted config |
| 2026-10-12 | `1034906965` | `ca7a78f65f` | paths: contained_path at the sources; evidence roots allowlisted; the daemon state leaves the repository; MCP decision records are agent_asserted; reference fetches pin protocols |
| 2026-10-12 | `cbcfcf1684` | `60a5fc31c0` | paths: the JSON-only file list and the search index's stored names go through the containment too; a refused status says so in git_info |
| 2026-10-12 | `2235ee7ef6` | `6b9c878a53` | Merge Task 5: one git funnel, path containment, the daemon state, MCP decision records, fetch flags (worktree-wf_77d39ded-a45-3) |
| 2026-10-12 | `583e673be7` | `6069a3dc0c` | After the wave-1 reviews: a share hidden in a file URL is refused, an evidence root on a share is refused before it is resolved, and ", so" states a reason |
| 2026-10-12 | `7fc52be0b7` | `b66d7b76e0` | After the wave-1 reviews, the minors: lead lines read through contained_path, graph-state looks without writing, a graphless index folder is never "fresh" |
| 2026-10-13 | `b05d29ed52` | `c1aea1c4e7` | one status rule for the model: in the server instructions, the gateway description and a 60-line skill; change_review without its bookkeeping |
| 2026-10-13 | `4b76bfab2a` | `5efccb9d93` | Merge Task 4: one status rule in the text; change_review trimmed (worktree-wf_19225926-c2b-2) |
| 2026-10-13 | `3f4ad693e5` | `c1669aeaa0` | history: one flat list of commits, the created-file and moved-file classes handled, path-free oldest appearance, partial results on time-out, no server lock |
| 2026-10-13 | `93f19961b3` | `45af01321b` | history: a path-bound `appeared` says "under <path>" and the proven path-free commit is `first_appearance`, met first in the MCP response |
| 2026-10-13 | `a7df657954` | `5acd73ab47` | history: the path-free oldest commit is "older" when the graph says so, the dates only for separate lines of history |
| 2026-10-13 | `f34a223366` | `cfeb10e10f` | Merge Task 3: history as one flat list, correct where git is blind, honest on time-outs (worktree-wf_19225926-c2b-1) |
| 2026-10-13 | `68b21337cc` | `27ae3cf939` | results: the eight public sets after D186 waves 1 and 2 - no fact lost, no fact gained |
| 2026-10-13 | `8849ced971` | `f653179d40` | results: verdict audit before D186 and after each wave - grades unchanged, answers shorter in 12 rows |
| 2026-10-13 | `12aaba303e` | `ca9f575537` | results: verdict audit README says the measured analyze seconds instead of an unmeasured minute |
| 2026-10-13 | `380e6a041a` | `b66a373926` | The call rule names the first tool call, and the engine's deferred-tools reminder no longer contradicts the pins |
| 2026-10-13 | `320c0b0ae3` | `f73613a746` | Merge the call-rule fix: the first tool call named, the deferred-tools reminder corrected (callrule-d186) |
| 2026-10-13 | `02aaadf95b` | `22d0115cdd` | docs: D186 Verinoda Lean; UPGRADING, OZELLIKLER, ARCHITECTURE, BACKLOG, BULGULARI |
| 2026-10-13 | `63e0a61727` | `83a2b1652a` | agent rules and the mod comment follow D186: the rules template carries the one status rule |
| 2026-10-13 | `22150efdeb` | `4830dd92c6` | docs: D186 states a target, not a result; the modelled figures are sourced; the 19/22 cause is not asserted |
| 2026-10-13 | `7869d53c95` | `91221d44b4` | Merge Task 7: the D186 documentation (worktree-wf_1135bc68-ca7-1) |
| 2026-10-13 | `72c5e05c77` | `6baa279df5` | docs and the rules template follow the call-rule fix: what the re-run measured, the new rule, the corrected reminder |
| 2026-10-13 | `575b2a50ad` | `85b85c7a7d` | Final review fix pass: a shipped core.worktree no longer opens the user's folder, history paths are refused lexically, and seven more |
| 2026-10-13 | `3c3a47fd61` | `7924b38814` | results: verdict audit after the final review's fix pass (85b85c7) - grades and answers unchanged, one leads unknown gained |
| 2026-10-13 | `32c5ae3af5` | `a86529ed14` | results: the eight public sets after the final review's fix pass (85b85c7) - no fact lost, no fact gained |
| 2026-10-13 | `09a762a932` | `60a7bb0385` | results: the D186 re-run at 85b85c7 - six tasks x 3 and the 24-pair cost sample, with the zero-call run and the call-rate probes as appendices |
| 2026-10-13 | `65a61c1403` | `1e938c1813` | docs: D186's measured re-run in DESIGN 158.3, BULGULARI 5.2-5.4 and OZELLIKLER 158; two backlog rows from it |
| 2026-10-13 | `70af272089` | `72c95730e5` | docs: the measured call rate (37 of 39) beside the probe figure; the re-run README names D185's strict citation figures |
| 2026-10-13 | `fa9d556edb` | `06ed85472b` | Handover after D186: what is left as backlog rows, how the work was done and the order to continue, the probe and comparison scripts |
| 2026-10-22 | `0738339c47` | `1037c9774c` | CLI start-up: the version, the claim engine, the question-plan module and urllib.request are loaded when used |
| 2026-10-22 | `9ddbbdabb6` | `02c6836928` | Delete twelve functions nothing calls |
| 2026-10-22 | `140444f0a3` | `4ef167719a` | analyze rebuilds a graph an older extraction built, as `verinoda update` does, and then reads the new graph |
| 2026-10-22 | `b9e8109377` | `913a7cf1e8` | grep-ast and the graph query language time their bounds with perf_counter: on Windows a bound never passed |
| 2026-10-22 | `f73d72752e` | `c7c660d193` | check keeps the words of the project's files in the user cache: a check after an edit no longer reads every file |
| 2026-10-22 | `dc01f6545a` | `01766503f5` | One analysis resolves each path once: contained_path answers from a memo that lives for one call |
| 2026-10-22 | `d5669de442` | `8c0554e3b9` | `datapack <kind>` without a name says the name is needed instead of looking up None |
| 2026-10-22 | `ecbefb3136` | `ccdb5686c5` | check of a large file: 174 s -> 56 s, the same answers (two walks per site made it quadratic) |
| 2026-10-22 | `867fd3260a` | `949af6510c` | The kept project words leave no temporary file behind; the start-up tests count only what verinoda loads |
| 2026-10-22 | `76ead82559` | `85c625c159` | tq-audit rerun after the cleanup: the measured cells show again |
| 2026-10-22 | `73fcb29102` | `de0df7ec5d` | consolidate keeps the later of two verifications made in the same second |
| 2026-10-22 | `0fa7d20809` | `ac98b52905` | Databases opened by several processes at once: no "database is locked", no migration run twice |
| 2026-10-22 | `d9e8402ba5` | `10fd971ad1` | tq-audit rerun after the concurrency and consolidate fixes |
| 2026-10-22 | `767e99f1f9` | `290d9c68d0` | An analysis looks at its paths again after the project's code ran; a newer schema found under the lock is said |
| 2026-10-22 | `921465f831` | `5119046054` | tq-audit rerun after 290d9c6 (store.py, paths.py and experiments.py are in tq's engine hash) |
| 2026-10-22 | `9b454d1668` | `94aeca15f1` | The fswatch handle test checks the handle is open on the watched folder, not that its number is valid |
| 2026-10-22 | `4077fb1816` | `b321fb574d` | Merge the 2026-10-22 cleanup (cleanup-2026-10-22): faster checks and start-up, defects fixed, no test failing |
| 2026-10-22 | `a1a043935c` | `0d753404ae` | docs: D187, the 2026-10-22 cleanup, in DESIGN 159, UPGRADING, BACKLOG and AGENTS.md's test baseline |
| 2026-10-22 | `318fa0b3b6` | `03b833c9c6` | Merge the D187 documentation (cleanup-2026-10-22): DESIGN 159, UPGRADING, BACKLOG 23.3/23.5, AGENTS.md's test baseline |
| 2026-10-22 | `2eb26bd143` | `f93a762db3` | Handover after D187: where the session left off, the installs it made, the next steps and its helper scripts |
| 2026-10-22 | `4bf380732e` | `ee1670cb68` | Merge the D187 handover (cleanup-2026-10-22): docs/drafts/2026-10-22-d187-devam.md and its helper scripts |
| 2026-10-23 | `19751be442` | `e1b0bf45f7` | D188: what a session carries - no tools where Verinoda cannot serve, index_update's short view, shorter fixed text |
| 2026-10-23 | `1ee71ad8dd` | `96b8f288b7` | docs: D188, what a session carries, in DESIGN 160, UPGRADING, BACKLOG 5.4-5.6 and AGENTS.md's range |
| 2026-10-23 | `c7ae87d650` | `b84c71e587` | D188 review: no update builds a first index of a home folder; a git work tree is one project; the view's notes cut |
| 2026-10-23 | `8734b859f4` | `44e514ee2c` | docs: D188's refusals said per path in UPGRADING; the whole suite's result in DESIGN 160 and AGENTS.md |
| 2026-10-23 | `9266c0e9ec` | `a75cc1e862` | Merge D188 (context-lean-2026-10-23): what a session carries - fewer tokens in every request, no home-folder scan |
| 2026-10-23 | `baf0391d9b` | `31a9bea46b` | D189: file cards for the compaction - Verinoda's one line per file the conversation read or edited |
| 2026-10-23 | `a0d2807203` | `0a7ca3180f` | docs: D189, long chats and file cards, in DESIGN 161, UPGRADING, BACKLOG 5.7 and AGENTS.md's range |
| 2026-10-23 | `27f35c305f` | `bc17a93016` | D189 review: cards in the folder the session was opened in when the allowed project is elsewhere or there is none |
| 2026-10-23 | `1dd16aff36` | `8b96e157cb` | docs: the whole suite at D189 (5405 passed, 0 failed) in DESIGN 161 and AGENTS.md's test baseline |
| 2026-10-23 | `a059c9ecf7` | `fd6b4cbe7d` | Merge D189 (compact-cards-2026-10-23): long chats - file cards in the compaction's summary |
| 2026-10-23 | `2ad768feb3` | `f0dfba6bbc` | D189: a card skips only a licence header, not a purpose that mentions one |
| 2026-10-23 | `2129e7ca2f` | `4ea6c4c547` | D190: the file a question names scopes its plain words; a subject found by one word of several is not met; a why says where its line came from |
| 2026-10-23 | `88bd302c5e` | `7731aef193` | tq-audit rerun after 4ea6c4c (question_plan, verdict_gate, history and lexicon are in tq's engine hash) |
| 2026-10-23 | `718c7d2bc7` | `59521252f7` | D190 review: the named file is where plain words are looked for first, not a fence; a line's commit is never a stated reason |
| 2026-10-23 | `c7bbe368ed` | `07cdcce43e` | tq-audit rerun after the review round (question_plan, verdict_gate and history changed again) |
| 2026-10-23 | `902bfa7a1e` | `2ec8667504` | docs: D190, a real task's question, in DESIGN 162, UPGRADING, AGENTS.md and docs/drafts/2026-10-23-d190 |
| 2026-10-23 | `e54ce8e571` | `50dd6ccb9b` | D190 second review: in-file seeds only for subject questions; "introduced" keeps the newest commits; the cap weighs the whole answer |
| 2026-10-23 | `634d0eda1c` | `6a9b60ba4c` | tq-audit rerun after the second review round (question_plan, verdict_gate and history changed again) |
| 2026-10-23 | `51844b9006` | `29378a8ec1` | docs: D190's second review in DESIGN 162, UPGRADING and AGENTS.md |
| 2026-10-23 | `a7e0c65f35` | `432ac1fb74` | Merge D190 (real-task-fixes-2026-10-23): a real task's question - the file it names, a subject found by one word, the line a why asks about |
| 2026-10-23 | `f8e19d343d` | `b603c800c4` | D191: the question rule - a user-scope Claude Code install puts it in ~/.claude/CLAUDE.md |
| 2026-10-24 | `52c410bae2` | `bc9b47d530` | D191 review: the question rule never stops an install, never overwrites the person's text, and holds with nobody to answer |
| 2026-10-24 | `ca9d9f2d02` | `7aec72c26c` | D191 last check: the question rule's scripted-run bullet holds only at a decision point |
| 2026-10-24 | `06734743bc` | `9c7db654c0` | Merge D191 (claude-md-question-rule): the question rule - a user-scope Claude Code install puts it in ~/.claude/CLAUDE.md |
| 2026-10-23 | `4fc2cb6b99` | `771ae768a7` | SWE-bench ceiling study: pre-registration before any change to the agents' set-up |
| 2026-10-24 | `c458d1eb27` | `16871a28b5` | SWE-bench ceiling study: amend C0 and C1 before any run |
| 2026-10-24 | `4c9feed5f4` | `74eb53aea2` | SWE-bench ceiling study: local evaluator, history copies, test environment, reset |
| 2026-10-24 | `9bff53b3da` | `122457133b` | SWE-bench ceiling: amendment 2, fresh copies per repeat, C1 guide, pytest version file, regrade, selector |
| 2026-10-24 | `276f5f68f1` | `7417bb2045` | SWE-bench ceiling: the C1 environment before any C1 session (compiled builds, dependencies, session venvs) |
| 2026-10-24 | `d10200584c` | `7479f1863d` | SWE-bench ceiling: shared environments through a junction, pytest's Windows deps |
| 2026-10-24 | `0c1e24c101` | `ec216337f9` | SWE-bench ceiling: the leak scan also flags the other arm's copy and cd .. |
| 2026-10-24 | `7abcf9bcf4` | `d341744541` | SWE-bench ceiling: the image's pip for scikit-learn, msbuild for matplotlib's freetype |
| 2026-10-24 | `aff890bbce` | `fea27d1394` | SWE-bench ceiling: headless matplotlib, no editable install left by a build, shared env watched |
| 2026-10-24 | `0b51e2dabf` | `e46e05164b` | SWE-bench ceiling: C1 gives LF back to files a session rewrote with CRLF |
| 2026-10-24 | `4c2b62097d` | `0db7d8822f` | SWE-bench ceiling: matplotlib's mpl_toolkits namespace as the image's install gives it; copies retry a failed setup |
| 2026-10-24 | `5dc688ed35` | `15662dd450` | SWE-bench ceiling: amendment 3 (environment, evaluator agreement, C1 harness and order) |
| 2026-10-24 | `1cfbd29b00` | `f66a3a08e7` | SWE-bench ceiling: swebench_reuse, a run's copies again for another attempt |
| 2026-10-24 | `d610991c8e` | `ba144276c7` | swebench_reuse: snapshot only copies whose Verinoda setup finished (builds.json) |
| 2026-10-24 | `3696b46b5d` | `17395c0ae7` | code_check: the activated environment (VIRTUAL_ENV) when the project holds none (D192) |
| 2026-10-24 | `40cf43d3fd` | `1bac406c7c` | D192: the activated environment is read again after an install; DESIGN 164 and UPGRADING |
| 2026-10-24 | `f631e5db24` | `231d65477a` | BACKLOG 24.1: the MCP server's own import path (from D192's not-done) |
| 2026-10-24 | `7c8dd3c617` | `99a346614e` | BACKLOG 24.2 and 24.3: what the ceiling study's C1 transcripts show of analyze |
| 2026-10-24 | `76cc7741c4` | `87dc62c5cd` | Merge swebench-c2-2026-10-24 (D192 and the SWE-bench ceiling harness it was cut with) before D193 |
| 2026-10-24 | `b07fcc0114` | `501a7eb3c0` | D193: a scripted session starts no re-index, so its end waits on nothing of the mod's |
| 2026-10-25 | `c6eebf6237` | `b1722732c7` | D194: analyze reads the working tree once per call |
| 2026-10-25 | `2f3d792ba1` | `9cbf7e83e6` | tq-audit after the D192 merge (codecheck.py and codecheck_env.py are in tq's engine closure) |
| 2026-10-25 | `da2d4d1e54` | `5781de517e` | BACKLOG 25: what the own-repository study and D193-D194 left |
| 2026-10-25 | `e7896290d3` | `88f9f22726` | D195: two defects in `verinoda review` that the Part B replay showed; no Stop hook |
| 2026-10-25 | `1a1acb5ddc` | `152d2fbb2b` | D196: an ignored .mcp.json that setup wrote no longer rebuilds the graph |
| 2026-10-25 | `898f55c3a4` | `e21fba4e11` | Merge D192-D196 (product-2026-10-24): the product fixes the ceiling and own-repository studies led to |
| 2026-10-24 | `566d6a718f` | `d83f9d45c4` | SWE-bench ceiling: amendment 4 before the runs it adds (the model, k attempts, labelled diagnostics) |
| 2026-10-24 | `1d0c0afc8c` | `da681db24e` | swebench_reuse: a reset also empties Claude Code's memory folder for the copy's path |
| 2026-10-24 | `cd9b8c3d46` | `8c304472c2` | SWE-bench ceiling: swebench_run_diag, the labelled diagnostics of amendment 4 |
| 2026-10-24 | `3d9105f0d6` | `5c7ac53d37` | swebench_leakscan: a session's own background command output is not a path outside its copy |
| 2026-10-24 | `91328b711d` | `168e024372` | SWE-bench ceiling: amendment 5, before any session of C4, C3, the diagnostics or the held-out run |
| 2026-10-24 | `46a8377f9a` | `93d51526a9` | SWE-bench ceiling, amendment 6: a session whose Bash lost its PATH is run again |
| 2026-10-24 | `9df89b25fe` | `39511c7311` | Amendment 6's heading: the time it was committed (06:45), not the estimate written before it |
| 2026-10-24 | `577ef9250f` | `bd8655f210` | Leak scan: a package download is network use; a session's own saved tool results are its own output |
| 2026-10-24 | `903aa492d9` | `ccb1f63c0e` | SWE-bench ceiling, amendment 7: recall of the upstream fix, measured; a closed-book probe |
| 2026-10-24 | `481b8a26ca` | `af1821bbfd` | Amendment 7's heading: the time it was committed (08:19), not the estimate written before it |
| 2026-10-24 | `a02e128e60` | `d5fbc25324` | SWE-bench ceiling, amendment 8: how C4's rule counts a row without a grade, fixed before any Fable grade |
| 2026-10-24 | `fd0360be63` | `a2dafa1631` | Ceiling study amendment 9: Opus for C3 on, usage-limit rows are not sessions |
| 2026-10-24 | `6329e035e0` | `a42611b980` | Ceiling study amendment 9: its times as recorded (13:16 commit, 13:14 usage reading) |
| 2026-10-24 | `cb6b5174e8` | `596ae2936f` | Ceiling study amendment 10: the diagnostics start beside C3 |
| 2026-10-24 | `3ba7fcd793` | `c0a0403a7d` | Ceiling study amendment 10: its time and C3's count as recorded (15:38, 145 sessions) |
| 2026-10-24 | `0e231123f6` | `f78b57c543` | Ceiling study amendment 11: the held-out run is cancelled; C3 runs to its end |
| 2026-10-25 | `8a50faadd8` | `0adbd73600` | Ceiling study results: SWE-bench Lite dev, 100 instances (2026-10-24/25) |
| 2026-10-25 | `94e595f650` | `12b2633e1b` | Ceiling results README: sympy-13146's regraded row and the OpenAI sentence (prose corrections) |
| 2026-10-25 | `a49a932eef` | `ac0725335c` | Merge the SWE-bench ceiling study (swebench-ceiling-2026-10-23): amendments 4-11 and its results |
| 2026-10-25 | `6700457568` | `65f6a201ed` | Release 0.5.0 (beta): the README says what was measured, links name Verinoda-Labs/verinoda |
