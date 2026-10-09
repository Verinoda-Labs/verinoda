"""A question's writes, and a read-only scope in which there are none (D177).

The read paths keep caches on disk for the next question: the freshness check's file hashes and git
answers, and a search index or receiver sidecar brought up to date with a rewritten graph. Inside
:func:`scope` each of those places says what it wrote (:func:`note`), so a query can list it
(``index_writes``); with ``on=True`` (``query --read-only``, ``query.read_only``) they build what they
need in memory instead and write nothing. Context variables, so one MCP call's scope never leaks into
another's.
"""

from __future__ import annotations

import contextvars
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_ON: contextvars.ContextVar[bool] = contextvars.ContextVar("verinoda_read_only", default=False)
_WROTE: contextvars.ContextVar[list[str] | None] = contextvars.ContextVar("verinoda_wrote", default=None)


def active() -> bool:
    return _ON.get()


def note(what: str) -> None:
    """Record a write made inside the current scope (nothing outside one)."""
    wrote = _WROTE.get()
    if wrote is not None and what not in wrote:
        wrote.append(what)


def shown(path: Path | str, root: Path | str) -> str:
    """``path`` as a write is listed: relative to the project when it lies inside it."""
    try:
        return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return str(path)


@contextmanager
def scope(on: bool = False) -> Iterator[list[str]]:
    """Collect the writes made inside (the yielded list); ``on``: make none."""
    t_on, t_wrote = _ON.set(on), _WROTE.set([])
    try:
        yield _WROTE.get()
    finally:
        _WROTE.reset(t_wrote)
        _ON.reset(t_on)
