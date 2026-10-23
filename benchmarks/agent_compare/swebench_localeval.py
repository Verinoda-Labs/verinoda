"""Evaluate SWE-bench Lite patches on Windows without Docker (not the official harness): each instance's Python environment
is rebuilt as a venv from its task-repo Dockerfile (`swebench_envspec.py`), its eval script's test command runs on a clean
copy of the base commit with the patch and the test patch applied, and SWE-bench's own log parser and grading decide.

    python swebench_localeval.py build DATA [IDS...]
    python swebench_localeval.py eval DATA PREDICTIONS.jsonl OUT.jsonl [--only IDS] [--workers N] [--keep-logs DIR]
        [--gold-report GOLD.jsonl[,MORE.jsonl]] [--copies DIR]
    python swebench_localeval.py regrade DATA OUT.jsonl LOG_DIR GOLD.jsonl[,MORE.jsonl] NEW_OUT.jsonl

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
# projects with compiled extensions, and the folder they are imported from: built once per instance, their build outputs then
# copied into each checkout of it (a build per evaluation would take minutes each)
COMPILED = {"scikit-learn/scikit-learn": ".", "matplotlib/matplotlib": "lib", "astropy/astropy": "."}
# installed from the environment file but unusable on Windows: eccodes needs its C library, which conda would have provided
WINDOWS_BROKEN = {"pydata/xarray": ["cfgrib", "eccodes"]}
# what pytest requires on Windows only (sys_platform == "win32"), so the image's Linux freeze lacks it: a pytest before 7.2
# does not import without atomicwrites
WINDOWS_DEPS = ("atomicwrites", "colorama")
REBUILD = re.compile(r"^diff --git a/(\S+\.(?:pyx|pxd|pxi|c|cpp|cc|h|hpp)|\S*setup\.py|\S*pyproject\.toml) ", re.MULTILINE)
APPLY =[["git", "apply", "--verbose"], ["git", "apply", "--verbose", "--reject"],
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


def run_env_for(env: Path) -> dict:
    return {**{k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "PYTHON", "VIRTUAL_ENV"))},
            "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
            "VIRTUAL_ENV": str(env), "PATH": f"{env / 'Scripts'}{os.pathsep}{os.environ.get('PATH', '')}"}


def build_env_for(run_env: dict) -> dict:
    """`run_env` for a compiled build: matplotlib before 3.6 builds its bundled freetype with msbuild on Windows, which a
    Visual Studio Build Tools install keeps off PATH."""
    vs = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Microsoft Visual Studio"
    found = sorted(vs.glob("*/*/MSBuild/Current/Bin/amd64"))
    return {**run_env, "PATH": f"{run_env['PATH']}{os.pathsep}{found[-1]}"} if found else run_env


def write_generated(src: Path, row: dict) -> None:
    """The files the project's own install generates and a checkout lacks. pytest's version module comes from setuptools_scm
    at install time; the copies have no tags and the envs no setuptools_scm, so without it `_pytest._version` is missing and
    no test imports (D184's four pytest instances)."""
    if row["repo"] == "pytest-dev/pytest" and (src / "src" / "_pytest").is_dir():
        version = f"{row['version']}.0"
        parts = tuple(int(x) for x in version.split("."))
        (src / "src" / "_pytest" / "_version.py").write_text(
            f"version = __version__ = {version!r}\nversion_tuple = __version_tuple__ = {parts!r}\n", encoding="utf-8",
            newline="\n")


def run_install(src: Path, row: dict, spec: dict, py: Path, run_env: dict) -> int:
    """The Dockerfile's install lines in `src`, as the image runs them. With dependencies: the venv holds the image's
    environment file, and the project's own install added what that file lacks (sphinx's sphinxcontrib packages, pytest's
    atomicwrites on Windows); pip leaves what is installed and satisfies the requirement alone. With build isolation unless the
    line turns it off: a project built by flit_core (sphinx 6 and later) or a compiled one needs its build requirements."""
    fix_env(py.parent.parent, row["repo"], spec)
    env = {**run_env, "SETUPTOOLS_SCM_PRETEND_VERSION": f"{row['version']}.0"}
    rc = 0
    for line in spec["install"]:
        if line.startswith("sed -i "):
            subprocess.run(["bash", "-c", line], cwd=src, capture_output=True, check=False)
        elif "pip install" in line:
            target = re.search(r"pip install (.*)$", line).group(1)
            target = re.sub(r"--verbose|-v\b", "", target).split()
            rc = subprocess.run([str(py), "-m", "pip", "install", "-q", *target], cwd=src, capture_output=True, env=env,
                                timeout=3 * TIMEOUT, check=False).returncode
    return rc


def fix_env(env: Path, repo: str, spec: dict) -> None:
    """Once per environment, and recorded in its marker: remove the packages that install on Windows without the system
    library they load (xarray's tests then fail to collect instead of skipping), add what the environment's pytest needs
    on Windows to import (WINDOWS_DEPS; pytest's own checkout is installed with its dependencies by `run_install` instead),
    and give the image's pip where the install lines use an option today's pip no longer has (scikit-learn's
    ``--no-use-pep517``, gone in pip 26)."""
    marker = env / "verinoda-env.json"
    info = json.loads(marker.read_text(encoding="utf-8"))
    remove = WINDOWS_BROKEN.get(repo) if "removed" not in info else None
    legacy = bool(spec.get("pip")) and any("--no-use-pep517" in x for x in spec["install"]) and "legacy_pip" not in info
    if not remove and not legacy and "windows_deps" in info:
        return
    py = str(venv_python(env))
    if legacy:
        options = subprocess.run([py, "-m", "pip", "install", "--help"], capture_output=True, text=True, check=False).stdout
        replace = "--no-use-pep517" not in options
        if replace:
            subprocess.run([py, "-m", "pip", "install", "-q", f"pip=={spec['pip']}"], capture_output=True, check=False)
        info["legacy_pip"] = spec["pip"] if replace else None
    if remove:
        subprocess.run([py, "-m", "pip", "uninstall", "-q", "-y", *remove], capture_output=True, check=False)
        info["removed"] = remove
    if "windows_deps" not in info:
        added = []
        for _ in WINDOWS_DEPS:
            p = subprocess.run([py, "-c", "import pytest"], capture_output=True, text=True, check=False)
            missing = re.search(r"No module named '(\w+)'", p.stderr)
            if p.returncode == 0 or not missing or missing.group(1) not in WINDOWS_DEPS:
                break
            subprocess.run([py, "-m", "pip", "install", "-q", "--no-deps", missing.group(1)], capture_output=True,
                           check=False)
            added.append(missing.group(1))
        info["windows_deps"] = added
    marker.write_text(json.dumps(info, indent=1), encoding="utf-8")


def build_outputs(data: Path, row: dict, spec: dict, origin: Path | None) -> dict:
    """A compiled project's build at the base commit, made once per instance in ``DATA/build/<id>``: the ignored files the
    build leaves there (extension modules, generated sources, the version file) are its outputs."""
    iid, base = row["instance_id"], row["base_commit"]
    root, marker = data / "build" / iid, data / "build" / f"{iid}.json"
    if marker.exists():
        return {**json.loads(marker.read_text(encoding="utf-8")), "root": root}
    t0 = time.perf_counter()
    if not (root / ".git").exists():
        if origin is None:
            raise FileNotFoundError(f"no checkout to build {iid} from")
        root.parent.mkdir(parents=True, exist_ok=True)
        git("clone", "-q", "--no-checkout", str(origin), str(root))
    git("checkout", "-q", "-f", base, cwd=root)
    git("clean", "-fdxq", cwd=root)
    env = data / "envs" / env_key(spec)
    rc = run_install(root, row, spec, venv_python(env), build_env_for(run_env_for(env)))
    git("checkout", "-q", "-f", base, "--", ".", cwd=root, check=False)  # the install's sed lines changed tracked files
    listed = git("ls-files", "--others", "--ignored", "--exclude-standard", cwd=root).stdout.decode("utf-8").splitlines()
    outputs = [p for p in listed if not p.startswith("build/") and "__pycache__" not in p]
    info = {"rc": rc, "ok": any(p.endswith((".pyd", ".so")) for p in outputs), "outputs": outputs,
            "seconds": round(time.perf_counter() - t0, 1)}
    marker.write_text(json.dumps(info, indent=1), encoding="utf-8")
    return {**info, "root": root}


def copy_outputs(build: dict, dest: Path) -> None:
    for rel in build["outputs"]:
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(build["root"] / rel, target)


def install_checkout(src: Path, row: dict, spec: dict, py: Path, run_env: dict, build: dict | None = None,
                     rebuild: bool = False) -> None:
    """Make the checkout importable the way the image does: through PYTHONPATH, with the Dockerfile's install lines, or, for
    a compiled project (`build`, from `build_outputs`), with its build outputs copied in and imported through PYTHONPATH (a
    patch that changes compiled sources, `rebuild`, is built again in place)."""
    fix_env(py.parent.parent, row["repo"], spec)
    write_generated(src, row)
    if row["repo"] in PYTHONPATH_REPOS:
        run_env["PYTHONPATH"] = str(src)
    elif row["repo"] in COMPILED and build is not None:
        copy_outputs(build, src)
        if rebuild:  # in place: an editable install would point the shared environment at this patched checkout
            subprocess.run([str(py), "setup.py", "build_ext", "--inplace"], cwd=src, capture_output=True,
                           env={**build_env_for(run_env), "SETUPTOOLS_SCM_PRETEND_VERSION": f"{row['version']}.0"},
                           timeout=3 * TIMEOUT, check=False)
        run_env["PYTHONPATH"] = str(src / COMPILED[row["repo"]])
    else:
        run_install(src, row, spec, py, run_env)


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
    run_env = run_env_for(env)
    build = build_outputs(data, row, spec, origin) if row["repo"] in COMPILED else None
    if build is not None:
        res["build_ok"] = build["ok"]
    install_checkout(src, row, spec, py, run_env, build, rebuild=bool(REBUILD.search(patch_text)))
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
    # the shared environment's editable install points here: the patch and the test patch do not stay on disk after the run
    git("reset", "-q", "--hard", base, cwd=src, check=False)
    git("clean", "-fdxq", cwd=src, check=False)
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


def load_broken(gold_report: Path | None) -> dict[str, set[str]]:
    """The tests that fail here with the gold patch, per instance; ``gold_report`` may name several files (comma-separated),
    a later row for an instance replacing an earlier one."""
    broken: dict[str, set[str]] = {}
    for path in str(gold_report or "").split(","):
        if path and Path(path).exists():
            for x in Path(path).read_text(encoding="utf-8").splitlines():
                if x.strip():
                    r = json.loads(x)
                    broken[r["instance_id"]] = set(r.get("f2p_failed") or []) | set(r.get("p2p_failed") or [])
    return broken


def cmd_regrade(data: Path, results: Path, logs: Path, gold_report: Path, out: Path) -> int:
    """Grade an evaluation again from its kept logs with a newer gold report (no test runs)."""
    rows, broken = rows_of(data), load_broken(gold_report)
    lines = []
    for x in results.read_text(encoding="utf-8").splitlines():
        if not x.strip():
            continue
        r = json.loads(x)
        log = logs / f"{r['instance_id']}.log"
        if r.get("patch_applied") and log.exists():
            skip = broken.get(r["instance_id"], set())
            g = grade(rows[r["instance_id"]], log.read_text(encoding="utf-8"), skip)
            r.update({"resolved": g["strict"]["resolved"], "resolved_calibrated": g["calibrated"]["resolved"],
                      "env_broken": sorted(skip)})
        lines.append(json.dumps(r))
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(lines)} rows regraded into {out}", flush=True)
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
    broken = load_broken(gold_report)
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
    if len(argv) == 6 and argv[0] == "regrade":
        return cmd_regrade(*(Path(a) for a in argv[1:]))
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
