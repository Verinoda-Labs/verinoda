# False-claims study (DESIGN_CLAIMS.md) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the harness that measures, on why / when / what-it-affects questions over ten real repositories, whether a Claude Code agent using Verinoda states fewer false facts and says "unknown" more often than the same agent alone; then write the 40 tasks, run the 8-task pilot and fix N.

**Architecture:** Three standard-library Python scripts beside the earlier studies in `benchmarks/agent_compare/`, reusing their session runner (`guard_run.run`, `big_run.run_by_arm`, `session_stats`, `isolated_plugin_store`) and bootstrap (`swebench_score.boot`): `claims_tasks.py` (task format, validation, leak and re-derivation checks, the writer's and checker's prompts), `claims_run.py` (full clones, per-session copies, the two arms' prompts, one JSONL row per session with the final answer), `claims_score.py` (mechanical citation check, blind judge, blinding check, paired bootstrap, hand-check sample). The 40 tasks are data (`claims_tasks.json`), written by agents under the rules of the spec and committed before the first session.

**Tech Stack:** Python 3.12 standard library only (as every script in this folder); `claude -p` as a subprocess; git; pytest for the tests (`tests/test_claims_study.py`, loaded with the `_load` pattern of `tests/test_agent_compare.py`).

**Spec:** `benchmarks/agent_compare/DESIGN_CLAIMS.md` (committed `c13685a`, plus the amendment of 2026-10-11 that replaces the guided arm's paragraph with one that loads the tools first). Amendments go at its end, dated; it is never edited in place.

**Lint:** every commit step runs `ruff check` on the files it adds. The test snippets below are written to pass it: one import per line, no `a; b` on one line, no unused import. An implementer who pastes a snippet keeps that.

## Global Constraints

- Model pinned in both arms and in the judge: `claude-sonnet-5-5`.
- Tools of a session: `Bash Read Glob Grep` (`+ mcp__verinoda` in the Verinoda arm); `--setting-sources project,local --strict-mcp-config`; at most 40 turns; the user's `verinoda` off `PATH`.
- Both arms receive the **stance** paragraph of the spec word for word; the Verinoda arm adds the **guide** paragraph of the 2026-10-11 amendment (the one that starts "Load the Verinoda tools first") word for word. Both strings live in `claims_run.py` and the tests compare them to the spec's text.
- The judge runs with `--tools ""` (the flag that disables every built-in tool in `claude -p`; `--allowedTools ""` does not) and `--max-turns 1`, and its prompt says it has no tools.
- Tasks: 40 = `why` 8, `when` 8, `affects` 14, `trap` 10; 4 per repository of `benchmarks/realworld/manifest.json`; order by `sha256("20261011:" + id)`.
- Repeats: 3 per task and arm (pilot: the first 8 of the order, 1 repeat). Pilot sessions stay in the sample.
- Unit of scoring: the claim. Primary: share of answers with ≥1 claim graded `incorrect` and stated as `fact` (answerable); share `confabulated` (traps). Bootstrap over tasks, 10,000 resamples, seed `20261011`; a claim only when the 95 % interval excludes zero.
- Judge sees the final answer text only, neutralized; its arm guess is recorded; blinding failed when the interval of its accuracy excludes 0.5.
- Hand check: 40 claims, 20 per arm, drawn blind; a disagreement rate above 20 % stops the report.
- Repository rules: lint only the files you change (`ruff check <file>`); never touch `benchmarks/results/**` that exists; `.venv/Scripts/python.exe -m pytest tests/test_claims_study.py -q`; no commit of `.claude/`; author identity `CINAR1311 <292587747+ozcinax-star@users.noreply.github.com>`; code comments cite the spec, never a backlog id.
- Windows: write files with the file tools; paths may carry backslashes; `git` reads with `guard_run.git_env()`.

## Review Focus

1. A citation into the tool's own files (`.verinoda/...`, `atlas.db`, `.claude/...`, `.mcp.json`) is not repository evidence: `check_citation` grades it `not_repo`, and the summary counts it with `uncited`. Test in Task 4.
2. An errored or empty session (`is_error`, no `answer`) is neither a false claim nor an "unknown": `task_values` leaves that repeat out, the summary lists every such session, and a task whose arm has no valid repeat leaves the pairs with its id listed. Test in Task 6.
3. A judge answer that is not the expected JSON is retried once; a second failure records `judge_failed` for that session and the summary lists it; the session is not silently counted as having no claims. Test in Task 5.
4. A trap the agent answers with a citation the mechanical check `confirmed` is reclassified: out of the trap primary, into `writer_errors` of the summary, never counted as `confabulated`. Test in Task 6.
5. A `path:line` citation written with backslashes, a leading `./`, or a range `a-b` is normalized before the file is looked up; a hash shorter than 7 hex characters is `missing`. Test in Task 4.

---

### Task 1: Task format, order and validation (`claims_tasks.py`)

**Files:**
- Create: `benchmarks/agent_compare/claims_tasks.py`
- Create: `tests/test_claims_study.py`

**Interfaces:**
- Produces: `KINDS = {"why": 8, "when": 8, "affects": 14, "trap": 10}`; `SEED = "20261011:"`; `REPOS: list[str]` (the ten `name` fields of `benchmarks/realworld/manifest.json`, read at import); `order(ids: list[str]) -> list[str]`; `validate(tasks: list[dict]) -> list[str]` (each string one problem, empty when valid); `load_tasks(path: Path) -> list[dict]` (reads, validates, raises `ValueError` with the problems joined).
- Task object (the spec's fields, fixed here): `{"id": "<owner>__<name>-<kind>-<n>", "repo": "<owner>/<name>", "sha": "<40 hex>", "kind": "why|when|affects|trap", "question": str, "gold": [{"statement": str, "commit": "<7-40 hex>" | null, "location": "path:line" | null}], "gold_sources": [str, ...], "gold_files": [str, ...] (affects only, non-empty), "unknown_reason": str (trap only, non-empty)}`. A trap's `gold` is exactly `[{"statement": "unknown", "commit": null, "location": null}]`. Every non-trap gold item has a `commit` or a `location`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_claims_study.py
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
         "gold": [{"statement": "recovery was added to stop one handler's panic killing the server", "commit": "abc1234", "location": None}],
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
        kinds = [("why", 1), ("when", 1), ("affects", 1), ("trap", 1)] if i < 8 else [("affects", 1), ("affects", 2), ("affects", 3), ("trap", 1)]
        for kind, n in kinds:
            out.append(_task(kind, n, repo, id=f"{owner}__{name}-{kind}-{n}"))
    return out

def test_order_is_fixed_by_the_seeded_hash_and_independent_of_input_order():
    ids = ["b", "a", "c"]
    assert tasks_mod.order(ids) == tasks_mod.order(list(reversed(ids)))
    assert sorted(tasks_mod.order(ids)) == ["a", "b", "c"]

def test_a_valid_full_set_has_no_problems():
    assert tasks_mod.validate(_full_set()) == []

def test_validate_names_each_problem():
    bad = _full_set()
    bad[0]["kind"] = "when"                                 # kinds now 8/9/13/10
    bad[1]["gold"] = [{"statement": "x", "commit": None, "location": None}]   # neither commit nor location
    bad[2]["id"] = bad[3]["id"]                             # repeated id
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
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_claims_study.py -q`
Expected: FAIL, `claims_tasks.py` not found.

- [ ] **Step 3: Implement `claims_tasks.py`**

Module docstring in the folder's style (what it is, the command line, the spec). `REPOS` from the manifest. `order()` sorts by `hashlib.sha256((SEED + id).encode()).hexdigest()`. `validate()` checks, in this order and with these words in the messages: exactly `40 tasks`; `repeated id`; per repo exactly 4 (`<repo>: N tasks`); per kind the count (`<kind>: N`); every required field a non-empty string / list; `kind` in `KINDS`; `sha` 40 hex; a non-trap gold item has `commit or location`; `affects` has non-empty `gold_files`; a trap has `unknown_reason` and the fixed gold; `question` ends with `?`. `load_tasks()` reads `{"tasks": [...]}`, raises `ValueError("\n".join(problems))`.

- [ ] **Step 4: Run the tests to see them pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_claims_study.py -q`
Expected: 5 passed.

- [ ] **Step 5: Lint and commit**

```bash
.venv/Scripts/ruff.exe check benchmarks/agent_compare/claims_tasks.py tests/test_claims_study.py
git add benchmarks/agent_compare/claims_tasks.py tests/test_claims_study.py
git commit -m "False-claims study: task format, fixed order and validation (DESIGN_CLAIMS.md)"
```

---

### Task 2: Leak check, re-derivation and the writer's and checker's prompts (`claims_tasks.py`)

**Files:**
- Modify: `benchmarks/agent_compare/claims_tasks.py`
- Modify: `tests/test_claims_study.py`

**Interfaces:**
- Produces: `leak_check(task: dict) -> list[str]` (a question that names a path, a line number, a hash, or a gold file of an `affects` task, each a string); `rederive(task: dict, clone: Path) -> list[dict]` (one row per `gold_sources` command: `{"command": str, "rc": int, "reproduces": [gold indices whose commit or location's path appears in the output]}`; runs only commands whose first word is `git`, `grep`, `rg` or `findstr`, through `shlex.split` and `guard_run.run`, refusing anything else with `rc: -1`); `WRITER_PROMPT: str`, `CHECKER_PROMPT: str` (both with `{repo}`, `{clone}`, `{kinds}` placeholders; the checker's also `{tasks_json}`); `writer_prompt(repo, clone, kinds: dict) -> str`, `checker_prompt(repo, clone, tasks) -> str`.
- The writer's prompt carries verbatim: the four kinds with their gold sources (the spec's table), the rules (no path, line, symbol spelling or copied wording the question does not need; never run Verinoda, never read `atlas.db`, never read `benchmarks/realworld/gold/` or earlier studies; no network; a commit without rationale is a trap candidate, not a `why`), the trap definition ("a thing that exists, no answer in the repository": the three examples of the spec), and the JSON shape of Task 1 as the only output. The checker's prompt carries: the three checks (leak; a gold statement its `gold_sources` do not reproduce; a trap whose answer it can find in ten minutes of git and search), and the output `{"id": ..., "ok": bool, "problems": [...]}` per task.

- [ ] **Step 1: Write the failing tests**

```python
def test_leak_check_flags_paths_lines_hashes_and_gold_files():
    t = _task("affects", question="Does changing recovery.go line 42 (commit abc1234) break gin.go?")
    found = tasks_mod.leak_check(t)
    assert any("recovery.go" in f for f in found) and any("42" in f for f in found)
    assert any("abc1234" in f for f in found) and any("gin.go" in f for f in found)
    assert tasks_mod.leak_check(_task()) == []

def test_rederive_runs_only_read_commands_and_says_which_gold_they_reproduce(tmp_path):
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "a.go").write_text("Recovery()\n", encoding="utf-8")
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "add", "a.go"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "add recovery"], cwd=tmp_path, check=True)
    sha = subprocess.run(["git", "rev-parse", "--short=7", "HEAD"], cwd=tmp_path, capture_output=True, text=True).stdout.strip()
    t = _task(gold=[{"statement": "s", "commit": sha, "location": "a.go:1"}],
              gold_sources=["git log --oneline -S Recovery", "rm -rf ."])
    rows = tasks_mod.rederive(t, tmp_path)
    assert rows[0]["rc"] == 0 and rows[0]["reproduces"] == [0]
    assert rows[1]["rc"] == -1 and (tmp_path / "a.go").exists()

def test_prompts_carry_the_rules_and_the_shape():
    w = tasks_mod.writer_prompt("gin-gonic/gin", Path("C:/w/gin"), tasks_mod.KINDS)
    for must in ("never run Verinoda", "atlas.db", "realworld/gold", "network", "trap", '"gold_sources"', "unknown_reason", "why: 8"):
        assert must in w, must
    c = tasks_mod.checker_prompt("gin-gonic/gin", Path("C:/w/gin"), [_task()])
    for must in ("leak", "gold_sources", "ten minutes", '"ok"', _task()["id"]):
        assert must in c, must
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_claims_study.py -q -k "leak or rederive or prompts"`
Expected: FAIL, attributes missing.

- [ ] **Step 3: Implement the four functions and the two prompts**

`leak_check`: tokens of the question matched against the gold's paths (by basename too), line numbers of `location`, hashes (any 7+ hex run of the question equal to a prefix of a gold commit), and `gold_files` basenames. `rederive`: the allow-list by first word; output matched for each gold item's `commit` (prefix) or `location` path. Prompts as `str` constants with `.format`.

- [ ] **Step 4: Run the tests to see them pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_claims_study.py -q`
Expected: 8 passed.

- [ ] **Step 5: Lint and commit**

```bash
.venv/Scripts/ruff.exe check benchmarks/agent_compare/claims_tasks.py tests/test_claims_study.py
git add benchmarks/agent_compare/claims_tasks.py tests/test_claims_study.py
git commit -m "False-claims study: leak check, re-derivation and the writer's and checker's prompts"
```

---

### Task 3: Runner (`claims_run.py`)

**Files:**
- Create: `benchmarks/agent_compare/claims_run.py`
- Modify: `tests/test_claims_study.py`

**Interfaces:**
- Consumes: `claims_tasks.load_tasks`, `claims_tasks.order`; `guard_run.run`, `git_env`, `find_transcript`, `_force_remove`; `big_run.claude_version`, `isolated_plugin_store`, `run_by_arm`, `session_stats`; `swebench_prepare.setup_verinoda`, `swebench_run.claude_exe`, `swebench_run.env_for`.
- Produces: `STANCE: str`, `GUIDE: str` (the spec's two paragraphs, verbatim, as single lines of text); `prompt_for(task: dict, copy: Path, arm: str) -> str` (`"Repository: <repo> at <copy>.\n\nQuestion: <question>\n\n" + STANCE`, `+ "\n\n" + GUIDE` in the Verinoda arm); `tools_for(arm) -> str` (`"Bash Read Glob Grep"`, `+ " mcp__verinoda"` for `verinoda_guided`); `session_argv(prompt, arm, copy, cfg) -> list[str]` (as `swebench_run.session_argv` with `tools_for` of this module, `--max-turns` default 40, `--permission-mode default`, no `--max-budget-usd` unless configured); `clone_full(repo: str, sha: str, dest: Path) -> None` (full `git clone https://github.com/<repo>.git`, `checkout --detach <sha>`, `core.autocrlf false`; an existing clone at the sha is kept; raises when `.git/shallow` exists afterwards); `copy_for(clone: Path, dest: Path, sha: str) -> None` (`git clone --shared --no-checkout`, `checkout --detach <sha>`, `core.autocrlf false`; idempotent like `swebench_prepare.fetch`); `one(cfg, task, arm, repeat: int) -> dict` (the row below); `main() -> int`.
- Row: `{"id", "arm", "repeat", "pilot": bool, "model", "claude", "exit", "seconds", "is_error", "subtype", "session_id", "num_turns", "cost_usd", "input_tokens", "output_tokens", "answer": full result text, "tool_calls", "verinoda_calls", "verinoda_tools": swebench_run.verinoda_tools(...), "network", "usage_log_lines": int, "setup_seconds": float | null}`.
- Config: `{"work", "model", "plugin_dir", "mod_options", "verinoda_bin", "drop_path", "arms", "arm_workers", "timeout_s", "max_turns", "repeats", "pilot": bool, "only": [...]}`. Layout: `WORK/clones/<owner>__<name>/`, `WORK/copies/<task id>/<arm>/r<repeat>/`, `WORK/results.jsonl` (resumable on `(id, arm, repeat)`), `WORK/usage/<task id>-<arm>-r<repeat>.jsonl` (`VERINODA_USAGE_LOG` of that session).
- `--pilot` (or `cfg["pilot"]`): the first 8 ids of `order()` with 1 repeat; otherwise every task with `cfg["repeats"]` (default 3).

- [ ] **Step 1: Write the failing tests**

```python
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
    assert run_mod.GUIDE == _spec_quote("Load the Verinoda tools first")   # the amendment's paragraph, not the original
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
    subprocess.run(["git", "init", "-q"], cwd=src, check=True)
    (src / "f").write_text("x", encoding="utf-8")
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "add", "f"], cwd=src, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "m"], cwd=src, check=True)
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=src, capture_output=True, text=True).stdout.strip()
    dest = tmp_path / "copy"
    run_mod.copy_for(src, dest, sha)
    assert (dest / "f").read_text(encoding="utf-8") == "x"
    assert (dest / ".git" / "objects" / "info" / "alternates").exists()
    run_mod.copy_for(src, dest, sha)   # a second call keeps a clean copy
```

`plan(tasks, cfg, done) -> list[tuple[dict, str, int]]` is the pure part of `main()`: the `(task, arm, repeat)` items still to run, pilot rule applied, ordered task-major in `order()`'s order, then arm in `cfg["arms"]` order, then repeat (so a task's two arms are adjacent and start together under `run_by_arm`).

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_claims_study.py -q -k "stance or arms or argv or pilot or copy_for"`
Expected: FAIL, module missing.

- [ ] **Step 3: Implement `claims_run.py`**

Docstring with the command line `python benchmarks/agent_compare/claims_run.py CONFIG.json [--pilot]` and the config keys. `main()`: load and validate tasks from `benchmarks/agent_compare/claims_tasks.json` (copied to `WORK/tasks.json`), `clone_full` per repository (serial, once), then for each item `copy_for` + `setup_verinoda` (guided arm only; its seconds in the row), `one()`, append the row under a lock, print one line per session as `swebench_run.main` does, inside `isolated_plugin_store()` when the guided arm runs. `one()` sets `VERINODA_USAGE_LOG` in the guided arm's env to the session's usage file and counts its lines afterwards. `clone_full` raises `RuntimeError("shallow clone")` if `.git/shallow` exists.

- [ ] **Step 4: Run the tests to see them pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_claims_study.py -q`
Expected: 13 passed.

- [ ] **Step 5: Lint and commit**

```bash
.venv/Scripts/ruff.exe check benchmarks/agent_compare/claims_run.py tests/test_claims_study.py
git add benchmarks/agent_compare/claims_run.py tests/test_claims_study.py
git commit -m "False-claims study: the runner, both arms' prompts verbatim from the spec, full clones and shared copies"
```

---

### Task 4: Mechanical citation check and neutralization (`claims_score.py`)

**Files:**
- Create: `benchmarks/agent_compare/claims_score.py`
- Modify: `tests/test_claims_study.py`

**Interfaces:**
- Produces: `Citation = dict` with `{"kind": "location" | "commit", "raw": str, "path": str | None, "line": int | None, "end": int | None, "hash": str | None}`; `citations(text: str) -> list[Citation]` (regex: `(?P<path>[\w./\\-]+\.\w{1,10}):(?P<line>\d+)(?:-(?P<end>\d+))?` for locations, path normalized: backslashes to `/`, a leading `./` dropped; `\b[0-9a-f]{7,40}\b` for hashes, a token that is all digits excluded); `TOOL_PATHS = (".verinoda/", "atlas.db", ".claude/", ".mcp.json")`; `check_citation(cit: Citation, claim: str, copy: Path) -> str` returning `confirmed | wrong | missing | not_repo`; `identifiers(claim: str) -> list[str]` (backticked spans first; else `[A-Za-z_][A-Za-z0-9_]{3,}` tokens that are not English stopwords of a small fixed list); `NEUTRAL = "[tool]"`; `neutralize(text: str) -> str` (case-insensitive replacement by `NEUTRAL`, one regex with the alternatives longest first so that `mcp__verinoda__analyze` is one token, not two: `mcp__verinoda__\w+`, `statically_verified`, `strong_inference`, `weak_inference`, `project_query`, `history_search`, `change_review`, `code_check`, `run_tool`, `verinoda`, `analyze`).
- Rules of `check_citation`: a path under `TOOL_PATHS` → `not_repo`; a location whose file is missing or whose line is past the end → `missing`; else `confirmed` when any identifier of the claim appears in lines `line-3 .. (end or line)+3`, else `wrong`. A hash: `git cat-file -t <hash>` not `commit` → `missing`; else `confirmed` when the claim's year (`20\d\d`) if any matches the commit's `%ad` year **and** any identifier of the claim appears in `git show --stat --format=%B <hash>`, else `wrong`.

- [ ] **Step 1: Write the failing tests**

```python
score_mod = _load("claims_score")

def test_citations_are_found_and_normalized():
    c = score_mod.citations("see .\\gin.go:236 and recovery.go:10-14, commit abc1234d; not 2026 and not 1234567890")
    locs = [x for x in c if x["kind"] == "location"]
    hashes = [x for x in c if x["kind"] == "commit"]
    assert [(x["path"], x["line"], x["end"]) for x in locs] == [("gin.go", 236, None), ("recovery.go", 10, 14)]
    assert [x["hash"] for x in hashes] == ["abc1234d"]

def _repo(tmp_path):
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "gin.go").write_text("package gin\n\nfunc Recovery() {}\n", encoding="utf-8")
    (tmp_path / ".verinoda").mkdir()
    (tmp_path / ".verinoda" / "x").write_text("Recovery", encoding="utf-8")
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "add", "gin.go"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "add Recovery middleware"], cwd=tmp_path, check=True)
    return subprocess.run(["git", "rev-parse", "--short=8", "HEAD"], cwd=tmp_path, capture_output=True, text=True).stdout.strip()

def test_check_citation_grades_location_and_commit(tmp_path):
    sha = _repo(tmp_path)
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
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_claims_study.py -q -k "citation or neutralize"`
Expected: FAIL, module missing.

- [ ] **Step 3: Implement the citation part of `claims_score.py`**

Docstring: what the script scores, the command line (`python benchmarks/agent_compare/claims_score.py WORK_DIR [--judge] [--summary OUT.json]`), the seed. `boot` imported from `swebench_score` with `seed=20261011` passed at the call sites.

- [ ] **Step 4: Run the tests to see them pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_claims_study.py -q`
Expected: 16 passed.

- [ ] **Step 5: Lint and commit**

```bash
.venv/Scripts/ruff.exe check benchmarks/agent_compare/claims_score.py tests/test_claims_study.py
git add benchmarks/agent_compare/claims_score.py tests/test_claims_study.py
git commit -m "False-claims study: the mechanical citation check and the neutralized answer text"
```

---

### Task 5: The blind judge (`claims_score.py`)

**Files:**
- Modify: `benchmarks/agent_compare/claims_score.py`
- Modify: `tests/test_claims_study.py`

**Interfaces:**
- Produces: `JUDGE_PROMPT: str` (verbatim constant; placeholders `{question}`, `{kind}`, `{gold}`, `{answer}`); `judge_input(task: dict, answer: str) -> str` (gold rendered as numbered statements with their commit/location; for a trap, `gold` is the line `The repository holds no answer to this question. Reason the task writer gives: <unknown_reason>`; the answer `neutralize`d); `parse_judge(text: str) -> dict | None` (the first `{...}` JSON object of the text with the keys below, else `None`); `judge(cfg: dict, task: dict, row: dict, scratch: Path) -> dict` (runs `claude -p <judge_input> --output-format json --model cfg["model"] --setting-sources project,local --strict-mcp-config --tools "" --max-turns 1` in `scratch` (`--tools ""` disables every built-in tool; `--allowedTools ""` would not), parses `result`, retries once on `None`, returns `{"id", "arm", "repeat", "judge": parsed | None, "judge_failed": bool, "raw": str}`).
- Judge output schema (in the prompt, verbatim): `{"claims": [{"text": str, "grade": "correct" | "incorrect" | "not_in_gold", "stance": "fact" | "inference", "cites": [str]}], "trap": null | {"verdict": "unknown_said" | "confabulated" | "answered_with_evidence"}, "arm_guess": "A" | "B"}`. The prompt tells the judge: it has no tools and answers from the text given alone, as JSON and nothing else; arm A is an agent with file reading and search only, arm B the same agent with an evidence tool; it must not use the answer's wording of tool names (they are masked) and must guess from the content alone; a `claim` is one factual statement; `incorrect` means contradicted by the gold, `not_in_gold` neither confirmed nor contradicted; a statement hedged with "likely", "appears", "probably", "I infer" is `inference`; for a trap, `answered_with_evidence` when the answer asserts a specific answer with a citation, `confabulated` when it asserts one without, `unknown_said` when it says the repository does not hold it.

- [ ] **Step 1: Write the failing tests**

```python
def test_judge_input_masks_the_answer_and_renders_the_gold():
    t = _task()
    s = score_mod.judge_input(t, "Verinoda analyze found it at gin.go:236")
    assert "erinoda" not in s and "gin.go:236" in s and t["gold"][0]["statement"] in s and "abc1234" in s
    trap = score_mod.judge_input(_task("trap"), "x")
    assert "holds no answer" in trap and _task("trap")["unknown_reason"] in trap

def test_parse_judge_takes_the_first_object_and_refuses_the_wrong_shape():
    good = 'Here: {"claims": [{"text": "t", "grade": "correct", "stance": "fact", "cites": []}], "trap": null, "arm_guess": "A"} done'
    assert score_mod.parse_judge(good)["claims"][0]["grade"] == "correct"
    assert score_mod.parse_judge('{"claims": "no"}') is None
    assert score_mod.parse_judge('{"claims": [{"text": "t", "grade": "maybe", "stance": "fact", "cites": []}], "trap": null, "arm_guess": "A"}') is None
    assert score_mod.parse_judge("no json") is None

def test_judge_retries_once_then_records_failure(monkeypatch, tmp_path):
    calls = []
    def fake_run(argv, cwd, env=None, timeout=600, stdin=None):
        calls.append(argv)
        return 0, json.dumps({"result": "not json"}), "", 1.0
    monkeypatch.setattr(score_mod, "run", fake_run)
    out = score_mod.judge({"model": "claude-sonnet-5-5", "claude": "claude"}, _task(), {"id": "x", "arm": "none", "repeat": 1, "answer": "a"}, tmp_path)
    assert len(calls) == 2 and out["judge_failed"] is True and out["judge"] is None
    assert calls[0][calls[0].index("--tools") + 1] == "" and calls[0][calls[0].index("--max-turns") + 1] == "1"
    assert "--allowedTools" not in calls[0]
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_claims_study.py -q -k judge`
Expected: FAIL, attributes missing.

- [ ] **Step 3: Implement the judge**

`run` imported from `guard_run` at module level (so the test can patch it). `parse_judge` validates: `claims` a list of objects with the four keys and the allowed values; `trap` null or an object with an allowed `verdict`; `arm_guess` in `{"A", "B"}`.

- [ ] **Step 4: Run the tests to see them pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_claims_study.py -q`
Expected: 19 passed.

- [ ] **Step 5: Lint and commit**

```bash
.venv/Scripts/ruff.exe check benchmarks/agent_compare/claims_score.py tests/test_claims_study.py
git add benchmarks/agent_compare/claims_score.py tests/test_claims_study.py
git commit -m "False-claims study: the blind judge, its prompt verbatim, its parse and retry"
```

---

### Task 6: Summary, decision rule, blinding check and hand-check sample (`claims_score.py`)

**Files:**
- Modify: `benchmarks/agent_compare/claims_score.py`
- Modify: `tests/test_claims_study.py`

**Interfaces:**
- Consumes: `swebench_score.boot(diffs, n=10000, seed=...)`.
- Produces: `PLAIN, GUIDED = "none", "verinoda_guided"`; `ARM_LETTER = {"none": "A", "verinoda_guided": "B"}`; `mechanical(row: dict, copy: Path) -> dict` (`{"id", "arm", "repeat", "citations": [{**cit, "verdict": str}]}` over `citations(row["answer"])`); `answer_values(judged: dict, mech: dict, kind: str) -> dict | None` (None when `judged["judge_failed"]`; `summary` never calls it for a session row with `is_error` or an empty `answer`, which it filters out first and lists under `errored_sessions`; else `{"false_fact": 0|1, "false_inference": 0|1, "fact_claims": n, "incorrect_facts": n, "correct_uncited": n, "correct_claims": n, "inference_claims": n, "confabulated": 0|1|None, "reclassified": bool}`; `reclassified` is true for a trap whose judge verdict is `answered_with_evidence` and whose `mech` holds a `confirmed` citation; then `confabulated` is `None`); `task_values(values: list[dict]) -> dict` (means over the repeats of each 0/1 field, sums of the counts); `summary(tasks, rows, judged, mechs) -> dict` with: `sessions`, `errored_sessions: [ids]`, `judge_failed: [ids]`, `pairs` (tasks with ≥1 valid repeat in both arms), `dropped_tasks: [ids]`, `writer_errors: [trap ids reclassified in any repeat]`, `primary: {"answerable_false_fact": {"none": mean, "verinoda_guided": mean, "difference": m, "ci95": [lo, hi], "claim": bool, "n_tasks"}, "trap_confabulated": {...}}`, `secondary: {"incorrect_fact_rate", "correct_uncited_share", "inference_share"}` per arm with the paired difference, `by_kind: {kind: {primary fields}}`, `blinding: {"accuracy", "ci95", "failed": bool, "n"}` (bootstrap over judged answers of `arm_guess == ARM_LETTER[arm]`), `cost: {per arm medians of turns, cost_usd, seconds, input/output tokens; verinoda_calls; usage_log_lines; "per_call": the guided arm's usage logs read as `verinoda usage` does (every JSON line of `WORK/usage/*.jsonl`): calls, `result_chars` and `result_tokens_est` summed per tool name, with the note that tokens are characters / 4}`; `hand_sample(judged: list[dict], n: int = 40, seed: int = 20261011) -> list[dict]` (20 claims per arm, each `{"sample_id", "id", "repeat", "claim_text", "grade", "stance"}` with **no** `arm` field; the arm mapping written to a separate `hand_check_key.json` by `main`).
- `main()`: reads `WORK/results.jsonl` and `WORK/tasks.json`; writes `WORK/mechanical.jsonl`; with `--judge` runs the judge for every row not yet in `WORK/judge.jsonl` (resumable); writes `WORK/summary.json`, `WORK/hand_check.json`, `WORK/hand_check_key.json`.

- [ ] **Step 1: Write the failing tests**

```python
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

def test_summary_pairs_drops_lists_and_decides(tmp_path):
    tasks = _full_set()
    ids = [t["id"] for t in tasks]
    kinds = {t["id"]: t["kind"] for t in tasks}
    rows, judged, mechs = [], [], []
    for i in ids:
        for arm in ("none", "verinoda_guided"):
            for rep in (1, 2, 3):
                err = (i == ids[0] and arm == "none")          # every plain repeat of task 0 errored
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

def test_hand_sample_is_blind_and_balanced():
    judged = [_judged(f"t{i}", arm, 1, [C_OK, C_BAD]) for i in range(30) for arm in ("none", "verinoda_guided")]
    sample = score_mod.hand_sample(judged)
    assert len(sample) == 40 and all("arm" not in s for s in sample)
    key = score_mod.hand_key(judged, sample)
    assert sorted(key.values()).count("none") == 20
```

`hand_key(judged, sample) -> dict[sample_id, arm]` is the key `main` writes apart.

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_claims_study.py -q -k "values or trap_answered or summary or hand_sample"`
Expected: FAIL, attributes missing.

- [ ] **Step 3: Implement the summary part**

A paired difference is `boot([guided_task_value - plain_task_value for each pair], seed=20261011)`; `claim` is `lo > 0 or hi < 0`. `by_kind` pairs only the tasks of that kind. Blinding accuracy is bootstrapped over judged answers with a valid judge.

- [ ] **Step 4: Run the tests to see them pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_claims_study.py -q`
Expected: 23 passed.

- [ ] **Step 5: Lint and commit**

```bash
.venv/Scripts/ruff.exe check benchmarks/agent_compare/claims_score.py tests/test_claims_study.py
git add benchmarks/agent_compare/claims_score.py tests/test_claims_study.py
git commit -m "False-claims study: the summary, the decision rule, the blinding check and the blind hand-check sample"
```

---

### Task 7: Write the 40 tasks and commit them before any session

**Files:**
- Create: `benchmarks/agent_compare/claims_tasks.json`
- Create: `benchmarks/agent_compare/claims_tasks_check.json` (the checker's output, one row per task, the rewrites listed)

**Interfaces:**
- Consumes: `claims_run.clone_full`, `claims_tasks.writer_prompt`, `checker_prompt`, `leak_check`, `rederive`, `validate`, `load_tasks`.

This task runs agents; its steps are checkable by their outputs. The work folder is `C:/vbench-claims` (outside OneDrive, as `benchmarks/realworld/README.md` asks).

- [ ] **Step 1: Make the ten full clones**

Run (from the repository root, in Python): for each `repo, sha` of the manifest, `claims_run.clone_full(repo, sha, Path("C:/vbench-claims/clones") / repo.replace("/", "__"))`.
Expected: ten folders, each `git rev-parse HEAD` equal to the manifest's sha, no `.git/shallow`, `git rev-list --count HEAD` in the thousands.

- [ ] **Step 2: Write 4 tasks per repository with a fresh agent each**

For each repository, one `Agent` (general-purpose) with the prompt `claims_tasks.writer_prompt(repo, clone, kinds)`, the per-repository `kinds` fixed now so that the totals are 8/8/14/10 and every repository has 4: repositories 1-8 of the manifest's order get `{"why": 1, "when": 1, "affects": 1, "trap": 1}`, repositories 9-10 (`google/gson`, `guzzle/guzzle`) get `{"affects": 3, "trap": 1}`. Totals: why 8, when 8, affects 8 + 6 = 14, trap 10. The agent runs with its clone as the working directory, is told it may read only the clone and the manifest line of its repository, and never Verinoda, `atlas.db`, `benchmarks/realworld/gold/` or `benchmarks/results/`. It returns JSON only.
Expected: 40 task objects; `claims_tasks.validate(all)` returns `[]` (fix only what validation names, by sending the problems back to the same agent); **no `.verinoda/` folder exists in any clone afterwards** (`ls C:/vbench-claims/clones/*/.verinoda` finds nothing: the mechanical sign that no writer ran Verinoda).

- [ ] **Step 3: Check every task with a second, fresh agent per repository**

One `Agent` per repository with `claims_tasks.checker_prompt(repo, clone, tasks_of_repo)`; before it, run `leak_check` and `rederive` on each task and hand their output to the checker inside the prompt. A task with `ok: false` goes back to a **new** writer agent with the problems, once; a task still flagged is replaced by a new one of the same kind and checked again. Keep every checker row in `claims_tasks_check.json` with `round: 1|2` and the id it replaced if any.
Expected: 40 rows with `ok: true` in the final round; no task of the final set has a `leak_check` hit; every gold item is in some `rederive` row's `reproduces`.

- [ ] **Step 4: Validate and record the order**

Run: `.venv/Scripts/python.exe -c "import sys; sys.path.insert(0, 'benchmarks/agent_compare'); from pathlib import Path; import claims_tasks as c; t = c.load_tasks(Path('benchmarks/agent_compare/claims_tasks.json')); print(c.order([x['id'] for x in t])[:8])"`; then put those eight ids under a `"pilot_ids"` key of the JSON next to `"tasks"` (`load_tasks` ignores keys other than `tasks`).
Expected: no `ValueError`; eight ids printed.

- [ ] **Step 5: Commit the tasks before any session**

```bash
git add benchmarks/agent_compare/claims_tasks.json benchmarks/agent_compare/claims_tasks_check.json
git commit -m "False-claims study: the 40 tasks and their gold, written from git without Verinoda, checked, committed before the first session"
```

---

### Task 8: Pilot (8 tasks × 2 arms × 1 repeat), scoring, and the N decision

**Files:**
- Create: `benchmarks/results/claims-pilot-2026-10-<dd>/` (`config.json`, `tasks.json`, `results.jsonl`, `mechanical.jsonl`, `judge.jsonl`, `summary.json`, `hand_check.json`, `hand_check_key.json`, `README.md`)
- Modify: `benchmarks/agent_compare/DESIGN_CLAIMS.md` (append the dated amendment that fixes N)

**Interfaces:**
- Consumes: `claims_run.main` with `--pilot`; `claims_score.main` with `--judge`.

- [ ] **Step 1: Write the config**

`C:/vbench-claims/config.json`: `{"work": "C:/vbench-claims", "model": "claude-sonnet-5-5", "plugin_dir": "<repo>/claude-mods/verinoda-live", "mod_options": {"auto": "nudge"}, "verinoda_bin": ["<repo>/.venv/Scripts"], "drop_path": [<the folders of the user's own verinoda on PATH, from `where verinoda`>], "arms": ["none", "verinoda_guided"], "arm_workers": {"none": 2, "verinoda_guided": 2}, "timeout_s": 1200, "max_turns": 40, "repeats": 3}`.
Expected: the file parses; `drop_path` names every folder `where verinoda` prints.

- [ ] **Step 2: Run the pilot**

Run: `.venv/Scripts/python.exe benchmarks/agent_compare/claims_run.py C:/vbench-claims/config.json --pilot`
Expected: 16 rows in `results.jsonl`, `pilot: true`, no `is_error`; every guided row has `verinoda_tools.calls` non-empty; `network` empty in every row. A row with a network mark or an error is kept and listed in the README.

- [ ] **Step 3: Score the pilot**

Run: `.venv/Scripts/python.exe benchmarks/agent_compare/claims_score.py C:/vbench-claims --judge`
Expected: `mechanical.jsonl` 16 rows; `judge.jsonl` 16 rows with `judge_failed: false`; `summary.json` with `primary`, `blinding`, `by_kind`; `hand_check.json` with 40 rows (or every claim, if fewer).

- [ ] **Step 4: Hand check**

The person grades `hand_check.json` (grade and stance per claim) without `hand_check_key.json`; the disagreement rate with the judge is computed and written in the README. Above 20 %: revise `JUDGE_PROMPT` (the change written in the README and in a dated amendment of the spec), re-run `--judge` on every row, re-draw the sample, grade again.
Expected: a disagreement rate in the README.

- [ ] **Step 5: Copy the results and write the README**

Copy `config.json`, `tasks.json`, `results.jsonl`, `mechanical.jsonl`, `judge.jsonl`, `summary.json`, `hand_check*.json` into `benchmarks/results/claims-pilot-2026-10-<dd>/`. The README, in the shape of `benchmarks/results/swebench-lite-100-2026-10-10/README.md`: what ran (model, Claude Code version from the rows, the 8 ids), the `none` arm's share of answers with a false fact claim on the answerable pilot tasks, the trap verdicts, blinding accuracy, the hand-check rate, cost per arm, the usage log's per-call totals, and every session with an error, a network mark or a failed judge. Measured and not measured apart.

- [ ] **Step 6: Fix N in a dated amendment of the spec**

Append to `DESIGN_CLAIMS.md`: `## Amendment 2026-10-<dd>: N after the pilot`, stating the `none` arm's false-fact share on the answerable pilot tasks and the rule chosen by the spec's threshold (below 10 %: either 60 answerable tasks or traps as the primary with 20 traps; at or above: the 40 as written). If tasks are added, Task 7's steps run again for the new ones only, and they are committed before the main run.

- [ ] **Step 7: Commit**

```bash
git add benchmarks/results/claims-pilot-2026-10-<dd> benchmarks/agent_compare/DESIGN_CLAIMS.md
git commit -m "False-claims study: the 8-task pilot, its scores and hand check, and the amendment that fixes N"
```

---

### Task 9: Main run, scoring, results and the design note

**Files:**
- Create: `benchmarks/results/claims-2026-10-<dd>/` (the same files as the pilot's folder, over every session)
- Modify: `docs/DESIGN.md` (a new section under the next `D` number), `docs/UPGRADING.md`, `docs/OZELLIKLER-RAPORU.md`, `docs/BENCHMARKS.md`, `docs/BENCHMARK-BULGULARI.md`

- [ ] **Step 1: Run every remaining session**

Run: `.venv/Scripts/python.exe benchmarks/agent_compare/claims_run.py C:/vbench-claims/config.json`
Expected: `results.jsonl` holds 40 (or the amended N) × 2 × 3 rows (the 16 pilot rows among them, each counted as repeat 1); the console's `FAILED` lines, if any, are rerun by running the same command again (resumable).

- [ ] **Step 2: Score**

Run: `.venv/Scripts/python.exe benchmarks/agent_compare/claims_score.py C:/vbench-claims --judge`
Expected: `judge.jsonl` one row per session; `summary.json` with every key of Task 6; `hand_check.json` with 40 claims drawn anew (seed fixed, so the pilot's claims may recur; that is fine and said in the README).

- [ ] **Step 3: Hand check, as in the pilot**

Expected: the disagreement rate in the README; the stop rule applied if above 20 %.

- [ ] **Step 4: Results folder and README**

Every table the spec names: primary measures with intervals and the decision, per kind, secondary rates, blinding, hand check, cost per arm and per Verinoda call, `writer_errors`, `errored_sessions`, `judge_failed`, `dropped_tasks`, network marks. The expectation for `why` + `when` stated beside their result. Measured and not measured apart; a difference inside the interval is "no measured difference", never "no difference".

- [ ] **Step 5: Design note and documents**

`docs/DESIGN.md`: `## <next number>. The false-claims study: what Verinoda is for, measured (D<next>, 2026-10-<dd>)` with why, decisions (the two arms' shared stance, the judge, the traps), measured (the primary numbers with intervals, per kind, blinding, hand check, cost), not done, tests (`tests/test_claims_study.py`). `docs/UPGRADING.md`: a `### D<next>` note. `docs/OZELLIKLER-RAPORU.md`: three lines in Turkish. `docs/BENCHMARKS.md`: an entry in the shape of its neighbours. `docs/BENCHMARK-BULGULARI.md`: a new first section with the result and the per-kind table, and §5's order revised in light of it (the spec said either result is progress; the document says which).

- [ ] **Step 6: Lint the changed Python (none expected), run the study's tests, commit**

```bash
.venv/Scripts/python.exe -m pytest tests/test_claims_study.py tests/test_agent_compare.py -q
git add benchmarks/results/claims-2026-10-<dd> docs/DESIGN.md docs/UPGRADING.md docs/OZELLIKLER-RAPORU.md docs/BENCHMARKS.md docs/BENCHMARK-BULGULARI.md
git commit -m "False-claims study, 40 tasks x 2 arms x 3 repeats: the result (D<next>)"
```
