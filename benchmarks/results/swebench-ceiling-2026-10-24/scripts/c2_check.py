"""Amendment 5's C2 question: did a Verinoda defect change an outcome? For a run, every instance the plain arm resolved and
the guided arm did not (final grades: amendment 2's regrade, amendment 6's re-runs), with the guided session's Verinoda
calls (tool, question or paths, status, budget spent, the first answer) and the failing tests of its evaluation log. Also
the run's whole guided arm: how many sessions called each Verinoda tool and how analyze's calls ended.

    python c2_check.py RUN
"""

import collections
import json
import re
import sys
from pathlib import Path

TMP = Path(__file__).resolve().parent
sys.path.insert(0, str(TMP))
from final_grades import final, rows

DATA = Path("C:/Users/ozcin/swebench-data")
PROJECTS = Path.home() / ".claude" / "projects"
FAIL = re.compile(r"^(FAIL|ERROR):|^E   |Error: |\[FAIL\]|^FAILED ", re.MULTILINE)


def calls(session_id: str) -> list[dict]:
    """The session's Verinoda tool calls in order, each with its result's text."""
    found = list(PROJECTS.glob(f"*/{session_id}.jsonl")) if session_id else []
    if not found:
        return []
    out, by_id = [], {}
    for line in found[0].read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            m = json.loads(line).get("message") or {}
        except ValueError:
            continue
        for x in m.get("content") if isinstance(m.get("content"), list) else []:
            if x.get("type") == "tool_use" and "verinoda" in (x.get("name") or ""):
                by_id[x["id"]] = {"tool": x["name"].rsplit("__", 1)[-1], "input": x.get("input") or {}, "result": ""}
                out.append(by_id[x["id"]])
            elif x.get("type") == "tool_result" and x.get("tool_use_id") in by_id:
                c = x.get("content")
                by_id[x["tool_use_id"]]["result"] = c if isinstance(c, str) else " ".join(
                    y.get("text", "") for y in c or [] if isinstance(y, dict))
    return out


def outcome(call: dict) -> str:
    try:
        r = json.loads(call["result"])
    except ValueError:
        return "not json: " + call["result"][:80].replace("\n", " ")
    if call["tool"] != "analyze":
        return str(r.get("status"))
    subs = ", ".join(f"{s.get('intent')}:{s.get('status')}" for s in r.get("subquestions") or [])
    spent = " (budget spent)" if r.get("budget_exhausted") else ""
    return f"{r.get('status')}{spent} [{subs}]"


def main() -> None:
    run = sys.argv[1]
    plain, guided = final(run, "none"), final(run, "verinoda_guided")
    sessions = {r["id"]: r for (i, a), r in rows(f"{run}").items() if a == "verinoda_guided"}
    for k in ("-r1", "-r2"):
        sessions.update({r["id"]: r for (i, a), r in rows(f"{run}{k}").items() if a == "verinoda_guided"})
    lost = sorted(i for i in plain if plain[i]["resolved"] and i in guided and guided[i]["resolved"] is False)
    print(f"{run}: resolved by the plain arm and not by the guided arm: {len(lost)}")
    for iid in lost:
        r = sessions.get(iid) or {}
        print(f"\n== {iid} (guided session {guided[iid]['run']} {r.get('session_id')}, turns {r.get('num_turns')})")
        for c in calls(r.get("session_id") or ""):
            what = c["input"].get("question") or c["input"].get("paths") or c["input"]
            print(f"  {c['tool']}: {str(what)[:160]}\n    -> {outcome(c)}")
        log = DATA / "logs" / f"{guided[iid]['run']}-verinoda_guided" / f"{iid}.log"
        text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
        print("  failing:", " | ".join(m.group(0) + text[m.end():m.end() + 90].split("\n")[0]
                                      for m in list(FAIL.finditer(text))[:4]) or "(no log)")
    tools, ends = collections.Counter(), collections.Counter()
    for r in sessions.values():
        cs = calls(r.get("session_id") or "")
        for t in {c["tool"] for c in cs}:
            tools[t] += 1
        for c in cs:
            if c["tool"] == "analyze":
                ends[outcome(c).split(" [")[0]] += 1
    print(f"\n{run} guided sessions: {len(sessions)}; sessions calling each tool: {dict(tools)}; analyze calls ended: "
          f"{dict(ends)}")


if __name__ == "__main__":
    main()
