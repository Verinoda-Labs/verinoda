"""Verinoda - evidence-first codebase analysis (derived from Graphify)."""

from __future__ import annotations


def __getattr__(name: str) -> str:
    # the version is looked up when asked for: importlib.metadata costs about 65 ms, and every CLI call (the editor
    # mod's status line, the agent hooks) imports the package
    if name != "__version__":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    try:
        from importlib.metadata import version as _v

        value = _v("verinoda")
    except Exception:  # pragma: no cover - running from a source tree
        value = "0.5.0"
    globals()["__version__"] = value
    return value
