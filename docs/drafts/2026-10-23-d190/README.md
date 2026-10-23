# D190 helpers (2026-10-23)

The scripts behind the measurements of `docs/DESIGN.md` section 162.1: how one agent session used Verinoda, read from the
session's own transcript (`~/.claude/projects/<project>/<session>/subagents/agent-<id>.jsonl` for a subagent). They read
the transcript only and write nothing.

- `vcalls.py <transcript.jsonl> [<out-dir>]`: the session's model calls (context mean, median and peak; uncached input,
  cache writes and reads), its tool results by tool, and each shell command that ran the `verinoda` CLI (or an
  `mcp__verinoda` tool): its result's size, the context before and after it, and how many later model calls carried it until
  a compaction dropped it. With an out-dir, each Verinoda result's full text is saved there.
- `carry.py <transcript.jsonl>`: where the session's context went: each tool result's characters times the model calls that
  carried it afterwards (characters / 4, an estimate), summed per tool, per file read and per kind of shell command (search,
  shell reads, git history, node runs, Verinoda), and the prompt's lines that name Verinoda.

The output counts of a model call are not reliable in a transcript (a streamed message records its first block's usage);
the input side (uncached, cache writes, cache reads) is what the API reported.
