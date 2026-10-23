"""The file a question names scopes its plain words, a subject found by one word of several is not met, and a why
says where the line it asks about came from (docs/DESIGN.md D190).

The case is a real agent's question about a chat bot (2026-10-23): "In <file>, why does relay() call talk.set for
the player even when the reply was [SUSKUN] (silent)? When was the 60 second conversation window introduced and what
depends on it?". Verinoda linked "window" to a capture helper in another folder and called the when-part met with
that helper's commits; its why read the function's commits for a stated reason, found none and did not say that the
line predates the [SUSKUN] case; and a folder of the path was searched as a code term.
"""

from __future__ import annotations

import os

os.environ.setdefault("GRAPHIFY_OUT", ".verinoda/index")

import shutil
import subprocess
from pathlib import Path

import pytest

from verinoda import analysis, analysis_view, index, lexicon, workflow
from verinoda import question_plan as qp
from verinoda.store import open_store

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not available")

BOT = "MyGame/bot/herald.js"
QUESTION = ("In MyGame/bot/herald.js, why does relay() call talk.set for the player even when the reply was "
            "[SUSKUN] (silent)? When was the 60 second conversation window introduced and what depends on it?")
WHEN = "When was the 60 second conversation window introduced?"

# the window's comment is Turkish, as in the bot the case came from: the English question's words name nothing in
# this file, and in the other folders "window" and "second" name a capture helper and a spell
HERALD = """const cfg = { talkMs: 60000 }
const talk = new Map() // oyuncu -> son cevap zamani (60 sn sohbet pencere)

function say (text) {
  return text
}

function deliver (text, item) {
  say(text)
}

async function relay (item) {
  const text = item.message
  deliver(text, item)
  if (item.player) talk.set(item.player, Date.now())
}

function onChat (username, message) {
  const inTalk = Date.now() - (talk.get(username) || 0) < cfg.talkMs
  if (!inTalk) return
  relay({ player: username, message })
}

module.exports = { relay, onChat }
"""
FXRUN = '''def find_window(title):
    """The game window by its title."""
    return title
'''
SPELL = """public class Spell {
    public int seconds() {
        return 10;
    }
}
"""


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "core.autocrlf=false", *args],
                          cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def _write(repo: Path, rel: str, text: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(text.encode("utf-8"))


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _scanned(repo: Path) -> Path:
    workflow.init(repo)
    st = open_store(repo)
    try:
        workflow.scan(st, repo)
    finally:
        st.close()
    return repo


@pytest.fixture(scope="module")
def bot(tmp_path_factory):
    """The bot (its window and the relay() line first, the [SUSKUN] marker last) and, in other folders, a
    window-capture helper and a spell with seconds(): ``(repo, [sha of each of the four commits])``."""
    repo = tmp_path_factory.mktemp("scope") / "game"
    repo.mkdir()
    _git(repo, "init", "-q")
    shas = []
    _write(repo, BOT, HERALD)
    shas.append(_commit(repo, "bot: chat brain with a conversation window"))
    _write(repo, "MyGame/tools/fxrun.py", FXRUN)
    _write(repo, "MyGame/src/Spell.java", SPELL)
    shas.append(_commit(repo, "fxrun: find the game window"))
    _write(repo, "MyGame/tools/fxrun.py", FXRUN.replace("return title", "return title.strip()"))
    shas.append(_commit(repo, "fxrun: capture the window by its title"))
    _write(repo, BOT, HERALD.replace("function deliver (text, item) {\n  say(text)",
                                    "function deliver (text, item) {\n  if (/\\[SUSKUN\\]/.test(text)) return\n"
                                    "  say(text)"))
    shas.append(_commit(repo, "bot: silent replies are not said"))
    return _scanned(repo), shas


@pytest.fixture(scope="module")
def answer(bot):
    repo, _ = bot
    st = open_store(repo)
    try:
        return analysis.analyze(st, repo, QUESTION)
    finally:
        st.close()


def _answers(res: dict, sq_id: str) -> list[dict]:
    claims = {c["id"]: c for c in res["claims"]}
    (s,) = [s for s in res["subquestions"] if s["id"] == sq_id]
    return [claims[i] for i in s["answer_claim_ids"] if i in claims]


def _status(res: dict, sq_id: str) -> str:
    return next(s["status"] for s in res["subquestions"] if s["id"] == sq_id)


def test_a_folder_of_a_path_is_not_a_code_term():
    assert "MyGame" not in analysis._code_terms(QUESTION)
    assert analysis._code_terms("why does `MyGame` load PriceCache?") == ["MyGame", "PriceCache"]


def test_the_file_a_question_names_scopes_its_plain_words(bot):
    repo, _ = bot
    g = index.load(repo)
    lex = lexicon.load(repo)
    plan = qp.draft(QUESTION, g, lex)
    res = qp.check(plan, g, repo, lex)
    where = {lk["text"]: sorted({g.file(n) for n in qp.mention_nodes(lk)}) for lk in res["links"]
             if lk["status"] in ("linked", "weak", "ambiguous")}
    assert where and all(files == [BOT] for files in where.values()), where


def test_the_when_part_is_answered_from_the_named_file_not_a_same_named_helper_elsewhere(bot, answer):
    _, shas = bot
    texts = [c["text"] for c in _answers(answer, "q2")]
    assert texts and not any("find_window" in t or "seconds" in t or "fxrun" in t for t in texts), texts
    assert any(shas[0][:10] in t for t in texts), texts        # the commit that brought the window
    assert _status(answer, "q2") == "met_with_inference"       # its subject is read from words, not named


def test_a_why_says_the_line_it_asks_about_came_before_the_case_it_names(bot, answer):
    _, shas = bot
    (line,) = [c for c in _answers(answer, "q1") if "talk.set" in c["text"] and "first appears" in c["text"]]
    assert shas[0][:10] in line["text"] and shas[3][:10] in line["text"] and "before" in line["text"], line["text"]
    assert _status(answer, "q1") == "met_with_inference"       # a commit order is not a stated reason
    (why,) = [u for u in answer["unknowns"] if u.get("sub_question") == "q1" and "reason was not found" in u["why"]]
    assert why["commits"][0].startswith(shas[0][:10]) and "talk.set" in why["commits"][0]   # the line's commit first
    # the path's folder is no code term: it is not searched for, and no "first appearance of `MyGame`" lead is made
    assert not any(s["step"] == "git_log_S" and s["detail"] == "MyGame" for s in answer["steps"])
    assert not any("`MyGame`" in str(u.get("commits") or "") for u in answer["unknowns"])


def test_the_text_view_leaves_other_files_context_out(answer):
    head = analysis_view.render_text(answer).split("\npassages (")[0]
    assert "fxrun.py" not in head and "Spell.java" not in head, head


@pytest.fixture(scope="module")
def helper(tmp_path_factory):
    """Only the window-capture helper, changed twice: nothing names a conversation window."""
    repo = tmp_path_factory.mktemp("scope") / "helper"
    repo.mkdir()
    _git(repo, "init", "-q")
    _write(repo, "tools/fxrun.py", FXRUN)
    _commit(repo, "fxrun: find the game window")
    _write(repo, "tools/fxrun.py", FXRUN.replace("return title", "return title.strip()"))
    _commit(repo, "fxrun: capture the window by its title")
    return _scanned(repo)


def test_a_subject_found_by_one_word_of_several_is_not_met(helper):
    st = open_store(helper)
    try:
        res = analysis.analyze(st, helper, WHEN)
        named = analysis.analyze(st, helper, "When was find_window added?")
    finally:
        st.close()
    (s,) = res["subquestions"]
    assert any("find_window" in c["text"] for c in _answers(res, s["id"]))
    assert s["status"] == "met_with_inference", s
    assert any("find_window" in u["why"] and "'window'" in u["why"] for u in res["unknowns"]), res["unknowns"]
    assert named["subquestions"][0]["status"] == "met"         # a subject the question names as code is not capped
