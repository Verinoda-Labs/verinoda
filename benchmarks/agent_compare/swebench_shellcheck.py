"""Flag the sessions of a SWE-bench run whose Bash tool lost its PATH (DESIGN_SWEBENCH_CEILING.md, amendment 6).

    python benchmarks/agent_compare/swebench_shellcheck.py RESULTS.jsonl [--json]

Claude Code on Windows gives a session's shell the PATH a login shell prints (``bash -lc 'echo "$PATH"'``, a 10-second
limit); when that times out, the session's shell snapshot exports the process's PATH in its Windows form, which bash
cannot search, and every command outside bash itself fails for the whole session. A session is flagged when a Bash tool
result in its transcript (``~/.claude/projects/*/<session_id>.jsonl``) says that one of the commands below is not found:
each is on the PATH of every session of this study when the PATH is right (Git's own tools, git, the environment's
python). The pattern is fixed by the amendment; a flagged session is flagged whether or not it resolved and whether or not
it recovered (PowerShell, a PATH set by hand).

Prints one line per flagged session (instance, arm, the tool call's number, broken and working Bash calls); ``--json``
prints the flagged lanes as a JSON list of [instance, arm] instead.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

NOT_FOUND = re.compile(r"bash: (?:line \d+: )?(ls|mkdir|head|tail|grep|cat|sed|find|wc|sort|awk|cp|mv|rm|touch|diff|tr|"
                       r"cut|xargs|env|which|dirname|basename|uname|date|git|python): command not found")


def transcript(session_id: str) -> Path | None:
    return next(iter((Path.home() / ".claude" / "projects").glob(f"*/{session_id}.jsonl")), None) if session_id else None


def check(session_id: str) -> dict | None:
    """The session's broken Bash calls, or None when it has none (or no transcript)."""
    path = transcript(session_id)
    if path is None:
        return None
    names: dict[str, tuple[int, str]] = {}
    first, broken, working, n = None, 0, 0, 0
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        content = (event.get("message") or {}).get("content")
        for c in content if isinstance(content, list) else []:
            if c.get("type") == "tool_use":
                n += 1
                names[c.get("id")] = (n, c.get("name"))
            elif c.get("type") == "tool_result" and names.get(c.get("tool_use_id"), (0, ""))[1] == "Bash":
                text = c.get("content")
                text = text if isinstance(text, str) else json.dumps(text)
                if NOT_FOUND.search(text):
                    broken += 1
                    first = first or names[c["tool_use_id"]][0]
                else:
                    working += 1
    return {"first_broken_call": first, "broken": broken, "working": working, "calls": n} if broken else None


def flagged(results: Path) -> dict[tuple[str, str], dict]:
    rows = [json.loads(x) for x in results.read_text(encoding="utf-8").splitlines() if x.strip()]
    out = {}
    for r in rows:
        got = check(r.get("session_id") or "")
        if got:
            out[(r["id"], r["arm"])] = got
    return out


def main() -> int:
    results = Path(sys.argv[1])
    found = flagged(results)
    if "--json" in sys.argv:
        print(json.dumps(sorted(found)))
        return 0
    rows = [json.loads(x) for x in results.read_text(encoding="utf-8").splitlines() if x.strip()]
    for arm in sorted({r["arm"] for r in rows}):
        lanes = sorted(k for k in found if k[1] == arm)
        print(f"{arm}: {len(lanes)} of {sum(r['arm'] == arm for r in rows)} sessions flagged")
        for lane in lanes:
            print(f"  {lane[0]:38} {found[lane]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
