// What the verinoda-live pane draws from, held by the host for the session (the check setting is also kept in the
// mod's store across sessions).

// The index as the pane shows it; every kind has a glyph and words, colour only reinforces them.
export type IndexKind =
  | 'checking' // the session-start check is running
  | 'fresh' // nothing waiting, no build running
  | 'pending' // edits waiting for the end of the turn (or for a running graph build: `waiting`)
  | 'updating' // `verinoda update --fast` is running
  | 'graph' // the text is in; the graph is rebuilt in the background (2-4 min on this repository)
  | 'behind' // the graph is behind with no build coming (files changed outside Claude's edit tools)
  | 'slow' // the watcher gave up after 10 minutes
  | 'failed' // the last update failed; its files are kept
  | 'unknown' // the graph state could not be read
  | 'noindex' // no .verinoda in the project
  | 'untrusted' // the .verinoda found is in an ancestor the person did not open or trust: nothing runs (D186)

export type IndexState = {
  kind: IndexKind
  n: number // files the state is about (pending, updating, graph, behind, failed)
  waiting: boolean // pending while a graph build runs: they go in when it ends
  since: number | null // ms: when the graph build started (graph)
  at: number | null // ms: when the index was last seen fresh in this session
  error: string // failed: the first line of the CLI's error; untrusted: the folder with the index
}

export type Notice = { text: string; tone: 'ok' | 'warn' | 'err' }

// The last check of an edit (`verinoda check`): what the model was told, for the pane.
export type CheckInfo = {
  file: string // the edited file, relative to the project
  n: number // names reported absent or mismatched on the edited lines
  ok: boolean // false: the check could not run (the edit went through all the same)
  at: number // ms
}

// The improvement checklist pane (D175): one list the model proposed and the person marks, then what came of it.
export type ImproveGroup = 'problem' | 'improvement' | 'taste' | 'own'
export type ImproveDecision = 'none' | 'apply' | 'keep' | 'check'
export type ImproveStatus = 'waiting' | 'applied' | 'partial' | 'failed' | 'not_confirmed' | 'unreported'

export type ImproveItem = {
  id: string // the model's id, or u1, u2, ... for the person's own
  group: ImproveGroup
  title: string // an own item: the person's text
  observation: string
  why: string
  change: string
  cost: string // '' when none was given
  evidence: string[]
  seen: boolean // taste: judged from a rendered view
  verified: boolean // a check confirmed it
  checked: string // the note of the check that confirmed it, else ''
  decision: ImproveDecision // an own item: always 'apply'
  sentAs: 'apply' | 'check' | null // what it was last sent as
  outcome: { status: ImproveStatus; note: string; evidence: string[] } | null
}

export type ImproveState = {
  phase: 'idle' | 'reviewing' | 'choosing' | 'sent'
  subject: string
  items: ImproveItem[] // the model's in rank order, then the person's own
  open: string | null // the item whose details are shown
  unfolded: ImproveGroup[] // groups whose folded items were opened
  extra: string[] // changes the model reported that were not on the list
  draft: string // what the own-item field holds
  ownSeq: number // the last number given to an own item; never reused in a session
  expect: '' | 'review' | 'selection' | 'report' // the prompt that was submitted and whose turn has not started
  queue: '' | 'review' // the review prompt waits for the command's own turn to end: the host refuses a submit from a command's hook
  turn: string | null // the id of the mod's own turn in flight
  note: '' | 'no-list' | 'not-sent'
}

declare module 'claude-code' {
  // The tools the mod registers (the improvement list's), so a `tool.call` hook can name them and read their arguments.
  interface McpToolInputs {
    'mcp__verinoda-live__improve_propose': {
      subject: string
      items: { id: string; group: 'problem' | 'improvement' | 'taste'; title: string; observation: string; why: string;
        change: string; cost?: string; evidence?: string[]; seen?: boolean }[]
    }
    'mcp__verinoda-live__improve_report': {
      outcomes: { id: string; status: 'applied' | 'partial' | 'failed' | 'confirmed' | 'not_confirmed'; note: string; change?: string; evidence?: string[] }[]
      extra_changes?: string[]
    }
  }

  interface PluginState {
    'verinoda-live': {
      status: string
      idx: IndexState
      notice: Notice | null
      check: boolean // check every edit of a Python, Java or Kotlin file (off unless the setting or /verinoda-check turns it on)
      lastCheck: CheckInfo | null
      improve: ImproveState // the improvement checklist pane's whole state
    }
  }
}
