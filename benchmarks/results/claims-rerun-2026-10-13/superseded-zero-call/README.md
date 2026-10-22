# Superseded: the Verinoda arm before the call-rule fix (39 sessions, no Verinoda call in any)

> **Note on paths (appendix copy).** This folder is a copy of `C:/vbench-claims-rerun/superseded-zero-call/`. Where the text below
> names `../analysis/` it means this results folder's `analysis/` (the scripts and `probe-p1-debug-excerpt.log`); `../results.jsonl`,
> `../config.json` and `../logs/` mean the results folder's `results.jsonl`, `config.json` and `logs/` (its `results.jsonl` holds the
> 24 plain rows and the 39 rows of the re-run, not the 24 alone); `../probe/` (the p2 result and the coordinator's probe folders) and
> `../usage/` of the work folder are not copied: the 39 usage logs of these sessions are in `usage/` here, and the probe results
> are summarised in the results folder's README. The results folder's own `usage/` holds the re-run's logs.

Measured data, kept as it was written. It is not part of the final comparison: the Verinoda arm is re-run on the branch with the
fixed rule. This folder says what was set aside, how, and why.

## What these are

39 `verinoda_guided` sessions of the D186 verification runs (plan Task 8, steps 5 and 6), run on 2026-10-13 (local time), harness
`benchmarks/agent_compare/claims_run.py`, model `claude-sonnet-5-5`, Claude Code 2.1.296, config `config.as-run.json` (the
Verinoda arm's prompt carries the stance only, `"guide_text": ""`; the mod's own prompt section carries the rule). Code: branch
`symbiosis-redesign-2026-10-12` at `68b2133`, working tree clean when the runs started.

| part | sessions | command (flags after the config path) | time | exit |
|---|---|---|---|---|
| the D185 re-run: six tasks x 3 repeats | 18 | `--arms verinoda_guided --repeats 3 --tasks fastapi__full-stack-fastapi-template-why-1,junegunn__fzf-why-1,guzzle__guzzle-trap-1,gin-gonic__gin-trap-1,axios__axios-when-1,sharkdp__bat-when-1` | 01:07 to 01:11 | 0 |
| the cost sample, Verinoda arm: 24 tasks x 1 repeat | 21 (3 of the 24 had been run by the first command and were skipped) | `--arms none,verinoda_guided --repeats 1 --tasks <the first 24 answerable ids of claims_tasks.order()>` | 01:16 to 01:22 | 0 |

The 24 ids of the second command, in the order given to `--tasks`: `fastapi__sqlmodel-affects-1`,
`fastapi__full-stack-fastapi-template-when-1`, `fastapi__full-stack-fastapi-template-why-1`, `gin-gonic__gin-affects-1`,
`guzzle__guzzle-affects-2`, `gin-gonic__gin-why-1`, `junegunn__fzf-affects-1`, `fastapi__sqlmodel-why-1`, `junegunn__fzf-why-1`,
`Graphify-Labs__graphify-why-1`, `sharkdp__bat-affects-1`, `expressjs__express-why-1`, `fastapi__full-stack-fastapi-template-affects-1`,
`junegunn__fzf-when-1`, `Graphify-Labs__graphify-affects-1`, `sharkdp__bat-why-1`, `expressjs__express-affects-1`,
`fastapi__sqlmodel-when-1`, `expressjs__express-when-1`, `google__gson-affects-2`, `google__gson-affects-3`, `axios__axios-affects-1`,
`guzzle__guzzle-affects-1`, `axios__axios-when-1`.

The second command also ran the 24 plain-Claude (`none`) sessions. They are the plain-Claude arm, unchanged, and stay in
`../results.jsonl`.

## What they showed

- `verinoda_calls` is 0 in all 39 rows. No ToolSearch call and no `mcp__verinoda__*` tool_use in any of the 39 transcripts; the
  first tool was Grep in 38 sessions and Bash in 1. No session error, no network lookup. Session cost as the CLI reports it:
  2.45 USD for the 39 (the 24 plain sessions: 1.38 USD).
- In all 39 sessions the mod and the server ran (each per-session usage log has exactly two lines: the mod's `graph-state` and
  the server's `mcp`), the call rule was in the system prompt (the paragraph that ends "A question one grep or one file read
  answers needs no Verinoda call."), the server's instructions were in the context, and the engine's deferred-tools reminder
  named the three core tools (`analyze`, `project_query`, `run_tool`) as deferred. The mod's `tool.describe` pin had moved them
  into the tool list all the same: probe p1's debug log (`../analysis/probe-p1-debug-excerpt.log`) has `tool.describe
  mcp__verinoda__analyze: a hook set isDeferred true -> false` (and the same for the other two) and `Dynamic tool loading: 0/19
  deferred tools included`; probe p2 (`../probe/p2/result.json`) has the model naming the three among its callable functions.
- So the Verinoda arm of these sessions is a configuration that never calls Verinoda: plain Claude Code with the stance, the
  rule text, three tool schemas and the server's instructions in its context. The per-arm dollar and model-call figures of these
  sessions measure that fixed context, not the design.

## Why superseded

No Verinoda call was made. The coordinator, while this work was paused, reported the cause as the rule's last sentence, which the
model took as a way out, together with the reminder that contradicted the pins, and reported 6 of 6 calls in its own probes of
the six re-run tasks with a reworded rule, a corrected reminder and a new `analyze` description. That is the coordinator's
statement; the probe folders that appeared in `../probe/` meanwhile (`B-*`, `B2-*`, `B3-*`, `C-*`, `P-*`) were not made by me and
I have not read them. The code change is `380e6a0` ("The call rule names the first tool call, and the engine's deferred-tools
reminder no longer contradicts the pins"), merged in `320c0b0`; the re-run uses it. The harness (`benchmarks/agent_compare/`)
is unchanged between `68b2133` and `320c0b0`.

## Files

| file | what |
|---|---|
| `results-verinoda-zero-call.jsonl` | the 39 `verinoda_guided` rows, each line byte for byte as the harness wrote it (the full answers, `session_id`, cost, turns, tool counts) |
| `results-as-run.jsonl` | `results.jsonl` as it stood when the second command ended: all 63 rows (24 plain, 39 Verinoda), a backup of the split, kept |
| `judge.jsonl` | the blind judge's rows for 27 answers (21 Verinoda: the 18 re-run answers and 3 cost-sample ones; 6 plain: fastapi when-1, sqlmodel affects-1, fastapi why-1, gin affects-1, guzzle affects-2, gin why-1); 0 judge failures |
| `mechanical.jsonl` | `claims_score.py`'s citation check of all 63 answers (both arms), written before the judging began |
| `logs/step1-rerun.log`, `logs/step2-cost-sample.log` | the two harness logs (copies; the originals stay in `../logs/`) |
| `logs/step3-score.log` | the log of the scoring run that was stopped (copy); it ends `exit=1` after 27 judged answers |
| `config.as-run.json` | the config the 63 sessions ran with (copy of `../config.json`) |
| `split-manifest.json` | counts and sha256 of what was split and moved |
| `usage/`, `usage-move-manifest.json` | the 39 per-session usage logs of these sessions (two lines each), moved here from `../usage/` on 2026-10-13 at 01:58 because the re-run's sessions write to the same file names and the logger appends; the manifest has each file's sha256 |

A session's usage log belongs to its row by name: `usage/<task id>-verinoda_guided-r<repeat>.jsonl`.

## How the split was made

`../analysis/split_superseded.py`, run at 2026-10-13 01:53 (local). `results.jsonl` (63 rows, sha256 `5acbf20b083bc2ee9521f5c97b9e31e84ad32f98baa4de3f62cf574d4a82be99`)
was split by arm without re-serialising a row: the 39 Verinoda lines (sha256 `88cef98cc7450f6304823c3ed0aa4a6de8a565f1aa33d0a691f766836cfb4b0b`)
are here, the 24 plain lines (sha256 `ddd37019ba2139f8141bc208a8f204fd70217cbb17c6d2dee2875583b8c4dd17`) are the new
`../results.jsonl`. The script checked that the two halves together are exactly the original's lines. `judge.jsonl` and
`mechanical.jsonl` were moved whole; the 6 plain judge rows in `judge.jsonl` are not copied back (the judge runs over all
answers once, at the end). The usage logs were moved by `../analysis/move_usage.py`.

## Not done

- The scoring of these sessions is incomplete: 27 of 63 answers judged, no `summary.json`, no `hand_check*` files, no
  `mechanical-strict.jsonl` (`claims_mech_strict.py` was not run). The stop was an instruction, not an error.
- The transcripts-based analysis (`../analysis/analyze_sessions.py`) was written but not run on these rows.
