"""Set the zero-call Verinoda-arm sessions aside (the coordinator's instruction of 2026-10-13, preparation for the re-run).

    python split_superseded.py WORK_DIR

Inside WORK_DIR only. Splits results.jsonl by arm without re-serialising a row (every line keeps its bytes), moves judge.jsonl and
mechanical.jsonl, copies the three logs and the as-run config, and writes superseded-zero-call/README.md with the counts it finds.
Refuses to run when superseded-zero-call/ already exists. The usage/ folder, the copies and the clones are not touched.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import time
from collections import Counter
from pathlib import Path

PLAIN, GUIDED = "none", "verinoda_guided"


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def rows_of(raw: bytes) -> list[dict]:
    return [json.loads(x) for x in raw.decode("utf-8").splitlines() if x.strip()]


def main() -> int:
    w = Path(sys.argv[1])
    sup = w / "superseded-zero-call"
    if sup.exists():
        print("refusing: superseded-zero-call/ exists already")
        return 1
    src = w / "results.jsonl"
    raw = src.read_bytes()
    lines = raw.splitlines(keepends=True)
    parsed = [json.loads(x) for x in lines if x.strip()]
    assert len(lines) == len(parsed) == 63, (len(lines), len(parsed))
    verinoda = [ln for ln, r in zip(lines, parsed) if r["arm"] == GUIDED]
    plain = [ln for ln, r in zip(lines, parsed) if r["arm"] == PLAIN]
    assert len(verinoda) == 39 and len(plain) == 24 and len(verinoda) + len(plain) == len(lines)
    assert all(ln.endswith(b"\n") for ln in lines)
    before = {"results.jsonl": sha(raw)}

    sup.mkdir()
    (sup / "logs").mkdir()
    (sup / "results-as-run.jsonl").write_bytes(raw)
    (sup / "results-verinoda-zero-call.jsonl").write_bytes(b"".join(verinoda))
    tmp = w / "results.jsonl.tmp"
    tmp.write_bytes(b"".join(plain))

    # verify before anything is replaced
    v_back = rows_of((sup / "results-verinoda-zero-call.jsonl").read_bytes())
    p_back = rows_of(tmp.read_bytes())
    assert len(v_back) == 39 and all(r["arm"] == GUIDED for r in v_back)
    assert len(p_back) == 24 and all(r["arm"] == PLAIN for r in p_back)
    assert sorted(verinoda + plain) == sorted(lines), "the two halves are not the original lines"
    assert all(r["verinoda_calls"] == 0 and not r["is_error"] for r in v_back)
    tmp.replace(src)

    moved = {}
    for name in ("judge.jsonl", "mechanical.jsonl"):
        f = w / name
        if f.exists():
            moved[name] = {"sha256": sha(f.read_bytes()), "bytes": f.stat().st_size, "rows": len(f.read_text(encoding="utf-8").splitlines())}
            shutil.move(str(f), str(sup / name))
            assert sha((sup / name).read_bytes()) == moved[name]["sha256"]
    copied = {}
    for name in ("step1-rerun.log", "step2-cost-sample.log", "step3-score.log"):
        f = w / "logs" / name
        if f.exists():
            shutil.copy2(f, sup / "logs" / name)
            copied[name] = f.stat().st_size
    shutil.copy2(w / "config.json", sup / "config.as-run.json")

    judge_rows = [json.loads(x) for x in (sup / "judge.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    judged_by_arm = Counter(j["arm"] for j in judge_rows)
    six = {"fastapi__full-stack-fastapi-template-why-1", "junegunn__fzf-why-1", "guzzle__guzzle-trap-1", "gin-gonic__gin-trap-1",
           "axios__axios-when-1", "sharkdp__bat-when-1"}
    rerun_keys = {(r["id"], r["repeat"]) for r in v_back if r["id"] in six}
    cost_sample_verinoda = [r for r in v_back if r["repeat"] == 1]
    info = {
        "made_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "original_results_sha256": before["results.jsonl"], "original_rows": len(lines),
        "verinoda_rows": len(verinoda), "verinoda_sha256": sha(b"".join(verinoda)),
        "plain_rows": len(plain), "plain_sha256": sha(b"".join(plain)),
        "rerun_six_rows": len(rerun_keys), "verinoda_repeat1_rows": len(cost_sample_verinoda),
        "verinoda_cost_usd": round(sum(r["cost_usd"] for r in v_back), 3), "plain_cost_usd": round(sum(r["cost_usd"] for r in p_back), 3),
        "moved": moved, "copied_logs": copied, "judge_rows_by_arm": dict(judged_by_arm),
        "judge_failed": sum(bool(j.get("judge_failed")) for j in judge_rows),
    }
    (sup / "split-manifest.json").write_text(json.dumps(info, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(info, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
