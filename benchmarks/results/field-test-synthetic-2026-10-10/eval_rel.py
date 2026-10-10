"""Edges read by `verinoda relations` against the prerequisites gen.py planted (topics.json "prerequisites").

Self-consistency only: gen.py's five sentence templates are among the patterns the rules were written for.
Usage: python eval_rel.py CORPUS_DIR
"""

import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
from verinoda import readonly, relations  # noqa: E402

kb = Path(sys.argv[1]) / "kb"
truth = {(p, t) for t, ps in json.loads((kb / "topics.json").read_text(encoding="utf-8"))["prerequisites"].items()
         for p in ps}
with readonly.scope(True):
    t0 = time.perf_counter()
    res = relations.find(kb, topics_file="topics.json", max_items=100000)
    secs = time.perf_counter() - t0
got = {(r["from"], r["to"]) for r in res["relations"] if r["kind"] == "prerequisite"}
tp = got & truth
by_rule = Counter(r["evidence"][0]["rule"] for r in res["relations"])
wrong_rule = Counter(r["evidence"][0]["rule"] for r in res["relations"] if (r["from"], r["to"]) not in truth)
print(json.dumps({"files": res["files_read"], "planted_edges": len(truth), "read_edges": len(got),
                  "correct": len(tp), "precision": round(len(tp) / max(1, len(got)), 3),
                  "recall": round(len(tp) / max(1, len(truth)), 3),
                  "reversed": len({(b, a) for a, b in got} & truth), "seconds": round(secs, 2),
                  "co_mentions": res["co_mentions"], "by_rule": dict(by_rule), "wrong_by_rule": dict(wrong_rule),
                  "statuses": dict(Counter(r["status"] for r in res["relations"]))}, ensure_ascii=False, indent=1))
