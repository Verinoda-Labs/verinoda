"""One cold product call that depends on Verinoda (option C): import it, load the index, answer, report peak memory.

Usage: python vq.py KB_DIR "question" [sentences|passages]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from stdlib_answer import peak_mb  # noqa: E402


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    kb, question = Path(sys.argv[1]), sys.argv[2]
    mode = sys.argv[3] if len(sys.argv) > 3 else "sentences"
    from verinoda import index, readonly, retrieval, sentences

    with readonly.scope(True):
        g = index.load(kb)
        if mode == "sentences":
            print(sentences.render(sentences.find(g, question)))
        else:
            res = retrieval.retrieve(g, question, retrieval.Budget(max_items=10, max_chars=6000), filters=True)
            print(retrieval.render_text(res, budget_chars=6000))
    print(f"PEAK_MB {peak_mb():.1f}", file=sys.stderr)


if __name__ == "__main__":
    main()
