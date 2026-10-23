"""Select the instances of DESIGN_SWEBENCH.md and prepare their working copies.

    python benchmarks/agent_compare/swebench_prepare.py DATA.parquet WORK_DIR N [--arms none,verinoda_guided] [--workers N]
        [--offset K] [--tasks-out PATH] [--history MIRRORS]

DATA.parquet: SWE-bench_Lite's test split. WORK_DIR gets ``tasks.json`` (the N first instances of the fixed order,
with the files the gold patch and the test patch change) and one checkout per instance and arm,
``WORK_DIR/copies/<instance>/<arm>``, at the instance's base commit. The ``verinoda_guided`` copy is a copy of the
``none`` one, set up with ``verinoda setup . --agents claude`` (Verinoda's own .venv python). Resumable.

``--offset K`` takes the N instances after the first K (the held-out set of DESIGN_SWEBENCH_CEILING.md is ``--offset 100``).
``--tasks-out`` writes ``tasks.json`` elsewhere: it names the FAIL_TO_PASS tests and the gold patch's files, so it must not
sit in the folder tree the sessions work in. ``--history MIRRORS`` gives each copy the base commit's whole history instead of
one commit, fetched from a local bare clone ``MIRRORS/<owner>__<repo>.git``: only the base commit's ancestors, no remote, no
tags, and the copy is refused if any commit in it is newer than the base commit (as in SWE-bench 5.x's images); the
``verinoda_guided`` copy then shares the ``none`` copy's objects.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from guard_run import _force_remove, git_env, run

SEED = "20261010:"
REPO_ROOT = Path(__file__).resolve().parents[2]
# VERINODA_PY pins the Verinoda a study runs (a worktree's own venv), so that work in the main checkout cannot change it mid-run
VERINODA_PY = Path(os.environ.get("VERINODA_PY") or REPO_ROOT / ".venv" / "Scripts" / "python.exe")


def files_of(diff: str) -> list[str]:
    return sorted(dict.fromkeys(re.findall(r"^diff --git a/(\S+) b/", diff, re.MULTILINE)))


def select(parquet: Path, n: int, offset: int = 0) -> list[dict]:
    import pyarrow.parquet as pq

    rows = pq.read_table(parquet).to_pylist()
    rows.sort(key=lambda r: hashlib.sha256((SEED + r["instance_id"]).encode()).hexdigest())
    return [{"id": r["instance_id"], "repo": r["repo"], "base_commit": r["base_commit"], "version": r["version"],
             "problem_statement": r["problem_statement"], "gold_files": files_of(r["patch"]),
             "test_files": files_of(r["test_patch"]), "fail_to_pass": r["FAIL_TO_PASS"]} for r in rows[offset:offset + n]]


def fetch_history(task: dict, dest: Path, mirrors: Path) -> None:
    """A checkout of the base commit with all its ancestors from a local bare clone, and nothing newer: no remote, no tags,
    no FETCH_HEAD; refused when a commit newer than the base is reachable."""
    env = git_env()
    mirror = mirrors / (task["repo"].replace("/", "__") + ".git")
    if dest.exists():
        head = run(["git", "rev-parse", "HEAD"], dest, env)[1].strip()
        dirty = run(["git", "status", "--porcelain", "--untracked-files=no"], dest, env)[1].strip()
        shallow = (dest / ".git" / "shallow").exists()
        if head == task["base_commit"] and not dirty and not shallow:
            return
        shutil.rmtree(dest, onerror=_force_remove)
    dest.mkdir(parents=True)
    for argv in (["git", "init", "-q"], ["git", "config", "core.longpaths", "true"],
                 ["git", "config", "core.autocrlf", "false"], ["git", "config", "core.eol", "lf"],
                 ["git", "fetch", "-q", "--no-tags", str(mirror), task["base_commit"]],
                 ["git", "checkout", "-q", "--detach", task["base_commit"]]):
        rc, _, err, _ = run(argv, dest, env, timeout=3600)
        if rc != 0:
            shutil.rmtree(dest, onerror=_force_remove)
            raise RuntimeError(f"{' '.join(argv)} in {dest}: {err[-400:]}")
    (dest / ".git" / "FETCH_HEAD").unlink(missing_ok=True)
    when = run(["git", "show", "-s", "--format=%ct", task["base_commit"]], dest, env)[1].strip()
    newer = run(["git", "rev-list", "--all", f"--since={int(when) + 1}"], dest, env)[1].split()
    if newer:  # a commit after the base would show the fix: never hand such a copy to a session
        shutil.rmtree(dest, onerror=_force_remove)
        raise RuntimeError(f"{task['id']}: {len(newer)} commits newer than the base commit are reachable")


def share_copy(base: Path, dest: Path, commit: str) -> None:
    """A second working copy of `base` that borrows its objects (git alternates): no remote, no refs but HEAD."""
    env = git_env()
    dest.mkdir(parents=True)
    rc, _, err, _ = run(["git", "init", "-q"], dest, env)
    (dest / ".git" / "objects" / "info").mkdir(parents=True, exist_ok=True)
    (dest / ".git" / "objects" / "info" / "alternates").write_text((base / ".git" / "objects").as_posix() + "\n",
                                                                   encoding="utf-8")
    for argv in (["git", "config", "core.longpaths", "true"], ["git", "config", "core.autocrlf", "false"],
                 ["git", "config", "core.eol", "lf"], ["git", "checkout", "-q", "--detach", commit]):
        rc, _, err, _ = run(argv, dest, env, timeout=1800)
        if rc != 0:
            raise RuntimeError(f"{' '.join(argv)} in {dest}: {err[-400:]}")


def fetch(task: dict, dest: Path) -> None:
    """A checkout of the repository at the base commit (one commit deep)."""
    env = git_env()
    if dest.exists():  # one a killed run left half done is fetched again
        head = run(["git", "rev-parse", "HEAD"], dest, env)[1].strip()
        dirty = run(["git", "status", "--porcelain", "--untracked-files=no"], dest, env)[1].strip()
        if head == task["base_commit"] and not dirty:
            return
        shutil.rmtree(dest, onerror=_force_remove)
    dest.mkdir(parents=True)
    # the machine's Git may convert line endings (autocrlf): the files must be exactly the blobs, as in SWE-bench's images
    for argv in (["git", "init", "-q"], ["git", "config", "core.longpaths", "true"],
                 ["git", "config", "core.autocrlf", "false"], ["git", "config", "core.eol", "lf"],
                 ["git", "remote", "add", "origin", f"https://github.com/{task['repo']}.git"],
                 ["git", "fetch", "-q", "--depth", "1", "origin", task["base_commit"]],
                 ["git", "checkout", "-q", "--detach", "FETCH_HEAD"]):
        rc, _, err, _ = run(argv, dest, env, timeout=1800)
        if rc != 0:
            shutil.rmtree(dest, onerror=_force_remove)
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

    def opt(name: str, default: str | None = None) -> str | None:
        return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default

    arms = opt("--arms", "none,verinoda_guided").split(",")
    mirrors = Path(opt("--history")) if opt("--history") else None
    tasks = select(parquet, n, int(opt("--offset", "0")))
    work.mkdir(parents=True, exist_ok=True)
    tasks_out = Path(opt("--tasks-out")) if opt("--tasks-out") else work / "tasks.json"
    tasks_out.parent.mkdir(parents=True, exist_ok=True)
    tasks_out.write_text(json.dumps({"seed": SEED, "tasks": tasks}, indent=1), encoding="utf-8")
    builds_path = tasks_out.parent / "builds.json"
    builds = json.loads(builds_path.read_text(encoding="utf-8")) if builds_path.exists() else {}
    lock = threading.Lock()

    def prepare(t: dict) -> None:
        base = work / "copies" / t["id"] / "none"
        t0 = time.perf_counter()
        if mirrors is not None:
            fetch_history(t, base, mirrors)
        else:
            fetch(t, base)
        print(f"{t['id']}: checkout ready ({round(time.perf_counter() - t0, 1)} s)", flush=True)
        for arm in arms:
            key = f"{t['id']}:{arm}"
            dest = work / "copies" / t["id"] / arm
            if arm == "none" or (dest.exists() and key in builds):
                continue
            if dest.exists():
                shutil.rmtree(dest, onerror=_force_remove)
            if mirrors is not None:
                share_copy(base, dest, t["base_commit"])
            else:
                shutil.copytree(base, dest)
            info = setup_verinoda(dest)
            with lock:
                builds[key] = info
                builds_path.write_text(json.dumps(builds, indent=1), encoding="utf-8")
            print(f"{key}: set up ({info['setup_seconds']} s)", flush=True)

    workers = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 1
    with ThreadPoolExecutor(workers) as pool:
        for fut in [pool.submit(prepare, t) for t in tasks]:
            fut.result()
    print("prepared", len(tasks), "instances", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
