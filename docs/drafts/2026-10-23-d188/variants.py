"""Variants of the 37 recorded analyze results, written beside them for tokcount.py:
v0 as recorded (compact JSON); v1 JSON with content trims (an answer claim repeated under a second sub-question named by
id, the snapshot commit at 12 hex); v2 the same dict as text; v3 text with the trims."""
import copy
import glob
import json
import os

D = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(D, "variants"), exist_ok=True)


def trims(d: dict) -> dict:
    d = copy.deepcopy(d)
    snap = d.get("snapshot") or {}
    if snap.get("commit"):
        snap["commit"] = snap["commit"][:12]
    said = set()
    for s in d.get("subquestions") or []:
        out = []
        for a in s.get("answers") or []:
            if a["id"] in said:
                out.append({"id": a["id"], "same_as_above": True})
            else:
                said.add(a["id"])
                out.append(a)
        s["answers"] = out
    return d


def _scalar(v) -> str:
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)


def _generic(key: str, v, ind: str, lines: list[str]) -> None:
    if isinstance(v, dict):
        lines.append(f"{ind}{key}:")
        for k, x in v.items():
            _generic(k, x, ind + "  ", lines)
    elif isinstance(v, list):
        if all(not isinstance(x, (dict, list)) for x in v):
            lines.append(f"{ind}{key}: " + "; ".join(_scalar(x) for x in v))
        else:
            lines.append(f"{ind}{key}:")
            for x in v:
                _generic("-", x, ind + "  ", lines)
    else:
        lines.append(f"{ind}{key}: {_scalar(v)}")


def text(d: dict) -> str:
    lines = [f"status: {d['status']}"]
    if d.get("understood_as"):
        lines.append(f"understood_as: {d['understood_as']}")
    snap = d.get("snapshot")
    if snap:
        lines.append(f"snapshot: {snap.get('id')} commit {snap.get('commit')}" + (" dirty" if snap.get("dirty") else ""))
    if d.get("analysis_id"):
        lines.append(f"analysis_id: {d['analysis_id']}")
    for k in ("errors", "clarifications", "plan_fallback", "intent_check", "budget_exhausted", "plan_id",
              "truncated", "truncation"):
        if d.get(k) is not None:
            _generic(k, d[k], "", lines)
    for s in d.get("subquestions") or []:
        lines.append(f"{s['id']} [{s['intent']}] {s['status']}" + ("" if s.get("answers") else ": no answer claim"))
        for a in s.get("answers") or []:
            if a.get("same_as_above"):
                lines.append(f"  {a['id']}: the same claim as above")
                continue
            conf = f" {a['confidence']}" if a.get("confidence") is not None else ""
            lines.append(f"  {a['id']} {a['status']}{conf}: {a['text']}")
            for e in a.get("evidence") or []:
                lines.append(f"    evidence: {e}")
            for u in a.get("uncertainties") or []:
                lines.append(f"    uncertain: {u}")
            if a.get("not_challenged"):
                lines.append(f"    not challenged: {a['not_challenged']}")
    if d.get("leads"):
        lines.append("leads:")
        lines += [f"  {x}" for x in d["leads"]]
    for u in d.get("unknowns") or []:
        lines.append(f"unknown ({u.get('sub_question')}): {u.get('question')}")
        lines.append(f"  why: {u.get('why')}")
        if u.get("commits"):
            lines.append("  commits: " + "; ".join(_scalar(c) for c in u["commits"]))
        lines.append(f"  next: {u.get('next_step')}")
        for k, v in u.items():
            if k not in ("sub_question", "question", "why", "commits", "next_step"):
                _generic(k, v, "  ", lines)
    if d.get("facts"):
        _generic("facts", d["facts"], "", lines)
    if d.get("context"):
        lines.append("context:")
        lines += [f"  {x}" for x in d["context"]]
    lines.append(f"coverage: {d['coverage']}")
    return "\n".join(lines)


for f in sorted(glob.glob(os.path.join(D, "results", "*.txt"))):
    base = os.path.splitext(os.path.basename(f))[0]
    d = json.loads(open(f, encoding="utf-8").read())
    t = trims(d)
    outs = {"v0": json.dumps(d, ensure_ascii=False, separators=(",", ":")),
            "v1": json.dumps(t, ensure_ascii=False, separators=(",", ":")),
            "v2": text(d), "v3": text(t)}
    for k, s in outs.items():
        with open(os.path.join(D, "variants", f"{base}.{k}.txt"), "w", encoding="utf-8", newline="") as fh:
            fh.write(s)
print("written")
