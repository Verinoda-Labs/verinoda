"""File cards (docs/DESIGN.md D189): what a file is, in one line, for a summary that should not keep its text.

A long Claude Code session reads its whole history again with every request, and its compaction is what makes it
small again; what the summary keeps of a file is the model's memory of it. A card says what the file is: its
repository path and length, what it is for (the first sentence of a module docstring, of the comment before its first
definition, or a Markdown title; a licence header is skipped), the top-level definitions its symbol facts name
(:mod:`verinoda.anchors`) and what it imports. It is read from the file on disk now: no index, no graph, no store, and
nothing is written. An image is its pixel size, a binary its byte count, a file that is gone is said to be gone.
``verinoda card`` prints the cards; the mod hands them to the compaction (its ``session.compact`` hook) for the files
the conversation read or edited, so the summary keeps one card per file and a later turn reads again what it needs.

A path is judged lexically before the file system is asked (:func:`verinoda.paths.escapes_lexically`: a UNC path is
never stat'ed, which alone would open the share), then contained (:func:`verinoda.paths.contained_path`: a link out of
the project is refused).
"""

from __future__ import annotations

import ast
import re
import struct
import sys
from pathlib import Path, PureWindowsPath

from verinoda import textnorm as tn
from verinoda.paths import contained_path, escapes_lexically

MAX_BYTES = 2_000_000   # a larger file is carded from its size alone
MAX_CHARS = 8000        # the text's default budget: whole cards, the rest counted
PURPOSE_CHARS = 140
DEFINES = 8
IMPORTS = 6
_HEAD_BYTES = 65_536    # what an image's size is read from

IMAGES = {".png", ".gif", ".jpg", ".jpeg", ".webp", ".bmp", ".ico"}
MARKDOWN = {".md", ".markdown"}
PYTHON = {".py", ".pyi"}
_SLASH = {".java", ".kt", ".kts", ".scala", ".groovy", ".gradle", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".c",
          ".h", ".cc", ".cpp", ".hpp", ".cs", ".go", ".rs", ".swift", ".php", ".dart", ".fsh", ".vsh", ".glsl", ".frag",
          ".vert", ".json5"}
_HASH = {".sh", ".bash", ".zsh", ".yml", ".yaml", ".toml", ".rb", ".pl", ".r", ".ps1", ".psm1", ".cfg", ".conf", ".ini",
         ".properties", ".mk", ".dockerfile", ".env"}
_DASH = {".sql", ".lua", ".hs"}
_JVM = {".java", ".kt", ".kts", ".scala", ".groovy"}
_JS = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}
_C = {".c", ".h", ".cc", ".cpp", ".hpp"}

_LICENCE = re.compile(r"(?i)\b(copyright|licen[cs]e[ds]?|spdx|all rights reserved)\b")
_JVM_IMPORT = re.compile(r"^[ \t]*import[ \t]+(static[ \t]+)?([\w.]+?)(\.\*)?[ \t]*(?:as[ \t]+\w+)?[ \t]*;?[ \t]*$",
                         re.MULTILINE)
_JS_IMPORT = re.compile(r"""\bimport\s+(?:[^'";]*?\sfrom\s+)?['"]([^'"\n]+)['"]|\brequire\(\s*['"]([^'"\n]+)['"]\s*\)""")
_C_INCLUDE = re.compile(r'^[ \t]*#[ \t]*include[ \t]*[<"]([^>"\n]+)[>"]', re.MULTILINE)
_CS_USING = re.compile(r"^[ \t]*using[ \t]+(?:static[ \t]+)?([\w.]+)[ \t]*;", re.MULTILINE)
_HEADING = re.compile(r"^[ \t]{0,3}#{1,6}[ \t]+(.+?)[ \t#]*$", re.MULTILINE)


# -- paths ---------------------------------------------------------------------------------------------------------

def _same(a: str, b: str) -> bool:
    return a.lower() == b.lower() if sys.platform == "win32" else a == b


def relative(repo: Path, path: str) -> str | None:
    """``path`` as a repository-relative POSIX path, judged without asking the file system; None when it names
    something outside ``repo`` (another drive or folder, a UNC share, a device path, ``..``, a stream suffix)."""
    p = str(path).strip().replace("\\", "/")
    if not p or "\x00" in p or p.startswith("//"):
        return None
    if PureWindowsPath(p).drive or p.startswith("/"):
        root = str(repo).replace("\\", "/").rstrip("/")
        # the prefix compared as it is spelled: lowering a whole path can change its length (a Turkish dotted I)
        if len(p) <= len(root) + 1 or p[len(root)] != "/" or not _same(p[:len(root)], root):
            return None
        p = p[len(root) + 1:]
    rel = p
    while rel.startswith("./"):
        rel = rel[2:]
    return None if escapes_lexically(rel) else rel


# -- what a file says ----------------------------------------------------------------------------------------------

def _image_size(head: bytes) -> tuple[int, int] | None:
    if head[:8] == b"\x89PNG\r\n\x1a\n" and head[12:16] == b"IHDR" and len(head) >= 24:
        return struct.unpack(">II", head[16:24])
    if head[:6] in (b"GIF87a", b"GIF89a") and len(head) >= 10:
        return struct.unpack("<HH", head[6:10])
    if head[:2] == b"\xff\xd8":  # JPEG: the first start-of-frame marker carries height and width
        i = 2
        while i + 9 < len(head):
            if head[i] != 0xFF:
                i += 1
                continue
            marker = head[i + 1]
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack(">HH", head[i + 5:i + 9])
                return w, h
            i += 2 + struct.unpack(">H", head[i + 2:i + 4])[0]
    return None


def _first_sentence(text: str) -> str:
    s = " ".join(text.split())
    m = re.search(r"(?<=[.!?])\s", s)
    return tn.clip(s[:m.start()] if m else s, PURPOSE_CHARS)


def _comment_blocks(lines: list[str], suffix: str) -> list[tuple[int, int, str]]:
    """The comment blocks of a file: ``(first line, last line, text)``, 1-based, comment marks stripped."""
    out: list[tuple[int, int, str]] = []
    slash, hashed, dash = suffix in _SLASH, suffix in _HASH or suffix in PYTHON, suffix in _DASH
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if slash and s.startswith("/*"):
            start, body = i, []
            while True:
                part = lines[i].strip()
                body.append(part)
                if "*/" in part or i == len(lines) - 1:
                    break
                i += 1
            text = " ".join(re.sub(r"^/\*+|\*+/$|^\*+", "", b).strip() for b in body)
            out.append((start + 1, i + 1, text))
        elif (slash and s.startswith("//")) or (hashed and s.startswith("#") and not s.startswith("#!")) \
                or (dash and s.startswith("--")):
            mark = "//" if s.startswith("//") else "#" if s.startswith("#") else "--"
            start, body = i, []
            while i < len(lines) and lines[i].strip().startswith(mark) and not lines[i].strip().startswith("#!"):
                body.append(lines[i].strip()[len(mark):].strip(" /#-"))
                i += 1
            out.append((start + 1, i, " ".join(body)))
            continue
        i += 1
    return out


def _usable(text: str) -> bool:
    t = re.sub(r"(?m)^\s*@\w+.*$", "", text).strip()  # Javadoc tags say nothing of the purpose
    return bool(t) and not _LICENCE.search(t) and not t.lower().startswith(("-*-", "coding", "eslint", "@ts-"))


def _purpose(text: str, suffix: str, first_def: int | None) -> str | None:
    if suffix in PYTHON:
        try:
            doc = ast.get_docstring(ast.parse(text))
        except (SyntaxError, ValueError):
            doc = None
        if doc and _usable(doc):
            return _first_sentence(doc)
    if suffix in MARKDOWN:
        m = _HEADING.search(text)
        if m:
            return tn.clip(m.group(1), PURPOSE_CHARS)
    lines = text.splitlines()
    blocks = [b for b in _comment_blocks(lines[:400], suffix) if _usable(b[2])]
    if first_def is not None:
        near = [b for b in blocks if b[1] < first_def and first_def - b[1] <= 3]  # the first definition's doc comment
        before = [b for b in blocks if b[1] < first_def]
        pick = near[-1] if near else (before[0] if before else None)
    else:
        pick = blocks[0] if blocks else None
    if pick is not None:
        return _first_sentence(re.sub(r"(?m)^\s*@\w+.*$", "", pick[2]))
    if suffix not in _SLASH and suffix not in PYTHON and suffix not in _DASH:
        first = next((ln.strip() for ln in lines if ln.strip() and not ln.startswith("#!")), "")
        return tn.clip(first, PURPOSE_CHARS) if first else None
    return None


def _defines(facts: dict | None, suffix: str) -> tuple[list[str], int]:
    """The top-level names (a single top-level class: its name and its members), and how many more there are."""
    if not facts:
        return [], 0
    if suffix in MARKDOWN:
        secs = sorted(((v.get("start") or 0, v.get("level") or 0, v.get("title") or "") for v in
                       (facts.get("sections") or {}).values()), key=lambda x: x[0])
        if not secs:
            return [], 0
        levels = sorted({lv for _, lv, _ in secs})
        want = levels[1] if len(levels) > 1 else levels[0]
        titles = [t for _, lv, t in secs if lv == want and t]
        if len(levels) == 1:
            titles = titles[1:]  # the first heading is the purpose
        return titles[:DEFINES], max(0, len(titles) - DEFINES)
    syms = facts.get("symbols") or {}
    top = sorted(((v.get("start") or 0, k) for k, v in syms.items() if "." not in k))
    names = [k for _, k in top]
    if len(names) == 1:
        prefix = names[0] + "."
        members = [k[len(prefix):] for _, k in sorted(((v.get("start") or 0, k) for k, v in syms.items()
                                                      if k.startswith(prefix) and "." not in k[len(prefix):]))]
        if members:
            shown = members[:DEFINES]
            return [f"{names[0]}: {', '.join(shown)}"], max(0, len(members) - len(shown))
    return names[:DEFINES], max(0, len(names) - DEFINES)


def _imports(text: str, suffix: str) -> list[str]:
    found: list[tuple[int, str]] = []
    if suffix in PYTHON:
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError):
            tree = None
        for node in ast.walk(tree) if tree is not None else ():
            if isinstance(node, ast.Import):
                found += [(node.lineno, a.name) for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module != "__future__":
                found.append((node.lineno, "." * node.level + (node.module or "")))
    elif suffix in _JVM:
        for m in _JVM_IMPORT.finditer(text):
            parts = m.group(2).split(".")
            if m.group(1):  # a static import names a member: its class is what the file depends on
                parts = parts[:-1]
            found.append((m.start(), ".".join(parts[-2:])))
    elif suffix in _JS:
        found = [(m.start(), m.group(1) or m.group(2)) for m in _JS_IMPORT.finditer(text)]
    elif suffix in _C:
        found = [(m.start(), m.group(1)) for m in _C_INCLUDE.finditer(text)]
    elif suffix == ".cs":
        found = [(m.start(), m.group(1)) for m in _CS_USING.finditer(text)]
    return list(dict.fromkeys(name for _, name in sorted(found) if name))


# -- the card -------------------------------------------------------------------------------------------------------

def card(repo: Path, path: str) -> dict:
    """The card of one file (see the module docstring); ``repo`` resolved."""
    rel = relative(repo, path)
    if rel is None:
        return {"path": str(path), "kind": "outside"}
    full = contained_path(repo, rel)
    if full is None:
        return {"path": rel, "kind": "outside"}
    try:
        st = full.stat()
    except OSError:
        return {"path": rel, "kind": "missing"}
    if not full.is_file():
        return {"path": rel, "kind": "folder" if full.is_dir() else "other"}
    suffix = full.suffix.lower()
    if suffix in IMAGES:
        try:
            with open(full, "rb") as fh:
                size = _image_size(fh.read(_HEAD_BYTES))
        except OSError:
            size = None
        return {"path": rel, "kind": "image", "bytes": st.st_size, **({"size": f"{size[0]}x{size[1]}"} if size else {})}
    if st.st_size > MAX_BYTES:
        return {"path": rel, "kind": "too_large", "bytes": st.st_size}
    try:
        data = full.read_bytes()
    except OSError:
        return {"path": rel, "kind": "missing"}
    if b"\x00" in data[:8192]:
        return {"path": rel, "kind": "binary", "bytes": len(data)}
    from verinoda import anchors  # the parsers load on a card's first use, not with the CLI

    text = data.decode("utf-8", errors="replace").lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    facts = anchors.compute_facts(rel, data)
    starts = [v.get("start") for v in ((facts or {}).get("symbols") or {}).values() if v.get("start")]
    out: dict = {"path": rel, "kind": "text", "lines": text.count("\n") + (0 if text.endswith("\n") or not text else 1)}
    purpose = _purpose(text, suffix, min(starts) if starts else None)
    if purpose:
        out["purpose"] = purpose
    defines, more = _defines(facts, suffix)
    if defines:
        out["defines"] = defines
        if more:
            out["more_defines"] = more
    imports = _imports(text, suffix)
    if imports:
        out["imports"] = imports[:IMPORTS]
        if len(imports) > IMPORTS:
            out["more_imports"] = len(imports) - IMPORTS
    return out


def render(c: dict) -> str:
    """One card as one line."""
    p, kind = c["path"], c["kind"]
    if kind == "outside":
        return f"{p}: outside the project, no card"
    if kind == "missing":
        return f"{p}: not on disk now"
    if kind in ("folder", "other"):
        return f"{p}: a {kind}, not a file"
    if kind == "image":
        return f"{p}: image {c['size']}" if c.get("size") else f"{p}: image, {c['bytes']} bytes"
    if kind == "binary":
        return f"{p}: binary, {c['bytes']} bytes"
    if kind == "too_large":
        return f"{p} ({c['bytes']} bytes): too large for a card"
    line = f"{p} ({c['lines']} lines)"
    if c.get("purpose"):
        line += f": {c['purpose']}"
    if c.get("defines"):
        line += " | defines " + ", ".join(c["defines"]) + (f" (+{c['more_defines']})" if c.get("more_defines") else "")
    if c.get("imports"):
        line += " | imports " + ", ".join(c["imports"]) + (f" (+{c['more_imports']})" if c.get("more_imports") else "")
    return line


def cards(repo: Path | str, paths: list[str], *, max_chars: int = MAX_CHARS) -> dict:
    """The cards of ``paths`` in their order, a path given twice (relative, ``./``, absolute) carded once, under
    ``max_chars``: whole cards (the first one always, clipped), the rest counted in ``more``."""
    repo = Path(repo).resolve()
    seen: set[str] = set()
    out: list[dict] = []
    lines: list[str] = []
    used = 0
    more = 0
    for p in paths:
        key = relative(repo, p) or str(p)
        if key in seen:
            continue
        seen.add(key)
        if more or (lines and used + 1 > max_chars):
            more += 1
            continue
        c = card(repo, p)
        line = render(c)
        if lines and used + len(line) + 1 > max_chars:
            more += 1
            continue
        out.append(c)
        lines.append(line if lines else line[:max_chars])
        used += len(lines[-1]) + 1
    text = "\n".join(lines) + (f"\n+{more} more file(s): no card for the budget" if more else "")
    return {"cards": out, "text": text, "more": more}
