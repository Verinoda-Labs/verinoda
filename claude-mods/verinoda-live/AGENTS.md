# Working on verinoda-live (for coding agents)

verinoda-live is a Claude Code mod: a plugin of function hooks that runs inside the session beside the agent. This note is
what you need before changing it. The improvement checklist pane (D175) is described in `IMPROVE-PANE.md` beside this file; its step 2 is still to build.

## What a mod is

- `.claude-plugin/plugin.json` is the manifest (name, version, `userConfig` settings, `"types": "./types/index.d.ts"`).
- `hooks/hooks.json` names one module, `hooks/register.tsx`. It exports `register(on, options)`; `options` holds the
  `userConfig` values. `on(event, matcher?, hook)` adds a hook, and every hook is `($, e, next)`: `$` is the engine interface, `e` the
  event's input (plain, frozen), `next(e)` runs the plugins beneath and then the engine. A hook that returns without calling
  it answers alone; `next({ ...e, x })` rewrites what the rest sees.
- The module has **no DOM and no Node**: files, processes, the clock, the store, the prompt and the screen are all reached
  through `$`. A module that holds `import()` does not load. Files of the mod are imported with `import` declarations.
- JSX compiles against the global `h`. Elements are not globals: take them from the surface's table in the hook,
  `const { Box, Text, Button, Input } = $.ui.resolve(e)`.

## The API reference: read it, do not guess

- **`.claude-plugin/types/claude-code/index.d.ts`** (about 15,000 lines) declares every event's input and result, every call
  on `$` with a doc comment and an example, and every element's props. It is the authority. Grep it for the name at hand:
  `export type ButtonProps`, `export type InputProps`, `export type PaneOpenArgs`, `export type PromptComposeInput`,
  `export type ToolSpec`, `export type CommandRunResult`, `Pane: {`, `'tool.call'`.
- Claude Code writes that folder each time it loads the mod, and git ignores it. If it is missing, start
  `claude --plugin-dir claude-mods/verinoda-live` once in a terminal (or ask the person to). Written against Claude Code
  2.1.289; the API is early access and moves between releases, so where this note and the declaration file disagree, the
  file wins.
- `claude-mods/.local-reference/plugin-authoring/`, when it exists, is a local copy of Claude Code's own authoring guide
  (its reference) and of three small complete examples (a pane, a band, a tool-call hook). It is not in the repository.

## Layout

| file | holds |
|---|---|
| `hooks/register.tsx` | the wiring: every `on(...)`, the session state (atoms), the module state (`live`, `cfg`), the tools-in-front hook and the call rule, where Verinoda runs from, the trust gate, the pane's drawing |
| `hooks/improve.ts`, `hooks/improve-pane.tsx` | the improvement list: its pure part (`improve.test.ts` tests it and its wiring) and its pane and hooks; `register.tsx` calls a few lines of it |
| `hooks/mascot.tsx` | a `Client` module: the animated mascot |
| `types/index.d.ts` | the contract: `PluginState['verinoda-live']` (every `$.state` key) and `McpToolInputs` (the tools' arguments) |
| `hooks/*.test.ts` | the tests, run by `claude plugin test` |

A new feature follows `improve`: its logic that needs no `$` goes in a file of its own with its own tests, and `register.tsx`
gets as little as wires it in. `register.tsx` is about 760 lines (1,270 before D186 cut the auto-context, assist and review
features); do not grow it by a feature's whole body.

## Checks: all three pass before you say it is done

Run from the repository root.

```
claude plugin validate claude-mods/verinoda-live        # ends with "Validation passed"
claude plugin test claude-mods/verinoda-live            # 85 pass, 0 fail in 5 files (125 in 6 before D186)
npx --yes -p typescript tsc -p claude-mods/verinoda-live --noEmit   # exit 0 and no output (without --noEmit it writes .js files beside the sources)
```

`validate` also lists what the module hooks, calls, reads and writes: read that list after a change, it is the quickest
sign that the engine sees what you meant. It holds every `$.state` key the module names to the contract in
`types/index.d.ts`, and every `$.env.get` name (see fact 15).

## How the tests work

A test gets the engine's `$` and an `on` whose hooks sit **beneath** the plugin and stand for the engine and the machine:
what they answer is what the plugin's `$` calls get. The existing files build that world in one function (`world(on)`), then
drive the plugin through `$`:

```ts
import { describe, expect, mock, test } from 'claude-code/testing'

test('the pane draws the setting and a press changes it', async ($, on) => {
  const clock = mock.clock(on)          // $.clock under the test's control
  mock.store(on, { check: true })       // $.store with what an earlier session chose (mock.store(on): empty)
  world(on)                             // fs, env, process.run, prompt.compose, tool.call ... answered here
  await $.session.start({ cwd: 'C:/work/proj', surface: 'terminal', isInteractive: true } as never)
  await clock.settle()                  // the background work session.start began has answered
  const pane = await $.ui.mount({
    plugin: 'verinoda-live', surface: 'terminal', component: 'Pane', requestId: 'verinoda',
    props: { title: 'Verinoda', isFocused: true, bodyColumns: 48, placement: 'dock', scroll: { offset: 0, bodyRows: 40 } } as never,
  })
  expect(await pane.find({ text: /✓ Index güncel/ })).toBeDefined()
  expect((await pane.find({ key: 'check-off' }))?.props.label).toBe('Kapalı')
  await $.ui.press({ plugin: 'verinoda-live', key: 'check-off' })          // a Button, by its key
  expect((await pane.find({ key: 'check-off' }))?.props.label).toBe('● Kapalı')
})
```

An `Input` a feature draws is typed into with `await $.ui.input({ plugin: 'verinoda-live', key: '<its key>', text: 'hello' })`
(Enter with that text; `kind: 'change'` for an edit without Enter).

`$.command.run({ command: 'verinoda-panel', args: '' } as never)` runs a command;
`$.tool.call({ tool: 'mcp__verinoda-live__improve_propose', ... } as never)` calls a tool as the model would, and what it
resolves to carries the `context` a hook added; `$.prompt.compose({ model, promptModel, surfaces, tools, outputStyle, traits })`
renders the system prompt (the plugin's `prompt.compose` hook reads `e.tools`, so a test names the tools the request offers);
`$.tool.describe({ tool, description, isDeferred: true })` asks where a tool is listed. Read `hooks/features.test.ts` (the pane
on terminal and desktop, the trust gate, nothing run from the repository) and `hooks/improve.test.ts` (tools) before writing a
test. The test body's own `$` drives the plugin (session, tool, command, prompt, ui); only the plugin's `$` inside a hook has
`fs`, `env` and `process`, so a test answers those with `on('fs.stat', ...)`, `mock.env(on, {...})` and `on('process.run', ...)`
and never calls them itself.

## Conventions of this mod

- **The pane's text is Turkish; a command's output and everything the model reads is English.**
- Every state has a glyph and words; colour only reinforces them. A control that would do nothing is not drawn.
- What a drawing reads lives in `$.state`: `const x = atom({ plugin: 'verinoda-live', key: 'x' } as const, initial)`,
  `read($, x)` while drawing, `update($, x, fn)` from a handler; the write redraws the readers. Declare the key in
  `types/index.d.ts`. A module variable is lost on a reload; `$.state` (the session's) and `$.store` (across sessions) stay.
  A reload (a saved file, a changed setting) runs `register` and the `session.start` hook again.
- A setting starts from `userConfig` (`options`), and a choice the person made with a command is kept in `$.store` and wins,
  **in interactive sessions only** (`loadSettings($, isInteractive)`).
- Work that must not hold up a hook is started with `background(promise)`.
- Every element that can be pressed, typed into or found by a test has a `key`.
- Comments say why (and what was measured), not what the next line does.
- **Nothing the mod runs comes from the opened repository** (D186 §4.6): the CLI is `cfg.cli`, resolved once from `PATH`
  outside the root (`resolveTools`), every process goes through `runCli` with the user's home as its working directory and
  `--repo` naming the project, and `update`, `graph-state` and `check` run only when `live.isAllowed` (the root is the
  session's folder, named in the settings, or on `verinoda trust --list`). A new process the mod runs keeps all three.
  When `PATH` names no program outside the root, `cfg.cli` is empty and nothing runs (`nocli`: `runCli` rejects,
  `live.isAllowed` is false, the trust list is not read); never fall back to a bare name, which the child resolves
  through the same `PATH`. A test world that expects a run names a `PATH` outside the project (`mock.env`).

## Facts about the host that cost time to find

1. **A plugin's tool, and an MCP server's, is deferred behind ToolSearch unless a hook says otherwise**, and a tool the
   model must look up first is not called. `tool.describe` answers `{ description, isDeferred: false }` for the mod's own
   tools (the improvement list's, in `improve-pane.tsx`) and for the Verinoda server's three core tools
   (`MCP_CORE_TOOLS` in `register.tsx`, named as the model names them, `mcp__verinoda__<tool>`); add a new tool to the
   matcher that fits. The hook pins only tools present at session start; a tool that appears after the first model call
   stays deferred, because moving it into the tools array invalidates the cached prefix (about 16k tokens).
2. **A plugin tool's result must be a plain string** (`{ result: 'text' }`). Any other shape fails the engine's check.
3. **`$.store` is one file per plugin, shared by every session that loads the mod and rewritten by each at its end.** A
   choice stored in one terminal once reached scripted sessions that never asked for it. A session with nobody at the
   keyboard (`session.start`'s `e.isInteractive === false`: `claude -p`, the SDK) reads no stored choice.
4. `$.http.fetch` has a short time limit of its own; an answer that takes tens of seconds is dropped. Slow work goes through
   `$.process.run(argv, { cwd, timeoutMs })` (30 s by default, ten minutes at most).
5. A hook has 10 s of its own time per dispatch; time spent inside a `$` call or `next(e)` does not count, except
   `$.clock.sleep`, which does.
6. **A pane opened because the person asked (the hook of a command they typed or a prompt they entered, a Button, Input or
   Select they worked) is placed at any width; one opened unasked (a timer, `session.start`, a queued prompt, `focus`) is
   placed only from 144 terminal columns** and otherwise waits undrawn (`$.ui.open` resolves `{ isPlaced: false }`). The
   floor is 110 columns for a pane id the person opened before and did not close by hand, and opening an id that is already
   open only retitles it and answers `isPlaced: true`. A model's tool call is in neither list; treat it as unasked and handle
   both answers. Open a pane from the command the person typed.
7. `$.prompt.submit({ text })` queues a prompt that starts a turn of its own once the session is idle; it is never folded
   into a running turn. The call resolves when that turn starts or when the prompt was queued behind a running one, so its
   resolution does not say the turn began: `turn.start` (`{ text, turnId }`) does, and `turn.complete` carries the same
   `turnId`. **Do not await it inside a `command.run` hook or a press handler** (the turn may not be able to start until the
   hook returns; this was not tried): start it with `background(...)`.
8. A plugin's prompt is shown to the model as "the plugin sent a message" unless it is submitted with `asUser: true`, which
   the model reads bare, as the person's own words (the transcript still names the plugin, and an `@file` mention in a
   plugin's prompt is not expanded). The improvement list's prompts are submitted so. The mod hooks `prompt.submit` no more
   (the auto-context and the gate went with D186), so nothing is attached to any prompt; the call rule is a `prompt.compose`
   section instead, present while the request's tools name the Verinoda server's.
9. `/verinoda` belongs to the Verinoda agent skill, which takes the slash before a plugin command: the mod's commands are
   `verinoda-<word>`.
10. Surfaces differ: `mobile` has no `Input` and no `Select`; narrow on `e.surface` and draw without them there. A tree that
    does not validate is not drawn at all, and only the debug log says why (`claude --debug`).
11. On the terminal a focused pane gives Tab to walk its elements, Enter to press, the arrows to scroll (the engine owns the
    scroll), and a Button's `hotkey` (one digit or one lowercase letter). The person gives it the keyboard with ctrl+x tab or a
    click; `$.ui.open({ focus: true })` is a request the surface may refuse.

12. **`$` is never followed across an import**, and **a second matcher-less hook on an event the module already hooks is
    refused** (`claude plugin validate` says so). A feature in a file of its own registers hooks only for events nothing else
    hooks (or with a matcher of its own); for `session.start`, `prompt.compose` and `turn.complete` the few lines that need `$`
    stay in `register.tsx`, and an atom is read where it is declared (declare it in each file that reads it).
13. **`$.prompt.submit` from a `command.run` hook is refused by the host** ("it would wait on the turn this hook is holding;
    submit from a later event (turn.complete)"); started in the background it never reached the prompt hook in the test
    engine. From a pressed button it is delivered. The improvement list's review prompt goes out when the command's own turn
    ends.
14. In the test engine a mounted pane redraws what a tool call or a turn event changed when it is next read (`find`,
    `drawn`): read before you press. The engine raises no `turn.complete` for a command; a test raises it.
15. **`$.env.get` takes a literal name** (`$.env.get('PATH')`, never `$.env.get(name)`): the host lists the variables a
    module reads and refuses the module at load otherwise, in `validate` and in every test.
16. `$.process.run` has no `which`: a program is found by walking `$.env.get('PATH')` with `$.fs.stat` (`fromPath` in
    `register.tsx`), which runs nothing; `where` would itself be a program found by the child's own search.

## What you cannot check, and must say so

Nothing here can click a pane in a real terminal, and a scripted session (`claude -p`) has no person. The tests mount the
pane and press its keys, which shows the logic; how it feels in a terminal (focus, scrolling a long list, wrapping at 40
columns) only a person sees. List what you could not check in your final message instead of calling it done.
