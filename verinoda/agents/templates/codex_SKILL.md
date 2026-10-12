---
name: verinoda
description: Evidence-first answers about this codebase with Verinoda - how a feature works, where something is implemented, how calls or data flow between components (handler -> service -> storage), why a design decision was made, what a change would affect, whether an earlier conclusion still holds, or what the code says for a should-we or which-to-pick decision (the user decides; Verinoda never chooses). Every answer is a set of claims with file:line evidence and an explicit status (verified, inference, unknown). Use it before explaining unfamiliar code, when the user disputes an earlier answer, and after writing Python code to check that the modules, names and keyword arguments it uses exist.
---
<!-- verinoda-managed v1 -->
<!-- Managed by `verinoda install`. After a local install, edits are kept: install will not overwrite them and uninstall leaves the file. A copy with no local install record is refreshed by install. Delete the marker line above to take ownership. -->

# Verinoda: evidence-first codebase analysis

The user mentions `$verinoda` in a prompt (or picks it from `/skills`); Codex may also choose it by itself when a task matches the
description. **There is no `/verinoda` slash command in Codex.** Do not tell the user to type one. The question to work on is the
rest of the user's message; if there is none about this repository, ask. Verinoda answers with claims that carry `path:line`
evidence and a status, or says **unknown**; its output is a lead for you to confirm.

## The rule
State as fact only what carries statically_verified, primary_source_verified, observed or experiment_verified; strong_inference and
below are not facts. Verinoda output is a lead: before stating 'no such change', 'first added in' or why something changed, confirm
with one git or grep check of your own. truncated: true or more: true proves no absence: narrow the call or check with git/grep
yourself. A question one grep or one file read answers needs no Verinoda call.

Verified means *verified at snapshot X* with the evidence (`snapshot.commit` in the result): `experiment_verified` (a recorded run),
`statically_verified` (cited lines re-checked against the tree), `primary_source_verified` (pinned docs, git history), `observed`.
`strong_inference` is "likely", say why; `weak_inference` is "possibly"; `contradicted` is false, cite the refutation; `stale` means
the code changed since: re-verify. Never present `weak_inference` or `unknown` as fact: say `unknown`, take its `next_step`, never guess.

## Which tool for which question

The MCP tools if the `verinoda` server is configured (`[mcp_servers.verinoda]` in `~/.codex/config.toml`), else the CLI.
- Why, how does X work, what does a change affect: `analyze` (`verinoda analyze "why is pricing separate from the service?"`). Start
  the answer with its `understood_as`; its leads are what to read next. `needs_clarification` is a normal result: ask the user its
  clarifications with `request_user_input` when it is available, otherwise as a short plain-text question.
- When a text appeared or disappeared, commits by message, author or path: `history_search` (`verinoda history text apply_discount`).
- Where is X: `project_query` (`verinoda query "where is the order total computed"`); hits are leads, not claims.
- Before editing a function: `change_review` (`verinoda review --target FILE::NAME --change signature`); before you say done:
  `verinoda review`. Report every concern and `unknown`: no finding is not safe.
- Code you wrote or edited (reading code needs no check): `code_check` (`verinoda check --diff`). Python, Java, Kotlin and TS/JS
  imports; another language comes back `not_checked`, never as checked. Never keep an `absent` site: use `nearest`, or `verinoda api <module>`.
- After code changes: `index_update` (`verinoda update .`). Claims on changed files become `stale`: verify them again.
- Pure code-writing: skip the question workflow; the name check, debug ledger and `decide check --changed` apply.

## Evidence, setup and safety

- Cite the narrowest `path:line` / `path:a-b` that holds each statement (passages number lines), not a function span.
- A graph edge alone is never verification: `trace`, `query` and `map` give leads; confirm them with source lines, and repeat a view's
  `coverage.limits` when you rely on it. Never invent a relation, call path, file, line or number; a code name reported `not_found`
  does not exist, never use a similar one. A budget that runs out leaves `unknown` (`usage.exhausted` in JSON): report it so.
- `verinoda doctor --brief` shows the `graph` and `snapshot` lines; no index yet: `verinoda scan .`. The CLI prints plain text written
  for you: read it as it is. Add `--json` only for a field the text leaves out: JSON costs 2-5x the tokens. In PowerShell,
  single-quote regexes and globs.
- Commands find the project root from the working directory; pass `--repo <dir>` otherwise. The CLI command
  recorded at install time is `{{VERINODA_CLI}}`.{{VERINODA_CLI_NOTE}} If it fails inside the Codex sandbox (`PermissionError` or `ModuleNotFoundError`
  importing `verinoda`) or is not on PATH, use the MCP tools (they run outside it; their entry stores the absolute path). A tool the
  MCP menu does not list: use the CLI, or ask the user for `"mcp": {"profile": "full"}` in their user-level Verinoda config and a
  restart. Never run `verinoda trust` yourself.
- Decisions are the user's: `verinoda decide brief "<question>"` gives the code's side and `questions_for_human`, never a recommendation.
  Record only their explicit choice: `verinoda decide record <brief-id> --chosen NAME --rationale "<their words>" --said "<their words, verbatim>"`.
  Never edit, supersede, accept or waive a decision yourself.
- Fixing a bug: `verinoda debug start "<symptom>" -- <repro command>` before the first edit (MCP `debug_start`),
  `verinoda debug try --hypothesis "<what you believe and why>"` after every edit (MCP `debug_attempt`; your own run:
  `--observed-output out.txt --exit-code N`). On `stop: true` stop editing and run `strategies[0]`; on `questions_for_human` ask the
  user (as above): never change a test's expected value or skip a failing test yourself. Never say "fixed": the repro passed at tree T in run R.
- The user's critique of an answer is a hypothesis: `verinoda feedback add --text "<their point>" --claim <claim-id> --process`.
  The rest (`trace`, `map`, `claim`, `verify`, `challenge`, `plan`, `resolve`, `owners`, `probe`): `verinoda <command> --help`.
