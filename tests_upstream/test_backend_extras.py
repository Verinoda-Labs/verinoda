"""The optional extras stay consistent: `[all]` is the union of every other extra, and the
version-gated dependencies are packaged.

Verinoda patch (D186): the tests of the upstream LLM backends' extras (`[anthropic]`, the
`_backend_pkg_hint` message, the PostgreSQL driver) left with llm.py and those extras
(docs/UPSTREAM.md); the `leiden` extra holds graspologic-native for every Python version.
"""
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def _extras():
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    return data["project"]["optional-dependencies"]


def test_version_gated_optional_backends_are_packaged():
    extras = _extras()
    for extra in ("leiden", "all"):
        assert "graspologic-native>=1.3.1,<2" in extras[extra]
    for extra in ("chinese", "all"):
        assert "jieba-py>=0.46.12,<1; python_version >= '3.12'" in extras[extra]


def test_all_extra_is_the_union_of_every_other_extra():
    """README documents `[all]` as "Everything above": every dependency of every
    other extra must be in it. `psycopg[binary]` from `[postgres]` was missing, so
    an `[all]` install still failed on `graphify extract --postgres` (#3482)."""
    extras = _extras()
    union = {dep for name, deps in extras.items() if name != "all" for dep in deps}
    missing = sorted(union - set(extras["all"]))
    assert not missing, f"[all] is missing dependencies from other extras: {missing}"
