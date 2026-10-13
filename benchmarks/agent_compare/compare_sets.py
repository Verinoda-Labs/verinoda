"""Compare two runs of the eight public sets fact by fact: python compare_sets.py BEFORE_DIR AFTER_DIR

Prints, per approach (verinoda_retrieve_text, verinoda_analyze): facts found before -> after over all questions, the
questions that lost or gained a fact (set, id, fact ids), and the per-set mean tokens per question before -> after.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SETS = ["orders_app", "orders_app_tr", "glow_mod", "forge_mod", "graphify_core", "graphify_core_tr",
        "heldout_repoatlas", "verinoda_user_tr"]
APPROACHES = ["verinoda_retrieve_text", "verinoda_analyze"]


def questions(path: Path) -> dict[str, dict]:
    d = json.loads(path.read_text(encoding="utf-8"))
    rows = d.get("questions")
    if not rows:
        raise SystemExit(f"{path}: no 'questions' list (schema 3 result expected)")
    return {q["id"]: q for q in rows}


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    before, after = Path(sys.argv[1]), Path(sys.argv[2])
    for ap in APPROACHES:
        tot_b = tot_a = n_facts = 0
        lost: list[str] = []
        gained: list[str] = []
        tokens: list[str] = []
        for s in SETS:
            qb, qa = questions(before / f"{s}.json"), questions(after / f"{s}.json")
            if set(qb) != set(qa):   # the two runs must have asked the same questions
                raise SystemExit(f"{s}: question ids differ: {sorted(set(qb) ^ set(qa))}")
            tb = ta = 0
            for qid, q in qb.items():
                fb = q["approaches"][ap]["score"]
                fa = qa[qid]["approaches"][ap]["score"]
                if fb["facts"]["total"] != fa["facts"]["total"]:   # a changed gold would make the totals lie
                    raise SystemExit(f"{s}/{qid}: facts.total differs ({fb['facts']['total']} vs {fa['facts']['total']})")
                n_facts += fb["facts"]["total"]
                tot_b += fb["facts"]["found_n"]
                tot_a += fa["facts"]["found_n"]
                sb, sa = set(fb["facts"]["found"]), set(fa["facts"]["found"])
                if sb - sa:
                    lost.append(f"{s}/{qid}: {sorted(sb - sa)}")
                if sa - sb:
                    gained.append(f"{s}/{qid}: {sorted(sa - sb)}")
                tb += fb["tokens"]
                ta += fa["tokens"]
            n = max(1, len(qb))
            tokens.append(f"{s}: {tb / n:,.0f} -> {ta / n:,.0f}")
        print(f"== {ap}: facts found {tot_b}/{n_facts} -> {tot_a}/{n_facts}")
        print("   lost:", lost or "none")
        print("   gained:", gained or "none")
        print("   mean tokens per question:", "; ".join(tokens))
    return 0


if __name__ == "__main__":
    sys.exit(main())
