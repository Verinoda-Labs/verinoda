"""Evaluate SWE-bench Lite patches on Windows without Docker (not the official harness): each instance's Python environment
is rebuilt as a venv from its task-repo Dockerfile (`swebench_envspec.py`), its eval script's test command runs on a clean
copy of the base commit with the patch and the test patch applied, and SWE-bench's own log parser and grading decide.

    python swebench_localeval.py build DATA [IDS...]
    python swebench_localeval.py eval DATA PREDICTIONS.jsonl OUT.jsonl [--only IDS] [--workers N] [--keep-logs DIR]

DATA holds ``lite.parquet`` (SWE-bench_Lite test split with the task repo's columns), ``tasks/<id>/Dockerfile``,
``py36/tools/python.exe`` (a portable CPython 3.6) and gets ``envs/``, ``src/`` and ``logs/``. Run it with a Python that has
``swebench`` installed (its parsers and grading are imported). The answer differs from the official one where Windows does
(paths, encodings, signals, missing system libraries): a test that fails here with the gold patch says so, and
``swebench_localeval.py eval`` with the gold predictions finds those tests (``--gold-report``) so that a grading can leave them
out, said in the row (``env_broken``).
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from swebench_envspec import env_key, parse

# repos whose tests import the checkout through PYTHONPATH; the others get `pip install -e .` into their environment,
# so their instances run one at a time per environment
PYTHONPATH_REPOS = {"django/django", "sympy/sympy", "psf/requests"}
APPLY = [["git", "apply", "--verbose"], ["git", "apply", "--verbose", "--reject"],
         ["patch", "--batch", "--fuzz=5", "-p1", "-i"]]
TIMEOUT = 1800


def rows_of(data: Path) -> dict[str, dict]:
    import pyarrow.parquet as pq

    return {r["instance_id"]: r for r in pq.read_table(data / "lite.parquet").to_pylist()}


def git(*args, cwd=None, check=True, **kw):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(["git", "-c", "core.autocrlf=false", "-c", "core.eol=lf", *args], cwd=cwd, env=env,
                          capture_output=True, check=check, **kw)


# MARK: environments

def python_for(data: Path, version: str) -> list[str]:
    if version.startswith("3.6"):
        return [str(data / "py36" / "tools" / "python.exe")]
    return ["uv", "run", "--no-project", "-p", ".".join(version.split(".")[:2]), "python"]


def venv_python(env: Path) -> Path:
    return env / "Scripts" / "python.exe"


def build_env(data: Path, spec: dict) -> dict:
    """The venv of one environment spec, made once: Python, then every package with --no-deps (the Dockerfile's list is a
    complete freeze), one by one when the batch fails; the packages that do not install on Windows are listed."""
    key = env_key(spec)
    env = data / "envs" / key
    marker = env / "verinoda-env.json"
    if marker.exists():
        info = json.loads(marker.read_text(encoding="utf-8"))
        if "build_tools" not in info and spec.get("build_tools"):  # built before the pins were read: add them
            install_tools(env, spec, info)
            marker.write_text(json.dumps(info, indent=1), encoding="utf-8")
        return info
    if env.exists():
        shutil.rmtree(env)
    major_minor = ".".join(spec["python"].split(".")[:2])
    old = major_minor == "3.6"
    if old:
        subprocess.run([*python_for(data, spec["python"]), "-m", "venv", str(env)], check=True, capture_output=True)
        subprocess.run([str(venv_python(env)), "-m", "pip", "install", "-q", "pip==21.3.1", "setuptools<60", "wheel"],
                       check=True, capture_output=True)
    else:
        subprocess.run(["uv", "venv", "-q", "-p", major_minor, "--seed", str(env)], check=True, capture_output=True)

    def install(pkgs: list[str]) -> bool:
        if old:
            cmd = [str(venv_python(env)), "-m", "pip", "install", "-q", "--no-deps", *pkgs]
        else:
            cmd = ["uv", "pip", "install", "-q", "--python", str(venv_python(env)), "--no-deps", *pkgs]
        return subprocess.run(cmd, capture_output=True, timeout=1800, check=False).returncode == 0

    skipped = []
    if not install(spec["packages"]):
        for p in spec["packages"]:
            if not install([p]):
                skipped.append(p)
    info = {"key": key, "python": spec["python"], "packages": len(spec["packages"]), "skipped": skipped}
    install_tools(env, spec, info)
    marker.write_text(json.dumps(info, indent=1), encoding="utf-8")
    return info


def install_tools(env: Path, spec: dict, info: dict) -> None:
    """The image's setuptools and wheel: a seeded venv gets today's setuptools, which no longer has pkg_resources (sphinx of
    2020 imports it)."""
    tools = spec.get("build_tools") or []
    if spec["python"].startswith("3.6") or not tools:
        info["build_tools"] = []
        return
    p = subprocess.run(["uv", "pip", "install", "-q", "--python", str(venv_python(env)), "--no-deps", *tools],
                       capture_output=True, timeout=600, check=False)
    info["build_tools"] = tools if p.returncode == 0 else [f"FAILED {t}" for t in tools]


# MARK: one evaluation

def test_command(eval_script: str) -> str:
    m = re.search(r": '>>>>> Start Test Output'\n(.*?)\n: '>>>>> End Test Output'", eval_script, re.DOTALL)
    if not m:
        raise ValueError("eval script without a test command")
    return m.group(1).strip()


def windows_argv(cmd: str, python: Path) -> tuple[dict, list[str]]:
    """The eval script's test command as an argv for this venv's Python, and the variables it sets."""
    env = {}
    while (m := re.match(r"^(\w+)=('[^']*'|\"[^\"]*\"|\S+)\s+", cmd)):
        env[m.group(1)] = m.group(2).strip("'\"")
        cmd = cmd[m.end():]
    argv = shlex.split(cmd)
    py = str(python)
    if argv[0] == "./tests/runtests.py":
        argv = [py, "tests/runtests.py", *argv[1:]]
    elif argv[0] == "bin/test":
        argv = [py, "bin/test", *argv[1:]]
    elif argv[0] == "pytest":
        argv = [py, "-m", "pytest", *argv[1:]]
    elif argv[0] == "tox":
        # sphinx: tox --current-env -epy39 -v -- FILES runs its testenv's command, `python -X dev -m pytest` (+ -rA, which the
        # Dockerfile's sed adds to tox.ini)
        files = argv[argv.index("--") + 1:] if "--" in argv else []
        argv = [py, "-X", "dev", "-m", "pytest", "-rA", "--durations", "25", *files]
    else:
        raise ValueError(f"unknown test command: {cmd}")
    return env, argv


def test_files_of(eval_script: str, base: str) -> list[str]:
    m = re.search(rf"git checkout {base} (.+)\n", eval_script)
    return m.group(1).split() if m else []


def apply_patch(src: Path, patch_text: str, name: str) -> tuple[bool, str]:
    pf = src.parent / f"{src.name}.{name}.patch"
    pf.write_bytes(patch_text.encode("utf-8"))
    try:
        for cmd in APPLY:
            p = subprocess.run([*cmd, str(pf)], cwd=src, capture_output=True, check=False)
            if p.returncode == 0:
                return True, " ".join(cmd[:3])
            git("checkout", "--", ".", cwd=src, check=False)
            git("clean", "-fdq", cwd=src, check=False)
        return False, p.stderr.decode("utf-8", "replace")[-500:]
    finally:
        pf.unlink(missing_ok=True)


def source_for(data: Path, iid: str, base: str, origin: Path | None, slot: str) -> Path:
    """A clean checkout of the base commit for one evaluation slot, cloned once from `origin` (a session copy) and reset
    before each use."""
    src = data / "src" / slot / iid
    if not (src / ".git").exists():
        if origin is None or not (origin / ".git").exists():
            raise FileNotFoundError(f"no checkout to clone {iid} from")
        src.parent.mkdir(parents=True, exist_ok=True)
        git("clone", "-q", "--no-checkout", str(origin), str(src))
        git("checkout", "-q", base, cwd=src)
    git("reset", "-q", "--hard", base, cwd=src)
    git("clean", "-fdxq", cwd=src)
    return src


def grade(row: dict, log: str, broken: set[str]) -> dict:
    from swebench.harness.constants import FAIL_TO_PASS, PASS_TO_PASS, EvalType
    from swebench.harness.grading import get_eval_tests_report, get_resolution_status
    from swebench.harness.log_parsers import PARSER_REGISTRY
    from swebench.types import TestSpec

    f2p, p2p = (json.loads(x) if isinstance(x, str) else list(x) for x in (row["FAIL_TO_PASS"], row["PASS_TO_PASS"]))
    spec = TestSpec(instance_id=row["instance_id"], image="", eval_script_list=[], repo=row["repo"], version=row["version"],
                    FAIL_TO_PASS=f2p, PASS_TO_PASS=p2p, log_parser=row["log_parser"], eval_type=row["eval_type"])
    sm = PARSER_REGISTRY[row["log_parser"]](log, spec)
    out = {}
    for label, skip in (("strict", set()), ("calibrated", broken)):
        gold = {FAIL_TO_PASS: [t for t in f2p if t not in skip], PASS_TO_PASS: [t for t in p2p if t not in skip]}
        rep = get_eval_tests_report(sm, gold, eval_type=EvalType(row["eval_type"] or "pass_and_fail"))
        out[label] = {"resolved": get_resolution_status(rep) == "RESOLVED_FULL" if gold[FAIL_TO_PASS] else None,
                      "f2p_failed": rep[FAIL_TO_PASS]["failure"], "p2p_failed": rep[PASS_TO_PASS]["failure"]}
    return out


def evaluate(data: Path, row: dict, patch_text: str, origin: Path | None, slot: str, broken: set[str],
             log_dir: Path | None) -> dict:
    iid, base = row["instance_id"], row["base_commit"]
    t0 = time.perf_counter()
    res = {"instance_id": iid}
    spec = parse(data / "tasks" / iid / "Dockerfile")
    env = data / "envs" / env_key(spec)
    py = venv_python(env)
    src = source_for(data, iid, base, origin, slot)
    ok, how = apply_patch(src, patch_text, "model") if patch_text.strip() else (False, "empty patch")
    res["patch_applied"], res["apply"] = ok, how
    if not ok:
        res.update({"resolved": False, "seconds": round(time.perf_counter() - t0, 1)})
        return res
    run_env = {**{k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "PYTHON", "VIRTUAL_ENV"))},
               "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
               "VIRTUAL_ENV": str(env), "PATH": f"{env / 'Scripts'}{os.pathsep}{os.environ.get('PATH', '')}"}
    if row["repo"] in PYTHONPATH_REPOS:
        run_env["PYTHONPATH"] = str(src)
    else:
        for line in spec["install"]:
            if line.startswith("sed -i "):
                subprocess.run(["bash", "-c", line], cwd=src, capture_output=True, check=False)
            elif "pip install" in line:
                target = re.search(r"pip install (.*)$", line).group(1)
                target = re.sub(r"--verbose|-v\b", "", target).split()
                subprocess.run([str(py), "-m", "pip", "install", "-q", "--no-deps", "--no-build-isolation", *target],
                               cwd=src, capture_output=True, env=run_env, timeout=TIMEOUT, check=False)
    files = test_files_of(row["eval_script"], base)
    if files:
        git("checkout", base, "--", *files, cwd=src, check=False)
    tok, _ = apply_patch(src, row["test_patch"], "test")
    res["test_patch_applied"] = tok
    extra, argv = windows_argv(test_command(row["eval_script"]), py)
    try:
        p = subprocess.run(argv, cwd=src, env={**run_env, **extra}, capture_output=True, timeout=TIMEOUT, check=False)
        log = p.stdout.decode("utf-8", "replace") + "\n" + p.stderr.decode("utf-8", "replace")
        res["exit"] = p.returncode
    except subprocess.TimeoutExpired as exc:
        log = (exc.stdout or b"").decode("utf-8", "replace") + f"\nTIMEOUT after {TIMEOUT} s"
        res["exit"] = "timeout"
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / f"{iid}.log").write_text(log, encoding="utf-8")
    g = grade(row, log, broken)
    res.update({"resolved": g["strict"]["resolved"], "resolved_calibrated": g["calibrated"]["resolved"],
                "f2p_failed": g["strict"]["f2p_failed"], "p2p_failed": g["strict"]["p2p_failed"],
                "env_broken": sorted(broken), "seconds": round(time.perf_counter() - t0, 1)})
    return res


# MARK: commands

def cmd_build(data: Path, ids: list[str]) -> int:
    rows = rows_of(data)
    specs = {}
    for i in ids or list(rows):
        s = parse(data / "tasks" / i / "Dockerfile")
        specs.setdefault(env_key(s), s)
    print(f"{len(specs)} environments", flush=True)

    def one(item):
        k, s = item
        t0 = time.perf_counter()
        try:
            info = build_env(data, s)
            return f"{k} py{s['python']} {info['packages']} packages, skipped {info['skipped']} ({time.perf_counter() - t0:.0f} s)"
        except Exception as e:  # noqa: BLE001 - one environment that cannot be built does not stop the others
            return f"{k} py{s['python']} FAILED: {e}"

    with ThreadPoolExecutor(3) as ex:
        for line in ex.map(one, specs.items()):
            print(line, flush=True)
    return 0


def cmd_eval(data: Path, preds_path: Path, out: Path, only: list[str], workers: int, log_dir: Path | None,
             gold_report: Path | None, copies: Path | None) -> int:
    rows = rows_of(data)
    preds = {}
    for line in preds_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            p = json.loads(line)
            preds[p["instance_id"]] = p.get("model_patch") or ""
    if only:
        preds = {k: v for k, v in preds.items() if k in only}
    done = set()
    if out.exists():
        done = {json.loads(x)["instance_id"] for x in out.read_text(encoding="utf-8").splitlines() if x.strip()}
    broken: dict[str, set[str]] = {}
    if gold_report and gold_report.exists():
        for x in gold_report.read_text(encoding="utf-8").splitlines():
            if x.strip():
                r = json.loads(x)
                broken[r["instance_id"]] = set(r.get("f2p_failed", [])) | set(r.get("p2p_failed", []))
    todo = [i for i in preds if i not in done]
    locks: dict[str, threading.Lock] = {}
    write = threading.Lock()
    print(f"{len(todo)} to evaluate ({len(done)} done)", flush=True)

    def one(iid):
        row = rows[iid]
        spec = parse(data / "tasks" / iid / "Dockerfile")
        lock = threading.Lock() if row["repo"] in PYTHONPATH_REPOS else locks.setdefault(env_key(spec), threading.Lock())
        origin = None
        if copies is not None:
            for arm in ("none", "verinoda_guided"):
                if (copies / iid / arm / ".git").exists():
                    origin = copies / iid / arm
                    break
        with lock:
            try:
                r = evaluate(data, row, preds[iid], origin, threading.current_thread().name.split("_")[-1], broken.get(iid, set()),
                             log_dir)
            except Exception as e:  # noqa: BLE001 - an instance that cannot be evaluated is a row with its error
                r = {"instance_id": iid, "resolved": None, "error": f"{type(e).__name__}: {e}"}
        with write, out.open("a", encoding="utf-8") as f:
            f.write(json.dumps(r) + "\n")
        print(f"{time.strftime('%H:%M:%S')} {iid} resolved={r.get('resolved')} calibrated={r.get('resolved_calibrated')} "
              f"{r.get('seconds')} s {r.get('error', '')}", flush=True)

    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(one, todo))
    return 0


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "build":
        return cmd_build(Path(argv[1]), argv[2:])
    if len(argv) >= 4 and argv[0] == "eval":
        data, preds, out = Path(argv[1]), Path(argv[2]), Path(argv[3])
        opts = argv[4:]

        def opt(name, default=None):
            return opts[opts.index(name) + 1] if name in opts else default

        only = opt("--only", "")
        return cmd_eval(data, preds, out, [x for x in only.split(",") if x], int(opt("--workers", "4")),
                        Path(opt("--keep-logs")) if opt("--keep-logs") else None,
                        Path(opt("--gold-report")) if opt("--gold-report") else None,
                        Path(opt("--copies")) if opt("--copies") else None)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
