// File cards for the compaction (D189): which files a conversation read or edited, and what the summarizer is told.
// Pure: no `$`; register.tsx runs `verinoda card` and passes the cards on (session.compact).
//
// A long session reads its whole history again with every request; the compaction is what makes it small again,
// and what its summary keeps of a file is the model's memory of it. Verinoda reads each file the conversation touched
// (its path and length, what it is for, its top-level definitions, its imports) and the summarizer is asked to keep
// that one line instead of the file's text; a later turn reads again what it needs. In the person's sessions a
// compaction cycle touched 67 files at the median (93 at the 90th percentile, under the 967k window); 40 cards of a
// real cycle took 0.67 s to make and 7,834 characters.

export const CARD_FILES = 40
export const CARD_CHARS = 8000
export const CARD_TIMEOUT_MS = 20_000

const FILE_TOOLS: Readonly<Record<string, string>> = {
  Read: 'file_path', Edit: 'file_path', MultiEdit: 'file_path', Write: 'file_path', NotebookEdit: 'notebook_path',
}

export type ToolUse = { tool: string; input: Readonly<Record<string, unknown>> }
export type Message = { toolUses?: readonly ToolUse[] }

// The files the messages read or edited under `root`, repository-relative (slashes forward, case kept): the edited
// ones first, then the read ones, each newest first, none under a `.verinoda` folder or climbing out with `..`, at most
// `max`. A path the model gave is only matched against the root here; `verinoda card` judges it again before reading.
export function touchedFiles(messages: readonly Message[], root: string, max = CARD_FILES): string[] {
  const base = root.replace(/\\/g, '/').replace(/\/+$/, '')
  const prefix = `${base.toLowerCase()}/`
  const edited: string[] = []
  const read: string[] = []
  for (const message of [...messages].reverse()) {
    for (const u of [...(message.toolUses ?? [])].reverse()) {
      const key = FILE_TOOLS[u.tool]
      const raw = key === undefined ? undefined : u.input[key]
      if (typeof raw !== 'string') continue
      const p = raw.replace(/\\/g, '/')
      if (!p.toLowerCase().startsWith(prefix)) continue
      const rel = p.slice(prefix.length)
      if (rel === '' || rel.split('/').some(s => s === '..' || s === '.' || s.toLowerCase() === '.verinoda')) continue
      ;(u.tool === 'Read' ? read : edited).push(rel)
    }
  }
  return [...new Set([...edited, ...read])].slice(0, max)
}

export const CARDS_HEAD = "Verinoda's cards of the files this conversation read or edited, read from the files on disk now. " +
  'In the summary keep each of these files as its card, not its contents; a later turn reads again what it needs:'

// What the summarizer is told: what it was told already (a `/compact <focus>`, another plugin's) first, then the cards.
export function cardInstructions(existing: string | undefined, cards: string): string {
  return [existing?.trim() ?? '', `${CARDS_HEAD}\n${cards.trim()}`].filter(s => s !== '').join('\n\n')
}
