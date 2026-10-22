# Backlog: features competitors have that Verinoda lacks

Source: a survey of about 150 open-source and commercial tools (code graphs and MCP servers, context engines,
program analysis, review and test tools, agent memory and docs tools, Minecraft/JVM tooling), 2026-09-29.
112 features were found; 106 fit Verinoda and are listed here, in build order. The 6 that do not fit are at the end.

How this file is used:

- **An item is deleted when it ships.** The shipped work gets its own decision in `docs/DESIGN.md` (D72, D73, ...)
  and a note in `docs/UPGRADING.md`; the design section, not this file, is the record. Code comments cite the
  D-number, never a backlog id, because the id disappears with the row.
- `verinoda backlog 1.1` shows an item; `verinoda backlog` reads this file (sections `## N - Title`, rows
  `| N.M | **Title** | ... |`).
- **(opt-in)** marks an item that needs the network, an external tool or a heavy dependency: off by default,
  turned on explicitly, like `resolve --network on`.
- Rules every item keeps: output is claims with a status and `file:line` evidence; a heuristic result (a score, a
  coupling, an embedding hit) is `strong_inference` at most; the core MCP profile stays at five tools (new tools go
  behind `run_tool` or the full profile); nothing leaves the machine unless the user turned it on.
- The "Seen in" column names tools that have the feature, for reference; it is not a claim about their quality.
  An item that did not come from the survey says so there ("none: our own idea") and is not one of the 106.

## 1 - Incremental index core

Everything that runs on every edit (hooks, `ui --watch`, the test map) waits on this block.

Status of 1.1 (2026-09-30): stage A (the same outputs, less work) is implemented on six `stagea-*` branches, not yet
verified or merged; see `benchmarks/results/stage-a-2026-09-30/README.md` for the measurements, the branches and the
next steps. Stage B (incremental cross-file passes) is not started.

| id | feature | what | seen in | done when |
|---|---|---|---|---|
| 1.1 | **Update proportional to the change** | Per-file hashes, re-extract only changed files and patch their nodes and edges into the graph, no whole-corpus rebuild; branch switch detected; the graph stage is done behind `VERINODA_INCREMENTAL` (D173, oracle-fuzzed equal to a fresh scan); left: the receiver sidecar, lexicon and search index proportional to the change, clustering, branch switch, default on | claude-context, narsil-mcp, codebase-memory-mcp, CodeGraph, GitHub Stack Graphs | an update of one edited file on Verinoda's own repository takes seconds, and its graph equals a full scan's node for node and edge for edge |

## 2 - Precise resolution layer

| id | feature | what | seen in | done when |
|---|---|---|---|---|
| 2.2 | **SCIP indexers run by Verinoda (opt-in)** | Detect the build and run scip-java, scip-typescript, scip-python and others instead of asking the user for a SCIP file | Sourcegraph auto-indexing | `scan --precise` on a Gradle project produces and adopts a SCIP index |
| 2.3 | **Compiler frontends (opt-in)** | javac/JDT, Roslyn, go/types, libclang as resolvers where no language server is installed | code-graph-rag, Eclipse JDT | one non-Python language resolved without an LSP |

## 3 - Structural search and query language

| id | feature | what | seen in | done when |
|---|---|---|---|---|

## 4 - Git history mining

| id | feature | what | seen in | done when |
|---|---|---|---|---|

## 5 - Retrieval and token economy

| id | feature | what | seen in | done when |
|---|---|---|---|---|
| 5.3 | **Hybrid lexical and embedding search (opt-in)** | A local embedding model adds leads fused with BM25 (reciprocal-rank fusion); leads only, never evidence | GitNexus, claude-context, Codanna, cocoindex-code, Augment | benchmark sets gain facts with no fact lost |

## 6 - Graph metrics and dependency health

| id | feature | what | seen in | done when |
|---|---|---|---|---|
| 6.5 | **Reachable vulnerable dependencies and SBOM (opt-in)** | Advisories filtered to library functions the code actually calls; CycloneDX output; licenses | Semgrep Supply Chain, narsil-mcp | an advisory is reported only with a call path to the vulnerable function |

## 7 - Architecture rules engine

| id | feature | what | seen in | done when |
|---|---|---|---|---|

## 8 - Change review extensions

| id | feature | what | seen in | done when |
|---|---|---|---|---|
| 8.8 | **Pull request triage (opt-in)** | Open PRs with CI and review state, PR impact, a warning when two PRs touch the same code | Graphify MCP | needs authenticated GitHub access |

## 9 - Test map and coverage

| id | feature | what | seen in | done when |
|---|---|---|---|---|

## 10 - New graph edges

| id | feature | what | seen in | done when |
|---|---|---|---|---|

## 11 - Claim history and memory

| id | feature | what | seen in | done when |
|---|---|---|---|---|

## 12 - Docs, decisions and specs

| id | feature | what | seen in | done when |
|---|---|---|---|---|
| 12.8 | **Issue and chat sources (opt-in)** | PR, issue, Jira and Slack threads as "why" evidence, with contradictions between sources shown | Unblocked, Glean, Tabnine | a why-answer cites a PR discussion |

## 13 - Agent integration

| id | feature | what | seen in | done when |
|---|---|---|---|---|
| 13.9 | **Improvement checklist pane (verinoda-live): the rest** | Step 1 shipped (D175): the command, two tools and the pane with three groups, a short first sight, details, three decisions, the person's own items, send and outcomes. **Step 2, to build:** single-choice groups for alternatives that exclude each other, items nested under an outcome, a free-text redirection that makes the model redo the list while the selections are kept, warnings about conflicting or dependent items. **Later:** previews and a screenshot loop for the `taste` group; a "keep" remembered from explicit decisions only, per project, with an expiry, that the user can see and delete, and that a new instruction overrides. **Not yet checked:** step 1 in a real terminal (`IMPROVE-PANE.md`, "What only a person can check"; the review starts from the command's own `turn.complete`, which the test engine does not raise). Known risks: a long list is not read (rank, fold, never pad); a guess in a checklist reads as a fact (a status on every item); the list frames what "better" means (own items); each review is a full pass and "check first" a second one (report the time and tokens) | none: our own idea (2026-10-04), not from the survey; Claude Code's review findings list is the nearest | a real session in which the result meets what the user wanted, no change outside the chosen outcomes goes unreported, and the evidence shown was right; compared with plain chat on vague requests: turns spent correcting, changes nobody asked for, what the user had to read, time and tokens. The share of shown items that get selected is a side figure, not the measure |

## 14 - Outputs and views

| id | feature | what | seen in | done when |
|---|---|---|---|---|

## 15 - Runtime evidence import

| id | feature | what | seen in | done when |
|---|---|---|---|---|

## 16 - Minecraft: vanilla source and mappings

| id | feature | what | seen in | done when |
|---|---|---|---|---|
| 16.1 | **Decompiled vanilla source (opt-in)** | The game version the build uses, decompiled and cached; classes and methods readable as evidence; its call graph and hierarchy | minecraft-dev-mcp, mcdev-mcp, minecraft-modding-mcp, ModLens, Loom genSources | `trace` and `when` continue into vanilla code |
| 16.2 | **Mapping namespace translation (opt-in)** | Names between obfuscated, Mojmap, Intermediary, Yarn, SRG and Parchment; stack traces remapped before `trace-log` | Linkie, Enigma, StackDeobfuscator | an intermediary crash log maps onto named code |
| 16.3 | **Symbol exists in a version and namespace** | "Does this method exist in 1.21.4 Mojmap?" | minecraft-modding-mcp | `api` answers per version |
| 16.4 | **Version diff for porting (opt-in)** | Class, member and registry changes between two game versions; breaking changes that touch the project | minecraft-dev-mcp, ModLens primers | `verinoda port 1.21.4 1.21.5` lists the project's sites that break |
| 16.5 | **Third-party mod jars (opt-in)** | A dependency mod's metadata, entry points, Mixin configs and decompiled code | minecraft-dev-mcp, ModLens | `api` reads a dependency mod's class |
| 16.7 | **Vanilla registry and data lookup (opt-in)** | Blocks, items, entities, vanilla tags, recipes and commands of the version | ModLens, misode/mcmeta | a datapack id is told apart from a typo |

## 17 - Minecraft validators

| id | feature | what | seen in | done when |
|---|---|---|---|---|
| 17.5 | **Command syntax and JSON schemas per version** | Commands, resource locations, NBT paths, loot tables and predicates checked against vanilla-mcdoc | Spyglass, Datapack Helper Plus | a malformed command is reported with its line |

## 18 - Flow analysis

| id | feature | what | seen in | done when |
|---|---|---|---|---|

## 19 - Behaviour probes and test generation

| id | feature | what | seen in | done when |
|---|---|---|---|---|
| 19.1 | **Symbolic differential behaviour (opt-in)** | Solver-found inputs where two versions differ; inputs that reach every branch | CrossHair diffbehavior and cover | `probe --symbolic` finds a planted difference random inputs miss |
| 19.2 | **Java differential tests (opt-in)** | Tests that pass on the old version and fail on the new, for Java | EvoSuiteR, Randoop, Diffblue Cover | `probe` works on a Java method |

## 20 - Field-test gaps (biology corpus, round 6)

From a field test of Symbiosis on a high-school biology corpus (31 to 41 topics, 12 queries, five rounds, a Symbiosis
variant against one without Verinoda); the report is `docs/SYMBIOSIS-GAPS.md`, the raw records
`biyo-platform/devtest/run6/` on the branch `biyo-platform-test` (not on the remote yet). The sample is one
corpus in one field, and the gold data was made by the product's designer in the same session, so it is not independent.
Ordered by the report's priority. Shipped from this section: D177 (20.5, 20.6), D178 (20.7), D179 (20.4 in part), D180 (20.2), D181 (20.1 stage A), D182 (20.3 for relations), D183 (20.8: documented).

| id | feature | what | seen in | done when |
|---|---|---|---|---|
| 20.1 | **Relation claims on a corpus: stage B** | Stage A shipped (D181): `verinoda relations` reads prerequisite, support and shared relations from cue words, with a named rule on each relation. Left: measure each rule on the field test's gold (the branch `biyo-platform-test` must reach the remote), then make the rules that measure well `analyze` claims of their own kind (`topic_relation`: history, staleness, `challenge`, reachable through MCP), still `strong_inference` at most | none: our own idea (field test, 2026-10-09), not from the survey | each rule's precision is measured on the gold; on the five measured pairs `analyze` returns a relation claim with the sentence that supports it and the right direction where the gold has one; edge coverage and direction accuracy measured again on the 12 queries |
| 20.3 | **User-defined evidence rule: on analyze claims** | Shipped for `verinoda relations` (D182: `evidence.rules`, which can only lower a status). Left: the same rules on `analyze`'s relation claims once stage B of 20.1 makes them, and conditions beyond `both_named`, `direction_known`, `no_conflict` and `min_sources` | none: our own idea (field test, 2026-10-09), not from the survey | the product's rule is written once and Verinoda's status for an `analyze` relation claim equals the product's |
| 20.4 | **MCP bound to a project root: the rest** | D179 found the cause (`--repo-of` serves the nearest folder whose `.mcp.json` registers the server) and made `setup` name the existing route (`projects add`, `mcp serve --all-projects`). Left: serving a nested project to a session in the outer folder without that registration, which D164's rule (a call never opens a project it names) does not allow as it stands; and the note in `doctor` and at the server's start | none: our own idea (field test, 2026-10-09) | a session in the outer folder reaches the nested project's index without editing its MCP entry, with D164's trust rule kept |

## 21 - Evaluation on a Docker machine

| id | feature | what | seen in | done when |
|---|---|---|---|---|

## 22 - Deferred from D186 (2026-10-12)

What the Verinoda Lean redesign (`docs/DESIGN.md` section 158) chose not to do, each with the reason it gives there. None of these
came from the survey.

| id | feature | what | seen in | done when |
|---|---|---|---|---|
| 22.1 | **Lab tools split** | The lab tools behind `--profile full` (question plans, references and research, feedback, experiments, the debug ledger, probes, runtime tracing and the modules under them) had no agent exposure in the agent studies, and the default install carries all of them. D186 kept them because a split into an extra or a distribution of its own is weeks of work, not because anything measured needs them. To do: decide the boundary (what the core profile imports), move the rest behind an extra, keep `--profile full` working through it | none: our own idea (D186 design review, 2026-10-12), not from the survey | `pip install verinoda` ships and imports the core profile's modules only; the extra brings the rest; both test suites pass; install size and import time are measured before and after |
| 22.2 | **Grammar cut** | The tree-sitter grammars (those of the Graphify port and the optional extras) have never been checked against what people index. To do: over a corpus of real repositories (the ten pinned clones and others) count the files indexed per grammar and the grammars that never yield a node; move the grammars no repository needs out of the default set into an extra, and say which. D186 kept the set because a cut without that count could remove a language someone uses | none: our own idea (D186 design review, 2026-10-12), not from the survey | a table of files indexed per grammar over the corpus, the cut list, install size before and after, and the eight sets with no fact lost |
| 22.3 | **Owner stamp for `.verinoda`** | A `.verinoda` folder that arrives with a clone or a copy is read as if this machine's Verinoda had built it: its graph, search index and `atlas.db` are whoever made them. D186 closed what such a folder could make Verinoda run or read outside the repository (the git funnel, path containment, the daemon state, MCP decision records) but not the foreign index itself. To do: write a stamp (an id of this user and machine, and the folder's real path) when Verinoda creates `.verinoda`; a folder without a matching stamp is reported as foreign (`doctor`, `setup`) and rebuilt or refused until the person adopts it with one command. Open: the cost of migrating indexes people copied on purpose | none: our own idea (D186 design review, 2026-10-12), not from the survey | a repository that ships a `.verinoda` is reported as foreign at the first command and nothing in it is trusted until adopted; an index the person copied is adopted with one command; the number of existing indexes the stamp would orphan is measured |
| 22.4 | **Read-only queries by default** | `query --read-only` (D177) writes nothing, but it is off by default, so a plain query still records freshness caches and may rewrite derived files. D186 left the default alone because the latency of rebuilding a stale index in memory is not measured. To do: measure it on the ten study clones (a stale search index and receiver sidecar); if it is acceptable make read-only the default for `query` and the MCP read tools, with an explicit way to refresh | none: our own idea (D186 design review, 2026-10-12), not from the survey | the in-memory rebuild time of a stale index is measured per clone, and the default is changed or the measurement says why it is not |
| 22.5 | **Two-session persistence study (project brain)** | No study spans two sessions or a context compaction, so a session-start card (a "project brain": what the last session found, with statuses) cannot be judged; the one measured up-front injection lost facts (207 against 212). D186 built nothing here. To do: pre-register a study in which session B on a repository starts with nothing, with a card made from session A's claims (statuses kept, stale ones marked), or with a card from the index alone; B's false facts and own model calls are the primary measures, and the decision rule is fixed before the first session | none: our own idea (D186 design review, 2026-10-12), not from the survey | the study runs with its rule fixed in advance; a card ships only if it lowers B's own model calls without losing facts or adding false ones |
| 22.6 | **Louvain headline re-measurement** | Every published result, the eight-set headline included (284/319 and 285/319 facts), ran with Leiden communities (graspologic-native); since D186 the default install clusters with networkx's Louvain. Not measured: the headline with Louvain, and the clustering time on large graphs (3.4 s against 1.0 s on Verinoda's own repository is D42's comment in `pyproject.toml`, not a re-measurement). To do: run the eight sets with and without the `leiden` extra, compare fact by fact, and time the clustering on the largest study clones | none: our own idea (D186 design review, 2026-10-12), not from the survey | per-set facts and clustering times with both backends in a dated results folder, a lost fact listed by id; the README says which backend the published numbers used |
| 22.7 | **The when-rule's limits** | For a "when was X added" question the first appearance of a code term the question names is a lead, never the answer (D186), and the rule fires only on a backticked token or a snake_case or camelCase identifier. Against the eight D185 when tasks it fires on one (axios, where the oldest commit is the gold); on four others the term's first appearance predates the asked-about change by 7 to 16 years (both counts are the design's, section 4.3 of `docs/drafts/2026-10-12-verinoda-lean-design.md`; session-local, not re-derived), so a looser rule would make false history on a kind of question that had none. To do: find a signal that tells the commit that introduced a term from the one that introduced the behaviour asked about, and test it on tasks written before the rule | none: our own idea (D186 design review, 2026-10-12), not from the survey | a rule whose firing set is fixed before the test; no wrong first-appearance claim on the D185 when tasks, and the axios class answered |
| 22.8 | **A path-free lead the agent's own search overrides** | On the guzzle trap of the D186 re-run (`benchmarks/results/claims-rerun-2026-10-13/`) every `analyze` result listed the true origin, 91f1e347, as the path-free first appearance of `MessageFormatter`, and every answer (3 of 3) still named b58db450, the oldest commit of the agent's own path-restricted `git log -S`, as the earliest: the lead was in front of the model and outranked by its own evidence. The call rule asks for one own check and does not say that a path-free first appearance outranks a path-bound one. To do: a sentence in the rule or in the lead line itself ("older than any commit under this path: a path-restricted `git log -S` misses it"), tested on the guzzle class before and after | our own measurement (the D186 re-run, 2026-10-13) | the guzzle trap answered without the false earliest commit in 3 of 3, the other five re-run tasks unchanged |
| 22.9 | **A renamed symbol's history before the rename** | On the gin trap the agent asked `analyze` with the constant's current name (`abortIndex`); the path-free first appearance was 8f30478, and 15216a0, where the history starts under the old name, was in no result and no answer (the judge graded none false; a hand reading finds 31323f6 named as the first). `git log -L` follows a file move, not a renamed identifier. To do: when a symbol's history begins with a rename or a re-addition of the same lines, follow the old name (the diff of the first commit names it) and add it as a lead; test on the gin class | our own measurement (the D186 re-run, 2026-10-13) | the gin trap's answers name 15216a0 as the start in 3 of 3 |

## 23 - After D186: what the final review and the re-run left (2026-10-13)

What the D186 branch leaves to do, in the order a next session should take it (`docs/CALISMA-NOTLARI.md` has the plan and
the method). None came from the survey; each names its own evidence.

| id | feature | what | seen in | done when |
|---|---|---|---|---|
| 23.1 | **Both arms in one time window** | The cost headline of the D186 re-run (`benchmarks/results/claims-rerun-2026-10-13/`: plain $0.0576, Verinoda $0.0633 a session, paired +$0.0057, 95 % +$0.0023 to +$0.0085) pairs 24 plain sessions run at 01:16 with Verinoda sessions run at 02:30 the same day; D185's plain arm agrees with the plain figure within 1.1 %, which is a check, not the same window. To do: both arms again in one command, from the work folder outside the repository (`C:/vbench-claims-rerun`, not the committed copy): move the 24 plain and the 24 Verinoda rows out of its `results.jsonl` and run `claims_run.py <config> --arms none,verinoda_guided --repeats 1 --tasks <the 24 ids>` (the harness runs the two arms side by side), about $2.9 and about 6 minutes (estimates from the first run's 01:16-01:22 and its session dollars), then the paired interval again | our own run (2026-10-13) | a dated results folder whose paired interval comes from sessions of one window, both intervals in its README |
| 23.2 | **An accuracy study that can show parity or a difference** (needs the user's go: on 2026-10-12 they said measurement studies are over, only cheap re-runs) | The re-run's 27 distinct tasks (21 with one repeat, 2 false-fact answers in the plain arm) cannot tell the D186 configuration from plain Claude Code, and nothing since 2026-10-02 measures it against Graphify with a model. To do: a pre-registered run on the D185 corpus (all 40 tasks, 3 repeats, both arms and a Graphify arm; the primary measure fixed before the first session: false-fact answers per arm with a paired interval; the judge is not blind, the harness's tool-name mask `[tool]` is itself a tell and the judge guessed the arm in 70 % of answers twice, so a hand reading is reported beside it, and a blinding that works, answers normalised in length and form, is a to-do of its own), about 360 sessions and as many judge calls (estimate: about $30 at the re-run's session prices; the judge calls and a Graphify arm are not priced) | our own study design (D185, D186) | an interval on the false-fact difference per arm, pre-registered, the blinding check reported, the Graphify arm in the same table |
| 23.3 | **Engine minors from the final review** | (a) a sub-question judged `met_with_inference` keeps that status when the critique later lowers its only claim to `weak_inference` (seen with a decision document that only names the symbol); (b) a when-question that fell back to the newest commits carries no marker that none shared the question's words; (c) `more: true` in `history_search`'s text and compare modes names no next call in its text; (d) the `quoted` bodies are cut independently of the rows past the cap; (e) `analyze` never rebuilds on an outdated extraction stamp: `_refresh_index` is not called when the tree hash is unchanged and its early return skips own-file-only changes, while `verinoda update` and `index_update` compare the stamp and rebuild; (f) Review Focus 2 of the D186 plan (a why whose history times out keeps its leads) is pinned only in part (`tests/test_analysis.py`). Each with a test that fails first | the final whole-branch review of D186 (2026-10-13; `docs/DESIGN.md` 158.5 for (a)-(d); the session ledger `docs/drafts/2026-10-13-d186-session-ledger.md` for (e) and (f)) | each item has a test and a DESIGN note, or a sentence in 158.4 saying why it stays |
| 23.4 | **Mod minors from the final review** | (a) a `cli` setting spelled with its Windows extension (`verinoda.exe`) is not found on PATH; (b) a relative `cli` setting is accepted as a path; (c) a UNC `cli` setting is ignored and `verinoda` is looked up on PATH instead, and nothing says so; (d) on POSIX a relative PATH entry (`.`, `bin`) is statted relative to the engine's working directory while every run uses the user's home as its directory; (e) `verinoda graph-state` maps every `checked: false` to `no_index`, "atlas.db unreadable" included. Tests in `claude-mods/verinoda-live/hooks/features.test.ts` and `tests/test_cli.py` | the final whole-branch review of D186 (2026-10-13) | each item tested, or recorded in the mod's AGENTS.md facts with the reason it stays |
| 23.5 | **Stale lines in the docs, and the test baseline** | Root `AGENTS.md`'s list of tests that fail on a clean checkout is of 2026-10-10 and was not re-measured after D186: run the whole suite once on a clean checkout and replace the list and its date. `docs/OZELLIKLER-RAPORU.md`'s intro says 148 sections; `docs/ARCHITECTURE.md` line 9 says D1-D40; `docs/BENCHMARKS.md` has no D186 section (the 2026-10-13 results folders are in their READMEs, DESIGN 158.3, BENCHMARK-BULGULARI 5.2-5.4 and OZELLIKLER 158, not there); `docs/UPSTREAM.md` records 3,813 upstream tests collected where this venv collects 3,811 (cause not determined: same tests, tree-sitter-hcl absent in both counts); `verinoda/scip_reader.py`'s docstring names the deleted `project_index/scip_ingest.py`; the local import block of `map_view` in `verinoda/mcp/server.py` carries a ruff I001 older than D186 (the per-file lint rule compares counts and let a second one through until the handover commit formatted it: compare the finding set against the branch base, not the count against HEAD) | the final review and the docs task of D186 (2026-10-13) | each line corrected against the tree; the test baseline from one whole-suite run on a clean checkout, listed in AGENTS.md with its date |
| 23.6 | **Known gaps carried from D186** | A removed Verinoda-own file still counts as a change for the index (the marker check runs on a missing file); `paths.escapes_lexically` rejects every `:` in a relative path, so a file with a colon in its name (legal on Linux and macOS) is dropped from the loaded graph and cannot be cited as evidence; the locate-daemon tests need the worktree's package on the child's path to run from a `git worktree` | `docs/DESIGN.md` 158.4 (the first two); the session ledger, the wave-1 minors (the third) | the own-file check reads the snapshot, not the file; the colon rule narrowed to Windows stream suffixes, with a test; the daemon tests green from a worktree |

## Out of scope

Not built, with the reason; listed so they are not proposed again without a new reason.

- Time-travel debugging (Undo, rr, Replay.io): a native debugger is a separate product.
- Live snapshots in running production services (Lightrun, Dynatrace): needs an agent in production.
- Branching and merging a shared knowledge store (ByteRover): needs a sync server.
- A single static binary: Verinoda is a Python package (Homebrew, Scoop and Winget wrappers stay possible).
- A bridge into a running game client (mcdev-mcp DebugBridge, ModLens): needs a mod shipped into the game.
- Reading and writing NBT: off the analysis mission.
