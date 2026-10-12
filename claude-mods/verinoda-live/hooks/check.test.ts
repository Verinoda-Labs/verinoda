import { describe, expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

import { checkNote, isCheckable } from './register'

const ROOT = 'C:/work/proj'
const START = { cwd: ROOT, surface: 'terminal', isInteractive: true } as never
const ON = { options: { check: true } }
const EDIT_PY = { tool: 'Edit', file_path: 'C:\\work\\proj\\pkg\\app.py', old_string: 'a', new_string: 'b' } as const
const WRITE_MD = { tool: 'Write', file_path: 'C:\\work\\proj\\README.md', content: '# x' } as const

// What `verinoda check --diff --json` prints: one absent name on the edited file, one on another file.
const site = (path: string, line: number, name: string, verdict = 'absent', nearest: string[] = []) => ({
  at: `${path}:${line}:5`, path, line, expr: `mod.${name}`, name, verdict,
  message: `not found in module mod in this project (mod.py)`,
  nearest: nearest.map(n => ({ name: n, kind: 'def', score: 0.9, at: 'mod.py:3' })),
})
const REPORT = {
  status: 'absent',
  summary: { sites: 9, absent: 2, mismatch: 0, unknown: 1, exists: 6, files: 2 },
  sites: [site('pkg/app.py', 12, 'timeoutMessage', 'absent', ['timeoutErrorMessage']), site('pkg/other.py', 4, 'gone')],
}
const CLEAN = { status: 'checked', summary: { sites: 4, absent: 0, mismatch: 0, unknown: 0, exists: 4, files: 1 }, sites: [] }

function world(on: On, opts: { diff?: { exitCode: number; stdout: string }; path?: { exitCode: number; stdout: string };
  rejects?: boolean } = {}) {
  const runs: { argv: string[]; stdin?: string }[] = []
  on('session.start', () => ({ cwd: ROOT }))
  on('session.cwd', () => ({ value: ROOT }))
  mock.store(on)
  mock.clock(on)
  on('fs.stat', () => ({ value: { isFile: false, isDirectory: true, size: 0, mtimeMs: 0 } }) as never)
  on('command.register', ($, e) => ({ value: { command: e.name } }) as never)
  on('ui.status', () => ({ value: undefined }))
  on('process.run', ($, e) => {
    runs.push({ argv: [...e.argv], stdin: e.init?.stdin })
    if (e.argv[1] === 'graph-state') return { value: { exitCode: 0, stdout: '{"locked": false, "behind": 0}', stderr: '' } } as never
    if (e.argv[1] === 'check') {
      if (opts.rejects) throw new Error('timed out')
      if (e.argv.includes('--diff')) return { value: { stderr: '', ...(opts.diff ?? { exitCode: 3, stdout: JSON.stringify(REPORT) }) } } as never
      return { value: { stderr: '', ...(opts.path ?? { exitCode: 0, stdout: JSON.stringify(CLEAN) }) } } as never
    }
    return { value: { exitCode: 0, stdout: '{}', stderr: '' } } as never
  })
  on('tool.call', () => ({ result: 'ok' }) as never)
  return { runs, checks: () => runs.filter(r => r.argv[1] === 'check') }
}

// What the pane says of the last check (the note itself rides the edit's result as `context`).
async function paneShows($: any, text: string): Promise<boolean> {
  const pane = await $.ui.mount({
    plugin: 'verinoda-live', surface: 'terminal', component: 'Pane', requestId: 'verinoda',
    props: { title: 'Verinoda', isFocused: true, bodyColumns: 80, placement: 'dock', scroll: { offset: 0, bodyRows: 40 } },
  })
  return (await pane.find({ text })) !== undefined
}

describe('check after edits: pure parts', () => {
  test('only Python, Java and Kotlin files are checked', () => {
    for (const f of ['a/b.py', 'x.PYI', 'src/Main.java', 'k/App.kt', 'build.gradle.kts']) expect(isCheckable(f)).toBe(true)
    for (const f of ['README.md', 'main.go', 'lib/index.js', 'a.py.orig', 'Cargo.toml']) expect(isCheckable(f)).toBe(false)
  })

  test("the note is one line: the edited file's absent names with their nearest real names, nothing else", () => {
    const note = checkNote(ROOT, `${ROOT}/pkg/app.py`, REPORT, 'verinoda')
    expect(note).toContain('pkg/app.py:12:5 mod.timeoutMessage')
    expect(note).toContain('nearest: timeoutErrorMessage')
    expect(note).not.toContain('other.py')
    expect(note?.startsWith('[Verinoda check]')).toBe(true)
    expect(note?.includes('\n')).toBe(false)
    expect(checkNote(ROOT, `${ROOT}/pkg/other.py`, CLEAN, 'verinoda')).toBeUndefined()
    expect(checkNote(ROOT, `${ROOT}/pkg/app.py`, { sites: [site('pkg/app.py', 3, 'x', 'unknown')] }, 'verinoda')).toBeUndefined()
  })

  test('a long report is cut to eight names and says how many more there are', () => {
    const many = { sites: Array.from({ length: 11 }, (_, i) => site('pkg/app.py', i + 1, `n${i}`, i % 2 ? 'mismatch' : 'absent')) }
    const note = checkNote(ROOT, `${ROOT}/pkg/app.py`, many, 'verinoda') ?? ''
    expect(note.match(/pkg\/app\.py:\d+:5 /g)?.length).toBe(8)
    expect(note).toContain('3 more')
  })
})

describe('check after edits', () => {
  test('an edit to a Python file is checked and what does not exist is reported', ON, async ($, on) => {
    const { checks } = world(on)
    await $.session.start(START)
    const r = await $.tool.call(EDIT_PY) as { context?: string[] }
    expect(checks().map(c => c.argv.slice(1))).toEqual([['check', '--diff', '--json', '--repo', ROOT]])
    expect(r.context?.length).toBe(1)
    expect(r.context?.[0]).toContain('pkg/app.py:12:5 mod.timeoutMessage')
    expect(await paneShows($, "Son kontrol: pkg/app.py · 1 isim bulunamadı, Claude'a söylendi")).toBe(true)
  })

  test('a clean check and a file in another language add nothing', ON, async ($, on) => {
    const { checks } = world(on, { diff: { exitCode: 0, stdout: JSON.stringify(CLEAN) } })
    await $.session.start(START)
    const r = await $.tool.call(EDIT_PY) as { context?: string[] }
    expect(r.context ?? []).toEqual([])
    await $.tool.call(WRITE_MD)
    expect(checks().length).toBe(1)
    expect(await paneShows($, 'Son kontrol: pkg/app.py · temiz')).toBe(true)
  })

  test('without git (the diff fails) the edited file itself is checked', ON, async ($, on) => {
    const { checks } = world(on, { diff: { exitCode: 2, stdout: '' }, path: { exitCode: 3, stdout: JSON.stringify(REPORT) } })
    await $.session.start(START)
    await $.tool.call(EDIT_PY)
    expect(checks().map(c => c.argv.slice(1, 3))).toEqual([['check', '--diff'], ['check', `${ROOT}/pkg/app.py`]])
    expect(await paneShows($, '1 isim bulunamadı')).toBe(true)
  })

  test('a check whose own step throws (no clock here) still leaves the edit as it was', ON, async ($, on) => {
    on('process.run', () => { throw new Error('not reached') })
    on('session.start', () => ({ cwd: ROOT }))
    on('session.cwd', () => ({ value: ROOT }))
    mock.store(on)
    on('fs.stat', () => ({ value: { isFile: false, isDirectory: true, size: 0, mtimeMs: 0 } }) as never)
    on('command.register', ($, e) => ({ value: { command: e.name } }) as never)
    on('ui.status', () => ({ value: undefined }))
    on('tool.call', () => ({ result: 'ok' }) as never)
    await $.session.start(START)
    const r = await $.tool.call(EDIT_PY) as { isError?: boolean; deny?: string }
    expect(r.isError ?? false).toBe(false)
    expect(r.deny).toBeUndefined()
  })

  test('a check that fails or times out never fails the edit', ON, async ($, on) => {
    world(on, { rejects: true })
    await $.session.start(START)
    const r = await $.tool.call(EDIT_PY) as { result?: unknown; isError?: boolean }
    expect(r.isError ?? false).toBe(false)
    expect(await paneShows($, 'Son kontrol çalışmadı: pkg/app.py (düzenleme yapıldı)')).toBe(true)
  })

  test('off unless asked: /verinoda-check on brings it, off stops it, and the choice is kept', async ($, on) => {
    const { checks } = world(on)
    await $.session.start(START)
    await $.tool.call(EDIT_PY)
    expect(checks().length).toBe(0)
    expect(await $.command.run({ command: 'verinoda-check', args: '' } as never)).toEqual(expect.objectContaining({ text: 'check after edits on' }))
    await $.tool.call(EDIT_PY)
    expect(checks().length).toBe(1)
    expect(await $.command.run({ command: 'verinoda-check', args: 'off' } as never)).toEqual(expect.objectContaining({ text: 'check after edits off' }))
    await $.tool.call(EDIT_PY)
    expect(checks().length).toBe(1)
    expect(await $.command.run({ command: 'verinoda-check', args: 'sometimes' } as never)).toEqual(expect.objectContaining({ text: 'usage: /verinoda-check [on|off]' }))
  })

  test('nothing is warmed at session start: no check runs before an edit', ON, async ($, on) => {
    const { runs } = world(on)
    await $.session.start(START)
    expect(runs.filter(r => r.argv[1] === 'check' || r.argv.includes('--stdin')).length).toBe(0)
  })
})
