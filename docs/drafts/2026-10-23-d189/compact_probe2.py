"""The probe's session compacted once more with VERINODA_USAGE_LOG set: did the mod's hook run `verinoda card`?"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:\Users\me\Desktop\verinoda-symbiosis")
MOD = REPO / "claude-mods" / "verinoda-live"
sid, proj = sys.argv[1], Path(sys.argv[2])
log = Path(sys.argv[3])
claude = shutil.which("claude.exe") or shutil.which("claude.cmd")
settings = json.dumps({"enabledPlugins": {"verinoda-live@verinoda-symbiosis-local": False}})
env = {**os.environ, "PATH": str(REPO / ".venv" / "Scripts") + os.pathsep + os.environ.get("PATH", ""),
       "VERINODA_USAGE_LOG": str(log)}
r = subprocess.run([claude, "-p", "--resume", sid, "/compact", "--plugin-dir", str(MOD), "--settings", settings,
                    "--model", "sonnet", "--output-format", "json"], cwd=proj, env=env, capture_output=True, text=True,
                   encoding="utf-8", stdin=subprocess.DEVNULL, timeout=600)
print("exit", r.returncode, "| cost", (json.loads(r.stdout) if r.stdout.strip().startswith("{") else {}).get("total_cost_usd"))
print("log exists:", log.exists())
if log.exists():
    for line in log.read_text(encoding="utf-8").splitlines():
        print("  ", line[:300])
