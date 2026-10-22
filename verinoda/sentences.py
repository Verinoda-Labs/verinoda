"""The sentences that answer a question, each once with its file and line (D180).

``query --sentences`` (MCP ``project_query`` with ``format="sentences"``). A plain query returns passages:
a symbol's lines, a data file's rows, at most three prose passages, each with the lines around its hits.
On a corpus of prose (a knowledge base, notes, a book) the reader wants the sentence that says it. Here
the question is ranked the usual way (``search_index.rank``, filters included), the prose files of the
ranked units are read in their rank order (at most :data:`FILES_READ`), split into sentences, and a
sentence is kept when it holds enough of the question's own words (:func:`_needed`); a word is held when
the sentence holds one of its tokens or a variant the query expanded it to (a Turkish suffix: "dokudan"
is held by "dokuları"). They are ranked by the number of words held, the weight of the terms, then by
the rank of their file and their place in it. Headings are not sentences. A sentence that occurs in
several places is listed once, with the other places.

Only prose files are read (:data:`verinoda.retrieval.PROSE_SUFFIXES`: Markdown, text, reStructuredText,
AsciiDoc and the text view of PDF and Office documents); code and data files among the ranked units are
counted, not read. A sentence is a lead, as a query's passages are: it is the line that holds the words,
not a check that it says what the question asks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from verinoda.paths import contained_path

FILES_READ = 20            # ranked prose files read, in rank order
MAX_SENTENCE_CHARS = 400   # longer sentences are cut and marked
MAX_FILE_BYTES = 2_000_000
DEFAULT_ITEMS = 10

_FENCE = re.compile(r"^\s{0,3}(```|~~~)")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s")
_ITEM = re.compile(r"^\s*(?:[-*+]|\d{1,3}[.)])\s+")
_TABLE = re.compile(r"^\s*\|")
_RULE = re.compile(r"^\s{0,3}(?:[-*_]\s*){3,}$")
# the end of a sentence: . ! ? or an ellipsis, closing quotes or brackets (kept with it), then a space before the
# next one, which does not start in lower case ("9. sınıf", "e.g. somatic" go on)
_END = re.compile(r"(?<=[.!?…])([\"'”’)\]]*)\s+(?=\S)")
# "e.g. x", "vs. x", "Dr. x", "No. 5": a short word or a lone letter before the point does not end a sentence
_ABBREV = re.compile(r"(?:^|\s)(?:[A-Za-zÇĞİÖŞÜçğıöşü]|e\.g|i\.e|vs|etc|cf|Dr|Mr|Mrs|Ms|Prof|No|Fig|vb|örn|bkz|yy)\.$",
                     re.IGNORECASE)


@dataclass
class Sentence:
    text: str
    line: int       # 1-based, where it starts
    end_line: int   # where it ends


def _blocks(lines: list[str]) -> list[list[tuple[int, str]]]:
    """Runs of lines that read as one paragraph: a heading, a list item, a table row and a blank line each end
    one; fenced code is left out."""
    out: list[list[tuple[int, str]]] = []
    cur: list[tuple[int, str]] = []
    fence = None
    for n, raw in enumerate(lines, 1):
        m = _FENCE.match(raw)
        if fence is not None:
            if m and m.group(1) == fence:
                fence = None
            continue
        if m:
            fence = m.group(1)
            if cur:
                out.append(cur)
                cur = []
            continue
        s = raw.strip()
        if not s or _RULE.match(raw):
            if cur:
                out.append(cur)
                cur = []
            continue
        if _HEADING.match(raw) or _TABLE.match(raw):
            if cur:
                out.append(cur)
                cur = []
            out.append([(n, s)])
            continue
        if _ITEM.match(raw) and cur:
            out.append(cur)
            cur = []
        cur.append((n, s))
    if cur:
        out.append(cur)
    return out


def split(lines: list[str]) -> list[Sentence]:
    """The sentences of a text, each with the lines it starts and ends on."""
    out: list[Sentence] = []
    for block in _blocks(lines):
        text, starts = "", []   # starts: (offset in text, line)
        for n, s in block:
            if text:
                text += " "
            starts.append((len(text), n))
            text += s

        def line_at(off: int, starts: list[tuple[int, int]] = starts) -> int:
            ln = starts[0][1]
            for o, n in starts:
                if o > off:
                    break
                ln = n
            return ln

        begin = 0
        for m in _END.finditer(text):
            head = text[begin:m.start() + len(m.group(1))].rstrip()
            if text[m.end()].islower() or _ABBREV.search(head[-8:] if len(head) > 8 else head):
                continue
            if head:
                out.append(Sentence(head, line_at(begin), line_at(max(begin, m.start() - 1))))
            begin = m.end()
        tail = text[begin:].strip()
        if tail:
            out.append(Sentence(tail, line_at(begin), line_at(len(text) - 1)))
    return out


def _needed(n_words: int) -> int:
    """How many of the question's own words a sentence must hold: all of one or two, two of three or more."""
    return max(1, min(2, n_words))


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().casefold()


def find(g, question: str, *, max_items: int = DEFAULT_ITEMS, filters: bool = True, handle=None) -> dict:
    """``{"question", "terms", "sentences": [{"file", "line", "end_line", "text", "terms", "score",
    "also_at"?}], "more", "files_read", "files_not_prose", "needed"}``; ``filters``: the query syntax
    (:mod:`verinoda.query_filters`)."""
    from verinoda import query_filters, search_index
    from verinoda.retrieval import PROSE_SUFFIXES
    from verinoda.textnorm import fold_tr

    fl = query_filters.parse(question) if filters else None
    ranked_text = fl.text if fl is not None else question
    rk = search_index.rank(g, ranked_text, limit=200, handle=handle,
                           where=query_filters.Selector(fl, g.root) if fl is not None else None)
    q = rk.query
    # each content word of the question: its own tokens and the variants the query expanded it to
    groups = [(w, set(search_index.tokens(w)) | {e["to"] for e in q.expansions if e.get("from") == w})
              for w in dict.fromkeys(q.words)]
    groups = [(w, grp) for w, grp in groups if grp]
    words = [fold_tr(w) for w, _ in groups]
    needed = _needed(len(groups))
    files: list[str] = []
    not_prose: list[str] = []
    for h in rk.hits:
        if h.file in files or h.file in not_prose:
            continue
        (files if h.file.lower().endswith(PROSE_SUFFIXES) else not_prose).append(h.file)
    read = files[:FILES_READ]
    found: dict[str, dict] = {}
    order: list[str] = []
    for rank_no, f in enumerate(read):
        p = contained_path(Path(g.root), f)
        if p is None:
            continue
        try:
            if p.stat().st_size > MAX_FILE_BYTES and not f.lower().endswith((".pdf", ".docx", ".xlsx", ".pptx")):
                continue
        except OSError:
            continue
        lines = search_index._read_lines(p)
        if not lines:
            continue
        for s in split(lines):
            if _HEADING.match(s.text):
                continue
            toks = set(search_index.tokens(s.text))
            hit_own = [w for w, grp in groups if toks & grp]
            if len(hit_own) < needed:
                continue
            score = sum(w for t, w in q.weights.items() if t in toks)
            key = _norm(s.text)
            if key in found:
                found[key].setdefault("also_at", []).append(f"{f}:{s.line}")
                continue
            text = s.text if len(s.text) <= MAX_SENTENCE_CHARS else s.text[:MAX_SENTENCE_CHARS - 1] + "…"
            found[key] = {"file": f, "line": s.line, "end_line": s.end_line, "text": text,
                          "terms": sorted(t for t in q.weights if t in toks), "score": round(score, 3),
                          "_rank": (-len(hit_own), -score, rank_no, s.line)}
            order.append(key)
    ranked = sorted((found[k] for k in order), key=lambda r: r["_rank"])
    for r in ranked:
        del r["_rank"]
    return {"question": question, "terms": words, "needed": needed, "sentences": ranked[:max_items],
            "more": max(0, len(ranked) - max_items), "files_read": len(read),
            "files_ranked": len(files), "files_not_prose": len(not_prose),
            **({"filters": fl.describe()} if fl is not None else {})}


def render(res: dict, *, max_chars: int = 6000) -> str:
    """Plain text: one line per sentence, ``file:line  text``; what was read and what was left out last."""
    out = [f"sentences holding {res['needed']} or more of: {', '.join(res['terms']) or '(no words)'}"]
    used = len(out[0])
    shown = 0
    for r in res["sentences"]:
        where = f"{r['file']}:{r['line']}" + (f"-{r['end_line']}" if r["end_line"] != r["line"] else "")
        line = f"{where}  {r['text']}"
        if r.get("also_at"):
            line += f"  (also at {', '.join(r['also_at'][:3])}" + (", ..." if len(r["also_at"]) > 3 else "") + ")"
        if used + len(line) + 1 > max_chars and shown:
            break
        out.append(line)
        used += len(line) + 1
        shown += 1
    left = len(res["sentences"]) - shown + res["more"]
    if not res["sentences"]:
        out.append("no sentence holds enough of the question's words in the prose files read")
    if left:
        out.append(f"(+{left} more: --max-items, or narrow the question)")
    tail = f"read {res['files_read']} of {res['files_ranked']} ranked prose file(s)"
    if res["files_not_prose"]:
        tail += f"; {res['files_not_prose']} code or data file(s) ranked, not read (sentences come from prose)"
    out.append(tail)
    return "\n".join(out)
