# verinoda-live: a Claude Code mod for Verinoda

A function-hooks plugin ("mod") for Claude Code that puts the Verinoda MCP server's tools in front of the model with a
one-paragraph call rule, keeps a Verinoda index fresh while Claude edits, and can check each edit for names that do not
exist. It finds the project (the nearest folder at or above the session's with a `.verinoda` index; never a home folder
or a drive root unless the settings name it) and the CLI (`verinoda` on PATH, outside the project) by itself; `/config`
overrides both (`root`, `cli`), turns the check after edits on (`check`) and the mascot's motion off (`motion`).

## What it does

| feature | how | default |
|---|---|---|
| Tools in front | `mcp__verinoda__analyze`, `project_query` and `run_tool` are placed in the model's tool list, not behind ToolSearch (a tool the model must look up first is not called: 0 of 286 study sessions with the tools deferred, 51 of 63 with a tool listed in front; the ToolSearch turn costs a model call of its own). Their descriptions stay the server's. | on |
| The call rule | While the Verinoda MCP server is connected (its tools are in the request), one paragraph in the system prompt (section `verinoda-live:rule`, about 630 characters): on a question that asks why something is the way it is, when or in which commit it changed, or what a change affects, the first tool call is `analyze` with the question, Grep, Read and git after it; its output is a lead, so confirm with one git or grep check before stating "no such change", "first added in" or why something changed; `statically_verified` and `primary_source_verified` claims are verified, `strong_inference` and below are not. A softer rule with a way out ("a question one grep answers needs no call") got no call in 39 of 39 headless sessions of the D186 re-run; this wording, with the reminder fix below and the server's matching description, got 6 of 6 in probes and 37 of 39 in the re-run, `analyze` first every time (D186, `benchmarks/results/claims-rerun-2026-10-13/`). The mod also takes the three pinned names out of the engine's reminder of tools behind ToolSearch, which is composed before the pins apply and said a direct call would fail. | on |
| Re-index after edits | Edit / Write / NotebookEdit inside `ROOT` mark the file; at the end of the main loop's turn one `verinoda update --fast` runs (subagent turns do not start one). A failed update keeps its files for `/verinoda-update`. Only in a project the person opened (the session's own folder), named in the settings, or trusted with `verinoda trust`: a `.verinoda` found in an ancestor they never opened runs nothing, the pane says so, and `/verinoda-update` names the command that allows it. | on |
| Graph state | After `--fast` the graph is rebuilt in the background; the status line says `text fresh · graph pending…` until `verinoda graph-state` reports no build holding the lock and no file changed since the latest snapshot, then `fresh ✓`. A graph left behind with no build coming (files changed outside Claude's edit tools) is named, and `/verinoda-update` takes it in. Edits made while the build runs wait for it and are indexed when it ends. | on |
| Check after edits (`/verinoda-check on\|off`, setting `check`) | After each Edit / Write of a Python, Java or Kotlin file inside `ROOT`, `verinoda check --diff` (falling back to the file itself without git) reads the changed lines; names on them that do not exist in the project or its environment are told to the model in one line with the edit's result (as a PostToolUse note), with the nearest real names. Nothing is said when nothing is absent. A cached check takes about 3 s, never more than 60 s, and never fails the edit. The pane shows the last check (`k` toggles). A choice made with `/verinoda-check` is kept and wins in a terminal; a scripted session (`claude -p`, the Agent SDK) takes the setting as given. | off |
| `/verinoda-improve [what to look at]` pane | A vague request ("make this better") becomes a list the person can recognise their wish in. The command asks Claude to look and **change nothing**; Claude hands the mod a ranked list through `improve_propose`; a second Turkish pane (`İyileştirme`) shows it in three groups (possible problems with `file:line` evidence, functional improvements, matters of taste) with nothing selected, the seven best ranked first and the rest folded. The person marks each item (`u` apply, `k` keep, `c` check first for a suspected problem), may add items of their own, and sends with `g`; only then does Claude work, on what was chosen, and report each outcome through `improve_report`. A suspicion is never drawn as a fact (`kanıtsız`, `tahmin`), an item without a decision is never read as rejected, and every change that was not on the list is reported. Nothing of it runs, and neither tool is listed to the model, before the command (or the `improveOffer` setting: one line in the system prompt that offers the list instead of guessing). A scripted session gets none of it. No Verinoda index is needed and nothing is stored. | command only |
| `/verinoda-panel` pane | In Turkish (technical nouns kept): the index state as glyph + words + colour with the one action that applies (`u`), the check after edits as a two-way control (`k`), and a purple Claude mascot with glasses in the room left over, animated like Claude Code's own (it blinks and shuffles its feet; while Verinoda works it reads, a glint sweeping its lenses; `hooks/mascot.tsx`, drawn by the surface as a `Client`, so frames repaint only its region; still on surfaces without `Client`) (hidden inline, below 24 columns or when the content needs the rows). | - |

## Nothing runs from the repository

A cloned repository can ship a `verinoda.exe` at its root, a `.venv/` with one inside, or a `.verinoda/` folder of its
own. The mod runs none of them (D186 §4.6):

- `verinoda` is resolved once at session start by walking `PATH` (with `PATHEXT` on Windows) and taking the first
  program found in a folder that is not inside the project, so an activated project `.venv` first on `PATH` is skipped;
  a `cli` setting that points into the project, or to a network share, is refused the same way. Without one outside
  the project nothing runs at all, not even `trust --list`: the status line says `verinoda not found on PATH outside
  the project · set cli`, the pane says it in Turkish, and `/verinoda-update` answers the same (a bare name handed to
  the child would be resolved through the same `PATH`, to the project's own program). The mod needs no python of its
  own: the graph's state comes from `verinoda graph-state --json`.
- Every run has the user's home folder as its working directory (a drive root without one), never the repository,
  because Windows searches a child's working directory before `PATH` and whether `$.process.run` does is unverified;
  `--repo` names the project.
- `update --fast`, `graph-state` and `check` run only where the person chose the index: the folder they opened, the
  one their settings name, or one `verinoda trust --list` knows (read once per session, through the CLI). A `.verinoda`
  in an ancestor they never opened is shown as `güvenilmiyor` and runs nothing.

`hooks/features.test.ts` puts a fake `verinoda.exe` in the project root and in its `.venv`, names both first on `PATH`,
and checks that every process the mod runs is the one outside the project, from the home folder; with no other on
`PATH` it checks that nothing runs, not even the trust list, and that the pane names the `cli` setting.

## What was measured, and what went (D186)

The 0.6 mod had an auto-context mode (`nudge`: an instruction to start with `verinoda analyze`; `search`: `verinoda
query` results attached to the prompt), a commit review after each git command that moved HEAD, assist features
(located files injected, coupled-file notes, `locate` and `coupled` tools, a gate on the first search), a session-start
warm-up of the checker, and the check after edits on by default. They are gone because the measurements gave no reason
to keep them:

- **nudge**: on 57 questions over corpora of 37-226 files (`benchmarks/results/agent-compare-2026-10-02/`) the same
  facts at 16 % fewer input tokens; on 51 questions over ten real repositories
  (`benchmarks/results/agent-compare-realworld-2026-10-02/`) the same facts at **1.14x** input tokens: the saving did
  not replicate. On a 27,078-file repository and on seL4 (`agent-compare-big-2026-10-02/`, `agent-compare-sel4-2026-10-02/`)
  the agent used Verinoda in 0 of 206 nudged sessions. In the false-claims study (D185) the nudge fired once per
  session, 875 characters, telling the model to run the CLI while the guide said to use the server.
- **search**: 5-6 facts fewer on the small corpora (207 against 212) at 1.29x output.
- **assist** (`inject`, `coupled`, `tool`, `prompt`, `gate`): development-set numbers only
  (`benchmarks/agent_compare/DESIGN_ASSIST.md`); the confirmatory run has no result file, and `gate` denied the
  model's own first search.
- **commit review**: a guard on every shell command that mentioned git, reading HEAD before and after; no study
  measured a gain.
- **check after edits**: on 30 coding tasks (`benchmarks/results/agent-compare-guard-2026-10-02/`, 60 real sessions)
  it fired 0 times in 65 edits; on SWE-bench Lite (D184) it found an absent name in 3 of 99 calls, none acted on, at
  about $0.009 per session. It works (a deliberate removed name is caught and the model told), so it stays, off.
- **the warm-up**: a `check --stdin` at every session start to build the checker's name index, for a check that
  rarely runs.

What replaces their delivery role is the tools in front and the call rule: in one headless session on the study's
fastapi copy the model called `analyze` at its first tool call, confirmed the lead with `git show` and cited the commit
that states the reason (546dc8b), where two sessions without the rule asserted the history gives none (D186 spec §3;
one session each, an observation, not a scored measure). What freshness itself is worth is measured in
`benchmarks/results/agent-compare-stale-2026-10-02/`: on projects under 300 files `analyze` refreshes a stale index by
itself; on the larger ones a stale index cost about a fifth more input tokens, and the fresh one the mod keeps brought
that back.

## Developing it

The live copy Claude Code hot-reloads is the session's dev-mods folder; this folder is its versioned source. Load it
from here in a terminal with `claude --plugin-dir <this repository>/claude-mods/verinoda-live`.

- `claude plugin validate <folder>`: what the module hooks and calls, and anything the engine would refuse.
- `claude plugin test <folder>`: `hooks/register.test.ts` (re-index and graph watcher), `hooks/features.test.ts` (the
  tools in front and the call rule, nothing run from the repository, the trust gate, the check after edits, the
  settings, the project, robustness, the pane on terminal and desktop), `hooks/check.test.ts` (the check after edits
  and its note), `hooks/improve.test.ts` (the improvement list: the proposed list and its first sight, decisions, the
  three prompts, reports, the wired command, tools and pane; `hooks/improve.ts` is its pure part and
  `hooks/improve-pane.tsx` its pane and hooks) and `hooks/mascot.test.ts`.
- Type-check: after the engine has loaded the mod once it writes `.claude-plugin/types/` and a `tsconfig.json`;
  then `tsc -p <folder>`. Both are generated and not kept here.

The 2026-10-02 version was reviewed by three independent lenses (API, state and failure paths, Windows and real-use
edge cases) with two skeptics per finding; the 13 upheld findings are fixed and covered by tests.

Note: the pane's command is `/verinoda-panel`, not `/verinoda`: the Verinoda agent skill (`~/.claude/skills/verinoda`,
installed by `verinoda install`) owns `/verinoda`, and a skill of that name takes the slash before a plugin command.

The pane was redesigned from a user-eyes evaluation (a first-time Turkish speaker, an all-day user, a terminal and
accessibility specialist), two mascot designs and one synthesized spec; the tests mount it on the terminal and
desktop surfaces, check every state's words, the hotkeys shown, and when the mascot appears.
