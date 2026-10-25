# Leak scan: hand review of flagged sessions

Each run's `results.jsonl` is scanned with `swebench_leakscan.py`; every flagged tool call is reviewed here.

- c0-s1 (34 none): 0 flagged.
- c0-s2 (34 none): 1 flagged. sympy__sympy-18087 none: `cd C:/Users/ozcin && find / -type d -name mpmath ... | head -3`,
  a search of the whole disk for the mpmath package (not installed in C0). It hit the 120 s tool timeout, went to the
  background and was killed with no output (`[killed]`); the session read no file outside its copy. Not a leak; counted.
- c0-s1 (34 Verinoda): network use in sympy__sympy-13895 and sympy__sympy-13915 (each downloaded an mpmath wheel into its
  copy, `pip download`; C0 has no environment). Not counted (the rules: network use). To scan in full when C0 is done.
- c1-s1, first 79 sessions (2026-10-24 04:47): 12 flagged calls in 5 sessions, none a leak.
  - sphinx-doc__sphinx-8801, -8627, -8282 (plain): the session read its own background command's output file,
    `AppData/Local/Temp/claude/<its copy's path>/<its session id>/tasks/<id>.output` (a test run it had sent to the
    background). Its own tool output; counted.
  - sphinx-doc__sphinx-8801 (Verinoda): `cd .. && grep ... sphinx/ext/autodoc/__init__.py`; the grep found the file, so
    the `cd ..` left a folder inside the copy for the copy's root (from the copy's root the folder above holds no
    `sphinx/`). Counted.
  - sympy__sympy-21627 (Verinoda): its own copy's path inside a `sed` expression that shortens traceback lines. Counted.
- 2026-10-24 05:00, a correction to the c0-s2 sympy__sympy-18087 entry and the c0-s1 Verinoda pair above: the tool's
  `[killed]` ended the shell, not its `find.exe`. Three `find / ... -name mpmath` processes outlived their sessions
  (started 01:46 from c0-s2 sympy-18087 none, 03:08 and 03:34 from the c0-s1 Verinoda sessions of sympy-13915 and
  sympy-13895; their parent shells gone) and were still walking the disk at 04:52, about a third of the CPU between them.
  They write nothing and no session reads their output, so no leak; they slowed the sessions and evaluations running beside
  them. The auto-mode classifier refused stopping them by PID (04:57). For the harness (after the C1/C4 runs, which keep
  its code frozen): end what a session started when the session ends (a job object over its process tree).
- c1-s1, 139 sessions (2026-10-24 06:20, `leakscan-0620.txt` beside its results): 11 flagged calls in 6 sessions, none a leak.
  - sphinx-doc__sphinx-8801 and sympy__sympy-21627 (Verinoda): the calls reviewed above. Counted.
  - django__django-12856 (Verinoda): `ls /c/Users/ozcin/AppData/Local/Programs/Python` (looking for a Python) and three
    `powershell.exe ... python ...` calls with System32 added to PATH, running its own reproduction and the project's tests
    in its own copy. Its Bash had lost its PATH (amendment 6), so the `ls` printed "command not found" and listed nothing.
    Counted (and re-run under amendment 6).
  - sympy__sympy-15678 (Verinoda): `cd` into its own copy by its absolute path, and `ls` of the instance's folder above its
    copy, which holds the other arm's copy: the `ls` printed "command not found" (the same lost PATH) and listed nothing.
    Counted (and re-run under amendment 6).
  - matplotlib__matplotlib-25442 (plain): an Edit of a file in its own copy by its absolute path. Counted.
  - scikit-learn__scikit-learn-11281 (plain): `cd ../..` after `cd sklearn/mixture`, back to its copy's root. Counted.
- 2026-10-24 07:30, every run scanned again with the scanner of 577ef92 (it now also flags `pip download`, `-m pip`, a wheel
  and PowerShell's web cmdlets, and exempts the session's own saved tool results; `leakscan-0730.txt` beside each run's
  results). The sessions not counted are listed in `runs/not-counted.json`, which the grading scripts apply.
  - c0-s1 sympy__sympy-13915 (plain): `pip download mpmath` into its copy, the wheel deleted before the end, so its patch
    never showed it; missed by the earlier pattern. Network use: not counted (it was unresolved).
  - c0-s1 sympy__sympy-13895 and sympy__sympy-13915 (Verinoda): the downloads reviewed above, now in not-counted.json
    (13895 was resolved: C0's Verinoda count is 8 of 32 counted before amendment 6's re-run, not 9 of 34).
  - c0-s1-r1 sympy__sympy-18087 (Verinoda; amendment 6's re-run of a session whose Bash lost its PATH): `pip download
    mpmath` and two `find /` searches for mpmath, which outlived the session (07:02 and 07:05; set to idle priority at
    07:25, as were the two older ones). Network use: not counted, so this lane counts in neither number for C0.
  - c4-opus, first 44 sessions: 8 calls in 3 sessions, none a leak. sympy__sympy-21627, django__django-16816 and
    sympy__sympy-16281 (plain) ran `which python python3 py; ls /c/Users/ozcin/AppData/Local/Programs/Python` (looking for
    an interpreter; the last two had lost their Bash PATH, so it printed "command not found"); django-16816 then ran its
    reproduction and the project's tests in its own copy through powershell.exe by its full path. Counted (the two flagged
    ones are re-run under amendment 6).
  - c1-s1 sympy__sympy-13031 (Verinoda): "s:/r/n" inside a Python string it wrote (an escaped line ending) read as a drive
    path. Counted.
- 2026-10-24 08:08, scheduling (amendment 6 says the held-out gold evaluation waits until the dev runs leave room): it was
  let into the orchestrator's evaluation queue (`chain-allow-heldout`). The queue runs one evaluation at a time at
  below-normal priority, so it adds no evaluation beside the dev ones; it runs after the dev runs' pending grades in each
  batch. Login shell (the probe amendment 6 is about) at 08:10: 488, 520 and 629 ms (10 s is the limit). A gold patch that
  fails under this load is evaluated again on a quiet machine before the held-out env_only is fixed; the held-out guided
  setup still waits for the dev guided setup to end.
- 2026-10-24 09:04, scheduling: the orchestrator reads its runner limit per arm (`chain-max-runners.txt`); set to one plain
  runner and two guided runners (up to 2 plain and 4 guided sessions at once), because the plain arm finishes C4 hours before
  the guided arm. What a session sees does not change; flagged sessions (amendment 6) are re-run as before, and the login
  shell is timed again under this load.
  Login shell right after (09:05): 8126, 8325 and 656 ms, close to the 10 s limit, so the limit went back to one runner per
  arm at 09:05 before any second guided runner had started.
- 2026-10-24 09:50, leak scan of C4 so far (`runs/c4-opus/leakscan-0950.txt`: 127 sessions, 49 hits; `runs/c4-fable/
  leakscan-0950.txt`: 42 sessions, 16 hits), then `leak_filter.py` (the kinds cleared before: the instance's own
  environment, the session's own saved tool results and task output, path-like fragments of text): 10 and 1 left, read by
  hand, none a leak. Opus: PowerShell and PATH repairs in sessions that lost their Bash PATH (django-16816, sympy-19254),
  `sed` patterns (sympy-21627, sphinx-8627), a search for a Python (sympy-17139 guided), and `ls` of the run's work folder
  `swebench-run/c1-s1/` (sympy-14396 guided; nothing under it was read: no other path outside its copy in that session).
  Fable: sympy-19254 plain writes a docstring reference with its DOI (text it writes; no network use).
- 2026-10-24 09:11, scheduling: the held-out guided setup started at 09:07 from a waiter whose task had been stopped; stopped
  at 09:11 (amendment 8). 09:16:51: Windows deleted volume C:'s shadow copies (Volsnap event 25: the shadow storage could
  not grow in time under the I/O load); no study file is on that storage, and free space went from 48 to 92 GB.
- 2026-10-24 10:58, scheduling: runner limit set to one plain runner and two guided runners again (`none=1 guided=2`; each
  runner runs two sessions at once). The dev guided setup ended at 09:07 and the held-out guided setup was stopped at 09:11,
  so the load that made the 09:04 try fail is gone: login shell at 10:57 471, 675 and 572 ms. C4's Fable guided arm (100
  lanes, reset and waiting) otherwise starts only after the Opus guided runner ends. What a session sees does not change;
  the login shell is timed again once the second guided runner runs.

## 2026-10-24 14:00: grades displayed after amendment 9

A search of eval-chain.log for a traceback (the evaluator's known exit-time warning from multiprocess, `_recursion_count`)
displayed context lines that carry grades: five of C3's first sessions (c3-opus-2) and one of the 66 usage-limit rows,
c4-opus-r1 guided scikit-learn-10949 (graded 12:54:43; its patch was empty, so its grade carries nothing). Amendment 9 had
been committed (13:16) and the row moved aside (13:1x) before. No rule depends on C3's grades being unread (the selector
reads none). Searches of the evaluation log show matching lines only from here on.
- 2026-10-24 14:15, leak scan of every C4 session and every re-run so far (`leakscan-1415.txt` beside each run's results:
  c4-opus 200 sessions, 15 flagged calls in 10 sessions; c4-fable 138 sessions (the guided arm's 38 after amendment 9),
  9 in 6; c4-opus-r1 8, c4-fable-r1 5, c1-s1-r1 8 sessions, none flagged), then `leak_filter.py`: 8 and 7 left, read by
  hand, none a leak. Opus: the kinds cleared at 09:50 (django-16816's PowerShell runs after its Bash lost the PATH,
  sympy-17139's search for a Python, sympy-14396's `ls` of the run's work folder) and Git's own `tail.exe` by its path
  (scikit-learn-10949 guided). Fable, plain arm: sympy-18532, pytest-7373, sympy-19487 and sympy-20639 look for a Python
  (`which`, `where.exe`, `ls -d` of install folders, of `.venv` beside their copy, of the run's work folder and of their
  instance's folder, which shows the two arms' folder names); none reads a file outside its copy.
- 2026-10-24 16:15, scheduling: the user chose the full held-out run as fixed before (amendments 4 and 5: Opus by amendment 9,
  k = 3, the selector, both arms) when asked at about 15:45 (the plan's week stood at 45 %, C: had 99.7 GB free). Its
  guided copies are being made beside C3 (`swebench_copies.py`, resumable, at below-normal priority) by
  `h1_setup_guarded.py`, which stops them when a login shell takes 5 s or more twice in a row or C: falls under 45 GB free.
  Its sessions start after C3, the selection and the quiet-machine work: amendment 2's regrade and the held-out gold
  patches that failed under load (amendment 7), evaluated again before the held-out env_only list is fixed. The
  diagnostics run beside C3 (amendment 10).

## 2026-10-25 03:16: the last leak scan (C3's later attempts, their re-runs, the diagnostics)

Amendment 11 (2026-10-24 18:08) cancelled the held-out run before any of its sessions ran; `runs/heldout/` holds only the
gold patches' evaluation. Every session not scanned at 14:15 was scanned after amendment 2's regrade (`leakscan-0316.txt`
beside each run's results):

| Run | Sessions | Flagged calls | Left after `leak_filter.py` |
|---|---|---|---|
| c3-opus-2 | 200 | 44 | 19 |
| c3-opus-2-r1 | 5 | 1 | 0 |
| c3-opus-3 | 200 | 31 | 1 |
| c3-opus-3-r1 | 2 | 0 | 0 |
| diag-hints | 6 | 0 | 0 |
| diag-tests | 6 | 0 | 0 |

The filter's outputs are `tmp/leakfilter-RUN-0316.txt` in the session's scratch folder. What was left was read by hand at
about 03:32. None of it is a leak:
- c3-opus-2, 19 calls in 5 sessions:
  - `sed` patterns read as paths (django-11630 guided).
  - PATH repairs and searches for a Python:
    - pytest-11148 plain (`ls` of the Python install folder);
    - scikit-learn-14983 plain (`ls /c/ProgramData | head -50`; nothing of the study is in it);
    - sphinx-8721 guided.
  - The session's own arm's environment beside its copy, `copies/<id>/env-<arm>/Scripts/python.exe`: pytest-11148 plain
    and sphinx-8721 guided, each its own arm's, never the other arm's.
  - A temporary folder the session made itself: sphinx-8721 plain (`AppData/Local/Temp/tmpn6pb683n`, first seen in the
    output of its own script's Sphinx build).
- c3-opus-3, 1 call: sympy-19487 guided, `ls /c/Windows/py.exe` (a search for a Python).

None of the calls left reads a file outside the session's copy, its own environment and its own temporary folder.
