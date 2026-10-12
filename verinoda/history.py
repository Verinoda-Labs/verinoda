"""Commit, diff and revision search: when a text appeared or disappeared, which commits match, what two
revisions differ in.

"When did ``retry_budget`` appear, and when did it go?" is a question about the repository's history, and git
answers it exactly: ``git log -S<text>`` lists the commits that changed how often the text occurs, ``-G<regex>``
the ones whose added or removed lines match. :func:`text_history` reads those commits with their zero-context
patches (oldest first), counts the text in each file's added and removed lines, and says:

- the commit that first added it (the oldest commit that added an occurrence), with the line it was added at;
- when HEAD has no occurrence, the commit that last removed it, with the line it was removed from;
- where it is at HEAD otherwise (``git grep``).

Each of these is a ``history`` claim whose evidence is the commit (``git_history``, the diff line quoted). The
reading is exact for the history reachable from HEAD; a shallow clone or a cut list (more than :data:`MAX_EVENTS`
commits) leaves the first appearance unproven, so that claim is ``strong_inference`` then, with the reason. A
regular expression is git's (POSIX extended) throughout: git selects the commits with it and ``git grep`` picks
the changed lines it matches, so the two never disagree and no pattern is matched in this process.

Where git is blind with a path (D186): a path that names one file is followed across renames (``--follow``), so
a one-for-one change before a move is found; a first event that created the file, or an older path-free commit,
is checked against :func:`oldest_appearance` (the whole history, oldest first), and the claim says what it found
(``earlier_elsewhere``). ``appeared`` is what happened under the path and says so (``scope: under <path>``);
``first_appearance`` (``scope: path-free``) stands beside it when the path-free read proved the first commit, so
neither is read as the other. A read that exceeds :data:`GIT_TIMEOUT` (``VERINODA_MCP_GIT_TIMEOUT``) answers
``status: partial`` with what was searched and the next call, never a bare error. Every result states its
``scope`` (what was searched, what was not) and ``more`` (the tool's own limit was reached).

When the project is a folder of its git repository, every search stays inside that folder and every path is
relative to it (``--relative``), as the index's paths are. A path is a literal file or folder prefix
(``--literal-pathspecs``: no glob, no ``:/`` magic) and never leaves the project.

:func:`commits` searches commit messages, authors, paths, dates and diff content (``git log --grep``,
``--author``, ``-G``); :func:`compare` lists what one revision has that another has not (the commits of
``A..B``, their merge base, the files changed with their line counts). Git is only read, never written; every
argument that reaches it is one ``--option=value`` word or a path after ``--``, and a revision is checked to name
a commit first.

:func:`symbol_history` answers why a symbol is the way it is from git: the commits whose diffs changed its lines
(``git log -L`` from HEAD; working-tree lines that differ from HEAD are mapped to HEAD's first), one row each
(``sha date author subject``, newest first) with the message bodies of the first and last :data:`QUOTED_EACH_END`
and of any that states a reason quoted as the author wrote them (D186: a claim per commit repeated every row).
:func:`symbol_commits` is the reading alone, each commit with its whole message; the why-questions of ``analyze``
use it.

:func:`co_changes` reads which files changed in the same commits as a set of files (temporal coupling):
``map --view impact`` lists those the graph does not link to the change as ``strong_inference`` claims with their
commit counts and the shared commits as evidence.
"""
from __future__ import annotations

import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Callable

from verinoda import evidence as evmod
from verinoda import gitexec
from verinoda.treestate import project_prefix

MAX_EVENTS = 200     # commits read for one text; more and the oldest (the first appearance) are cut
MAX_COMMITS = 100    # commits a search or a comparison lists at most
MAX_FILES = 200      # changed files a comparison lists at most
MAX_SITES = 10       # HEAD occurrences listed
QUOTED_EACH_END = 3  # rows at each end of a symbol's history whose message body is quoted (D186)
QUOTE_CHARS = 300    # characters of one quoted body (the row carries the subject; `git show` has the rest)


def _seconds(name: str, default: float) -> float:
    try:
        v = float(os.environ.get(name) or "")
    except ValueError:
        return default
    return v if v > 0 else default


# a -S, -G or -L read over a whole history; rev-parse and grep are short. On expiry the tool answers `partial`
# with what was searched, never a bare error (D186). The 60 s is not measured on a 50k-commit repository.
GIT_TIMEOUT = _seconds("VERINODA_MCP_GIT_TIMEOUT", 60)
GIT_SHORT_TIMEOUT = 20.0
_HDR = "\x1e@@"      # start of one commit in the log output (never in a diff line)
_FMT = f"--format={_HDR}%H%x1f%an%x1f%aI%x1f%s"
_HUNK = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
# no external diff or text conversion (a repository's config could name a program), no colour, no renames
# (a moved file's text is neither added nor removed)
_DIFF_SAFE = ("--no-ext-diff", "--no-textconv", "--no-color", "--no-renames")
# the same with the one followed file's renames detected: the move shows no occurrence change and drops out
_DIFF_FOLLOW = ("--no-ext-diff", "--no-textconv", "--no-color", "--follow")
_LIT = "--literal-pathspecs"   # a user path is a file or folder prefix: no glob, no `:/` magic
_NEXT_NARROW = (f"narrow with path=<a file or folder>, or raise VERINODA_MCP_GIT_TIMEOUT (now {GIT_TIMEOUT:g} s) "
                "and ask again")


def _run_git(repo: Path, *args: str, timeout: float | None = None) -> gitexec.GitResult:
    """One git call through the funnel (D186); the caller reads ``returncode`` and ``timed_out``."""
    return gitexec.run(repo, *args, timeout=GIT_TIMEOUT if timeout is None else timeout)


def _git(repo: Path, *args: str, timeout: float | None = None) -> str | None:
    """stdout of a git call that succeeded, else None (a time-out included: a caller that must tell the two apart
    reads :func:`_run_git`)."""
    r = _run_git(repo, *args, timeout=timeout)
    return r.stdout if r.returncode == 0 else None


def _partial(searched: str, next_step: str, **found) -> dict:
    """A result cut short by a time-out: what was searched for how long, how to go on, what was found (D186)."""
    return {"status": "partial", "timed_out": True, "searched": searched, "next_step": next_step, "more": False,
            **found}


def _probe(repo: Path, kind: str) -> dict | None:
    """None when ``repo`` is a git work tree with a commit; else the answer: ``not_git``, or ``partial`` when the
    probe itself timed out (no answer in time is not "no history")."""
    r = _run_git(repo, "rev-parse", "--verify", "--quiet", "HEAD^{commit}", timeout=GIT_SHORT_TIMEOUT)
    if r.returncode == 0:
        return None
    if r.timed_out:
        return {"kind": kind, **_partial(f"git rev-parse HEAD, {GIT_SHORT_TIMEOUT:g} s: the repository gave no answer",
                                         "ask again; a repository this slow to answer is busy or on a slow disk")}
    return _not_git(kind, repo)


def _is_git(repo: Path) -> bool:
    return _probe(repo, "") is None


def _shallow(repo: Path) -> bool:
    return (_git(repo, "rev-parse", "--is-shallow-repository", timeout=GIT_SHORT_TIMEOUT) or "").strip() == "true"


def _word(value: str | None, what: str) -> str | None:
    """A filter value as given (stripped), or None; one line only."""
    if value is None:
        return None
    v = str(value).strip()
    if not v:
        return None
    if "\n" in v or "\r" in v or "\x00" in v:
        raise ValueError(f"{what} must be one line")
    return v


def _pathspec(path: str | None) -> list[str]:
    p = _word(path, "path")
    if not p:
        return []
    p = p.replace("\\", "/")
    if ".." in p.split("/"):   # from a sub-project, `..` would reach a sibling folder of the same repository
        raise ValueError(f"path: {p!r} leaves the project (a path is a file or folder prefix inside it)")
    return ["--", p]


def _scope(repo: Path, path: str | None) -> tuple[list[str], list[str]]:
    """The pathspec and the diff option that keep a search inside the project: in a folder of its git
    repository, only that folder (``.``, or the path given, both relative to it), its paths relative to it."""
    spec = _pathspec(path)
    if not project_prefix(repo):
        return spec, []
    return (spec or ["--", "."]), ["--relative"]


def _one_file(repo: Path, path: str | None) -> bool:
    """Does ``path`` name one file of the working tree? Its history is then followed across renames: a one-for-one
    change before a move is invisible to ``-S`` under the new path alone (D186, the fastapi class). A folder
    cannot be followed; a deleted file's path is read as it is."""
    p = _word(path, "path")
    if not p:
        return False
    try:
        return (Path(repo) / p.replace("\\", "/")).is_file()
    except (OSError, ValueError):
        return False


def _scope_text(repo: Path, path: str | None, follow: bool) -> str:
    """One sentence: which paths and moves were searched, which were not."""
    if not path:
        s = "path-free, HEAD history"
    elif follow:
        s = f"HEAD history of {path}, renames followed"
    else:
        s = f"HEAD history of {path} (pre-move paths not searched)"
    pre = project_prefix(repo)
    return s + (f"; only the project's folder {pre!r} of its repository" if pre else "")


def _rev(repo: Path, rev: str, what: str) -> str:
    """The commit ``rev`` names (a branch, tag, sha, ``HEAD~3``); ValueError when it names none."""
    r = _word(rev, what)
    if not r:
        raise ValueError(f"{what}: a revision is needed")
    if r.startswith("-"):
        raise ValueError(f"{what}: {r!r} is not a revision")
    got = _run_git(repo, "rev-parse", "--verify", "--quiet", "--end-of-options", f"{r}^{{commit}}",
                   timeout=GIT_SHORT_TIMEOUT)
    if got.timed_out:
        raise ValueError(f"{what}: git rev-parse took over {GIT_SHORT_TIMEOUT:g} s")
    sha = got.stdout.strip() if got.returncode == 0 else ""
    if not sha:
        raise ValueError(f"{what}: {r!r} names no commit in this repository")
    return sha


def _when(iso: str) -> datetime | None:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None


def _not_git(kind: str, repo: Path) -> dict:
    return {"status": "not_git", "kind": kind, "note": f"{repo} is not a git work tree with a commit: no history "
                                                       "to search"}


def _header(line: str) -> dict:
    sha, author, date, subject = line[len(_HDR):].split("\x1f", 3)
    return {"commit": sha, "date": date, "author": author, "subject": subject}


def _ev(c: dict, *, path: str | None = None, line: int | None = None, excerpt: str | None = None,
        change: str | None = None) -> dict:
    """``git_history`` evidence for commit ``c``: the diff line when there is one, else the subject. A removed
    line is a line of the parent's file, and its locator says so (``removed from <sha>^:<path>:<line>``)."""
    where = f" {path}:{line}" if path and line else (f" {path}" if path else "")
    if change == "removed" and path and line:
        where = f" removed from {c['commit']}^:{path}:{line}"
    text = excerpt if excerpt is not None else c["subject"]
    meta = {"date": c["date"], "author": c["author"], "subject": c["subject"]}
    if path:
        meta.update({"file": path, "line": line, "change": change})
    return {"source_type": "git_history", "locator": f"commit {c['commit']}{where}", "commit_sha": c["commit"],
            "content_hash": evmod.content_hash(text), "excerpt": text[:300], "meta": meta}


# -- when a text appeared or disappeared ---------------------------------------------------------------------

def _ere_lines(lines: list[str], pattern: str) -> set[int]:
    """The indexes of ``lines`` that git's extended regular expression ``pattern`` matches: ``git grep -E`` over
    them (a temporary file, removed at once), the engine ``git log -G`` selects commits with. ValueError when git
    cannot read the pattern."""
    with tempfile.TemporaryDirectory(prefix="verinoda-history-") as d:
        (Path(d) / "lines.txt").write_bytes("".join(x + "\n" for x in lines).encode("utf-8"))
        r = gitexec.run(d, "grep", "--no-index", "-a", "-h", "-n", "-E", "-e", pattern, "--", "lines.txt",
                        timeout=GIT_TIMEOUT)
    if r.timed_out:
        raise ValueError(f"text: git took over {GIT_TIMEOUT:g} s to match the pattern")
    if r.returncode in (126, 127):
        raise ValueError(f"git could not run: {r.stderr}")
    if r.returncode not in (0, 1):  # 1: no line matched
        raise ValueError(f"text: not a regular expression git reads: {r.stderr.strip()[:200]}")
    return {int(n) - 1 for n, _, _ in (x.partition(":") for x in r.stdout.split("\n")) if n.isdigit()}


def _counter(text: str, regex: bool) -> Callable[[list[str]], list[int]]:
    """Occurrences per line: a literal counts each occurrence, a regex the lines it matches (as -G reads them)."""
    if regex:
        def count(lines: list[str]) -> list[int]:
            hit = _ere_lines(lines, text) if lines else set()
            return [1 if i in hit else 0 for i in range(len(lines))]
        return count
    return lambda lines: [x.count(text) for x in lines]


def _parse_patches(out: str, count: Callable[[list[str]], list[int]]) -> list[dict]:
    """Commits (as git listed them) with, per file, the occurrences its added and removed lines hold and the
    first line of each (new-file line for an addition, parent-file line for a removal), and whether the commit
    created the file (``new_file``: the text may have lived in another file before, D186). A commit whose patch
    has a binary file is marked ``binary``: such a file has no lines to count."""
    commits: list[dict] = []
    cur: dict | None = None
    f: dict | None = None
    old_ln = new_ln = 0
    pending: list[tuple[dict, str, int, str]] = []  # (file, "added" or "removed", line number, the line)
    for line in out.split("\n"):
        if line.startswith(_HDR):
            cur = {**_header(line), "files": [], "binary": False}
            commits.append(cur)
            f = None
            continue
        if cur is None:
            continue
        if line.startswith("diff --git "):
            f = {"path": None, "added": 0, "removed": 0, "added_at": None, "removed_at": None,
                 "added_line": None, "removed_line": None, "new_file": False}
            cur["files"].append(f)
            in_header = True  # until the first hunk: a removed "-- x" line is "--- x" too
            continue
        if f is None:
            continue
        if in_header and line.startswith("--- "):
            if line == "--- /dev/null":
                f["new_file"] = True
            else:
                f["path"] = f["path"] or _diff_path(line[4:], "a/")
            continue
        if in_header and line.startswith("+++ "):
            if line != "+++ /dev/null":
                f["path"] = _diff_path(line[4:], "b/")
            continue
        if in_header and line.startswith("Binary files ") and line.endswith(" differ"):
            cur["binary"] = True
            continue
        m = _HUNK.match(line)
        if m:
            old_ln, new_ln = int(m.group(1)), int(m.group(2))
            in_header = False
            continue
        if in_header:
            continue
        if line.startswith("+"):
            pending.append((f, "added", new_ln, line[1:]))
            new_ln += 1
        elif line.startswith("-"):
            pending.append((f, "removed", old_ln, line[1:]))
            old_ln += 1
    for (f, side, ln, body), n in zip(pending, count([p[3] for p in pending])):
        if n:
            f[side] += n
            if f[f"{side}_at"] is None:
                f[f"{side}_at"], f[f"{side}_line"] = ln, body.strip()
    for c in commits:
        c["files"] = [x for x in c["files"] if x["path"] and (x["added"] or x["removed"])]
    return commits


_ESC = {"\\": "\\", '"': '"', "t": "\t", "n": "\n", "r": "\r", "a": "\a", "b": "\b", "f": "\f", "v": "\v"}


def _diff_path(p: str, prefix: str) -> str:
    """A path of a ``---``/``+++`` line; git quotes one with a control character, a quote or a backslash (other
    characters stay as they are with core.quotepath off)."""
    p = p.rstrip("\t")
    if len(p) > 1 and p.startswith('"') and p.endswith('"'):
        raw, out, i = p[1:-1], bytearray(), 0
        while i < len(raw):
            ch = raw[i]
            if ch == "\\" and i + 1 < len(raw):
                if raw[i + 1:i + 4].isdigit() and len(raw[i + 1:i + 4]) == 3:
                    out.append(int(raw[i + 1:i + 4], 8) & 0xFF)
                    i += 4
                    continue
                out += _ESC.get(raw[i + 1], raw[i + 1]).encode("utf-8")
                i += 2
                continue
            out += ch.encode("utf-8")
            i += 1
        p = out.decode("utf-8", "replace")
    return p[len(prefix):] if p.startswith(prefix) else p


def _at_head(repo: Path, text: str, regex: bool, spec: list[str]) -> dict:
    """The lines at HEAD that hold the text (``git grep``, binary files left out): how many (counted per file by
    git) and the first :data:`MAX_SITES` of them, read from the first files only. ``present`` is None when git
    timed out: whether HEAD holds the text is then not known."""
    kind = "-E" if regex else "-F"
    counted = _run_git(repo, _LIT, "grep", "-c", "-I", "--null", kind, "-e", text, "HEAD", *spec)
    if counted.timed_out:
        return {"present": None, "count": None, "sites": [], "truncated": False, "timed_out": True}
    per_file: list[tuple[str, int]] = []
    for line in (counted.stdout if counted.returncode == 0 else "").splitlines():
        where, _, n = line.partition("\x00")
        per_file.append((where[len("HEAD:"):] if where.startswith("HEAD:") else where, int(n) if n.isdigit() else 0))
    count = sum(n for _, n in per_file)
    sites: list[dict] = []
    if per_file:
        out = _git(repo, _LIT, "grep", "-n", "-I", "--null", f"--max-count={MAX_SITES}", kind,
                   "-e", text, "HEAD", "--", *(p for p, _ in per_file[:MAX_SITES]))
        for line in (out or "").splitlines():
            parts = line.split("\x00", 2)
            if len(parts) < 3 or not parts[1].isdigit():
                continue
            where, ln, body = parts
            sites.append({"path": where[len("HEAD:"):] if where.startswith("HEAD:") else where, "line": int(ln),
                          "text": body.strip()[:200]})
            if len(sites) == MAX_SITES:
                break
    return {"present": count > 0, "count": count, "sites": sites, "truncated": count > len(sites)}


def text_history(repo: Path, text: str, *, regex: bool = False, path: str | None = None) -> dict:
    """When ``text`` (a literal; with ``regex``, an extended regular expression) appeared and, when HEAD no
    longer has it, disappeared: the commits that added and removed it, oldest first, and claims citing them.
    With a path, the path-free oldest commit is read as well (:func:`oldest_appearance`): a text born in another
    file is said so, ``earlier_elsewhere`` names the commit, ``appeared`` carries ``scope: under <path>`` and
    ``first_appearance`` the proven path-free commit (D186)."""
    repo = Path(repo)
    t = _word(text, "text")
    if not t:
        raise ValueError("text: give the text (or with regex, the pattern) to look for")
    if regex:
        _ere_lines([], t)  # a pattern git cannot read is the caller's error, before any history is read
    base = {"kind": "text", "text": t, "regex": bool(regex), "path": _word(path, "path")}
    bad = _probe(repo, "text")
    if bad:
        return {**base, **bad}
    spec, rel = _scope(repo, path)
    follow = _one_file(repo, path)
    scope = _scope_text(repo, base["path"], follow)
    pick = f"-G{t}" if regex else f"-S{t}"
    got = _run_git(repo, _LIT, "log", pick, f"-n{MAX_EVENTS + 1}", _FMT, "-p", "-U0",
                   *(_DIFF_FOLLOW if follow else _DIFF_SAFE), *rel, *spec)
    if got.timed_out:
        return {**base, **_partial(f"git log {pick[:2]}<text> over the {scope}, {GIT_TIMEOUT:g} s: no commit was "
                                   "read", _NEXT_NARROW, scope=scope), "events": [], "claims": [], "unknowns": []}
    if got.returncode != 0:
        raise ValueError(f"git log {pick[:2]} failed (a pattern git cannot read): {got.stderr.strip()[:200]}")
    listed = _parse_patches(got.stdout, _counter(t, bool(regex)))
    more = len(listed) > MAX_EVENTS
    events = [c for c in reversed(listed[:MAX_EVENTS]) if c["files"]]  # oldest first
    shallow = _shallow(repo)
    now = _at_head(repo, t, bool(regex), spec)
    limits = ["history reachable from HEAD only (other branches are not searched)",
              "merge commits are not diffed: a text a merge alone introduced or removed is not seen",
              (f"renames of {base['path']} followed: its history before a move is read" if follow else
               "no rename detection: a moved file's text is removed from the old path and added at the new one"),
              "a binary file has no lines to read"]
    if regex:
        limits.append("the regex is git's (POSIX extended: [0-9] or [[:digit:]], not \\d)")
    if project_prefix(repo):
        limits.append(f"only the project's folder {project_prefix(repo)!r} of its git repository")
    res = {**base, "status": "found" if events else "not_found", "scope": scope, "more": more,
           "events": [_event(c) for c in events], "at_head": now, "shallow": shallow,
           "coverage": {"method": f"git log {pick[:2]} over the history of HEAD, zero-context patches; "
                                  "git grep at HEAD", "limits": limits},
           "claims": [], "unknowns": []}
    if now.get("timed_out"):
        res["unknowns"].append({"question": f"is {t!r} at HEAD?", "why": f"git grep at HEAD took over {GIT_TIMEOUT:g} s",
                                "next_step": _NEXT_NARROW})
    if not events:
        selected = listed[:MAX_EVENTS]
        if selected and any(c["binary"] for c in selected):
            why = (f"git selected {len(selected)} commit(s), but they changed it only in binary files, which have "
                   "no lines to read (git grep leaves binary files out too)")
        elif selected:
            why = f"git selected {len(selected)} commit(s), but none of their changed lines holds it"
        else:
            why = "no commit reachable from HEAD added or removed it" + (" (a shallow clone)" if shallow else "")
        if not now["present"]:
            step = ("check the spelling or search without --path; `verinoda history commits --diff PATTERN` "
                    "matches changed lines by regex")
        elif shallow:
            step = "the clone is shallow: `git fetch --unshallow`, then ask again"
        else:
            step = (f"it is at HEAD, so a merge commit (not diffed here) brought it in: `git log -m --first-parent "
                    f"{pick[:2]}<text>` diffs each merge against its first parent")
        res["unknowns"].append({"question": f"when did {t!r} appear?", "why": why, "next_step": step})
        return res
    complete = not more and not shallow
    why_not = ("the history is cut at %d commits: an older commit may have added it first" % MAX_EVENTS
               if more else "a shallow clone: the commits before its boundary are missing")
    first = next((c for c in events if any(f["added"] for f in c["files"])), None)
    if first is not None:
        f = next(x for x in first["files"] if x["added"])
        claim = {"kind": "history", "status": "primary_source_verified" if complete else "strong_inference",
                 "text": f"`{t}` first appeared in commit {first['commit'][:10]} ({first['date'][:10]}, "
                         f"{first['author']}): {first['subject']} - added at {f['path']}:{f['added_at']}"
                         + (f" (history under {base['path']})" if base["path"] else ""),
                 "evidence": [_ev(first, path=f["path"], line=f["added_at"], excerpt="+" + (f["added_line"] or ""),
                                  change="added")],
                 "subjects": [f["path"]]}
        if not complete:
            claim["uncertainties"] = [why_not]
        if base["path"]:   # the path-bound reading may be blind to an older life of the text in another file
            _past_the_path(repo, res, claim, t, bool(regex), first, f)
        # under a path, `appeared` is what arrived there and is labelled so: read on its own it was taken for
        # the first appearance when the claim beside it named an older commit (D186, the guzzle class)
        res["appeared"] = {"commit": first["commit"], "at": f"{f['path']}:{f['added_at']}", **_under(base["path"])}
        res["claims"].append(claim)
    else:
        res["unknowns"].append({"question": f"when did {t!r} appear?",
                                "why": "the commits found only removed it: " + (why_not if not complete else
                                                                                "it was added before them"),
                                "next_step": "search without --path (it may have come from another file)"})
    if now["present"] is False:   # None: git grep timed out, so nothing is said about a disappearance
        last = next((c for c in reversed(events) if any(f["removed"] for f in c["files"])), None)
        if last is not None:
            f = next(x for x in last["files"] if x["removed"])
            res["claims"].append({
                "kind": "history", "status": "primary_source_verified",
                "text": f"`{t}` disappeared in commit {last['commit'][:10]} ({last['date'][:10]}, {last['author']}): "
                        f"{last['subject']} - removed from {f['path']}:{f['removed_at']}; HEAD has no occurrence"
                        + (f" under {base['path']}" if base["path"] else ""),
                "evidence": [_ev(last, path=f["path"], line=f["removed_at"],
                                 excerpt="-" + (f["removed_line"] or ""), change="removed")],
                "subjects": [f["path"]]})
            res["disappeared"] = {"commit": last["commit"], "at": f"{f['path']}:{f['removed_at']}",
                                  **_under(base["path"])}
        else:
            res["unknowns"].append({
                "question": f"when did {t!r} disappear?",
                "why": "HEAD has no occurrence, but no commit read removed it: a merge commit (merges are not "
                       "diffed) or a change to a binary file removed it",
                "next_step": f"`git log -m --first-parent {pick[:2]}<text>` diffs each merge against its first "
                             "parent"})
    return res


def _under(path: str | None) -> dict:
    """The scope label of a path-bound ``appeared`` or ``disappeared``; nothing without a path (the result's
    ``scope`` says path-free then)."""
    return {"scope": f"under {path}"} if path else {}


def _event(c: dict) -> dict:
    added = [f for f in c["files"] if f["added"]]
    return {"commit": c["commit"], "date": c["date"], "author": c["author"], "subject": c["subject"],
            "new_file": bool(added) and all(f["new_file"] for f in added),   # the text arrived with the file
            "files": [{"path": f["path"], "added": f["added"], "removed": f["removed"],
                       **({"added_at": f["added_at"]} if f["added"] else {}),
                       **({"removed_at": f["removed_at"]} if f["removed"] else {})} for f in c["files"]]}


def oldest_appearance(repo: Path, text: str, *, regex: bool = False) -> dict | None:
    """The oldest commit of HEAD's history that changed how often ``text`` occurs (``-S``; with ``regex``, the
    oldest whose changed lines match it, ``-G``), read path-free and oldest first: ``git log`` lists every such
    commit (no ``-n``: the newest-first cut of :func:`text_history` drops the oldest, the one wanted here), the
    last line is the oldest, and ``git show -U0`` of that one commit gives the file and line it added the text at
    (0.2 to 2.7 s on the ten study clones, D186). ``{"sha", "date", "author", "subject", "path", "line", "text"}``,
    the last three None when that commit only removed it; None when no commit changed it; ``{"timed_out": True}``
    when git took over :data:`GIT_TIMEOUT` s. In a sub-project only the project's folder is read."""
    repo = Path(repo)
    t = _word(text, "text")
    if not t:
        raise ValueError("text: give the text to look for")
    spec, rel = _scope(repo, None)
    pick = f"-G{t}" if regex else f"-S{t}"
    listed = _run_git(repo, _LIT, "log", pick, "--format=%H%x1f%aI%x1f%an%x1f%s", *_DIFF_SAFE, *spec)
    if listed.timed_out:
        return {"timed_out": True}
    if listed.returncode != 0:
        raise ValueError(f"git log {pick[:2]} failed (a pattern git cannot read): {listed.stderr.strip()[:200]}")
    lines = [x for x in listed.stdout.split("\n") if x]
    if not lines:
        return None
    sha, date, author, subject = (lines[-1].split("\x1f", 3) + [""] * 4)[:4]
    out = {"sha": sha, "date": date, "author": author, "subject": subject, "path": None, "line": None, "text": None}
    shown = _run_git(repo, _LIT, "show", "-U0", *_DIFF_SAFE, _FMT, "--end-of-options", sha, *rel, *spec)
    if shown.timed_out:
        return {"timed_out": True}
    if shown.returncode == 0:
        for c in _parse_patches(shown.stdout, _counter(t, bool(regex))):
            for f in c["files"]:
                if f["added"]:
                    out.update(path=f["path"], line=f["added_at"], text=f["added_line"])
                    return out
    return out


def _past_the_path(repo: Path, res: dict, claim: dict, text: str, regex: bool, first: dict, f: dict) -> None:
    """The path-free oldest commit against the path-bound first event (D186). A text can be born in another
    file: when the first event under the path created the file (the guzzle class), the first appearance is the
    path-free one and the claim is re-made from it; when it modified the file and an older commit added the text
    elsewhere (the gin class), the claim names that commit as a lead. Both set ``earlier_elsewhere``. A first
    appearance the path-free read proved (re-made, or the same commit) is ``first_appearance`` too, labelled
    ``path-free``, beside the path-bound ``appeared``. A path-free read that times out leaves a created-file
    claim one step down, with the reason."""
    created = f["new_file"]
    oldest = oldest_appearance(repo, text, regex=regex)
    if oldest is None or oldest.get("timed_out"):
        if created:
            claim["status"] = "strong_inference"
            claim.setdefault("uncertainties", []).extend([
                (f"created at this path: {f['path']} arrived with the text in {first['commit'][:10]}, which may "
                 "have lived in another file before"),
                f"path-free search timed out after {GIT_TIMEOUT:g} s" if oldest else
                "the path-free search found no commit that added it"])
        return
    if oldest["sha"] == first["commit"]:
        if created and not res["shallow"]:   # the whole history was read for this: nothing lived elsewhere before
            claim["status"] = "primary_source_verified"
            claim.pop("uncertainties", None)
            claim["text"] += " (path-free: the oldest commit that added it anywhere in the project)"
            res["scope"] += "; the first appearance read path-free: the same commit"
            res["first_appearance"] = {"commit": first["commit"], "at": f"{f['path']}:{f['added_at']}",
                                       "scope": "path-free"}
        return
    then, here = _when(oldest["date"]), _when(first["date"])
    if then is None or here is None or then >= here:
        return
    res["earlier_elsewhere"] = {"sha": oldest["sha"], "date": oldest["date"], "subject": oldest["subject"]}
    lead = f"{oldest['sha'][:10]} {oldest['date'][:10]} {oldest['subject'][:90]}"
    if created and oldest["path"]:
        # the path-bound first event only brought the text here: the first appearance is the path-free one
        c = {"commit": oldest["sha"], "date": oldest["date"], "author": oldest["author"], "subject": oldest["subject"]}
        claim["text"] = (f"`{text}` first appeared in commit {c['commit'][:10]} ({c['date'][:10]}, {c['author']}): "
                         f"{c['subject']} - added at {oldest['path']}:{oldest['line']} (path-free; under "
                         f"{res['path']} it arrived in {first['commit'][:10]}, which created {f['path']})")
        claim["evidence"] = [_ev(c, path=oldest["path"], line=oldest["line"], excerpt="+" + (oldest["text"] or ""),
                                 change="added")]
        claim["subjects"] = [oldest["path"]]
        claim["status"] = "strong_inference" if res["shallow"] else "primary_source_verified"
        claim["uncertainties"] = [(f"the history under {res['path']} starts at {first['commit'][:10]}, which "
                                   f"created {f['path']} with the text")] \
            + (["a shallow clone: the commits before its boundary are missing"] if res["shallow"] else [])
        res["scope"] += "; the first appearance read path-free (the whole HEAD history)"
        res["first_appearance"] = {"commit": oldest["sha"], "at": f"{oldest['path']}:{oldest['line']}",
                                   "scope": "path-free"}
    else:
        claim.setdefault("uncertainties", []).append(f"the text existed earlier at another path: {lead}")


# -- commit search -------------------------------------------------------------------------------------------

def commits(repo: Path, *, message: str | None = None, author: str | None = None, path: str | None = None,
            since: str | None = None, until: str | None = None, diff: str | None = None,
            limit: int = 20) -> dict:
    """Commits reachable from HEAD, newest first, whose message matches ``message``, whose author (name or
    e-mail) matches ``author``, that touch ``path``, fall between ``since`` and ``until`` (any date git reads:
    ``2026-01-31``, ``2 weeks ago``) and, with ``diff``, whose added or removed lines match that regular
    expression. Message, author and diff patterns ignore case. Each commit lists the files it changed (with
    ``diff``: the files whose lines matched)."""
    repo = Path(repo)
    limit = max(1, min(int(limit), MAX_COMMITS))
    filters = {k: v for k, v in (("message", _word(message, "message")), ("author", _word(author, "author")),
                                 ("path", _word(path, "path")), ("since", _word(since, "since")),
                                 ("until", _word(until, "until")), ("diff", _word(diff, "diff"))) if v}
    base = {"kind": "commits", "filters": filters}
    bad = _probe(repo, "commits")
    if bad:
        return {**base, **bad}
    spec, rel = _scope(repo, path)
    follow = _one_file(repo, path)
    scope = _scope_text(repo, filters.get("path"), follow)
    # all three patterns are extended regular expressions (--grep and --author read basic ones without -E)
    args = [_LIT, "log", f"-n{limit + 1}", _FMT, "--name-only", *(_DIFF_FOLLOW if follow else _DIFF_SAFE), *rel,
            "--regexp-ignore-case", "--extended-regexp"]
    if "message" in filters:
        args.append(f"--grep={filters['message']}")
    if "author" in filters:
        args.append(f"--author={filters['author']}")
    if "since" in filters:
        args.append(f"--since={filters['since']}")
    if "until" in filters:
        args.append(f"--until={filters['until']}")
    if "diff" in filters:
        args.append(f"-G{filters['diff']}")
    got = _run_git(repo, *args, *spec)
    if got.timed_out:
        return {**base, **_partial(f"git log over the {scope}, {GIT_TIMEOUT:g} s: no commit was read", _NEXT_NARROW,
                                   scope=scope), "commits": []}
    if got.returncode != 0:
        raise ValueError(f"git log failed (a pattern or date git cannot read): {got.stderr.strip()[:200]}")
    found: list[dict] = []
    for line in got.stdout.split("\n"):
        if line.startswith(_HDR):
            found.append({**_header(line), "files": []})
        elif line.strip() and found:
            found[-1]["files"].append(line.strip())
    for c in found:
        c["evidence"] = _ev(c)
    limits = ["history reachable from HEAD only",
              "message, author and diff patterns are git's extended regular expressions (POSIX: [0-9], not \\d), "
              "case ignored; a merge commit's diff is not searched"]
    if project_prefix(repo):
        limits.append(f"only the project's folder {project_prefix(repo)!r} of its git repository")
    more = len(found) > limit
    return {**base, "status": "found" if found else "not_found", "scope": scope, "commits": found[:limit],
            "more": more, **({"next_step": _more_step(limit)} if more else {}),
            "coverage": {"method": "git log over the history of HEAD, newest first", "limits": limits}}


def _more_step(limit: int) -> str:
    return f"limit={min(MAX_COMMITS, limit * 2)} lists more (up to {MAX_COMMITS})"


# -- two revisions -------------------------------------------------------------------------------------------

def compare(repo: Path, base_rev: str, head_rev: str, *, path: str | None = None) -> dict:
    """What ``head_rev`` has that ``base_rev`` has not: the commits of ``base..head`` (newest first), the merge
    base, and the files that differ between the two trees with their added and removed line counts."""
    repo = Path(repo)
    out_base = {"kind": "compare", "base": {"rev": base_rev}, "head": {"rev": head_rev}, "path": _word(path, "path")}
    bad = _probe(repo, "compare")
    if bad:
        return {**out_base, **bad}
    a = _rev(repo, base_rev, "base")
    b = _rev(repo, head_rev, "head")
    out_base["base"]["commit"], out_base["head"]["commit"] = a, b
    spec, rel = _scope(repo, path)
    scope = f"{a[:10]}..{b[:10]}" + (f" under {out_base['path']}" if out_base["path"] else "") \
        + (f"; only the project's folder {project_prefix(repo)!r} of its repository" if project_prefix(repo) else "")
    mb = (_git(repo, "merge-base", "--end-of-options", a, b) or "").strip() or None
    log = _run_git(repo, _LIT, "log", f"-n{MAX_COMMITS + 1}", _FMT, "--end-of-options", f"{a}..{b}", *spec)
    if log.timed_out:
        return {**out_base, **_partial(f"git log {a[:10]}..{b[:10]}, {GIT_TIMEOUT:g} s: no commit was read",
                                       _NEXT_NARROW, scope=scope), "merge_base": mb, "commits": [], "files": []}
    only_head = [_header(x) for x in (log.stdout if log.returncode == 0 else "").split("\n") if x.startswith(_HDR)]
    back = _git(repo, _LIT, "rev-list", "--count", "--end-of-options", f"{b}..{a}", *spec)
    status = _git(repo, _LIT, "diff", "--name-status", "-z", *_DIFF_SAFE, *rel, "--end-of-options", a, b, *spec)
    numstat = _git(repo, _LIT, "diff", "--numstat", "-z", *_DIFF_SAFE, *rel, "--end-of-options", a, b, *spec)
    if status is None or numstat is None:
        raise ValueError("git diff failed between the two revisions")
    kinds = {}
    parts = status.split("\x00")
    for i in range(0, len(parts) - 1, 2):
        if parts[i]:
            kinds[parts[i + 1]] = {"A": "added", "D": "deleted", "M": "modified", "T": "type changed"}.get(
                parts[i][:1], parts[i])
    files = []
    for rec in numstat.split("\x00"):
        m = re.match(r"^(-|\d+)\t(-|\d+)\t(.*)$", rec, re.S)
        if not m:
            continue
        p = m.group(3)
        files.append({"path": p, "change": kinds.get(p, "modified"),
                      "added": None if m.group(1) == "-" else int(m.group(1)),
                      "removed": None if m.group(2) == "-" else int(m.group(2))})
    files.sort(key=lambda f: f["path"])
    same = a == b
    return {**out_base, "status": "same" if same else "found", "scope": scope, "merge_base": mb,
            "more": len(only_head) > MAX_COMMITS or len(files) > MAX_FILES,
            "commits": only_head[:MAX_COMMITS], "commits_truncated": len(only_head) > MAX_COMMITS,
            "commits_only_in_base": int(back.strip()) if back and back.strip().isdigit() else None,
            "files": files[:MAX_FILES], "files_truncated": len(files) > MAX_FILES,
            "totals": {"files": len(files), "added": sum(f["added"] or 0 for f in files),
                       "removed": sum(f["removed"] or 0 for f in files)},
            "coverage": {"method": "git log base..head, git diff base head (the two trees, not the working tree)",
                         "limits": ["a renamed file is listed as deleted and added",
                                    "binary files have no line counts (null)"]
                         + ([f"only the project's folder {project_prefix(repo)!r} of its git repository"]
                            if project_prefix(repo) else [])}}


# -- files that change together ------------------------------------------------------------------------------

COUPLING_COMMITS = 1000    # most recent commits read for co-change
COUPLING_BULK = 30         # a commit changing more files than this (a reformat, a mass rename) is left out
COUPLING_MIN_SHARED = 3    # commits a file must share with the target
COUPLING_MIN_DEGREE = 0.3  # share of the target's commits that also changed the file
COUPLING_SHOWN = 20        # coupled files listed
COUPLING_EVIDENCE = 3      # shared commits quoted per coupled file (newest first)


def co_changes(repo: Path, files: list[str], *, linked: dict[str, set[str]] | None = None,
               skip: set[str] | frozenset[str] = frozenset(), max_commits: int = COUPLING_COMMITS) -> dict:
    """Files that changed together with ``files`` in the recent history of HEAD: for each target, the files that
    changed in at least :data:`COUPLING_MIN_SHARED` of the commits that changed it and in at least
    :data:`COUPLING_MIN_DEGREE` of them. ``linked`` maps a target to the files a graph edge joins it to and
    ``skip`` names files listed elsewhere already; both are left out, as are the targets themselves and files
    missing from the working tree. Each coupled file is a ``temporal_coupling`` claim, ``strong_inference`` (a
    pattern in the history, never a proven dependency), whose evidence is the newest commits it shares."""
    repo = Path(repo)
    targets = sorted({f.replace("\\", "/") for f in files if f})
    limits = ["history reachable from HEAD only, merge commits left out",
              f"commits changing more than {COUPLING_BULK} files are left out (reformats, mass renames)",
              "no rename detection: a file's history before a move is not joined to it",
              "file level only: functions that change together are not told apart",
              "changing together is a pattern in the history, not a dependency"]
    if project_prefix(repo):
        limits.append(f"only the project's folder {project_prefix(repo)!r} of its git repository")
    coverage = {"method": f"git log --name-only over the last {max_commits} commits of HEAD; a file is coupled to a "
                          f"target when it changed in >= {COUPLING_MIN_SHARED} and >= "
                          f"{round(COUPLING_MIN_DEGREE * 100)}% of the commits that changed the target"
                          + (" and no graph edge links the two files" if linked is not None else ""),
                "limits": limits}
    is_git = _is_git(repo)
    if not targets or not is_git:
        return {"is_git": is_git, "commits_read": 0, "bulk_skipped": 0, "coupled": [], "coverage": coverage}
    spec, rel = _scope(repo, None)
    out = _git(repo, "log", f"-n{max_commits}", "--no-merges", _FMT, "--name-only", *_DIFF_SAFE, *rel, *spec)
    if out is None:  # a timeout or an unreadable object store: no reading, which is not "nothing coupled"
        return {"is_git": True, "commits_read": 0, "bulk_skipped": 0, "coupled": [], "coverage": coverage,
                "error": f"git log failed (it took over {GIT_TIMEOUT:g} s, or the repository could not be read): "
                         "co-change was not read"}
    shallow = _shallow(repo)
    if shallow:
        limits.append("a shallow clone: the commits before its boundary are missing (git fetch --unshallow)")
    commits: list[dict] = []
    for line in out.split("\n"):
        if line.startswith(_HDR):
            commits.append({**_header(line), "files": set()})
        elif line.strip() and commits:
            commits[-1]["files"].add(line.strip())
    kept = [c for c in commits if len(c["files"]) <= COUPLING_BULK]
    want = set(targets)
    best: dict[str, tuple[int, float, str, int, list[dict]]] = {}  # file -> its strongest coupling
    for t in targets:
        mine = [c for c in kept if t in c["files"]]  # newest first
        if len(mine) < COUPLING_MIN_SHARED:
            continue
        shared: dict[str, list[dict]] = {}
        for c in mine:
            for f in c["files"]:
                if f != t:
                    shared.setdefault(f, []).append(c)
        near = (linked or {}).get(t, set())
        for f, cs in shared.items():
            degree = len(cs) / len(mine)
            if (len(cs) < COUPLING_MIN_SHARED or degree < COUPLING_MIN_DEGREE or f in want or f in near
                    or f in skip or not (repo / f).is_file()):
                continue
            row = (len(cs), degree, t, len(mine), cs)
            if f not in best or row[:2] > best[f][:2]:
                best[f] = row
    order = sorted(best.items(), key=lambda kv: (-kv[1][0], -kv[1][1], kv[0]))
    coupled = []
    for f, (n, degree, t, n_t, cs) in order[:COUPLING_SHOWN]:
        coupled.append({
            "kind": "temporal_coupling", "status": "strong_inference", "file": f, "coupled_to": t, "commits": n,
            "target_commits": n_t, "degree": round(degree, 2),
            "text": f"{f} changed in {n} of the {n_t} commits that changed {t} (last {len(commits)} commits read)"
                    + ("; no graph edge links the two files" if linked is not None else ""),
            "evidence": [_pair_ev(c, t, f) for c in cs[:COUPLING_EVIDENCE]],
            "uncertainties": ["changing together is a pattern in the history, not a proven dependency"],
            "subjects": [f, t]})
    return {"is_git": True, "commits_read": len(commits), "bulk_skipped": len(commits) - len(kept),
            "coupled": coupled, **({"truncated": True} if len(order) > COUPLING_SHOWN else {}),
            **({"shallow": True} if shallow else {}), "coverage": coverage}


def _pair_ev(c: dict, target: str, other: str) -> dict:
    """``git_history`` evidence that commit ``c`` changed both ``target`` and ``other``."""
    ev = _ev(c, path=other)
    ev["locator"] = f"commit {c['commit']} {target} and {other}"
    ev["meta"]["files"] = [target, other]
    return ev


# -- the commits that changed a symbol -----------------------------------------------------------------------

MAX_BODY_LINES = 12   # lines of a commit message body quoted
_SPAN = re.compile(r"^(?P<path>.+):(?P<a>\d+)-(?P<b>\d+)$")
# trailers that name people or tooling, not reasons ("Reason:", "Note:" or "See:" lines are kept)
_TRAILER = re.compile(r"(?i)^(signed-off-by|co-authored-by|reviewed-by|acked-by|tested-by|reported-by|suggested-by"
                      r"|helped-by|cc|change-id|git-svn-id): \S")


def _head_lines(repo: Path, rel: str, a: int, b: int) -> tuple[tuple[int, int] | None, str | None]:
    """Lines ``a``-``b`` of the working-tree file ``rel`` as HEAD's lines (``git log -L`` starts from HEAD),
    and a note when they had to be mapped. ``(None, why)`` when HEAD has no such file or none of the lines."""
    head = _git(repo, "show", f"HEAD:./{rel}")
    if head is None:
        return None, f"{rel} is not in HEAD (not committed yet)"
    head = head.replace("\r\n", "\n")
    n_head = len(head.split("\n")) - (1 if head.endswith("\n") else 0)
    if not (repo / rel).exists():
        if a > n_head:
            return None, f"{rel} is not in the working tree and has {n_head} lines at HEAD"
        return (a, min(b, n_head)), f"{rel} is not in the working tree: lines {a}-{min(b, n_head)} are HEAD's"
    try:
        cur = (repo / rel).read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    except OSError:
        return None, f"{rel} cannot be read"
    n_cur = len(cur.split("\n")) - (1 if cur.endswith("\n") else 0)
    if a > n_cur:
        raise ValueError(f"{rel} has {n_cur} lines; the range starts at line {a}")
    b = min(b, n_cur)
    if head == cur:
        return (a, b), None
    from verinoda.hotspots import _line_map

    m = _line_map(head, cur)
    old = [i + 1 for i, ln in enumerate(m) if a <= ln <= b]
    if not old:
        return None, f"lines {a}-{b} of {rel} are all new since HEAD (not committed yet)"
    return (min(old), max(old)), (f"{rel} differs from HEAD: lines {a}-{b} were mapped to HEAD's lines "
                                  f"{min(old)}-{max(old)} by a text diff")


def symbol_commits(repo: Path, rel: str, a: int, b: int, *, limit: int = 10, rev: str | None = None,
                   probe: bool = True) -> dict:
    """The commits reachable from HEAD that changed lines ``a``-``b`` of ``rel`` (working-tree lines), newest
    first, as git's ``log -L`` follows the range back through the file's history, each with its whole message
    (subject, and the body up to :data:`MAX_BODY_LINES` lines) and ``git_history`` evidence quoting it.
    ``{"status": "found" | "not_found" | "not_committed" | "not_git" | "partial", "commits", "head_lines", "note",
    "more", "shallow"}``. ``rev`` (a commit): the lines are that commit's and its history is read. ``probe=False``:
    the caller already knows this is a git work tree (no ``rev-parse`` per call; ``shallow`` is then not read)."""
    repo = Path(repo)
    limit = max(1, min(int(limit), MAX_COMMITS))
    if probe:
        bad = _probe(repo, "symbol")
        if bad:
            return bad
    if rev:
        rev = _rev(repo, rev, "rev")   # set only by callers of this module; checked all the same (D186)
        span, note = (a, b), None
    else:
        span, note = _head_lines(repo, rel, a, b)
        if span is None:
            return {"status": "not_committed", "commits": [], "note": note}
    fmt = f"--format={_HDR}%H%x1f%an%x1f%aI%x1f%P%x1f%B"
    where = f"{rel}:{span[0]}-{span[1]}"
    got = _run_git(repo, "log", f"-n{limit + 1}", f"-L{span[0]},{span[1]}:{rel}", "--no-patch", "--no-ext-diff",
                   "--no-textconv", "--no-color", fmt, *(["--end-of-options", rev] if rev else []))
    if got.timed_out:
        return {**_partial(f"git log -L {where} over the HEAD history, {GIT_TIMEOUT:g} s: no commit was read",
                           f"raise VERINODA_MCP_GIT_TIMEOUT (now {GIT_TIMEOUT:g} s) and ask again, or history_search "
                           f"with text=<a line of the symbol> and path={rel}"),
                "commits": [], "head_lines": list(span), "shallow": None,
                "note": f"git log -L {where} timed out after {GIT_TIMEOUT:g} s: its commits were not read"}
    if got.returncode != 0:
        raise ValueError(f"git log -L could not read {where} at HEAD: {got.stderr.strip()[:200]}")
    found: list[dict] = []
    for block in got.stdout.split(_HDR)[1:]:
        sha, author, date, parents, msg = (block.split("\x1f", 4) + [""] * 5)[:5]
        lines = msg.strip("\n").splitlines()
        subject = lines[0].strip() if lines else ""
        body = lines[1:]
        while body and not body[0].strip():
            body.pop(0)
        while body and not body[-1].strip():
            body.pop()
        # a closing block of people trailers (Signed-off-by:, Co-Authored-By:) names people, not reasons
        k = len(body)
        while k and _TRAILER.match(body[k - 1]):
            k -= 1
        if k < len(body) and (k == 0 or not body[k - 1].strip()):
            body = body[:k]
            while body and not body[-1].strip():
                body.pop()
        c = {"commit": sha.strip(), "date": date, "author": author, "subject": subject,
             "body": "\n".join(body[:MAX_BODY_LINES]), "body_truncated": len(body) > MAX_BODY_LINES,
             "merge": len(parents.split()) > 1}
        quote = subject + ("\n\n" + c["body"] if c["body"] else "")
        c["evidence"] = _ev(c, path=rel, excerpt=quote)
        c["evidence"]["locator"] = f"commit {c['commit']} {rel}"
        c["evidence"]["meta"]["head_lines"] = list(span)
        found.append(c)
    return {"status": "found" if found else "not_found", "commits": found[:limit], "more": len(found) > limit,
            "head_lines": list(span), "note": note, "shallow": _shallow(repo) if probe else None}


def _project_rel(repo: Path, path: str) -> str:
    """``path`` (relative to the project, or absolute) as a '/'-separated path inside the project; ValueError
    for one outside it (the history read is the project's)."""
    p = Path(path.replace("\\", "/"))
    root = repo.resolve()
    full = (p if p.is_absolute() else root / p).resolve()
    try:
        rel = full.relative_to(root).as_posix()
    except ValueError:
        raise ValueError(f"{path} is outside the project {repo}") from None
    if rel in ("", ".") or rel.startswith(".git/"):
        raise ValueError(f"{path} is not a file of the project")
    return rel


def symbol_history(repo: Path, g, target: str, *, stale=(), limit: int = 10) -> dict:
    """Why a symbol is the way it is, from git: the commits that changed its lines, newest first, one row each
    (``sha date author subject``), and ``quoted``, the message bodies of the first and last :data:`QUOTED_EACH_END`
    rows and of any that states a reason, as the author wrote them (D186: a claim per commit repeated every row
    at 28,725 chars of JSON for 5,361 of git output). ``target`` is a name the index resolves exactly
    (``Class.method``, ``path/file.py::name``, a node id) or ``path:A-B``; a name that does not resolve to one
    symbol is answered with its candidates, never replaced by a similar one."""
    from verinoda import naming

    repo = Path(repo)
    base = {"kind": "symbol", "target": target}
    t = _word(target, "target")
    if not t:
        raise ValueError("target: a symbol or path:A-B is needed")
    m = _SPAN.match(t)
    if m:
        rel, a, b = _project_rel(repo, m.group("path")), int(m.group("a")), int(m.group("b"))
        if a < 1 or b < a:
            raise ValueError(f"{t}: the line range must be A-B with 1 <= A <= B")
        label = f"{rel}:{a}-{b}"
    else:
        if g is None:
            return {**base, "status": "unresolved", "note": "no index: run `verinoda scan`, or give path:A-B"}
        res = naming.resolve(g, t, stale=stale)
        if not res.exact:
            return {**base, "status": "ambiguous" if res.status == naming.AMBIGUOUS else "unresolved",
                    "note": res.note or f"{t!r} names no one symbol of the index", "candidates": res.rows(g)}
        sp = g.span(res.node)
        rel = g.file(res.node)
        if not sp or not rel:
            return {**base, "status": "unresolved", "note": f"{g.label(res.node)} has no line span in the index"}
        if rel in set(stale or ()):   # the index's lines are the file's as it was scanned, not as it is now
            return {**base, "status": "stale_index", "symbol": g.label(res.node), "file": rel,
                    "note": f"{rel} changed since the index: its lines for {g.label(res.node)} may have moved; "
                            "run `verinoda update` or give path:A-B"}
        (a, b), label = sp, g.label(res.node)
        if res.note:
            base["resolution_note"] = res.note
    got = symbol_commits(repo, rel, a, b, limit=limit)
    scope = f"HEAD history of {rel}:{a}-{b} (git log -L; a move from another file not followed)" \
        + (f"; only the project's folder {project_prefix(repo)!r} of its repository" if project_prefix(repo) else "")
    out = {**base, **got, "symbol": label, "file": rel, "lines": [a, b], "scope": scope}
    if got["status"] in ("not_git", "not_committed", "partial"):
        return out
    for key in ("note", "shallow"):   # said when there is something to say
        if not out.get(key):
            out.pop(key, None)
    out["commits"] = [_row(c) for c in got["commits"]]
    out["quoted"] = _quoted(got["commits"])
    if got["more"]:
        out["next_step"] = _more_step(limit)
    limits = ["a commit message states the author's intent when committing, not the current behaviour"]
    if got.get("shallow"):
        limits.append("a shallow clone: older commits are missing")
    out["coverage"] = {"method": "git log -L over the symbol's lines at HEAD, newest first", "limits": limits}
    if got["status"] == "not_found":
        out["unknowns"] = [{"why": "no commit reachable from HEAD changed these lines",
                            "next_step": "`verinoda history text` with a line of the symbol"}]
    return out


def _row(c: dict) -> str:
    return f"{c['commit'][:10]} {c['date'][:10]} {c['author']} {c['subject'][:90]}"


def _quoted(commits: list[dict]) -> list[dict]:
    """The message bodies worth their bytes (D186): those of the first and last :data:`QUOTED_EACH_END` rows and
    of any commit whose message states a reason (D185's gold commit was the eleventh of fourteen). A commit
    without a body is not quoted: its row carries the subject."""
    from verinoda.verdict_gate import states_reason

    n = len(commits)
    out = []
    for i, c in enumerate(commits):
        body = c.get("body") or ""
        if not body or not (i < QUOTED_EACH_END or i >= n - QUOTED_EACH_END or states_reason([], c["subject"], body)):
            continue
        cut = len(body) > QUOTE_CHARS or c.get("body_truncated")
        out.append({"sha": c["commit"][:10], "message": body[:QUOTE_CHARS] + ("..." if cut else "")})
    return out


def _render_symbol(res: dict) -> str:
    if res.get("status") in ("unresolved", "ambiguous", "stale_index"):
        out = [f"{res['target']}: {res['status']} - {res.get('note')}"]
        out += [f"  candidate: {c['label']} ({c.get('at')})" for c in res.get("candidates") or []]
        return "\n".join(out)
    where = f"{res['file']}:{res['lines'][0]}-{res['lines'][1]}"
    out = [(where if res["symbol"] == where else f"{res['symbol']} ({where})") + ":"]
    for key in ("resolution_note", "note"):
        if res.get(key):
            out.append(f"  note: {res[key]}")
    if res.get("shallow"):
        out.append("  note: a shallow clone: older commits are missing")
    if res["status"] == "not_committed":
        return "\n".join(out)
    if not res.get("commits"):
        out.append("  no commit reachable from HEAD changed these lines")
    quoted = {q["sha"]: q["message"] for q in res.get("quoted") or []}
    for row in res.get("commits") or []:
        out.append(f"  {row}")
        out += [f"    | {ln}" for ln in quoted.get(row.split(" ", 1)[0], "").splitlines()]
    if res.get("more"):
        out.append(f"  (more: {res.get('next_step') or 'raise --limit'})")
    return "\n".join(out)


# -- rendering -----------------------------------------------------------------------------------------------

def _short(c: dict) -> str:
    return f"{c['commit'][:10]} {c['date'][:10]} {c['author']}: {c['subject']}"


def _label(res: dict) -> str:
    kind = res.get("kind")
    if kind == "text":
        what = f"/{res['text']}/" if res.get("regex") else repr(res["text"])
        return what + (f" under {res['path']}" if res.get("path") else "")
    if kind == "symbol":
        return res.get("symbol") or res["target"]
    if kind == "commits":
        f = res.get("filters") or {}
        return "commits" + (" where " + ", ".join(f"{k}={v!r}" for k, v in f.items()) if f else "")
    return f"{res['base']['rev']} .. {res['head']['rev']}"


def render(res: dict) -> str:
    if res.get("status") == "not_git":
        return res["note"]
    if res.get("status") == "partial":
        return f"{_label(res)}: partial - {res['searched']}\n  next: {res['next_step']}"
    kind = res.get("kind")
    if kind == "text":
        out = [_label(res) + ":"]
        if res.get("scope"):
            out.append(f"  scope: {res['scope']}")
        for c in res.get("claims") or []:
            out.append(f"  [{c['status']}] {c['text']}")
            out += [f"    uncertain: {u}" for u in c.get("uncertainties") or []]
        e = res.get("earlier_elsewhere")
        if e:
            out.append(f"  earlier at another path: {e['sha'][:10]} {e['date'][:10]} {e['subject']}")
        for u in res.get("unknowns") or []:
            out.append(f"  unknown: {u['why']}\n    next: {u['next_step']}")
        if res.get("events"):
            out.append(f"  commits that added or removed it ({len(res['events'])}, oldest first):")
            for e in res["events"]:
                ch = ", ".join(f"{f['path']} +{f['added']}/-{f['removed']}" for f in e["files"][:4])
                out.append(f"    {_short(e)}  [{ch}]" + ("  (created the file)" if e.get("new_file") else ""))
        head = res.get("at_head") or {}
        if head.get("present"):
            out.append(f"  at HEAD: {head['count']} line(s): "
                       + ", ".join(f"{s['path']}:{s['line']}" for s in head["sites"])
                       + (" ..." if head.get("truncated") else ""))
        elif head.get("present") is None:
            out.append("  at HEAD: not known (git grep timed out)")
        else:
            out.append("  at HEAD: none")
        if res.get("more"):
            out.append(f"  (cut at {MAX_EVENTS} commits: narrow with --path)")
        return "\n".join(out)
    if kind == "symbol":
        return _render_symbol(res)
    if kind == "commits":
        out = [_label(res) + ":"]
        if not res.get("commits"):
            out.append("  none")
        for c in res.get("commits") or []:
            out.append(f"  {_short(c)}")
            if c["files"]:
                out.append("    " + ", ".join(c["files"][:6]) + (" ..." if len(c["files"]) > 6 else ""))
        if res.get("more"):
            out.append("  (more: raise --limit or narrow the filters)")
        return "\n".join(out)
    b, h = res["base"], res["head"]
    out = [f"{b['rev']} ({b['commit'][:10]}) .. {h['rev']} ({h['commit'][:10]})"
           + (f" under {res['path']}" if res.get("path") else "")
           + (f"; merge base {res['merge_base'][:10]}" if res.get("merge_base") else "; no merge base")]
    if res["status"] == "same":
        out.append("  the same commit")
        return "\n".join(out)
    out.append(f"  {len(res['commits'])}{'+' if res.get('commits_truncated') else ''} commit(s) only in "
               f"{h['rev']}; {res.get('commits_only_in_base')} only in {b['rev']}")
    for c in res["commits"][:20]:
        out.append(f"    {_short(c)}")
    t = res["totals"]
    out.append(f"  {t['files']} file(s) differ, +{t['added']}/-{t['removed']} lines:")
    for f in res["files"][:40]:
        counts = "binary" if f["added"] is None else f"+{f['added']}/-{f['removed']}"
        out.append(f"    {f['change']:<9} {f['path']} {counts}")
    if len(res["files"]) > 40 or res.get("files_truncated"):
        out.append("    ... (--json lists them)")
    return "\n".join(out)
