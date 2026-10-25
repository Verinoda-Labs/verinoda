"""The closed-book probe (DESIGN_SWEBENCH_CEILING.md, amendment 7): a model is given only an instance's repository, base
commit and issue, with no tool, no file and no server, and asked for the patch. What it writes of the upstream fix beyond
what the issue gives (`swebench_recall.py`) can only come from what it remembers. A labelled diagnostic outside the
benchmark's rules: never graded, never a resolved share.

    python benchmarks/agent_compare/swebench_closedbook.py MODEL TASKS.json OUT_DIR [--only ID,...]

One call at a time, at below-normal priority, from an empty folder made for the probe (`OUT_DIR/empty`): `claude -p` with
no tool (`--tools ""`), no MCP server (`--strict-mcp-config`), no plugin, settings from that folder only, one turn and a
short system prompt in place of Claude Code's. Writes OUT_DIR/results.jsonl (one row per instance: the reply, the diff
taken from it, cost, seconds, session id) and skips the instances it already holds.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from swebench_run import claude_exe

SYSTEM = "You are an expert software engineer. You answer with a patch only."
PROMPT = """Repository: {repo} (at commit {base_commit}, version {version}).

Issue:
{problem_statement}

You have no access to the repository's files and no tools. Write the patch that fixes this issue as a unified diff in git's
format (paths relative to the repository's root, with a/ and b/ prefixes). Reply with the diff only, in one ```diff block."""
TIMEOUT = 600
DIFF = re.compile(r"```(?:diff|patch)?\s*\n(.*?)```", re.DOTALL)


def patch_of(reply: str) -> str:
    blocks = DIFF.findall(reply)
    text = max(blocks, key=len) if blocks else reply
    return text if text.endswith("\n") else text + "\n"


def main() -> int:
    model, tasks, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    only = set(sys.argv[sys.argv.index("--only") + 1].split(",")) if "--only" in sys.argv else None
    empty = out / "empty"
    empty.mkdir(parents=True, exist_ok=True)
    if any(empty.iterdir()):
        sys.exit(f"{empty} is not empty")
    results = out / "results.jsonl"
    done = {json.loads(x)["id"] for x in results.read_text(encoding="utf-8").splitlines() if x.strip()} \
        if results.exists() else set()
    for t in json.loads(tasks.read_text(encoding="utf-8"))["tasks"]:
        if t["id"] in done or (only is not None and t["id"] not in only):
            continue
        prompt = PROMPT.format(repo=t["repo"], base_commit=t["base_commit"], version=t["version"],
                               problem_statement=t["problem_statement"])
        argv = [claude_exe({}), "-p", prompt, "--output-format", "json", "--model", model, "--tools", "",
                "--strict-mcp-config", "--setting-sources", "project,local", "--max-turns", "1",
                "--system-prompt", SYSTEM, "--disable-slash-commands"]
        start = time.time()
        try:
            p = subprocess.run(argv, cwd=empty, capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=TIMEOUT, check=False, creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS)
            rc, raw = p.returncode, p.stdout
        except subprocess.TimeoutExpired:
            rc, raw = None, ""
        try:
            j = json.loads(raw)
        except ValueError:
            j = {}
        reply = j.get("result") or ""
        row = {"id": t["id"], "model": model, "exit": rc, "reply": reply, "patch": patch_of(reply) if reply else "",
               "cost_usd": j.get("total_cost_usd"), "seconds": round(time.time() - start, 1),
               "session_id": j.get("session_id"), "is_error": j.get("is_error")}
        with results.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(row) + "\n")
        print(f"{t['id']}: exit {rc}, {len(row['patch'].splitlines())} diff lines, ${row['cost_usd']}, {row['seconds']} s",
              flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
