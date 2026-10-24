"""The labelled diagnostics of DESIGN_SWEBENCH_CEILING.md (amendment 4): `swebench_run.py`'s sessions given what SWE-bench
withholds, to show what the instances no attempt resolves need. Outside the benchmark's rules: a result here is never
reported as a SWE-bench result or as Verinoda's score.

    python benchmarks/agent_compare/swebench_run_diag.py CONFIG.json

CONFIG: `swebench_run.py`'s (C1's environment, "out" a folder of its own), plus "dataset" (``lite.parquet``) and "diag":
"hints", the issue's comments from before the fix (the dataset's ``hints_text``) added after the issue, on the instances
that have any; or "tests", the instance's test patch applied to the copy before the session and its FAIL_TO_PASS tests
named in the prompt as the tests that must pass. Each row carries "diag", and "changed_tests": the test files the session
changed from what the test patch left (its patch never holds them: `swebench_run.patch_of` leaves them out, as the
evaluation applies the test patch over it).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import swebench_run as sr
from guard_run import git_env

CFG: dict = {}
ROWS: dict[str, dict] = {}
_prompt_for, _one = sr.prompt_for, sr.one


def extra_for(diag: str, row: dict) -> str:
    if diag == "hints":
        return ("For this run you are also given the comments other people wrote on the issue before it was fixed:\n\n"
                f"{row['hints_text'].strip()}")
    f2p = json.loads(row["FAIL_TO_PASS"]) if isinstance(row["FAIL_TO_PASS"], str) else list(row["FAIL_TO_PASS"])
    names = "\n".join(f"- {t}" for t in f2p)
    return ("For this run the tests that check the fix are already in the repository (added for you, not by the user). "
            f"These fail now and must pass once the issue is fixed:\n\n{names}\n\nRun them as part of the project's tests; "
            "do not change them or the files that hold them.")


def prompt_for(task: dict, copy: Path, arm: str, with_env: bool = False) -> str:
    text = _prompt_for(task, copy, arm, with_env)
    issue = f"{task['problem_statement']}\n\n"
    extra = extra_for(CFG["diag"], ROWS[task["id"]])
    # after the issue, before the task: the rest of the prompt (the order of work, the arm's guide) stays C1's
    return text.replace(issue, f"{issue}{extra}\n\n", 1) if issue in text else f"{text}\n\n{extra}"


def digests(copy: Path, files: list[str]) -> dict[str, str]:
    return {f: hashlib.sha256((copy / f).read_bytes()).hexdigest() if (copy / f).is_file() else "" for f in files}


def one(cfg: dict, task: dict, arm: str) -> dict:
    copy = Path(cfg["work"]) / "copies" / task["id"] / arm
    before = {}
    if cfg["diag"] == "tests":
        # into the working tree only: the index keeps the base commit's files, as for the session's own edits
        p = subprocess.run(["git", "-C", str(copy), "apply", "--whitespace=nowarn", "-"],
                           input=ROWS[task["id"]]["test_patch"].encode("utf-8"), capture_output=True, env=git_env(),
                           check=False)
        if p.returncode:
            raise RuntimeError(f"the test patch does not apply: {p.stderr.decode('utf-8', 'replace')[-300:]}")
        before = digests(copy, task["test_files"])
    r = _one(cfg, task, arm)
    after = digests(copy, task["test_files"]) if before else {}
    return {**r, "diag": cfg["diag"], "changed_tests": sorted(f for f in before if before[f] != after.get(f))}


def main() -> int:
    import pyarrow.parquet as pq

    CFG.update(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")))
    if CFG.get("diag") not in ("hints", "tests") or not all(CFG.get(k) for k in ("env_data", "out", "only", "dataset")):
        print('CONFIG needs "diag" ("hints" or "tests"), "env_data", "out", "only" and "dataset"', flush=True)
        return 2
    for row in pq.read_table(CFG["dataset"]).to_pylist():
        ROWS[row["instance_id"]] = row
    if CFG["diag"] == "hints":
        empty = sorted(i for i in CFG["only"] if not (ROWS[i].get("hints_text") or "").strip())
        if empty:
            # swebench_run.main reads CONFIG itself: the instances with nothing to add leave its list there
            print(f"no hints, not run: {', '.join(empty)}", flush=True)
            CFG["only"] = [i for i in CFG["only"] if i not in empty]
            Path(sys.argv[1]).write_text(json.dumps(CFG, indent=1), encoding="utf-8", newline="\n")
    sr.prompt_for, sr.one = prompt_for, one
    return sr.main()


if __name__ == "__main__":
    sys.exit(main())
