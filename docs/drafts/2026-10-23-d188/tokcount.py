"""Exact token counts of text files, free and local: each file becomes a rule file of an empty project, and Claude
Code's `/context` (print mode, no model call) lists every memory file with its tokens. A one-character calibration file
gives the per-file wrapper (8 tokens on 2026-10-23), which is subtracted.

    python tokcount.py <out.json> <file> [<file> ...]
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile


CHUNK = 1200   # chars: the table prints counts of 1,000 and more rounded to 100 ("1.5k"); hex runs 0.65 tokens a char


def _pieces(text: str) -> list[str]:
    """``text`` cut at a newline, a space or a comma near every CHUNK chars (a cut there splits no token)."""
    out = []
    while len(text) > CHUNK:
        cut = max(text.rfind(c, 0, CHUNK) for c in "\n ,")
        cut = cut + 1 if cut > CHUNK // 2 else CHUNK
        out.append(text[:cut])
        text = text[cut:]
    return [*out, text] if text else out


def count(paths: list[str]) -> dict[str, int]:
    work = tempfile.mkdtemp(prefix="tokcount-")
    try:
        rules = os.path.join(work, ".claude", "rules")
        os.makedirs(rules)
        names = {}
        for i, p in enumerate(paths):
            with open(p, encoding="utf-8", newline="") as f:
                text = f.read()
            for j, piece in enumerate(_pieces(text)):
                name = f"f{i:04d}p{j:03d}.md"
                names[name] = p
                with open(os.path.join(rules, name), "w", encoding="utf-8", newline="") as f:
                    f.write(piece)
        with open(os.path.join(rules, "zcalib.md"), "w", encoding="utf-8", newline="") as f:
            f.write("x")
        with open(os.path.join(work, "none.mcp.json"), "w", encoding="utf-8") as f:
            f.write('{"mcpServers": {}}')
        exe = shutil.which("claude.exe") or shutil.which("claude.cmd") or "claude"
        run = subprocess.run([exe, "-p", "/context", "--strict-mcp-config", "--mcp-config", "none.mcp.json",
                              "--output-format", "text"], cwd=work, capture_output=True, text=True, encoding="utf-8",
                             stdin=subprocess.DEVNULL, timeout=600)
        got = {}
        for line in run.stdout.splitlines():
            m = re.search(r"rules[\\/](\w+\.md) \| ([\d.,]+k?) \|", line)
            if m:
                v = m.group(2).replace(",", "")
                got[m.group(1)] = int(float(v[:-1]) * 1000) if v.endswith("k") else int(v)
        if "zcalib.md" not in got:
            raise SystemExit("no calibration row; output was:\n" + run.stdout[-3000:] + run.stderr[-2000:])
        wrap = got["zcalib.md"] - 1
        missing = sorted(set(names) - set(got))
        if missing:
            raise SystemExit(f"{len(missing)} pieces not in the table, e.g. {missing[:3]}")
        total: dict[str, int] = {}
        for k, v in got.items():
            if k in names:
                if v >= 1000:
                    raise SystemExit(f"{k} counted {v}: a rounded row; lower CHUNK")
                total[names[k]] = total.get(names[k], 0) + v - wrap
        return total
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    out = count(sys.argv[2:])
    json.dump(out, open(sys.argv[1], "w", encoding="utf-8"), indent=1)
    print(len(out), "files counted;", sum(out.values()), "tokens")
