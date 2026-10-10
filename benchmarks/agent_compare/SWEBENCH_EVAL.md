# SWE-bench Lite study: how to evaluate the patches (run it where Docker or a cloud runner exists)

`swebench_run.py` writes `predictions-none.jsonl` and `predictions-verinoda_guided.jsonl` (SWE-bench format:
`instance_id`, `model_name_or_path`, `model_patch`). **The share of instances resolved is the study's main measure and it
is not measured until those files are evaluated with the official SWE-bench harness on a machine that can run it.** The
Windows development machine this study was built on cannot: SWE-bench's evaluation runs each instance in a Docker image and
recommends an `x86_64` Linux machine with 120 GB of free disk, 16 GB of RAM and 8 cores. Without that, only proxies are
available (the patch applies to the base commit, it changes the gold patch's files, cost and time per session), and
file overlap is not correctness. Do not report a resolved share from the proxies.

## Ways to evaluate, from least to most effort

1. **SWE-bench's cloud evaluation (`sb-cli`), no local Docker.** It runs the official evaluation on AWS.

   ```
   pip install sb-cli
   sb-cli gen-api-key you@example.com        # then verify the key with the code mailed to you; keep the key private
   sb-cli submit swe-bench_lite test --predictions_path predictions-none.jsonl --run_id verinoda-none
   sb-cli submit swe-bench_lite test --predictions_path predictions-verinoda_guided.jsonl --run_id verinoda-guided
   sb-cli get-report swe-bench_lite test verinoda-none -o ./reports
   ```

   (Check `https://www.swebench.com/sb-cli/` for the current options. Predictions leave your machine: they contain the
   patches only, not the transcripts.)
2. **Modal** (`docs/guides/evaluation.md`, "Cloud-Based Evaluation" in the SWE-bench repository): the same harness with
   `--modal true`, billed by Modal.
3. **A Linux machine or VM with Docker** (a cloud instance with 120+ GB of disk is enough; stop it when done):

   ```
   pip install swebench
   python -m swebench.harness.run_evaluation --dataset_name SWE-bench/SWE-bench_Lite \
       --predictions_path predictions-none.jsonl --run_id none --max_workers 8
   python -m swebench.harness.run_evaluation --dataset_name SWE-bench/SWE-bench_Lite \
       --predictions_path predictions-verinoda_guided.jsonl --run_id verinoda_guided --max_workers 8
   ```

   The harness caches by `run_id` and instance: give a changed prediction file a new `run_id`.

Evaluate both arms the same way, on the same instances (an instance in only one file is missing from the other arm and
is left out of the comparison). Then compare per instance (resolved in one arm and not the other), not only the totals;
the pre-registered analysis is in `DESIGN_SWEBENCH.md`.

## A better test without Docker (not done here)

Docker is needed for the official number; these are the ways to get closer to it without it, with what each costs:

- **Native evaluation of the pure-Python repositories** (django, sympy, sphinx, pytest, requests, flask, pylint: about 240
  of the 300 Lite instances): a virtual environment per repository version with the Python and the pinned dependencies of
  `swebench.harness.constants.MAP_REPO_VERSION_TO_SPECS`, then the instance's `FAIL_TO_PASS` and `PASS_TO_PASS` tests.
  Validate every instance first by applying the **gold** patch and keeping only those where the gold patch passes natively
  (Windows path and locale differences will fail some); evaluate patches on the validated ones only and report the
  validated count. Compiled repositories (matplotlib, astropy, scikit-learn, xarray) stay out. Each version's environment
  is a few hundred MB, far below Docker's images. The numbers are native-environment numbers, not the leaderboard's.
- **Give the agents the same environment**, so that they can run tests while they work as the published agents do: the
  harness's agents ran in the instance images. Native environments (above) give most of that for the pure-Python subset.
- **More than one session per instance and arm**, to see the agent's own variation (the pilot ran one).
