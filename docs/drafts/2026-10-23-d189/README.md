# D189 helpers (2026-10-23)

The scripts behind `docs/DESIGN.md` section 161. Copy the folder to a scratch place before running: they write their outputs
beside themselves, and their paths (the transcripts folder, the person's projects, the repository) are this machine's.

- `compose.py <out.json> <transcript.jsonl>...`: what fills a long session: characters per category (tool results by tool,
  the model's tool inputs, its text, the person's, the attachments by type), images apart, compactions, and each model call's
  context size as the API reported it.
- `shrink_sim.py <out.json> <transcript.jsonl>...`: a lower inline limit for tool results (above it the first 2,000 and the
  last 1,000 characters), simulated on the recorded results and the calls that read each again before the next compaction.
- `compact_sim2.py <transcript.jsonl>...`: an earlier auto-compaction simulated on the recorded growth of the context; the
  967k window is the check (it reproduced 96-109 % of the recorded reads on the four big sessions).
- `cycle_files.py <transcript.jsonl> <root>`: the files the busiest compaction cycle read or edited under a root, in the
  mod's order (edited first, then the latest reads), for timing `verinoda card` on real files.
- `compact_probe.py`, `compact_probe2.py`: a throwaway headless session with the working tree's mod and CLI: three files read,
  then `/compact`; the summary and the `card` row of `VERINODA_USAGE_LOG`. They call the model (sonnet, a few cents each).
