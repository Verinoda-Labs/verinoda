"""The study's tables (DESIGN_SWEBENCH_CEILING.md: the measures, amendments 6 and 7), from what is graded so far.

    python report.py [--markdown]

Per run and arm: lanes, graded, resolved (local calibrated after amendment 2's regrade; the last session counts, amendment
6), not counted (the leak review), flagged sessions (first attempt, last), the sensitivity line (first attempts, flagged
left out), cost, turns and seconds per session (every session the lane ran, re-runs included), and amendment 7's recall:
mean among the resolved, verbatim count, and the resolved count leaving out verbatim patches on instances whose
false_negative annotation is 2 or more. Then the paired comparisons the design names: the arms within a run, each run
against C1 per arm, and C4's rule (resolved summed over both arms).
"""

import json
import random
import sys
from pathlib import Path

TMP = Path(__file__).resolve().parent
sys.path.insert(0, str(TMP))
sys.path.insert(0, "C:/Users/ozcin/Desktop/vwt-ceiling/benchmarks/agent_compare")
from swebench_recall import VERBATIM, recall

from compare import mcnemar
from final_grades import final, rows

DATA = Path("C:/Users/ozcin/swebench-data")
RUNS = [("C0 (D184's harness, repeat 1)", "c0-s1"), ("C1 Sonnet", "c1-s1"), ("C4 Opus", "c4-opus"),
        ("C4 Fable", "c4-fable"), ("C3 attempt 2 (Opus)", "c3-opus-2"), ("C3 attempt 3 (Opus)", "c3-opus-3"),
        ("C3 attempt 2 (Fable)", "c3-fable-2"), ("C3 attempt 3 (Fable)", "c3-fable-3"),
        ("diagnostic: hints", "diag-hints"), ("diagnostic: tests", "diag-tests")]
ARMS = {"none": "plain", "verinoda_guided": "guided"}
CEILING = {r["id"]: r for r in json.loads((TMP / "ceiling.json").read_text(encoding="utf-8"))}


def lite() -> dict[str, dict]:
    import pyarrow.parquet as pq
    return {r["instance_id"]: r for r in pq.read_table(DATA / "lite.parquet").to_pylist()}


def sessions(run: str, arm: str) -> list[dict]:
    out = []
    for k in ("", "-r1", "-r2"):
        out += [r for (i, a), r in rows(run + k).items() if a == arm]
    return out


def last_rows(run: str, arm: str) -> dict[str, dict]:
    got = {}
    for k in ("", "-r1", "-r2"):
        got.update({i: r for (i, a), r in rows(run + k).items() if a == arm})
    return got


def paired(a: dict[str, bool], b: dict[str, bool]) -> str:
    ids = sorted(set(a) & set(b))
    if not ids:
        return "no instance graded in both"
    only_a = sum(a[i] and not b[i] for i in ids)
    only_b = sum(b[i] and not a[i] for i in ids)
    rng = random.Random(20261024)
    diffs = sorted((sum(b[i] for i in s) - sum(a[i] for i in s)) / len(s)
                   for s in ([rng.choice(ids) for _ in ids] for _ in range(10000)))
    return (f"n {len(ids)}: {sum(a[i] for i in ids)} vs {sum(b[i] for i in ids)} (discordant {only_a}/{only_b}), "
            f"difference {(sum(b[i] for i in ids) - sum(a[i] for i in ids)) / len(ids):+.3f} "
            f"[{diffs[250]:+.3f}, {diffs[9749]:+.3f}], McNemar p {mcnemar(only_a, only_b):.3f}")


def main() -> None:
    data = lite()
    resolved: dict[tuple[str, str], dict[str, bool]] = {}
    print("run / arm | lanes | graded | resolved | not counted | flagged first/last | sensitivity | $/session | turns | "
          "s/session | recall (resolved) | verbatim | resolved w/o verbatim on fn>=2")
    for label, run in RUNS:
        for arm, short in ARMS.items():
            f = final(run, arm)
            if not f:
                continue
            graded = {i: bool(v["resolved"]) for i, v in f.items() if v["resolved"] is not None}
            resolved[(run, arm)] = graded
            first_ok = [v for v in f.values() if not v["first_flagged"] and v["first_resolved"] is not None]
            ss = sessions(run, arm)
            cost = sum(r.get("cost_usd") or 0 for r in ss) / max(len(ss), 1)
            turns = sum(r.get("num_turns") or 0 for r in ss) / max(len(ss), 1)
            secs = sum(r.get("seconds") or 0 for r in ss) / max(len(ss), 1)
            last = last_rows(run, arm)
            rec = {i: recall(last[i].get("patch") or "", data[i]["patch"], data[i]["problem_statement"])
                   for i in graded if graded[i] and i in last}
            known = [x for x in rec.values() if x is not None]
            verbatim = {i for i, x in rec.items() if x is not None and x >= VERBATIM}
            fn2 = {i for i in verbatim if float(CEILING[i]["false_negative"] or 0) >= 2}
            print(f"{label} / {short} | {len(f)} | {len(graded)} | {sum(graded.values())} | "
                  f"{sum(bool(v['not_counted']) for v in f.values())} | {sum(v['first_flagged'] for v in f.values())}/"
                  f"{sum(v['last_flagged'] for v in f.values())} | {sum(bool(v['first_resolved']) for v in first_ok)} of "
                  f"{len(first_ok)} | {cost:.3f} | {turns:.1f} | {secs:.0f} | "
                  f"{sum(known) / max(len(known), 1):.2f} | {len(verbatim)} | {sum(graded.values()) - len(fn2)}")
    print()
    for label, run in RUNS:
        if (run, "none") in resolved and (run, "verinoda_guided") in resolved:
            print(f"{label}, guided - plain: {paired(resolved[(run, 'none')], resolved[(run, 'verinoda_guided')])}")
    for label, run in RUNS[2:4]:
        for arm, short in ARMS.items():
            if (run, arm) in resolved and ("c1-s1", arm) in resolved:
                print(f"{label} - C1 Sonnet, {short}: {paired(resolved[('c1-s1', arm)], resolved[(run, arm)])}")
    for arm, short in ARMS.items():
        if ("c4-opus", arm) in resolved and ("c4-fable", arm) in resolved:
            print(f"C4 Fable - C4 Opus, {short}: {paired(resolved[('c4-opus', arm)], resolved[('c4-fable', arm)])}")
    # amendment 9: C4's rule is reported and chooses nothing; Fable's guided arm has 38 lanes (the usage limit)
    fable = {(i, a) for a in ARMS for i in final("c4-fable", a)}
    plain = {(i, "none") for i in final("c4-opus", "none")}
    both = {(i, a) for i, a in fable if i in resolved.get(("c4-opus", a), {}) and i in resolved.get(("c4-fable", a), {})}

    def count(run: str, lanes: set[tuple[str, str]]) -> int:
        return sum(resolved.get((run, a), {}).get(i, False) for i, a in lanes)
    print(f"C4's rule (amendment 9: reported, chooses nothing): plain arms, Opus {count('c4-opus', plain)} of {len(plain)}, "
          f"Fable {count('c4-fable', fable & {(i, 'none') for i, _ in fable})} of "
          f"{len({i for i, a in fable if a == 'none'})}; over Fable's {len(fable)} lanes: Opus {count('c4-opus', fable)}, "
          f"Fable {count('c4-fable', fable)}; over the {len(both)} of them graded for both: Opus {count('c4-opus', both)}, "
          f"Fable {count('c4-fable', both)}")
    closed_book(data)


def closed_book(data: dict[str, dict]) -> None:
    """Amendment 7's probe: recall per model with no file and no tool, paired over the instances every model answered,
    beside the same model's sessions with the repository (plain arm; the last session counts)."""
    import re

    from swebench_recall import added_lines
    probe = Path("C:/Users/ozcin/swebench-run/closedbook")
    agentic = {"claude-sonnet-5-5": "c1-s1", "claude-opus-5-5": "c4-opus", "claude-fable-5-1": "c4-fable"}
    got = {}
    for model in agentic:
        f = probe / model / "results.jsonl"
        got[model] = {r["id"]: recall(r["patch"], data[r["id"]]["patch"], data[r["id"]]["problem_statement"])
                      for r in (json.loads(x) for x in (f.read_text(encoding="utf-8").splitlines() if f.exists() else [])
                                if x.strip())}
    ids = sorted(set.intersection(*(set(v) for v in got.values() if v)) if any(got.values()) else set())
    ids = [i for i in ids if all(got[m].get(i) is not None for m in got if got[m])]
    if not ids:
        return

    def size(i: str) -> int:
        given = re.sub(r"\s+", "", data[i]["problem_statement"])
        return len([t for t in added_lines(data[i]["patch"]) if t not in given])

    print(f"\nclosed-book probe, {len(ids)} instances answered by every model run so far "
          f"({', '.join(m for m in got if got[m])}):")
    for model, run in agentic.items():
        if not got[model]:
            continue
        last = last_rows(run, "none")
        mine = {i: recall(last[i].get("patch") or "", data[i]["patch"], data[i]["problem_statement"])
                for i in ids if i in last}
        for lo, hi in ((1, 4), (5, 9), (10, 10 ** 6), (1, 10 ** 6)):
            part = [i for i in ids if lo <= size(i) <= hi]
            cb = [got[model][i] for i in part]
            ag = [mine[i] for i in part if mine.get(i) is not None]
            band = "all" if (lo, hi) == (1, 10 ** 6) else f"{lo}-{hi if hi < 10 ** 6 else ''} lines"
            print(f"  {model:18} {band:10} n {len(part):3}: closed-book mean {sum(cb) / max(len(cb), 1):.2f}, verbatim "
                  f"{sum(x >= VERBATIM for x in cb):2} | with the repository ({run}, plain) mean "
                  f"{sum(ag) / max(len(ag), 1):.2f}, verbatim {sum(x >= VERBATIM for x in ag):2} (n {len(ag)})")


if __name__ == "__main__":
    main()
