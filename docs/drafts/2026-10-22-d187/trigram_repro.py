import os, subprocess, sys, tempfile, threading
from pathlib import Path
os.environ.setdefault("GRAPHIFY_OUT", ".verinoda/index")
from verinoda import trigram

fails = 0
runs = int(sys.argv[1]) if len(sys.argv) > 1 else 15
for r in range(runs):
    root = Path(tempfile.mkdtemp(prefix="tri-"))
    (root / "src").mkdir()
    for i in range(30):
        (root / "src" / f"m{i}.py").write_text(f"alpha {i}\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    errors = []
    def go():
        try:
            trigram.search(root, "alpha 2")
        except Exception as exc:
            errors.append(exc)
    ts = [threading.Thread(target=go) for _ in range(6)]
    for t in ts: t.start()
    for t in ts: t.join()
    if errors:
        fails += 1
        print("run", r, type(errors[0]).__name__, str(errors[0])[-80:])
print(f"{fails} of {runs} runs had an error")
