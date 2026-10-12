"""Commit, diff and revision search (verinoda/history.py): when a text appeared or disappeared, with the commit
as evidence; commits by message, author, path, date and diff content; two revisions compared."""

from __future__ import annotations

import os

os.environ.setdefault("GRAPHIFY_OUT", ".verinoda/index")

import json  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

from verinoda import cli, history  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not available")


def _git(cwd: Path, *args: str, author: str = "Bob", date: str | None = None) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": author, "GIT_AUTHOR_EMAIL": f"{author.lower()}@example.org",
           "GIT_COMMITTER_NAME": author, "GIT_COMMITTER_EMAIL": f"{author.lower()}@example.org"}
    if date:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = date
    return subprocess.run(["git", "-c", "core.autocrlf=false", "-c", "init.defaultBranch=main",
                           "-c", "commit.gpgsign=false", *args], cwd=cwd, env=env, check=True,
                          capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout.strip()


def _commit(repo: Path, files: dict[str, str | None], msg: str, *, author: str = "Bob", date: str) -> str:
    for rel, text in files.items():
        p = repo / rel
        if text is None:
            p.unlink()
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(text.encode("utf-8"))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg, author=author, date=date)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture(scope="module")
def repo(tmp_path_factory) -> tuple[Path, list[str]]:
    """Five commits: main() first; Alice adds RETRY_BUDGET to svc.py; it is used in job.py; it is dropped from
    both; a SQL comment line (`-- note`, which a zero-context diff shows as `--- note`) is removed."""
    r = tmp_path_factory.mktemp("history") / "proj"
    r.mkdir()
    _git(r, "init", "-q")
    shas = [
        _commit(r, {"svc.py": "def main():\n    return 1\n", "q.sql": "-- note\nselect 1;\n"}, "Initial import",
                date="2026-01-05T10:00:00+00:00"),
        _commit(r, {"svc.py": "def main():\n    RETRY_BUDGET = 3\n    return RETRY_BUDGET\n"},
                "Add Retry budget to the service", author="Alice", date="2026-02-10T10:00:00+00:00"),
        _commit(r, {"lib/job.py": "from svc import main\n\nLIMIT = 1  # RETRY_BUDGET is the service's\n"},
                "Use the retry budget in the job", date="2026-03-15T10:00:00+00:00"),
        _commit(r, {"svc.py": "def main():\n    return 1\n", "lib/job.py": "from svc import main\n\nLIMIT = 1\n"},
                "Drop the retry budget", date="2026-04-20T10:00:00+00:00"),
        _commit(r, {"q.sql": "select 1;\n"}, "Remove the SQL note", date="2026-05-25T10:00:00+00:00"),
    ]
    return r, shas


def test_a_text_that_came_and_went_is_answered_with_both_commits(repo):
    r, shas = repo
    res = history.text_history(r, "RETRY_BUDGET")
    assert res["status"] == "found" and not res["at_head"]["present"]
    assert [e["commit"] for e in res["events"]] == [shas[1], shas[2], shas[3]]  # oldest first
    appeared, gone = res["claims"]
    assert appeared["status"] == "primary_source_verified" and appeared["kind"] == "history"
    assert shas[1][:10] in appeared["text"] and "svc.py:2" in appeared["text"] and "Alice" in appeared["text"]
    ev = appeared["evidence"][0]
    assert ev["source_type"] == "git_history" and ev["commit_sha"] == shas[1]
    assert ev["locator"] == f"commit {shas[1]} svc.py:2" and ev["excerpt"] == "+RETRY_BUDGET = 3"
    assert ev["meta"]["change"] == "added" and ev["meta"]["date"].startswith("2026-02-10")
    assert gone["status"] == "primary_source_verified" and shas[3][:10] in gone["text"]
    assert "HEAD has no occurrence" in gone["text"]
    assert gone["evidence"][0]["meta"]["change"] == "removed" and gone["evidence"][0]["commit_sha"] == shas[3]
    # a removed line is a line of the parent's file, and the locator names the parent
    assert gone["evidence"][0]["locator"] == f"commit {shas[3]} removed from {shas[3]}^:lib/job.py:3"
    assert "RETRY_BUDGET" in _git(r, "show", f"{shas[3]}^:lib/job.py").split("\n")[2]
    assert res["appeared"]["commit"] == shas[1] and res["disappeared"]["commit"] == shas[3]
    counts = {f["path"]: (f["added"], f["removed"]) for f in res["events"][2]["files"]}
    assert counts == {"svc.py": (0, 2), "lib/job.py": (0, 1)}


def test_a_text_still_at_head_has_no_disappearance(repo):
    r, shas = repo
    res = history.text_history(r, "def main")
    assert [c["text"].split(" in commit ")[0] for c in res["claims"]] == ["`def main` first appeared"]
    assert res["appeared"] == {"commit": shas[0], "at": "svc.py:1"}
    assert res["at_head"]["present"] and res["at_head"]["sites"][0] == {"path": "svc.py", "line": 1,
                                                                   "text": "def main():"}


def test_a_path_narrows_the_history(repo):
    r, shas = repo
    res = history.text_history(r, "RETRY_BUDGET", path="lib")
    assert res["appeared"] == {"commit": shas[2], "at": "lib/job.py:3"}
    assert res["disappeared"]["commit"] == shas[3] and "under lib" in res["claims"][1]["text"]


def test_a_regex_matches_changed_lines(repo):
    r, shas = repo
    res = history.text_history(r, r"RETRY_[A-Z]+ = [0-9]", regex=True)  # git's regex: POSIX, no \d
    assert res["regex"] and res["appeared"]["commit"] == shas[1]
    assert res["disappeared"]["commit"] == shas[3]
    with pytest.raises(ValueError, match="not a regular expression"):
        history.text_history(r, "RETRY_(", regex=True)


def test_a_regex_is_git_s_both_to_select_commits_and_to_pick_lines(repo):
    """A POSIX bracket class selects the commits in git; the lines are matched by git too, so they are found."""
    r, shas = repo
    res = history.text_history(r, "RETRY_[[:upper:]]+ = [[:digit:]]", regex=True)
    assert res["appeared"]["commit"] == shas[1] and res["disappeared"]["commit"] == shas[3]
    # \d is not POSIX: git selects nothing, and the answer does not blame a shallow clone
    res = history.text_history(r, r"RETRY_BUDGET = \d", regex=True)
    assert res["status"] == "not_found" and "shallow" not in res["unknowns"][0]["next_step"]


def test_a_catastrophic_python_pattern_is_matched_by_git(tmp_path):
    """No pattern runs in Python's backtracking engine: one that takes exponential time there returns at once."""
    r = tmp_path / "redos"
    r.mkdir()
    _git(r, "init", "-q")
    sha = _commit(r, {"f.txt": "a" * 34 + "!\n"}, "a line of a's", date="2026-01-05T10:00:00+00:00")
    res = history.text_history(r, "(a|a)+c|a", regex=True)
    assert res["appeared"]["commit"] == sha and res["at_head"]["count"] == 1


def test_a_removed_sql_comment_is_a_line_not_a_file_header(repo):
    r, shas = repo
    res = history.text_history(r, "note")
    assert res["disappeared"] == {"commit": shas[4], "at": "q.sql:1"}
    assert res["claims"][1]["evidence"][0]["excerpt"] == "--- note"


def test_nothing_found_is_an_unknown_with_a_next_step(repo):
    r, _ = repo
    res = history.text_history(r, "never_written_anywhere")
    assert res["status"] == "not_found" and not res["claims"]
    assert res["unknowns"] and "next_step" in res["unknowns"][0]
    with pytest.raises(ValueError):
        history.text_history(r, "  ")
    with pytest.raises(ValueError, match="one line"):
        history.text_history(r, "a\nb")


def test_a_shallow_clone_does_not_prove_the_first_appearance(repo, tmp_path):
    r, shas = repo
    clone = tmp_path / "shallow"
    _git(tmp_path, "clone", "-q", "--depth", "1", r.resolve().as_uri(), str(clone))
    res = history.text_history(clone, "def main")
    assert res["shallow"] and res["claims"][0]["status"] == "strong_inference"
    assert "shallow" in res["claims"][0]["uncertainties"][0]


def test_a_cut_history_does_not_prove_the_first_appearance(repo, monkeypatch):
    r, shas = repo
    monkeypatch.setattr(history, "MAX_EVENTS", 2)  # three commits changed it: the oldest is cut
    res = history.text_history(r, "RETRY_BUDGET")
    assert res["more"] and [e["commit"] for e in res["events"]] == [shas[2], shas[3]]
    appeared, gone = res["claims"]
    assert appeared["status"] == "strong_inference" and "cut at 2" in appeared["uncertainties"][0]
    assert res["appeared"]["commit"] == shas[2]
    assert gone["status"] == "primary_source_verified"  # the newest removal is never the one cut


def test_a_text_a_merge_removed_has_an_unknown_disappearance(tmp_path):
    r = tmp_path / "merge"
    r.mkdir()
    _git(r, "init", "-q")
    added = _commit(r, {"a.py": "x = 1\nFLAG_Z = 1\ny = 2\n"}, "add flag", date="2026-01-05T10:00:00+00:00")
    _git(r, "checkout", "-q", "-b", "side")
    _commit(r, {"a.py": "x = 1\nFLAG_Z = 2\ny = 2\n"}, "side flag", date="2026-01-06T10:00:00+00:00")
    _git(r, "checkout", "-q", "main")
    _commit(r, {"a.py": "x = 1\nFLAG_Z = 3\ny = 2\n"}, "main flag", date="2026-01-07T10:00:00+00:00")
    with pytest.raises(subprocess.CalledProcessError):  # a conflict
        _git(r, "merge", "-q", "side")
    (r / "a.py").write_bytes(b"x = 1\ny = 2\n")  # the conflict resolved by deleting the line
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "--no-edit", date="2026-01-08T10:00:00+00:00")
    res = history.text_history(r, "FLAG_Z")
    assert res["status"] == "found" and not res["at_head"]["present"]
    assert res["appeared"]["commit"] == added and "disappeared" not in res
    gone = [u for u in res["unknowns"] if "disappear" in u["question"]]
    assert gone and "merge" in gone[0]["why"] and "--first-parent" in gone[0]["next_step"]


def test_a_text_only_in_binary_files_is_not_said_to_be_unchanged(tmp_path):
    r = tmp_path / "bin"
    r.mkdir()
    _git(r, "init", "-q")
    _commit(r, {"b.bin": "png\x00FLAG_BIN\n"}, "binary", date="2026-01-05T10:00:00+00:00")
    res = history.text_history(r, "FLAG_BIN")
    assert res["status"] == "not_found"
    assert "binary" in res["unknowns"][0]["why"] and "no commit" not in res["unknowns"][0]["why"]


def test_a_project_in_a_folder_of_its_repository_searches_that_folder_only(tmp_path):
    top = tmp_path / "top"
    top.mkdir()
    _git(top, "init", "-q")
    _commit(top, {"other.py": "alpha_token outside\n", "sub proj/a.py": "alpha_token inside\n",
                  "sub proj/lat.txt": "beta_tok\n"}, "both", date="2026-01-05T10:00:00+00:00")
    gone = _commit(top, {"sub proj/a.py": "nothing\n"}, "drop inside", date="2026-01-06T10:00:00+00:00")
    proj = top / "sub proj"
    res = history.text_history(proj, "alpha_token")
    assert not res["at_head"]["present"] and res["appeared"]["at"] == "a.py:1"
    assert res["disappeared"] == {"commit": gone, "at": "a.py:1"}
    res = history.text_history(proj, "beta_tok")
    assert res["appeared"]["at"] == "lat.txt:1" and res["at_head"]["sites"][0]["path"] == "lat.txt"
    assert [c["commit"] for c in history.commits(proj, message="drop")["commits"]] == [gone]
    assert history.commits(proj, message="drop")["commits"][0]["files"] == ["a.py"]
    assert history.commits(tmp_path / "top", message="drop")["commits"][0]["files"] == ["sub proj/a.py"]
    cmp = history.compare(proj, "HEAD~1", "HEAD")
    assert [f["path"] for f in cmp["files"]] == ["a.py"]


def test_head_sites_are_capped_but_counted(tmp_path):
    r = tmp_path / "many"
    r.mkdir()
    _git(r, "init", "-q")
    _commit(r, {f"f{i:02}.txt": "hit\nhit\n" for i in range(12)}, "many", date="2026-01-05T10:00:00+00:00")
    now = history.text_history(r, "hit")["at_head"]
    assert now["count"] == 24 and len(now["sites"]) == history.MAX_SITES and now["truncated"]


def test_commits_by_message_author_path_date_and_diff(repo):
    r, shas = repo
    assert [c["commit"] for c in history.commits(r, message="retry budget")["commits"]] == \
        [shas[3], shas[2], shas[1]]  # newest first, case ignored
    by_alice = history.commits(r, author="alice")["commits"]
    assert [c["commit"] for c in by_alice] == [shas[1]] and by_alice[0]["files"] == ["svc.py"]
    assert [c["commit"] for c in history.commits(r, path="lib")["commits"]] == [shas[3], shas[2]]
    dated = history.commits(r, since="2026-03-01", until="2026-04-30")["commits"]
    assert [c["commit"] for c in dated] == [shas[3], shas[2]]
    diff = history.commits(r, diff=r"retry_budget = 3")
    assert [c["commit"] for c in diff["commits"]] == [shas[3], shas[1]]
    assert diff["commits"][0]["files"] == ["svc.py"]  # the file whose lines matched
    # message and author are extended regexes, as diff is: alternation works in all three
    assert [c["commit"] for c in history.commits(r, message="initial|remove the sql")["commits"]] == \
        [shas[4], shas[0]]
    assert [c["commit"] for c in history.commits(r, author="alice|nobody")["commits"]] == [shas[1]]
    assert by_alice[0]["evidence"]["commit_sha"] == shas[1]
    assert by_alice[0]["evidence"]["source_type"] == "git_history"
    cut = history.commits(r, limit=2)
    assert len(cut["commits"]) == 2 and cut["more"] and "limit=4" in cut["next_step"]
    whole = history.commits(r, limit=50)
    assert whole["scope"] == "path-free, HEAD history" and whole["more"] is False and "next_step" not in whole
    assert history.commits(r, message="no such words")["status"] == "not_found"


def test_compare_two_revisions(repo):
    r, shas = repo
    res = history.compare(r, shas[1], "HEAD")
    assert res["status"] == "found" and res["merge_base"] == shas[1]
    assert [c["commit"] for c in res["commits"]] == [shas[4], shas[3], shas[2]]
    assert res["commits_only_in_base"] == 0
    files = {f["path"]: f for f in res["files"]}
    assert set(files) == {"svc.py", "q.sql", "lib/job.py"}
    assert files["svc.py"]["change"] == "modified" and files["svc.py"]["removed"] == 2
    assert files["lib/job.py"]["change"] == "added" and files["lib/job.py"]["added"] == 3
    res = history.compare(r, shas[0], shas[2], path="lib")
    assert [f["path"] for f in res["files"]] == ["lib/job.py"] and res["files"][0]["change"] == "added"
    assert history.compare(r, "HEAD", shas[4])["status"] == "same"
    with pytest.raises(ValueError, match="names no commit"):
        history.compare(r, "no-such-branch", "HEAD")
    with pytest.raises(ValueError, match="is not a revision"):
        history.compare(r, "--output=x", "HEAD")


def test_not_a_git_tree(tmp_path):
    for res in (history.text_history(tmp_path, "x"), history.commits(tmp_path), history.compare(tmp_path, "a", "b")):
        assert res["status"] == "not_git"


def test_a_claim_is_one_the_store_rules_allow(repo):
    """The status a claim states is one :func:`verinoda.claims.check_status` allows for its evidence."""
    from verinoda.claims import check_status

    r, _ = repo
    for c in history.text_history(r, "RETRY_BUDGET")["claims"]:
        evs = [{**e, "relation": "supports", "id": f"evd_{i}"} for i, e in enumerate(c["evidence"])]
        assert check_status(c["status"], evs, claim={"kind": c["kind"], "text": c["text"]}, repo=r) is None, c


def test_cli(repo, capsys):
    r, shas = repo
    assert cli.main(["history", "text", "RETRY_BUDGET", "--repo", str(r), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["disappeared"]["commit"] == shas[3]
    assert cli.main(["history", "text", "RETRY_BUDGET", "--repo", str(r)]) == 0
    text = capsys.readouterr().out
    assert "first appeared in commit " + shas[1][:10] in text and "at HEAD: none" in text
    assert cli.main(["history", "commits", "--author", "alice", "--repo", str(r)]) == 0
    assert "Add Retry budget" in capsys.readouterr().out
    assert cli.main(["history", "compare", shas[0], "--repo", str(r)]) == 0
    assert "lib/job.py" in capsys.readouterr().out
    assert cli.main(["history", "text", "never_written_anywhere", "--repo", str(r)]) == 2
    assert cli.main(["history", "compare", "no-such-branch", "--repo", str(r)]) == 1


def test_mcp_history_search(repo):
    from verinoda.mcp.server import AtlasTools

    r, shas = repo
    (r / ".verinoda").mkdir(exist_ok=True)  # the tools answer in a project Verinoda has set up
    try:
        t = AtlasTools(r)
        res = t.history_search(text="RETRY_BUDGET")
        assert res["appeared"]["commit"] == shas[1] and res["claims"][0]["evidence"][0]["commit_sha"] == shas[1]
        assert [c["commit"] for c in t.history_search(author="alice")["commits"]] == [shas[1]]
        assert t.history_search(base=shas[3])["commits"][0]["commit"] == shas[4]
        assert t.history_search(base="no-such-branch")["error"] == "invalid_argument"
        assert "next_step" in t.history_search(text="never_written_anywhere")
        # a parameter of another mode is an error, not dropped
        for bad in ({"text": "x", "base": "HEAD~1"}, {"text": "x", "message": "fix"}, {"base": "HEAD", "diff": "x"},
                    {"author": "alice", "head": "HEAD"}, {"message": "x", "regex": True}):
            err = t.history_search(**bad)
            assert err["error"] == "invalid_argument", bad
        assert t.history_search(text="RETRY_BUDGET", path="lib")["appeared"]["commit"] == shas[2]
    finally:
        shutil.rmtree(r / ".verinoda")


# -- the commits that changed a symbol ---------------------------------------------------------------------------

PRICING_1 = "def compute_total(items):\n    return sum(items)\n\n\ndef other():\n    return 0\n"
PRICING_2 = "def compute_total(items):\n    return round(sum(items), 2)\n\n\ndef other():\n    return 0\n"
PRICING_3 = "def compute_total(items):\n    return round(sum(items), 2)\n\n\ndef other():\n    return 1\n"


@pytest.fixture(scope="module")
def sym_repo(tmp_path_factory) -> tuple[Path, list[str]]:
    """compute_total written, then rounded (a message with a body and a trailer block); then other() changed."""
    r = tmp_path_factory.mktemp("symbol history ğ") / "proj"
    r.mkdir()
    _git(r, "init", "-q")
    body = ("Round totals to cents\n\nInvoices showed 10.000000001; the ledger stores cents, so the total is\n"
            "rounded where it is computed.\n\nCo-Authored-By: Someone <s@example.org>\nSigned-off-by: Bob <b@x>\n")
    shas = [_commit(r, {"pricing.py": PRICING_1}, "Add pricing", date="2026-01-05T10:00:00+00:00"),
            _commit(r, {"pricing.py": PRICING_2}, body, author="Alice", date="2026-02-10T10:00:00+00:00"),
            _commit(r, {"pricing.py": PRICING_3}, "Other returns one", date="2026-03-15T10:00:00+00:00")]
    return r, shas


def test_the_commits_that_changed_a_line_range_quote_their_messages(sym_repo):
    r, shas = sym_repo
    res = history.symbol_history(r, None, "pricing.py:1-2")
    # one row per commit, newest first; the bodies quoted as the author wrote them, people trailers dropped
    assert res["status"] == "found" and "claims" not in res
    assert res["commits"] == [f"{shas[1][:10]} 2026-02-10 Alice Round totals to cents",
                              f"{shas[0][:10]} 2026-01-05 Bob Add pricing"]
    (rounded,) = res["quoted"]   # "Add pricing" has no body: nothing to quote beyond its row
    assert rounded["sha"] == shas[1][:10] and rounded["message"].startswith("Invoices showed 10.000000001")
    assert "Signed-off-by" not in rounded["message"] and "Co-Authored-By" not in rounded["message"]
    assert res["scope"].startswith("HEAD history of pricing.py:1-2") and res["more"] is False
    # the reading behind it keeps each commit whole, with git_history evidence quoting the message
    got = history.symbol_commits(r, "pricing.py", 1, 2)
    assert [c["commit"] for c in got["commits"]] == [shas[1], shas[0]] and got["commits"][0]["author"] == "Alice"
    ev = got["commits"][0]["evidence"]
    assert ev["locator"] == f"commit {shas[1]} pricing.py" and "ledger stores cents" in ev["excerpt"]
    assert "Co-Authored-By" not in ev["excerpt"]
    from verinoda.claims import check_status

    for c in got["commits"]:
        evs = [{**c["evidence"], "relation": "supports", "id": "evd_0"}]
        text = f"`pricing.py:1-2` was changed in {c['commit'][:10]} ({c['date'][:10]}, {c['author']}): {c['subject']}"
        assert check_status("primary_source_verified", evs, claim={"kind": "history", "text": text}, repo=r) is None, c
    other = history.symbol_history(r, None, "pricing.py:5-6")
    assert [row.split(" ", 1)[0] for row in other["commits"]] == [shas[2][:10], shas[0][:10]]


def test_working_tree_lines_are_mapped_to_head_first(sym_repo, tmp_path):
    r, shas = sym_repo
    work = tmp_path / "w"
    _git(tmp_path, "clone", "-q", str(r), str(work))
    (work / "pricing.py").write_bytes(("import math\n\n\n" + PRICING_3).encode())   # uncommitted: 3 lines on top
    res = history.symbol_history(work, None, "pricing.py:4-5")
    assert res["head_lines"] == [1, 2] and "mapped to HEAD's lines 1-2" in res["note"]
    assert [row.split(" ", 1)[0] for row in res["commits"]] == [shas[1][:10], shas[0][:10]]
    new = history.symbol_history(work, None, "pricing.py:1-1")
    assert new["status"] == "not_committed" and "new since HEAD" in new["note"]
    (work / "fresh.py").write_bytes(b"x = 1\n")
    assert history.symbol_history(work, None, "fresh.py:1-1")["status"] == "not_committed"
    with pytest.raises(ValueError):
        history.symbol_history(work, None, "pricing.py:5-4")


def test_a_name_resolves_through_the_index_and_is_never_replaced(sym_repo, tmp_path):
    from verinoda import index, workflow
    from verinoda.store import open_store

    r, shas = sym_repo
    work = tmp_path / "idx"
    _git(tmp_path, "clone", "-q", str(r), str(work))
    workflow.init(work)
    st = open_store(work)
    try:
        workflow.scan(st, work)
    finally:
        st.close()
    g = index.load(work)
    res = history.symbol_history(work, g, "compute_total")
    assert res["status"] == "found" and res["symbol"].startswith("compute_total") and res["lines"] == [1, 2]
    assert [row.split(" ", 1)[0] for row in res["commits"]] == [shas[1][:10], shas[0][:10]]
    miss = history.symbol_history(work, g, "compute_totl")
    assert miss["status"] == "unresolved" and "commits" not in miss
    assert history.symbol_history(work, None, "compute_total")["status"] == "unresolved"
    # analyze's why-question quotes the message body as the commit's evidence
    from verinoda import analysis

    st = open_store(work)
    try:
        ans = analysis.analyze(st, work, "Why does compute_total round the total?")
        hist = [c for c in ans["claims"] if " were changed in " in c["text"]]
        assert hist and shas[1][:10] in hist[0]["text"]
        from verinoda.claims import Claims

        ev = next(e for e in Claims(st).evidence(hist[0]["id"]) if e["relation"] == "supports")
        assert "ledger stores cents" in ev["excerpt"]
    finally:
        st.close()


def test_symbol_history_cli_and_mcp(sym_repo, capsys):
    from verinoda.mcp.server import AtlasTools

    r, shas = sym_repo
    assert cli.main(["history", "symbol", "pricing.py:1-2", "--repo", str(r)]) == 0
    text = capsys.readouterr().out
    assert text.startswith("pricing.py:1-2:") and "| Invoices showed" in text and shas[1][:10] in text
    assert cli.main(["history", "symbol", "pricing.py:1-2", "--repo", str(r), "--json", "--limit", "1"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert [row.split(" ", 1)[0] for row in out["commits"]] == [shas[1][:10]] and out["more"]
    (r / ".verinoda").mkdir(exist_ok=True)
    try:
        t = AtlasTools(r)
        res = t.history_search(symbol="pricing.py:5-6")
        assert res["commits"][0].startswith(shas[2][:10]) and "claims" not in res
        assert list(res)[:3] == ["status", "scope", "more"]   # the keys a reader needs first, kept whole
        for bad in ({"symbol": "pricing.py:1-2", "text": "x"}, {"symbol": "pricing.py:1-2", "path": "lib"},
                    {"symbol": "pricing.py:1-2", "base": "HEAD"}):
            assert t.history_search(**bad)["error"] == "invalid_argument", bad
    finally:
        shutil.rmtree(r / ".verinoda")


def test_symbol_history_outside_git(tmp_path):
    (tmp_path / "a.py").write_bytes(b"x = 1\n")
    assert history.symbol_history(tmp_path, None, "a.py:1-1")["status"] == "not_git"


def test_review_round_edges(sym_repo, tmp_path):
    r, shas = sym_repo
    work = tmp_path / "top"
    _git(tmp_path, "clone", "-q", str(r), str(work))
    # only people trailers are dropped; "Reason:" and "Note:" lines are the reason
    (work / "pricing.py").write_bytes(PRICING_3.replace("return 1", "return 2").encode())
    _git(work, "commit", "-q", "-am", "Change other\n\nReason: the API v2 contract.\nNote: see RFC-12\n\n"
                                      "Signed-off-by: Bob <b@x>", author="Bob")
    got = history.symbol_history(work, None, "pricing.py:5-6")
    assert got["quoted"][0]["message"] == "Reason: the API v2 contract.\nNote: see RFC-12"
    # a range past the end, a path outside the project, an absolute path inside it
    with pytest.raises(ValueError, match="has 6 lines"):
        history.symbol_history(work, None, "pricing.py:50-60")
    with pytest.raises(ValueError, match="outside the project"):
        history.symbol_history(work, None, "../x.py:1-2")
    absolute = history.symbol_history(work, None, f"{(work / 'pricing.py').as_posix()}:1-2")
    assert absolute["file"] == "pricing.py" and absolute["status"] == "found"
    # a file deleted in the working tree is read at HEAD, not taken for a name
    (work / "pricing.py").unlink()
    gone = history.symbol_history(work, None, "pricing.py:1-2")
    assert gone["status"] == "found" and "not in the working tree" in gone["note"]
    _git(work, "checkout", "--", "pricing.py")
    # a stale index is not used for line numbers
    from verinoda import index, workflow
    from verinoda.store import open_store

    workflow.init(work)
    st = open_store(work)
    try:
        workflow.scan(st, work)
    finally:
        st.close()
    (work / "pricing.py").write_bytes(("import math\n\n\n" + PRICING_3).encode())
    stale = history.symbol_history(work, index.load(work), "other", stale=["pricing.py"])
    assert stale["status"] == "stale_index" and "commits" not in stale
    # a shallow clone says so in text
    shallow = tmp_path / "shallow"
    _git(tmp_path, "clone", "-q", "--depth", "1", (r.as_uri()), str(shallow))
    assert cli.main(["history", "symbol", "pricing.py:1-2", "--repo", str(shallow)]) == 0


def test_mcp_refuses_an_empty_symbol(sym_repo):
    from verinoda.mcp.server import AtlasTools

    r, _ = sym_repo
    (r / ".verinoda").mkdir(exist_ok=True)
    try:
        assert AtlasTools(r).history_search(symbol="  ")["error"] == "invalid_argument"
    finally:
        shutil.rmtree(r / ".verinoda")


# -- one flat list, correct where git is blind, honest on time-outs (D186) ----------------------------------------

def _rows_repo(root: Path) -> tuple[Path, list[str]]:
    """Thirty commits, each changing the one line of compute_total; a body on a few of them, one stating a
    reason in the middle, one a plain note in the middle."""
    r = root / "rows"
    r.mkdir()
    _git(r, "init", "-q")
    bodies = {1: "The total starts here.", 3: "Items are summed.", 10: "A plain note in the middle.",
              15: "because the ledger counts from one", 28: "Near the end.", 30: "The newest step."}
    shas = []
    for i in range(1, 31):
        msg = f"total step {i:02}" + (f"\n\n{bodies[i]}\n" if i in bodies else "")
        shas.append(_commit(r, {"calc.py": f"def compute_total(items):\n    return sum(items) + {i}\n"}, msg,
                            date=f"2026-01-{i:02}T10:00:00+00:00"))
    return r, shas


def test_symbol_history_is_one_flat_list_with_bodies_on_the_ends(tmp_path):
    from verinoda.mcp.server import _size

    r, shas = _rows_repo(tmp_path)
    res = history.symbol_history(r, None, "calc.py:1-2", limit=30)
    assert res["status"] == "found" and "claims" not in res and res["more"] is False
    rows = res["commits"]
    assert len(rows) == 30 and all(isinstance(x, str) for x in rows)
    assert rows[0] == f"{shas[29][:10]} 2026-01-30 Bob total step 30"      # newest first, every commit one row
    assert rows[-1] == f"{shas[0][:10]} 2026-01-01 Bob total step 01"
    # bodies on the first three and the last three rows that have one, and on the one that states a reason;
    # the plain note in the middle is not quoted
    assert [q["sha"] for q in res["quoted"]] == [shas[29][:10], shas[27][:10], shas[14][:10], shas[2][:10],
                                                 shas[0][:10]]
    assert next(q["message"] for q in res["quoted"] if q["sha"] == shas[14][:10]) == "because the ledger counts from one"
    assert "HEAD history of calc.py:1-2" in res["scope"]
    assert _size(res) <= 2000, _size(res)
    cut = history.symbol_history(r, None, "calc.py:1-2", limit=14)
    assert len(cut["commits"]) == 14 and cut["more"] is True and "limit" in cut["next_step"]
    assert cut["commits"][0].startswith(shas[29][:10]) and cut["commits"][-1].startswith(shas[16][:10])
    assert {q["sha"] for q in cut["quoted"]} == {shas[29][:10], shas[27][:10]}


def test_text_history_marks_a_created_file_and_searches_path_free_oldest_first(tmp_path):
    r = tmp_path / "born"
    r.mkdir()
    _git(r, "init", "-q")
    born = _commit(r, {"old.py": "MAGIC_TOKEN = 1\n"}, "Add the token", date="2026-01-05T10:00:00+00:00")
    _commit(r, {"notes.txt": "nothing\n"}, "Unrelated", date="2026-01-06T10:00:00+00:00")
    created = _commit(r, {"new.py": "MAGIC_TOKEN = 2\n"}, "Create new.py with the token",
                      date="2026-01-07T10:00:00+00:00")
    # the guzzle class (D186): the path-bound first event created the file, so the text may have lived elsewhere;
    # the path-free search, oldest first, finds the commit that first added it to the project
    res = history.text_history(r, "MAGIC_TOKEN", path="new.py")
    assert res["status"] == "found" and res["events"][0]["new_file"] is True
    assert res["appeared"] == {"commit": created, "at": "new.py:1"}    # what appeared under the path
    claim = res["claims"][0]
    assert claim["status"] == "primary_source_verified" and born[:10] in claim["text"] and "old.py:1" in claim["text"]
    assert "path-free" in claim["text"] and any("new.py" in u for u in claim["uncertainties"])
    assert claim["evidence"][0]["commit_sha"] == born and claim["evidence"][0]["excerpt"] == "+MAGIC_TOKEN = 1"
    assert res["earlier_elsewhere"]["sha"] == born and res["earlier_elsewhere"]["subject"] == "Add the token"
    assert "path-free" in res["scope"]
    # the project's first commit created the file: the path-free oldest is the same commit, the status is restored
    first = history.text_history(r, "MAGIC_TOKEN", path="old.py")
    assert first["events"][0]["new_file"] is True and first["claims"][0]["status"] == "primary_source_verified"
    assert first["appeared"]["commit"] == born and "earlier_elsewhere" not in first
    assert "path-free" in first["claims"][0]["text"]


def test_regex_and_text_mode_follow_a_moved_file_when_one_path_is_given(tmp_path):
    r = tmp_path / "moved"
    r.mkdir()
    _git(r, "init", "-q")
    shas = [_commit(r, {"a/old_name.py": "x = 1\nLIMIT = 10\n"}, "Add the limit", date="2026-01-05T10:00:00+00:00"),
            _commit(r, {"a/old_name.py": "x = 1\nLIMIT = 20\n"}, "Raise the limit", date="2026-01-06T10:00:00+00:00")]
    (r / "b").mkdir()
    _git(r, "mv", "a/old_name.py", "b/new_name.py")
    _git(r, "commit", "-q", "-m", "Move the module", date="2026-01-07T10:00:00+00:00")
    shas.append(_git(r, "rev-parse", "HEAD"))
    # the fastapi class (D186): a one-for-one change before the move, which -S with the new path alone never sees
    res = history.text_history(r, "LIMIT = 20", path="b/new_name.py")
    assert res["appeared"] == {"commit": shas[1], "at": "a/old_name.py:2"} and "renames followed" in res["scope"]
    assert [e["commit"] for e in res["events"]] == [shas[1]]    # the pure move shows no occurrence change
    rx = history.text_history(r, "LIMIT = 2[0-9]", regex=True, path="b/new_name.py")
    assert rx["appeared"]["commit"] == shas[1]
    found = history.commits(r, diff="LIMIT = 20", path="b/new_name.py")
    assert [c["commit"] for c in found["commits"]] == [shas[1]] and "renames followed" in found["scope"]
    # a folder path keeps today's result: no rename detection, the move adds the text at the new path
    folder = history.text_history(r, "LIMIT = 20", path="b")
    assert folder["appeared"] == {"commit": shas[2], "at": "b/new_name.py:2"} and "pre-move" in folder["scope"]


def test_the_general_rule_names_an_earlier_commit_at_another_path(tmp_path):
    r = tmp_path / "elsewhere"
    r.mkdir()
    _git(r, "init", "-q")
    first = _commit(r, {"lib.py": "SHARED_KEY = 'a'\n"}, "Add the shared key", date="2026-01-05T10:00:00+00:00")
    _commit(r, {"app.py": "x = 1\n"}, "Add the app", date="2026-01-06T10:00:00+00:00")
    again = _commit(r, {"app.py": "x = 1\nSHARED_KEY = 'b'\n"}, "Use the key in the app",
                    date="2026-01-07T10:00:00+00:00")
    # the gin trap-1 class (D186): the path-bound first event is a modification; the text was born in another file
    res = history.text_history(r, "SHARED_KEY", path="app.py")
    assert res["events"][0]["new_file"] is False and res["appeared"] == {"commit": again, "at": "app.py:2"}
    claim = res["claims"][0]
    assert claim["status"] == "primary_source_verified" and again[:10] in claim["text"]
    assert any(u.startswith(f"the text existed earlier at another path: {first[:10]} 2026-01-05 Add the shared key")
               for u in claim["uncertainties"])
    assert res["earlier_elsewhere"]["sha"] == first and res["earlier_elsewhere"]["date"].startswith("2026-01-05")
    assert res["earlier_elsewhere"]["subject"] == "Add the shared key"


def test_a_timed_out_search_is_partial_not_an_error(repo, monkeypatch):
    from verinoda import gitexec

    r, shas = repo
    real = gitexec.run

    def slow_log(repo_, *args, **kw):   # the -S, -G and -L reads time out; rev-parse, show and grep answer
        if "log" in args:
            return gitexec.GitResult(124, "", "git log timed out after 60 s", timed_out=True)
        return real(repo_, *args, **kw)

    monkeypatch.setattr(gitexec, "run", slow_log)
    res = history.text_history(r, "RETRY_BUDGET")
    assert res["status"] == "partial" and res["timed_out"] is True and "error" not in res
    assert "log -S" in res["searched"] and "VERINODA_MCP_GIT_TIMEOUT" in res["next_step"] and "path" in res["next_step"]
    assert res["claims"] == [] and "scope" in res
    sym = history.symbol_history(r, None, "svc.py:1-2")
    assert sym["status"] == "partial" and sym["timed_out"] is True and sym["commits"] == []
    assert history.commits(r, message="budget")["status"] == "partial"

    def slow_path_free(repo_, *args, **kw):   # only the automatic path-free read times out
        if "log" in args and "--" not in args:
            return gitexec.GitResult(124, "", "git log timed out after 60 s", timed_out=True)
        return real(repo_, *args, **kw)

    monkeypatch.setattr(gitexec, "run", slow_path_free)
    res = history.text_history(r, "RETRY_BUDGET", path="lib")
    assert res["status"] == "found" and res["appeared"]["commit"] == shas[2] and res["events"][0]["new_file"] is True
    claim = res["claims"][0]
    assert claim["status"] == "strong_inference"
    assert any("path-free search timed out" in u for u in claim["uncertainties"])
    assert any("created at this path" in u for u in claim["uncertainties"])


def test_literal_pathspecs_and_end_of_options(repo, tmp_path):
    top = tmp_path / "top"
    top.mkdir()
    _git(top, "init", "-q")
    _commit(top, {"other.py": "zeta_tok outside\n", "sub/a.py": "nothing\n", "sub/b.py": "zeta_tok inside\n"},
            "both", date="2026-01-05T10:00:00+00:00")
    proj = top / "sub"
    # pathspec magic (`:/` is the repository root) and globs are read literally: a path is a file or folder prefix
    assert history.text_history(proj, "zeta_tok", path=":/other.py")["status"] == "not_found"
    assert history.text_history(proj, "zeta_tok", path="*.py")["status"] == "not_found"
    assert history.text_history(proj, "zeta_tok", path="b.py")["appeared"]["at"] == "b.py:1"
    with pytest.raises(ValueError, match="leaves the project"):
        history.text_history(proj, "zeta_tok", path="../other.py")
    r, _ = repo
    with pytest.raises(ValueError, match="is not a revision"):
        history.compare(r, "-x", "HEAD")
    with pytest.raises(ValueError, match="is not a revision"):
        history.symbol_commits(r, "svc.py", 1, 2, rev="--output=x")
