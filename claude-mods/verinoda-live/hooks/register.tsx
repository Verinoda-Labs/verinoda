import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { CheckInfo, ImproveState, IndexKind, IndexState, Notice } from '../types'
import { IMPROVE_SPECS, initialImprove, reviewPrompt, undoSend } from './improve'
import { COMMAND as IMPROVE_COMMAND, endOfTurn, improveSections, mod as improveMod, registerImprove } from './improve-pane'
import { frameRows, MASCOT_HEIGHT, MASCOT_WIDTH } from './mascot'
import type { MascotProps, Mood } from './mascot'

const PANE = 'verinoda'
const GRAPH_POLL_MS = 1_000
const GRAPH_WAIT_MS = 10 * 60_000
// Unlocked yet behind this long: no build is coming (files changed outside Claude's edit tools).
const GRAPH_STALL_MS = 15_000
// The host's longest wait for a process (10 min). `verinoda update` itself waits up to 600 s for the build lock, so
// the mod never starts one while its own background build holds it (reindex defers to the watcher instead).
const UPDATE_TIMEOUT_MS = 600_000
const TRUST_TIMEOUT_MS = 20_000
const NOTICE_MS = 6_000
const EDIT_TOOLS = ['Edit', 'Write', 'NotebookEdit'] as const
// the Verinoda MCP server's tools, as the model names them; the three of its core profile are listed in front
const MCP_TOOL_PREFIX = 'mcp__verinoda__'
const MCP_CORE_TOOLS = ['mcp__verinoda__analyze', 'mcp__verinoda__project_query', 'mcp__verinoda__run_tool'] as const

// After each edit of a file `verinoda check` reads (Python, Java, Kotlin), the names the edited lines use that do not
// exist in the project or its environment are told to the model with the edit's result. Off unless asked (D186 §4.4):
// 0 notes in 65 edits of the guard study, an absent name in 3 of 99 SWE-bench calls and none acted on. A cached check
// takes about 3 s; the edit never waits longer than CHECK_TIMEOUT_MS for it.
const CHECKABLE = /\.(py|pyi|java|kt|kts)$/i
const CHECK_TIMEOUT_MS = 60_000
const CHECK_NOTE_MAX = 8

// The call rule (D186 §4.6), a section of the system prompt while the Verinoda MCP server is connected. The tools listed
// in front alone did not make the model call them (one headless session: Grep, Read, Read, Bash); with this paragraph it
// called analyze first, confirmed the lead with `git show` and cited the commit that states the reason (546dc8b) where
// two sessions without it asserted the history gives none. The one own check it asks for costs about one model call on
// history questions and is priced in the design's cost model (1.1-1.2x of plain Claude Code, modelled).
export const RULE_SECTION = 'verinoda-live:rule'
export const CALL_RULE =
  'For a why, when or what-does-it-affect question about this repository, call `mcp__verinoda__analyze` once with the ' +
  'question first: it returns a verdict and leads with file:line and commits. Its output is a lead, not the answer: ' +
  "confirm with one git or grep check of your own before stating 'no such change', 'first added in' or why something " +
  'changed. `statically_verified` and `primary_source_verified` claims are verified; `strong_inference` and below are ' +
  'not. A question one grep or one file read answers needs no Verinoda call.'

const CHECKING: IndexState = { kind: 'checking', n: 0, waiting: false, since: null, at: null, error: '' }

// Session state the drawing reads (declared in ../types); the check setting is also kept in $.store across sessions.
const status = atom({ plugin: 'verinoda-live', key: 'status' } as const, '')
const idx = atom({ plugin: 'verinoda-live', key: 'idx' } as const, CHECKING)
const notice = atom({ plugin: 'verinoda-live', key: 'notice' } as const, null as Notice | null)
const check = atom({ plugin: 'verinoda-live', key: 'check' } as const, false)
const lastCheck = atom({ plugin: 'verinoda-live', key: 'lastCheck' } as const, null as CheckInfo | null)
// the improvement list's state (D175); ./improve-pane.tsx declares the same source, because the scan reads an atom where it is used
const improve = atom({ plugin: 'verinoda-live', key: 'improve' } as const, initialImprove())

// Where Verinoda runs from, settled at session start (D186 §4.6: nothing the mod runs comes from the opened repository).
// `cli` is the program: the setting's path when it lies outside the project, else what PATH names outside the project,
// else the bare name. `cwd` is the working directory of every run: the user's home (a drive root without one), never
// the repository, because Windows searches a child's working directory before PATH and whether $.process.run does is
// unverified; `--repo` names the project. The settings' `python` went with the python probe (`verinoda graph-state`).
const cfg = { cli: 'verinoda', cwd: '', check: false, motion: true }

// Module state: a reload starts it over, which only forgets edits not yet indexed.
const live = {
  root: undefined as string | undefined,
  cwd: '',
  isAllowed: false, // the root is the session's folder, the one the settings name, or trusted with `verinoda trust`
  pending: new Set<string>(),
  isChecking: true, // the session-start look at the graph has not answered yet
  isRunning: false,
  runningCount: 0,
  isGraphBehind: false,
  graphSince: null as number | null,
  graphFiles: 0,
  stalledBehind: 0, // files the graph is behind on with no build coming; /verinoda-update takes them in
  isSlow: false,
  isUnknown: false,
  failed: null as { n: number; error: string } | null,
  freshAt: null as number | null,
}

export function norm(p: string): string {
  return p.replace(/\\/g, '/').replace(/\/+$/, '').toLowerCase()
}

// slashes made forward, case kept: a case-sensitive file system finds a folder only as it is spelled
const slashes = (p: string) => p.replace(/\\/g, '/').replace(/\/+$/, '')

export function isCheckable(path: string): boolean {
  return CHECKABLE.test(path)
}

type CheckSite = { at?: string; path?: string; expr?: string; name?: string; verdict?: string; message?: string;
  nearest?: { name?: string }[] }

// A file under the project, relative to it, slashes forward and case kept (it is shown and passed on as spelled).
function relPath(root: string, file: string): string {
  const r = root.replace(/\\/g, '/').replace(/\/+$/, '')
  return file.replace(/\\/g, '/').slice(r.length + 1)
}

function badSites(report: { sites?: CheckSite[] }, rel: string): CheckSite[] {
  return (report.sites ?? []).filter(s =>
    (s.verdict === 'absent' || s.verdict === 'mismatch') && norm(s.path ?? '') === norm(rel))
}

// The note the model reads after an edit, one line: the edited file's sites `verinoda check` found absent or mismatched
// (an unknown is not checked, so it is never reported), each with the nearest real names; undefined when there are none,
// which is nearly always (D186 §4.4), so a note is rare and short.
export function checkNote(root: string, file: string, report: { sites?: CheckSite[] }, cli: string): string | undefined {
  const rel = relPath(root, file)
  const bad = badSites(report, rel)
  if (bad.length === 0) return undefined
  const sites = bad.slice(0, CHECK_NOTE_MAX).map(s => {
    const near = (s.nearest ?? []).map(n => n.name).filter(Boolean).slice(0, 3)
    return `${s.at ?? rel} ${s.expr ?? s.name ?? ''}: ${s.message ?? s.verdict}${near.length ? ` (nearest: ${near.join(', ')})` : ''}`
  })
  const more = bad.length > CHECK_NOTE_MAX ? ` (+${bad.length - CHECK_NOTE_MAX} more: ${cli} check --diff --repo ${root})` : ''
  const what = bad.length === 1 ? 'a name that does' : `${bad.length} names that do`
  return `[Verinoda check] The lines you changed in ${rel} use ${what} not exist in this project or its environment ` +
    `(a static check; runtime-made names are never reported): ${sites.join('; ')}${more}`
}

// Work left running after a hook returns (a re-index, the graph watcher): a reload or the end of the session aborts
// its $ calls, which is no error of the person's, so the rejection is dropped here.
function background(work: Promise<unknown>): void {
  work.catch(() => undefined)
}

function plural(n: number): string {
  return `${n} file${n === 1 ? '' : 's'}`
}

function isInside(path: string, root: string): boolean {
  const p = norm(path)
  const r = norm(root)
  return p === r || p.startsWith(`${r}/`)
}

// Is the Verinoda MCP server connected? The request's tool list names its tools; a `.mcp.json` would only say it is
// configured. No index is needed: the server indexes the project it was set up for.
export function isServerConnected(tools: readonly string[] | undefined): boolean {
  return (tools ?? []).some(t => t.startsWith(MCP_TOOL_PREFIX))
}

// The index state from the module's fields, as the pane reads it and as the status line says it (in English, as the
// slash commands do). The first matching rule wins: a running update over a failure, a failure over waiting edits.
export function indexState(): { state: IndexState; line: string } {
  const base = { waiting: false, since: null, at: live.freshAt, error: '' }
  const at = (kind: IndexKind, n: number, line: string, extra: Partial<IndexState> = {}) =>
    ({ state: { ...base, kind, n, ...extra }, line })
  if (live.root === undefined) return at('noindex', 0, `no .verinoda index at or above ${live.cwd}`)
  if (!live.isAllowed) return at('untrusted', 0, `index at ${live.root} not trusted · verinoda trust ${live.root}`, { error: live.root })
  if (live.isRunning) return at('updating', live.runningCount, `updating (${plural(live.runningCount)})…`)
  if (live.failed !== null) {
    return at('failed', live.failed.n, `update failed · ${plural(live.failed.n)} kept for /verinoda-update`, { error: live.failed.error })
  }
  if (live.pending.size > 0) return at('pending', live.pending.size, `${plural(live.pending.size)} pending`, { waiting: live.isGraphBehind })
  if (live.isGraphBehind) return at('graph', live.graphFiles, 'text fresh · graph pending…', { since: live.graphSince })
  if (live.stalledBehind > 0) return at('behind', live.stalledBehind, `graph behind ${plural(live.stalledBehind)} · /verinoda-update`)
  if (live.isSlow) return at('slow', 0, 'graph build still running (10 min+)')
  if (live.isUnknown) return at('unknown', 0, 'graph state unknown')
  if (live.isChecking) return at('checking', 0, 'checking…')
  return at('fresh', 0, 'fresh ✓')
}

function publish($: EngineInterface): void {
  const { state, line } = indexState()
  $.ui.status(live.root === undefined ? undefined : `Verinoda: ${line}`)
  // the pane's copy is best effort: a write refused after the module unloaded is dropped
  update($, status, () => line).catch(() => undefined)
  update($, idx, () => state).catch(() => undefined)
}

async function setCheck($: EngineInterface, value: boolean): Promise<void> {
  await update($, check, () => value)
  await $.store.set('check', value)
}

// The check after edits starts from the setting (`userConfig.check`, off unless set); what the person chose last with
// /verinoda-check is kept in the store and wins. A scripted session (`claude -p`, the Agent SDK) has nobody at the
// keyboard, so what was chosen there is not read: it takes the settings (`pluginConfigs`) as they are given. (The store
// is shared by every session that loads the mod and rewritten by each at its end: a choice made once in a terminal
// would otherwise reach the arms of a study that never asked for it, and did.)
async function loadSettings($: EngineInterface, isInteractive: boolean): Promise<void> {
  const stored = isInteractive ? await $.store.get('check') : undefined
  await update($, check, () => (typeof stored === 'boolean' ? stored : cfg.check))
}

// Every run of the CLI: the resolved program, the user's home as the working directory, the project named with --repo.
function runCli($: EngineInterface, args: string[], timeoutMs?: number) {
  return $.process.run([cfg.cli, ...args], { cwd: cfg.cwd, ...(timeoutMs === undefined ? {} : { timeoutMs }) })
}

// `check --diff` reads the lines changed against HEAD (and new files whole); a project without git, or a diff the
// CLI cannot read, falls back to the edited file whole. Exit 3 (something absent) and 4 (something not checked) are
// answers too. Whatever happens, the edit itself has already gone through.
async function runCheck($: EngineInterface, root: string, file: string): Promise<{ sites?: CheckSite[] } | undefined> {
  for (const args of [['check', '--diff', '--json', '--repo', root], ['check', file, '--json', '--repo', root]]) {
    try {
      const { exitCode, stdout } = await runCli($, args, CHECK_TIMEOUT_MS)
      if (exitCode !== 0 && exitCode !== 3 && exitCode !== 4) continue
      const report = JSON.parse(stdout) as { sites?: CheckSite[] }
      if (typeof report === 'object' && report !== null) return report
    } catch {
      return undefined // a timeout or a CLI that will not start: the second command would wait as long
    }
  }
  return undefined
}

async function checkEdit($: EngineInterface, root: string, file: string): Promise<string | undefined> {
  const report = await runCheck($, root, file)
  const note = report === undefined ? undefined : checkNote(root, file, report, cfg.cli)
  const at = await $.clock.now()
  const rel = relPath(root, file)
  const n = report === undefined ? 0 : badSites(report, rel).length
  await update($, lastCheck, () => ({ file: rel, n, ok: report !== undefined, at }))
  return note
}

type GraphState = { locked: boolean; behind: number }

// `update --fast` takes the text in at once and rebuilds the graph in a background `verinoda update`. The graph has
// caught up when no build holds the lock and no file changed since the latest snapshot (the background build records
// it); the lock alone misses a build that has not taken it yet. `verinoda graph-state` answers both (D186: the CLI's
// own subcommand; the mod used to run a python of its own for this, `-c` with the repository as its working directory,
// which put the repository first on sys.path).
async function graphState($: EngineInterface, root: string): Promise<GraphState | undefined> {
  try {
    const { exitCode, stdout } = await runCli($, ['graph-state', '--repo', root, '--json'])
    if (exitCode !== 0) return undefined
    const d = JSON.parse(stdout) as Partial<GraphState>
    return typeof d.locked === 'boolean' && typeof d.behind === 'number' ? { locked: d.locked, behind: d.behind } : undefined
  } catch {
    return undefined
  }
}

// One look at the graph (session start, or the pane's "check again"): fresh, a build to watch, or behind.
async function checkGraph($: EngineInterface): Promise<void> {
  const root = live.root
  if (root === undefined || !live.isAllowed || live.isRunning || live.isGraphBehind) return
  live.isChecking = true
  live.isUnknown = false
  live.isSlow = false
  publish($)
  const state = await graphState($, root)
  live.isChecking = false
  if (state === undefined) live.isUnknown = true
  else if (state.locked) background(watchGraph($, root, state.behind))
  else if (state.behind > 0) live.stalledBehind = state.behind
  else live.freshAt = await $.clock.now()
  publish($)
}

// One watcher at a time; a later update while it runs only keeps it going.
async function watchGraph($: EngineInterface, root: string, files: number): Promise<void> {
  if (live.isGraphBehind) return
  live.isGraphBehind = true
  live.graphFiles = files
  live.stalledBehind = 0
  live.isSlow = false
  live.isUnknown = false
  const started = await $.clock.now()
  live.graphSince = started
  publish($)
  let idleSince: number | undefined // first poll that saw no build running while behind
  try {
    while ((await $.clock.now()) - started < GRAPH_WAIT_MS) {
      await $.clock.sleep(GRAPH_POLL_MS)
      if (live.isRunning) {
        idleSince = undefined
        continue
      }
      const state = await graphState($, root)
      if (state === undefined) {
        live.isUnknown = true
        return
      }
      const now = await $.clock.now()
      if (state.locked || state.behind === 0) idleSince = undefined
      else idleSince ??= now
      const isStalled = idleSince !== undefined && now - idleSince >= GRAPH_STALL_MS
      if (state.behind === 0 || isStalled) {
        live.stalledBehind = isStalled ? state.behind : 0
        if (!isStalled) live.freshAt = now
        return
      }
    }
    live.isSlow = true
  } finally {
    live.isGraphBehind = false
    live.graphSince = null
    publish($)
    if (live.pending.size > 0 && !live.isRunning) background(reindex($)) // edits made while the build ran
  }
}

async function exists($: EngineInterface, path: string): Promise<boolean> {
  return (await $.fs.stat(path).catch(() => undefined)) !== undefined
}

// The project: the folder the settings name, else the nearest one at or above the session's with a .verinoda index.
async function findRoot($: EngineInterface, named: string, cwd: string): Promise<string | undefined> {
  if (named !== '') return (await exists($, `${slashes(named)}/.verinoda`)) ? slashes(named) : undefined
  // a home folder or a drive root is never taken for a project unless the settings name it (Verinoda's own first
  // scan refuses them too): every edit anywhere under it would re-index it
  const homes = new Set<string>()
  const profile = await $.env.get('USERPROFILE').catch(() => undefined)
  const home = await $.env.get('HOME').catch(() => undefined)
  for (const h of [profile, home]) if (h) homes.add(norm(h))
  let dir = slashes(cwd)
  for (let i = 0; i < 40 && dir !== ''; i++) {
    const isTooWide = homes.has(norm(dir)) || /^[A-Za-z]:$/.test(dir) || dir === ''
    if (!isTooWide && (await exists($, `${dir}/.verinoda`))) return dir
    const up = dir.replace(/\/[^/]*$/, '')
    if (up === dir || /^[A-Za-z]:$/.test(dir)) break
    dir = up
  }
  return undefined
}

// The user's home, where every run of the CLI starts; without one (neither variable set), the drive root, which is
// outside any project the mod would take (findRoot refuses drive roots).
async function homeFolder($: EngineInterface, root: string): Promise<string> {
  const profile = await $.env.get('USERPROFILE').catch(() => undefined)
  const home = await $.env.get('HOME').catch(() => undefined)
  for (const v of [profile, home]) if (typeof v === 'string' && v.trim() !== '') return slashes(v.trim())
  const drive = /^[A-Za-z]:/.exec(root)
  return drive === null ? '/' : `${drive[0]}/`
}

// The program as PATH names it, outside the project: the first folder of PATH that is not inside the root and holds
// it (with a PATHEXT extension on Windows); undefined when none does. Nothing is run to find it (`where` would itself
// be a program found by the child's own search), and the project's own .venv on PATH (an activated one) is skipped.
async function fromPath($: EngineInterface, name: string, root: string): Promise<string | undefined> {
  const path = await $.env.get('PATH').catch(() => undefined)
  if (typeof path !== 'string' || path === '') return undefined
  const isWindows = /^[A-Za-z]:/.test(root)
  const pathext = isWindows ? await $.env.get('PATHEXT').catch(() => undefined) : undefined
  const exts = isWindows
    ? (typeof pathext === 'string' && pathext !== '' ? pathext : '.EXE;.CMD;.BAT').split(';').map(x => x.trim().toLowerCase()).filter(Boolean)
    : ['']
  for (const entry of path.split(isWindows ? ';' : ':')) {
    const dir = slashes(entry.trim().replace(/^"|"$/g, ''))
    if (dir === '' || isInside(dir, root)) continue
    for (const ext of exts) {
      const candidate = `${dir}/${name}${ext}`
      const found = await $.fs.stat(candidate).catch(() => undefined)
      if (found !== undefined && found.kind !== 'dir') return candidate
    }
  }
  return undefined
}

// The program and the working directory of every run (D186 §4.6: the mod never runs anything from the opened
// repository, not even a `.venv` it ships). A `cli` setting is taken when it is a bare name (looked up on PATH like the
// default) or a path outside the root; a path inside the root, or on a network share, is refused like a found one.
async function resolveTools($: EngineInterface, root: string, options: Record<string, unknown>): Promise<void> {
  cfg.cwd = await homeFolder($, root)
  const given = typeof options.cli === 'string' ? slashes(options.cli.trim()) : ''
  const isPath = /[/\\]/.test(given)
  if (given !== '' && isPath && !isInside(given, root) && !given.startsWith('//')) {
    cfg.cli = given
    return
  }
  const name = given !== '' && !isPath ? given : 'verinoda'
  cfg.cli = (await fromPath($, name, root)) ?? name
}

// Is the root a project the person trusted (`verinoda trust`)? The list is read through the CLI (its file lives in the
// user's config dir), once per session; a list that cannot be read trusts nothing.
async function isTrusted($: EngineInterface, root: string): Promise<boolean> {
  try {
    const { exitCode, stdout } = await runCli($, ['trust', '--list', '--json'], TRUST_TIMEOUT_MS)
    if (exitCode !== 0) return false
    const d = JSON.parse(stdout) as { trusted?: { path?: unknown; subfolders?: unknown }[] }
    const key = norm(root)
    return (Array.isArray(d.trusted) ? d.trusted : []).some(e => {
      if (typeof e.path !== 'string') return false
      const p = norm(e.path)
      // with `subfolders` every folder below counts, except one under a .verinoda folder (reference checkouts live there)
      return key === p || (e.subfolders === true && key.startsWith(`${p}/`) && !key.slice(p.length + 1).split('/').includes('.verinoda'))
    })
  } catch {
    return false
  }
}

// What a re-index came to: `text` is the command's answer (English, as before); `code` lets the pane say it.
type Outcome = {
  code: 'noindex' | 'untrusted' | 'running' | 'graph-fresh' | 'fresh' | 'waiting' | 'updated' | 'failed'
  n: number
  text: string
}

async function reindex($: EngineInterface): Promise<Outcome> {
  const { root, pending } = live
  if (root === undefined) return { code: 'noindex', n: 0, text: `no .verinoda index at or above ${live.cwd}` }
  if (!live.isAllowed) {
    return { code: 'untrusted', n: 0, text: `the index at ${root} is in a folder above the session's that is not trusted: ` +
      `run \`verinoda trust ${root}\` or start Claude Code in it` }
  }
  if (live.isRunning) return { code: 'running', n: live.runningCount, text: 'an update is already running' }
  if (pending.size === 0 && live.isGraphBehind) {
    return { code: 'graph-fresh', n: 0, text: 'text index fresh; the graph is still being rebuilt' }
  }
  if (pending.size === 0 && live.stalledBehind === 0 && live.failed === null) return { code: 'fresh', n: 0, text: 'index already fresh' }
  if (live.isGraphBehind) {
    // the background build holds the lock; `update` would wait for it, so the files wait instead
    publish($)
    return { code: 'waiting', n: pending.size, text: `waiting for the graph build; ${plural(pending.size)} will be indexed when it ends` }
  }

  live.isRunning = true
  const files = [...pending]
  const stalled = live.stalledBehind
  const count = files.length || stalled || live.failed?.n || 0
  live.runningCount = count
  pending.clear()
  live.stalledBehind = 0
  live.failed = null
  live.isSlow = false
  live.isUnknown = false
  const fail = (error: string) => {
    files.forEach(f => live.pending.add(f))
    live.stalledBehind = Math.max(live.stalledBehind, stalled)
    live.failed = { n: count, error }
  }
  publish($)
  try {
    const { exitCode, stderr } = await runCli($, ['update', '--fast', '--repo', root], UPDATE_TIMEOUT_MS)
    if (exitCode !== 0) {
      fail(`çıkış ${exitCode}: ${stderr.trim().split('\n').pop()?.slice(0, 160) ?? ''}`)
      return { code: 'failed', n: count, text: `update failed (exit ${exitCode}): ${stderr.slice(0, 300)}` }
    }
    live.isRunning = false
    background(watchGraph($, root, count))
    return { code: 'updated', n: count, text: `text index updated (${plural(count)}); the graph is rebuilt in the background` }
  } catch (err) {
    fail(String(err).slice(0, 160))
    return { code: 'failed', n: count, text: `update failed: ${String(err)}` }
  } finally {
    live.isRunning = false
    publish($)
  }
}

const NOTICE_TEXT: Record<Outcome['code'], (n: number) => Notice> = {
  noindex: () => ({ text: 'Bu projede index yok', tone: 'err' }),
  untrusted: () => ({ text: 'Klasöre güvenilmiyor · verinoda trust', tone: 'err' }),
  running: n => ({ text: `Zaten güncelleniyor (${n} dosya)`, tone: 'ok' }),
  'graph-fresh': () => ({ text: 'Metin güncel · graph hâlâ kuruluyor', tone: 'ok' }),
  fresh: () => ({ text: 'Index zaten güncel', tone: 'ok' }),
  waiting: n => ({ text: `Graph bitince ${n} dosya eklenecek`, tone: 'ok' }),
  updated: n => ({ text: `Güncellendi (${n} dosya) · graph arka planda kuruluyor`, tone: 'ok' }),
  failed: () => ({ text: 'Güncelleme başarısız · ayrıntı yukarıda', tone: 'err' }),
}

// The pane's update button: run it, and say what happened under the button for a few seconds.
async function updateFromPane($: EngineInterface): Promise<void> {
  const outcome = await reindex($)
  const said = NOTICE_TEXT[outcome.code](outcome.n)
  await update($, notice, () => said)
  await $.clock.sleep(NOTICE_MS)
  await update($, notice, n => (n === said ? null : n))
}

async function recheckFromPane($: EngineInterface): Promise<void> {
  await update($, notice, () => ({ text: 'Kontrol ediliyor…', tone: 'ok' }))
  await checkGraph($)
  await update($, notice, () => null)
}

async function registerImproveTools($: EngineInterface): Promise<void> {
  for (const spec of IMPROVE_SPECS) {
    await $.tool.register({ name: spec.name, description: spec.description, inputSchema: spec.inputSchema as unknown as Record<string, unknown> })
  }
}

export function settingCommand(arg: string, current: boolean): boolean | undefined {
  const a = arg.trim().toLowerCase()
  if (a === '') return !current
  if (a === 'on' || a === 'açık' || a === 'ac' || a === 'aç') return true
  if (a === 'off' || a === 'kapalı' || a === 'kapat') return false
  return undefined
}

// ---- the pane's words, pictures and layout (pure: tested without the engine) ----------------------------------

export function hhmm(ms: number | null): string {
  if (ms === null) return '--:--'
  const d = new Date(ms)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

export type Tone = 'ok' | 'busy' | 'warn' | 'err' | 'idle'
export const TONE_COLOR: Record<Tone, string> = { ok: 'green', busy: 'cyan', warn: 'yellow', err: 'red', idle: 'gray' }
export type Action = 'update' | 'retry' | 'recheck'

// Every state as a glyph, words and a tone; the glyph and words carry the meaning, the colour only reinforces it.
export function describeIndex(s: IndexState): { head: string; tone: Tone; details: string[]; action: Action | null } {
  switch (s.kind) {
    case 'checking': return { head: '◌ Kontrol ediliyor…', tone: 'idle', details: [], action: null }
    case 'fresh': return { head: '✓ Index güncel', tone: 'ok', details: [s.at === null ? 'bu oturumda değişiklik yok' : `son kontrol ${hhmm(s.at)}`], action: null }
    case 'pending':
      return s.waiting
        ? { head: `● ${s.n} dosya bekliyor`, tone: 'warn', details: ['graph bitince eklenecek'], action: null }
        : { head: `● ${s.n} dosya bekliyor`, tone: 'warn', details: ['tur bitince kendiliğinden güncellenir'], action: 'update' }
    case 'updating': return { head: `◐ Güncelleniyor · ${s.n} dosya`, tone: 'busy', details: [], action: null }
    case 'graph':
      return { head: s.n > 0 ? `◐ Graph kuruluyor · ${s.n} dosya` : '◐ Graph kuruluyor', tone: 'busy',
        details: [`${hhmm(s.since)}'den beri · genelde 2-4 dk`, 'Metin araması şimdiden güncel'], action: null }
    case 'behind': return { head: `▲ Graph ${s.n} dosya geride`, tone: 'warn', details: ["Claude'un dışında değişen dosyalar"], action: 'update' }
    case 'slow': return { head: "▲ Graph kurulumu 10 dk'yı geçti", tone: 'warn', details: [], action: 'recheck' }
    case 'failed': return { head: `✗ Güncelleme başarısız · ${s.n} dosya bekletiliyor`, tone: 'err', details: [s.error], action: 'retry' }
    case 'unknown': return { head: '? Graph durumu okunamadı', tone: 'idle', details: [], action: 'recheck' }
    case 'noindex': return { head: "? Bu projede Verinoda index'i yok", tone: 'idle', details: ['Proje klasöründe çalıştır:', 'verinoda init, sonra verinoda update'], action: null }
    case 'untrusted':
      return { head: "▲ Üstteki klasörün index'ine güvenilmiyor", tone: 'warn',
        details: [s.error, `izin için: verinoda trust ${s.error}`, "ya da Claude Code'u o klasörde başlat"], action: null }
  }
}

export const ACTION_LABEL: Record<Action, string> = { update: 'Şimdi güncelle', retry: 'Tekrar dene', recheck: 'Tekrar kontrol et' }
export const CHECK_HINT = "Python/Java/Kotlin düzenlemesindeki var olmayan isimler Claude'a söylenir"

export function checkLine(c: CheckInfo | null): { text: string; tone: Tone } | null {
  if (c === null) return null
  if (!c.ok) return { text: `Son kontrol çalışmadı: ${c.file} (düzenleme yapıldı)`, tone: 'warn' }
  if (c.n === 0) return { text: `Son kontrol: ${c.file} · temiz`, tone: 'idle' }
  return { text: `Son kontrol: ${c.file} · ${c.n} isim bulunamadı, Claude'a söylendi`, tone: 'warn' }
}

// The mascot (./mascot.tsx) is drawn by the surface as a `Client`, animated there; a surface without `Client`
// (VS Code, mobile) gets its first frame, still.
const ANIMATED_SURFACES = ['terminal', 'desktop']
const MOOD: Record<Tone, Mood> = { ok: 'idle', idle: 'idle', busy: 'busy', warn: 'warn', err: 'err' }

export function mascotCaption(s: IndexState): { text: string; tone: Tone } {
  if (s.kind === 'failed') return { text: 'Bir şey ters gitti', tone: 'err' }
  if (s.kind === 'untrusted') return { text: 'İzin bekliyor', tone: 'warn' }
  if (s.kind === 'pending' || s.kind === 'behind' || s.kind === 'slow') return { text: 'Güncelleme bekliyor', tone: 'warn' }
  if (s.kind === 'updating' || s.kind === 'graph' || s.kind === 'checking') return { text: 'Kodu okuyorum…', tone: 'busy' }
  if (s.kind === 'noindex') return { text: 'Index yok', tone: 'idle' }
  return { text: 'Her şey güncel', tone: 'idle' }
}

// Rows a line takes at this width (a wrapped line may take several).
export function rowsOf(text: string, columns: number): number {
  return Math.max(1, Math.ceil(text.length / Math.max(1, columns)))
}

export const register: Register = (on, options) => {
  registerImprove(on)

  on('session.start', async ($, e, next) => {
    live.cwd = await $.session.cwd()
    cfg.check = options.check === true
    cfg.motion = options.motion !== false
    const named = typeof options.root === 'string' ? options.root.trim() : ''
    live.root = await findRoot($, named, live.cwd)
    live.isAllowed = false
    if (live.root !== undefined) {
      await resolveTools($, live.root, options)
      // the index is used where the person chose it: the folder they opened, the one their settings name, or one they
      // trusted with `verinoda trust`; a .verinoda in an ancestor they never opened is not, so a hostile repository's
      // index can make the mod run nothing (D186 §4.6)
      live.isAllowed = named !== '' || norm(live.root) === norm(live.cwd) || (await isTrusted($, live.root))
    }
    await loadSettings($, e.isInteractive !== false)
    // the improvement list (D175): its command is always there, its tools only for a person and when a list is in play or offered
    improveMod.interactive = e.isInteractive !== false
    improveMod.offered = options.improveOffer === true
    await $.command.register(IMPROVE_COMMAND)
    if (improveMod.interactive && (improveMod.offered || (await read($, improve)).phase !== 'idle')) await registerImproveTools($)
    await $.command.register({ name: 'verinoda-update', description: 'Re-index the files edited this session now.' })
    await $.command.register({ name: 'verinoda-check', description: 'Check each edit of Python/Java/Kotlin code for names that do not exist: on, off, or toggle.' })
    // not plain `verinoda`: the Verinoda agent skill of that name takes `/verinoda` first
    await $.command.register({ name: 'verinoda-panel', description: 'Open the Verinoda pane: index state and the check setting.' })
    publish($)
    background(checkGraph($))
    return next(e)
  })

  // The server's core tools are first-class: their schemas in the prompt's list, not behind ToolSearch, where the agent
  // studies found a tool that must first be looked up is not called (0 of 286 sessions with the tools deferred; `locate`
  // listed in front was called in 51 of 63), and the ToolSearch turn that loads them costs a model call (D186). In this
  // build a plugin's or a server's tool is deferred unless a hook says not. The descriptions stay the server's.
  on('tool.describe', { tool: [...MCP_CORE_TOOLS] }, ($, e) => ({ description: e.description, isDeferred: false }))

  // The call rule rides the system prompt while the server is connected; the improvement list's offer (D175) with it.
  on('prompt.compose', async ($, e, next) => {
    const out = await next(e)
    const sections = improveSections(out.sections)
    if (!isServerConnected(e.tools)) return sections === out.sections ? out : { sections }
    return { sections: [...sections, { id: RULE_SECTION, text: CALL_RULE, scope: 'session' as const }] }
  })

  on('tool.call', { tool: EDIT_TOOLS }, async ($, e, next) => {
    const ran = await next(e)
    const root = live.root
    if (root === undefined || !live.isAllowed || ran.deny !== undefined || ran.isError === true) return ran

    const path = e.tool === 'NotebookEdit' ? e.notebook_path : e.tool === 'Edit' || e.tool === 'Write' ? e.file_path : undefined
    const file = path === undefined ? '' : norm(path)
    if (!file.startsWith(`${norm(root)}/`) || file.includes('/.verinoda/')) return ran
    live.pending.add(file)
    publish($)
    if (path === undefined || !isCheckable(path) || !(await read($, check))) return ran
    // the edit has gone through: nothing the check does may change that
    const note = await checkEdit($, root, path.replace(/\\/g, '/')).catch(() => undefined)
    return note === undefined ? ran : { ...ran, context: [...(ran.context ?? []), note] }
  })

  // One re-index per turn, not per edit; left running so the turn ends at once.
  on('turn.complete', async ($, e, next) => {
    const improving = await read($, improve)
    if (e.agentId === undefined && improving.turn !== null && e.turnId === improving.turn) await update($, improve, endOfTurn)
    // the improvement review waits for the command's own turn to end: a submit from the command's hook is refused by the host
    if (e.agentId === undefined && improving.queue === 'review') {
      await update($, improve, (s: ImproveState) => ({ ...s, queue: '' as const, expect: 'review' as const, turn: null, note: '' as const }))
      const failed = () => update($, improve, (s: ImproveState) => (s.expect === 'review' ? undoSend(s, 'review') : s))
      background($.prompt.submit({ text: reviewPrompt(improving.subject), asUser: true }).then(r => (r.drop === undefined ? undefined : failed()), failed))
    }
    if (e.agentId === undefined && live.pending.size > 0 && !live.isRunning) background(reindex($))
    return next(e)
  })

  on('command.run', { command: 'verinoda-update' }, async $ => ({ text: (await reindex($)).text }))

  on('command.run', { command: 'verinoda-check' }, async ($, e) => {
    const value = settingCommand(e.args, await read($, check))
    if (value === undefined) return { text: 'usage: /verinoda-check [on|off]' }
    await setCheck($, value)
    return { text: `check after edits ${value ? 'on' : 'off'}` }
  })

  on('command.run', { command: 'verinoda-panel' }, async $ => {
    await $.ui.open({ id: PANE, title: 'Verinoda', focus: true })
    return { text: 'Verinoda pane opened.' }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Button, Text } = $.ui.resolve(e)
    const s = await read($, idx)
    const said = await read($, notice)
    const isCheck = await read($, check)
    const lastChk = await read($, lastCheck)

    const columns = Math.max(20, e.props.bodyColumns ?? 48)
    const isInline = e.props.placement === 'inline'
    const bodyRows = e.props.scroll?.bodyRows ?? 0
    const tone = (t: Tone) => TONE_COLOR[t]
    let used = 0 // rows the content takes, counted while the tree is built, to know what is left for the mascot
    const count = (text: string) => { used += rowsOf(text, columns) }

    // 1 · the index
    const ix = describeIndex(s)
    const action = ix.action
    const indexBlock = (
      <Box key="index" flexDirection="column">
        <Text bold color={tone(ix.tone)} wrap="wrap">{ix.head}</Text>
        {!isInline && ix.details.map((d, i) => <Text key={`d${i}`} dimColor wrap="truncate">{`  ${d}`}</Text>)}
        {action !== null && (
          <Button key="update" label={ACTION_LABEL[action]} hotkey="u" variant={action === 'recheck' ? 'secondary' : 'primary'}
            onPress={() => background(action === 'recheck' ? recheckFromPane($) : updateFromPane($))} />
        )}
        {said !== null && (
          <Text key="notice" color={said.tone === 'err' ? 'red' : said.tone === 'warn' ? 'yellow' : undefined}
            dimColor={said.tone === 'ok'} wrap="truncate">{`  ${said.text}`}</Text>
        )}
      </Box>
    )
    count(ix.head)
    if (!isInline) used += ix.details.length
    if (action !== null) used += 1
    if (said !== null) used += 1

    // nothing runs in these two states, so a setting would do nothing and is not drawn
    if (s.kind === 'noindex' || s.kind === 'untrusted') return <Box flexDirection="column">{indexBlock}</Box>

    // 2 · the check after edits: a two-option control; k always flips it; the last check under it
    const lastLine = checkLine(lastChk)
    const checkEl = (
      <Box key="check" flexDirection="column">
        <Box flexDirection={columns < 40 ? 'column' : 'row'} columnGap={1}>
          <Text bold={!isInline}>{isInline ? 'Kontrol' : 'Kod kontrolü'}</Text>
          <Button key="check-on" label={isCheck ? '● Açık' : 'Açık'} hotkey={isCheck ? undefined : 'k'}
            variant={isCheck ? 'primary' : 'secondary'} onPress={() => (isCheck ? undefined : setCheck($, true))} />
          <Button key="check-off" label={isCheck ? 'Kapalı' : '● Kapalı'} hotkey={isCheck ? 'k' : undefined}
            variant={isCheck ? 'secondary' : 'primary'} onPress={() => (isCheck ? setCheck($, false) : undefined)} />
        </Box>
        {!isInline && <Text dimColor wrap="wrap">{CHECK_HINT}</Text>}
        {lastLine !== null && (
          <Text key="check-last" dimColor={lastLine.tone === 'idle'} color={lastLine.tone === 'warn' ? 'yellow' : undefined}
            wrap="truncate">{lastLine.text}</Text>
        )}
      </Box>
    )
    if (!isInline) {
      used += 2 + (columns < 40 ? 2 : 0) // the row (stacked when narrow) and the gap above it
      count(CHECK_HINT)
      if (lastLine !== null) used += 1
    }

    if (isInline) {
      return (
        <Box flexDirection="column">
          {indexBlock}
          <Box flexDirection="row" columnGap={2} flexWrap="wrap">{checkEl}</Box>
        </Box>
      )
    }

    // 3 · footer: only the keys that exist in this drawing
    const keys = [action !== null ? 'u güncelle' : '', 'k kontrol'].filter(Boolean)
    const footer = e.props.isFocused ? keys.join(' · ') : 'Kısayollar için ctrl+x tab'
    used += 2 // the footer and the gap above it

    // 4 · the mascot, only in the room left over: never cropped, never pushing content
    const spare = bodyRows - used
    const caption = mascotCaption(s)
    const showMascot = columns >= 24 && spare >= MASCOT_HEIGHT + 3
    const mascotProps: MascotProps = {
      mood: MOOD[caption.tone], caption: caption.text, captionColor: tone(caption.tone), captionDim: caption.tone === 'idle',
    }
    const { Client } = $.ui.resolve(e) as { Client?: (props: Record<string, unknown>) => JSX.Element }
    const mascot = !showMascot ? null : (
      <Box key="mascot" flexDirection="column" alignItems="center" marginTop={Math.max(0, spare - MASCOT_HEIGHT - 3)}>
        {Client !== undefined && cfg.motion && ANIMATED_SURFACES.includes(e.surface)
          ? <Client key="mascot-client" module="./mascot.tsx" props={mascotProps} width={MASCOT_WIDTH} height={MASCOT_HEIGHT + 1} />
          : (
            <Box flexDirection="column" width={MASCOT_WIDTH}>
              {frameRows(0, mascotProps.mood).map((row, i) => (
                <Text key={`m${i}`} wrap="truncate">
                  {row.map(([text, c], j) => (c === null ? text : <Text key={`m${i}-${j}`} color={c}>{text}</Text>))}
                </Text>
              ))}
              <Text color={mascotProps.captionColor} dimColor={mascotProps.captionDim} wrap="truncate">{caption.text}</Text>
            </Box>
          )}
      </Box>
    )

    return (
      <Box flexDirection="column" rowGap={1}>
        {indexBlock}
        {checkEl}
        {mascot}
        <Text dimColor wrap="truncate">{footer}</Text>
      </Box>
    )
  })
}
