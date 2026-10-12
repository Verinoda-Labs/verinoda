# Verdict audit before and after D186 (2026-10-13)

The verdict audit runs every case of the verdict corpus (39 questions over seven small projects, 22 controls that
must stay answered and 17 traps that must not be answered as fact) through `analyze` and grades each answer
against its gold: `met`, `met_with_inference`, `not_supported` or `unmet`, plus `wrong_met` (a trap answered as
fact) and `above_ceiling` (a status higher than the case allows). D186 (the "Verinoda Lean" redesign,
`docs/DESIGN.md`) changed the analyze answer shape, the why/when handlers, the status rule and history; this folder
holds the audit before the redesign and after each of its two code waves, so a reader can see what the redesign
changed in the answers and what it did not change in the grades.

## What ran

Command, identical for the three runs, from the repository root of the commit named:

```
verinoda benchmark verdict-audit --split all
```

| file | commit | tree |
|---|---|---|
| `before-feae584.json` | feae584 | the branch point of D186 (the commit before wave 1), run in a detached worktree of that commit |
| `after-wave1-7fc52be.json` | 7fc52be | the merged tree after wave 1 (Tasks 1, 2, 5, 6 and the review minors) |
| `after-wave2-f34a223.json` | f34a223 | the merged tree after wave 2 (Tasks 3 and 4) |

The JSON schema is `verinoda.verdict_audit_result/1`. It does not record the commit; the commits above come from the
session ledger. Each run took under a minute; the `seconds` field of a row is the wall time of one `analyze` call
and varies between runs (0.1 to 10 seconds), so it is not compared below.

## Grades: unchanged

| run | cases | met | met_with_inference | not_supported | unmet | wrong_met | above_ceiling | controls kept | traps |
|---|---|---|---|---|---|---|---|---|---|
| before, all | 39 | 16 | 13 | 3 | 7 | 1 (forge-maxheat-declared) | 0 | 15/22 | 17 |
| after, all | 39 | 16 | 13 | 3 | 7 | 1 (forge-maxheat-declared) | 0 | 15/22 | 17 |
| before, dev | 23 | 9 | 9 | 1 | 4 | 0 | 0 | 9/13 | 10 |
| after, dev | 23 | 9 | 9 | 1 | 4 | 0 | 0 | 9/13 | 10 |
| before, held_out | 16 | 7 | 4 | 2 | 3 | 1 (forge-maxheat-declared) | 0 | 6/9 | 7 |
| after, held_out | 16 | 7 | 4 | 2 | 3 | 1 (forge-maxheat-declared) | 0 | 6/9 | 7 |

"after" is the wave-2 file; the wave-1 file is identical to it in every field but `seconds`, so wave 2 (history
as one list, the status rule in the text) changed no row of this corpus.

Row by row: all 39 rows carry the same verdict, the same `wrong_met`, the same `above_ceiling` and the same
sub-question statuses before and after. The seven controls lost before are the same seven lost after:
`pyloop-why-adr`, `webui-renderlist-callers`, `glow-config-load-callers`, `forge-addheat-callers`,
`mixmod-coolall-callers`, `forge-maxheat-declared`, `verinoda-mcp-size-env`. The one `wrong_met`
(`forge-maxheat-declared`, a control graded as a trap by the corpus's own rule) is the same before and after.

The plan's acceptance line for this step was "equal or better than wrong_met 1/39, above_ceiling 0, controls kept
15/22": equal.

## Answers: shorter in 12 rows

The grades did not move, but the answer text did, in 12 of the 39 rows. The claims listed as the answer got fewer in
every one of them; no row gained a line. Two D186 decisions explain all 12:

- **A why-question whose reason was not found no longer lists "lines were changed in `<sha>`" as a claim** (five
  rows). The commit is still named, inside the `unknown` ("the reason was not found: 1 commit(s) changed these
  lines and none states a reason about it in its message; no decision record explains it") together with the next
  step, instead of standing as an answer to a question it does not answer.
- **A claim that does not answer the sub-question is no longer listed as an answer** (seven rows): "X is defined
  at", a text match, or a call edge that the question did not ask about. The `unknown` carries what was not found.

| id | kind | verdict (same before and after) | answer lines before, after | what changed |
|---|---|---|---|---|
| pyloop-why-pause | trap | unmet | 1, 0 | history line dropped; unknown reworded |
| webui-useauth-components | trap | unmet | 2, 0 | definition lines dropped |
| glow-wisp-ticked | trap | unmet | 5, 0 | definition and text-match lines dropped |
| verinoda-lock-why | trap | met_with_inference | 4, 3 | history line dropped |
| mixmod-spark-ticked | trap | unmet | 3, 0 | definition lines dropped |
| orders-not-called-by-handlers | trap | not_supported | 6, 0 | call lines dropped (see below) |
| orders-why-commit | trap | met_with_inference | 2, 1 | history line dropped |
| webui-useauth-components-tr | trap | unmet | 1, 0 | definition line dropped |
| pyloop-why-adr | control | met_with_inference | 2, 1 | history line dropped |
| mixmod-lamp-ticked | control | met | 4, 2 | definition lines dropped |
| forge-blockentity-ticked | control | met | 3, 1 | definition lines dropped |
| orders-why-sqlite | control | met | 2, 1 | history line dropped |

`orders-not-called-by-handlers` asks which functions of a module the HTTP handlers do not call. Before, the answer
listed six call edges, among them two functions the handlers do call, and the gold check marked those two as
wrong; after, the answer lists nothing and the gold check marks the one right function as missing. The verdict is
`not_supported` in both runs: the question is a set difference that no check computes, and the `unknown` says so in
both.

## What was not measured

- Whether a reader or a model does better with the shorter answers. The grades above are the corpus's rule applied
  to the claims; they do not grade the `unknown` text or the next steps.
- The eight public benchmark sets after D186 are in `../compare-2026-10-13-after-d186/`; the D185 re-run and the
  cost sample are in `../claims-rerun-2026-10-13/`. This folder is the verdict corpus only.
- Timing: `seconds` differs between the runs by up to a factor of two on the same row in both directions; the runs
  were not timed under controlled load.
