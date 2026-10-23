"""Claude Code's /context (print mode, no model call) with one MCP config each: the MCP rows and the totals."""
import json, os, re, shutil, subprocess, sys, tempfile

PY = r"C:\Users\me\Desktop\verinoda-symbiosis\.venv\Scripts\python.exe"
EXE = r"C:\Users\me\.local\bin\verinoda.exe"
REPO = r"C:\Users\me\Desktop\verinoda-symbiosis"
HOME = r"C:\Users\me"
configs = {
    "installed@repo": {"command": EXE, "args": ["mcp", "serve", "--repo", REPO]},
    "dev@repo": {"command": PY, "args": ["-m", "verinoda", "mcp", "serve", "--repo", REPO], "cwd": REPO},
    "installed@home": {"command": EXE, "args": ["mcp", "serve", "--repo", HOME]},
    "dev@home": {"command": PY, "args": ["-m", "verinoda", "mcp", "serve", "--repo", HOME], "cwd": REPO},
    "none": None,
}
claude = shutil.which("claude.exe") or shutil.which("claude.cmd")
for name, srv in configs.items():
    work = tempfile.mkdtemp(prefix="ctx-")
    cfg = {"mcpServers": {"verinoda": {"type": "stdio", "env": {}, **srv}} if srv else {}}
    with open(os.path.join(work, "mcp.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f)
    run = subprocess.run([claude, "-p", "/context", "--strict-mcp-config", "--mcp-config", "mcp.json",
                          "--output-format", "text"], cwd=work, capture_output=True, text=True, encoding="utf-8",
                         stdin=subprocess.DEVNULL, timeout=300)
    rows = [ln for ln in run.stdout.splitlines() if re.match(r"\| (System prompt|MCP|mcp__verinoda)", ln)
            or ln.startswith("**Tokens:**")]
    print(f"== {name}")
    for r in rows:
        print("  ", r)
    shutil.rmtree(work, ignore_errors=True)
