"""Run every verinoda CLI command once on small indexed example projects and report crashes (tracebacks).

Isolation: HOME, USERPROFILE, APPDATA, LOCALAPPDATA, XDG_* and VERINODA_CACHE_DIR point into a throw-away folder,
so nothing writes to the real user configuration. Nothing is pushed, no network (`--network off` where offered).
usage: python smoke.py <verinoda checkout> <work dir> <out.json>
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

CHECKOUT = Path(sys.argv[1]).resolve()
WORK = Path(sys.argv[2]).resolve()
OUT = Path(sys.argv[3])
PY = str(CHECKOUT / ".venv" / "Scripts" / "python.exe")

if WORK.exists():
    shutil.rmtree(WORK)
home = WORK / "home"
for d in ("home", "home/AppData/Roaming", "home/AppData/Local", "cache", "xdgc", "xdgcache"):
    (WORK / d).mkdir(parents=True, exist_ok=True)
env = dict(os.environ)
env.update(HOME=str(home), USERPROFILE=str(home), APPDATA=str(home / "AppData" / "Roaming"),
           LOCALAPPDATA=str(home / "AppData" / "Local"), XDG_CONFIG_HOME=str(WORK / "xdgc"),
           XDG_CACHE_HOME=str(WORK / "xdgcache"), VERINODA_CACHE_DIR=str(WORK / "cache"),
           PYTHONIOENCODING="utf-8", GIT_CONFIG_NOSYSTEM="1", ANTHROPIC_API_KEY="")
env.pop("VERINODA_USAGE_LOG", None)


def git(cwd, *a):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "core.autocrlf=false", *a], cwd=cwd,
                   check=True, capture_output=True)


def project(name: str) -> Path:
    dst = WORK / name
    shutil.copytree(CHECKOUT / "examples" / name, dst, ignore=shutil.ignore_patterns(".verinoda", "__pycache__"))
    git(dst, "init", "-q")
    git(dst, "add", "-A")
    git(dst, "commit", "-qm", "init")
    return dst


def run(args: list[str], cwd: Path, timeout: float = 240, stdin: str | None = None) -> dict:
    t = time.perf_counter()
    try:
        r = subprocess.run([PY, "-m", "verinoda", *args], cwd=cwd, env=env, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout, input=stdin)
        code, out, err = r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired as exc:
        code, out, err = "timeout", str(exc.stdout or "")[-500:], str(exc.stderr or "")[-500:]
    return {"args": args, "cwd": cwd.name, "exit": code, "seconds": round(time.perf_counter() - t, 2),
            "traceback": "Traceback (most recent call last)" in (err or "") or "Traceback (most recent call last)"
            in (out or ""), "stderr": (err or "")[-1500:], "stdout_head": (out or "")[:300]}


orders = project("orders_app")
glow = project("glow_mod")
forge = project("forge_mod")
results = []
for p in (orders, glow, forge):
    results.append(run(["scan", ".", "--json"], p))
# a small commit so history and diff commands have something
svc = orders / "orders" / "service.py"
svc.write_text(svc.read_text(encoding="utf-8") + "\n\ndef smoke_added(x):\n    return x + 1\n", encoding="utf-8")
git(orders, "add", "-A")
git(orders, "commit", "-qm", "add smoke_added")
results.append(run(["update", ".", "--json"], orders))

O = [
    ["doctor", "--json"], ["doctor", "--brief"], ["graph-state", "--json"], ["hooks", "status"],
    ["agent-hooks", "status"], ["projects", "list"], ["group", "list"], ["trust", "--list"],
    ["consolidate", "--json", "--dry-run"], ["notes", "--json"], ["map", "--json"], ["map", "--view", "dependencies"],
    ["map", "--view", "hotspots"], ["map", "--view", "dsm"], ["map", "--view", "impact", "--target", "orders/service.py"],
    ["map", "--trace", "create_order", "compute_total"], ["review", "--json", "--base", "HEAD~1"],
    ["affected", "--json", "--base", "HEAD~1"], ["health", "--json"], ["query", "where is compute_total defined?"],
    ["query", "--json", "how are orders saved?"], ["locate", "--no-daemon", "--json", "order total is wrong"],
    ["coupled", "--no-daemon", "orders/service.py"], ["trace", "create_order", "compute_total"], ["schema", "--json"],
    ["routes", "--json"], ["export", "--format", "graphml", "--out", "graph.graphml"],
    ["export", "--format", "cypher", "--out", "graph.cypher"], ["export", "--format", "obsidian", "--out", "vault"],
    ["diagram", "architecture"], ["diagram", "flow", "create_order"], ["diagram", "sequence", "create_order",
                                                                        "compute_total"],
    ["wiki", "--json"], ["relations", "--json", "--co-mentions"], ["rationale", "--json"], ["agent-lint", "--json"],
    ["brief", "--json"], ["secret-scan", "--json"], ["when", "compute_total"], ["butterfly", "compute_total"],
    ["extract", "compute_total"], ["history", "text", "smoke_added"], ["history", "symbol", "compute_total"],
    ["history", "commits", "--message", "smoke"], ["docs", "check"], ["spec", "check"],
    ["grep-ast", "--json", "def $F($$$)"], ["infra", "--json"], ["context", "orders/service.py"],
    ["tour", "--json", "create_order", "compute_total"], ["rules", "--json"], ["monitor", "check"],
    ["owners", "--json"], ["rename-preview", "compute_total", "order_total"],
    ["what-if", "--move", "orders/pricing.py=orders/price.py"], ["analyze", "--json", "How is an order total computed?"],
    ["analyze", "Why was smoke_added added?"], ["plan", "draft", "where is compute_total defined?"],
    ["plan", "schema"], ["decide", "list"], ["decide", "toc"], ["decide", "check"], ["decide", "undocumented"],
    ["claim", "list"], ["resolve", "--network", "off", "requests 2.31"], ["fact", "list"], ["feedback", "list"],
    ["inventory", "--json", "def "], ["q", "match (f:function) return f limit 3"],
    ["tq", "exists compute_total", "calls create_order compute_total"], ["taint", "--json"],
    ["slice", "orders/service.py:5"], ["search", "compute_total"], ["resolve-call", "orders/service.py:1",
                                                                     "compute_total"],
    ["lsp", "definition", "orders/service.py:1", "compute_total"], ["check", "orders/service.py", "--json"],
    ["check", "--diff", "HEAD~1", "--json"], ["check", "--deps", "--json"], ["api", "json"], ["memory", "list"],
    ["install", "--agent", "claude", "--scope", "project", "--dry-run"], ["mcp", "prompts"],
    ["usage", "--json"], ["benchmark", "--help"], ["backlog", "--json", "1.1"],
    ["coverage", "--json"], ["observe", "--json", "--timeout", "60"],
    ["probe", "--json", "--changed", "--base", "HEAD~1", "--timeout", "60"],
    ["debug", "status"], ["experiment", "--help"], ["mutate", "--help"], ["pin", "--help"],
    ["verify", "--help"], ["challenge", "--help"], ["research", "--help"], ["compare", "--help"],
    ["ui", "--export", "ui.html"], ["sarif", "--help"], ["import-findings", "--help"], ["trace-log", "--help"],
]
MC = [
    ["datapack", "--json"], ["datapack", "function"], ["shader", "--json"], ["access-check", "--json"],
    ["mixin-check", "--json"], ["mixin-check", "--conflicts", "--json"], ["lang", "--json"],
    ["check", "--json", "src"], ["query", "where is the glow effect applied?"],
    ["analyze", "--json", "What does the mod register at startup?"],
]
for a in O:
    results.append(run(a, orders))
for p in (glow, forge):
    for a in MC:
        results.append(run(a, p))
OUT.write_text(json.dumps(results, indent=1), encoding="utf-8")
bad = [r for r in results if r["traceback"] or r["exit"] == "timeout"]
print(f"{len(results)} runs, {len(bad)} with a traceback or a time-out")
for r in bad:
    print(r["cwd"], r["args"], r["exit"], r["stderr"][-600:].replace("\n", " | "))
codes = {}
for r in results:
    codes.setdefault(str(r["exit"]), []).append(" ".join(r["args"][:3]))
for c, a in sorted(codes.items()):
    print(f"exit {c}: {len(a)}" + ("" if c == "0" else f" -> {a}"))
slow = sorted(results, key=lambda r: -r["seconds"])[:8]
print("slowest:", [(r["cwd"], " ".join(r["args"][:3]), r["seconds"]) for r in slow])
