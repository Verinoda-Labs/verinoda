# SWE-bench Lite: how far can Claude Code with Verinoda go? (pre-registration, 2026-10-23)

The person who owns Verinoda asked for the way to 100 of 100 resolved on the study of `DESIGN_SWEBENCH.md` (D184: 72 of 100 in
each arm). This file fixes, before any change to the agents' set-up, what is allowed, what is measured, on which instances, and
in what order. It is written after looking at the 28 failures of the Verinoda arm (the dev set below) and before any re-run.

## What is known before any change

From the 100 instances of D184, the leaderboard's own per-instance results (github.com/SWE-bench/experiments, `evaluation/lite`,
84 submissions up to 2025-09; `evaluation/verified`, 175 submissions with results) and OpenAI's SWE-bench Verified annotation
(`ensembled_annotations_public.csv`: per instance, whether the issue is underspecified and whether the tests may reject valid
solutions, each 0-3, and `filter_out`):

- 18 of the 100 instances were resolved by none of the 84 Lite submissions; 13 of the Verinoda arm's 28 failures are among them
  (5 of the 18 were resolved by one or both arms of D184).
- 22 of the 28 failures are `filter_out` instances (annotated as underspecified or as having tests that reject valid
  solutions); 3 are not annotated; 3 are annotated fair (`sympy__sympy-17630`, `astropy__astropy-14182`,
  `django__django-13158`). On the 31 instances annotated fair, the Verinoda arm resolved 28 and the plain arm 30.
- The annotators' notes name, for many failures, a detail the hidden tests demand and the issue does not state (a new config
  name, error code E109 instead of E108, an exact message, a printing format, a specific variant of a bound).

So 100 of 100 is not expected to be reachable without information the benchmark withholds. This study measures how far the
legitimate levers go and says, per instance, why the rest is not reached.

## Rules (what counts as the agent's result)

A session sees the issue text and the repository at the base commit, nothing more. Never in a session's reach: the gold patch,
the test patch, the names of the FAIL_TO_PASS tests, the hints (issue comments), commits after the base commit, the web.
Concretely: the dataset and the run's own files (`tasks.json`, results, predictions) live outside the folder tree the sessions
work in; every session's transcript is scanned afterwards for paths outside its copy and for network use, and a session that
reached any of them is reported and not counted. Git history given to a session holds only the base commit's ancestors, with no
remote and no tags newer than the base, checked by asserting that no commit is newer than the base commit (the official 5.x
images do the same; the "git peek" of earlier images is what this prevents). A condition that uses the hints would be a
separate, labelled condition; none is planned. A result that used any withheld information is never reported as Verinoda's.

## Instances

- Dev set: the 100 instances of D184 (the first 100 of the seeded order, sha256("20261010:" + instance_id)). Everything below is
  developed and tuned on them.
- Held-out set: instances 101-200 of the same order (`heldout100.txt` in the run's data folder; 37 django, 23 sympy, 10
  scikit-learn, 9 matplotlib, ...). Not inspected per instance before the final run. The final claim is made on it, both arms,
  one configuration fixed before it runs.

## Evaluation

No Docker on this machine. `swebench_localeval.py` evaluates on Windows: per instance a venv from the task repo's Dockerfile
(Python version and frozen packages), the eval script's test command on a clean base checkout with the patch and the test patch,
SWE-bench's own log parser and grading. It is checked against the official evaluation of D184 (its 200 patches) before it is used
to judge anything; its agreement is reported. Tests that fail locally with the gold patch are environment failures: a
"calibrated" grade leaves them out and says so. Every local number is labelled local. Official numbers need the Docker evaluation
(`SWEBENCH_DOCKER_TALIMAT.md`) and are reported as not measured until it runs.

## Conditions, in this order

- C0, noise floor: D184's prompt and harness, more sessions on the dev failures, both arms. What flips here is sampling, and no
  change below is credited with it. Gives pass@k for the unchanged method (a diagnostic, never a resolved share: choosing among k
  attempts with the hidden tests is not allowed). Amended before any run (same day): the Verinoda installed now is a7e0c65
  (D186-D190), not the code of 2026-10-10 that D184 ran; C0 uses it, so C0 against D184 mixes sampling with that change, and
  C0's own repeats are the noise floor.
- C1, the official image's working environment, both arms: the instance's venv on PATH with the checkout importable, the base
  commit's whole history in the checkout (SWE-bench 5.x's images carry it; D184's copies were one commit deep, which also left
  Verinoda's history tools blind), and the prompt says how to run the project's tests and that the agent should reproduce the
  issue and run the related tests. Same prompt otherwise. Amended before any run: history was first planned for C2 and the
  Verinoda arm only; given to one arm it would be credited to Verinoda.
- C2, Verinoda's own changes, Verinoda arm only: engine and protocol changes that each name a defect seen in a dev-set
  transcript (first the six instances only the plain arm resolved). No change names an instance.
- C3, more attempts with a legitimate selector, both arms: k sessions per instance and a selector that sees only the issue, the
  candidate patches and the test environment (it may run existing tests and its own reproductions, never the hidden tests).
  k and the selector are fixed on the dev set before the held-out run.

Measures: resolved (local strict and calibrated; official when available), paired difference with a bootstrap 95 % interval,
exact McNemar on discordant pairs, cost (dollars, turns, seconds). A lever that lifts both arms equally is reported as not
Verinoda's. Per instance that stays unresolved: the reason (the test's demand and whether the issue, the code or only the hints
determine it).

## Amendment 2 (2026-10-24, after C0's first plain-arm sessions, before any C1 session)

- C0's copies. Resetting D184's copies in place was stopped. Each C0 repeat gets fresh copies instead
  (`swebench_copies.py`), checked out at the base commit and borrowing D184's plain copies' objects through git alternates.
  D184's copies stay as its sessions left them. Their object stores hold dangling blobs that D184's harness wrote (`git add
  -A` before the diff). One is visible from a C0 copy (`git fsck --unreachable`). A session that ran `git fsck`,
  `git cat-file --batch-all-objects` or a lost-found search could read D184's plain patch. The leak scan looks for these
  commands; a session that ran one is reported and not counted.
- C1's copies. No session ever works in the pool. Both arms' copies borrow from the fetched history copy, so neither arm can
  reach the other's objects.
- C1 where the environment works. An instance gets C1 (the environment and the reproduce-and-test prompt) only if the gold
  patch resolves it locally in that environment (calibrated grade). Otherwise both arms' sessions get C0's prompt, which says
  dependencies are not installed, and no environment. Results are reported split this way. A prompt that calls a broken
  environment "ready" would only cost turns.
- The Verinoda arm's C1 guide. GUIDE told the session to "work in this order" and ended at `code_check`. That is the shortcut in
  D184's transcripts: analyze, edit, code_check, done. Next to C1's own order (reproduce, fix, run the script and the tests) it
  would give two orders. GUIDE_C1 keeps GUIDE's three uses of Verinoda (load the tools, analyze before reading, code_check
  after editing). It places them inside the C1 steps and says `code_check` does not replace the reproduction or the tests. This
  is a change to the Verinoda arm's protocol made together with C1. It cannot be told apart from C1 without another run, and it
  is reported that way.
- Versions from setuptools_scm. The copies carry no tags. Sessions and the evaluator therefore get
  `SETUPTOOLS_SCM_PRETEND_VERSION` set to the instance's version plus ".0". pytest's `src/_pytest/_version.py`, which its own
  install would generate, is written into the checkout as an ignored file. Without it, every pytest test failed to import
  locally: four of the five instances where the local and official plain-arm grades disagreed.
- Grading. A local "unresolved" is graded again once on a quiet machine before it is counted, because sleep-based tests flake
  under load (django-16379). Instances whose project needs a compiled build (scikit-learn, matplotlib, astropy) are graded
  locally only once their gold patch passes here. Until then they are "official grading only": not measured locally.
- The environment, as built before C1 (same day).
  - The project's install runs with its dependencies, as in the image. The environment file lacks what the project's own
    install adds there: sphinx's sphinxcontrib packages, and pytest's atomicwrites and colorama on Windows.
  - On Windows, packages that load a missing system library are removed (xarray: cfgrib, eccodes).
  - Where numpy 1.19.2 and scipy 1.5.2 have no Windows wheel for Python 3.9, numpy 1.19.5 and scipy 1.5.4 are installed
    instead. Each environment's marker file records this.
  - A compiled project is built once per instance at its base commit with MSVC (`build_outputs`). Its build outputs are
    copied into each checkout of that instance and imported through PYTHONPATH. A patch that touches compiled sources is
    built again in place.
  - A session never gets an editable install of its checkout. The evaluator's editable install in a shared environment
    points at the evaluator's checkout, which holds a patch and the test patch while it runs, and the evaluator now resets that
    checkout after each run. A session imports its own checkout through PYTHONPATH (from `src/` for pytest and flask), in one of
    two venvs:
    - the shared environment (django, sympy, requests, Python 3.6, compiled projects), which holds no such install of a
      patched checkout;
    - otherwise a venv of its own with the same packages as the shared one, as the gold patch's evaluation left it.

## Amendment 3 (2026-10-24, before C1's first session)

- The environment, made to pass every gold patch it can. The gold patch now resolves locally on 99 of the 100 dev
  instances (calibrated grade). The exception is django-13658, whose FAIL_TO_PASS test fails here with the gold patch, so
  it is not graded locally. What it took, beyond amendment 2:
  - pytest before 7.2 needs atomicwrites on Windows, which the image's Linux freeze lacks; it is added where `import
    pytest` asks for it (every scikit-learn test failed to collect without it);
  - the image's pip (24.2) where scikit-learn's install line uses `--no-use-pep517`, which pip 26 dropped;
  - Visual Studio's msbuild on PATH for a compiled build (matplotlib before 3.6 builds its freetype with it);
  - `MPLBACKEND=Agg`, for the evaluator and C1 sessions: the image has no display, and matplotlib's Tk backend failed
    seaborn-2848's tests here;
  - a compiled build no longer leaves its editable install in the shared environment (it pointed every user of the
    environment at the build folder and showed sessions the data folder); for matplotlib before 3.7, a `.pth` puts
    `mpl_toolkits` in `sys.modules` from the checkout on PYTHONPATH without running its `__init__.py`, as the image's
    develop-mode `-nspkg.pth` does (otherwise pkg_resources' deprecation warning, an error under pytest.ini, stopped
    every test of matplotlib 22835, 23964 and 25442).
- The evaluator's agreement with the official grade of D184's 200 patches, with every gold report: calibrated 99 of
  100 in the plain arm and 98 of 100 in the Verinoda arm (strict: 93 and 91). Every difference: django-13658 in both arms
  (not gradable locally), and django-16379 in the Verinoda arm, resolved here and not officially (its test sleeps; see
  amendment 2's re-grading).
- C1's harness. A file a session changes or adds with CRLF where the base commit has no CR gets LF back before the patch
  is taken: rewriting a file through Python's text mode from Bash writes CRLF on Windows and LF on the image's Linux (a
  37-line change of C0's django-11019 became a 2163-line diff). C0 keeps D184's harness. A session's row records what
  changed at the top of a shared environment's site-packages while it ran, and a session's PATH names the shared
  environment through a junction outside the data folder.
- The leak scan also flags the other arm's copy of the same instance (it sits beside the session's copy and holds that
  arm's patch), by an absolute or a relative path, and a `cd ..`.
- C1's order. The plain arm's sessions start while the Verinoda arm's 100 copies are being set up (about five minutes
  each). The compiled instances run after the environment check of their sessions (`mpl_toolkits` above was found
  there, after the plain arm's first non-compiled sessions and before any matplotlib session).

## Amendment 4 (2026-10-24, during C1's first run, before any session of the conditions it adds)

- What C1's first sessions show (local calibrated grades, 39 plain-arm and 10 Verinoda-arm sessions): every unresolved one
  misses a FAIL_TO_PASS test, and only two also break an existing test. In django-14730 both arms wrote the same patch,
  character for character, and it fails on one word of the warning the hidden test demands ("i.e." where the test has
  "e.g."). In the Verinoda arm, Verinoda's part is one `analyze` and one `code_check` per session. What is left to move the
  number: the model, more attempts, and information the benchmark withholds.
- C1's first run (`c1-s1`) runs the code of commit d610991 of the study's branch (Verinoda's engine and the mod as in
  a7e0c65). Every later run below uses the same Verinoda.
- C2. One defect is seen in C1's transcripts so far: `code_check` checked against Verinoda's interpreter, standard library
  only, in every Verinoda-arm session, because it ignored the activated environment (`VIRTUAL_ENV`). It is fixed in the
  product (docs/DESIGN.md D192). On the copy where it was seen, the check with the fix gives the same verdicts (250 sites,
  89 unknown, 0 absent). The study keeps the frozen Verinoda, so no result is credited to the fix. A C2 run is added (by a
  new amendment) only if a transcript shows a defect that changed an outcome.
- C4, the model. Both arms, all 100 dev instances, one session each, C1's environment and prompt, with Opus 5.5 and with
  Fable 5.1 in place of Sonnet 5.5. A session's spending cap scales with the model's price (Sonnet 3, Opus 6, Fable 15
  dollars; the turn cap stays 100). The model with the higher resolved count summed over both arms (local, calibrated)
  is used for C3 and the held-out run; a tie goes to the cheaper one. A lift both arms share is the model's, not
  Verinoda's.
- C3. k = 3 sessions per instance and arm with the chosen model (its C4 session is the first). The selector is
  `swebench_select.py` (amendment 2). pass@3 by the hidden tests is reported as a diagnostic only.
- Outside the benchmark's rules (labelled, never reported as a SWE-bench result or as Verinoda's score). On the dev
  instances that no C3 attempt resolves in either arm: one session per arm with the issue's hints (`hints_text`: the
  issue's comments before the fix) added to the prompt. On those still unresolved: one session per arm with the test patch
  applied to the copy and the FAIL_TO_PASS tests named in the prompt. They show what the remaining instances need.
- The held-out run: the configuration fixed after C3 (model, k = 3, the selector), both arms, on instances 101-200, after
  their environments, builds and gold validation (env_only) are made the same way as for the dev set.
- C0's second repeat is run last, if at all: C3's repeats of C1 give that condition's noise floor.

## Amendment 5 (2026-10-24, during C1's first run, before any session of C4, C3, the diagnostics or the held-out run)

- The diagnostics' instance lists, fixed now. "Resolved" is the local calibrated grade after amendment 2's quiet-machine
  regrade. The hints stage takes the dev instances that no attempt resolves in either arm (C1, both C4 models, C3) and that
  have hints (77 of the 100 dev instances do). The tests stage takes the instances that no attempt and no hints session
  resolves in either arm, the 23 without hints among them (they skip the hints stage). Each stage runs one session per arm
  with the model C4 chooses (`swebench_run_diag.py`: "hints", "tests"), its prompt otherwise C1's.
- The held-out run's copies: `swebench-run/h1/copies/<id>/<arm>`, borrowing the objects of a pool made with the projects'
  history up to each base commit (`swebench_prepare.py --history`, as for the dev pool). Its 36 environments (19 not
  needed by the dev set) were built with 0 failures; gold validation and env_only follow the dev set's rule (the gold patch
  resolves locally, calibrated). Its guided copies are set up after the dev set's, with the same Verinoda.
- Sessions can leave processes running after they end: three `find /` searches started by C0 sessions outlived them by
  hours (`runs/leak-review.md`). They read no file a later session sees and change no result; the harness stays as it is for
  every run of this study, so C3's attempts and the held-out run use the harness C1 and C4 use.

## Amendment 6 (2026-10-24, 06:45; C4's first sessions started at 06:20, none of them graded or read before this)

- What was seen. In C1's first run 11 sessions (6 of 100 plain, 5 of 47 guided so far) had a Bash tool that found no
  command: `ls`, `mkdir`, `python`, "command not found". The cause, read in Claude Code 2.1.296's own code: on Windows a
  session's shell snapshot takes its PATH from a login shell (`bash -lc 'echo "$PATH"'`, a 10-second limit); when that
  fails or times out, the snapshot exports the process's PATH in its Windows form, which bash cannot search, and every
  command outside bash itself fails for the rest of the session. On this machine, under the study's load, a login shell
  took 4.4 to 13.2 s (5 timings, 06:33), and 3.7 to 7.1 s (5 timings, 06:40) once the held-out gold evaluation was stopped
  and the dev guided setup's priority lowered. C0's first repeat has 1 of 34 sessions per arm. D184 has 0 of 200, but only
  15 of its 100 sessions per arm used Bash at all (C1: 99 of 100 plain), so its rate says little.
- The rule. A session is flagged when a Bash tool result in its transcript says that one of a fixed set of commands is not
  found (`swebench_shellcheck.py`, its pattern fixed now: Git's own tools, git and python, each on every session's PATH
  when the PATH is right). It is flagged whether or not it resolved and whether or not it recovered (PowerShell, a PATH set
  by hand; the PowerShell tool was itself refused or timed out in 12 of the 55 calls the flagged C1 sessions made). A
  flagged session's lane is reset and the session run again with the same run's configuration (run `<run>-r1`, then
  `<run>-r2` when that one is flagged too); the last session counts, whichever way it is graded, and after two re-runs the
  last counts even when flagged, reported as such. The resolved flagged sessions are re-run too (6 of the 7 graded in C1 so
  far resolved): re-running only the failures would lift every condition that has more of them.
- Scope: every run of this study (C0, C1, C4, C3, the diagnostics, the held-out run). Each run reports its flagged count
  per arm and one sensitivity line with the flagged sessions left out. The C4 model choice uses the grades after the
  re-runs.
- The arms so far (5 of 47 guided, 6 of 100 plain) may differ because the guided setup loads the machine and the Verinoda
  server starts with a guided session; the rule takes that out of the comparison.
- Not changed: the sessions' environment (no PATH and no time limit given to Claude Code), so C1 and C4 stay one condition.
  The machine's load is cut instead: the held-out gold evaluation and the held-out guided setup wait until the dev runs
  leave room, and the dev guided setup runs at below-normal priority. Neither changes what a session sees.

## Amendment 7 (2026-10-24, 08:19; before any session of C4's Fable run, C3, the diagnostics or the held-out run)

- What was seen (exploratory: the measure below was defined after reading C4's Opus grades, 53 of them at 08:18). Opus
  writes the upstream fix verbatim far more often than Sonnet does. On the 53 dev instances graded in both C1's plain arm
  (Sonnet) and C4's Opus plain arm, the share of the gold patch's lines (those the issue does not give) that the patch also
  writes is 0.39 for Sonnet and 0.63 for Opus on average, with 12 and 27 patches at 0.9 or more. On the 40 instances both
  resolved, where correctness cannot explain it, it is 0.48 and 0.71 (12 and 24 at 0.9 or more). In django-16816, whose
  tests demand an error id and message the issue does not give (OpenAI's false_negative annotation 3), Opus's patch is the
  gold patch character for character; in sympy-19254, whose tests assert the numbers of the gold's own variant of the bound
  (false_negative 3), Opus's patch carries the gold's docstring line "The Knuth-Cohen variant of Mignotte bound"; in
  django-14730 it writes the gold's warning with its "e.g.", the one word C1's Sonnet patch missed (amendment 4). The
  models may have seen these fixes in training (the limits below); the strongest model shows it the most.
- The measure, fixed now: `swebench_recall.py`. The gold patch's added lines in non-test files, whitespace removed, 8
  characters or more, leaving out those the problem statement holds; recall is the share of them a patch adds (none left:
  not measured); a patch is "verbatim" at 0.9 or more. Confirmatory from here on (C4's Fable run, C3, the diagnostics, the
  held-out run). Reported per run and arm: mean recall among the resolved and the verbatim count; paired with C1's Sonnet
  sessions on the instances both resolved; and a sensitivity line, the resolved count leaving out verbatim patches on
  instances whose false_negative annotation is 2 or more (tests that demand what the issue may not determine). The C4 rule
  does not change: the model with the higher resolved count summed over both arms; the sensitivity line stands beside it
  and never replaces it.
- The closed-book probe (outside the benchmark's rules, labelled, never graded and never a resolved share):
  `swebench_closedbook.py`. For each of the 100 dev instances, one call per model (Sonnet 5.5, Opus 5.5, Fable 5.1) given
  only the repository, the base commit and the issue: no tool (`--tools ""`), no MCP server, no plugin, settings from an
  empty folder only, one turn, a short system prompt in place of Claude Code's; one call at a time at below-normal
  priority. Measured: recall per model, paired over the instances. What a model writes of the upstream fix with no file
  to read can only come from memory. One call (Sonnet, psf__requests-2674, 08:17) was made to test the mechanics: $0.017,
  12 s, a diff came back; its recall was not computed. Closed-book diffs are not graded (they seldom apply).
- C2 for C1 so far (77 of 100 guided sessions): no transcript shows a Verinoda defect that changed an outcome, so no C2
  run. Of the two instances only the plain arm resolved, sympy-21627's session got a `statically_verified` claim about a
  different `is_zero` (sympy/polys/agca/homomorphisms.py) and wrote "Not helpful; go direct" before fixing the right file
  its own way; django-11564's `analyze` spent its 60-second budget unanswered, and its patch prefixes absolute URLs, which
  the hidden test rejects. In C1's guided sessions so far, 21 of 76 `analyze` calls ended unanswered (14 with the budget
  spent). Both defects go to the product's backlog, not to this study.
- Scheduling (amendment 6 has the held-out gold evaluation wait until the dev runs leave room): at 08:08 it was let into
  the orchestrator's evaluation queue, which runs one evaluation at a time at below-normal priority, so it adds no
  evaluation beside the dev ones. Login shell at 08:10: 488, 520 and 629 ms (the limit is 10 s). A gold patch that fails
  under this load is evaluated again on a quiet machine before the held-out env_only is fixed. The held-out guided setup
  still waits for the dev guided setup to end.
- The held-out run controls for tuning on the dev set, not for memory: instances 101-200 come from the same public
  repositories and the same benchmark. A claim free of recall needs tasks fixed after the models' training data; this
  study has none, and its write-up says so.

## Amendment 8 (2026-10-24, 09:36; 37 sessions of C4's Fable run so far, none of them graded)

- C4's rule, how it counts, fixed before any Fable grade (it left open what a row without a grade adds). Each model's
  resolved rows over its own 200 lanes (instance and arm), each lane's last session after amendment 6's re-runs and
  amendment 2's regrade. A row with no grade adds nothing: calibration cannot grade it (django-13658 in C1's and C4's Opus
  plain arms: the admin_scripts tests fail with the gold patch in this environment too, so `resolved_calibrated` is null),
  or the leak review does not count it. Reported beside it, never in its place: the same count over the lanes graded for
  both models. The rule is computed once no lane of either model waits for a session, a re-run, a grade or the regrade.
- Scheduling. The held-out guided setup started at 09:07, when the dev guided setup ended (100 snapshots), from a waiter
  whose background task Claude Code had stopped for low memory at about 07:45 while the waiter's own process lived on. It
  was stopped at 09:11 with one copy made and recorded (`h1/builds.json`; a half-made copy is made again), and resumes from
  there once memory allows.

## Limits fixed now

The model may have seen SWE-bench fixes in training (both arms share it). The dev set is no longer a fair test once tuned on;
only the held-out run supports a claim. Windows is not the official Linux image: local results can differ, and the agreement
check measures by how much.
