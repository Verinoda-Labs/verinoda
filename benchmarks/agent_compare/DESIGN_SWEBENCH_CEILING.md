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

## Limits fixed now

The model may have seen SWE-bench fixes in training (both arms share it). The dev set is no longer a fair test once tuned on;
only the held-out run supports a claim. Windows is not the official Linux image: local results can differ, and the agreement
check measures by how much.
