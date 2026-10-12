import { describe, expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

import { CALL_RULE, isServerConnected, RULE_SECTION } from './register'

const ROOT = 'C:/work/verinoda'
const HOME = 'C:/Users/dev'
const CLI = `${HOME}/.local/bin/verinoda.exe` // Verinoda as PATH finds it, outside the project
const START = { cwd: ROOT, surface: 'terminal', isInteractive: true } as never
const compose = (tools: string[]) =>
  ({ model: 'm', promptModel: 'm', surfaces: ['terminal'], tools, outputStyle: null, traits: [] }) as never
const run = (command: string, args = '') => ({ command, args }) as never
const edit = (file: string) => ({ tool: 'Edit', file_path: file, old_string: 'a', new_string: 'b' }) as never
const TURN = { turnId: 't1', answer: '', durationMs: 1, isAborted: false, reason: 'end_turn' } as never
const QUESTION = 'Where is the graph rebuilt after update --fast?'
const PANE = { title: 'Verinoda', isFocused: true, bodyColumns: 48, placement: 'dock', scroll: { offset: 0, bodyRows: 40 } }

// What `verinoda check --diff --json` prints: one absent name on the edited file.
const ABSENT = JSON.stringify({ status: 'absent', sites: [{ at: 'a.py:3:5', path: 'a.py', line: 3, expr: 'mod.gone', name: 'gone',
  verdict: 'absent', message: 'not found in module mod in this project (mod.py)', nearest: [{ name: 'going', kind: 'def' }] }] })
const CLEAN = '{"status": "checked", "sites": []}'

type Trusted = { path: string; subfolders?: boolean }
type Run = { argv: string[]; cwd: string | undefined }

// The world beneath the plugin: a project with an index, the user's home with Verinoda installed under it (what PATH
// names, spelled as Windows spells it), the trust list `verinoda trust --list` answers, and a record of every run.
function world(on: On, opts: {
  cwd?: string; existing?: string[]; path?: string; trusted?: Trusted[] | 'fails'; update?: { exitCode: number }
  graph?: { locked: boolean; behind: number }[]; checks?: { exitCode: number; stdout: string }[]
} = {}) {
  const runs: Run[] = []
  const registered: string[] = []
  const opened: string[] = []
  const statuses: (string | undefined)[] = []
  let isStartChecked = false
  let graphCalls = 0
  let checkCalls = 0
  on('session.start', () => ({ cwd: opts.cwd ?? ROOT }))
  on('session.cwd', () => ({ value: opts.cwd ?? ROOT }))
  mock.env(on, { USERPROFILE: 'C:\\Users\\dev', PATH: opts.path ?? 'C:\\Windows\\System32;C:\\Users\\dev\\.local\\bin', PATHEXT: '.EXE;.CMD' })
  // the index and the installed CLI exist, with what `existing` adds; nothing else does
  const existing = new Set([`${ROOT}/.verinoda`, CLI, ...(opts.existing ?? [])].map(p => p.toLowerCase()))
  on('fs.stat', ($, e) => (existing.has(e.path.replace(/\\/g, '/').toLowerCase())
    ? { value: { kind: 'file', size: 0, mtimeMs: 0, isLink: false } } : { deny: 'ENOENT' }) as never)
  on('command.register', ($, e) => {
    registered.push(e.name)
    return { value: { command: e.name } } as never
  })
  on('ui.open', ($, e) => {
    opened.push(e.id)
    return { value: { id: e.id } } as never
  })
  on('ui.status', ($, e) => {
    statuses.push(e.text)
    return { value: undefined }
  })
  on('process.run', ($, e) => {
    runs.push({ argv: [...e.argv], cwd: e.init?.cwd })
    const cmd = e.argv[1]
    if (cmd === 'trust') {
      if (opts.trusted === 'fails') return { value: { exitCode: 1, stdout: '', stderr: 'boom' } } as never
      const rows = (opts.trusted ?? []).map(t => ({ path: t.path, subfolders: t.subfolders === true, at: '2026-10-12T00:00:00Z' }))
      return { value: { exitCode: 0, stdout: JSON.stringify({ trust_file: `${HOME}/AppData/Roaming/verinoda/trust.json`, trusted: rows }), stderr: '' } } as never
    }
    if (cmd === 'graph-state') {
      if (!isStartChecked) {
        isStartChecked = true // the session-start look at the graph finds it fresh; `graph` answers the watcher
        return { value: { exitCode: 0, stdout: '{"locked": false, "behind": 0, "state": "fresh"}', stderr: '' } } as never
      }
      const g = opts.graph ?? [{ locked: false, behind: 0 }]
      return { value: { exitCode: 0, stdout: JSON.stringify(g[Math.min(graphCalls++, g.length - 1)]), stderr: '' } } as never
    }
    if (cmd === 'update') return { value: { exitCode: opts.update?.exitCode ?? 0, stdout: '{}', stderr: 'locked' } } as never
    if (cmd === 'check') {
      const answers = opts.checks ?? [{ exitCode: 0, stdout: CLEAN }]
      return { value: { stderr: '', ...answers[Math.min(checkCalls++, answers.length - 1)] } } as never
    }
    return { value: { exitCode: 0, stdout: '{}', stderr: '' } } as never
  })
  on('tool.call', () => ({ result: 'ok' }) as never)
  on('prompt.submit', ($, e) => ({ text: e.text, context: e.context }))
  on('prompt.compose', () => ({ sections: [{ id: 'intro', text: 'You are an agent.', scope: 'shared' }] }) as never)
  on('turn.complete', () => ({ text: '' }) as never)
  const of = (cmd: string) => runs.filter(r => r.argv[1] === cmd)
  return { runs, registered, opened, statuses, of }
}

// The text of a drawing, its elements' strings joined (a Client's drawing is read with `drawn({ in: key })`).
const flat = (n: unknown): string => (typeof n === 'string' ? n
  : ((n as { children?: unknown[] }).children ?? []).map(flat).join(''))

const mount = ($: any, surface = 'terminal', props: Record<string, unknown> = PANE) =>
  $.ui.mount({ plugin: 'verinoda-live', surface, component: 'Pane', requestId: 'verinoda', props })

describe('the MCP server tools in front, and the call rule', () => {
  // the agent studies found a tool the model must first look up (deferred behind ToolSearch) is not called: 0 of 286
  // sessions with the tools deferred, 51 of 63 with `locate` listed in front; and the ToolSearch turn itself costs a
  // model call (D186). The server's core tools are placed in the prompt's list; their descriptions are the server's.
  test('analyze, project_query and run_tool are listed, not deferred, with the engine description kept', async ($, on) => {
    mock.clock(on)
    mock.store(on)
    world(on)
    await $.session.start(START)
    for (const tool of ['mcp__verinoda__analyze', 'mcp__verinoda__project_query', 'mcp__verinoda__run_tool']) {
      const d = await $.tool.describe({ tool, description: 'engine text', isDeferred: true } as never) as { isDeferred?: boolean; description: string }
      expect(d.isDeferred).toBe(false)
      expect(d.description).toBe('engine text')
    }
  })

  // listing alone did not make the model call the tool (one session: Grep, Read, Read, Bash); with the rule it called
  // analyze first and confirmed the lead with git (§3 of the D186 spec)
  test('the call rule is a prompt section only when the Verinoda MCP server is connected', async ($, on) => {
    mock.clock(on)
    mock.store(on)
    world(on)
    await $.session.start(START)
    const out = await $.prompt.compose(compose(['Read', 'Grep', 'mcp__verinoda__analyze', 'mcp__verinoda__run_tool']))
    expect(out.sections.map(s => s.id)).toEqual(['intro', RULE_SECTION])
    const rule = out.sections.find(s => s.id === RULE_SECTION)
    expect(rule?.scope).toBe('session')
    expect(rule?.text).toBe(CALL_RULE)
    for (const words of ['mcp__verinoda__analyze', 'primary_source_verified', 'one grep', 'lead, not the answer']) expect(rule?.text).toContain(words)
    expect(CALL_RULE.length).toBeLessThan(600) // about 400 chars: the rule is priced in the cost model

    const without = await $.prompt.compose(compose(['Read', 'Grep', 'mcp__other__search']))
    expect(without.sections.map(s => s.id)).toEqual(['intro'])
    expect(isServerConnected(undefined)).toBe(false)
    expect(isServerConnected(['mcp__verinoda__project_query'])).toBe(true)
  })

  test('the rule needs the server, not an index: a session outside any project gets it too', async ($, on) => {
    mock.clock(on)
    mock.store(on)
    world(on, { cwd: 'C:/work/other' })
    await $.session.start(START)
    expect((await $.prompt.compose(compose(['mcp__verinoda__analyze']))).sections.map(s => s.id)).toEqual(['intro', RULE_SECTION])
  })
})

describe('nothing is run from the repository', () => {
  // Windows searches a child's working directory before PATH, and whether $.process.run does is unverified (D186 §4.6):
  // Verinoda is resolved from PATH to an absolute path outside the project once, and every run has the user's home as
  // its working directory, the project named with --repo.
  test('a verinoda.exe at the root or in its .venv is not used, even when PATH names them first', async ($, on) => {
    const clock = mock.clock(on)
    mock.store(on)
    const { runs, of } = world(on, {
      // an activated project .venv puts its Scripts folder first on PATH; the root itself ships a verinoda.exe too
      path: 'C:\\work\\verinoda\\.venv\\Scripts;C:\\work\\verinoda;C:\\Users\\dev\\.local\\bin',
      existing: [`${ROOT}/verinoda.exe`, `${ROOT}/.venv/Scripts/verinoda.exe`, `${ROOT}/.venv/Scripts/python.exe`],
    })
    await $.session.start(START)
    await clock.settle()
    await $.tool.call(edit(`${ROOT}/a.py`))
    await $.turn.complete(TURN)
    await clock.settle()
    expect(of('graph-state').length).toBeGreaterThan(0)
    expect(of('update').length).toBe(1)
    for (const r of runs) {
      expect(r.argv[0]).toBe(CLI)
      expect(r.cwd).toBe(HOME)
      expect(r.argv.some(a => a.toLowerCase().startsWith(`${ROOT.toLowerCase()}/`))).toBe(false)
    }
  })

  test('a cli setting that points into the project is refused like a found one', { options: { cli: 'C:/work/verinoda/.venv/Scripts/verinoda.exe' } }, async ($, on) => {
    const clock = mock.clock(on)
    mock.store(on)
    const { runs } = world(on, { existing: [`${ROOT}/.venv/Scripts/verinoda.exe`] })
    await $.session.start(START)
    await clock.settle()
    expect(runs.length).toBeGreaterThan(0)
    for (const r of runs) expect(r.argv[0]).toBe(CLI)
  })

  test('without Verinoda on PATH outside the project the bare name is run, still from the home folder', async ($, on) => {
    const clock = mock.clock(on)
    mock.store(on)
    const { runs } = world(on, { path: 'C:\\work\\verinoda\\.venv\\Scripts', existing: [`${ROOT}/.venv/Scripts/verinoda.exe`] })
    await $.session.start(START)
    await clock.settle()
    expect(runs.length).toBeGreaterThan(0)
    for (const r of runs) {
      expect(r.argv[0]).toBe('verinoda')
      expect(r.cwd).toBe(HOME)
    }
  })
})

describe('freshness only where the person allows it', () => {
  // a hostile repository's .verinoda folder must not make the mod run anything (D186 §4.6): the index is used when the
  // person opened its folder, or trusted it with `verinoda trust`; a .verinoda found in an ancestor they did not open is not.
  test('a .verinoda folder in an untrusted ancestor does not start update or the graph probe', async ($, on) => {
    const clock = mock.clock(on)
    mock.store(on)
    const { of, statuses } = world(on, { cwd: `${ROOT}/pkg/sub`, trusted: [] })
    await $.session.start(START)
    await clock.settle()
    await $.tool.call(edit(`${ROOT}/pkg/a.py`))
    await $.turn.complete(TURN)
    await clock.settle()
    expect(of('update').length).toBe(0)
    expect(of('graph-state').length).toBe(0)
    expect(of('trust').map(r => r.argv.slice(1))).toEqual([['trust', '--list', '--json']])
    expect(of('trust')[0]?.cwd).toBe(HOME)
    expect(statuses.at(-1)).toContain('not trusted')
    const res = await $.command.run(run('verinoda-update'))
    expect(res).toEqual(expect.objectContaining({ text: expect.stringContaining(`verinoda trust ${ROOT}`) }))
    expect(of('update').length).toBe(0)
    const pane = await mount($)
    expect(await pane.find({ text: /güvenilmiyor/ })).toBeDefined()
    expect(await pane.find({ text: new RegExp(`verinoda trust ${ROOT}`) })).toBeDefined()
  })

  test('a trust list that cannot be read counts as not trusted', async ($, on) => {
    const clock = mock.clock(on)
    mock.store(on)
    const { of } = world(on, { cwd: `${ROOT}/pkg`, trusted: 'fails' })
    await $.session.start(START)
    await clock.settle()
    expect(of('graph-state').length).toBe(0)
  })

  test('an ancestor the person trusted is used, and the list is asked once per session', async ($, on) => {
    const clock = mock.clock(on)
    mock.store(on)
    // recorded as the CLI spells it: real path, backslashes
    const { of } = world(on, { cwd: `${ROOT}/pkg`, trusted: [{ path: 'C:\\work\\verinoda' }] })
    await $.session.start(START)
    await clock.settle()
    expect(of('graph-state').length).toBe(1)
    expect(of('graph-state')[0]?.argv.slice(1)).toEqual(['graph-state', '--repo', ROOT, '--json'])
    await $.tool.call(edit(`${ROOT}/pkg/a.py`))
    await $.turn.complete(TURN)
    await clock.settle()
    expect(of('update').length).toBe(1)
    expect(of('trust').length).toBe(1)
  })

  test('a folder trusted with its subfolders covers the project', async ($, on) => {
    const clock = mock.clock(on)
    mock.store(on)
    const { of } = world(on, { cwd: `${ROOT}/pkg`, trusted: [{ path: 'C:\\work', subfolders: true }] })
    await $.session.start(START)
    await clock.settle()
    expect(of('graph-state').length).toBe(1)
  })

  test('a session started in the project asks no trust list', async ($, on) => {
    const clock = mock.clock(on)
    mock.store(on)
    const { of } = world(on)
    await $.session.start(START)
    await clock.settle()
    expect(of('trust').length).toBe(0)
    expect(of('graph-state').length).toBe(1)
  })
})

describe('check after edits', () => {
  // 0 notes in 65 edits of the guard study, 3 absent names in 99 calls on SWE-bench, none acted on (D186 §4.4): off
  // unless the setting or /verinoda-check turns it on, and then a hook that says nothing when nothing is absent
  test('off by default: an edit runs no check', async ($, on) => {
    mock.clock(on)
    mock.store(on)
    const { of } = world(on)
    await $.session.start(START)
    const r = await $.tool.call(edit(`${ROOT}/a.py`)) as { context?: string[] }
    expect(of('check').length).toBe(0)
    expect(r.context ?? []).toEqual([])
    const pane = await mount($)
    expect((await pane.find({ key: 'check-off' }))?.props.label).toBe('● Kapalı')
  })

  test('check on: an edit runs verinoda check --diff; a clean report adds nothing, an absent name adds one line naming it',
    { options: { check: true } }, async ($, on) => {
      mock.clock(on)
      mock.store(on)
      const { of } = world(on, { checks: [{ exitCode: 0, stdout: CLEAN }, { exitCode: 3, stdout: ABSENT }] })
      await $.session.start(START)
      const clean = await $.tool.call(edit(`${ROOT}/a.py`)) as { context?: string[] }
      expect(of('check').map(c => c.argv.slice(1))).toEqual([['check', '--diff', '--json', '--repo', ROOT]])
      expect(clean.context ?? []).toEqual([])
      const absent = await $.tool.call(edit(`${ROOT}/a.py`)) as { context?: string[] }
      expect(absent.context?.length).toBe(1)
      const line = absent.context?.[0] ?? ''
      expect(line.startsWith('[Verinoda check]')).toBe(true)
      expect(line).toContain('mod.gone')
      expect(line).toContain('nearest: going')
      expect(line.includes('\n')).toBe(false)
      expect(await $.tool.call({ tool: 'Write', file_path: `${ROOT}/README.md`, content: '# x' } as never)).toEqual({ result: 'ok' })
      expect(of('check').length).toBe(2) // Markdown is not checked
    })
})

describe('the settings', () => {
  test('the settings no longer know auto, assist or guard', { options: { auto: 'nudge', assist: 'full', guard: true } }, async ($, on) => {
    const clock = mock.clock(on)
    mock.store(on, { auto: 'search', assist: 'strict', guard: true })
    const { registered, runs, of } = world(on)
    await $.session.start(START)
    await clock.settle()
    for (const gone of ['verinoda-auto', 'verinoda-assist', 'verinoda-guard', 'verinoda']) expect(registered).not.toContain(gone)
    for (const kept of ['verinoda-update', 'verinoda-check', 'verinoda-panel', 'verinoda-improve']) expect(registered).toContain(kept)
    // a code question gets no context and starts no search; a git command in a shell reads nothing
    const res = await $.prompt.submit({ text: QUESTION, wait: false, origin: { kind: 'composer' } } as never)
    expect(res.context ?? []).toEqual([])
    await $.tool.call({ tool: 'Bash', command: 'git commit -m "x"' } as never)
    await clock.settle()
    for (const cmd of ['query', 'locate', 'coupled', 'review']) expect(of(cmd).length).toBe(0)
    expect(runs.some(r => r.argv[0] === 'git')).toBe(false)
    const pane = await mount($)
    for (const key of ['auto-off', 'auto-nudge', 'auto-search', 'guard-on', 'guard-off', 'review-more']) expect(await pane.find({ key })).toBeUndefined()
    expect(await pane.find({ text: /Otomatik bağlam|Commit incelemesi|Son commit/ })).toBeUndefined()
    expect((await pane.find({ key: 'check-off' }))?.props.label).toBe('● Kapalı')
    expect(await pane.find({ text: /^k kontrol$/ })).toBeDefined() // the footer: only the keys that exist
  })

  test('/verinoda-check on is kept for the next session; a stored choice wins over the setting in a terminal', async ($, on) => {
    mock.clock(on)
    mock.store(on, { check: true })
    const { of } = world(on)
    await $.session.start(START)
    await $.tool.call(edit(`${ROOT}/a.py`))
    expect(of('check').length).toBe(1)
    expect(await $.command.run(run('verinoda-check', 'off'))).toEqual(expect.objectContaining({ text: 'check after edits off' }))
    await $.tool.call(edit(`${ROOT}/a.py`))
    expect(of('check').length).toBe(1)
  })

  test('a scripted session takes the settings as given, not a stored choice', async ($, on) => {
    mock.clock(on)
    mock.store(on, { check: true })
    const { of } = world(on)
    await $.session.start({ cwd: ROOT, surface: null, isInteractive: false } as never)
    await $.tool.call(edit(`${ROOT}/a.py`))
    expect(of('check').length).toBe(0)
  })
})

describe('the project', () => {
  test('a home folder with an index is not taken for the project unless the settings name it', async ($, on) => {
    mock.clock(on)
    mock.store(on)
    const { runs } = world(on, { cwd: HOME, existing: [`${HOME}/.verinoda`] })
    await $.session.start(START)
    await $.tool.call(edit(`${HOME}/notes.py`))
    expect(await $.command.run(run('verinoda-update')))
      .toEqual(expect.objectContaining({ text: expect.stringContaining('no .verinoda index') }))
    expect(runs.length).toBe(0)
  })

  test('a session started outside the configured project uses it, and runs nothing from it', { options: { root: ROOT } }, async ($, on) => {
    const clock = mock.clock(on)
    mock.store(on)
    const { of, runs } = world(on, { cwd: 'C:/work/other-project' })
    await $.session.start(START)
    await clock.settle()
    expect(of('trust').length).toBe(0) // named in the settings: the person's own choice
    expect(of('graph-state')[0]?.argv).toEqual([CLI, 'graph-state', '--repo', ROOT, '--json'])
    for (const r of runs) expect(r.cwd).toBe(HOME)
  })
})

describe('re-index robustness', () => {
  test('a failed update keeps the files, and /verinoda-update tries again', async ($, on) => {
    mock.clock(on)
    mock.store(on)
    const { of } = world(on, { update: { exitCode: 1 } })
    await $.session.start(START)
    await $.tool.call(edit(`${ROOT}/a.py`))
    const first = await $.command.run(run('verinoda-update'))
    expect(first).toEqual(expect.objectContaining({ text: expect.stringContaining('update failed (exit 1)') }))
    const second = await $.command.run(run('verinoda-update'))
    expect(second).toEqual(expect.objectContaining({ text: expect.stringContaining('update failed (exit 1)') }))
    expect(of('update').length).toBe(2)
  })

  test('edits made while the graph build runs wait for it, then are indexed without being asked', async ($, on) => {
    const clock = mock.clock(on)
    mock.store(on)
    // the build holds the lock for two polls, then the graph has caught up
    const { of } = world(on, { graph: [{ locked: true, behind: 1 }, { locked: true, behind: 1 }, { locked: false, behind: 0 }] })
    await $.session.start(START)
    await $.tool.call(edit(`${ROOT}/a.py`))
    await $.command.run(run('verinoda-update'))
    await $.tool.call(edit(`${ROOT}/b.py`))
    const waiting = await $.command.run(run('verinoda-update'))
    expect(waiting).toEqual(expect.objectContaining({ text: 'waiting for the graph build; 1 file will be indexed when it ends' }))
    expect(of('update').length).toBe(1)
    for (let i = 0; i < 3; i++) await clock.advance(1_000)
    await clock.settle()
    expect(of('update').length).toBe(2)
  })

  test('a subagent turn does not start a re-index; the main loop turn does', async ($, on) => {
    mock.clock(on)
    mock.store(on)
    const { of } = world(on)
    await $.session.start(START)
    await $.tool.call(edit(`${ROOT}/a.py`))
    await $.turn.complete({ turnId: 't1', agentId: 'sub-1', answer: '', durationMs: 1, isAborted: false, reason: 'end_turn' } as never)
    expect(of('update').length).toBe(0)
    await $.turn.complete({ turnId: 't2', answer: '', durationMs: 1, isAborted: false, reason: 'end_turn' } as never)
    expect(of('update').length).toBe(1)
  })
})

describe('pane', () => {
  test('/verinoda-panel opens it, and no command is named plain verinoda (a skill of that name wins the slash)', async ($, on) => {
    mock.clock(on)
    mock.store(on)
    const { registered, opened } = world(on)
    await $.session.start(START)
    expect(registered).toContain('verinoda-panel')
    expect(registered).not.toContain('verinoda')
    const res = await $.command.run(run('verinoda-panel'))
    expect(res).toEqual(expect.objectContaining({ text: 'Verinoda pane opened.' }))
    expect(opened).toEqual(['verinoda'])
  })

  for (const surface of ['terminal', 'desktop'] as const) {
    test(`draws the state and the check setting on ${surface}, in Turkish, and a press changes the setting`, async ($, on) => {
      const clock = mock.clock(on)
      mock.store(on)
      const { of } = world(on)
      await $.session.start(START)
      await clock.settle()
      const pane = await mount($, surface)
      expect(await pane.find({ text: /✓ Index güncel/ })).toBeDefined()
      expect((await pane.find({ key: 'check-off' }))?.props.label).toBe('● Kapalı')
      expect((await pane.find({ key: 'check-on' }))?.props.label).toBe('Açık')
      expect(await pane.find({ text: /var olmayan isimler Claude'a söylenir/ })).toBeDefined()
      expect(await pane.find({ key: 'update' })).toBeUndefined() // nothing to update: no button that does nothing
      await $.ui.press({ plugin: 'verinoda-live', key: 'check-on' })
      expect((await pane.find({ key: 'check-on' }))?.props.label).toBe('● Açık')
      await $.tool.call(edit(`${ROOT}/a.py`))
      expect(of('check').length).toBe(1)
      expect(await pane.find({ text: /Son kontrol: a\.py · temiz/ })).toBeDefined()
    })
  }

  test('the mascot sits in the room left over, and only there', async ($, on) => {
    const clock = mock.clock(on)
    mock.store(on)
    world(on)
    await $.session.start(START)
    await clock.settle() // the session-start look at the graph answers
    // one drawing at a time: mount at a size, read it, unmount
    const hasMascot = async (bodyRows: number, bodyColumns = 48, placement = 'dock') => {
      const pane = await mount($, 'terminal', { ...PANE, isFocused: false, bodyColumns, placement, scroll: { offset: 0, bodyRows } })
      const isDrawn = (await pane.find({ key: 'mascot-client' })) !== undefined
      const found = {
        mascot: (await pane.find({ key: 'mascot' })) !== undefined,
        // the caption is the animated Client's: read from its own drawing
        caption: isDrawn && flat(await pane.drawn({ in: 'mascot-client' })).includes('Her şey güncel'),
        hint: (await pane.find({ text: /ctrl\+x tab/ })) !== undefined,
      }
      await pane.unmount()
      return found
    }
    expect(await hasMascot(40)).toEqual({ mascot: true, caption: true, hint: true }) // not focused: how to get the keys
    expect((await hasMascot(14)).mascot).toBe(false) // too short: hidden, never cropped
    expect((await hasMascot(40, 22)).mascot).toBe(false) // too narrow
    expect((await hasMascot(40, 96, 'inline')).mascot).toBe(false) // inline: never
  })

  test('a failed update shows what failed and a retry, with the mascot saying so', async ($, on) => {
    const clock = mock.clock(on)
    mock.store(on)
    world(on, { update: { exitCode: 1 } })
    await $.session.start(START)
    await clock.settle()
    await $.tool.call(edit(`${ROOT}/a.py`))
    await $.command.run(run('verinoda-update'))
    const pane = await mount($)
    expect(await pane.find({ text: /✗ Güncelleme başarısız · 1 dosya bekletiliyor/ })).toBeDefined()
    expect(await pane.find({ text: /çıkış 1: locked/ })).toBeDefined()
    expect((await pane.find({ key: 'update' }))?.props.label).toBe('Tekrar dene')
    expect(flat(await pane.drawn({ in: 'mascot-client' }))).toContain('Bir şey ters gitti')
    expect(await pane.find({ text: /^u güncelle · k kontrol$/ })).toBeDefined()
  })
})
