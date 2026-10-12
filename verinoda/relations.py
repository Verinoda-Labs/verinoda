"""Relations between the topics of a prose corpus, read from cue words (D181).

``verinoda relations [TOPIC]``: the topic names come from a topics file (``--topics FILE`` or ``corpus.topics`` in
``.verinoda/config.json``; :func:`load_topics` says which shapes it reads). Every prose file of the project is read
(not ranked: a file that names a topic only through an alias still counts), split into sentences
(:func:`verinoda.sentences.split`), and the topics each sentence names are found with their grammatical role:
a Turkish name is matched with nominal endings only (plural, third-person possessive, case, ``-ki``, copula; a
final p/t/k softened), the longest name first, so "Organ" is not found in "Organeller" nor "Hücre" inside
"Hücre zarı"; when the name itself is bare, the case is read from the head noun after it ("Doku konusundan").

A sentence that names two topics is read by the first rule of :data:`RULES` that fires; every rule has a name,
and every relation carries the rule that read it, so a rule can be measured on its own. The kinds are
``prerequisite`` (one is learned before the other), ``support`` (one helps with the other) and ``shared`` (they
share concepts; no direction). A negation in the sentence flips an order rule and drops a requirement rule, and
lowers what is left to ``weak_inference``; so does a relation whose one end is the file's own topic ("bu konu",
or the subject Turkish leaves out), and two sentences that give one pair opposite orders (``conflict``).
Otherwise a relation is ``strong_inference``: the reading rests on cue words, and word cues never verify an
order or a direction (docs/DESIGN.md D31). The quoted sentence itself is at the line shown; that much anyone
can check.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from verinoda.paths import contained_path

MAX_FILES = 5000
STRONG, WEAK = "strong_inference", "weak_inference"
STATUS_RANK = {STRONG: 2, WEAK: 1, "unknown": 0}
KINDS = ("prerequisite", "support", "shared")
ACCEPTED = ("a JSON list of names; a JSON list of objects with name|title|label|id and optional "
            "aliases|names|synonyms; a JSON object with a 'topics' list; a JSON object mapping each name to its "
            "aliases; or a text file with one topic per line, aliases after '|' separated by commas")

# -- cue words (folded: Turkish letters to ASCII, lower case) ----------------------------------------------------
CUES = {
    "once": {"once", "oncesinde", "evvel"},
    "sonra": {"sonra", "sonrasinda", "ardindan"},
    "for": {"icin"},
    "understand": ("anlamak", "ogrenmek", "kavramak", "calismak", "bilmek"),
    # bare "temel" is mostly the adjective "basic" ("hücrenin temel kavramları"): only its noun forms count
    "prereq_noun": ("onkosul", "kosul", "temeli", "temelidir", "temelini", "temeldir", "temelinde", "sart",
                    "gerekli", "onsart"),
    "require_verb": ("gerektir", "dayan", "gerekir", "gerekmektedir"),
    "built_on": ("kurulur", "kuruludur", "insa"),
    "passage": ("gecil", "gecis", "ilerlen", "gecmek", "gecer"),
    "support": ("yardimci", "destekl", "kolaylastir", "katki", "help", "support", "aids"),
    "shared": ("ortak", "iliskili", "baglantili", "benzer", "share", "common", "related"),
    "en_before": {"before", "prior"},
    "en_after": {"after"},
    "en_requires": ("requir", "depend", "build", "built", "reli", "rely"),
    "en_prereq": ("prerequisite", "basis", "foundation", "underlie", "precede"),
    "en_follows": ("follow",),
}
_MEDEN = re.compile(r"(?<=\w\w)m[ae]d[ae]n$")            # öğrenmeden, bilmeden, anlamadan; not the noun "maden"
_NEG = re.compile(r"(?:m[ae]z|m[ae]m[ae]l[ie]|m[ae]m[ae]kt[ae]d[ie]r)$")
_NEG_WORDS = {"olmaz", "degil", "degildir", "not", "never", "cannot", "dont", "doesnt"}
_HEADS = ("konu", "unite", "bolum", "kavram", "baslik", "ders")
_THIS = {"bu", "this"}
_EN_HEADS = {"topic", "topics", "chapter", "unit"}
# a Turkish noun's own endings, in their order: plural, third-person possessive, case, -ki, copula
_NOMINAL = re.compile(r"^(?:lar|ler)?(?:lari|leri|si|su|i|u)?"
                      r"(?P<case>nden|ndan|nde|nda|nin|nun|den|dan|ten|tan|yle|yla|ile|de|da|te|ta|yi|yu|ni|nu|"
                      r"ye|ya|ne|na|in|un|le|la|i|u|e|a)?(?:ki)?(?:dir|dur|tir|tur)?$")
_EN_NOMINAL = re.compile(r"^(?:s|es)?$")
_TOKEN = re.compile(r"\w+(?:['’]\w+)?|[;:]")
# where a clause ends: a negation counts only in the clause of the relation it would turn
_BOUNDARY = {";", ":", "ama", "ancak", "fakat", "oysa", "but", "however", "whereas"}
_SOFT = {"p": "b", "t": "d", "k": "g"}


class TopicsError(ValueError):
    """The topics file is missing, outside the project or of a shape this does not read (the message says which)."""


@dataclass
class Topic:
    name: str
    forms: list[tuple[str, ...]]   # the name and each alias, as folded words


@dataclass
class Mention:
    topic: str
    start: int            # first token
    end: int              # the token after the mention (its head noun included)
    role: str             # source, target, owner, object, container, instrument, plain
    icin: bool = False    # followed by "için"
    implicit: bool = False


@dataclass
class Relation:
    earlier: Mention      # for support: the one that helps; for shared: either
    later: Mention
    kind: str
    rule: str
    negated: bool = False


@dataclass
class _Found:
    kind: str
    frm: str
    to: str
    evidence: list[dict] = field(default_factory=list)


def _fold(text: str) -> str:
    from verinoda.textnorm import fold_tr

    return fold_tr(text)


def _words(text: str) -> list[str]:
    return re.findall(r"\w+", _fold(text))


# -- the topics file ------------------------------------------------------------------------------------------------

def _aliases(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [a.strip() for a in v.split(",") if a.strip()]
    if isinstance(v, list) and all(isinstance(a, str) for a in v):
        return [a.strip() for a in v if a.strip()]
    raise TopicsError(f"aliases must be a string or a list of strings, not {type(v).__name__}")


def _from_obj(o: dict) -> tuple[str, list[str]]:
    name = next((o[k] for k in ("name", "title", "label", "id") if isinstance(o.get(k), str)), None)
    if not name:
        raise TopicsError(f"a topic object has no name|title|label|id: {json.dumps(o, ensure_ascii=False)[:120]}")
    return name, _aliases(next((o[k] for k in ("aliases", "names", "synonyms", "alias") if k in o), None))


def _from_json(data) -> list[tuple[str, list[str]]]:
    if isinstance(data, list):
        out = []
        for item in data:
            if isinstance(item, str):
                out.append((item, []))
            elif isinstance(item, dict):
                out.append(_from_obj(item))
            else:
                raise TopicsError(f"a topic is neither a name nor an object: {item!r}")
        return out
    if isinstance(data, dict):
        if "topics" in data:
            return _from_json(data["topics"])
        out = []
        for k, v in data.items():
            if not isinstance(k, str):
                raise TopicsError(f"not a shape this reads; accepted: {ACCEPTED}")
            if isinstance(v, dict):
                out.append((k, _aliases(next((v[a] for a in ("aliases", "names", "synonyms", "alias") if a in v),
                                             None))))
            else:
                out.append((k, _aliases(v)))
        return out
    raise TopicsError(f"not a shape this reads; accepted: {ACCEPTED}")


def parse_topics(text: str, suffix: str = "") -> list[Topic]:
    """The topics of a file's text (see :data:`ACCEPTED`)."""
    if suffix == ".json" or text.lstrip().startswith(("[", "{")):
        try:
            entries = _from_json(json.loads(text))
        except ValueError as exc:
            if isinstance(exc, TopicsError):
                raise
            raise TopicsError(f"not valid JSON ({exc}); accepted: {ACCEPTED}") from None
    else:
        entries = []
        for line in text.splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            name, _, rest = s.partition("|")
            entries.append((name.strip(), _aliases(rest)))
    topics: list[Topic] = []
    seen: set[str] = set()
    for name, aliases in entries:
        forms: list[tuple[str, ...]] = []
        for n in (name, *aliases):
            w = tuple(_words(n))
            if w and w not in forms:
                forms.append(w)
        if forms and name not in seen:
            topics.append(Topic(name, forms))
            seen.add(name)
    if not topics:
        raise TopicsError(f"the topics file names no topic; accepted: {ACCEPTED}")
    return topics


def topics_path(repo: Path, path: str | None = None) -> Path:
    """The topics file: ``path``, else ``corpus.topics`` of the project's config; it must lie inside the project."""
    from verinoda.paths import load_config

    repo = Path(repo).resolve()
    raw = path or ((load_config(repo).get("corpus") or {}).get("topics"))
    if not raw:
        raise TopicsError("no topics file: pass --topics FILE, or set corpus.topics in .verinoda/config.json "
                          f"(accepted: {ACCEPTED})")
    p = Path(str(raw))
    p = (p if p.is_absolute() else repo / p).resolve()
    try:
        p.relative_to(repo)
    except ValueError:
        raise TopicsError(f"{raw}: not inside the project {repo}") from None
    if not p.is_file():
        raise TopicsError(f"{raw}: no such file")
    return p


def load_topics(repo: Path, path: str | None = None) -> tuple[list[Topic], Path]:
    p = topics_path(repo, path)
    return parse_topics(p.read_text(encoding="utf-8-sig"), p.suffix.lower()), p


# -- finding the topics a sentence names ---------------------------------------------------------------------------

class _Matcher:
    """Topic names indexed for one pass over a sentence's tokens: several-word names by their first word, one-word
    names by the word and its softened stem."""

    def __init__(self, topics: list[Topic]):
        self.multi: dict[str, list[tuple[tuple[str, ...], str]]] = {}
        self.single: dict[str, list[tuple[str, str]]] = {}
        for t in topics:
            for f in t.forms:
                if len(f) > 1:
                    self.multi.setdefault(f[0], []).append((f, t.name))
                else:
                    for stem in _stems(f[0]):
                        self.single.setdefault(stem, []).append((f[0], t.name))
        for v in self.multi.values():
            v.sort(key=lambda x: (-len(x[0]), -len(" ".join(x[0]))))


def _stems(word: str) -> list[str]:
    out = [word]
    if len(word) > 2 and word[-1] in _SOFT:
        out.append(word[:-1] + _SOFT[word[-1]])
    return out


def _case_role(rest: str) -> str | None:
    """The role the endings ``rest`` give a noun, "plain" without a case, None when ``rest`` is not a noun's endings
    (Turkish ones, else an English plural)."""
    from verinoda.textnorm import TR_CASE_ROLES

    m = _NOMINAL.match(rest)
    if not m:
        return "plain" if _EN_NOMINAL.match(rest) else None
    case = m.group("case")
    return TR_CASE_ROLES.get(case, "plain") if case else "plain"


def _tokens(sentence: str) -> list[tuple[str, str | None]]:
    """Folded words; a word joined by an apostrophe ("DNA'nın") is the word with its endings apart. An English
    "n't" is the word "not"."""
    out = []
    for m in _TOKEN.finditer(_fold(sentence)):
        w = m.group(0)
        for ap in ("'", "’"):
            if ap in w:
                base, _, tail = w.partition(ap)
                if tail == "t" and base.endswith("n"):
                    out += [(base[:-1], None), ("not", None)]
                else:
                    out.append((base, tail))
                break
        else:
            out.append((w, None))
    return out


def _last_word(tok: tuple[str, str | None], word: str) -> str | None:
    """The role of ``tok`` as the name word ``word`` with its endings, or None."""
    w, tail = tok
    if tail is not None:
        return _case_role(tail) if w == word else None
    for stem in _stems(word):
        if w.startswith(stem):
            role = _case_role(w[len(stem):])
            if role is not None:
                return role
    return None


def _head_role(tok: tuple[str, str | None]) -> str | None:
    w, tail = tok
    if w in _EN_HEADS:
        return "plain"
    for h in _HEADS:
        if w.startswith(h):
            role = _case_role(tail if tail is not None else w[len(h):])
            if role is not None:
                return role
    return None


def mentions(sentence: str, matcher: _Matcher, file_topic: str | None = None) -> tuple[list[Mention], list[str]]:
    """The topics ``sentence`` names, in order, and its folded words. "bu konu" / "this topic" (and the like) is a
    mention of ``file_topic``, marked implicit."""
    toks = _tokens(sentence)
    words = [w for w, _ in toks]
    out: list[Mention] = []
    i, n = 0, len(toks)
    while i < n:
        found = None
        for form, name in matcher.multi.get(words[i], ()):
            k = len(form)
            if i + k <= n and all(words[i + j] == form[j] and toks[i + j][1] is None for j in range(k - 1)):
                role = _last_word(toks[i + k - 1], form[-1])
                if role is not None:
                    found = (name, k, role)
                    break
        if found is None:
            w = words[i]
            for cut in range(len(w), 1, -1):
                for word, name in matcher.single.get(w[:cut], ()):
                    role = _last_word(toks[i], word)
                    if role is not None:
                        found = (name, 1, role)
                        break
                if found:
                    break
        if found is None and file_topic and words[i] in _THIS and i + 1 < n:
            role = _head_role(toks[i + 1])
            if role is not None:
                out.append(Mention(file_topic, i, i + 2, role, implicit=True))
                i += 2
                continue
        if found is None:
            i += 1
            continue
        name, k, role = found
        end = i + k
        if role == "plain" and end < n:
            head = _head_role(toks[end])
            if head is not None:
                role, end = head, end + 1
        m = Mention(name, i, end, role)
        if end < n and words[end] == "icin":
            m.icin = True
        out.append(m)
        i = end
    return out, words


# -- the rules ------------------------------------------------------------------------------------------------------

def _starts(word: str, prefixes) -> bool:
    return word.startswith(tuple(prefixes))


def _negated(words: list[str]) -> bool:
    return any(w in _NEG_WORDS or (len(w) > 4 and _NEG.search(w)) for w in words)


def _clause(words: list[str], lo: int, hi: int) -> list[str]:
    """The words of the clause(s) holding positions ``lo``..``hi``: up to the boundaries around them."""
    a = lo
    while a > 0 and words[a - 1] not in _BOUNDARY:
        a -= 1
    b = max(hi, lo)
    while b < len(words) and words[b] not in _BOUNDARY:
        b += 1
    return words[a:b]


def _other(ms: list[Mention], m: Mention) -> Mention | None:
    rest = [x for x in ms if x is not m and x.topic != m.topic]
    return min(rest, key=lambda x: abs(x.start - m.start)) if rest else None


def _r_ablative(ms, words):
    for m in ms:
        if m.role != "source":
            continue
        near = words[m.end:m.end + 2]
        o = _other(ms, m)
        if o is None:
            continue
        if any(w in CUES["once"] for w in near):
            return Relation(o, m, "prerequisite", "tr-ablative-once")
        if any(w in CUES["sonra"] for w in near):
            return Relation(m, o, "prerequisite", "tr-ablative-sonra")
    return None


def _r_meden(ms, words):
    for p, w in enumerate(words):
        if not _MEDEN.search(w):
            continue
        before = [m for m in ms if m.end <= p]
        after = [m for m in ms if m.start > p]
        if not before:
            continue
        x = before[-1]
        y = after[0] if after else (before[-2] if len(before) > 1 else None)
        if y is None or y.topic == x.topic:
            continue
        if p + 1 < len(words) and words[p + 1] in CUES["once"]:
            return Relation(y, x, "prerequisite", "tr-meden-once")       # before learning x, y: y comes first
        if _negated(_clause(words, p + 1, p + 1)):
            return Relation(x, y, "prerequisite", "tr-meden-negated")    # without x, no y: x comes first
    return None


def _r_understand_for(ms, words):
    for p in range(len(words) - 1):
        if words[p + 1] in CUES["for"] and _starts(words[p], CUES["understand"]):
            before = [m for m in ms if m.end <= p]
            after = [m for m in ms if m.start > p + 1]
            if before and after and before[-1].topic != after[0].topic:
                return Relation(after[0], before[-1], "prerequisite", "tr-anlamak-icin")
    return None


def _r_prereq_noun(ms, words):
    if not any(_starts(w, CUES["prereq_noun"]) for w in words):
        return None
    later = next((m for m in ms if m.role == "owner" or m.icin), None)
    if later is None:
        return None
    earlier = next((m for m in ms if m is not later and m.role == "plain" and not m.icin and m.topic != later.topic),
                   None)
    return Relation(earlier, later, "prerequisite", "tr-onkosul") if earlier else None


def _r_require_verb(ms, words):
    p = next((i for i, w in enumerate(words) if _starts(w, CUES["require_verb"])
              or (_starts(w, CUES["built_on"]) and "uzerine" in words[:i])), None)
    if p is None:
        return None
    rule = ("tr-uzerine-kurulur" if _starts(words[p], CUES["built_on"]) else
            "tr-dayanir" if words[p].startswith("dayan") else "tr-gerektirir")
    icin = [m for m in ms if m.icin]
    if icin:
        later = icin[0]
        earlier = next((m for m in ms if m is not later and m.topic != later.topic), None)
    else:
        later = next((m for m in ms if m.role == "plain"), None)
        earlier = next((m for m in ms if m is not later and m.role in ("object", "owner", "target")
                        and (later is None or m.topic != later.topic)), None)
    if later is None or earlier is None:
        return None
    return Relation(earlier, later, "prerequisite", rule)


def _r_passage(ms, words):
    if not any(_starts(w, CUES["passage"]) for w in words):
        return None
    src = next((m for m in ms if m.role == "source"), None)
    tgt = next((m for m in ms if m.role == "target" and (src is None or m.topic != src.topic)), None)
    return Relation(src, tgt, "prerequisite", "tr-gecis") if src and tgt else None


def _r_enumeration(ms, words):
    p1 = next((i for i, w in enumerate(words) if w in CUES["once"]), None)
    p2 = next((i for i, w in enumerate(words) if w in CUES["sonra"] and p1 is not None and i > p1), None)
    if p1 is None or p2 is None:
        return None
    x = next((m for m in ms if p1 < m.start < p2), None)
    y = next((m for m in ms if m.start > p2), None)
    return Relation(x, y, "prerequisite", "tr-once-sonra") if x and y and x.topic != y.topic else None


def _r_en_order(ms, words):
    for cue, key, rule in (("before", "en_before", "en-before"), ("after", "en_after", "en-after")):
        p = next((i for i, w in enumerate(words) if w in CUES[key]), None)
        if p is None:
            continue
        before = [m for m in ms if m.end <= p]
        after = [m for m in ms if m.start > p]
        if before and after:
            a, b = before[-1], after[0]
        elif len(after) >= 2:                      # "Before B, A ..." / "After A, B ..."
            a, b = (after[1], after[0]) if cue == "before" else (after[0], after[1])
            return Relation(a, b, "prerequisite", rule + "-initial") if a.topic != b.topic else None
        else:
            continue
        if a.topic == b.topic:
            continue
        return Relation(a, b, "prerequisite", rule) if cue == "before" else Relation(b, a, "prerequisite", rule)
    return None


def _r_en_requires(ms, words):
    for p, w in enumerate(words):
        before = [m for m in ms if m.end <= p]
        after = [m for m in ms if m.start > p]
        if not before or not after or before[-1].topic == after[0].topic:
            continue
        if _starts(w, CUES["en_requires"]):
            if w.startswith("requir") and p + 1 < len(words) and words[p + 1] == "for":
                return Relation(before[-1], after[0], "prerequisite", "en-required-for")
            return Relation(after[0], before[-1], "prerequisite", "en-requires")
        if _starts(w, CUES["en_prereq"]):
            return Relation(before[-1], after[0], "prerequisite", "en-prerequisite")
        if _starts(w, CUES["en_follows"]):
            return Relation(after[0], before[-1], "prerequisite", "en-follows")
    return None


def _r_support(ms, words):
    if not any(_starts(w, CUES["support"]) for w in words) or len(ms) < 2:
        return None
    a = next((m for m in ms if m.role == "plain"), ms[0])
    b = next((m for m in ms if m is not a and m.topic != a.topic), None)
    return Relation(a, b, "support", "support") if b else None


def _r_shared(ms, words):
    if not any(_starts(w, CUES["shared"]) for w in words):
        return None
    a = ms[0]
    b = next((m for m in ms[1:] if m.topic != a.topic), None)
    return Relation(a, b, "shared", "shared") if b else None


# the order they are tried in: the more specific first; the first that fires reads the sentence
RULES = (_r_meden, _r_understand_for, _r_ablative, _r_prereq_noun, _r_require_verb, _r_passage, _r_enumeration,
         _r_en_order, _r_en_requires, _r_support, _r_shared)
ORDER_RULES = {"tr-ablative-once", "tr-ablative-sonra", "tr-meden-once", "tr-once-sonra", "tr-gecis", "en-before",
               "en-after", "en-before-initial", "en-after-initial", "en-follows"}


def read_sentence(sentence: str, matcher: _Matcher, file_topic: str | None = None) -> tuple[Relation | None, int]:
    """The relation a sentence states (None) and how many distinct topics it names."""
    ms, words = mentions(sentence, matcher, file_topic)
    named = {m.topic for m in ms}
    if len(ms) == 1 and file_topic and file_topic not in named:
        # Turkish leaves the subject out: the file's own topic is the other end ("Hücre konusundan sonra gelir.")
        ms.append(Mention(file_topic, len(words) + 1, len(words) + 1, "plain", implicit=True))
    if len({m.topic for m in ms}) < 2:
        return None, len(named)
    for rule in RULES:
        rel = rule(ms, words)
        if rel is None:
            continue
        # a negation turns the relation only in its own clause ("...öğrenilmelidir; Organ bilinmez" does not)
        at = [m for m in (rel.earlier, rel.later) if m.start < len(words)]
        scope = _clause(words, min(m.start for m in at), max(m.end for m in at)) if at else words
        if rel.rule != "tr-meden-negated" and _negated(scope):
            if rel.rule not in ORDER_RULES:
                return None, len(named)          # "B, A'yı gerektirmez": no requirement is stated
            rel = Relation(rel.later, rel.earlier, rel.kind, rel.rule, negated=True)
        if rel.rule == "tr-meden-negated":
            rel.negated = True
        return rel, len(named)
    return None, len(named)


def _file_topic(lines: list[str], rel: str, topics: list[Topic]) -> str | None:
    """The topic a file is about: its first heading, else its file name, matched to a topic's name or alias."""
    by_form = {f: t.name for t in topics for f in t.forms}
    for ln in lines[:20]:
        if ln.lstrip().startswith("#"):
            hit = by_form.get(tuple(_words(ln.lstrip("# \t"))))
            if hit:
                return hit
            break
    return by_form.get(tuple(_words(Path(rel).stem.replace("-", " ").replace("_", " "))))


def find(repo: Path, topic: str | None = None, *, topics_file: str | None = None, kind: str | None = None,
         max_items: int = 50, co_mentions: bool = False, rules: bool = True) -> dict:
    """``{"topics_file", "topics", "focus", "relations": [{"from", "to", "kind", "status", "sources", "conflict",
    "evidence": [{"file", "line", "end_line", "text", "rule", "implicit", "negated"}], "lowered_by"?}], "more",
    "files_read", "files_not_prose", "truncated", "co_mentions", "evidence_rules"?, "rule_errors"?}``. ``rules``: apply
    the user's evidence rules (:mod:`verinoda.evidence_rules`, D182), which can only lower a status."""
    from verinoda import evidence_rules, search_index, sentences
    from verinoda.paths import load_config
    from verinoda.retrieval import PROSE_SUFFIXES
    from verinoda.snapshot import list_files

    repo = Path(repo).resolve()
    topics, tpath = load_topics(repo, topics_file)
    focus = None
    if topic:
        want = tuple(_words(topic))
        focus = next((t.name for t in topics if want in t.forms), None)
        if focus is None:
            near = [t.name for t in topics if want and want[0] in t.forms[0]][:5]
            raise TopicsError(f"{topic!r} is not a topic of {tpath.name}" + (f" (close: {', '.join(near)})" if near
                                                                             else ""))
    matcher = _Matcher(topics)
    tp_rel = tpath.relative_to(repo).as_posix()
    files = [f for f in list_files(repo) if f != tp_rel]
    prose = [f for f in files if f.lower().endswith(PROSE_SUFFIXES)]
    truncated = len(prose) > MAX_FILES
    found: dict[tuple[str, str, str], _Found] = {}
    co = 0
    co_examples: list[dict] = []
    for f in prose[:MAX_FILES]:
        p = contained_path(repo, f)
        lines = search_index._read_lines(p) if p is not None else None
        if not lines:
            continue
        ftopic = _file_topic(lines, f, topics)
        for s in sentences.split(lines):
            if s.text.lstrip().startswith("#"):
                continue
            rel, named = read_sentence(s.text, matcher, ftopic)
            if rel is None:
                if named >= 2:
                    co += 1
                    if co_mentions and len(co_examples) < max_items:
                        co_examples.append({"file": f, "line": s.line, "text": s.text})
                continue
            a, b = rel.earlier.topic, rel.later.topic
            if rel.kind == "shared":
                a, b = sorted((a, b))
            key = (rel.kind, a, b)
            ev = {"file": f, "line": s.line, "end_line": s.end_line, "text": s.text, "rule": rel.rule,
                  "implicit": rel.earlier.implicit or rel.later.implicit, "negated": rel.negated}
            found.setdefault(key, _Found(rel.kind, a, b)).evidence.append(ev)
    rows = []
    for (k, a, b), fd in found.items():
        # two sentences that give one pair opposite orders: neither is taken at its word
        conflict = k == "prerequisite" and ("prerequisite", b, a) in found
        each = [WEAK if (e["implicit"] or e["negated"]) else STRONG for e in fd.evidence]
        status = WEAK if conflict else max(each, key=STATUS_RANK.get)
        rows.append({"from": a, "to": b, "kind": k, "status": status, "sources": len(fd.evidence),
                     "conflict": conflict, "evidence": fd.evidence})
    rule_list, rule_errors = evidence_rules.load(load_config(repo)) if rules else ([], [])
    evidence_rules.apply(rows, rule_list)   # D182: a product's own terms, applied only downwards
    if focus:
        rows = [r for r in rows if focus in (r["from"], r["to"])]
    if kind:
        rows = [r for r in rows if r["kind"] == kind]
    rows.sort(key=lambda r: (-STATUS_RANK[r["status"]], -r["sources"], KINDS.index(r["kind"]), r["from"], r["to"]))
    out = {"topics_file": tp_rel, "topics": len(topics), "focus": focus, "relations": rows[:max_items],
           "more": max(0, len(rows) - max_items), "files_read": min(len(prose), MAX_FILES),
           "files_not_prose": len(files) - len(prose), "truncated": truncated, "co_mentions": co}
    if co_mentions:
        out["co_mention_examples"] = co_examples
    if rule_list:
        out["evidence_rules"] = [r.name for r in rule_list]
    if rule_errors:
        out["rule_errors"] = rule_errors
    return out


def render(res: dict) -> str:
    head = f"relations{' for ' + res['focus'] if res['focus'] else ''} ({res['topics_file']}: {res['topics']} " \
           f"topics; {res['files_read']} prose file(s) read)"
    out = [head]
    for r in res["relations"]:
        arrow = "<->" if r["kind"] == "shared" else "->"
        ev = r["evidence"][0]
        where = f"{ev['file']}:{ev['line']}" + (f"-{ev['end_line']}" if ev["end_line"] != ev["line"] else "")
        notes = [ev["rule"]] + (["implicit"] if ev["implicit"] else []) + (["negated"] if ev["negated"] else []) \
            + (["conflict"] if r["conflict"] else []) + [f"lowered by {n}" for n in r.get("lowered_by") or []]
        out.append(f"{r['from']} {arrow} {r['to']}  {r['kind']}  {r['status']}  {where}  \"{ev['text']}\"  "
                   f"[{', '.join(notes)}]")
        if r["sources"] > 1:
            out.append(f"  + {r['sources'] - 1} more source(s): "
                       + ", ".join(f"{e['file']}:{e['line']}" for e in r["evidence"][1:4])
                       + (", ..." if r["sources"] > 4 else ""))
    if not res["relations"]:
        out.append("no relation read: no sentence names two topics with a cue this reads")
    if res["more"]:
        out.append(f"(+{res['more']} more: --max-items)")
    if res["co_mentions"]:
        out.append(f"{res['co_mentions']} sentence(s) name two topics without a cue this reads (co-mentions, not "
                   "relations" + ("" if "co_mention_examples" in res else "; --co-mentions lists them") + ")")
        for c in res.get("co_mention_examples") or []:
            out.append(f"  {c['file']}:{c['line']}  \"{c['text']}\"")
    if res["truncated"]:
        out.append(f"only the first {MAX_FILES} prose files were read")
    if res.get("evidence_rules"):
        out.append(f"evidence rules applied (they only lower): {', '.join(res['evidence_rules'])}")
    for e in res.get("rule_errors") or []:
        out.append(f"evidence rule not applied: {e}")
    out.append("read from cue words: strong_inference at most, weak_inference when one end is the file's own topic, "
               "the sentence is negated or two sentences disagree; the quoted sentence is at the line shown")
    return "\n".join(out)
