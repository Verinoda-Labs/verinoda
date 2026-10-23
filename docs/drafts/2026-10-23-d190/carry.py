"""Where a subagent's context went: each tool result's size times the model calls that carried it afterwards (chars/4,
an estimate), summed per tool, per file read and per kind of shell command; and the lines of its prompt naming Verinoda.

    python carry.py <subagent.jsonl>
"""
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def ts(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


calls, seen, uses, results, boundaries = [], set(), {}, [], []
prompt = None
for line in Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace").splitlines():
    try:
        m = json.loads(line)
    except ValueError:
        continue
    t = ts(m.get("timestamp"))
    if m.get("type") == "system" and m.get("subtype") == "compact_boundary":
        boundaries.append(t)
        continue
    msg = m.get("message") or {}
    content = msg.get("content")
    if m.get("type") == "assistant":
        u = msg.get("usage")
        if u and msg.get("id") not in seen:
            seen.add(msg.get("id"))
            calls.append((t, sum(u.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens",
                                                          "cache_read_input_tokens"))))
        for x in content or []:
            if isinstance(x, dict) and x.get("type") == "tool_use":
                uses[x.get("id")] = (x.get("name"), x.get("input") or {})
    elif m.get("type") == "user":
        if prompt is None:
            prompt = content if isinstance(content, str) else "".join(
                y.get("text") or "" for y in content or [] if isinstance(y, dict) and y.get("type") == "text")
        if isinstance(content, list):
            for x in content:
                if isinstance(x, dict) and x.get("type") == "tool_result":
                    c = x.get("content")
                    n = len(c) if isinstance(c, str) else sum(len(y.get("text") or "") for y in c or []
                                                              if isinstance(y, dict))
                    results.append((t, x.get("tool_use_id"), n))


def kind(cmd):
    c = cmd.lower()
    if re.search(r"(?<![-\w])verinoda(\.exe)?[\"']?\s+[a-z]", cmd):
        return "verinoda"
    if re.search(r"\b(grep|rg|findstr|select-string)\b", c):
        return "search (grep/rg)"
    if re.search(r"\bgit\s+(log|show|blame|diff)\b", c):
        return "git history/diff"
    if re.search(r"\b(cat|head|tail|sed -n|get-content)\b", c):
        return "read via shell"
    if re.search(r"\bnode\b", c):
        return "node (tests, bot runs)"
    return "other"


total_calls = len(calls)
by_tool, by_file, by_kind = defaultdict(lambda: [0, 0, 0.0]), defaultdict(lambda: [0, 0, 0.0]), defaultdict(
    lambda: [0, 0, 0.0])
for t, uid, n in results:
    name, inp = uses.get(uid, ("?", {}))
    nxt = min((b for b in boundaries if b and t and b > t), default=None)
    carried = sum(1 for c in calls if c[0] and t and c[0] > t and (nxt is None or c[0] < nxt))
    carry = n / 4 * carried
    for d, key in ((by_tool, name),
                   (by_file, inp.get("file_path") if name == "Read" else None),
                   (by_kind, kind(str(inp.get("command") or "")) if name in ("Bash", "PowerShell") else None)):
        if key:
            d[key][0] += 1
            d[key][1] += n
            d[key][2] += carry
all_carry = sum(v[2] for v in by_tool.values())
reads = sum(c[1] for c in calls)
print(f"model calls {total_calls}; context read in all {reads:,} tokens; tool results carried ~{all_carry:,.0f}"
      f" ({all_carry / reads:.0%} of it; the rest is the prompt, system text, tools and the model's own turns)")
for title, d in (("per tool", by_tool), ("per file read (Read)", by_file), ("per shell command kind", by_kind)):
    print(title + ":")
    for k, (cnt, chars, carry) in sorted(d.items(), key=lambda kv: -kv[1][2])[:8]:
        short = k if len(k) < 70 else "..." + k[-67:]
        print(f"   {short:70} {cnt:3}x  {chars:9,} chars  carried ~{carry:11,.0f}  {carry / reads:6.1%}")
print("prompt lines naming Verinoda:")
for ln in (prompt or "").splitlines():
    if "verinoda" in ln.lower():
        print("   " + ln[:300])
