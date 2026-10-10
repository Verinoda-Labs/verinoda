"""Select the instances of DESIGN_SWEBENCH.md and prepare their working copies.

    python benchmarks/agent_compare/swebench_prepare.py DATA.parquet WORK_DIR N [--arms none,verinoda_guided]

DATA.parquet: SWE-bench_Lite's test split. WORK_DIR gets ``tasks.json`` (the N first instances of the fixed order,
with the files the gold patch and the test patch change) and one checkout per instance and arm,
``WORK_DIR/copies/<instance>/<arm>``, at the instance's base commit. The ``verinoda_guided`` copy is a copy of the
``none`` one, set up with ``verinoda setup . --agents claude`` (Verinoda's own .venv python). Resumable.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from guard_run import git_env, run

SEED = "20261010:"
REPO_ROOT = Path(__file__).resolve().parents[2]
VERINODA_PY = REPO_ROOT / ".venv" / "Scripts" / "python.exe"


def files_of(diff: str) -> list[str]:
    return sorted(dict.fromkeys(re.findall(r"^diff --git a/(\S+) b/", diff, re.MULTILINE)))


def select(parquet: Path, n: int) -> list[dict]:
    import pyarrow.parquet as pq

    rows = pq.read_table(parquet).to_pylist()
    rows.sort(key=lambda r: hashlib.sha256((SEED + r["instance_id"]).encode()).hexdigest())
    return [{"id": r["instance_id"], "repo": r["repo"], "base_commit": r["base_commit"], "version": r["version"],
             "problem_statement": r["problem_statement"], "gold_files": files_of(r["patch"]),
             "test_files": files_of(r["test_patch"]), "fail_to_pass": r["FAIL_TO_PASS"]} for r in rows[:n]]


def fetch(task: dict, dest: Path) -> None:
    """A checkout of the repository at the base commit (one commit deep)."""
    if dest.exists():
        return
    env = git_env()
    dest.mkdir(parents=True)
    # the machine's Git may convert line endings (autocrlf): the files must be exactly the blobs, as in SWE-bench's images
    for argv in (["git", "init", "-q"], ["git", "config", "core.longpaths", "true"],
                 ["git", "config", "core.autocrlf", "false"], ["git", "config", "core.eol", "lf"],
                 ["git", "remote", "add", "origin", f"https://github.com/{task['repo']}.git"],
                 ["git", "fetch", "-q", "--depth", "1", "origin", task["base_commit"]],
                 ["git", "checkout", "-q", "--detach", "FETCH_HEAD"]):
        rc, _, err, _ = run(argv, dest, env, timeout=1800)
        if rc != 0:
            shutil.rmtree(dest, ignore_errors=True)
            raise RuntimeError(f"{' '.join(argv)} in {dest}: {err[-400:]}")


def setup_verinoda(copy: Path) -> dict:
    t0 = time.perf_counter()
    rc, out, err, _ = run([str(VERINODA_PY), "-m", "verinoda", "setup", str(copy), "--agents", "claude"], copy,
                          git_env(), timeout=7200)
    exclude = copy / ".git" / "info" / "exclude"
    with exclude.open("a", encoding="utf-8") as f:
        f.write("\n.verinoda/\n.claude/\n.mcp.json\n")
    if rc != 0:
        raise RuntimeError(f"verinoda setup failed in {copy}: {(err or out)[-400:]}")
    return {"setup_seconds": round(time.perf_counter() - t0, 1)}


def main() -> int:
    parquet, work, n = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
    arms = (sys.argv[sys.argv.index("--arms") + 1] if "--arms" in sys.argv else "none,verinoda_guided").split(",")
    tasks = select(parquet, n)
    work.mkdir(parents=True, exist_ok=True)
    (work / "tasks.json").write_text(json.dumps({"seed": SEED, "tasks": tasks}, indent=1), encoding="utf-8")
    builds_path = work / "builds.json"
    builds = json.loads(builds_path.read_text(encoding="utf-8")) if builds_path.exists() else {}
    for t in tasks:
        base = work / "copies" / t["id"] / "none"
        t0 = time.perf_counter()
        fetch(t, base)
        print(f"{t['id']}: checkout ready ({round(time.perf_counter() - t0, 1)} s)", flush=True)
        for arm in arms:
            if arm == "none":
                continue
            dest = work / "copies" / t["id"] / arm
            if dest.exists() and f"{t['id']}:{arm}" in builds:
                continue
            shutil.rmtree(dest, ignore_errors=True)
            shutil.copytree(base, dest)
            key = f"{t['id']}:{arm}"
            builds[key] = setup_verinoda(dest)
            builds_path.write_text(json.dumps(builds, indent=1), encoding="utf-8")
            print(f"{key}: set up ({builds[key]['setup_seconds']} s)", flush=True)
    print("prepared", len(tasks), "instances", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
