# Call-rate probes (2026-10-13): one headless session per task per variant, observations

After the first re-run showed no Verinoda call in 39 of 39 Verinoda-arm sessions (`../superseded-zero-call/`), five
variants of the mod were tried on the six re-run tasks, one `claude -p` session each, built exactly as the harness
builds a Verinoda-arm session (`claims_run.copy_for`, `setup_verinoda`, `session_argv`, `env_for`; the session's
`probe_rule.py` passed a different `--plugin-dir` and, for `P`, `PYTHONPATH` so that the MCP server imported the
worktree under test). Each folder holds the harness's `result.json` (the CLI's JSON result) and a `summary.json`
(the tool calls in order, the number of `mcp__verinoda__analyze` calls, turns, cost, session id); `index.json`
lists them all.

| variant | what changed against the first rule (`..`: the mod at 68b2133) | analyze called first |
|---|---|---|
| B | the rule's way out ("a question one grep or one file read answers needs no Verinoda call") removed; "it is in your tool list, not behind ToolSearch" added | 3 of 6 (fastapi why, guzzle trap, gin trap; not fzf why, bat when, axios when) |
| B2 | B, and a `prompt.attachment` hook that takes the three pinned tool names out of the engine's deferred-tools reminder (which said a direct call would fail) | 4 of 6 (the when-questions went to `git log -S`, both right) |
| B3 | B2, and the rule names the first tool call ("Your first tool call on a question that asks why ... is `mcp__verinoda__analyze`; Grep, Read and git come after it"), with an `analyze` description that starts "Start here for a why, when, which-commit or what-does-it-affect question" (set by the mod for the probe) | 5 of 6 (not axios when) |
| C | the first rule unchanged, plus a `prompt.submit` hook attaching one sentence of context to the user's turn | 1 of 3; the attached text was in no transcript: `prompt.submit` does not fire for a `-p` prompt, so C equals the first rule |
| P | the committed configuration (320c0b0 / 380e6a0): B3's rule, B2's hook, the server's description and status rule changed in `verinoda/mcp/server.py` instead of the mod | 6 of 6 |

Costs in `summary.json` are not comparable between variants: a variant's first sessions write a new system-prompt
prefix to the prompt cache and six concurrent sessions each paid for it (B3 and P: $0.12-0.14 a session; B2, whose
prefix B had cached minutes before: $0.03-0.05). The re-run's 24 pairs are the cost measurement; these are not.

Not measured: more than one session per task per variant; the answers' correctness (the re-run's judge grades the
re-run's answers, not these); whether the two when-questions would call `analyze` more often than 1 of 2 in B3.
