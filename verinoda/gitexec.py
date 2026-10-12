"""One place runs git (docs/DESIGN.md D186).

Every git command line Verinoda builds is built here: :func:`run` for a call read when it ends, :func:`popen` for
one fed or read while it runs (``cat-file --batch``, a streamed ``grep``). ``tests/test_gitexec.py`` keeps it so.
Both carry the same safety:

* :data:`SAFE_FLAGS` (``--no-optional-locks -c core.fsmonitor=false -c core.quotepath=off``) and
  ``GIT_OPTIONAL_LOCKS=0``: a read never writes ``.git/index``, a repository's ``core.fsmonitor`` hook (a command
  of the repository's choosing) never runs, and paths come back unquoted. ``locks=True`` keeps the optional locks
  (``update-index --refresh``); ``safe=False`` leaves the repository's own config in force (``core.hooksPath``).
* the environment loses the repository-local variables (``GIT_DIR``, ``GIT_WORK_TREE``, ``GIT_INDEX_FILE``, ...):
  inherited from a hook or a ``git bisect run``, they would make ``git -C <repo>`` describe another repository.
  ``GIT_TERMINAL_PROMPT=0`` and stdin from ``/dev/null``: a prompt could only hang (under the MCP server stdin
  is the protocol pipe, and on Windows a git child holding it can hang).
* ``status``, ``diff``, ``diff-index`` and ``update-index`` compare the work tree with the index, which runs a
  ``filter.*.clean``, a ``diff.*.command`` or a ``diff.*.textconv`` the repository's own config names. In a
  repository the user has not trusted (``verinoda trust``) such a config refuses the call (exit code 126, the keys
  named) instead of running it: :func:`untrusted_config_risk`.
* a time-out is a result (``timed_out``, exit code 124), a missing git is one too (127): never an exception.
* ``net=<source>`` on a clone, fetch or ls-remote adds :data:`NET_FLAGS`: https and ssh only, no ``ext::`` or
  ``git://``, no redirect followed; the ``file`` transport only for a directory of this machine (a UNC path is a
  share: opening it to check would be the connection to avoid). ``--`` must precede the source in ``args``.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

SAFE_FLAGS = ("--no-optional-locks", "-c", "core.fsmonitor=false", "-c", "core.quotepath=off")
NET_FLAGS = ("-c", "protocol.allow=never", "-c", "protocol.https.allow=always", "-c", "protocol.ssh.allow=always",
             "-c", "http.followRedirects=false")
# variables that point git at another repository or index (a caller running under a hook or `git bisect run`
# has them set)
_LOCAL_ENV = frozenset({
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_IMPLICIT_WORK_TREE", "GIT_PREFIX", "GIT_NAMESPACE",
    "GIT_SHALLOW_FILE", "GIT_GRAFT_FILE", "GIT_NO_REPLACE_OBJECTS", "GIT_REPLACE_REF_BASE",
    "GIT_INTERNAL_SUPER_PREFIX",
})
# the subcommands whose work-tree comparison runs what the repository's config names
_CONFIG_SENSITIVE = ("status", "diff", "diff-index", "update-index")
# global options that take their value as the next word (skipped when the subcommand is looked for)
_WITH_VALUE = ("-c", "-C", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--super-prefix",
               "--config-env")
_BOOL_VALUES = ("", "true", "false", "yes", "no", "on", "off", "1", "0")
_SECTION_RX = re.compile(r'^\[\s*([^\s"\]]+)(?:\s+"((?:[^"\\]|\\.)*)")?\s*\]')
_KEY_RX = re.compile(r"^([A-Za-z][A-Za-z0-9-]*)\s*(?:=\s*(.*))?$")


@dataclass
class GitResult:
    returncode: int
    stdout: str | bytes
    stderr: str
    timed_out: bool = False


def argv(repo: Path | str | None, *args: str, safe: bool = True, locks: bool = False,
         net: str | None = None) -> list[str]:
    """The command line of a call: ``git [-C repo] <safety flags> [<network flags>] <args>``."""
    out = ["git"]
    if repo is not None:
        out += ["-C", str(repo)]
    if safe:
        out += [f for f in SAFE_FLAGS if not (locks and f == "--no-optional-locks")]
    if net is not None:
        if "--" not in args:
            raise ValueError("a network call puts `--` before its source")
        out += NET_FLAGS
        if _local_directory(net):
            out += ["-c", "protocol.file.allow=always"]
    out += args
    return out


def environment(*, safe: bool = True, locks: bool = False, env: dict | None = None) -> dict[str, str]:
    """The process environment of a call: no repository-local variables, no prompt, ``env`` on top."""
    out = {k: v for k, v in os.environ.items() if k.upper() not in _LOCAL_ENV}
    out["GIT_TERMINAL_PROMPT"] = "0"
    if safe and not locks:
        out["GIT_OPTIONAL_LOCKS"] = "0"
    if env:
        out.update(env)
    return out


def run(repo: Path | str | None, *args: str, timeout: float = 60, safe: bool = True, locks: bool = False,
        env: dict | None = None, net: str | None = None, input: bytes | str | None = None,
        binary: bool = False) -> GitResult:
    """Run git in ``repo`` (None: no ``-C``) and read it when it ends. ``input`` is fed on stdin (bytes with
    ``binary``, which also leaves ``stdout`` as bytes); without it stdin is never inherited."""
    empty: str | bytes = b"" if binary else ""
    refused = _refusal(repo, args, safe)
    if refused is not None:
        return GitResult(126, empty, refused)
    kw: dict = {"capture_output": True, "timeout": timeout, "env": environment(safe=safe, locks=locks, env=env)}
    if not binary:
        kw.update(text=True, encoding="utf-8", errors="replace")
    if input is None:
        kw["stdin"] = subprocess.DEVNULL
    else:
        kw["input"] = input
    try:
        r = subprocess.run(argv(repo, *args, safe=safe, locks=locks, net=net), check=False, **kw)
    except subprocess.TimeoutExpired:
        return GitResult(124, empty, f"git {_subcommand(args) or ''} timed out after {timeout:g} s", timed_out=True)
    except FileNotFoundError:
        return GitResult(127, empty, "git executable not found on PATH")
    except OSError as exc:
        return GitResult(126, empty, f"could not run git: {exc}")
    err = r.stderr if isinstance(r.stderr, str) else (r.stderr or b"").decode("utf-8", "replace")
    return GitResult(r.returncode, r.stdout, err)


def popen(repo: Path | str | None, *args: str, safe: bool = True, locks: bool = False, env: dict | None = None,
          **kw) -> subprocess.Popen:
    """Start git for a caller that feeds or reads it while it runs (plumbing: ``cat-file --batch``, ``grep``);
    ``kw`` goes to :class:`subprocess.Popen`. stdin is ``/dev/null`` unless the caller pipes it."""
    kw.setdefault("stdin", subprocess.DEVNULL)
    kw["env"] = environment(safe=safe, locks=locks, env=env)
    return subprocess.Popen(argv(repo, *args, safe=safe, locks=locks), **kw)


def _subcommand(args: tuple[str, ...]) -> str | None:
    it = iter(args)
    for a in it:
        if a in _WITH_VALUE:
            next(it, None)
            continue
        if a.startswith("-"):
            continue
        return a
    return None


def _refusal(repo: Path | str | None, args: tuple[str, ...], safe: bool) -> str | None:
    """Why a work-tree comparison in an untrusted repository with a risky config is not run; None to run it."""
    if repo is None or not safe or _subcommand(args) not in _CONFIG_SENSITIVE:
        return None
    from verinoda.paths import is_trusted

    if is_trusted(repo):
        return None
    keys = untrusted_config_risk(Path(repo))
    if not keys:
        return None
    return (f"repository config carries {', '.join(keys)}; run `verinoda trust {Path(repo).resolve()}` to allow "
            "(the user's decision: it names a command the repository's own config would run)")


def _local_directory(source: str) -> bool:
    """Is ``source`` a directory of this machine? A URL or a UNC path (``\\\\server\\share``, ``//server/share``) is not,
    and is not looked at: the look would be the connection."""
    s = str(source)
    if "://" in s or s.startswith(("\\\\", "//")):
        return False
    try:
        return Path(s).is_dir()
    except (OSError, ValueError):
        return False


# -- the repository's own config --------------------------------------------------------------------------------

def _config_file(repo: Path) -> Path | None:
    """``.git/config``; for a linked work tree (``.git`` a file naming its git dir) the common dir's config."""
    dot = Path(repo) / ".git"
    try:
        if dot.is_dir():
            return dot / "config"
        if not dot.is_file():
            return None
        text = dot.read_text(encoding="utf-8", errors="replace")
        if not text.startswith("gitdir:"):
            return None
        gd = Path(text[len("gitdir:"):].strip())
        if not gd.is_absolute():
            gd = dot.parent / gd
        common = (gd / "commondir").read_text(encoding="utf-8").strip() if (gd / "commondir").is_file() else ""
    except OSError:
        return None
    return (gd / common if common else gd) / "config"


def _risky(section: str, sub: str, key: str, value: str) -> bool:
    k = key.lower()
    if section == "core" and k == "fsmonitor":  # a boolean is the built-in daemon; anything else is a hook to run
        return value not in _BOOL_VALUES
    if section == "core" and k == "sshcommand":
        return True
    if section == "filter" and k in ("clean", "smudge", "process"):
        return True
    if section == "diff" and sub and k in ("command", "textconv"):
        return True
    return section in ("include", "includeif")


def untrusted_config_risk(repo: Path) -> list[str]:
    """The keys of the repository's own config that name a command git would run on a status or diff, or pull
    in another config file: ``core.fsmonitor`` (a command, not a boolean), ``core.sshCommand``, ``filter.*``
    (clean, smudge, process), ``diff.*.command``, ``diff.*.textconv``, ``include.*``/``includeIf.*``. Sorted;
    empty when there is no config to read."""
    p = _config_file(Path(repo))
    if p is None:
        return []
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    found: set[str] = set()
    section = sub = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line[0] in "#;":
            continue
        m = _SECTION_RX.match(line)
        if m:
            section, sub = m.group(1).lower(), m.group(2) or ""
            if sub == "" and "." in section:  # the deprecated `[section.subsection]` spelling
                section, sub = section.split(".", 1)
            continue
        m = _KEY_RX.match(line)
        if not m:
            continue
        key = m.group(1)
        value = re.split(r"\s[;#]", m.group(2) or "", 1)[0].strip().strip('"').lower()
        if _risky(section, sub, key, value):
            found.add(f"{section}.{sub}.{key}" if sub else f"{section}.{key}")
    return sorted(found)
