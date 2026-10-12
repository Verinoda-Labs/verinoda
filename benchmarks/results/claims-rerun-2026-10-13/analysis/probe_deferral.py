"""Diagnosis probe, not part of the measured study: one Verinoda-arm session built exactly as the harness builds it, on a
throwaway copy, with the CLI's debug log on, to see where the server's core tools sit at the first model request (in the
prompt's list, or behind ToolSearch) and what the mod's hooks did.

    python probe_deferral.py NAME [--max-turns N] [--prompt-file FILE]

NAME is a folder under C:/vbench-claims-rerun/probe/. Writes NAME/debug.log, NAME/result.json and prints the transcript's
deferred-tools list and the first tool calls.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\ozcin\Desktop\verinoda-symbiosis")
sys.path.insert(0, str(REPO / "benchmarks" / "agent_compare"))

import claims_run as cr  # noqa: E402
from claims_tasks import REPO_ROOT, load_tasks  # noqa: E402
from guard_run import find_transcript  # noqa: E402


def main() -> int:
    name = sys.argv[1]
    max_turns = int(sys.argv[sys.argv.index("--max-turns") + 1]) if "--max-turns" in sys.argv else 1
    cfg = json.loads(Path("C:/vbench-claims-rerun/config.json").read_text(encoding="utf-8"))
    work = Path("C:/vbench-claims-rerun/probe") / name
    work.mkdir(parents=True, exist_ok=True)
    tasks = {t["id"]: t for t in load_tasks(REPO_ROOT / "benchmarks" / "agent_compare" / "claims_tasks.json")}
    task = tasks["fastapi__full-stack-fastapi-template-why-1"]
    clone = Path(cfg["work"]) / "clones" / task["repo"].replace("/", "__")
    copy = work / "copy"
    cr.copy_for(clone, copy, task["sha"])
    cr.setup_verinoda(copy)
    prompt = cr.prompt_for(task, copy, cr.GUIDED, cfg)
    if "--prompt-file" in sys.argv:
        prompt = Path(sys.argv[sys.argv.index("--prompt-file") + 1]).read_text(encoding="utf-8").replace("{copy}", copy.as_posix())
    argv = cr.session_argv(prompt, cr.GUIDED, copy, cfg)
    argv[argv.index("--max-turns") + 1] = str(max_turns)
    argv += ["--debug-file", str(work / "debug.log")]
    env = cr.env_for(cr.GUIDED, cfg)
    rc, out, err, secs = cr.run(argv, copy, env, timeout=600)
    (work / "result.json").write_text(out or err, encoding="utf-8")
    try:
        rep = json.loads(out)
    except ValueError:
        print("not json:", (out or err)[-500:])
        return 1
    print("rc", rc, "secs", secs, "turns", rep.get("num_turns"), "cost", rep.get("total_cost_usd"), "subtype", rep.get("subtype"))
    tr = find_transcript(rep.get("session_id", ""))
    print("transcript", tr)
    if tr is None:
        return 1
    for line in tr.read_text(encoding="utf-8").splitlines():
        e = json.loads(line)
        att = e.get("attachment") or {}
        if att.get("type") == "deferred_tools_delta":
            print("DEFERRED:", [n for n in att.get("addedNames", []) if "verinoda" in n], "of", len(att.get("addedNames", [])))
        m = e.get("message") or {}
        if m.get("role") == "assistant" and isinstance(m.get("content"), list):
            for x in m["content"]:
                if x.get("type") == "tool_use":
                    print("TOOL_USE:", x["name"], json.dumps(x["input"])[:200])
    return 0


if __name__ == "__main__":
    sys.exit(main())
