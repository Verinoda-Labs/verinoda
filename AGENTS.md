# Working in this repository (for coding agents)

Verinoda is a Python package (`verinoda/`, the `verinoda` CLI) that answers questions about a codebase with claims that
carry `file:line` evidence and a status. `claude-mods/verinoda-live/` is a Claude Code mod (TypeScript function hooks) that
runs beside the agent in a session.

## Where things are

- `docs/ARCHITECTURE.md`: how the package is laid out. `docs/DESIGN.md`: one numbered section per shipped decision
  (`D1` ... `D186`), each with why, what was decided, what was measured and what was not done.
- `docs/BACKLOG.md`: what is to do. `verinoda backlog 13.9` prints one item. Sections 22 and 23 are what the last redesign
  (D186, 2026-10-12; its final review and re-run 2026-10-13) left.
- `docs/CALISMA-NOTLARI.md` (Turkish): how D186 was worked (test first, lint equality, worktrees, the final review, which
  model for what, the probe method), what it taught, and the order of work after it. Read it after this file: its plan is
  the order; the improvement pane (backlog 13.9, `claude-mods/verinoda-live/IMPROVE-PANE.md`) is the feature option.
- `docs/OZELLIKLER-RAPORU.md`: every design section in three lines (Turkish).
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
  `uv pip install --python .venv -e ".[mcp,precise]" pytest hypothesis ruff`. Six tests failed on a clean checkout before
  your change (Windows 11, Python 3.12, 2026-10-10) and are not yours: `tests/test_agents.py::test_skill_templates_are_complete`
  for `claude` and for `codex` (a template body is 243 and 242 lines long where the test allows fewer than 240),
  `tests/test_consolidate.py::test_the_later_verification_is_kept`, `tests/test_grep_ast.py::test_bounds_are_said`,
  `tests/test_query_language.py::test_budgets_cut_the_answer_and_say_so` and
  `tests/test_tq_measured.py::test_an_edit_to_a_module_naming_imports_hides_measured`; `tests/test_asof.py::test_recorded_time`
  fails now and then in a whole-suite run and passes alone. Seen since D186 (2026-10-13), each on this tree, not on a clean
  checkout: the two skill-length cases pass; `tests/test_consolidate.py::test_the_later_verification_is_kept` and
  `tests/test_history.py::test_a_name_resolves_through_the_index_and_is_never_replaced` pass alone (the second failed in one
  whole-suite run); `tests/test_trigram.py::test_two_searches_at_once_do_not_fail` and the handle test of `tests/test_fswatch.py`
  fail now and then in a whole-suite run. The whole suite was not re-run on a clean checkout after D186 (backlog 23.5).
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
