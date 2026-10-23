import { describe, expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

import { CARD_CHARS, CARD_FILES, CARDS_HEAD, cardInstructions, touchedFiles } from './cards'

const ROOT = 'C:/work/mod'
const HOME = 'C:/Users/dev'
const CLI = `${HOME}/.local/bin/verinoda.exe` // Verinoda as PATH finds it, outside the project
const START = { cwd: ROOT, surface: 'terminal', isInteractive: true } as never
const CARDS = 'src/Kale.java (20 lines): Builds the castle. | defines Kale: build\nart/wing.png: image 640x480'

type Use = { tool_use_id?: string; tool: string; input: Record<string, unknown> }
let ids = 0
const use = (tool: string, input: Record<string, unknown>): Use => ({ tool_use_id: `u${ids++}`, tool, input })
const said = (...uses: Use[]) => ({ role: 'assistant', text: '', toolUses: uses })

describe('the files a conversation touched (pure)', () => {
  test('edited files come first, then the read ones, each newest first, each once', () => {
    const msgs = [
      said(use('Read', { file_path: `${ROOT}/a.py` }), use('Read', { file_path: `${ROOT}/b.py` })),
      said(use('Edit', { file_path: `${ROOT}/b.py`, old_string: 'x', new_string: 'y' })),
      said(use('Read', { file_path: `${ROOT}/c.py` }), use('Write', { file_path: `${ROOT}/d.py`, content: 'z' })),
      said(use('Read', { file_path: `${ROOT}/a.py` })),
    ]
    expect(touchedFiles(msgs, ROOT)).toEqual(['d.py', 'b.py', 'a.py', 'c.py'])
  })

  test('only paths under the root, never under .verinoda or climbing out; backslashes and case as Windows spells them', () => {
    const msgs = [said(
      use('Read', { file_path: 'C:\\Work\\Mod\\src\\Kale.java' }),
      use('Read', { file_path: 'C:/work/other/x.py' }),
      use('Read', { file_path: `${ROOT}/.verinoda/index/graph.json` }),
      use('Read', { file_path: `${ROOT}/../secret.txt` }),
      use('Read', { file_path: `${ROOT}` }),
      use('NotebookEdit', { notebook_path: `${ROOT}/nb/a.ipynb`, new_source: '' }),
      use('Grep', { pattern: 'x', path: `${ROOT}/src` }),
      use('Read', { file_path: 42 }),
    )]
    expect(touchedFiles(msgs, ROOT)).toEqual(['nb/a.ipynb', 'src/Kale.java'])
    expect(touchedFiles(msgs, 'C:\\work\\mod\\')).toEqual(['nb/a.ipynb', 'src/Kale.java'])
  })

  test(`at most ${CARD_FILES} files`, () => {
    const msgs = [said(...Array.from({ length: 60 }, (_, i) => use('Read', { file_path: `${ROOT}/f${i}.py` })))]
    const got = touchedFiles(msgs, ROOT)
    expect(got.length).toBe(CARD_FILES)
    expect(got[0]).toBe('f59.py') // the newest first
  })

  test('the cards follow what the summarizer was told already', () => {
    expect(cardInstructions('keep the plan', `${CARDS}\n`)).toBe(`keep the plan\n\n${CARDS_HEAD}\n${CARDS}`)
    expect(cardInstructions(undefined, CARDS)).toBe(`${CARDS_HEAD}\n${CARDS}`)
    expect(cardInstructions('  ', CARDS)).toBe(`${CARDS_HEAD}\n${CARDS}`)
  })
})

type Run = { argv: string[]; cwd: string | undefined }

// The world beneath the plugin: a project with an index, Verinoda installed in the user's home (what PATH names), a
// `verinoda card` that answers `card`, and the engine's compaction, which records what it was handed.
function world(on: On, opts: { card?: { exitCode: number; stdout: string } | 'throws'; path?: string; cwd?: string } = {}) {
  const runs: Run[] = []
  const compactions: { instructions?: string; messages?: unknown[] }[] = []
  const cwd = opts.cwd ?? ROOT
  on('session.start', () => ({ cwd }))
  on('session.cwd', () => ({ value: cwd }))
  mock.env(on, { USERPROFILE: 'C:\\Users\\dev', PATH: opts.path ?? 'C:\\Windows\\System32;C:\\Users\\dev\\.local\\bin', PATHEXT: '.EXE;.CMD' })
  const existing = new Set([`${ROOT}/.verinoda`, CLI].map(p => p.toLowerCase()))
  on('fs.stat', ($, e) => (existing.has(e.path.replace(/\\/g, '/').toLowerCase())
    ? { value: { kind: 'file', size: 0, mtimeMs: 0, isLink: false } } : { deny: 'ENOENT' }) as never)
  on('command.register', ($, e) => ({ value: { command: e.name } }) as never)
  on('ui.status', () => ({ value: undefined }))
  on('process.run', ($, e) => {
    runs.push({ argv: [...e.argv], cwd: e.init?.cwd })
    const cmd = e.argv[1]
    if (cmd === 'card') {
      if (opts.card === 'throws') throw new Error('timed out')
      return { value: { stderr: '', ...(opts.card ?? { exitCode: 0, stdout: `${CARDS}\n` }) } } as never
    }
    if (cmd === 'trust') return { value: { exitCode: 0, stdout: JSON.stringify({ trusted: [] }), stderr: '' } } as never
    if (cmd === 'graph-state') return { value: { exitCode: 0, stdout: JSON.stringify({ locked: false, behind: 0, state: 'fresh' }), stderr: '' } } as never
    return { value: { exitCode: 0, stdout: '{}', stderr: '' } } as never
  })
  on('session.compact', ($, e) => {
    compactions.push({ instructions: e.instructions, messages: e.messages as unknown[] })
    return { messages: [{ role: 'user', text: 'the summary', toolUses: [] }] } as never
  })
  return { runs, compactions, cards: () => runs.filter(r => r.argv[1] === 'card') }
}

const CONVERSATION = [
  said(use('Read', { file_path: `${ROOT}/art/wing.png` })),
  said(use('Edit', { file_path: `${ROOT}/src/Kale.java`, old_string: 'a', new_string: 'b' })),
]
// the test engine's own compaction carries no transcript: the test hands it the conversation, as core does
const compact = ($: any, args: Record<string, unknown> = {}) =>
  $.session.compact({ instructions: 'keep the plan', messages: CONVERSATION, ...args } as never)

describe('the cards reach the compaction', () => {
  test('verinoda card runs from the home folder with --repo and the touched files; the summarizer gets them after the focus', async ($, on) => {
    const clock = mock.clock(on)
    mock.store(on)
    const w = world(on)
    await $.session.start(START)
    await clock.settle()
    await compact($)
    expect(w.cards()).toEqual([{ argv: [CLI, 'card', '--repo', ROOT, '--max-chars', String(CARD_CHARS), '--', 'src/Kale.java', 'art/wing.png'], cwd: HOME }])
    expect(w.compactions.length).toBe(1)
    expect(w.compactions[0]?.instructions).toBe(`keep the plan\n\n${CARDS_HEAD}\n${CARDS}`)
    expect(w.compactions[0]?.messages).toEqual(CONVERSATION) // the conversation itself is handed on as it was
  })

  for (const [name, card] of [['fails', { exitCode: 2, stdout: '' }], ['throws (a time-out, no card command)', 'throws'],
    ['prints nothing', { exitCode: 0, stdout: '  \n' }]] as const) {
    test(`a card run that ${name} leaves the compaction as it was`, async ($, on) => {
      const clock = mock.clock(on)
      mock.store(on)
      const w = world(on, { card: card as { exitCode: number; stdout: string } | 'throws' })
      await $.session.start(START)
      await clock.settle()
      await compact($)
      expect(w.cards().length).toBe(1)
      expect(w.compactions).toEqual([{ instructions: 'keep the plan', messages: CONVERSATION }])
    })
  }

  test("nothing runs for a conversation that touched no file, nor for a subagent's compaction", async ($, on) => {
    const clock = mock.clock(on)
    mock.store(on)
    const w = world(on)
    await $.session.start(START)
    await clock.settle()
    await compact($, { messages: [said(use('Bash', { command: 'ls' }))] })
    await compact($, { agentId: 'agent-1' })
    expect(w.cards().length).toBe(0)
    expect(w.compactions.map(c => c.instructions)).toEqual(['keep the plan', 'keep the plan'])
  })

  test('the setting off leaves the compaction to Claude Code', { options: { compactCards: false } }, async ($, on) => {
    const clock = mock.clock(on)
    mock.store(on)
    const w = world(on)
    await $.session.start(START)
    await clock.settle()
    await compact($)
    expect(w.cards().length).toBe(0)
    expect(w.compactions[0]?.instructions).toBe('keep the plan')
  })

  test('an index in an untrusted ancestor runs no card', async ($, on) => {
    const clock = mock.clock(on)
    mock.store(on)
    const w = world(on, { cwd: `${ROOT}/sub` }) // the session opened below the index, the folder never trusted
    await $.session.start({ cwd: `${ROOT}/sub`, surface: 'terminal', isInteractive: true } as never)
    await clock.settle()
    await compact($)
    expect(w.cards().length).toBe(0)
    expect(w.compactions[0]?.instructions).toBe('keep the plan')
  })

  test('no Verinoda on PATH outside the project: no card, the compaction as it was', async ($, on) => {
    const clock = mock.clock(on)
    mock.store(on)
    const w = world(on, { path: 'C:\\Windows\\System32' })
    await $.session.start(START)
    await clock.settle()
    await compact($)
    expect(w.cards().length).toBe(0)
    expect(w.compactions[0]?.instructions).toBe('keep the plan')
  })
})
