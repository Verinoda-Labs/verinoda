# fetch a PDF or image URL into a raw folder, and save a query result as a memory document
# Verinoda patch (D186): the tweet, arXiv, web page and YouTube fetchers left the package with transcribe.py
# and the markdownify extra (docs/UPSTREAM.md); `ingest` keeps the PDF and image downloads.
from __future__ import annotations
import re
import uuid
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from verinoda.project_index.reflect import OUTCOMES
from verinoda.project_index.security import safe_fetch, validate_url


def _yaml_str(s: str) -> str:
    """Escape a string for embedding in a YAML double-quoted scalar.

    Handles every YAML 1.1/1.2 line-break and control character that could
    let a hostile value (e.g. a fetched page title) break out of the quoted
    scalar and inject sibling YAML keys (F-009 / F-019). The previous
    implementation missed `\\t`, `\\0`, the unicode line-separator U+2028 and
    paragraph-separator U+2029 — all of which YAML treats as line breaks.

    We intentionally do not depend on PyYAML (not in pyproject deps) and
    instead emit safely-escaped double-quoted scalars by hand: the YAML
    double-quoted form recognises `\\\\`, `\\"`, `\\n`, `\\r`, `\\t`, `\\0`,
    `\\L` (U+2028), `\\P` (U+2029), and `\\xNN`/`\\uNNNN` numeric escapes.
    """
    if s is None:
        return ""
    out: list[str] = []
    for ch in str(s):
        cp = ord(ch)
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif ch == "\0":
            out.append("\\0")
        elif cp == 0x2028:
            out.append("\\L")
        elif cp == 0x2029:
            out.append("\\P")
        elif cp < 0x20 or cp == 0x7F:
            out.append(f"\\x{cp:02x}")
        else:
            out.append(ch)
    return "".join(out)


def _safe_filename(url: str, suffix: str) -> str:
    """Turn a URL into a safe filename."""
    parsed = urllib.parse.urlparse(url)
    name = parsed.netloc + parsed.path
    name = re.sub(r"[^\w\-]", "_", name).strip("_")
    name = re.sub(r"_+", "_", name)[:80]
    return name + suffix


def _detect_url_type(url: str) -> str:
    """Classify the URL for targeted extraction."""
    lower = url.lower()
    if "twitter.com" in lower or "x.com" in lower:
        return "tweet"
    if "arxiv.org" in lower:
        return "arxiv"
    if "github.com" in lower:
        return "github"
    if "youtube.com" in lower or "youtu.be" in lower:
        return "youtube"
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.lower()
    if path.endswith(".pdf"):
        return "pdf"
    if any(path.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif")):
        return "image"
    return "webpage"


def _download_binary(url: str, suffix: str, target_dir: Path) -> Path:
    """Download a binary file (PDF, image) directly."""
    filename = _safe_filename(url, suffix)
    out_path = target_dir / filename
    out_path.write_bytes(safe_fetch(url))
    return out_path


def ingest(url: str, target_dir: Path, author: str | None = None, contributor: str | None = None) -> Path:
    """
    Fetch a URL and save it into target_dir as a graphify-ready file.

    Returns the path of the saved file.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    url_type = _detect_url_type(url)

    try:
        validate_url(url)
    except ValueError as exc:
        raise ValueError(f"ingest: {exc}") from exc

    try:
        if url_type == "pdf":
            out = _download_binary(url, ".pdf", target_dir)
            print(f"Downloaded PDF: {out.name}")
            return out

        if url_type == "image":
            suffix = Path(urllib.parse.urlparse(url).path).suffix or ".jpg"
            out = _download_binary(url, suffix, target_dir)
            print(f"Downloaded image: {out.name}")
            return out
    except (urllib.error.HTTPError, urllib.error.URLError, OSError) as exc:
        raise RuntimeError(f"ingest: failed to fetch {url!r}: {exc}") from exc
    raise ValueError(f"ingest: {url_type} URLs are not fetched: the tweet, arXiv, web page and YouTube "
                     "fetchers left the package (Verinoda patch, D186); pass a PDF or image URL")


def save_query_result(
    question: str,
    answer: str,
    memory_dir: Path,
    query_type: str = "query",
    source_nodes: list[str] | None = None,
    outcome: str | None = None,
    correction: str | None = None,
) -> Path:
    """Save a Q&A result as markdown so it gets extracted into the graph on next --update.

    Files are stored in memory_dir (typically graphify-out/memory/) with YAML frontmatter
    that graphify's extractor reads as node metadata. This closes the feedback loop:
    the system grows smarter from both what you add AND what you ask.

    ``outcome`` (one of :data:`OUTCOMES`) and ``correction`` are optional work-memory
    signals: they are written both to the frontmatter (so `graphify reflect` can
    aggregate them deterministically) and to an ``## Outcome`` body section (so the
    signal round-trips into the graph on the next semantic re-extraction).
    """
    if outcome is not None and outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {OUTCOMES}, got {outcome!r}")

    memory_dir = Path(memory_dir)
    memory_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    slug = re.sub(r"[^\w]", "_", question.lower())[:50].strip("_")
    # A second-granularity stamp plus a 50-char slug is not unique: two saves in
    # the same second whose questions share a prefix resolve to one path, and the
    # later write_text silently replaces the earlier one (#3301). The short uuid
    # makes every save its own file; the query_ prefix and .md suffix are kept.
    filename = f"query_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}_{slug}.md"

    frontmatter_lines = [
        "---",
        f'type: "{query_type}"',
        f'date: "{now.isoformat()}"',
        f'question: "{_yaml_str(question)}"',
        'contributor: "graphify"',
    ]
    if outcome:
        frontmatter_lines.append(f'outcome: "{_yaml_str(outcome)}"')
    if correction:
        frontmatter_lines.append(f'correction: "{_yaml_str(correction)}"')
    if source_nodes:
        nodes_str = ", ".join(f'"{_yaml_str(n)}"' for n in source_nodes[:10])
        frontmatter_lines.append(f"source_nodes: [{nodes_str}]")
    frontmatter_lines.append("---")

    body_lines = [
        "",
        f"# Q: {question}",
        "",
        "## Answer",
        "",
        answer,
    ]
    if outcome or correction:
        body_lines += ["", "## Outcome", ""]
        if outcome:
            body_lines.append(f"- Signal: {outcome}")
        if correction:
            body_lines.append(f"- Correction: {correction}")
    if source_nodes:
        body_lines += ["", "## Source Nodes", ""]
        body_lines += [f"- {n}" for n in source_nodes]

    content = "\n".join(frontmatter_lines + body_lines)
    out_path = memory_dir / filename
    out_path.write_text(content, encoding="utf-8")
    return out_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Fetch a URL into a graphify /raw folder")
    parser.add_argument("url", help="URL to fetch")
    parser.add_argument("target_dir", nargs="?", default="./raw", help="Target directory (default: ./raw)")
    parser.add_argument("--author", help="Your name (stored as node metadata)")
    parser.add_argument("--contributor", help="Contributor name for team graphs")
    args = parser.parse_args()
    out = ingest(args.url, Path(args.target_dir), author=args.author, contributor=args.contributor)
    print(f"Ready for graphify: {out}")
