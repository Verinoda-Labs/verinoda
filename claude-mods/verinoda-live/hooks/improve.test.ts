import { describe, expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'
import type { Engine } from 'claude-code/testing'

import type { ImproveItem, ImproveState } from '../types'
import {
  addOwn, applyReport, canCheck, countsLine, decide, groupViews, initialImprove, listItems, markSent, proposeList, reportPrompt,
  reviewPrompt, selectionPrompt, visibleIds, unfold, toggleOpen,
} from './improve'

const ROOT = 'C:/work/proj'
const START = { cwd: ROOT, surface: 'terminal', isInteractive: true } as never
const PROPOSE = 'mcp__verinoda-live__improve_propose'
const REPORT = 'mcp__verinoda-live__improve_report'
const PANE = 'verinoda-improve'
const LOCATE_JSON = { text: 'verinoda locate: 1 file\nlikely\n  src/a.c:1-9 f', files: [{ path: 'src/a.c', tier: 'likely', why: 'matches: f' }] }

const it = (id: string, group: string, extra: Record<string, unknown> = {}) =>
  ({ id, group, title: `Title ${id}`, observation: `obs ${id}`, why: `why ${id}`, change: `change ${id}`, ...extra })
const proposed = (items: unknown[], subject = 'src/a.ts') => ({ subject, items })
const ok = (p: ReturnType<typeof proposeList>): ImproveState => {
  if ('error' in p) throw new Error(p.error)
  return p.state
}
const list = (items: unknown[]) => ok(proposeList(initialImprove(), proposed(items), ''))
const many = (n: number, group = 'problem') => Array.from({ length: n }, (_, i) => it(`i${i + 1}`, group, { evidence: ['a.ts:1'] }))
const byId = (s: ImproveState, id: string): ImproveItem => s.items.find(i => i.id === id) as ImproveItem

describe('improve: a proposed list', () => {
  test('is stored in the order given, texts trimmed and cut, every decision none; the subject falls back', () => {
    const s = ok(proposeList(initialImprove(), proposed([
      it('i1', 'problem', { title: `  ${'x'.repeat(200)}  `, why: 'y'.repeat(700), evidence: ['f.ts:1', 7, '', ' g.ts:2 ', ...Array(8).fill('z'.repeat(200))] }),
      it('i2', 'taste', { seen: true, cost: '  small  ' }),
    ], '  src/a.ts  '), ''))
    expect(s.items.map(i => i.id)).toEqual(['i1', 'i2'])
    expect(s.items.every(i => i.decision === 'none' && i.outcome === null && !i.verified)).toBe(true)
    expect(byId(s, 'i1').title.length).toBe(120)
    expect(byId(s, 'i1').title.endsWith('…')).toBe(true)
    expect(byId(s, 'i1').why.length).toBe(600)
    expect(byId(s, 'i1').evidence.length).toBe(6)
    expect(byId(s, 'i1').evidence.slice(0, 2)).toEqual(['f.ts:1', 'g.ts:2'])
    expect(byId(s, 'i1').evidence.every(e => e.length <= 160)).toBe(true)
    expect(byId(s, 'i2').cost).toBe('small')
    expect(byId(s, 'i2').seen).toBe(true)
    expect(s.subject).toBe('src/a.ts')
    expect(s.phase).toBe('choosing')
    expect(ok(proposeList(initialImprove(), { subject: '  ', items: [it('i1', 'problem')] }, 'the parser')).subject).toBe('the parser')
    expect(ok(proposeList(initialImprove(), { subject: 3, items: [it('i1', 'problem')] }, '')).subject).toBe('bu konuşma')
  })

  test('each invalid input is refused with a message that names the item, and nothing is stored', () => {
    const before = initialImprove()
    const bad: [unknown, RegExp][] = [
      [undefined, /items must be a list of 1 to 30/],
      [[], /items must be a list of 1 to 30/],
      [many(31), /items must be a list of 1 to 30/],
      [[it('i1', 'problem'), it('i1', 'taste')], /id i1 is used twice/],
      [[it('bad id!', 'problem')], /item 1 has an id/],
      [[it('', 'problem')], /item 1 has an id/],
      [[it('u1', 'problem')], /item 1 has an id/],
      [[it('i1', 'wish')], /item i1 has a group/],
      [[it('i1', 'problem', { title: ' ' })], /item i1 needs a non-empty title/],
      [[it('i1', 'problem', { change: undefined })], /item i1 needs a non-empty change/],
      [['text'], /item 1 is not an object/],
    ]
    for (const [items, message] of bad) {
      const p = proposeList(before, { subject: 's', items }, '')
      expect('error' in p ? p.error : '').toMatch(message)
      expect('error' in p ? p.error : '').toMatch(/^verinoda improve: .*; nothing was shown$/)
    }
    expect(before).toEqual(initialImprove())
  })

  test('optional fields of the wrong type are treated as absent, not refused', () => {
    const s = list([it('i1', 'problem', { cost: 5, evidence: 'a.ts:1', seen: 'yes' }), it('i2', 'problem', { evidence: [1, null, 'a.ts:2'] })])
    expect(byId(s, 'i1')).toMatchObject({ cost: '', evidence: [], seen: false })
    expect(byId(s, 'i2').evidence).toEqual(['a.ts:2'])
  })
})

describe('improve: the first sight', () => {
  test('shows the seven best ranked and counts only what is folded; a decision, a verified item and the open item stay shown', () => {
    let s = list([...many(8, 'problem'), ...many(4, 'taste').map(i => ({ ...i, id: `t${i.id}` }))])
    expect(groupViews(s).map(g => [g.group, g.rows.length, g.more])).toEqual([['problem', 7, 1], ['taste', 0, 4]])
    s = decide(s, 'ti4', 'apply')
    s = toggleOpen(s, 'i8')
    const views = groupViews(s)
    expect(views.find(g => g.group === 'problem')).toMatchObject({ more: 0 })
    expect(views.find(g => g.group === 'taste')?.rows.map(r => r.id)).toEqual(['ti4'])
    expect(views.find(g => g.group === 'taste')?.more).toBe(3)
    const verified = { ...s, open: null, items: s.items.map(i => (i.id === 'i8' ? { ...i, verified: true } : i)) }
    expect(visibleIds(verified).has('i8')).toBe(true)
    const all = unfold(s, 'taste')
    expect(groupViews(all).find(g => g.group === 'taste')).toMatchObject({ rows: expect.any(Array), more: 0 })
    expect(groupViews(all).find(g => g.group === 'taste')?.rows.length).toBe(4)
  })

  test('the row suffixes and marks say what is a guess and what is decided', () => {
    let s = list([it('i1', 'problem'), it('i2', 'problem', { evidence: ['a.ts:1'] }), it('i3', 'taste'), it('i4', 'taste', { seen: true }), it('i5', 'improvement')])
    s = decide(s, 'i2', 'apply')
    s = decide(s, 'i4', 'keep')
    s = decide(s, 'i1', 'check')
    const rows = Object.fromEntries(groupViews(s).flatMap(g => g.rows).map(r => [r.id, `${r.mark}${r.suffix}`]))
    expect(rows).toEqual({ i1: '[?] (kanıtsız)', i2: '[✓]', i3: '[ ] (tahmin)', i4: '[–]', i5: '[ ]' })
    expect(countsLine(s)).toBe('5 madde · 1 uygula · 1 kontrol · 1 kalsın')
    expect(countsLine(initialImprove())).toBe('')
  })
})

describe('improve: decisions', () => {
  test('apply, keep and check set a decision; the same again clears it; check only for an unverified problem', () => {
    let s = list([it('i1', 'problem'), it('i2', 'improvement'), it('i3', 'taste')])
    for (const d of ['apply', 'keep', 'check'] as const) {
      s = decide(s, 'i1', d)
      expect(byId(s, 'i1').decision).toBe(d)
      s = decide(s, 'i1', d)
      expect(byId(s, 'i1').decision).toBe('none')
    }
    expect(decide(s, 'i2', 'check')).toBe(s)
    expect(decide(s, 'i3', 'check')).toBe(s)
    const verified = { ...s, items: s.items.map(i => (i.id === 'i1' ? { ...i, verified: true } : i)) }
    expect(canCheck(byId(verified, 'i1'))).toBe(false)
    expect(decide(verified, 'i1', 'check')).toBe(verified)
    expect(decide(s, 'nope', 'apply')).toBe(s)
  })
})

describe('improve: what is sent', () => {
  test('the selection lists apply, check and keep under their headings, leaves an empty section out and never names an undecided item', () => {
    let s = list([it('i1', 'problem'), it('i2', 'improvement'), it('i3', 'taste'), it('i4', 'improvement'), it('i5', 'problem')])
    s = decide(s, 'i1', 'check')
    s = decide(s, 'i2', 'apply')
    s = decide(s, 'i3', 'keep')
    s = addOwn(s, 'rename the button')
    const text = selectionPrompt(s)
    expect(text.split('\n')[0]).toBe('My decisions on the improvement list (src/a.ts):')
    expect(text).toContain('Apply these:\n- [i2] Title i2: change i2\n- [u1] rename the button (my own item)\n')
    expect(text).toContain('Check these first (investigate only; change nothing for them):\n- [i1] Title i1\n')
    expect(text).toContain('Keep these as they are (do not change them, also not as a side effect):\n- [i3] Title i3\n')
    expect(text).not.toContain('i4')
    expect(text).not.toContain('i5')
    expect(text).toContain('mcp__verinoda-live__improve_report')
    const onlyApply = selectionPrompt(decide(list([it('i1', 'problem')]), 'i1', 'apply'))
    expect(onlyApply).not.toContain('Check these first')
    expect(onlyApply).not.toContain('Keep these')
  })

  test('after a first send an item that already has an outcome is not named again', () => {
    let s = decide(decide(list([it('i1', 'problem'), it('i2', 'improvement')]), 'i1', 'apply'), 'i2', 'apply')
    s = markSent(s)
    expect(s.phase).toBe('sent')
    expect(s.expect).toBe('selection')
    const r = applyReport(s, { outcomes: [{ id: 'i1', status: 'applied', note: 'done' }] })
    s = 'state' in r ? r.state : s
    s = decide(s, 'i2', 'keep') // waiting: not changed
    const text = selectionPrompt(s)
    expect(text).not.toContain('[i1]')
    expect(text).not.toContain('[i2]')
    expect(reportPrompt(['i1', 'i2'])).toBe('Report the outcome of the items I sent that you have not reported yet (i1, i2) with mcp__verinoda-live__improve_report.\nChange nothing else.')
    expect(reviewPrompt('').split('\n')[1]).toBe('What to look at: what we have been working on in this conversation. If that is not clear, ask me one question first.')
    expect(reviewPrompt(' the parser ').split('\n')[1]).toBe('What to look at: the parser')
  })
})

describe('improve: a report', () => {
  const sent = () => {
    let s = list([it('i1', 'problem'), it('i2', 'improvement'), it('i3', 'problem'), it('i4', 'taste')])
    s = decide(decide(decide(s, 'i1', 'apply'), 'i2', 'apply'), 'i3', 'check')
    return markSent(s)
  }
  const reported = (s: ImproveState, input: Record<string, unknown>) => {
    const r = applyReport(s, input)
    if ('error' in r) throw new Error(r.error)
    return r
  }

  test('each status lands on its item; a confirmed item is back in the list, verified, undecided, with the new change', () => {
    const r = reported(sent(), {
      outcomes: [
        { id: 'i1', status: 'partial', note: 'half', evidence: ['a.ts:3', 4] },
        { id: 'i2', status: 'applied', note: 'done', change: 'ignored' },
        { id: 'i3', status: 'confirmed', note: 'real', change: 'new fix', evidence: ['b.ts:9'] },
      ],
      extra_changes: ['touched c.ts', 3, ''],
    })
    expect(r.answer).toBe('Recorded: 3 outcomes.')
    const s = r.state
    expect(byId(s, 'i1').outcome).toEqual({ status: 'partial', note: 'half', evidence: ['a.ts:3'] })
    expect(byId(s, 'i2').outcome?.status).toBe('applied')
    expect(byId(s, 'i2').change).toBe('change i2')
    expect(byId(s, 'i3')).toMatchObject({ verified: true, checked: 'real', outcome: null, decision: 'none', sentAs: null, change: 'new fix', evidence: ['b.ts:9'] })
    expect(s.extra).toEqual(['touched c.ts'])
    expect(s.phase).toBe('choosing')
    expect(listItems(s).map(i => i.id)).toEqual(['i3', 'i4'])
    const again = applyReport(s, { outcomes: [{ id: 'i3', status: 'applied', note: 'x' }] })
    expect('error' in again ? again.error : '').toBe('verinoda improve: no item i3 is waiting for an outcome')
  })

  test('a partial report says what is still waiting and keeps the phase', () => {
    const r = reported(sent(), { outcomes: [{ id: 'i1', status: 'failed', note: 'could not' }] })
    expect(r.answer).toBe('Recorded: 1 outcomes. Still waiting for: i2, i3.')
    expect(r.state.phase).toBe('sent')
  })

  test('a call with anything invalid records nothing and says which', () => {
    const s = sent()
    const refused: [Record<string, unknown>, string][] = [
      [{}, 'verinoda improve: outcomes must list at least one item; nothing was recorded'],
      [{ outcomes: [] }, 'verinoda improve: outcomes must list at least one item; nothing was recorded'],
      [{ outcomes: [{ id: 'i1', status: 'applied', note: 'a' }, { id: 'i1', status: 'failed', note: 'b' }] }, 'verinoda improve: item i1 is reported twice'],
      [{ outcomes: [{ id: 'zz', status: 'applied', note: 'a' }] }, 'verinoda improve: no item zz is waiting for an outcome'],
      [{ outcomes: [{ id: 'i4', status: 'applied', note: 'a' }] }, 'verinoda improve: no item i4 is waiting for an outcome'],
      [{ outcomes: [{ id: 'i1', status: 'done', note: 'a' }] }, 'verinoda improve: item i1 was sent to apply; its outcome is one of applied, partial or failed'],
      [{ outcomes: [{ id: 'i1', status: 'confirmed', note: 'a' }] }, 'verinoda improve: item i1 was sent to apply; its outcome is one of applied, partial or failed'],
      [{ outcomes: [{ id: 'i3', status: 'applied', note: 'a' }] }, 'verinoda improve: item i3 was sent to check; its outcome is one of confirmed or not_confirmed'],
      [{ outcomes: [{ id: 'i1', status: 'applied', note: '  ' }] }, 'verinoda improve: item i1 needs a note the user can read'],
      [{ outcomes: [{ id: 'i2', status: 'applied', note: 'ok' }, { id: 'i1', status: 'applied', note: '' }] }, 'verinoda improve: item i1 needs a note the user can read'],
    ]
    for (const [input, message] of refused) {
      const r = applyReport(s, input)
      expect('error' in r ? r.error : 'accepted').toBe(message)
    }
    expect(s.items.filter(i => i.outcome?.status === 'waiting').length).toBe(3)
  })
})

// ---- wired through the engine -------------------------------------------------------------------------------------

type Opts = { placed?: boolean; drop?: boolean; reject?: boolean; dropAfter?: number }

// The world beneath the plugin: an indexed project, a CLI whose locate answers, and a record of what was shown, registered
// and submitted. Its ui.open answers `{ isPlaced }` (the older worlds answer none).
function world(on: On, opts: Opts = {}) {
  const registered: string[] = []
  const commands: string[] = []
  const opened: { id: string; title?: string; rows?: number; focus?: true }[] = []
  const submitted: { text: string; origin?: { kind: string; name?: string; asUser?: true }; context?: readonly string[] }[] = []
  on('session.start', () => ({ cwd: ROOT }))
  on('session.cwd', () => ({ value: ROOT }))
  on('fs.stat', () => ({ value: { isFile: false, isDirectory: true, size: 0, mtimeMs: 0 } }) as never)
  on('command.register', ($, e) => {
    commands.push(e.name)
    return { value: { command: e.name } } as never
  })
  on('ui.status', () => ({ value: undefined }))
  on('ui.open', ($, e) => {
    opened.push({ id: e.id, title: e.title, rows: e.rows, focus: e.focus })
    return { value: opts.placed === false ? { isPlaced: false, reason: 'narrow' } : { isPlaced: true } } as never
  })
  on('tool.register', ($, e) => {
    registered.push(e.name)
    return { value: { tool: `mcp__verinoda-live__${e.name}` } } as never
  })
  on('process.run', ($, e) => {
    if (e.argv[1] === 'check') return { value: { exitCode: 0, stdout: '{"sites": []}', stderr: '' } } as never
    if (e.argv[1] === '-c') return { value: { exitCode: 0, stdout: '{"locked": false, "behind": 0}', stderr: '' } } as never
    if (e.argv[1] === 'locate') return { value: { exitCode: 0, stdout: JSON.stringify(LOCATE_JSON), stderr: '' } } as never
    return { value: { exitCode: 0, stdout: '{}', stderr: '' } } as never
  })
  on('tool.call', () => ({ result: 'ok' }) as never)
  on('prompt.submit', ($, e) => {
    submitted.push({ text: e.text, origin: e.origin as never, context: e.context })
    if (opts.reject === true) throw new Error('queue refused')
    if (opts.drop === true || (opts.dropAfter !== undefined && submitted.length > opts.dropAfter)) return { drop: 'blocked' } as never
    return { text: e.text, context: e.context }
  })
  on('prompt.compose', () => ({ sections: [{ id: 'intro', text: 'You are an agent.', scope: 'shared' }] }) as never)
  on('turn.start', ($, e) => ({ turnId: e.turnId }))
  on('turn.complete', () => ({ text: '' }) as never)
  on('session.end', ($, e) => ({ sessionId: e.sessionId }))
  return { registered, commands, opened, submitted }
}

const cmd = (args = '') => ({ command: 'verinoda-improve', args, origin: { kind: 'composer' } }) as never
const call = (tool: string, input: Record<string, unknown>) => ({ tool, ...input }) as never
const propose = (items: unknown[], subject = 'src/a.ts') => call(PROPOSE, proposed(items, subject))
const report = (outcomes: unknown[], extra?: unknown[]) => call(REPORT, { outcomes, extra_changes: extra })
const text = async (r: unknown) => String(((await r) as { result?: unknown; text?: unknown }).result ?? ((await r) as { text?: unknown }).text)
const flat = (n: unknown): string => (typeof n === 'string' ? n : ((n as { children?: unknown[] }).children ?? []).map(flat).join(''))
const COMPOSE = { model: 'm', promptModel: 'm', surfaces: ['terminal'], tools: [], outputStyle: null, traits: [] } as never

type Pane = { find: (q: Record<string, unknown>) => Promise<{ props: Record<string, unknown> } | undefined>; drawn: (q?: Record<string, unknown>) => Promise<unknown>; unmount: () => Promise<void> }
async function mountPane($: { ui: { mount: (a: never) => Promise<unknown> } }, props: Record<string, unknown> = {}, surface = 'terminal') {
  return (await $.ui.mount({
    plugin: 'verinoda-live', surface, component: 'Pane', requestId: PANE,
    props: { title: 'İyileştirme', isFocused: true, bodyColumns: 48, placement: 'dock', scroll: { offset: 0, bodyRows: 40 }, ...props },
  } as never)) as Pane
}
// a press (or a command) may leave work running, the submit of a prompt: settle the clock before reading what it did
let clock: { settle: () => Promise<void> }
const press = async ($: { ui: { press: (a: never) => Promise<unknown> } }, key: string) => {
  await $.ui.press({ plugin: 'verinoda-live', key } as never)
  await clock.settle()
}
// A command runs inside a turn of its own; the review prompt goes out when that turn ends (the host refuses a submit from the hook).
let turns = 0
const run = async ($: Engine, args = ''): Promise<string> => {
  const r = await text($.command.run(cmd(args)))
  await $.turn.complete(DONE(`t-command-${++turns}`))
  await clock.settle()
  return r
}
const label = async (pane: Pane, key: string) => String((await pane.find({ key }))?.props.label ?? '')
const typeInto = ($: { ui: { input: (a: never) => Promise<unknown> } }, key: string, t: string, kind?: string) =>
  $.ui.input({ plugin: 'verinoda-live', key, text: t, ...(kind === undefined ? {} : { kind }) } as never)
const MIX = [
  it('i1', 'problem'), it('i2', 'problem', { evidence: ['a.ts:4'] }), it('i3', 'improvement'), it('i4', 'taste'), it('i5', 'taste', { seen: true }),
]
const TURN = (turnId: string, t: string) => ({ text: t, turnId }) as never
const DONE = (turnId: string, extra: Record<string, unknown> = {}) => ({ turnId, answer: 'x', durationMs: 1, isAborted: false, ...extra }) as never

async function begin($: Engine, on: On, opts: Opts = {}, start: unknown = START) {
  clock = mock.clock(on)
  mock.store(on)
  const w = world(on, opts)
  await $.session.start(start as never)
  await clock.settle()
  return w
}

describe('improve: the command and the tools', () => {
  test('in a scripted session the command says it needs a person and does nothing', async ($, on) => {
    const w = await begin($, on, {}, { cwd: ROOT, surface: 'terminal', isInteractive: false })
    const r = await run($, 'the parser')
    expect(r).toBe('verinoda improve needs a person to choose: it does nothing in a scripted session')
    expect(w.opened).toEqual([])
    expect(w.registered).toEqual([])
    expect(w.submitted).toEqual([])
    expect(await text($.tool.call(propose([it('i1', 'problem')])))).toBe('verinoda improve: nobody is at the keyboard to choose; ask in text instead')
  })

  test('in an interactive session the tools wait for the command, which opens the pane and submits the review as the person', async ($, on) => {
    const w = await begin($, on)
    expect(w.commands).toContain('verinoda-improve')
    expect(w.registered).not.toContain('improve_propose')
    const r = await run($, ' the parser ')
    expect(r).toBe('looking at it; the list will appear in the pane, and nothing is changed until you choose')
    expect(w.registered).toEqual(['improve_propose', 'improve_report'])
    expect(w.opened).toEqual([{ id: PANE, title: 'İyileştirme', rows: 16, focus: true }])
    expect(w.submitted.length).toBe(1)
    expect(w.submitted[0]?.text).toBe(reviewPrompt('the parser'))
    expect(w.submitted[0]?.origin).toMatchObject({ kind: 'plugin', name: 'verinoda-live', asUser: true })
    await $.session.start(START) // a reload: nothing is lost, the tools are asked for again because a list is in play
    expect(w.registered.slice(2)).toEqual(['improve_propose', 'improve_report'])
  })

  test('both tools are listed in front, not behind ToolSearch', async ($, on) => {
    await begin($, on)
    for (const tool of [PROPOSE, REPORT]) {
      const d = await $.tool.describe({ tool, description: 'engine text', isDeferred: true } as never) as { isDeferred?: boolean; description: string }
      expect(d.isDeferred).toBe(false)
      expect(d.description.startsWith(tool === PROPOSE ? 'Show the user a list' : 'Report what happened')).toBe(true)
    }
  })

  // the auto-context and the gate went with D186; what stays is that the mod's prompts carry no context and deny no search
  test("the mod's own prompts go out untouched: no context attached, no search denied after them", async ($, on) => {
    const w = await begin($, on)
    await run($, 'where is the parser slow?')
    expect(w.submitted[0]?.context ?? []).toEqual([])
    const grep = await $.tool.call({ tool: 'Grep', pattern: 'parse' } as never) as { deny?: unknown }
    expect(grep.deny).toBeUndefined() // no task was started by the review prompt
    // the selection and the report prompts go through the same way
    await $.tool.call(propose([it('i1', 'problem')]))
    const pane = await mountPane($)
    expect(await pane.find({ key: 'item-i1' })).toBeDefined()
    await press($, 'item-i1')
    await press($, 'act-apply')
    await press($, 'send')
    expect(w.submitted[1]?.text.startsWith('My decisions on the improvement list')).toBe(true)
    expect(w.submitted[1]?.context ?? []).toEqual([])
    await $.turn.start(TURN('t-sel', w.submitted[1]?.text ?? ''))
    await $.turn.complete(DONE('t-sel'))
    expect(await pane.find({ key: 'ask-report' })).toBeDefined()
    await press($, 'ask-report')
    expect(w.submitted[2]?.text.startsWith('Report the outcome of the items I sent')).toBe(true)
    expect(w.submitted[2]?.context ?? []).toEqual([])
    expect(((await $.tool.call({ tool: 'Grep', pattern: 'parse' } as never)) as { deny?: unknown }).deny).toBeUndefined()
  })

  test('improve_propose draws the three groups in order, nothing selected, and says Shown when the pane is placed', async ($, on) => {
    const w = await begin($, on)
    await run($)
    const pane = await mountPane($)
    const answer = await text($.tool.call(propose(MIX)))
    expect(answer).toBe('Shown to the user: 5 items (2 possible problems, 1 improvements, 2 matters of taste). Stop here: change nothing and wait for their selection, which arrives as a message.')
    const drawn = flat(await pane.drawn())
    const order = ['Olası sorunlar', 'İşlevsel iyileştirmeler', 'Estetik seçenekler'].map(h => drawn.indexOf(h))
    expect(order.every(n => n >= 0) && order[0]! < order[1]! && order[1]! < order[2]!).toBe(true)
    expect(await label(pane, 'item-i1')).toBe('[ ] Title i1 (kanıtsız)')
    expect(await label(pane, 'item-i4')).toBe('[ ] Title i4 (tahmin)')
    expect(await label(pane, 'item-i5')).toBe('[ ] Title i5')
    for (const id of ['i1', 'i2', 'i3', 'i4', 'i5']) expect(await label(pane, `item-${id}`)).toMatch(/^\[ \] /) // nothing selected
    expect(await pane.find({ key: 'send' })).toBeUndefined()
    expect(await pane.find({ text: /Göndermek için en az bir madde seçin\./ })).toBeDefined()
    expect(w.opened.length).toBe(2)
  })

  test('a pane that is not on screen is said so, and the list is kept', { }, async ($, on) => {
    await begin($, on, { placed: false })
    await run($)
    const answer = await text($.tool.call(propose(MIX)))
    expect(answer).toBe('The list is stored (5 items) but the pane is not on screen. Tell the user to run /verinoda-improve to see it. Change nothing meanwhile.')
  })
})

describe('improve: marking and sending', () => {
  test('a row opens its details; a problem without evidence says so; apply marks it and Gönder (1) appears; keep alone sends nothing', async ($, on) => {
    await begin($, on)
    await run($)
    await $.tool.call(propose(MIX))
    const pane = await mountPane($)
    await press($, 'item-i1')
    expect(await pane.find({ text: /Kanıt: Kanıt verilmedi/ })).toBeDefined()
    expect(await pane.find({ text: /Gözlem: obs i1/ })).toBeDefined()
    expect((await pane.find({ key: 'act-apply' }))?.props.hotkey).toBe('u')
    expect(await pane.find({ key: 'act-check' })).toBeDefined()
    await press($, 'act-keep')
    expect(await pane.find({ key: 'send' })).toBeUndefined()
    expect((await pane.find({ key: 'act-keep' }))?.props.label).toBe('● Kalsın')
    await press($, 'act-apply')
    expect((await pane.find({ key: 'send' }))?.props.label).toBe('Gönder (1)')
    expect(await label(pane, 'item-i1')).toBe('[✓] Title i1 (kanıtsız)')
    await press($, 'act-apply') // the same decision again clears it
    expect(await pane.find({ key: 'send' })).toBeUndefined()
    await press($, 'item-i3') // an improvement has no "check first"
    expect(await pane.find({ key: 'act-check' })).toBeUndefined()
    expect(await pane.find({ text: /Kanıt:/ })).toBeUndefined()
  })

  test('a folded group opens with its button', async ($, on) => {
    await begin($, on)
    await run($)
    await $.tool.call(propose(many(10)))
    const pane = await mountPane($)
    expect((await pane.find({ key: 'more-problem' }))?.props.label).toBe('3 madde daha')
    expect(await pane.find({ key: 'item-i10' })).toBeUndefined()
    await press($, 'more-problem')
    expect(await pane.find({ key: 'item-i10' })).toBeDefined()
    expect(await pane.find({ key: 'more-problem' })).toBeUndefined()
  })

  test('the own field: typing keeps the text, Enter adds a selected item and empties the field, remove deletes it, ids are not reused, ten at most', async ($, on) => {
    await begin($, on)
    await run($)
    await $.tool.call(propose(MIX))
    const pane = await mountPane($)
    await typeInto($, 'own', 'make the title shorter', 'change')
    expect((await pane.find({ key: 'own' }))?.props.value).toBe('make the title shorter')
    await typeInto($, 'own', 'make the title shorter')
    expect((await pane.find({ key: 'own' }))?.props.value).toBe('')
    expect(flat(await pane.drawn())).toContain('Sizin eklediğiniz')
    expect(await label(pane, 'item-u1')).toBe('[✓] make the title shorter')
    expect((await pane.find({ key: 'send' }))?.props.label).toBe('Gönder (1)')
    await press($, 'item-u1')
    await press($, 'act-remove')
    expect(await pane.find({ key: 'item-u1' })).toBeUndefined()
    await typeInto($, 'own', 'second')
    expect(await pane.find({ key: 'item-u2' })).toBeDefined()
    expect(await pane.find({ key: 'item-u1' })).toBeUndefined()
    for (let n = 0; n < 9; n++) await typeInto($, 'own', `item ${n}`)
    expect(await pane.find({ key: 'own' })).toBeUndefined() // ten own items: no more field
  })

  test('send submits the selection as the person and shows what is waiting; stop-waiting gives it back', async ($, on) => {
    const w = await begin($, on)
    await run($)
    await $.tool.call(propose(MIX))
    const pane = await mountPane($)
    await press($, 'item-i2')
    await press($, 'act-apply')
    await press($, 'send')
    expect(w.submitted.length).toBe(2)
    expect(w.submitted[1]?.text).toContain('Apply these:\n- [i2] Title i2: change i2')
    expect(w.submitted[1]?.origin).toMatchObject({ kind: 'plugin', asUser: true })
    for (const key of ['item-i1', 'own', 'send', 'ask-report', 'more-problem']) expect(await pane.find({ key })).toBeUndefined()
    expect(flat(await pane.drawn())).toContain('[✓] Title i2 … bekleniyor')
    expect(await pane.find({ text: /Seçimleriniz gönderildi; sonuçlar burada görünecek\./ })).toBeDefined()
    await press($, 'stop-waiting')
    expect(flat(await pane.drawn())).toContain('? Sonuç bildirilmedi · Title i2')
    expect(await pane.find({ key: 'item-i1' })).toBeDefined()
  })

  test('improve_propose during sent is refused and the list is as it was; during choosing it replaces the list and keeps unsent own items', async ($, on) => {
    await begin($, on)
    await run($)
    await $.tool.call(propose(MIX))
    const pane = await mountPane($)
    await typeInto($, 'own', 'my idea')
    await press($, 'item-i2')
    await press($, 'act-apply')
    const fresh = [it('n1', 'improvement'), it('n2', 'improvement')]
    const replaced = await text($.tool.call(propose(fresh)))
    expect(replaced).toContain('Shown to the user: 2 items (0 possible problems, 2 improvements, 0 matters of taste).')
    expect(replaced.endsWith(' The earlier list (5 items, 1 decisions) was replaced.')).toBe(true)
    expect(await pane.find({ key: 'item-u1' })).toBeDefined()
    expect(await pane.find({ key: 'item-i2' })).toBeUndefined()
    await press($, 'send')
    const refused = await text($.tool.call(propose(MIX)))
    expect(refused).toBe('verinoda improve: a selection is being applied; report its outcomes with improve_report before proposing a new list')
    expect(await pane.find({ key: 'item-n1' })).toBeUndefined() // sent: nothing to mark, the list is as it was
    expect(flat(await pane.drawn())).toContain('n1')
  })
})

describe('improve: outcomes and turns', () => {
  async function sentTwo($: Engine, on: On) {
    const w = await begin($, on)
    await run($)
    await $.tool.call(propose(MIX))
    const pane = await mountPane($)
    for (const id of ['i2', 'i3']) {
      await press($, `item-${id}`)
      await press($, 'act-apply')
    }
    await press($, 'send')
    return { w, pane }
  }

  test('a report for one of two sent items keeps the phase; reporting the other shows both results and returns the pane to choosing', async ($, on) => {
    const { pane } = await sentTwo($, on)
    expect(await text($.tool.call(report([{ id: 'i2', status: 'applied', note: 'done', evidence: ['a.ts:4'] }])))).toBe('Recorded: 1 outcomes. Still waiting for: i3.')
    expect(flat(await pane.drawn())).toContain('✓ Uygulandı · Title i2')
    expect(flat(await pane.drawn())).toContain('[✓] Title i3 … bekleniyor')
    expect(await text($.tool.call(report([{ id: 'i2', status: 'applied', note: 'again' }])))).toBe('verinoda improve: no item i2 is waiting for an outcome')
    await $.tool.call(report([{ id: 'i3', status: 'partial', note: 'half' }], ['touched b.ts']))
    const drawn = flat(await pane.drawn())
    expect(drawn).toContain('◐ Kısmen uygulandı · Title i3')
    expect(drawn).toContain('Listede olmayan değişiklikler')
    expect(drawn).toContain('· touched b.ts')
    expect(await pane.find({ key: 'item-i1' })).toBeDefined() // back in choosing: what is left can be marked
  })

  test('the mod\'s own turn ending with an item waiting shows "not reported" and a button that asks; another turn changes nothing', async ($, on) => {
    const { w, pane } = await sentTwo($, on)
    const selection = w.submitted[1]?.text ?? ''
    await $.turn.start(TURN('t-other', 'something typed meanwhile'))
    await $.turn.complete(DONE('t-other'))
    expect(await pane.find({ key: 'stop-waiting' })).toBeDefined() // still sent
    await $.turn.start(TURN('t-sel', selection))
    await $.turn.complete(DONE('t-sub', { agentId: 'sub' })) // a subagent's end
    expect(await pane.find({ key: 'stop-waiting' })).toBeDefined()
    await $.turn.complete(DONE('t-sel'))
    const drawn = flat(await pane.drawn())
    expect(drawn).toContain('? Sonuç bildirilmedi · Title i2')
    expect((await pane.find({ key: 'ask-report' }))?.props.label).toBe('Sonucu iste')
    await press($, 'ask-report')
    expect(w.submitted[2]?.text).toBe(reportPrompt(['i2', 'i3']))
    expect(await pane.find({ key: 'stop-waiting' })).toBeDefined()
    expect(await text($.tool.call(report([{ id: 'i2', status: 'failed', note: 'late' }])))).toBe('Recorded: 1 outcomes. Still waiting for: i3.')
  })

  test('a turn that was running when send was pressed, or an earlier tracked turn, does not count as the selection\'s', async ($, on) => {
    const w = await begin($, on)
    await run($)
    await $.turn.start(TURN('t-review', w.submitted[0]?.text ?? '')) // the review's turn matched and is tracked
    await $.tool.call(propose(MIX))
    const pane = await mountPane($)
    await press($, 'item-i2')
    await press($, 'act-apply')
    await press($, 'send') // the review's turn is still running: send clears the tracked turn
    await $.turn.complete(DONE('t-review'))
    expect(await pane.find({ key: 'stop-waiting' })).toBeDefined()
    expect(flat(await pane.drawn())).not.toContain('Sonuç bildirilmedi')
  })

  test('the review turn ending without a list says so; a list that comes later replaces the line; another turn changes nothing', async ($, on) => {
    const w = await begin($, on)
    await run($)
    const pane = await mountPane($)
    expect(await pane.find({ text: /İnceleniyor… Claude listeyi hazırlıyor/ })).toBeDefined()
    await $.turn.start(TURN('t-x', 'unrelated'))
    await $.turn.complete(DONE('t-x'))
    expect(await pane.find({ text: /Liste henüz gelmedi/ })).toBeUndefined()
    await $.turn.start(TURN('t-r', w.submitted[0]?.text ?? ''))
    await $.turn.complete(DONE('t-r'))
    expect(await pane.find({ text: /Liste henüz gelmedi\. Claude bir soru sormuş olabilir/ })).toBeDefined()
    await $.tool.call(propose(MIX))
    expect(await pane.find({ text: /Liste henüz gelmedi/ })).toBeUndefined()
    expect(await pane.find({ key: 'item-i1' })).toBeDefined()
  })

  test('a confirmed report puts the item back, verified, with its details and no "check first"', async ($, on) => {
    const w = await begin($, on)
    await run($)
    await $.tool.call(propose(MIX))
    const pane = await mountPane($)
    await press($, 'item-i1')
    await press($, 'act-check')
    await press($, 'send')
    expect(w.submitted[1]?.text).toContain('Check these first')
    await $.tool.call(report([{ id: 'i1', status: 'confirmed', note: 'it is real', change: 'fix it so', evidence: ['c.ts:2'] }]))
    expect(await label(pane, 'item-i1')).toBe('[ ] Title i1 (doğrulandı)')
    expect(await pane.find({ text: /İnceleme: it is real/ })).toBeDefined() // the open item stays open
    expect(await pane.find({ text: /Öneri: fix it so/ })).toBeDefined()
    expect(await pane.find({ key: 'act-check' })).toBeUndefined()
    expect(await pane.find({ text: /Kanıt: c\.ts:2/ })).toBeDefined()
  })

  test('the command: opens the open list, starts over with an argument, starts nothing while sent, starts anew when every item is final', async ($, on) => {
    const w = await begin($, on)
    await run($, 'first')
    await $.tool.call(propose(MIX))
    const pane = await mountPane($)
    expect(await run($)).toBe('improvement list opened (5 items)')
    expect(w.submitted.length).toBe(1)
    await press($, 'item-i2')
    await press($, 'act-apply')
    expect(await run($, 'again')).toBe('looking at it; the list will appear in the pane, and nothing is changed until you choose (the earlier list of 5 items was replaced)')
    expect(w.submitted.length).toBe(2)
    await $.tool.call(propose([it('i1', 'problem')]))
    expect(await pane.find({ key: 'item-i1' })).toBeDefined() // read first: the pane redraws what a tool call changed when it is read
    await press($, 'item-i1')
    await press($, 'act-apply')
    await press($, 'send')
    expect(await run($, 'x')).toBe('a selection is being applied; its outcomes will show in the pane')
    expect(w.submitted.length).toBe(3)
    await $.tool.call(report([{ id: 'i1', status: 'applied', note: 'ok' }]))
    expect(await pane.find({ text: /✓ Uygulandı · Title i1/ })).toBeDefined()
    expect(await run($)).toContain('looking at it')
    expect(w.submitted.length).toBe(4)
  })

  test('a submit that did not enter puts the state back and says so', async ($, on) => {
    const w = await begin($, on, { drop: true })
    await run($)
    const pane = await mountPane($)
    await clock.settle()
    expect(await pane.find({ text: /Liste yok\./ })).toBeDefined()
    expect(await pane.find({ text: /İstek gönderilemedi\./ })).toBeDefined()
    expect(w.submitted.length).toBe(1)
    await $.tool.call(propose(MIX))
    expect(await pane.find({ text: /İstek gönderilemedi\./ })).toBeUndefined()
    await press($, 'item-i2')
    await press($, 'act-apply')
    await press($, 'send')
    expect(await pane.find({ key: 'send' })).toBeDefined() // sendable again, the same marks
    expect(await label(pane, 'item-i2')).toBe('[✓] Title i2')
    expect(await pane.find({ text: /İstek gönderilemedi\./ })).toBeDefined()
  })
})

describe('improve: a report request that did not enter', () => {
  test('its items go back to not reported, and the line says so', { }, async ($, on) => {
    const w = await begin($, on, { dropAfter: 2 })
    await run($)
    await $.tool.call(propose(MIX))
    const pane = await mountPane($)
    expect(await pane.find({ key: 'item-i2' })).toBeDefined()
    await press($, 'item-i2')
    await press($, 'act-apply')
    await press($, 'send')
    await $.turn.start(TURN('t-sel', w.submitted[1]?.text ?? ''))
    await $.turn.complete(DONE('t-sel'))
    expect(await pane.find({ key: 'ask-report' })).toBeDefined()
    await press($, 'ask-report') // the third submit is dropped
    expect(w.submitted.length).toBe(3)
    expect(flat(await pane.drawn())).toContain('? Sonuç bildirilmedi · Title i2')
    expect(await pane.find({ key: 'ask-report' })).toBeDefined()
    expect(await pane.find({ text: /İstek gönderilemedi\./ })).toBeDefined()
    expect(await pane.find({ key: 'stop-waiting' })).toBeUndefined()
  })
})

describe('improve: the offer, /clear and the surfaces', () => {
  test('with improveOffer on, an interactive session registers the tools and the prompt carries the section; off, neither', { options: { improveOffer: true } }, async ($, on) => {
    const w = await begin($, on)
    expect(w.registered).toEqual(['improve_propose', 'improve_report'])
    const out = await $.prompt.compose(COMPOSE)
    expect(out.sections.map(s => s.id)).toEqual(['intro', 'verinoda-live:improve'])
    expect(out.sections[1]?.scope).toBe('session')
    expect(out.sections[1]?.text).toContain('/verinoda-improve')
    expect(out.sections[1]?.text).toContain('mcp__verinoda-live__improve_propose')
  })

  test('off by default, and a scripted session gets neither', async ($, on) => {
    const w = await begin($, on)
    expect(w.registered).toEqual([])
    expect((await $.prompt.compose(COMPOSE)).sections.map(s => s.id)).toEqual(['intro'])
  })

  test('with improveOffer on, a scripted session still gets neither', { options: { improveOffer: true } }, async ($, on) => {
    const w = await begin($, on, {}, { cwd: ROOT, surface: 'terminal', isInteractive: false })
    expect(w.registered).toEqual([])
    expect((await $.prompt.compose(COMPOSE)).sections.map(s => s.id)).toEqual(['intro'])
  })

  test('/clear resets the state; another reason does not', async ($, on) => {
    const w = await begin($, on)
    await run($)
    await $.tool.call(propose(MIX))
    const pane = await mountPane($)
    await $.session.end({ reason: 'other', sessionId: 's1' } as never)
    expect(await pane.find({ key: 'item-i1' })).toBeDefined()
    await press($, 'item-i2')
    await press($, 'act-apply')
    await press($, 'send')
    await $.session.end({ reason: 'clear', sessionId: 's1' } as never)
    expect(await pane.find({ text: /Liste yok\./ })).toBeDefined()
    expect(await run($)).toContain('looking at it')
    expect(w.submitted.length).toBe(3)
  })

  test('the pane draws on the desktop as on the terminal, and on mobile without the field', async ($, on) => {
    await begin($, on)
    await run($)
    await $.tool.call(propose(MIX))
    const desktop = await mountPane($, {}, 'desktop')
    expect(await desktop.find({ key: 'item-i1' })).toBeDefined()
    expect(await desktop.find({ key: 'own' })).toBeDefined()
    await desktop.unmount()
    const mobile = await mountPane($, {}, 'mobile')
    expect(await mobile.find({ key: 'item-i1' })).toBeDefined()
    expect(await mobile.find({ key: 'own' })).toBeUndefined()
    expect(await mobile.find({ text: /Kendi maddenizi eklemek için terminali ya da masaüstünü kullanın\./ })).toBeDefined()
  })

  test('a narrow pane still draws, and an unfocused one names the key that gives it the keyboard', async ($, on) => {
    await begin($, on)
    await run($)
    await $.tool.call(propose([...MIX, ...many(4, 'improvement').map(i => ({ ...i, id: `m${i.id}`, title: 'A long title that has to wrap at thirty columns' }))]))
    const narrow = await mountPane($, { bodyColumns: 30, isFocused: false })
    expect(await narrow.find({ key: 'item-i1' })).toBeDefined()
    expect(await narrow.find({ text: /^Seçmek için ctrl\+x tab$/ })).toBeDefined()
    await narrow.unmount()
    const focused = await mountPane($, { bodyColumns: 30, isFocused: true })
    expect(await focused.find({ text: /^tab gezin · enter aç$/ })).toBeDefined()
    await press($, 'item-i2')
    await press($, 'act-apply')
    expect(await focused.find({ text: /^g gönder · tab gezin · enter aç$/ })).toBeDefined()
  })
})
