# D188 helpers (2026-10-23)

The scripts behind `docs/DESIGN.md` section 160. Copy the folder to a scratch place before running: they write their outputs
beside themselves, and their paths (the transcripts folder, the results file, the installed `verinoda.exe`) are this machine's.

- `tokcount.py <out.json> <file>...`: exact token counts, free and local. Each file becomes a rule file of an empty project
  (cut in pieces under 1,000 tokens: `/context` rounds larger rows), `claude -p "/context"` lists every memory file with its
  tokens, a one-character file gives the wrapper (8 tokens) to subtract. No model call.
- `fixedctx.py`: `/context`'s MCP rows with the installed server and the working tree's, in a project and in the home folder.
- `sessions.py` + `turns.py`: the D186 re-run's transcripts per session (model calls, the first request's size, each Verinoda
  result and the calls that read it again) and the token-reads of the fixed text against the results'.
- `realuse.py`: the person's own sessions (not the benchmark copies): every Verinoda call and its result's size.
- `variants.py`: the recorded analyze results as compact JSON, JSON with two trims, text, text with the trims (for `tokcount.py`).
