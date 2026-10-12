import { atom, read, update } from 'claude-code'
import type { EngineInterface, On } from 'claude-code'

import type { ImproveGroup, ImproveItem, ImproveState } from '../types'
import {
  addOwn, applyReport, askReport, canCheck, countsLine, decide, expectedLine, groupViews, IMPROVE_PANE, IMPROVE_PROPOSE, IMPROVE_REPORT,
  IMPROVE_SPECS, initialImprove, isInList, isUnreported, isWaiting, listItems, markSent, modelItems, OFFER_SECTION, OWN_MAX,
  proposeAnswer, proposeList, removeOwn, reportPrompt, resultItems, RESULT_WORDS, selectionPrompt, sendableItems,
  startReview, toggleOpen, undoSend, unfold, unreport, WORDS, ownItems,
} from './improve'
import type { Proposal, Report } from './improve'

// One key of the session's state holds all of it (declared in ../types); a reload keeps it. The feature is why this file
// exists apart from register.tsx: its drawing and hooks are a module of their own that `register` calls once (D175).
export const improve = atom({ plugin: 'verinoda-live', key: 'improve' } as const, initialImprove())

export const COMMAND = {
  name: 'verinoda-improve',
  description: 'List what could be changed here and choose what to apply; nothing changes until you choose.',
  argumentHint: '[what to look at]',
}
const TITLE = 'İyileştirme'
const PANE_ROWS = 16

// The session's interactivity, kept from `session.start` as everywhere in this mod: nobody at the keyboard gets none of it.
export const mod = { interactive: false, offered: false }

// Work left running after a hook returns: a rejection after the module unloaded is no error of the person's.
function background(work: Promise<unknown>): void {
  work.catch(() => undefined)
}

const patch = ($: EngineInterface, fn: (s: ImproveState) => ImproveState) => update($, improve, fn).then(() => undefined)

async function registerTools($: EngineInterface): Promise<void> {
  for (const spec of IMPROVE_SPECS) {
    await $.tool.register({ name: spec.name, description: spec.description, inputSchema: spec.inputSchema as unknown as Record<string, unknown> })
  }
}

const openPane = ($: EngineInterface) => $.ui.open({ id: IMPROVE_PANE, title: TITLE, focus: true, rows: PANE_ROWS })

// A prompt the mod submits is the person's own decision, read bare by the model. Never awaited by a press (the turn may not be
// able to start until the handler returns); one that did not enter puts the state back as it was. (The review prompt is
// submitted from register.tsx, from turn.complete: the host refuses a submit from a command's hook.)
function submit($: EngineInterface, kind: 'selection' | 'report', text: string): void {
  const back = () => patch($, s => (s.expect === kind ? undoSend(s, kind) : s))
  background($.prompt.submit({ text, asUser: true }).then(r => (r.drop === undefined ? undefined : back()), back))
}

// The turn the mod's own prompt started has ended, or was interrupted.
export function endOfTurn(s: ImproveState): ImproveState {
  const base = { ...s, turn: null }
  if (s.phase === 'sent') return unreport(base)
  if (s.phase === 'reviewing') return { ...base, note: 'no-list' }
  return base
}

// The three events `register.tsx` already hooks without a matcher (a second such hook is refused) reach this feature through
// what is exported here; `$` is never passed across an import, so the few lines that need it stay in `register.tsx`.
export function improveSections(sections: readonly { id: string; text: string; scope: 'session' | 'shared' }[]) {
  if (!mod.offered || !mod.interactive) return sections
  return [...sections, { id: 'verinoda-live:improve', text: OFFER_SECTION, scope: 'session' as const }]
}

export function registerImprove(on: On): void {
  // First-class, as the Verinoda server's core tools are (MCP_CORE_TOOLS in register.tsx): a tool the model must look up
  // first is not called.
  on('tool.describe', { tool: [IMPROVE_PROPOSE, IMPROVE_REPORT] }, ($, e) => {
    const spec = IMPROVE_SPECS.find(s => `mcp__verinoda-live__${s.name}` === e.tool)
    return { description: spec?.description ?? e.description, isDeferred: false }
  })

  on('command.run', { command: COMMAND.name }, async ($, e) => {
    if (!mod.interactive) return { text: 'verinoda improve needs a person to choose: it does nothing in a scripted session' }
    const what = e.args.trim()
    const s = await read($, improve)
    const size = listItems(s).length
    if (s.phase === 'sent') {
      await openPane($)
      return { text: 'a selection is being applied; its outcomes will show in the pane' }
    }
    if (s.phase === 'choosing' && what === '' && (size > 0 || s.items.some(isUnreported))) {
      await openPane($)
      return { text: `improvement list opened (${size} items)` }
    }
    // the list this replaces: told only when the person had decided something in it
    const old = modelItems(s).filter(isInList)
    const replaced = old.some(i => i.decision !== 'none') ? ` (the earlier list of ${old.length} items was replaced)` : ''
    await registerTools($)
    await patch($, x => startReview(x, what))
    await openPane($)
    // the review prompt goes out when this command's own turn ends (register.tsx): the host refuses a submit from here
    return { text: `looking at it; the list will appear in the pane, and nothing is changed until you choose${replaced}` }
  })

  on('tool.call', { tool: IMPROVE_PROPOSE }, async ($, e) => {
    if (!mod.interactive) return { result: 'verinoda improve: nobody is at the keyboard to choose; ask in text instead' }
    const s = await read($, improve)
    if (s.phase === 'sent') {
      return { result: 'verinoda improve: a selection is being applied; report its outcomes with improve_report before proposing a new list' }
    }
    const p = proposeList(s, e as unknown as Proposal, s.phase === 'reviewing' ? s.subject : '')
    if ('error' in p) return { result: p.error }
    await patch($, () => p.state)
    const opened = await openPane($)
    return { result: proposeAnswer(p, opened.isPlaced) }
  })

  on('tool.call', { tool: IMPROVE_REPORT }, async ($, e) => {
    const s = await read($, improve)
    const r = applyReport(s, e as unknown as Report)
    if ('error' in r) return { result: r.error }
    await patch($, () => r.state)
    return { result: r.answer }
  })

  // Which turn is the mod's own: the one whose text starts with the first line of the prompt that was submitted.
  on('turn.start', async ($, e, next) => {
    const s = await read($, improve)
    if (s.expect !== '' && e.text.trim().startsWith(expectedLine(s))) await patch($, x => ({ ...x, turn: e.turnId, expect: '' }))
    return next(e)
  })

  // `/clear` ends the conversation without a `session.start` after it, so the list of the old one goes.
  on('session.end', async ($, e, next) => {
    if (e.reason === 'clear') await patch($, initialImprove)
    return next(e)
  })

  on('ui.render', { component: 'Pane', requestId: IMPROVE_PANE }, async ($, e) => {
    const { Box, Button, Text, Input } = $.ui.resolve(e) as ReturnType<typeof $.ui.resolve> & { Input?: unknown }
    const InputEl = Input as ((props: Record<string, unknown>) => JSX.Element) | undefined
    const s = await read($, improve)
    const columns = Math.max(20, e.props.bodyColumns ?? 48)
    const isNarrow = columns < 40

    if (s.phase === 'idle') {
      return (
        <Box flexDirection="column">
          <Text wrap="wrap">{WORDS.idle}</Text>
          {s.note === 'not-sent' && <Text key="not-sent" color="yellow" wrap="wrap">{WORDS.notSent}</Text>}
        </Box>
      )
    }
    if (s.phase === 'reviewing') {
      return (
        <Box flexDirection="column">
          <Text wrap="wrap">{s.note === 'no-list' ? WORDS.noList : WORDS.reviewing}</Text>
          {s.note === 'not-sent' && <Text key="not-sent" color="yellow" wrap="wrap">{WORDS.notSent}</Text>}
        </Box>
      )
    }

    const isSent = s.phase === 'sent'
    const results = resultItems(s)
    const views = groupViews(s)
    const sendN = sendableItems(s).length
    const counts = countsLine(s)
    const openItem = s.items.find(i => i.id === s.open && isInList(i))

    const detail = (i: ImproveItem) => {
      const line = (k: string, label: string, text: string) => <Text key={k} wrap="wrap">{`    ${label}: ${text}`}</Text>
      if (i.group === 'own') {
        return (
          <Box key={`open-${i.id}`} flexDirection="column">
            {!isSent && !isWaiting(i) && <Button key="act-remove" label="Kaldır" variant="secondary" onPress={() => background(patch($, x => removeOwn(x, i.id)))} />}
          </Box>
        )
      }
      const evidence = i.evidence.length > 0 ? i.evidence.join(', ') : i.group === 'problem' ? WORDS.noEvidence : ''
      const pick = (d: 'apply' | 'keep' | 'check', label: string, hotkey: string) => (
        <Button key={`act-${d}`} label={`${i.decision === d ? '● ' : ''}${label}`} hotkey={hotkey}
          variant={i.decision === d ? 'primary' : 'secondary'} onPress={() => background(patch($, x => decide(x, i.id, d)))} />
      )
      return (
        <Box key={`open-${i.id}`} flexDirection="column">
          {line('obs', 'Gözlem', i.observation)}
          {line('why', 'Neden', i.why)}
          {line('chg', 'Öneri', i.change)}
          {i.cost !== '' && line('cost', 'Bedel', i.cost)}
          {evidence !== '' && line('evd', 'Kanıt', evidence)}
          {i.verified && line('chk', 'İnceleme', i.checked)}
          {!isSent && (
            <Box flexDirection={isNarrow ? 'column' : 'row'} columnGap={1}>
              {pick('apply', 'Uygula', 'u')}
              {pick('keep', 'Kalsın', 'k')}
              {canCheck(i) && pick('check', 'Önce kontrol et', 'c')}
            </Box>
          )}
        </Box>
      )
    }

    const resultBlock = results.length === 0 ? null : (
      <Box key="results" flexDirection="column">
        <Text bold>{WORDS.results}</Text>
        {results.map(i => {
          const status = (i.outcome?.status ?? 'unreported') as keyof typeof RESULT_WORDS
          const tone = status === 'applied' ? 'green' : status === 'failed' ? 'red' : status === 'not_confirmed' ? undefined : 'yellow'
          return (
            <Box key={`res-${i.id}`} flexDirection="column">
              <Text color={tone} dimColor={status === 'not_confirmed'} wrap="wrap">{`  ${RESULT_WORDS[status]} · ${i.title}`}</Text>
              {i.outcome !== null && i.outcome.note !== '' && <Text key="note" wrap="wrap">{`      ${i.outcome.note}`}</Text>}
              {i.outcome !== null && i.outcome.evidence.length > 0 && <Text key="evd" dimColor wrap="wrap">{`      ${i.outcome.evidence.join(', ')}`}</Text>}
            </Box>
          )
        })}
        {!isSent && results.some(isUnreported) && (
          <Button key="ask-report" label="Sonucu iste" variant="secondary"
            onPress={() => background(askFor($))} />
        )}
      </Box>
    )

    const extraBlock = s.extra.length === 0 ? null : (
      <Box key="extra" flexDirection="column">
        <Text bold>{WORDS.extra}</Text>
        {s.extra.map((x, n) => <Text key={`extra-${n}`} wrap="wrap">{`  · ${x}`}</Text>)}
      </Box>
    )

    const groupBlock = (g: { group: ImproveGroup; label: string; rows: { id: string; mark: string; title: string; suffix: string; waiting: boolean }[]; more: number }) => (
      <Box key={`group-${g.group}`} flexDirection="column">
        <Text bold>{g.label}</Text>
        {g.rows.map(r => (
          <Box key={`row-${r.id}`} flexDirection="column">
            {isSent
              ? <Text key={`item-${r.id}`} wrap="wrap">{`  ${r.mark} ${r.title}${r.suffix}${r.waiting ? WORDS.waiting : ''}`}</Text>
              : <Button key={`item-${r.id}`} plain label={`${r.mark} ${r.title}${r.suffix}`} onPress={() => background(patch($, x => toggleOpen(x, r.id)))} />}
            {openItem !== undefined && openItem.id === r.id && detail(openItem)}
          </Box>
        ))}
        {!isSent && g.more > 0 && g.group !== 'own' && (
          <Button key={`more-${g.group}`} plain label={`${g.more} madde daha`} onPress={() => background(patch($, x => unfold(x, g.group)))} />
        )}
      </Box>
    )

    const ownCount = ownItems(s).filter(isInList).length
    let ownEl = null
    if (!isSent && ownCount < OWN_MAX) {
      ownEl = e.surface === 'mobile' || InputEl === undefined
        ? <Text key="own-mobile" dimColor wrap="wrap">{WORDS.mobileOwn}</Text>
        : (
          <InputEl key="own" label={WORDS.own} submitLabel="ekle" value={s.draft}
            onInput={(v: string) => background(patch($, x => ({ ...x, draft: v })))}
            onSubmit={(v: string) => background(patch($, x => addOwn(x, v)))} />
        )
    }

    const sendEl = isSent
      ? (
        <Box key="sent" flexDirection="column">
          <Text wrap="wrap">{WORDS.sent}</Text>
          <Button key="stop-waiting" label="Beklemeyi bırak" variant="secondary"
            onPress={() => background(patch($, x => ({ ...unreport(x), expect: '', turn: null, note: '' })))} />
        </Box>
      )
      : sendN > 0
        ? <Button key="send" label={`Gönder (${sendN})`} hotkey="g" variant="primary" onPress={() => background(sendSelection($))} />
        : <Text key="need-one" dimColor wrap="wrap">{WORDS.needOne}</Text>

    const keys = isSent ? [] : [sendN > 0 ? 'g gönder' : '', views.some(v => v.rows.length > 0) ? 'tab gezin · enter aç' : ''].filter(Boolean)
    const footer = e.props.isFocused ? keys.join(' · ') : WORDS.unfocused

    return (
      <Box flexDirection="column" rowGap={1}>
        <Box key="head" flexDirection="column">
          <Text bold wrap="wrap">{`İyileştirme: ${s.subject}`}</Text>
          {counts !== '' && <Text dimColor wrap="wrap">{counts}</Text>}
        </Box>
        {s.note === 'not-sent' && <Text key="not-sent" color="yellow" wrap="wrap">{WORDS.notSent}</Text>}
        {resultBlock}
        {extraBlock}
        {views.map(groupBlock)}
        {ownEl}
        {sendEl}
        {footer !== '' && <Text key="footer" dimColor wrap="wrap">{footer}</Text>}
      </Box>
    )
  })
}

// Press handlers kept beside the drawing: both read the list as it is when pressed, mark it and then raise the prompt.
async function sendSelection($: EngineInterface): Promise<void> {
  let text = ''
  await patch($, s => {
    if (s.phase !== 'choosing' || sendableItems(s).length === 0) return s
    text = selectionPrompt(s)
    return markSent(s)
  })
  if (text !== '') submit($, 'selection', text)
}

async function askFor($: EngineInterface): Promise<void> {
  let text = ''
  await patch($, s => {
    const ids = s.items.filter(isUnreported).map(i => i.id)
    if (s.phase !== 'choosing' || ids.length === 0) return s
    text = reportPrompt(ids)
    return askReport(s)
  })
  if (text !== '') submit($, 'report', text)
}
