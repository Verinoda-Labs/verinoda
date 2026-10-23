"""One real check of D189: a throwaway project, the working tree's mod and CLI, a few Reads, then /compact; does the
summary carry Verinoda's cards? Two small model calls (sonnet)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(r"C:\Users\me\Desktop\verinoda-symbiosis")
MOD = REPO / "claude-mods" / "verinoda-live"
claude = shutil.which("claude.exe") or shutil.which("claude.cmd")
proj = Path(tempfile.mkdtemp(prefix="cardprobe-")) / "proj"
(proj / ".verinoda").mkdir(parents=True)
(proj / "pricing.py").write_text('"""Computes order totals with the discount rule."""\nimport math\n\n\ndef total(items):\n'
                                 '    return sum(items)\n', encoding="utf-8")
(proj / "Kale.java").write_text("package demo;\n\nimport java.util.List;\n\n/** Builds the castle of the demon. */\n"
                                "public class Kale {\n  void build() {}\n}\n", encoding="utf-8")
(proj / "PLAN.md").write_text("# Wing release plan\n\n## Art\n\n## Code\n", encoding="utf-8")
settings = json.dumps({"enabledPlugins": {"verinoda-live@verinoda-symbiosis-local": False}})
env = {**os.environ, "PATH": str(REPO / ".venv" / "Scripts") + os.pathsep + os.environ.get("PATH", ""), "VERINODA_USAGE_LOG": str(Path(__file__).with_name("usage-probe3.jsonl"))}
base = [claude, "-p", "--plugin-dir", str(MOD), "--settings", settings, "--model", "sonnet", "--output-format", "json"]


def run(args):
    r = subprocess.run(base[:2] + args + base[2:], cwd=proj, env=env, capture_output=True, text=True, encoding="utf-8",
                       stdin=subprocess.DEVNULL, timeout=600)
    try:
        return json.loads(r.stdout)
    except ValueError:
        print("stdout:", r.stdout[-1500:], "\nstderr:", r.stderr[-1500:])
        raise


first = run(["Read pricing.py, Kale.java and PLAN.md with the Read tool, then answer only: OK"])
sid = first["session_id"]
print("session", sid, "| answer:", str(first.get("result"))[:80], "| cost", first.get("total_cost_usd"))
second = run(["--resume", sid, "/compact"])
print("compact:", str(second.get("result"))[:300], "| cost", second.get("total_cost_usd"))
enc = "C--" + str(proj).replace(":\\", "-").replace("\\", "-").replace(" ", "-").split("C--", 1)[-1]
hits = [p for p in (Path.home() / ".claude" / "projects").glob(f"*{proj.parent.name}*/{sid}.jsonl")]
hits += [p for p in (Path.home() / ".claude" / "projects").glob(f"*/{sid}.jsonl") if p not in hits]
print("transcripts:", [str(h) for h in hits])
for h in hits[:1]:
    for line in h.read_text(encoding="utf-8").splitlines():
        m = json.loads(line)
        if m.get("isCompactSummary") or (m.get("type") == "system" and m.get("subtype") == "compact_boundary"):
            c = (m.get("message") or {}).get("content")
            text = c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)
            print("----", m.get("type"), m.get("subtype"), (m.get("compactMetadata") or {}).get("trigger"))
            print(text[:3000] if text else "")

log = Path(__file__).with_name("usage-probe3.jsonl")
print("card calls:", [l[:200] for l in log.read_text(encoding="utf-8").splitlines() if '"name":"card"' in l] if log.exists() else "no log")
