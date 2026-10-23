# Working in this repository (for coding agents)

Verinoda is a Python package (`verinoda/`, the `verinoda` CLI) that answers questions about a codebase with claims that
carry `file:line` evidence and a status. `claude-mods/verinoda-live/` is a Claude Code mod (TypeScript function hooks) that
runs beside the agent in a session.

## Where things are

- `docs/ARCHITECTURE.md`: how the package is laid out. `docs/DESIGN.md`: one numbered section per shipped decision
  (`D1` ... `D190`), each with why, what was decided, what was measured and what was not done.
- `docs/BACKLOG.md`: what is to do. `verinoda backlog 13.9` prints one item. Sections 22 and 23 are what the last redesign
  (D186, 2026-10-12; its final review and re-run 2026-10-13) left.
- `docs/CALISMA-NOTLARI.md` (Turkish): how D186 was worked (test first, lint equality, worktrees, the final review, which
  model for what, the probe method), what it taught, and the order of work after it. Read it after this file: its plan is
  the order; the improvement pane (backlog 13.9, `claude-mods/verinoda-live/IMPROVE-PANE.md`) is the feature option.
- `docs/OZELLIKLER-RAPORU.md`: every design section in three lines (Turkish).
- `docs/drafts/2026-10-22-d187-devam.md` (Turkish): where the D187 cleanup session (2026-10-22) left off, what it installed on
  this machine and what comes next; its helper scripts are beside it.
- `benchmarks/`: the harnesses and their results. `benchmarks/results/**` is measured data.
- **The mod: read `claude-mods/verinoda-live/AGENTS.md` before touching that folder.**

## Rules

- **Never edit, regenerate or reformat anything under `benchmarks/results/`.** It is what was measured. The one exception is a
  README's own prose there: a factual slip in a sentence we wrote may be corrected, the commit message saying what and why;
  a data file, a log, a script that ran, never.
- **Lint only the files you changed**: `ruff check` followed by those files. Never `ruff --fix` or a formatter over a folder:
  a broad fix once rewrote 88 result files.
- Python tests: `.venv/Scripts/python.exe -m pytest tests/test_<area>.py -q` for what you changed (`pytest tests` is the whole
  suite, about 35 minutes). No `.venv` in a fresh clone: `uv venv .venv -p 3.12` then
  `uv pip install --python .venv -e ".[mcp,precise]" pytest hypothesis ruff`. No test is known to fail (Windows 11, Python 3.12,
  2026-10-23, D190: 5423 passed, 1 failed, the timing flake below; D189: 5405 passed, 0 failed; 2026-10-22, D187): the whole
  suite gave 5388 passed and 0 failed, and in a second run 1 failed, the handle test of `tests/test_fswatch.py`, whose cause
  was the test's and was fixed (20 of 20 runs alone since). The clean checkout before D187
  (fa9d556) had 4 failures, each fixed in D187 (`docs/DESIGN.md` 159). `tests/test_asof.py::test_recorded_time` is a timing
  flake: the store records a claim's transitions to the second (`store.now`), and the test fails when its last two land in the
  same second, as in both D190 whole-suite runs; on D189's code it failed 1 of 12 and 1 of 16 runs in one warm process and
  passed that day's whole suite. `tests/test_history.py::test_a_name_resolves_through_the_index_and_is_never_replaced` failed
  once in an earlier whole-suite run and not since.
  `tests/test_tq_measured.py::test_an_edit_to_a_module_naming_imports_hides_measured` fails whenever you change an engine file
  of `tq` (the modules `tq.py` and `index.py` import, at any depth): run `verinoda benchmark tq-audit` (about 70 s) and commit
  `verinoda/data/tq_calibration.json` with its dated report folder. `pytest tests_upstream` has 37 known failures, the same on
  the clean checkout (mostly the Terraform grammar this venv lacks; `docs/UPSTREAM.md`).
  Check on a clean checkout (a `git worktree` of `HEAD`, run from its folder so it imports its own code) before you blame
  your change for any other failure.
- When a backlog item ships: add a section to `docs/DESIGN.md` under the next `D` number (why, decisions, measured, not done,
  tests), add a note to `docs/UPGRADING.md`, and delete the item's row from `docs/BACKLOG.md` (a row whose item shipped only
  in part is cut down to what is left). Code comments cite the `D` number, never a backlog id.
- Say what was measured and what was not. A result that was not measured is written "not measured", never implied. A test
  that fails is reported with its output.
- Write code that reads like the code around it: its comment density, its naming, its idiom. Comments say why, not what.
- Do not commit `.claude/`, `p.out` or anything under a `.venv`. Do not push, and do not open a pull request, unless the person
  asks. When you commit, use the author identity the last commits carry (`git log -1 --format='%an <%ae>'`).
- This is a Windows machine: paths may hold backslashes and spaces, and a Python or a shell here-document that carries
  backslashes can lose them. Write files with your file tools, not through a shell string.
