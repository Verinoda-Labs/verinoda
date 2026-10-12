# Upstream origin: Graphify

Verinoda (formerly developed under the working name RepoAtlas) is a derivative of **Graphify**
(<https://github.com/Graphify-Labs/graphify>). It is an independent project and
is **not** an official Graphify release or endorsed by its authors.

| | |
|---|---|
| Upstream repository | https://github.com/Graphify-Labs/graphify |
| Pinned commit | `20a20d30d8e7eef77675651f0199d87f913bd3e7` (2026-09-20, "test(ts): de-flake the normalizer scaling test…") |
| Nearest tag | `v0.9.65` (the commit is after it on `main`) |
| Upstream package | `graphifyy` 0.9.65 (not a runtime dependency of Verinoda) |
| Licence | Apache-2.0, with earlier contributions under MIT. `LICENSE`, `LICENSE-MIT` and the upstream `NOTICE` text are kept unchanged. `NOTICE` adds the derivation statement. |
| Recorded in code | `verinoda/project_index/UPSTREAM_COMMIT` |

## How the code was brought in

`tools/port_upstream.py <graphify-checkout>` is the only way upstream code
enters this repository. It:

1. copies upstream `graphify/` → `verinoda/project_index/` and `tests/` → `tests_upstream/`;
2. rewrites module paths only: `graphify.<module>` → `verinoda.project_index.<module>`,
   `from graphify import` / `import graphify` / `-m graphify`, and the
   distribution name used in `importlib.metadata.version("graphifyy")` → `"verinoda"`;
3. in tests only, rewrites repo-relative paths (package dir, skill bodies,
   `ARCHITECTURE.md`/`how-it-works.md` now under `docs/upstream/`);
4. appends a clearly delimited "Verinoda port adjustments" block to
   `tests_upstream/conftest.py` (see below);
5. writes the upstream commit SHA to `verinoda/project_index/UPSTREAM_COMMIT`;
6. deletes the upstream surface Verinoda does not ship (`DELETED` in the
   script; the inventory is under [Removed in D186](#removed-in-d186)) and
   every upstream test that imports one of those modules or runs the upstream
   CLI. A test file that mixes such tests with tests of kept code is deleted
   whole by the script and trimmed by hand instead (the trimmed files are
   listed under [Modified](#modified)): re-apply the trims after a re-sync.

Files under `verinoda/project_index/` are hand-edited only for the local
changes listed under [Modified](#modified), each marked `Local change (Verinoda)`
or `Verinoda patch` in the code. Everything else Verinoda adds lives outside that directory,
including the one runtime patch described under
[Runtime patch applied from outside the vendored tree](#runtime-patch-applied-from-outside-the-vendored-tree).
Re-syncing is therefore: check out a newer upstream commit, re-run the script,
re-apply the local changes, review `git diff`, run both test suites.

The import rewrite was necessary rather than cosmetic: keeping a top-level
`graphify` package would collide with an installed `graphifyy` in the same
environment. There was no other bulk renaming (functions, CLI strings, the
`graphify-out` default name, messages all stay as upstream wrote them).

## Upstream test-suite after the port

Measured at port time on the development machine (Windows 11, Python 3.12.0,
`.[mcp]` extras only), and again on 2026-10-12 before and after the D186
deletions (the same machine, `.[mcp,precise]`, graspologic-native installed).
Verinoda's round-3 work did not edit `project_index/`, but the path-identity
patch below changes how it runs inside Verinoda; that patch has its own test
in the product suite.

| Run | Passed | Failed | Skipped | Notes |
|---|---|---|---|---|
| Upstream checkout, unmodified (`pytest` in `upstream-graphify/`), port time | 5503 | 51 | 297 | baseline |
| Ported (`pytest tests_upstream`), port time | 5436 | 50 | 299 (+1 xfail) | |
| Ported, 2026-10-12 before D186 | 5451 | 54 | 280 (+1 xfail) | the same suite with the local patches since the port |
| Ported, 2026-10-12 after D186 (94 files deleted, 22 trimmed) | 3645 | 38 | 130 | 3813 collected against 5786 |

Every failure in the ported run at port time also failed in the unmodified
upstream checkout on the same machine (checked test-by-test). They come from
optional grammars that are dev-only upstream (`tree-sitter-hcl` → all terraform
tests), Windows lacking `os.mkfifo`/`AF_UNIX`/unprivileged symlinks, and
Windows' default `cp1254` console encoding in a few tests. The difference in
the passed count at port time is `test_skillgen.py` (67 tests), which was
excluded. The 38 failures after D186 are the 34 of the 54 before it whose files
remain (the other 20 were in deleted files), the three terraform-module ids
their trimmed parametrization renamed (the file fails whole without
`tree-sitter-hcl`, as before), and `test_extract.py::test_collect_files_skips_hidden`,
which fails only because the measuring checkout sat under a `.claude/worktrees/`
folder (a dot component in every fixture path; it passed in a copy outside it).
`test_backend_extras.py::test_all_extra_is_the_union_of_every_other_extra`
failed before D186 (`[all]` lacked `hypothesis`) and passes after it.

Port adjustments (in `tests_upstream/conftest.py`, appended by the script):

- `test_the_warning_names_the_stale_destination_and_the_exact_command` is
  `xfail(strict=True)`: the upstream installer compares a skill stamp against
  the `graphifyy` version line (0.8.x/0.9.x); Verinoda is 0.1.x, so the
  fixture's "stale" skill looks newer and takes the downgrade branch. (The test
  left with the installer in D186; the mark stays for a re-sync that brings it back.)
- Until D186, `test_skillgen.py` was excluded from collection: it regenerated
  upstream's own skill bodies and audited them against blobs from upstream's
  git history, which this repository does not hold. The skill files and
  `tools/skillgen/` left in D186, and the script now deletes the test with them.

## Runtime patch applied from outside the vendored tree

**Path-identity memo.** The vendored incremental rebuild
(`project_index/watch.py`, class `_StoredSourcePaths`) recomputes a pathlib
identity for every node and edge on every update. `identity()`,
`in_watch_root()` and `rebase_preserved()` are pure functions of the
`source_file` string and of fields set once in `__init__`. Verinoda
therefore memoises them per instance.

- **Where:** `verinoda.index.install_path_identity_memo()`, called from
  `verinoda.index.build()`. It is a monkeypatch. `watch.py` itself is
  unchanged and stays byte-identical to upstream. The patch is idempotent,
  and it is skipped silently if a future upstream renames the class.
- **What it changes:** only speed. The memo returns exactly what the original
  methods return. `tests/test_index.py::test_path_identity_memo_keeps_the_graph_byte_identical`
  builds two copies of `examples/orders_app`, changes one file in each and
  runs the vendored incremental rebuild, once with the memo and once
  without. It requires the two `graph.json` files to be byte-identical.
- **Measured effect** (round-3 search track, one run on the development
  machine, not a benchmark-harness result): a one-file update of
  `graphify_core` (226 files, `querylog.py` touched). The index step fell
  from 4.45 s without the memo to 2.69 s with it, and the whole
  `verinoda update` from 6.25 s to 4.24 s. The two `graph.json` files had
  identical nodes, links, attributes and order. They differed only in
  `built_at_commit`, because each measured copy was its own git repository.
  The memoised methods took about 60% of such an update before the patch.

## Post-processing of graph.json from outside the vendored tree

**Portable ids.** An id with no file of its own keeps what the upstream
pipeline minted it from: the target of an import whose file does not exist
(`require('./missing')`, resolved against the importer's absolute path) and the
element ids of a `.dmf` interface file (they embed the window's id) carry the
scan root folded into `_` parts, user name included.

- **Where:** `verinoda.portable_ids.make_graph_portable()`, called from
  `verinoda.index.build()` after the pipeline wrote graph.json and before the
  receiver-call sidecar is refreshed. No vendored file changes.
- **What it changes:** only ids that start with the root's folded form and
  belong to no node with a source file, and the `_elem_<root>_` part of `.dmf`
  ids; an id that would take one another thing already has gets `_unresolved`;
  nothing under a root of one folder. The `label` and `norm_label` of a node
  whose id is rewritten lose the root the same way (the pipeline labels such a
  node with its id: until 2026-09-24 the name shown for it kept the path). graph.json is written back in the
  pipeline's own format (indent 2, key order kept). On the eight benchmark
  corpora no id carries the root, so they are unchanged (fresh-index A/B,
  2026-09-24: identical results).

**Case-distinct ids.** The pipeline folds case into every id (`make_id`) and
keeps colliding ids apart only across files, so two symbols of one file whose
names differ only in case were one node: `class OrderService` and `export const
orderService = new OrderService()` merged into a node with the class's kind and
the const's label and line, and `new OrderService()` and `import { orderService }`
both landed on it (senior evaluation, 2026-09-26).

- **Where:** `verinoda.case_ids.split_case_collisions()`, run by
  `verinoda.index._distinct_case_ids` for the length of a build on the output of
  the pipeline's `extract()` and on the input of its `build_from_json()` (a
  wrapper of the module attributes, as for the other build-time patches). No
  vendored file changes.
- **What it changes:** only such groups, and only in case-sensitive languages
  (JS/TS, Python, Java, Kotlin, Go, Rust, C/C++, C#, Swift, Ruby, ...; not SQL,
  Pascal, Fortran, PHP, Apex). The name that sorts first keeps the id; each other
  gets `<id>_<6 hex of sha1(name)>`. Edges are moved by the line they were read
  from (details in the module docstring); an update, which keeps the unchanged
  files' nodes, routes a new edge into such a pair the same way.

**No upstream graph.html.** `verinoda.index.build()` runs the pipeline with
`GRAPHIFY_VIZ_NODE_LIMIT=0` (the upstream switch; `_without_upstream_html`)
unless the variable is set, so no `graph.html` is written and the pipeline
removes an old one itself. That page loaded vis-network from a CDN when opened;
`verinoda ui` and `verinoda ui --export` show the graph with nothing from
outside. It cost about a second and 3 MB per build on Python's standard library
as a project (2,305 files). A positive value keeps the page. graph.json and
GRAPH_REPORT.md are the same either way (orders_app, forge_mod, glow_mod byte
for byte; Verinoda's own repository node for node and link for link, 2026-09-24).

## Feature inventory

"Carried" = the code is present and unmodified apart from the import rewrite.
"Used" = a Verinoda command depends on it. "Exposed" = reachable by a user.

### Carried and used by Verinoda

| Upstream feature | Upstream location | How Verinoda uses it |
|---|---|---|
| File detection / corpus scan | `detect.py` | via the rebuild pipeline in `scan`/`update` |
| Tree-sitter AST extraction (Python, JS/TS, Go, Rust, Java, C/C++, C#, Ruby, Kotlin, Scala, PHP, Swift, Lua, Zig, PowerShell, Elixir, ObjC, Julia, Verilog, Fortran, Bash, JSON, Groovy, COBOL + optional grammars: SQL, Terraform, OCaml, Common Lisp, DreamMaker, Robot Framework, and from v0.9.73 Erlang, R, Solidity, VB.NET) | `extract.py`, `extractors/` | the knowledge graph behind every Verinoda view. Upstream already resolves method calls by receiver type in about ten languages (Swift, TS/JS, C++, C#, Java, ObjC, Kotlin, Ruby, Rust); for Python it resolves only `ClassName.method()`. Verinoda adds a narrow Python pass for annotated parameters and `x = Cls()` locals, marked `INFERRED` + `derived_by=verinoda.receiver`. |
| Graph build, dedup, symbol resolution | `build.py`, `dedup.py`, `symbol_resolution.py`, … | same |
| Code-only rebuild (no LLM), incremental rebuild with changed paths, per-repo lock | `watch._rebuild_code` | `verinoda scan` (full) and `verinoda update` (changed files only), with the path-identity memo above |
| Community detection, report, HTML graph | `cluster.py`, `report.py`, `export.py` | produced in `.verinoda/index/` on every build (GRAPH_REPORT.md; graph.html only when `GRAPHIFY_VIZ_NODE_LIMIT` is a positive number, see above) |
| Query term extraction and node scoring | `serve._query_terms`, `_score_query`, `_score_nodes`, `_pick_scored_endpoint` | fuzzy name resolution in `index.Graph.resolve` (trace endpoints, node lookups) after Verinoda's exact id/path/`Class.method` rules, and `retrieval.terms_for` (the term list of the benchmark's raw baseline). Ranking for `query`/`analyze` now comes from Verinoda's own `search_index.py`. |
| Graphify query renderer | `serve._query_graph_text` | the "Graphify baseline" in `verinoda benchmark` |
| Confidence labels on edges (EXTRACTED / INFERRED / AMBIGUOUS) | extraction schema | kept on every edge; Verinoda never treats them as verification |
| URL validation and safe fetching | `security.py` | document research (`verinoda research <url>`) and the reference resolver's live HTTP transport |

### Removed in D186

Until 2026-10-12 the upstream CLI was reachable as `verinoda index -- <graphify
arguments>` (a pass-through with the installer and the `~/.graphify` writers
blocked), and the package shipped the modules and 126 skill Markdown files only
that CLI used. No Verinoda command and no measured result reached them
(docs/DESIGN.md D186), so they left the package. `tools/port_upstream.py`
deletes them again after every re-sync (`DELETED`).

| Upstream item | What it was | Forced edits |
|---|---|---|
| `cli.py`, `__main__.py` | the `graphify` command line and `python -m graphify`; `verinoda index` with it | `verinoda/cli.py` lost `cmd_index`, the `index` subparser and the block lists `UPSTREAM_BLOCKED` / `UPSTREAM_HOME_WRITERS`; `tests/test_cli.py`, `tests/test_docs.py`, `tests/test_packaging.py` lost the pass-through cases |
| `install.py`, `hooks.py`, `skill*.md`, `skills/*/references/*.md`, `always_on/*.md`, `command-kilo.md`, `tools/skillgen/` | the multi-platform installer of *Graphify*-named skills (22 assistants), git hooks and merge driver, the skill bodies and the generator that rendered them | pyproject `package-data` for `verinoda.project_index` is `["UPSTREAM_COMMIT"]` (read by `verinoda doctor` and the benchmark runner); `tests/test_packaging.py` `MUST_SHIP` and the skill-file counts |
| `wiki.py`, `tree_html.py`, `diagnostics.py`, `affected.py`, `global_graph.py`, `cross_repo_calls.py`, `cross_repo_types.py`, `multigraph_compat.py`, `scip_ingest.py`, `semantic_cleanup.py`, `benchmark.py`, `cargo_introspect.py`, `pg_introspect.py`, `manifest.py` | wiki and tree exports, extraction diagnostics, the `affected` query, the `~/.graphify` global graph and cross-repository merges, the multigraph probe, the SCIP JSON skeleton (Verinoda reads real `index.scip` files with its own `scip_reader.py`), LLM-fragment cleanup, the upstream benchmark, Cargo and PostgreSQL introspection, the `.graphify-manifest` writer | `project_index/__init__.py` lost the lazy `to_wiki` entry (marked) |
| `llm.py`, `prs.py`, `transcribe.py`, `google_workspace.py`, `callflow_html.py`, `exporters/graphdb.py`, the upstream MCP server in `serve.py` (`_build_server`, `serve`, `serve_http`, `_ApiKeyMiddleware`, `_main`, with `ToolError` and `_filter_blank_stdin`; its tools were `query_graph`, `get_node`, `get_neighbors`, `get_community`, `god_nodes`, `graph_stats`, `shortest_path`, `list_prs`, `triage_prs`, `get_pr_impact`) | the LLM extraction backends (openai, kimi, gemini, ollama, bedrock, anthropic) with their chunking and provider registry, the GitHub PR views (`gh`), YouTube transcription (yt-dlp, faster-whisper), Google Workspace shortcut export, the call-flow HTML page, the Neo4j and FalkorDB pushers, and the second MCP/HTTP server (`verinoda mcp serve` serves Verinoda's own tools) | `detect.py` lost the google_workspace import, the `.gdoc/.gsheet/.gslides` classification and the `google_workspace` parameter of `detect()` / `detect_incremental()`; `export.py` the graphdb re-export; `dedup.py` `_llm_tiebreak` and `dedup_llm_backend`, with the `build()` / `build_merge()` parameter of `build.py` that passed it through; `serve.py` keeps the query helpers (`verinoda.index`, `verinoda.retrieval` and the benchmark use them); `ingest.py` lost the tweet, arXiv, web page and YouTube fetchers (`ingest` keeps the PDF and image downloads) and `OUTCOMES` moved to `reflect.py`; `watch.py` lost the callflow refresh; the extras kimi, ollama, bedrock, anthropic, gemini, openai, video, neo4j, falkordb, postgres and google went, and `markdownify` left the pdf extra. Each edit is marked "Verinoda patch (D186)" |

Upstream tests of this surface left with it (the script's rule and
`DELETED_TESTS`), 94 files; the tests of kept code in files that also tested
it were kept and the files trimmed (listed under [Modified](#modified)).

### Removed from the distribution

| Upstream item | Reason |
|---|---|
| Console scripts `graphify`, `graphify-mcp` | Would clash with an installed `graphifyy`. |
| `Dockerfile`, `uv.lock`, `scripts/`, `worked/` examples, `docs/translations/`, logos and other visual assets | Not needed; Verinoda must not reuse Graphify's visual identity. |
| Upstream README/ARCHITECTURE/BENCHMARKS/CHANGELOG/SECURITY/how-it-works | Kept verbatim under `docs/upstream/` for reference. They describe Graphify, not Verinoda, and since D186 the ARCHITECTURE table names modules that are no longer in the package (`tests_upstream/test_architecture_doc.py`, which checked that table against the code, left with them: `DELETED_TESTS` in the port script). In particular Graphify's published accuracy, cost and token figures are **not** Verinoda claims; Verinoda's own measurements are in `docs/BENCHMARKS.md`. |

### Modified

| Item | Change |
|---|---|
| All upstream Python and skill files | module paths only (see above) |
| Version lookup | reports the `verinoda` distribution version |
| Output directory | unchanged in the module (`GRAPHIFY_OUT`, default `graphify-out`); Verinoda entry points set `GRAPHIFY_OUT=.verinoda/index` before importing it |
| `watch._StoredSourcePaths` (at run time only) | memoised by the path-identity monkeypatch; source file unchanged |
| `tests_upstream/conftest.py` | appended port-adjustment block (above) |
| `project_index/__init__.py` (D186, marked "Verinoda patch") | no lazy `to_wiki` entry: `wiki.py` left with the upstream CLI surface |
| `detect.py` (import block, `classify_file`, `detect()`, `detect_incremental()`), `export.py` (import block), `dedup.py` (`deduplicate_entities`), `build.py` (`build`, `build_merge`), `serve.py` (header; the server cut from the end of the file), `ingest.py` (header, `ingest`), `reflect.py` (`OUTCOMES`), `watch.py` (`_rebuild_code`'s product line) (D186, each marked "Verinoda patch") | the edits the removal of the LLM, PR and media layer forced, as listed under [Removed in D186](#removed-in-d186) |
| `tests_upstream/test_detect.py`, `test_dedup.py`, `test_file_slice.py`, `test_partial_cache.py`, `test_hyperedge_member_shapes.py`, `test_semantic_cache_out_root.py` (D186, each marked "Verinoda patch"); `tests_upstream/test_backend_extras.py` (rewritten, marked) | the tests of the LLM layer, of `dedup_llm_backend` and of the Google Workspace conversion were cut out; `test_backend_extras.py` keeps the two extras invariants (`[all]` is the union, the version-gated dependencies are packaged) and lost the `[anthropic]`, PostgreSQL and `_backend_pkg_hint` cases |
| `tests_upstream/test_cjs_module_extension.py`, `test_duplicate_annotation_edges.py`, `test_export_path_length.py`, `test_god_nodes_exclude_hubs.py`, `test_indirect_call_nested_closure_shadow.py`, `test_indirect_dispatch.py`, `test_indirect_dispatch_assign_return.py`, `test_indirect_dispatch_getattr.py`, `test_js_dynamic_imports.py`, `test_no_dedup_flag.py`, `test_query_induced_edges.py`, `test_reflect.py`, `test_scala_self_type.py`, `test_terraform_modules.py`, `test_unverified_semantic_shrink.py` (D186, each marked "Verinoda patch") | the tests of the removed upstream CLI, `affected`, `diagnostics` and `wiki` were cut out of files that also test kept code (an `affected` query over an extracted graph, a CLI run next to a `watch._rebuild_code` run, ...); the tests kept are upstream's. A re-sync deletes these files whole (the script's rule): re-apply the trims |
| `extractors/csharp.py` `_resolve_csharp_type_references` (local change, D65) | a dangling type reference finds the first placeholder of its label through a dict built once, not a scan of all nodes per reference; the same graph, the pass 4.2 s -> 0.05 s on a 591-file C# repository |
| `extractors/engine.py` call binding, `extractors/go.py`, `extractors/rust.py` (local change, D65) | a member call binds to a same-file definition only through the method's own receiver (`self`/`cls`, `this`, `$this`, Ruby `self`/`self.class`, the Go receiver, Rust `self`/`Self::`/`Type::`, also with a turbofish) or a receiver whose type the file states (Go: a parameter, a local or package variable of `&T{}` / `T{}` / a constructor `NewT()`, a struct field, a method promoted from an embedded struct; PHP: a typed parameter, `$x = new T()`, a typed or promoted property, `$this->p = new T()`); an untyped PHP receiver binds only to the one same-named method of another class of the file; Python `super().m()` binds to an in-file base's `m` in C3 order (past `object`) or not at all; `self.m()` prefers the own class; bare Go/Rust calls never bind to a method. `cache._AST_CACHE_SCHEMA` is 7 |
| `extract.py` `extract`, new `vendored.py` (local change, D65) | vendored files (`vendor/` at the root, beside `go.mod`/`composer.json`/`Gemfile`/`Cargo.toml` or under a static-asset folder; `_vendor/`, `third_party/`, `third-party/`, `thirdparty/`; `deps/` beside `mix.exs`/`rebar.config`; a git submodule under `deps/` or `extern/`) and generated files (a generator's header comment) keep their definitions, marked `vendored`, but no edge other than their structure (`contains`, `method`, `defines`, `inherits` ...) leaves them; minified files (`.min.js`/`.bundle.js`, or a script mostly in lines of code over 1,000 bytes) keep their file node only; `VERINODA_GRAPH_VENDORED=1` (config `index.vendored`) keeps everything. `guards.is_generated` uses the same header rule |
| `extractors/engine.py` `_distinct_def_id`, `_def_symbol_name`, `_same_def_name`, `_distinct_id_via`, `_public_def_swaps`, `_apply_id_swaps`, the Java overload numbering and their calls at the definition sites (local change, marked "Verinoda patch") | two definitions of one scope whose names mint one id (`request` / `_request`, `getX` / `getx`; case is folded in PHP) were one node, the second dropped by `add_node` and its body's calls read as the first one's: a different name gets `<id>_<6 hex of sha1(name)>`, and at the end of the file the name with the fewest leading underscores takes the plain id (`const _config` then `function config`: the function); a salted Java method's overloads are numbered from its salted id. Covers functions, methods, nested functions, JS `const f = () =>`, `exports.f =` / `X.prototype.f =` / `this.f =` assignments and class-field arrows. `cache._AST_CACHE_SCHEMA` is 10 |
| `detect.py` `CODE_EXTENSIONS`, `extract.py` `_DISPATCH` and the C++ resolver's suffixes (local change, D65) | `.hh .hxx .ipp .inl .tpp` are C++ |
| `extractors/engine.py` `_declaration_line`, `_python_note_overload` and the class, function and Python `decorated_definition` branches of `_extract_generic`; `cache._AST_CACHE_SCHEMA` 9 (local change, marked "Verinoda patch") | a class or function is cited at its name's line, not at the annotations or attributes its node starts with (`@Override` above a Java method, `[HttpGet]` above a C# one; every grammar whose definition node has a `name` field), the line a decorated Python def already had; Python `@overload` stubs and their implementation stay one node, located at the implementation (the def without `@overload`), the stubs' lines in its `overloads` metadata (`overload_stub: true` while no implementation follows, as in a stub file) |
| New `extractors/cobol.py`, `erlang.py`, `r.py`, `solidity.py`, `vbnet.py`; `extractors/ocaml.py`, `razor.py`, `terraform.py`; the language tables of `extract.py` (imports, `_DISPATCH`, `_CASE_INSENSITIVE_EXTS`, `_LANG_FAMILY_BY_EXT`, the four resolvers and `cobol_copybooks`, `_EXTRA_FOR_EXTENSION`, the `Rscript` shebang), `detect.py` `CODE_EXTENSIONS`, `analyze.py` `_LANG_FAMILY`, `extractors/__init__.py`, `extractors/base.py` `_CaseIds` (marked "Verinoda patch: ported from upstream Graphify v0.9.73 (ef4450d)") | the languages upstream added after the pinned commit, ported from tag `v0.9.73` (commit `ef4450d9c28acb2b8cdc22d369c1777b77148eef`) with the module-path rewrite, plus these hand edits, each marked "Verinoda patch": VB.NET nested types are read (a nested `Class`/`Structure`/`Module` block is not wrapped in `type_declaration`, so upstream skipped it with all its members); a COBOL scope terminator (`END-READ.`, `END-EVALUATE.`, ...) or a fixed-format name outside Area A is not a paragraph; a COBOL `COPY` of a copybook in another directory is bound by `resolve_cobol_copybooks` (a fifth resolver) or not at all, never to a file that does not exist; R, Solidity and Erlang symbols whose names differ only in case keep two ids (`extractors/base.py` `_CaseIds`); an Erlang export written in base notation (`f/2#1`) no longer drops its file. The languages: COBOL (regex, no grammar), Erlang and R (`tree-sitter-language-pack==0.11.0`), Solidity (`tree-sitter-solidity==1.2.13`), VB.NET (`tree-sitter-vb-dotnet==0.3.0`), each grammar an optional extra; OCaml classes with their methods and instance variables, Razor `@functions` blocks, and Terraform secret redaction inside lists, name/value pairs and sensitive variable/output blocks, as v0.9.73 has them. The rest of `extract.py` and the other extractors stay at the pinned commit. A re-sync to v0.9.73 or later takes these files as they are upstream |
| `detect.py` `_git_env`, `_git_ls`, `_git_rules`, `_git_rules_are_utf8`, `_git_listed_files`, `_git_kept_untracked`, `_git_enumerate`, the `enumeration` parameter of `detect()` (local change, D66, marked "Verinoda patch") | at the top of a git work tree the file list comes from `git ls-files` (git's own ignore semantics) instead of the walk; a re-sync with `tools/port_upstream.py` overwrites the file: re-apply and run `tests/test_detect_git.py` and `tests_upstream/test_detect.py` |
| `extractors/engine.py` `_js_extra_walk`, `_scan_js_nested_function_declarations`, the JS/TS call binding, new `_js_module_owner_names` and `_js_collect_body_bound_names`; `extract.py` cross-file label index; the marker lists in `watch.py` and in `cli.py` (since removed, D186) (local change, marked "Verinoda patch") | `obj.m = function name() {}` / `obj.m = () => {}` at module level, where `obj` is bound at module level in the file (a `var`/`let`/`const`, a function or a class), is the method `.m()` of `obj` (Express `res.json`, `app.render`; each name of an alias chain `res.set = res.header = fn`); a function bound in a function (`const login = async () => {}`) is a nested symbol with its own calls; a bare call binds to the nested function visible from the caller, a member call never to a nested function; a method of such an object binds only through that object or its own `this`; a nested function's locals include the enclosing scope's names; such a method takes no bare name in the file's label map, and both kinds carry the `_no_bare_name` marker, which keeps them out of the cross-file bare-name and by-value index in `extract.py` (kept for unchanged files on incremental builds). `cache._AST_CACHE_SCHEMA` is 10; test: `tests/test_graph_precision.py` |
| `extractors/go.py` receiver chains and new `resolve_go_receiver_calls`; `extractors/rust.py` receiver types (`_rust_type_desc`, `_rust_use_map`) and the `_rust_returns_self` marker; `extractors/engine.py` PHP `Foo::m()` / `self::` / `parent::` binding, `_php_namespace_facts`, the `_php_fqn` marker and JS/TS `fn.call/apply/bind`; `extract.py` new `_resolve_rust_typed_member_calls` and `_resolve_php_static_calls`; the marker lists in `watch.py` and in `cli.py` (since removed, D186) (local change, marked "Verinoda patch") | a method call binds when the source states the receiver's type: Go locals, parameters, fields, elements and method results typed across the files of a package (read from disk by the package pass); Rust `Type::m()` of this crate (by its `use`/path root and one declaration in the corpus), parameters and `let`s of a stated type or a `Self`-returning constructor; PHP `Foo::m()` to Foo's method by the class FQN (namespace and `use`), no longer to the class; JS/TS `fn.call/apply` as a call of `fn`, `fn.bind` as an indirect call. A Go interface, a Rust trait object or `impl Trait` binds to the interface's or trait's declaration of the method (a lead, INFERRED 0.75), never to an implementation. Edges from a receiver's type are INFERRED (0.85). `cache._AST_CACHE_SCHEMA` is 14; tests: `tests/test_rw_receivers.py`, `tests/test_graph_precision.py`, `tests_upstream/test_php_object_creation.py`, `tests_upstream/test_rust_self_member_calls.py` |

### New in Verinoda (not in Graphify)

Everything under `verinoda/` except `project_index/`, described per module in
[ARCHITECTURE.md](ARCHITECTURE.md):

- **Graph and indexes:** `index.py`, `search_index.py`, `textnorm.py`,
  `lexicon.py`, `snapshot.py`, `architecture_map.py`, `retrieval.py`.
- **Question and references:** `question_plan.py`, `references/`.
- **Claims and trust:** `store.py`, `evidence.py`, `anchors.py`, `entail.py`,
  `claims.py`, `callsite.py`, `critique.py`, `precise.py`, `scip_reader.py`,
  `runtime/`, `memory.py`.
- **Loops and entry points:** `workflow.py`, `analysis.py`, `experiments.py`,
  `research.py`, `feedback.py`, `cli.py`, `mcp/`, `agents/`, `benchmark/`,
  `doctor.py`, `paths.py`.

Also new: `tests/`, `examples/orders_app`, `tools/port_upstream.py`,
`tools/record_reference_cassettes.py`, and the docs in `docs/` except
`docs/upstream/`.
