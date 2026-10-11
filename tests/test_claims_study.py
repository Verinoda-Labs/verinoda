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
    t = {"id": f"gin-gonic__gin-{kind}-{n}", "repo": repo, "sha": tasks_mod.SHA_OF[repo], "kind": kind,
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


# -- Task 3: the runner -----------------------------------------------------------------------------------------------------

run_mod = _load("claims_run")
SPEC = (ROOT / "benchmarks" / "agent_compare" / "DESIGN_CLAIMS.md").read_text(encoding="utf-8")


def _spec_quote(first_words: str) -> str:
    """The blockquote of the spec that starts with these words, joined to one line (the guide is indented under a list item)."""
    block = []
    on = False
    for raw in SPEC.splitlines():
        line = raw.lstrip()
        if line.startswith("> ") and (on or line[2:].startswith(first_words)):
            on = True
            block.append(line[2:].strip())
        elif on:
            break
    return " ".join(block)


def test_the_stance_and_the_guide_are_the_specs_text_word_for_word():
    assert run_mod.STANCE == _spec_quote("Answer the question below")
    assert run_mod.GUIDE == _spec_quote("Load the Verinoda tools first")  # the amendment's paragraph, not the original
    assert "ToolSearch" in run_mod.GUIDE


def test_both_arms_get_the_same_stance_and_only_the_guided_arm_the_guide():
    t = _task()
    copy = Path("C:/w/copies/x/none/r1")
    plain, guided = run_mod.prompt_for(t, copy, "none"), run_mod.prompt_for(t, copy, "verinoda_guided")
    assert run_mod.STANCE in plain and run_mod.GUIDE not in plain and t["question"] in plain
    assert guided.startswith(plain) and guided.endswith(run_mod.GUIDE)


def test_session_argv_pins_the_model_the_tools_and_the_turn_limit():
    cfg = {"model": "claude-sonnet-5-5", "claude": "claude", "plugin_dir": "P"}
    argv = run_mod.session_argv("q", "none", Path("C:/w"), cfg)
    assert argv[argv.index("--model") + 1] == "claude-sonnet-5-5"
    assert argv[argv.index("--allowedTools") + 1] == "Bash Read Glob Grep"
    assert argv[argv.index("--max-turns") + 1] == "40" and "--mcp-config" not in argv
    g = run_mod.session_argv("q", "verinoda_guided", Path("C:/w"), cfg)
    assert g[g.index("--allowedTools") + 1] == "Bash Read Glob Grep mcp__verinoda" and "--mcp-config" in g


def test_pilot_is_the_first_eight_of_the_order_with_one_repeat():
    tasks = _full_set()
    items = run_mod.plan(tasks, {"arms": ["none", "verinoda_guided"], "pilot": True, "repeats": 3}, done=set())
    assert len(items) == 16 and {i[2] for i in items} == {1}
    assert [t["id"] for t, _, _ in items[::2]] == tasks_mod.order([t["id"] for t in tasks])[:8]
    full = run_mod.plan(tasks, {"arms": ["none"], "repeats": 3}, done={(tasks[0]["id"], "none", 1)})
    assert len(full) == 40 * 3 - 1


def test_copy_for_is_a_shared_detached_clone_at_the_sha(tmp_path):
    import subprocess

    src = tmp_path / "src"
    src.mkdir()
    _git_repo(src, filename="f", content="x", message="m")
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=src, capture_output=True, text=True, check=True).stdout.strip()
    dest = tmp_path / "copy"
    run_mod.copy_for(src, dest, sha)
    assert (dest / "f").read_text(encoding="utf-8") == "x"
    assert (dest / ".git" / "objects" / "info" / "alternates").exists()
    run_mod.copy_for(src, dest, sha)  # a second call keeps a clean copy
    assert (dest / "f").read_text(encoding="utf-8") == "x"


# -- Task 4: the mechanical citation check and the neutralized text ------------------------------------------------------

score_mod = _load("claims_score")


def test_citations_are_found_and_normalized():
    c = score_mod.citations(r"see .\gin.go:236 and recovery.go:10-14, commit abc1234d; not 2026 and not 1234567890")
    locs = [x for x in c if x["kind"] == "location"]
    hashes = [x for x in c if x["kind"] == "commit"]
    assert [(x["path"], x["line"], x["end"]) for x in locs] == [("gin.go", 236, None), ("recovery.go", 10, 14)]
    assert [x["hash"] for x in hashes] == ["abc1234d"]


def _score_repo(tmp_path):
    sha = _git_repo(tmp_path, filename="gin.go", content="package gin\n\nfunc Recovery() {}\n", message="add Recovery middleware")
    (tmp_path / ".verinoda").mkdir()
    (tmp_path / ".verinoda" / "x").write_text("Recovery", encoding="utf-8")
    return sha


def test_check_citation_grades_location_and_commit(tmp_path):
    sha = _score_repo(tmp_path)
    claim = "`Recovery` is defined in gin.go"
    loc = {"kind": "location", "raw": "gin.go:3", "path": "gin.go", "line": 3, "end": None, "hash": None}
    assert score_mod.check_citation(loc, claim, tmp_path) == "confirmed"
    assert score_mod.check_citation({**loc, "line": 1}, "the `Timeout` option", tmp_path) == "wrong"
    assert score_mod.check_citation({**loc, "line": 99}, claim, tmp_path) == "missing"
    assert score_mod.check_citation({**loc, "path": ".verinoda/x", "line": 1}, claim, tmp_path) == "not_repo"
    com = {"kind": "commit", "raw": sha, "path": None, "line": None, "end": None, "hash": sha}
    assert score_mod.check_citation(com, "Recovery was added as middleware", tmp_path) == "confirmed"
    assert score_mod.check_citation(com, "Recovery was added in 1999", tmp_path) == "wrong"
    assert score_mod.check_citation({**com, "hash": "deadbee"}, claim, tmp_path) == "missing"
    assert score_mod.check_citation({**com, "hash": "abc12"}, claim, tmp_path) == "missing"


def test_neutralize_hides_the_tool_words():
    out = score_mod.neutralize("Verinoda's analyze (mcp__verinoda__analyze) says statically_verified; history_search found it")
    assert "erinoda" not in out and "analyze" not in out and "statically_verified" not in out and "history_search" not in out
    assert out.count(score_mod.NEUTRAL) == 5


# -- Task 5: the blind judge --------------------------------------------------------------------------------------------------


def test_judge_input_masks_the_answer_and_renders_the_gold():
    t = _task()
    s = score_mod.judge_input(t, "Verinoda analyze found it at gin.go:236")
    assert "erinoda" not in s and "gin.go:236" in s and t["gold"][0]["statement"] in s and "abc1234" in s
    trap = score_mod.judge_input(_task("trap"), "x")
    assert "holds no answer" in trap and _task("trap")["unknown_reason"] in trap
    assert "no tools" in s


def test_parse_judge_takes_the_first_object_and_refuses_the_wrong_shape():
    good = ('Here: {"claims": [{"text": "t", "grade": "correct", "stance": "fact", "cites": []}], "trap": null, '
            '"arm_guess": "A"} done')
    assert score_mod.parse_judge(good)["claims"][0]["grade"] == "correct"
    assert score_mod.parse_judge('{"claims": "no"}') is None
    assert score_mod.parse_judge('{"claims": [{"text": "t", "grade": "maybe", "stance": "fact", "cites": []}], "trap": null, '
                                 '"arm_guess": "A"}') is None
    assert score_mod.parse_judge("no json") is None
    nested = '{"claims": [{"text": "a {b} c", "grade": "correct", "stance": "fact", "cites": []}], "trap": {"verdict": "unknown_said"}, "arm_guess": "B"}'
    assert score_mod.parse_judge(nested)["trap"]["verdict"] == "unknown_said"


def test_judge_retries_once_then_records_failure(monkeypatch, tmp_path):
    calls = []

    def fake_run(argv, cwd, env=None, timeout=600, stdin=None):
        calls.append(argv)
        return 0, json.dumps({"result": "not json"}), "", 1.0

    monkeypatch.setattr(score_mod, "run", fake_run)
    out = score_mod.judge({"model": "claude-sonnet-5-5", "claude": "claude"}, _task(),
                          {"id": "x", "arm": "none", "repeat": 1, "answer": "a"}, tmp_path)
    assert len(calls) == 2 and out["judge_failed"] is True and out["judge"] is None
    assert calls[0][calls[0].index("--tools") + 1] == "" and calls[0][calls[0].index("--max-turns") + 1] == "1"
    assert "--allowedTools" not in calls[0]
    assert out["id"] == "x" and out["arm"] == "none" and out["repeat"] == 1


# -- Task 6: the summary, the decision rule, the blinding check and the hand-check sample -----------------------------------


def _judged(id, arm, rep, claims, trap=None, guess="A", failed=False):
    return {"id": id, "arm": arm, "repeat": rep, "judge_failed": failed,
            "judge": None if failed else {"claims": claims, "trap": trap, "arm_guess": guess}}


C_OK = {"text": "x", "grade": "correct", "stance": "fact", "cites": ["a.go:1"]}
C_BAD = {"text": "y", "grade": "incorrect", "stance": "fact", "cites": []}
C_INF = {"text": "z", "grade": "incorrect", "stance": "inference", "cites": []}


def test_answer_values_separate_false_fact_from_false_inference_and_uncited():
    mech = {"citations": [{"raw": "a.go:1", "verdict": "confirmed"}]}
    v = score_mod.answer_values(_judged("t", "none", 1, [C_OK, C_INF]), mech, "why")
    assert v["false_fact"] == 0 and v["false_inference"] == 1 and v["inference_claims"] == 1 and v["correct_uncited"] == 0
    v = score_mod.answer_values(_judged("t", "none", 1, [{**C_OK, "cites": []}, C_BAD]), {"citations": []}, "why")
    assert v["false_fact"] == 1 and v["correct_uncited"] == 1 and v["incorrect_facts"] == 1 and v["fact_claims"] == 2
    assert score_mod.answer_values(_judged("t", "none", 1, [], failed=True), {"citations": []}, "why") is None


def test_a_trap_answered_with_a_confirmed_citation_is_reclassified_not_confabulated():
    j = _judged("t", "none", 1, [C_OK], trap={"verdict": "answered_with_evidence"})
    v = score_mod.answer_values(j, {"citations": [{"raw": "a.go:1", "verdict": "confirmed"}]}, "trap")
    assert v["reclassified"] is True and v["confabulated"] is None
    j2 = _judged("t", "none", 1, [C_BAD], trap={"verdict": "confabulated"})
    assert score_mod.answer_values(j2, {"citations": []}, "trap")["confabulated"] == 1
    j3 = _judged("t", "none", 1, [C_OK], trap={"verdict": "answered_with_evidence"})
    assert score_mod.answer_values(j3, {"citations": [{"raw": "a.go:1", "verdict": "wrong"}]}, "trap")["confabulated"] == 1


def test_summary_pairs_drops_lists_and_decides():
    tasks = _full_set()
    ids = [t["id"] for t in tasks]
    kinds = {t["id"]: t["kind"] for t in tasks}
    rows, judged, mechs = [], [], []
    for i in ids:
        for arm in ("none", "verinoda_guided"):
            for rep in (1, 2, 3):
                err = i == ids[0] and arm == "none"  # every plain repeat of task 0 errored
                rows.append({"id": i, "arm": arm, "repeat": rep, "is_error": err, "answer": "" if err else "a",
                             "num_turns": 3, "cost_usd": 0.1, "seconds": 10, "input_tokens": 100, "output_tokens": 10,
                             "verinoda_calls": 0, "usage_log_lines": 0})
                if kinds[i] == "trap":
                    claims, trap = [C_BAD], {"verdict": "confabulated" if arm == "none" else "unknown_said"}
                else:
                    claims, trap = ([C_BAD] if arm == "none" else [C_OK]), None
                judged.append(_judged(i, arm, rep, claims, trap, guess="A" if arm == "none" else "B"))
                mechs.append({"id": i, "arm": arm, "repeat": rep, "citations": []})
    s = score_mod.summary(tasks, rows, judged, mechs)
    assert s["dropped_tasks"] == [ids[0]] and len(s["errored_sessions"]) == 3
    p = s["primary"]["answerable_false_fact"]
    assert p["none"] == 1.0 and p["verinoda_guided"] == 0.0 and p["claim"] is True and p["ci95"][1] < 0
    assert s["primary"]["trap_confabulated"]["claim"] is True
    assert s["blinding"]["failed"] is True and s["blinding"]["accuracy"] == 1.0
    assert set(s["by_kind"]) == {"why", "when", "affects", "trap"}
    assert s["pairs"] == 39 and s["judge_failed"] == [] and s["writer_errors"] == []


def test_hand_sample_is_blind_and_balanced():
    judged = [_judged(f"t{i}", arm, 1, [C_OK, C_BAD]) for i in range(30) for arm in ("none", "verinoda_guided")]
    sample = score_mod.hand_sample(judged)
    assert len(sample) == 40 and all("arm" not in s for s in sample)
    key = score_mod.hand_key(judged, sample)
    assert sorted(key.values()).count("none") == 20


# -- Task 7 rulings: the sha against the manifest, single-branch clones, headless writers --------------------------------------


def test_validate_checks_the_sha_against_the_manifest():
    bad = _full_set()
    bad[5]["sha"] = "0" * 40
    assert any("manifest" in p and bad[5]["id"] in p for p in tasks_mod.validate(bad))
    assert tasks_mod.SHA_OF["gin-gonic/gin"] == _task()["sha"]


def test_writer_prompt_carries_the_sha_and_asks_for_forward_slashes():
    w = tasks_mod.writer_prompt("gin-gonic/gin", Path("C:/w/gin"), tasks_mod.KINDS)
    assert tasks_mod.SHA_OF["gin-gonic/gin"] in w and "forward slashes" in w


def test_clone_argv_is_single_branch_at_the_tag_without_other_tags():
    argv = run_mod.clone_argv("gin-gonic/gin", "v1.12.0", Path("C:/w/clones/gin-gonic__gin"))
    assert "--single-branch" in argv and "--no-tags" in argv and argv[argv.index("--branch") + 1] == "v1.12.0"
    assert "https://github.com/gin-gonic/gin.git" in argv


def test_a_copy_holds_no_history_past_its_source(tmp_path):
    import subprocess

    src = tmp_path / "src"
    src.mkdir()
    _git_repo(src, filename="f", content="x", message="m")
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=src, capture_output=True, text=True, check=True).stdout.strip()
    dest = tmp_path / "copy"
    run_mod.copy_for(src, dest, sha)
    count = lambda *a: subprocess.run(["git", "rev-list", "--count", *a], cwd=dest, capture_output=True, text=True,
                                      check=True).stdout.strip()
    assert count("--all") == count("HEAD") == "1"


def test_agent_argv_isolates_the_writer_like_a_study_session():
    argv = tasks_mod.agent_argv("prompt", {"model": "claude-opus-5-5", "claude": "claude"})
    assert argv[argv.index("--model") + 1] == "claude-opus-5-5" and "--strict-mcp-config" in argv
    assert argv[argv.index("--allowedTools") + 1] == "Bash Read Glob Grep" and "--mcp-config" not in argv
    assert argv[argv.index("--setting-sources") + 1] == "project,local"


def test_parse_tasks_output_takes_the_first_object_with_a_tasks_list():
    assert tasks_mod.parse_agent_json('text {"tasks": [{"id": "a"}]} more', "tasks") == {"tasks": [{"id": "a"}]}
    assert tasks_mod.parse_agent_json('{"x": 1} {"results": []}', "results") == {"results": []}
    assert tasks_mod.parse_agent_json("nothing", "tasks") is None


def test_rederive_records_a_program_that_is_not_installed_instead_of_raising(tmp_path, monkeypatch):
    def missing(argv, cwd, env=None, timeout=600, stdin=None):
        raise FileNotFoundError(argv[0])

    monkeypatch.setattr(tasks_mod, "run", missing)
    t = _task(gold_sources=["rg -n Recovery"])
    rows = tasks_mod.rederive(t, tmp_path)
    assert rows[0]["rc"] == -2 and "not found" in rows[0]["note"] and rows[0]["reproduces"] == []


def test_writer_prompt_limits_gold_and_traps_after_the_gin_trial():
    w = tasks_mod.writer_prompt("gin-gonic/gin", Path("C:/w/gin"), tasks_mod.KINDS)
    assert "at most 3 gold statements" in w and "rg is not installed" in w
    assert "A trap is a why or a when" in w and "symbol with no caller" not in w


# -- after the pilot: the mechanical check was too strict (8 of 8 sampled `wrong` verdicts were correct citations) ------------


def test_identifiers_split_backticked_spans_and_drop_citations_and_hashes():
    ids = score_mod.identifiers("`SQLModelMetaclass.__init__` calls it at `sqlmodel/main.py:671-672`")
    assert "SQLModelMetaclass" in ids and "__init__" in ids and not any(":" in i or "/" in i for i in ids)
    ids = score_mod.identifiers("The fix is likely commit `472d086`: \"fix(tree): panic in findCaseInsensitivePathRec\"")
    assert "472d086" not in ids and "findCaseInsensitivePathRec" in ids
    assert "ToRunes" in score_mod.identifiers("asserts `&runes[0] == &chars.ToRunes()[0]`")


def test_check_citation_accepts_an_identifier_of_the_question_and_a_hash_whose_diff_holds_the_claim(tmp_path):
    sha = _score_repo(tmp_path)
    loc = {"kind": "location", "raw": "gin.go:3", "path": "gin.go", "line": 3, "end": None, "hash": None}
    assert score_mod.check_citation(loc, "it is called here", tmp_path) == "wrong"
    assert score_mod.check_citation(loc, "it is called here", tmp_path, extra=["Recovery"]) == "confirmed"
    com = {"kind": "commit", "raw": sha, "path": None, "line": None, "end": None, "hash": sha}
    # `func Recovery` is in the commit's diff, not in its message: the diff counts
    assert score_mod.check_citation(com, "this commit introduced `func Recovery`", tmp_path) == "confirmed"


def test_mechanical_passes_the_questions_identifiers(tmp_path):
    _score_repo(tmp_path)
    row = {"id": "t", "arm": "none", "repeat": 1, "answer": "- It is defined at gin.go:3."}
    task = {"question": "Where is `Recovery` defined?"}
    assert score_mod.mechanical(row, tmp_path, task)["citations"][0]["verdict"] == "confirmed"
