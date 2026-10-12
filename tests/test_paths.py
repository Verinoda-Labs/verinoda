"""verinoda.paths: path containment at the sources and the evidence-root allowlist (docs/DESIGN.md D186)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from verinoda import paths

PKG = Path(__file__).resolve().parents[1] / "verinoda"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
                   cwd=cwd, check=True, capture_output=True)


def _link(link: Path, target: Path) -> bool:
    """A symbolic link to a folder, or a junction on Windows (a symlink needs a privilege there); False when
    neither can be made."""
    try:
        os.symlink(target, link, target_is_directory=True)
        return True
    except (OSError, NotImplementedError):
        pass
    if os.name == "nt":
        r = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, check=False)
        return r.returncode == 0
    return False


@pytest.mark.parametrize("rel", [r"\\server\share\x", "//server/x", r"C:\x", "C:/x", r"..\x", "../x",
                                 "a/../../x", "x:stream", r"\\?\C:\x", r"\\.\pipe\x", "/etc/passwd", r"\x",
                                 "a\0b", ""])
def test_contained_path_rejects_lexically_before_touching_the_file_system(monkeypatch, tmp_path, rel):
    def boom(self, *a, **k):
        raise AssertionError(f"resolve() was called for {rel!r}: a UNC path would be opened to be judged")

    monkeypatch.setattr(Path, "resolve", boom)
    assert paths.escapes_lexically(rel)
    assert paths.contained_path(tmp_path, rel) is None


def test_contained_path_accepts_a_plain_relative_file(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "mod.py").write_text("x = 1\n", encoding="utf-8")
    p = paths.contained_path(tmp_path, "pkg/mod.py")
    assert p == tmp_path / "pkg" / "mod.py" and p.is_file()
    # a path need not exist to be inside; a name holding dots is not a climb
    assert paths.contained_path(tmp_path, "missing/file.py") == tmp_path / "missing" / "file.py"
    assert not paths.escapes_lexically("pkg/mod.py") and not paths.escapes_lexically("a..b/.c.d")
    assert paths.contained_path(tmp_path, "a..b/.c.d") == tmp_path / "a..b" / ".c.d"


def test_a_symlinked_root_outside_the_repo_is_not_allowed(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".verinoda" / "research").mkdir(parents=True)
    outside = tmp_path / "outside"
    (outside / "lib").mkdir(parents=True)
    (outside / "lib" / "x.py").write_text("x = 1\n", encoding="utf-8")
    if not _link(repo / "ref", outside):
        pytest.skip("neither a symlink nor a junction can be made here")
    assert not paths.evidence_root_allowed(repo, repo / "ref")   # a link that leaves the repository
    assert not paths.evidence_root_allowed(repo, outside)        # its target, named directly
    assert not paths.evidence_root_allowed(repo, tmp_path / "repo-sibling")
    assert paths.contained_path(repo, "ref/lib/x.py") is None    # a file read through the link
    assert paths.contained_path(outside, "lib/x.py") == outside / "lib" / "x.py"
    # the repository, a folder of it and its research checkouts are allowed
    assert paths.evidence_root_allowed(repo, repo)
    assert paths.evidence_root_allowed(repo, repo / "pkg")
    assert paths.evidence_root_allowed(repo, paths.research_dir(repo) / "slug" / "abc123def456")
    # research checkouts kept elsewhere through a link are compared after resolving: still allowed
    other = tmp_path / "repo2"
    (other / ".verinoda").mkdir(parents=True)
    store = tmp_path / "research-store"
    (store / "slug" / "abc123def456").mkdir(parents=True)
    if _link(other / ".verinoda" / "research", store):
        assert paths.evidence_root_allowed(other, other / ".verinoda" / "research" / "slug" / "abc123def456")
        assert paths.evidence_root_allowed(other, store / "slug" / "abc123def456")


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_the_git_work_tree_top_of_a_subfolder_project_is_allowed(tmp_path):
    top = tmp_path / "mono"
    proj = top / "services" / "orders"
    proj.mkdir(parents=True)
    (top / "CODEOWNERS").write_text("* @team\n", encoding="utf-8")
    (proj / "app.py").write_text("x = 1\n", encoding="utf-8")
    _git(top, "init", "-q")
    _git(top, "add", "-A")
    _git(top, "commit", "-q", "-m", "init")
    assert paths.work_tree_top(proj) == top.resolve()
    assert paths.evidence_root_allowed(proj, top)                   # CODEOWNERS evidence cites the top
    assert not paths.evidence_root_allowed(proj, top / "services")  # only the top itself, not every folder above
    assert paths.evidence_root_allowed(proj, proj / "sub")
    plain = tmp_path / "plain"
    plain.mkdir()
    assert paths.work_tree_top(plain) is None


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_a_core_worktree_in_the_repositorys_config_does_not_move_the_top(tmp_path):
    """A cloned repository ships its .git/config: `core.worktree = <the folder above>` makes `git rev-parse
    --show-toplevel` name the user's folder, and with it every file there would be a readable evidence root (the
    final review, Critical). The top is taken from git only when the repository's config sets no core.worktree."""
    outer = tmp_path / "outer"
    repo = outer / "proj"
    repo.mkdir(parents=True)
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
    (outer / "secret.txt").write_text("not yours\n", encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    _git(repo, "config", "core.worktree", str(outer))
    assert paths.work_tree_top(repo) is None
    assert not paths.evidence_root_allowed(repo, outer)
    assert paths.evidence_root_allowed(repo, repo)


_ROOT_JOIN = re.compile(r"\broot\s*/\s*ev\b|\[\"root\"\]\)?\s*/\s")


def test_no_evidence_root_is_joined_outside_the_helper():
    """``meta.root`` of an evidence row meets a path only in ``paths.contained_path`` (D186)."""
    hits = []
    for p in sorted(PKG.rglob("*.py")):
        rel = p.relative_to(PKG).as_posix()
        if rel.startswith(("benchmark/", "project_index/")) or rel == "paths.py":
            continue
        for n, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if _ROOT_JOIN.search(line.split("#", 1)[0]):
                hits.append(f"{rel}:{n}")
    assert hits == []


def test_an_evidence_root_on_a_share_is_refused_before_it_is_resolved(tmp_path, monkeypatch):
    # the review of D186: meta.root comes from the store, which a repository can ship; resolving a UNC root would
    # itself open the connection, so the refusal is lexical and comes first
    from pathlib import Path

    from verinoda import paths

    original = Path.resolve

    def guarded(self, *a, **k):
        if str(self).startswith(("\\\\", "//")):
            raise AssertionError(f"resolved a share path {self}")
        return original(self, *a, **k)

    monkeypatch.setattr(Path, "resolve", guarded)
    for root in (r"\attacker\share\x", "//attacker/share/x", r"\?\C:\x", r"\.\pipe\x"):
        assert paths.evidence_root_allowed(tmp_path, Path(root)) is False, root
    assert paths.evidence_root_allowed(tmp_path, tmp_path / "sub") is True
