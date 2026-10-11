"""The false-claims study's scripts (benchmarks/agent_compare/claims_*.py, DESIGN_CLAIMS.md): the task format and its
checks, both arms' prompts against the spec's text, the mechanical citation check, the blind judge and the summary."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"agent_compare_{name}", ROOT / "benchmarks" / "agent_compare" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


tasks_mod = _load("claims_tasks")


def _task(kind="why", n=1, repo="gin-gonic/gin", **over):
    t = {"id": f"gin-gonic__gin-{kind}-{n}", "repo": repo, "sha": "7" * 40, "kind": kind,
         "question": "Why does the engine recover from panics by default?",
         "gold": [{"statement": "recovery was added to stop one handler's panic killing the server", "commit": "abc1234",
                   "location": None}],
         "gold_sources": ["git log -S Recovery --oneline"]}
    if kind == "affects":
        t["gold_files"] = ["gin.go", "recovery.go"]
    if kind == "trap":
        t["gold"] = [{"statement": "unknown", "commit": None, "location": None}]
        t["unknown_reason"] = "the commit message is 'fix' with no body and no PR text"
    t.update(over)
    return t


def _full_set():
    """The real assignment of Task 7: repositories 1-8 one of each kind, 9-10 three `affects` and a trap (8/8/14/10)."""
    out = []
    for i, repo in enumerate(tasks_mod.REPOS):
        owner, name = repo.split("/")
        kinds = ([("why", 1), ("when", 1), ("affects", 1), ("trap", 1)] if i < 8
                 else [("affects", 1), ("affects", 2), ("affects", 3), ("trap", 1)])
        for kind, n in kinds:
            out.append(_task(kind, n, repo, id=f"{owner}__{name}-{kind}-{n}"))
    return out


# -- Task 1: format, order, validation ----------------------------------------------------------------------------------


def test_order_is_fixed_by_the_seeded_hash_and_independent_of_input_order():
    ids = ["b", "a", "c"]
    assert tasks_mod.order(ids) == tasks_mod.order(list(reversed(ids)))
    assert sorted(tasks_mod.order(ids)) == ["a", "b", "c"]


def test_a_valid_full_set_has_no_problems():
    assert tasks_mod.validate(_full_set()) == []


def test_validate_names_each_problem():
    bad = _full_set()
    bad[0]["kind"] = "when"  # kinds now 7/9/14/10
    bad[1]["gold"] = [{"statement": "x", "commit": None, "location": None}]  # neither commit nor location
    bad[2]["id"] = bad[3]["id"]  # repeated id
    problems = tasks_mod.validate(bad)
    assert any("when: 9" in p for p in problems)
    assert any("commit or location" in p and bad[1]["id"] in p for p in problems)
    assert any("repeated id" in p for p in problems)


def test_a_trap_needs_the_unknown_gold_and_a_reason_and_affects_needs_files():
    t = _task("trap", unknown_reason="")
    assert any("unknown_reason" in p for p in tasks_mod.validate([t] + _full_set()[1:]))
    a = _task("affects", gold_files=[])
    assert any("gold_files" in p for p in tasks_mod.validate([a] + _full_set()[1:]))


def test_load_tasks_raises_with_the_problems(tmp_path):
    p = tmp_path / "t.json"
    p.write_text(json.dumps({"tasks": [_task()]}), encoding="utf-8")
    with pytest.raises(ValueError, match="40 tasks"):
        tasks_mod.load_tasks(p)


# -- Task 2: leak check, re-derivation, the writer's and checker's prompts ------------------------------------------------


def _git_repo(tmp_path, filename="a.go", content="Recovery()\n", message="add recovery"):
    """One commit in a temporary repository; returns the short hash."""
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / filename).write_text(content, encoding="utf-8")
    who = ["-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(["git", *who, "add", filename], cwd=tmp_path, check=True)
    subprocess.run(["git", *who, "commit", "-q", "-m", message], cwd=tmp_path, check=True)
    return subprocess.run(["git", "rev-parse", "--short=8", "HEAD"], cwd=tmp_path, capture_output=True, text=True,
                          check=True).stdout.strip()


def test_leak_check_flags_paths_lines_hashes_and_gold_files():
    t = _task("affects", question="Does changing recovery.go line 42 (commit abc1234) break gin.go?",
              gold=[{"statement": "s", "commit": "abc1234", "location": "recovery.go:42"}])
    found = tasks_mod.leak_check(t)
    assert any("recovery.go" in f for f in found) and any("42" in f for f in found)
    assert any("abc1234" in f for f in found) and any("gin.go" in f for f in found)
    assert tasks_mod.leak_check(_task()) == []


def test_rederive_runs_only_read_commands_and_says_which_gold_they_reproduce(tmp_path):
    sha = _git_repo(tmp_path)
    t = _task(gold=[{"statement": "s", "commit": sha, "location": "a.go:1"}],
              gold_sources=["git log --oneline -S Recovery", "rm -rf ."])
    rows = tasks_mod.rederive(t, tmp_path)
    assert rows[0]["rc"] == 0 and rows[0]["reproduces"] == [0]
    assert rows[1]["rc"] == -1 and (tmp_path / "a.go").exists()


def test_prompts_carry_the_rules_and_the_shape():
    w = tasks_mod.writer_prompt("gin-gonic/gin", Path("C:/w/gin"), tasks_mod.KINDS)
    for must in ("never run Verinoda", "atlas.db", "realworld/gold", "network", "trap", '"gold_sources"', "unknown_reason",
                 "why: 8"):
        assert must in w, must
    c = tasks_mod.checker_prompt("gin-gonic/gin", Path("C:/w/gin"), [_task()])
    for must in ("leak", "gold_sources", "ten minutes", '"ok"', _task()["id"]):
        assert must in c, must
