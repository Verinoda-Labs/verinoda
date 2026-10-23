"""Choose one patch per instance among several attempts without the hidden tests (DESIGN_SWEBENCH_CEILING.md, C3).

    python swebench_select.py DATA TASKS.json ARM OUT.jsonl RUN_DIR... [--copies DIR] [--workers N]

Each RUN_DIR holds a ``results.jsonl`` of `swebench_run.py` and the sessions' reproductions (``scratch/<id>--<arm>/*.py``, kept
by the C1 prompt: a script that fails while the issue is present). Every reproduction is run on the base commit first and kept
only if it fails there; then every candidate patch is applied to a clean base checkout and every kept reproduction runs against
it. A candidate's score is the number of reproductions it passes; ties go to the candidate whose diff agrees with most others,
then to the earlier run. Nothing here reads the gold patch, the test patch or the FAIL_TO_PASS tests: only what the sessions
themselves wrote. Writes one prediction per instance (SWE-bench format) and, beside it, the score table.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from swebench_envspec import env_key, parse
from swebench_localeval import (
    COMPILED,
    PYTHONPATH_REPOS,
    REBUILD,
    apply_patch,
    build_outputs,
    git,
    install_checkout,
    run_env_for,
    source_for,
    venv_python,
)

RUN_TIMEOUT = 180


def run_script(script: Path, src: Path, py: Path, env: dict, iid: str, arm: str) -> bool:
    """Run one reproduction against the checkout `src` (made importable by `install_checkout`, whose variables `env` holds);
    a path to the session's own copy (``.../copies/<id>/<arm>``, in any run's folder and either slash) is pointed at `src`."""
    text = script.read_text(encoding="utf-8", errors="replace")
    own = re.compile(r"[A-Za-z]:(?:[/\\]+[^/\\\s'\"]+)*?[/\\]+copies[/\\]+" + re.escape(iid) + r"[/\\]+" + re.escape(arm))
    text = own.sub(lambda _: src.as_posix(), text)
    target = src / ".select" / script.name
    target.parent.mkdir(exist_ok=True)
    target.write_text(text, encoding="utf-8")
    try:
        p = subprocess.run([str(py), str(target)], cwd=src, env=env, capture_output=True, timeout=RUN_TIMEOUT, check=False)
        return p.returncode == 0
    except subprocess.TimeoutExpired:
        return False


def similarity(a: str, b: str) -> float:
    def body(d: str) -> str:
        return "\n".join(x for x in d.splitlines() if x[:1] in "+-" and not x.startswith(("+++", "---")))

    return SequenceMatcher(None, body(a), body(b)).ratio()


def select_one(data: Path, task: dict, arm: str, cands: list[dict], scripts: list[Path], origin: Path | None,
               slot: str) -> dict:
    spec = parse(data / "tasks" / task["id"] / "Dockerfile")
    env = data / "envs" / env_key(spec)
    py = venv_python(env)

    row = {**task, "instance_id": task["id"]}
    build = build_outputs(data, row, spec, origin) if task["repo"] in COMPILED else None

    def checkout(patch: str | None) -> tuple[bool, Path, dict]:
        src = source_for(data, task["id"], task["base_commit"], origin, f"select{slot}")
        ok = apply_patch(src, patch, "candidate")[0] if patch is not None else True
        run_env = run_env_for(env)
        if ok:
            install_checkout(src, row, spec, py, run_env, build, rebuild=bool(patch and REBUILD.search(patch)))
        return ok, src, run_env

    # a reproduction must fail on the base commit
    _, src, run_env = checkout(None)
    valid = [s for s in scripts if not run_script(s, src, py, run_env, task["id"], arm)]
    for c in cands:
        ok, src, run_env = checkout(c["patch"])
        c["applies"] = ok
        c["passes"] = [s.parent.name + "/" + s.name for s in valid if ok and run_script(s, src, py, run_env, task["id"], arm)]
        c["agreement"] = sum(similarity(c["patch"], o["patch"]) for o in cands if o is not c)
    git("reset", "-q", "--hard", task["base_commit"], cwd=src, check=False)
    ranked = sorted(cands, key=lambda c: (-c["applies"], -len(c["passes"]), -c["agreement"], c["run_index"]))
    return {"instance_id": task["id"], "chosen_run": ranked[0]["run"], "valid_reproductions": len(valid),
            "reproductions": len(scripts), "candidates": [{k: c[k] for k in ("run", "applies", "passes", "agreement")}
                                                          for c in ranked], "patch": ranked[0]["patch"]}


def main(argv: list[str]) -> int:
    data, tasks_path, arm, out = Path(argv[0]), Path(argv[1]), argv[2], Path(argv[3])
    opts = [a for a in argv[4:]]
    copies = Path(opts[opts.index("--copies") + 1]) if "--copies" in opts else None
    workers = int(opts[opts.index("--workers") + 1]) if "--workers" in opts else 3
    runs = [Path(a) for i, a in enumerate(opts) if not a.startswith("--") and (i == 0 or not opts[i - 1].startswith("--"))]
    tasks = {t["id"]: t for t in json.loads(tasks_path.read_text(encoding="utf-8"))["tasks"]}
    by_id: dict[str, list[dict]] = {}
    scripts: dict[str, list[Path]] = {}
    for k, run in enumerate(runs):
        for line in (run / "results.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r["arm"] != arm or not (r.get("patch") or "").strip():
                continue
            by_id.setdefault(r["id"], []).append({"run": run.name, "run_index": k, "patch": r["patch"]})
            scripts.setdefault(r["id"], []).extend(sorted((run / "scratch" / f"{r['id']}--{arm}").glob("*.py")))
    locks: dict[str, threading.Lock] = {}

    def one(item):
        iid, cands = item
        origin = None
        if copies is not None and (copies / iid / "none" / ".git").exists():
            origin = copies / iid / "none"
        # an editable install points the shared environment at one checkout: one instance per environment at a time
        spec = parse(data / "tasks" / iid / "Dockerfile")
        lock = (threading.Lock() if tasks[iid]["repo"] in PYTHONPATH_REPOS
                else locks.setdefault(env_key(spec), threading.Lock()))
        with lock:
            return select_one(data, tasks[iid], arm, cands, scripts.get(iid, []), origin,
                              threading.current_thread().name.split("_")[-1])

    with ThreadPoolExecutor(workers) as ex:
        rows = list(ex.map(one, sorted(by_id.items())))
    with out.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps({"instance_id": r["instance_id"], "model_name_or_path": f"selected-{arm}",
                                "model_patch": r["patch"]}) + "\n")
    table = out.with_suffix(".scores.json")
    table.write_text(json.dumps([{k: v for k, v in r.items() if k != "patch"} for r in rows], indent=1), encoding="utf-8")
    print(f"{len(rows)} instances selected; scores in {table}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
