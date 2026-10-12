"""verinoda.gitexec: the one place that runs git (docs/DESIGN.md D186)."""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pytest

from verinoda import gitexec, paths

PKG = Path(__file__).resolve().parents[1] / "verinoda"


class _Done:
    def __init__(self, args, returncode=0, stdout="", stderr=""):
        self.args, self.returncode, self.stdout, self.stderr = args, returncode, stdout, stderr


def _recorder(monkeypatch, seen: dict, **result):
    def fake_run(argv, **kw):
        seen.clear()
        seen.update(kw, argv=argv)
        return _Done(argv, **result)

    monkeypatch.setattr(gitexec.subprocess, "run", fake_run)


def test_run_adds_the_safety_flags_and_env(monkeypatch, tmp_path):
    seen: dict = {}
    _recorder(monkeypatch, seen, stdout="ok\n")
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "elsewhere" / ".git"))
    r = gitexec.run(tmp_path, "status", "--porcelain")
    assert (r.returncode, r.stdout, r.stderr, r.timed_out) == (0, "ok\n", "", False)
    argv = seen["argv"]
    assert argv[:3] == ["git", "-C", str(tmp_path)]
    assert argv[3:3 + len(gitexec.SAFE_FLAGS)] == list(gitexec.SAFE_FLAGS)
    assert argv[-2:] == ["status", "--porcelain"]
    assert "--no-optional-locks" in argv and "core.fsmonitor=false" in argv and "core.quotepath=off" in argv
    assert seen["env"]["GIT_OPTIONAL_LOCKS"] == "0" and seen["env"]["GIT_TERMINAL_PROMPT"] == "0"
    assert "GIT_DIR" not in seen["env"]  # a hook's or `git bisect run`'s variables never point git elsewhere
    assert seen["stdin"] is subprocess.DEVNULL and seen["timeout"] == 60
    # locks=True keeps the optional locks: neither the flag nor the variable
    gitexec.run(tmp_path, "update-index", "--refresh", locks=True)
    assert "--no-optional-locks" not in seen["argv"] and "GIT_OPTIONAL_LOCKS" not in seen["env"]
    assert "core.fsmonitor=false" in seen["argv"]
    # safe=False: the repository's own config applies
    gitexec.run(tmp_path, "config", "--get", "core.hooksPath", safe=False)
    assert "core.fsmonitor=false" not in seen["argv"] and "GIT_OPTIONAL_LOCKS" not in seen["env"]
    # no repository: no -C; extra environment and a caller's own -c options come through
    gitexec.run(None, "-c", "core.longpaths=true", "--version", env={"GCM_INTERACTIVE": "never"})
    assert seen["argv"][0] == "git" and "-C" not in seen["argv"] and seen["argv"][-1] == "--version"
    assert "core.longpaths=true" in seen["argv"] and seen["env"]["GCM_INTERACTIVE"] == "never"


def test_run_passes_input_and_reads_bytes_when_asked(monkeypatch, tmp_path):
    seen: dict = {}
    _recorder(monkeypatch, seen, stdout=b"a\0b\0", stderr=b"")
    r = gitexec.run(tmp_path, "check-ignore", "-z", "--stdin", input=b"a\0b\0", binary=True)
    assert seen["input"] == b"a\0b\0" and "stdin" not in seen and "text" not in seen
    assert r.stdout == b"a\0b\0" and r.stderr == ""


def test_run_reports_a_timeout_as_timed_out_not_an_exception(monkeypatch, tmp_path):
    def slow(argv, **kw):
        raise subprocess.TimeoutExpired(argv, kw.get("timeout"))

    monkeypatch.setattr(gitexec.subprocess, "run", slow)
    r = gitexec.run(tmp_path, "log", "-S", "x", timeout=0.5)
    assert r.timed_out and r.returncode == 124 and r.stdout == "" and "0.5" in r.stderr and "log" in r.stderr

    def missing(argv, **kw):
        raise FileNotFoundError("git")

    monkeypatch.setattr(gitexec.subprocess, "run", missing)
    r = gitexec.run(tmp_path, "log")
    assert r.returncode == 127 and not r.timed_out and "not found" in r.stderr
    r = gitexec.run(tmp_path, "log", binary=True)
    assert r.returncode == 127 and r.stdout == b""


def test_popen_builds_the_same_argv_and_environment(monkeypatch, tmp_path):
    seen: dict = {}

    class FakePopen:
        def __init__(self, argv, **kw):
            seen.update(kw, argv=argv)

    monkeypatch.setattr(gitexec.subprocess, "Popen", FakePopen)
    gitexec.popen(tmp_path, "cat-file", "--batch", stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    assert seen["argv"] == ["git", "-C", str(tmp_path), *gitexec.SAFE_FLAGS, "cat-file", "--batch"]
    assert seen["env"]["GIT_OPTIONAL_LOCKS"] == "0" and seen["stdin"] is subprocess.PIPE
    gitexec.popen(tmp_path, "grep", "-n", "x")
    assert seen["stdin"] is subprocess.DEVNULL  # never the caller's stdin (the MCP pipe)


def _config(repo: Path, text: str) -> None:
    (repo / ".git").mkdir(parents=True, exist_ok=True)
    (repo / ".git" / "config").write_text(text, encoding="utf-8")


def test_untrusted_config_risk_names_the_keys(tmp_path):
    repo = tmp_path / "r"
    _config(repo, "[core]\n\trepositoryformatversion = 0\n\tfsmonitor = .git/hooks/fsmonitor-watchman\n"
                  '[filter "lfs"]\n\tclean = evil\n\tsmudge = cat\n\trequired = true\n'
                  '[diff "pdf"]\n\ttextconv = pdftotext\n[Include]\n\tpath = ../other\n'
                  '[remote "origin"]\n\turl = https://example.org/r.git\n')
    assert gitexec.untrusted_config_risk(repo) == [
        "core.fsmonitor", "diff.pdf.textconv", "filter.lfs.clean", "filter.lfs.smudge", "include.path"]
    _config(repo, "[core]\n\tfsmonitor = true\n\tsshCommand = evil\n")
    assert gitexec.untrusted_config_risk(repo) == ["core.sshCommand"]  # a boolean fsmonitor is the built-in daemon
    _config(repo, "[core]\n\tbare = false\n[remote \"origin\"]\n\turl = x\n")
    assert gitexec.untrusted_config_risk(repo) == []
    assert gitexec.untrusted_config_risk(tmp_path / "none") == []
    # a linked work tree: .git is a file naming the git dir, whose commondir holds the config
    main = tmp_path / "main"
    (main / ".git" / "worktrees" / "wt").mkdir(parents=True)
    (main / ".git" / "config").write_text('[diff "x"]\n\tcommand = evil\n', encoding="utf-8")
    (main / ".git" / "worktrees" / "wt" / "commondir").write_text("../..\n", encoding="utf-8")
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {main / '.git' / 'worktrees' / 'wt'}\n", encoding="utf-8")
    assert gitexec.untrusted_config_risk(wt) == ["diff.x.command"]


def test_a_risky_config_refuses_status_and_diff_in_an_untrusted_repository(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.CONFIG_DIR_ENV, str(tmp_path / "user"))  # nothing is trusted here
    repo = tmp_path / "r"
    _config(repo, '[filter "lfs"]\n\tclean = evil\n')
    seen: dict = {}
    _recorder(monkeypatch, seen)
    for args in (("status", "--porcelain=v2"), ("-c", "core.quotepath=off", "diff", "--name-only"),
                 ("--literal-pathspecs", "diff-index", "HEAD"), ("update-index", "--refresh")):
        r = gitexec.run(repo, *args)
        assert r.returncode == 126 and "filter.lfs.clean" in r.stderr and "verinoda trust" in r.stderr
        assert not seen  # git was not started
    assert gitexec.run(repo, "status", binary=True).stdout == b""
    assert gitexec.run(repo, "rev-parse", "HEAD").returncode == 0 and seen["argv"][-1] == "HEAD"
    paths.set_trust(repo)
    assert gitexec.run(repo, "status").returncode == 0 and seen["argv"][-1] == "status"


def test_a_refused_status_is_said_in_git_info(monkeypatch, tmp_path):
    """An untrusted repository with git-lfs installed locally (`git lfs install --local` writes filter.lfs.* into
    .git/config) is not read as "not git" silently: the refusal and the way out are in the answer."""
    from verinoda import snapshot

    monkeypatch.setenv(paths.CONFIG_DIR_ENV, str(tmp_path / "user"))
    repo = tmp_path / "r"
    _config(repo, '[filter "lfs"]\n\tclean = git-lfs clean -- %f\n\tsmudge = git-lfs smudge -- %f\n'
                  "\tprocess = git-lfs filter-process\n\trequired = true\n")
    info = snapshot.git_info(repo)
    assert info["is_git"] is False and info["commit"] is None
    assert "filter.lfs.clean" in info["refused"] and "verinoda trust" in info["refused"]
    paths.set_trust(repo)
    assert "refused" not in snapshot.git_info(repo)  # trusted: git runs (and finds no repository here)


def _starts_with_git(node: ast.AST) -> bool:
    return (isinstance(node, (ast.List, ast.Tuple)) and bool(node.elts)
            and isinstance(node.elts[0], ast.Constant) and node.elts[0].value == "git")


def _git_argv_sites(path: Path) -> list[str]:
    """Lines of ``path`` that build a git argv: a list or tuple whose first element is "git" (a membership test
    ``x in ("git", ...)`` and a tuple unpacked into several targets are not one), or a subprocess call whose first
    argument is such a list."""
    tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    parent = {c: p for p in ast.walk(tree) for c in ast.iter_child_nodes(p)}
    hits: list[int] = []
    for node in ast.walk(tree):
        if _starts_with_git(node):
            p = parent.get(node)
            unpacking = isinstance(p, ast.Assign) and isinstance(p.targets[0], ast.Tuple)
            if not isinstance(p, ast.Compare) and not unpacking:
                hits.append(node.lineno)
        elif isinstance(node, ast.Call) and node.args and _starts_with_git(node.args[0]):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
            if name in ("run", "Popen", "check_output", "check_call", "call"):
                hits.append(node.lineno)
    return [f"{path.relative_to(PKG).as_posix()}:{n}" for n in sorted(set(hits))]


def test_no_bare_git_argv_outside_gitexec():
    """The guard of the funnel: ``verinoda/gitexec.py`` is the only module that builds a git command line. The
    benchmark harnesses and the vendored ``project_index`` (Apache-2.0, re-synced from upstream) are left out."""
    hits: list[str] = []
    for p in sorted(PKG.rglob("*.py")):
        rel = p.relative_to(PKG).as_posix()
        if rel.startswith(("benchmark/", "project_index/")) or "fixtures" in rel.split("/"):
            continue
        hits += _git_argv_sites(p)
    assert hits and all(h.startswith("gitexec.py:") for h in hits), \
        "git argv built outside gitexec: " + ", ".join(h for h in hits if not h.startswith("gitexec.py:"))


def test_reference_fetches_pin_protocols_and_refuse_redirects(monkeypatch, tmp_path):
    seen: dict = {}
    _recorder(monkeypatch, seen)
    url = "https://example.invalid/x.git"
    gitexec.run(None, "clone", "--bare", "--quiet", "--", url, str(tmp_path / "m.git"), net=url)
    argv = seen["argv"]
    for flag in ("protocol.allow=never", "protocol.https.allow=always", "protocol.ssh.allow=always",
                 "http.followRedirects=false"):
        assert flag in argv and argv.index(flag) < argv.index("clone")
    assert argv.index("clone") < argv.index("--") < argv.index(url)
    assert "protocol.file.allow=always" not in argv
    local = tmp_path / "src"
    local.mkdir()
    gitexec.run(None, "ls-remote", "--symref", "--", str(local), net=str(local))
    assert "protocol.file.allow=always" in seen["argv"] and "protocol.allow=never" in seen["argv"]
    unc = r"\\server\share\x"
    gitexec.run(None, "ls-remote", "--", unc, net=unc)  # a UNC path is a network share, not a local directory
    assert "protocol.file.allow=always" not in seen["argv"]
    gitexec.run(None, "ls-remote", "--", local.as_uri(), net=local.as_uri())  # file:// of a local directory
    assert "protocol.file.allow=always" in seen["argv"]
    share = "file://server/share/x"
    gitexec.run(None, "ls-remote", "--", share, net=share)  # file:// with a host is a share too
    assert "protocol.file.allow=always" not in seen["argv"]
    with pytest.raises(ValueError, match="--"):
        gitexec.run(None, "clone", url, str(tmp_path / "n.git"), net=url)


def test_a_unc_path_hidden_in_a_file_url_is_not_a_local_directory(monkeypatch):
    # the review of D186's funnel: `file:////server/share/x` and `file://localhost//server/share` have no host in the
    # URL, and url2pathname turns their path into `\server\share\x` - a look at it would be the connection
    from pathlib import Path

    from verinoda import gitexec

    def never_a_share(self):
        # a drive-relative result (`\server\share\x`, one backslash) is a folder of this machine: asking is harmless
        if str(self).startswith(("\\\\", "//")):
            raise AssertionError(f"the file system was asked about the share {self}")
        return False

    monkeypatch.setattr(Path, "is_dir", never_a_share)
    for src in ("file:////server/share/x", "file://localhost//server/share", r"file:///\server\share", "//server/share",
                r"\server\share\x"):
        assert gitexec._local_directory(src) is False, src
