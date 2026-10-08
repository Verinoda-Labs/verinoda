// The improvement checklist pane (D175), the part that needs no `$`: a proposed list is validated and stored, the
// person's decisions, what may be sent, what the first sight shows, a report of outcomes applied, the three prompts,
// the two tools and the pane's words. ./improve-pane.tsx wires it to the engine.
import type { ImproveDecision, ImproveGroup, ImproveItem, ImproveState, ImproveStatus } from '../types'

export const IMPROVE_PANE = 'verinoda-improve'
export const IMPROVE_PROPOSE = 'mcp__verinoda-live__improve_propose'
export const IMPROVE_REPORT = 'mcp__verinoda-live__improve_report'

const TITLE_MAX = 120
const TEXT_MAX = 600
const EVIDENCE_MAX = 6
const EVIDENCE_CHARS = 160
const ITEMS_MAX = 30
const SUBJECT_MAX = 80
const EXTRA_MAX = 20
const EXTRA_CHARS = 300
export const OWN_MAX = 10
export const OWN_CHARS = 300
export const FIRST_SIGHT = 7
export const FALLBACK_SUBJECT = 'bu konuşma'

const MODEL_GROUPS = ['problem', 'improvement', 'taste'] as const
const ID_FORM = /^[A-Za-z0-9_-]{1,16}$/
const OWN_ID_FORM = /^u\d+$/

export function initialImprove(): ImproveState {
  return {
    phase: 'idle', subject: '', items: [], open: null, unfolded: [], extra: [], draft: '', ownSeq: 0, expect: '', queue: '', turn: null, note: '',
  }
}

// ---- the list and its parts --------------------------------------------------------------------------------------

// The list holds what has no outcome yet or is waiting for one; the results hold the rest. An item is in one of them.
export const isInList = (i: ImproveItem): boolean => i.outcome === null || i.outcome.status === 'waiting'
export const isResult = (i: ImproveItem): boolean => !isInList(i)
export const isSendable = (i: ImproveItem): boolean => (i.decision === 'apply' || i.decision === 'check') && i.outcome === null
export const isOwn = (i: ImproveItem): boolean => i.group === 'own'
export const isWaiting = (i: ImproveItem): boolean => i.outcome?.status === 'waiting'
export const isUnreported = (i: ImproveItem): boolean => i.outcome?.status === 'unreported'

export const listItems = (s: ImproveState): ImproveItem[] => s.items.filter(isInList)
export const resultItems = (s: ImproveState): ImproveItem[] => s.items.filter(isResult)
export const sendableItems = (s: ImproveState): ImproveItem[] => s.items.filter(isSendable)
export const ownItems = (s: ImproveState): ImproveItem[] => s.items.filter(isOwn)
export const modelItems = (s: ImproveState): ImproveItem[] => s.items.filter(i => !isOwn(i))

// A text cut to `max` characters, trimmed; a cut ends in an ellipsis.
export function clip(text: string, max: number): string {
  const t = text.trim()
  return t.length <= max ? t : `${t.slice(0, max - 1).trimEnd()}…`
}

function strings(value: unknown, max: number, chars: number): string[] {
  if (!Array.isArray(value)) return []
  const out: string[] = []
  for (const v of value) {
    if (typeof v !== 'string' || v.trim() === '') continue
    out.push(clip(v, chars))
    if (out.length === max) break
  }
  return out
}

// ---- a proposed list ---------------------------------------------------------------------------------------------

export type Proposal = { subject?: unknown; items?: unknown }

export type Replaced = { n: number; decided: number }

export type Proposed =
  | { error: string }
  | { state: ImproveState; replaced: Replaced | null; counts: { problem: number; improvement: number; taste: number } }

const refused = (what: string) => ({ error: `verinoda improve: ${what}; nothing was shown` })

// Validated whole or not at all: the first failure is the answer. The person's own items that were not sent stay.
export function proposeList(state: ImproveState, input: Proposal, what: string): Proposed {
  const raw = input.items
  if (!Array.isArray(raw) || raw.length < 1 || raw.length > ITEMS_MAX) return refused(`items must be a list of 1 to ${ITEMS_MAX} objects`)
  const seen = new Set<string>()
  const items: ImproveItem[] = []
  for (let n = 0; n < raw.length; n++) {
    const r = raw[n] as Record<string, unknown> | null
    const at = `item ${n + 1}`
    if (typeof r !== 'object' || r === null || Array.isArray(r)) return refused(`${at} is not an object`)
    const id = typeof r.id === 'string' ? r.id.trim() : ''
    if (id === '' || !ID_FORM.test(id) || OWN_ID_FORM.test(id)) {
      return refused(`${at} has an id that is empty or not 1 to 16 letters, digits, - or _ (u and digits are kept for the user's own items)`)
    }
    if (seen.has(id)) return refused(`id ${id} is used twice`)
    seen.add(id)
    if (!MODEL_GROUPS.includes(r.group as never)) return refused(`item ${id} has a group that is not problem, improvement or taste`)
    const text = (k: string, max: number): string | undefined => {
      const v = r[k]
      return typeof v === 'string' && v.trim() !== '' ? clip(v, max) : undefined
    }
    const title = text('title', TITLE_MAX)
    const observation = text('observation', TEXT_MAX)
    const why = text('why', TEXT_MAX)
    const change = text('change', TEXT_MAX)
    for (const [k, v] of [['title', title], ['observation', observation], ['why', why], ['change', change]] as const) {
      if (v === undefined) return refused(`item ${id} needs a non-empty ${k}`)
    }
    items.push({
      id, group: r.group as ImproveGroup, title: title ?? '', observation: observation ?? '', why: why ?? '', change: change ?? '',
      cost: typeof r.cost === 'string' ? clip(r.cost, TEXT_MAX) : '', evidence: strings(r.evidence, EVIDENCE_MAX, EVIDENCE_CHARS),
      seen: r.seen === true, verified: false, checked: '', decision: 'none', sentAs: null, outcome: null,
    })
  }
  const subject = clip(typeof input.subject === 'string' ? input.subject : '', SUBJECT_MAX) || clip(what, SUBJECT_MAX) || FALLBACK_SUBJECT
  const old = modelItems(state).filter(isInList)
  const replaced = old.length === 0 ? null : { n: old.length, decided: old.filter(i => i.decision !== 'none').length }
  const kept = ownItems(state).filter(isSendable)
  const own = kept.filter(i => i.outcome === null)
  const counts = { problem: 0, improvement: 0, taste: 0 }
  for (const i of items) counts[i.group as keyof typeof counts]++
  return {
    state: { ...state, phase: 'choosing', subject, items: [...items, ...own], open: null, unfolded: [], extra: [], queue: '', note: '' },
    replaced, counts,
  }
}

export function proposeAnswer(p: { counts: { problem: number; improvement: number; taste: number }; replaced: Replaced | null }, isPlaced: boolean): string {
  const n = p.counts.problem + p.counts.improvement + p.counts.taste
  const tail = p.replaced === null ? '' : ` The earlier list (${p.replaced.n} items, ${p.replaced.decided} decisions) was replaced.`
  return (isPlaced
    ? `Shown to the user: ${n} items (${p.counts.problem} possible problems, ${p.counts.improvement} improvements, ${p.counts.taste} matters of taste). ` +
      'Stop here: change nothing and wait for their selection, which arrives as a message.'
    : `The list is stored (${n} items) but the pane is not on screen. Tell the user to run /verinoda-improve to see it. Change nothing meanwhile.`) + tail
}

// ---- decisions ---------------------------------------------------------------------------------------------------

export function canCheck(i: ImproveItem): boolean {
  return i.group === 'problem' && !i.verified
}

// Pressing the decision an item has clears it. `check` is for a suspected problem that no check confirmed yet; an own item
// is `apply` from the start and keeps it.
export function decide(state: ImproveState, id: string, decision: Exclude<ImproveDecision, 'none'>): ImproveState {
  const i = state.items.find(x => x.id === id)
  if (i === undefined || !isInList(i) || isOwn(i) || isWaiting(i)) return state
  if (decision === 'check' && !canCheck(i)) return state
  const next: ImproveDecision = i.decision === decision ? 'none' : decision
  return { ...state, items: state.items.map(x => (x.id === id ? { ...x, decision: next } : x)) }
}

export function addOwn(state: ImproveState, text: string): ImproveState {
  const t = clip(text, OWN_CHARS)
  if (t === '' || ownItems(state).filter(isInList).length >= OWN_MAX) return { ...state, draft: '' }
  const seq = state.ownSeq + 1
  const item: ImproveItem = {
    id: `u${seq}`, group: 'own', title: t, observation: '', why: '', change: '', cost: '', evidence: [], seen: true,
    verified: false, checked: '', decision: 'apply', sentAs: null, outcome: null,
  }
  return { ...state, items: [...state.items, item], ownSeq: seq, draft: '' }
}

export function removeOwn(state: ImproveState, id: string): ImproveState {
  const i = state.items.find(x => x.id === id)
  if (i === undefined || !isOwn(i) || !isInList(i) || isWaiting(i)) return state
  return { ...state, items: state.items.filter(x => x.id !== id), open: state.open === id ? null : state.open }
}

export const toggleOpen = (state: ImproveState, id: string): ImproveState => ({ ...state, open: state.open === id ? null : id })
export const unfold = (state: ImproveState, group: ImproveGroup): ImproveState =>
  state.unfolded.includes(group) ? state : { ...state, unfolded: [...state.unfolded, group] }

// ---- what the first sight shows ----------------------------------------------------------------------------------

// Of the list's model items the seven best ranked, and besides them any item with a decision, any verified one and the open
// one. A group that was unfolded shows whole. The person's own items are always shown (their own group is small by design).
export function visibleIds(state: ImproveState): Set<string> {
  const list = listItems(state)
  const out = new Set<string>()
  list.filter(i => !isOwn(i)).forEach((i, rank) => {
    if (rank < FIRST_SIGHT || i.decision !== 'none' || i.verified || i.id === state.open || state.unfolded.includes(i.group)) out.add(i.id)
  })
  for (const i of list) if (isOwn(i)) out.add(i.id)
  return out
}

export type RowView = { id: string; mark: string; title: string; suffix: string; waiting: boolean }
export type GroupView = { group: ImproveGroup; label: string; rows: RowView[]; more: number }

const GROUP_LABEL: Record<ImproveGroup, string> = {
  problem: 'Olası sorunlar', improvement: 'İşlevsel iyileştirmeler', taste: 'Estetik seçenekler', own: 'Sizin eklediğiniz',
}
const MARK: Record<ImproveDecision, string> = { none: '[ ]', apply: '[✓]', keep: '[–]', check: '[?]' }

export function rowSuffix(i: ImproveItem): string {
  if (i.verified) return ' (doğrulandı)'
  if (i.group === 'problem' && i.evidence.length === 0) return ' (kanıtsız)'
  if (i.group === 'taste' && !i.seen) return ' (tahmin)'
  return ''
}

export function groupViews(state: ImproveState): GroupView[] {
  const shown = visibleIds(state)
  const list = listItems(state)
  const views: GroupView[] = []
  for (const group of ['problem', 'improvement', 'taste', 'own'] as const) {
    const all = list.filter(i => i.group === group)
    if (all.length === 0) continue
    const rows = all.filter(i => shown.has(i.id)).map(i => ({
      id: i.id, mark: MARK[i.decision], title: i.title, suffix: rowSuffix(i), waiting: isWaiting(i),
    }))
    views.push({ group, label: GROUP_LABEL[group], rows, more: all.length - rows.length })
  }
  return views
}

export function countsLine(state: ImproveState): string {
  const list = listItems(state)
  if (list.length === 0) return ''
  const send = sendableItems(state)
  const parts = [
    `${list.length} madde`,
    ...([[send.filter(i => i.decision === 'apply').length, 'uygula'], [send.filter(i => i.decision === 'check').length, 'kontrol'],
      [list.filter(i => i.decision === 'keep').length, 'kalsın']] as const).filter(([n]) => n > 0).map(([n, w]) => `${n} ${w}`),
  ]
  return parts.join(' · ')
}

export const RESULT_WORDS: Record<Exclude<ImproveStatus, 'waiting'>, string> = {
  applied: '✓ Uygulandı', partial: '◐ Kısmen uygulandı', failed: '✗ Uygulanamadı',
  not_confirmed: '○ İncelendi: sorun doğrulanmadı', unreported: '? Sonuç bildirilmedi',
}

export const WORDS = {
  idle: 'Liste yok. /verinoda-improve [neye bakılsın] ile başlatın.',
  notSent: 'İstek gönderilemedi.',
  reviewing: 'İnceleniyor… Claude listeyi hazırlıyor; hiçbir şey değiştirilmiyor.',
  noList: 'Liste henüz gelmedi. Claude bir soru sormuş olabilir: yanıtlayın ya da /verinoda-improve ile yeniden başlatın.',
  sent: 'Seçimleriniz gönderildi; sonuçlar burada görünecek.',
  needOne: 'Göndermek için en az bir madde seçin.',
  mobileOwn: 'Kendi maddenizi eklemek için terminali ya da masaüstünü kullanın.',
  unfocused: 'Seçmek için ctrl+x tab',
  results: 'Sonuçlar',
  extra: 'Listede olmayan değişiklikler',
  own: 'Kendi maddeniz',
  noEvidence: 'Kanıt verilmedi',
  waiting: ' … bekleniyor',
}

// ---- sending and what comes back ---------------------------------------------------------------------------------

// Every sendable item gets `sentAs` (its decision) and the outcome waiting; its decision, and so its mark, stays.
export function markSent(state: ImproveState): ImproveState {
  return {
    ...state, phase: 'sent', expect: 'selection', turn: null, note: '',
    items: state.items.map(i => (isSendable(i)
      ? { ...i, sentAs: i.decision === 'check' ? 'check' as const : 'apply' as const, outcome: { status: 'waiting' as const, note: '', evidence: [] } }
      : i)),
  }
}

// The person stops waiting, or the mod's own turn ended: what is still waiting is unreported, and the list can be marked again.
export function unreport(state: ImproveState): ImproveState {
  return {
    ...state, phase: 'choosing',
    items: state.items.map(i => (isWaiting(i) ? { ...i, outcome: { status: 'unreported' as const, note: '', evidence: [] } } : i)),
  }
}

// A prompt that did not enter: the state before the press, so that the same marks can be sent again.
export function undoSend(state: ImproveState, kind: 'review' | 'selection' | 'report'): ImproveState {
  const base = { ...state, expect: '' as const, queue: '' as const, note: 'not-sent' as const }
  if (kind === 'review') return { ...base, phase: 'idle' }
  if (kind === 'selection') {
    return { ...base, phase: 'choosing', items: state.items.map(i => (isWaiting(i) ? { ...i, sentAs: null, outcome: null } : i)) }
  }
  return {
    ...base, phase: 'choosing',
    items: state.items.map(i => (isWaiting(i) ? { ...i, outcome: { status: 'unreported' as const, note: '', evidence: [] } } : i)),
  }
}

export function askReport(state: ImproveState): ImproveState {
  return {
    ...state, phase: 'sent', expect: 'report', turn: null, note: '',
    items: state.items.map(i => (isUnreported(i) ? { ...i, outcome: { status: 'waiting' as const, note: '', evidence: [] } } : i)),
  }
}

export function startReview(state: ImproveState, what: string): ImproveState {
  return {
    ...state, phase: 'reviewing', subject: what, items: ownItems(state).filter(isSendable), open: null, unfolded: [], extra: [],
    expect: '', queue: 'review', turn: null, note: '',
  }
}

export type Report = { outcomes?: unknown; extra_changes?: unknown }
const REPORT_STATUSES = ['applied', 'partial', 'failed', 'confirmed', 'not_confirmed'] as const
const FITS: Record<'apply' | 'check', readonly string[]> = { apply: ['applied', 'partial', 'failed'], check: ['confirmed', 'not_confirmed'] }

export type Reported = { error: string } | { state: ImproveState; answer: string }

// A call with any invalid outcome records nothing.
export function applyReport(state: ImproveState, input: Report): Reported {
  const fail = (what: string) => ({ error: `verinoda improve: ${what}` })
  const raw = input.outcomes
  if (!Array.isArray(raw) || raw.length < 1 || raw.some(o => typeof o !== 'object' || o === null || Array.isArray(o))) {
    return fail('outcomes must list at least one item; nothing was recorded')
  }
  const outs = raw as Record<string, unknown>[]
  const ids = outs.map(o => (typeof o.id === 'string' ? o.id.trim() : ''))
  const twice = ids.find((id, n) => ids.indexOf(id) !== n)
  if (twice !== undefined) return fail(`item ${twice} is reported twice`)
  const byId = new Map(state.items.map(i => [i.id, i]))
  for (const id of ids) {
    const i = byId.get(id)
    if (i === undefined || !(isWaiting(i) || isUnreported(i))) return fail(`no item ${id} is waiting for an outcome`)
  }
  for (const [n, o] of outs.entries()) {
    const i = byId.get(ids[n] ?? '') as ImproveItem
    const sent = i.sentAs ?? 'apply'
    if (!REPORT_STATUSES.includes(o.status as never) || !FITS[sent].includes(o.status as string)) {
      return fail(`item ${i.id} was sent to ${sent}; its outcome is one of ${FITS[sent].join(sent === 'apply' ? ', ' : ' or ').replace(/, ([a-z_]+)$/, ' or $1')}`)
    }
  }
  for (const [n, o] of outs.entries()) {
    if (typeof o.note !== 'string' || o.note.trim() === '') return fail(`item ${ids[n]} needs a note the user can read`)
  }
  const items = state.items.map(i => {
    const n = ids.indexOf(i.id)
    if (n < 0) return i
    const o = outs[n] as Record<string, unknown>
    const note = clip(o.note as string, TEXT_MAX)
    const evidence = strings(o.evidence, EVIDENCE_MAX, EVIDENCE_CHARS)
    if (o.status === 'confirmed') {
      const change = typeof o.change === 'string' && o.change.trim() !== '' ? clip(o.change, TEXT_MAX) : i.change
      return {
        ...i, verified: true, checked: note, outcome: null, decision: 'none' as const, sentAs: null, change,
        evidence: [...i.evidence, ...evidence].slice(0, EVIDENCE_MAX),
      }
    }
    return { ...i, outcome: { status: o.status as ImproveStatus, note, evidence } }
  })
  const extra = [...state.extra, ...strings(input.extra_changes, EXTRA_MAX, EXTRA_CHARS)].slice(0, EXTRA_MAX)
  const waiting = items.filter(isWaiting)
  const next: ImproveState = { ...state, items, extra, phase: state.phase === 'sent' && waiting.length === 0 ? 'choosing' : state.phase }
  const still = waiting.length > 0 ? ` Still waiting for: ${waiting.map(i => i.id).join(', ')}.` : ''
  return { state: next, answer: `Recorded: ${outs.length} outcomes.${still}` }
}

// ---- the three prompts -------------------------------------------------------------------------------------------

export function reviewPrompt(what: string): string {
  const w = what.trim()
  return [
    'Make a list of what could be changed here so that I can choose. Do not change anything yet.',
    `What to look at: ${w === '' ? 'what we have been working on in this conversation. If that is not clear, ask me one question first.' : w}`,
    '',
    'Look at it first: read the code, and if it has a rendered view you can look at, look at it. Then call',
    `${IMPROVE_PROPOSE} with the items, ranked, the most worth doing first. Do not pad the list. Then stop and`,
    'wait for my selection.',
  ].join('\n')
}

export function selectionPrompt(state: ImproveState): string {
  const send = sendableItems(state)
  const line = (i: ImproveItem, withChange: boolean) =>
    isOwn(i) ? `- [${i.id}] ${i.title} (my own item)` : `- [${i.id}] ${i.title}${withChange ? `: ${i.change}` : ''}`
  const section = (head: string, items: ImproveItem[], withChange: boolean) =>
    items.length === 0 ? [] : [head, ...items.map(i => line(i, withChange)), '']
  const keep = listItems(state).filter(i => i.decision === 'keep' && !isOwn(i))
  return [
    `My decisions on the improvement list (${state.subject}):`,
    '',
    ...section('Apply these:', send.filter(i => i.decision === 'apply'), true),
    ...section('Check these first (investigate only; change nothing for them):', send.filter(i => i.decision === 'check'), false),
    ...section('Keep these as they are (do not change them, also not as a side effect):', keep, false),
    'Everything else stays as it is. You may make the small auxiliary changes an item needs. If one would add behaviour, change',
    'behaviour I did not choose, or cost something, tell me before you do it. When you are done or cannot go on, call',
    `${IMPROVE_REPORT} with one outcome for each item to apply or to check, and list under extra_changes any`,
    'change that was not on the list.',
  ].join('\n')
}

export function reportPrompt(ids: string[]): string {
  return [
    `Report the outcome of the items I sent that you have not reported yet (${ids.join(', ')}) with ${IMPROVE_REPORT}.`,
    'Change nothing else.',
  ].join('\n')
}

// A turn belongs to the mod when its text starts with the first line of the prompt that was submitted.
export function firstLine(prompt: string): string {
  return (prompt.split('\n')[0] ?? '').trim()
}

export function expectedLine(state: ImproveState): string {
  if (state.expect === 'review') return firstLine(reviewPrompt(''))
  if (state.expect === 'selection') return firstLine(selectionPrompt(state))
  if (state.expect === 'report') return firstLine(reportPrompt(state.items.filter(isWaiting).map(i => i.id)))
  return ''
}

// ---- the tools ---------------------------------------------------------------------------------------------------

export const IMPROVE_SPECS = [
  {
    name: 'improve_propose',
    description:
      'Show the user a list of what could be changed, in the Verinoda pane, so that they choose. Call it only when the user asked ' +
      'for improvement options or a review list, in words or with /verinoda-improve; never on your own initiative. Before calling, ' +
      'look at the code or the screen in question and change nothing. Rank the items, the most worth doing first, and do not pad ' +
      'the list. Each item is one change the user can say yes or no to. `group`: `problem` is a possible bug, inconsistency or ' +
      'unexpected behaviour (give `evidence`, the file:line you read); `improvement` is usability, readability, performance or ' +
      'upkeep; `taste` is look, tone, density, colour or layout, a preference and not a defect (set `seen` to true only if you ' +
      'judged it from a rendered view or a screenshot). `title` says the change in one concrete line (not "improve the hierarchy" ' +
      'but "make Save the only primary button"); `observation` is what is there now; `why` is why it may matter; `change` is ' +
      'exactly what you would do and what stays as it is; `cost` is what it costs or risks, if anything. After the call, stop: ' +
      'change nothing and wait for the user\'s selection, which arrives as a message.',
    inputSchema: {
      type: 'object',
      properties: {
        subject: { type: 'string', description: 'What was looked at, in a few words: a file, a screen, a module' },
        items: {
          type: 'array', minItems: 1, maxItems: 30,
          items: {
            type: 'object',
            properties: {
              id: { type: 'string', description: 'Short and unique in this list: i1, i2, ...' },
              group: { enum: ['problem', 'improvement', 'taste'] },
              title: { type: 'string' },
              observation: { type: 'string' },
              why: { type: 'string' },
              change: { type: 'string' },
              cost: { type: 'string' },
              evidence: { type: 'array', items: { type: 'string' } },
              seen: { type: 'boolean' },
            },
            required: ['id', 'group', 'title', 'observation', 'why', 'change'],
          },
        },
      },
      required: ['subject', 'items'],
    },
  },
  {
    name: 'improve_report',
    description:
      'Report what happened to each item the user sent from the Verinoda pane, once you are done or cannot go on. One outcome per ' +
      'item id you were given. For an item to apply: `applied` (done as described), `partial` (say what is missing) or `failed` ' +
      '(say why). For an item to check first: `confirmed` (the problem is real; put the fix you propose in `change` and do not ' +
      'apply it) or `not_confirmed` (you looked and found nothing that needs a change). `note` is one or two sentences the user ' +
      'reads; `evidence` is what shows it: the check you ran and its result, a file:line. List under `extra_changes` every change ' +
      'you made that was not on the list.',
    inputSchema: {
      type: 'object',
      properties: {
        outcomes: {
          type: 'array', minItems: 1,
          items: {
            type: 'object',
            properties: {
              id: { type: 'string' },
              status: { enum: ['applied', 'partial', 'failed', 'confirmed', 'not_confirmed'] },
              note: { type: 'string' },
              change: { type: 'string' },
              evidence: { type: 'array', items: { type: 'string' } },
            },
            required: ['id', 'status', 'note'],
          },
        },
        extra_changes: { type: 'array', items: { type: 'string' } },
      },
      required: ['outcomes'],
    },
  },
] as const

// The one line the system prompt carries when `improveOffer` is on.
export const OFFER_SECTION =
  'When the user asks for something to be better, nicer, cleaner or of higher quality without saying what should change, do ' +
  'not guess and do not start editing. Offer in one line to list what could be changed so that they choose: ' +
  '`/verinoda-improve` opens the list, and they may add what to look at. If they ask for the list in words, look first, then ' +
  `call \`${IMPROVE_PROPOSE}\`. A request that says what to change is not vague: do it.`
