"""Time, size and evidence recall of three ways a product can answer, on a corpus made by gen.py.

  stdlib     stdlib_answer.py: word overlap over sentences, no index (a stand-in for a standard-library product)
  sentences  Verinoda `query --sentences` (option C with D180)
  passages   Verinoda `query` (option C with the plain query)

Cold: a new process per question (what a command-line product pays each time). Warm: one process, index loaded
once (what a long-running product pays per question). Recall: the share of a question's planted prerequisite
sentences that appear in the answer's text. Tokens: characters / 4, an estimate, not a tokenizer.

Usage: python measure.py CORPUS_DIR [--quick]
"""

import json
import re
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
PY = sys.executable


def run(cmd: list[str]) -> tuple[float, str, str, int]:
    t0 = time.perf_counter()
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return time.perf_counter() - t0, p.stdout, p.stderr, p.returncode


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def dir_mb(p: Path) -> float:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 2**20


def med(xs):
    return round(statistics.median(xs), 3) if xs else None


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(sys.argv[1])
    quick = "--quick" in sys.argv
    kb = root / "kb"
    gold = json.loads((root / "gold.json").read_text(encoding="utf-8"))
    if quick:
        gold = gold[:8]
    out: dict = {"corpus": str(root), "files": len(list(kb.rglob("*.md"))), "questions": len(gold)}

    # -- the index: built once, refreshed when the corpus changes ------------------------------------------
    shutil.rmtree(kb / ".verinoda", ignore_errors=True)
    t, _, err, rc = run([PY, "-m", "verinoda", "setup", str(kb), "--agents", "none"])
    assert rc == 0, err[-2000:]
    out["index_first_build_s"] = round(t, 2)
    out["index_mb"] = round(dir_mb(kb / ".verinoda"), 2)
    out["corpus_mb"] = round(sum(f.stat().st_size for f in kb.rglob("*.md")) / 2**20, 3)
    t, *_ = run([PY, "-m", "verinoda", "update", str(kb)])
    out["update_nothing_changed_s"] = round(t, 2)
    edited = sorted((kb / "konular").glob("*.md"))[0]
    before = edited.read_text(encoding="utf-8")
    edited.write_text(before + "\nBu konu tekrar edilecektir.\n", encoding="utf-8", newline="\n")
    t, *_ = run([PY, "-m", "verinoda", "update", str(kb)])
    out["update_one_file_edited_s"] = round(t, 2)
    edited.write_text(before, encoding="utf-8", newline="\n")
    run([PY, "-m", "verinoda", "update", str(kb)])

    # -- start-up: what every new process pays before it reads anything -----------------------------------
    def startup(code: str, n: int = 7) -> float:
        return med([run([PY, "-c", code])[0] for _ in range(n)])

    out["startup_s"] = {
        "python_only": startup("pass"),
        "stdlib_imports": startup("import json, re, sqlite3, pathlib"),
        "verinoda_imports": startup("import verinoda.index, verinoda.retrieval, verinoda.sentences, "
                                    "verinoda.search_index"),
    }

    # -- per question: cold processes ------------------------------------------------------------------------
    methods = {
        "stdlib": lambda q: [PY, str(HERE / "stdlib_answer.py"), str(kb), q],
        "sentences": lambda q: [PY, "-m", "verinoda", "query", q, "--repo", str(kb), "--sentences", "--read-only"],
        "passages": lambda q: [PY, "-m", "verinoda", "query", q, "--repo", str(kb), "--read-only"],
    }
    per: dict[str, dict] = {m: {"cold_s": [], "chars": [], "recall": [], "complete": 0, "density": [],
                                "precision": [], "rr": [], "top3": 0, "to_first": []} for m in methods}
    for item in gold:
        q, g = item["question"], [norm(s) for s in item["gold"]]
        for m, cmd in methods.items():
            t, text, err, rc = run(cmd(q))
            assert rc == 0, (m, q, err[-1500:])
            body = norm(text)
            found = [s for s in g if s in body]
            per[m]["cold_s"].append(t)
            per[m]["chars"].append(len(text))
            per[m]["recall"].append(len(found) / len(g))
            per[m]["complete"] += len(found) == len(g)
            per[m]["density"].append(sum(len(s) for s in found) / max(1, len(text)))
            # what a reader goes through before the first planted sentence ends (the whole answer when none is there)
            ends = [norm(text).find(s) + len(s) for s in found]
            per[m]["to_first"].append(min(ends) if ends else len(norm(text)))
            if m in ("stdlib", "sentences"):  # one sentence per line: the share of lines that are planted evidence
                lines = [ln for ln in text.splitlines() if re.match(r"^\S+\.md:\d+", ln)]
                hits = [i for i, ln in enumerate(lines, 1) if any(s in norm(ln) for s in g)]
                per[m]["precision"].append(len(hits) / len(lines) if lines else 0.0)
                per[m]["rr"].append(1 / hits[0] if hits else 0.0)
                per[m]["top3"] += bool(hits) and hits[0] <= 3

    # -- warm: one process, index loaded once ----------------------------------------------------------------
    sys.path.insert(0, str(HERE))
    import stdlib_answer  # noqa: E402

    from verinoda import index, readonly, retrieval, sentences  # noqa: E402

    with readonly.scope(True):
        t0 = time.perf_counter()
        g = index.load(kb)
        load_s = time.perf_counter() - t0
        warm = {"sentences": [], "passages": [], "stdlib": []}
        sentences.find(g, gold[0]["question"])  # the search index handle is opened once
        for item in gold:
            q = item["question"]
            t0 = time.perf_counter()
            sentences.render(sentences.find(g, q))
            warm["sentences"].append(time.perf_counter() - t0)
            t0 = time.perf_counter()
            res = retrieval.retrieve(g, q, retrieval.Budget(max_items=10, max_chars=6000), filters=True)
            retrieval.render_text(res, budget_chars=6000)
            warm["passages"].append(time.perf_counter() - t0)
    t0 = time.perf_counter()
    corpus = stdlib_answer.load(kb)
    stdlib_load_s = time.perf_counter() - t0
    for item in gold:
        t0 = time.perf_counter()
        stdlib_answer.answer(corpus, item["question"])
        warm["stdlib"].append(time.perf_counter() - t0)
    out["warm_load_s"] = {"verinoda_graph": round(load_s, 3), "stdlib_sentences": round(stdlib_load_s, 4)}

    # -- memory of one cold call -----------------------------------------------------------------------------
    q0 = gold[0]["question"]
    mem = {}
    for name, cmd in {"stdlib": [PY, str(HERE / "stdlib_answer.py"), str(kb), q0, "--mem"],
                      "sentences": [PY, str(HERE / "vq.py"), str(kb), q0, "sentences"],
                      "passages": [PY, str(HERE / "vq.py"), str(kb), q0, "passages"]}.items():
        _, _, err, _ = run(cmd)
        m = re.search(r"PEAK_MB ([\d.]+)", err)
        mem[name] = float(m.group(1)) if m else None
    out["peak_memory_mb"] = mem

    out["methods"] = {}
    for m, r in per.items():
        out["methods"][m] = {
            "cold_s_median": med(r["cold_s"]), "warm_ms_median": round(1000 * statistics.median(warm[m]), 2),
            "chars_median": med(r["chars"]), "tokens_est_median": round(statistics.median(r["chars"]) / 4),
            "evidence_recall": round(statistics.mean(r["recall"]), 3),
            "complete_answers": f"{r['complete']}/{len(gold)}",
            "evidence_density": round(statistics.mean(r["density"]), 3),
            "chars_to_first_evidence_median": med(r["to_first"]),
            **({"line_precision": round(statistics.mean(r["precision"]), 3),
                "mrr": round(statistics.mean(r["rr"]), 3), "first_evidence_in_top3": f"{r['top3']}/{len(gold)}"}
               if r["precision"] else {}),
        }
    (root / "results.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
