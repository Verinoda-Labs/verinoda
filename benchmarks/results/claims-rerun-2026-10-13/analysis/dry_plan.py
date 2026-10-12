"""Dry check of what the two harness commands would run now, without running them.

    python dry_plan.py WORK_DIR

Builds the ``done`` set from WORK/results.jsonl exactly as claims_run.main() does, applies each command's flags with
claims_run.apply_flags and asks claims_run.plan for the items still to run. Starts no session and clones nothing: it reads
results.jsonl, the config and git's state of the clones and of the existing working copies, and writes only analysis/dry-plan.json.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(r"C:\Users\ozcin\Desktop\verinoda-symbiosis")
sys.path.insert(0, str(REPO / "benchmarks" / "agent_compare"))

import claims_run as cr  # noqa: E402
from claims_tasks import REPO_ROOT, TAG_OF, load_tasks, order  # noqa: E402

SIX = ("fastapi__full-stack-fastapi-template-why-1,junegunn__fzf-why-1,guzzle__guzzle-trap-1,gin-gonic__gin-trap-1,"
       "axios__axios-when-1,sharkdp__bat-when-1")


def dirsize(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.is_dir() else 0


def main() -> int:
    work = Path(sys.argv[1])
    base = json.loads((work / "config.json").read_text(encoding="utf-8"))
    tasks = load_tasks(REPO_ROOT / "benchmarks" / "agent_compare" / "claims_tasks.json")
    by_id = {t["id"]: t for t in tasks}
    ids = order(list(by_id))
    twenty_four = ",".join([i for i in ids if by_id[i]["kind"] != "trap"][:24])
    cmd1 = ["--arms", "verinoda_guided", "--repeats", "3", "--tasks", SIX]
    cmd2 = ["--arms", "none,verinoda_guided", "--repeats", "1", "--tasks", twenty_four]
    out = work / "results.jsonl"
    done = set()
    if out.exists():  # the line of claims_run.main()
        done = {(r["id"], r["arm"], r["repeat"]) for r in map(json.loads, out.read_text(encoding="utf-8").splitlines()) if r}
    print(f"results.jsonl: {len(done)} rows done, by arm {dict(Counter(a for _, a, _ in done))}")
    res: dict = {"done": len(done)}

    def todo_for(argv: list[str], done_set: set) -> list:
        cfg = cr.apply_flags(json.loads(json.dumps(base)), argv)
        return cr.plan(tasks, cfg, done_set)

    t1 = todo_for(cmd1, done)
    print(f"command 1 (the six tasks, Verinoda arm, 3 repeats): {len(t1)} sessions to run ({len(done)} done), by arm "
          f"{dict(Counter(a for _, a, _ in t1))}")
    t2_alone = todo_for(cmd2, done)
    print(f"command 2 (24 tasks, both arms, 1 repeat) on its own: {len(t2_alone)} to run, by arm {dict(Counter(a for _, a, _ in t2_alone))}")
    done_after1 = done | {(t["id"], a, r) for t, a, r in t1}
    t2 = todo_for(cmd2, done_after1)
    print(f"command 2 after command 1: {len(t2)} to run ({len(done_after1)} done), by arm {dict(Counter(a for _, a, _ in t2))}")
    keys1 = {(t["id"], a, r) for t, a, r in t1}
    keys2 = {(t["id"], a, r) for t, a, r in t2}
    moved = {(r["id"], r["arm"], r["repeat"]) for r in map(json.loads, (work / "superseded-zero-call" / "results-verinoda-zero-call.jsonl")
                                                          .read_text(encoding="utf-8").splitlines()) if r}
    print(f"command 1 and command 2 (after 1) overlap: {len(keys1 & keys2)}; their union: {len(keys1 | keys2)}; "
          f"the moved Verinoda rows: {len(moved)}; union == moved set: {(keys1 | keys2) == moved}")
    print(f"the order the other way round (2, then 1): {len(t2_alone)} + {len(todo_for(cmd1, done | {(t['id'], a, r) for t, a, r in t2_alone}))}")
    res["command1"], res["command2_alone"], res["command2_after_1"] = len(t1), len(t2_alone), len(t2)
    res["union_equals_moved_rows"] = (keys1 | keys2) == moved
    # what main() does before the first session: clone_full per (repo, sha) in the todo; a clean full clone returns at once
    need = sorted({(t["repo"], t["sha"]) for t, _, _ in t1 + t2})
    clean = {repo: cr._clean_at(work / "clones" / repo.replace("/", "__"), sha) for repo, sha in need}
    print(f"clones needed: {len(need)}, clean at the pinned sha (no network clone): {sum(clean.values())}")
    # what one() does per session: copy_for returns at once when the copy is clean at the sha; the old index stays in it
    state = Counter()
    sizes = []
    for t, a, r in t1 + t2:
        c = cr.copy_dir(work, t, a, r)
        if not c.exists():
            state["no copy yet"] += 1
        elif cr._clean_at(c, t["sha"]):
            state["copy exists, clean at the sha: reused as it is"] += 1
            sizes.append((dirsize(c / ".verinoda"), dirsize(c)))
        else:
            state["copy exists, not clean: recreated"] += 1
        state["has .verinoda/"] += (c / ".verinoda").is_dir()
        state["has .mcp.json"] += (c / ".mcp.json").is_file()
        state["has .claude/"] += (c / ".claude").is_dir()
    print("working copies of the sessions to run:", dict(state))
    if sizes:
        print(f"  .verinoda/ per reused copy: {min(s for s, _ in sizes) / 1e6:.1f} to {max(s for s, _ in sizes) / 1e6:.1f} MB; "
              f"whole copy {min(c for _, c in sizes) / 1e6:.1f} to {max(c for _, c in sizes) / 1e6:.1f} MB; "
              f"total {sum(c for _, c in sizes) / 1e6:.0f} MB")
    # the usage log of a session: derived from (task, arm, repeat); the logger appends
    usage = work / "usage"
    names = {f"{t['id']}-{a}-r{r}.jsonl" for t, a, r in t1 + t2 if a == cr.GUIDED}
    present = {p.name for p in usage.glob("*.jsonl")} if usage.is_dir() else set()
    print(f"usage logs the sessions to run would write to: {len(names)}; of them already present (would be appended to): "
          f"{len(names & present)}; files in usage/: {len(present)}; files in usage/ no row of results.jsonl names: "
          f"{len(present - {f'{i}-{a}-r{r}.jsonl' for i, a, r in done})}")
    res["usage_present_and_reused_name"] = len(names & present)
    (work / "analysis" / "dry-plan.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
