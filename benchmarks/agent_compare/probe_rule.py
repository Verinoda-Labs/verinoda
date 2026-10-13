"""A call-rate probe, not a measurement: one Verinoda-arm session built with the claims harness's own functions, with a
plugin folder of your choice (a copy of the mod carrying a rule variant) and, when given, the package of a worktree
under test for the MCP server. D186 used it to try five rule variants on six tasks, one session each
(``benchmarks/results/claims-rerun-2026-10-13/probes/``): it shows a direction; the paired cost sample measures.

    python probe_rule.py CONFIG NAME PLUGIN_DIR TASK_ID [--max-turns N] [--pythonpath DIR]

``CONFIG`` is the harness config (``claims_run.py``'s). The session runs on a copy of the task's repository under
``<work>/probe/copies/<hash>/verinoda_guided/r1/`` (the harness's opaque name: the task id carries the task's kind, and
D185's review found every trap session reading "trap-1" on its prompt's first line), made once per task and reused by
later variants with its index; it writes ``<work>/probe/NAME/result.json`` (the CLI's result) and ``summary.json`` (the
tool calls in order, the number of ``mcp__verinoda__analyze`` calls, turns, cost, session id, the transcript read).
``--max-turns`` defaults to 12 (the harness: the config's ``max_turns``); the session time-out is 900 s. ``--pythonpath``
is put in the session's environment so the MCP server child imports that tree's ``verinoda`` first; give both folders
as absolute paths.

What differs from a harness session (``claims_run.one``): no ``isolated_plugin_store`` wrap, no ``VERINODA_USAGE_LOG``,
one copy per task shared by every variant (each session writes to its ``.verinoda/atlas.db``, and ``verinoda setup``
runs again on it), and a session whose transcript is not found reports its counts as null, not 0.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import claims_run as cr
from claims_tasks import REPO_ROOT, load_tasks
from guard_run import find_transcript


def _flag(name: str, default: str | None) -> str | None:
    if name not in sys.argv:
        return default
    at = sys.argv.index(name) + 1
    if at >= len(sys.argv):
        raise SystemExit(f"{name} needs a value")
    return sys.argv[at]


def main() -> int:
    if len(sys.argv) < 5:
        print(__doc__)
        return 2
    config, name, plugin_dir, task_id = sys.argv[1:5]
    max_turns = int(_flag("--max-turns", "12") or "12")   # parsed before any copy or index step
    pythonpath = _flag("--pythonpath", None)
    cfg = json.loads(Path(config).read_text(encoding="utf-8"))
    cfg["plugin_dir"] = str(Path(plugin_dir).resolve())
    work = Path(cfg["work"]) / "probe" / name
    work.mkdir(parents=True, exist_ok=True)
    tasks = {t["id"]: t for t in load_tasks(REPO_ROOT / "benchmarks" / "agent_compare" / "claims_tasks.json")}
    task = tasks[task_id]
    clone = Path(cfg["work"]) / "clones" / task["repo"].replace("/", "__")
    copy = cr.copy_dir(Path(cfg["work"]) / "probe", task, cr.GUIDED, 1)
    cr.copy_for(clone, copy, task["sha"])
    cr.setup_verinoda(copy)
    prompt = cr.prompt_for(task, copy, cr.GUIDED, cfg)
    argv = cr.session_argv(prompt, cr.GUIDED, copy, cfg)
    argv[argv.index("--max-turns") + 1] = str(max_turns)
    env = cr.env_for(cr.GUIDED, cfg)
    if pythonpath is not None:
        env = {**env, "PYTHONPATH": str(Path(pythonpath).resolve())}
    rc, out, err, secs = cr.run(argv, copy, env, timeout=900)
    (work / "result.json").write_text(out or err, encoding="utf-8")
    try:
        rep = json.loads(out)
    except ValueError:
        print(name, "not json:", (out or err)[-500:])
        return 1
    tr = find_transcript(rep.get("session_id", ""))
    calls: list[str] | None = None
    if tr is not None:
        calls = []
        for line in tr.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            m = e.get("message") or {}
            if m.get("role") == "assistant" and isinstance(m.get("content"), list):
                calls += [x["name"] for x in m["content"] if x.get("type") == "tool_use"]
    else:
        print(name, "warning: no transcript found for the session; the call counts are unknown, not 0", file=sys.stderr)
    summary = {"name": name, "task": task_id, "plugin_dir": cfg["plugin_dir"], "rc": rc, "secs": round(secs, 1),
               "turns": rep.get("num_turns"), "cost": rep.get("total_cost_usd"),
               "analyze_calls": None if calls is None else sum(1 for c in calls if c == "mcp__verinoda__analyze"),
               "verinoda_calls": None if calls is None else sum(1 for c in calls if c.startswith("mcp__verinoda__")),
               "tools": calls, "transcript": None if tr is None else str(tr),
               "session_id": rep.get("session_id"), "answer_head": (rep.get("result") or "")[:300]}
    (work / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
