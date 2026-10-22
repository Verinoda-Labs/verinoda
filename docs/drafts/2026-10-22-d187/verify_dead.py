"""For each dead def: where else its name appears (package other than its own def line, tests, upstream tests, rest)."""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
g = json.load(open(sys.argv[2]))
defs, files = g["defs"], g["files"]
seen_txt = Path(sys.argv[3]).read_text(encoding="utf-8")

tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split("\n")
texts = {}
for f in tracked:
    if f.endswith((".py", ".ts", ".tsx", ".md", ".json", ".sh", ".toml", ".js", ".html")) and not f.startswith(
            ("benchmarks/results/", "docs/")):
        try:
            texts[f] = (ROOT / f).read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass

rows = []
for line in seen_txt.splitlines():
    path, rest = line.split(": ", 1)[0].split(" ", 1)[1].strip(), line.split(": ", 1)[1]
    for item in rest.split(", "):
        name = item.rsplit("(", 1)[0]
        short = name.split(".")[-1]
        if short.startswith("pytest_") or short in ("__getattr__", "__init__"):
            continue
        pat = re.compile(r"\b" + re.escape(short) + r"\b")
        own = path.replace("\\", "/")
        pkg = tests = up = other = 0
        where = []
        for f, t in texts.items():
            n = len(pat.findall(t))
            if not n:
                continue
            if f == own:
                n -= 1  # its def
                if n <= 0:
                    continue
            if f.startswith("verinoda/"):
                pkg += n
            elif f.startswith("tests_upstream/"):
                up += n
            elif f.startswith("tests/"):
                tests += n
            else:
                other += n
            where.append(f)
        rows.append((own, name, pkg, tests, up, other, where[:4]))

for r in rows:
    print(f"{r[0]}:{r[1]}  pkg={r[2]} tests={r[3]} upstream={r[4]} other={r[5]}  {' '.join(r[6]) if r[2] or r[5] else ''}")
