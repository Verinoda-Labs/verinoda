"""The C3 selection's deviation check: the `none` arm's selection (22:05-22:41, with load at 22:08-22:14) against its
repeat on a quiet machine. Per instance: the chosen attempt and the selected patch's text, and where they differ, both
candidates' reproduction results. Usage: select_compare.py FIRST.jsonl REPEAT.jsonl"""
import json
import sys
from pathlib import Path


def load(p: Path) -> tuple[dict, dict]:
    rows = {json.loads(x)["instance_id"]: json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()}
    scores = Path(str(p)[: -len(".jsonl")] + ".scores.json")
    sc = {s["instance_id"]: s for s in json.loads(scores.read_text(encoding="utf-8"))} if scores.exists() else {}
    return rows, sc


a_rows, a_sc = load(Path(sys.argv[1]))
b_rows, b_sc = load(Path(sys.argv[2]))
ids = sorted(set(a_rows) | set(b_rows))
same_run = same_patch = 0
diffs = []
for i in ids:
    ra, rb = a_sc.get(i, {}).get("chosen_run"), b_sc.get(i, {}).get("chosen_run")
    pa, pb = (a_rows.get(i) or {}).get("model_patch"), (b_rows.get(i) or {}).get("model_patch")
    same_run += ra == rb
    same_patch += pa == pb
    if ra != rb or pa != pb:
        diffs.append(i)
print(f"instances {len(ids)} (first {len(a_rows)}, repeat {len(b_rows)}); same chosen attempt {same_run}; "
      f"same selected patch {same_patch}")
for i in diffs:
    def brief(sc):
        return [(c["run"], c.get("applies"), len(c.get("passes") or []), round(c.get("agreement") or 0, 2))
                for c in (sc.get(i) or {}).get("candidates", [])]
    print(f"- {i}: first {a_sc.get(i, {}).get('chosen_run')} {brief(a_sc)}")
    print(f"  {'':{len(i)}}  repeat {b_sc.get(i, {}).get('chosen_run')} {brief(b_sc)}")
