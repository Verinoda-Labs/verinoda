"""What each call cost, for a test run that wants it per call (D178).

An agent's own report gives the tokens of a whole session or stage; what one Verinoda call added is
not in it. With ``VERINODA_USAGE_LOG`` set to a file, every MCP tool call and every CLI command
appends one JSON line there: the tool or command, the characters of its arguments and of its
result as the agent receives it (the MCP content text; the CLI's standard output), the seconds it
took, and a token estimate. Nothing is added to the result itself (it would cost every call the
tokens it measures, and a plain-text MCP answer carries no other field to the agent), and nothing is
written when the variable is not set.

``tokens_est`` is characters / 4, the estimate Verinoda uses elsewhere (``context_tokens_est``); it
is not the model's tokenizer, and Turkish or code-heavy text is usually more tokens than that.
"""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

LOG_ENV = "VERINODA_USAGE_LOG"
CHARS_PER_TOKEN = 4


def log_path() -> Path | None:
    raw = os.environ.get(LOG_ENV, "").strip()
    return Path(raw) if raw else None


def chars(obj: Any) -> int:
    """Characters of ``obj`` as compact JSON (a string: its own length)."""
    if isinstance(obj, str):
        return len(obj)
    return len(json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str))


def tokens_est(n_chars: int) -> int:
    return (n_chars + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN


def record(surface: str, name: str, args_chars: int, result_chars: int, seconds: float, *,
           error: str | None = None, extra: dict | None = None) -> bool:
    """Append one line to the log (False when no log is set or it cannot be written: a call never fails for it)."""
    p = log_path()
    if p is None:
        return False
    row = {"ts": round(time.time(), 3), "surface": surface, "name": name, "args_chars": args_chars,
           "result_chars": result_chars, "result_tokens_est": tokens_est(result_chars),
           "args_tokens_est": tokens_est(args_chars), "seconds": round(seconds, 4), "pid": os.getpid(),
           **({"error": error} if error else {}), **(extra or {})}
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    except OSError:
        return False
    return True


def wire_text(res: Any) -> str:
    """The text an MCP client receives for a tool's result: the content blocks of a ``CallToolResult``
    (mcp 2.x), else the dict as compact JSON (mcp 1.x serialises it itself: an approximation there)."""
    content = getattr(res, "content", None)
    if content is not None:
        return "".join(getattr(c, "text", "") or "" for c in content)
    return res if isinstance(res, str) else json.dumps(res, ensure_ascii=False, separators=(",", ":"), default=str)


def summarize(path: Path) -> dict:
    """Totals of a log, per surface and name: calls, characters and estimated tokens, seconds. Unreadable
    lines are counted, not guessed."""
    by: dict[tuple[str, str], dict] = defaultdict(lambda: {"calls": 0, "args_chars": 0, "result_chars": 0,
                                                           "seconds": 0.0, "errors": 0})
    bad = 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                r = json.loads(line)
                key = (str(r["surface"]), str(r["name"]))
                row = by[key]
                row["calls"] += 1
                row["args_chars"] += int(r.get("args_chars") or 0)
                row["result_chars"] += int(r.get("result_chars") or 0)
                row["seconds"] += float(r.get("seconds") or 0)
                row["errors"] += 1 if r.get("error") else 0
            except (ValueError, KeyError, TypeError):
                bad += 1
    rows = []
    for (surface, name), r in sorted(by.items(), key=lambda kv: -kv[1]["result_chars"]):
        rows.append({"surface": surface, "name": name, **r, "seconds": round(r["seconds"], 3),
                     "result_tokens_est": tokens_est(r["result_chars"])})
    total = {k: sum(r[k] for r in rows) for k in ("calls", "args_chars", "result_chars", "errors")}
    total["result_tokens_est"] = tokens_est(total["result_chars"])
    total["seconds"] = round(sum(r["seconds"] for r in rows), 3)
    return {"path": str(path), "rows": rows, "total": total, "unreadable_lines": bad,
            "tokens_est": f"characters / {CHARS_PER_TOKEN}, not the model's tokenizer"}


def render(res: dict) -> str:
    out = [(f"{res['path']}: {res['total']['calls']} call(s), {res['total']['result_chars']} result characters "
            f"(~{res['total']['result_tokens_est']} tokens, {res['tokens_est']}), {res['total']['seconds']} s")]
    for r in res["rows"]:
        out.append(f"  {r['surface']:<4} {r['name']:<24} {r['calls']:>5} call(s)  {r['result_chars']:>9} chars  "
                   f"~{r['result_tokens_est']:>7} tokens  args {r['args_chars']:>6} chars  {r['seconds']:>8} s"
                   + (f"  {r['errors']} error(s)" if r["errors"] else ""))
    if res.get("unreadable_lines"):
        out.append(f"  {res['unreadable_lines']} unreadable line(s) left out")
    return "\n".join(out)


class CountingStream:
    """``sys.stdout`` for one CLI command: counts the characters written, writes them on."""

    def __init__(self, inner):
        self._inner = inner
        self.chars = 0

    def write(self, text: str) -> int:
        self.chars += len(text)
        return self._inner.write(text)

    def __getattr__(self, name: str):
        return getattr(self._inner, name)
