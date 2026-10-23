"""The file a question names is where its plain words are looked for first, a subject found by one word of several is
not met, and a why says where the line it asks about came from (docs/DESIGN.md D190).

The case is a real agent's question about a chat bot (2026-10-23): "In <file>, why does relay() call talk.set for
the player even when the reply was [SUSKUN] (silent)? When was the 60 second conversation window introduced and what
depends on it?". Verinoda linked "window" to a capture helper in another folder and called the when-part met with
that helper's commits; its why read the function's commits for a stated reason, found none and did not say that the
line predates the [SUSKUN] case; and a folder of the path was searched as a code term. Two fresh reviews of the fix
added the cases at the end: a fence around the named file, a line's commit read as a reason, seeds for a callers part,
a value in a when-question, and a cap that lowered right answers.
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


def test_the_file_a_question_names_gives_its_plain_words_their_candidates_there(bot):
    repo, _ = bot
    g = index.load(repo)
    lex = lexicon.load(repo)
    plan = qp.draft(QUESTION, g, lex)
    links = {lk["text"]: lk for lk in qp.check(plan, g, repo, lex)["links"]}
    # the project-wide link stays as without the file; the word's candidates in the file are kept beside it, an
    # English word's through its Turkish ("window" -> the "pencere" of the window's comment)
    assert g.file(qp.mention_nodes(links["window"])[0]) == "MyGame/tools/fxrun.py"
    assert [g.file(n) for n in links["window"]["in_scope"]] == [BOT] and links["window"]["in_scope_at"] == [f"{BOT}:2-2"]
    assert not links["second"].get("in_scope")


def test_the_when_part_is_answered_from_the_named_file_not_a_same_named_helper_elsewhere(bot, answer):
    _, shas = bot
    texts = [c["text"] for c in _answers(answer, "q2")]
    assert texts and not any("find_window" in t or "seconds" in t or "fxrun" in t for t in texts), texts
    assert any(shas[0][:10] in t for t in texts), texts        # the commit that brought the window
    assert _status(answer, "q2") == "met"   # read from words, and its commit says "conversation window"


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


def _history_repo(root: Path, name: str, steps: list[tuple[str, str, str]]) -> tuple[Path, list[str]]:
    repo = root / name
    repo.mkdir()
    _git(repo, "init", "-q")
    shas = []
    for rel, text, message in steps:
        _write(repo, rel, text)
        shas.append(_commit(repo, message))
    return _scanned(repo), shas


def _when(repo: Path, question: str) -> list[str]:
    st = open_store(repo)
    try:
        res = analysis.analyze(st, repo, question)
    finally:
        st.close()
    (s,) = res["subquestions"]
    return [c["text"] for c in _answers(res, s["id"])]


SETTINGS = ("const retryPolicy = { limit: 3 }\n\nfunction fetchPage (url) {\n  return url\n}\n\n"
            "module.exports = { retryPolicy, fetchPage }\n")
FETCH = '''def fetch(url, tries=1):
    """Read a page."""
    for _ in range(tries):
        return url
    return None
'''


@pytest.fixture(scope="module")
def retry_policy(tmp_path_factory):
    """One object-valued constant (a primitive one is no graph node) whose one line four commits changed: the first
    brought it, three tuned it."""
    return _history_repo(tmp_path_factory.mktemp("scope"), "settings", [
        ("settings.js", SETTINGS, "initial import")] + [
        ("settings.js", SETTINGS.replace("limit: 3", f"limit: {n}"), f"tune: {n} tries") for n in (4, 5, 6)])


def test_when_a_one_line_definition_was_introduced_is_its_oldest_commit(retry_policy):
    # the newest three commits (D186's when-answer without a shared word) are its later edits
    repo, shas = retry_policy
    texts = _when(repo, "When was the retry policy introduced?")
    assert any(shas[0][:10] in t for t in texts), texts


def test_a_when_about_a_change_after_the_introduction_keeps_the_newest_commits(retry_policy):
    repo, shas = retry_policy   # the review's case: the creation commit alone came back
    texts = _when(repo, "When was the retry policy changed after it was added?")
    assert any(shas[-1][:10] in t for t in texts), texts


def test_when_a_function_was_given_a_behaviour_is_not_its_first_commit(tmp_path):
    # the oldest commit of a function's lines is the function's birth, not the change asked about (backlog 22.7)
    repo, shas = _history_repo(tmp_path, "fetcher", [
        ("fetch.py", FETCH, "initial import"),
        ("fetch.py", FETCH.replace("        return url", "        try:\n            return url\n"
                                   "        except TimeoutError:\n            continue"),
         "fetch: retry once more on a timeout")])
    texts = _when(repo, "When was the retry on a timeout introduced?")
    assert any(shas[1][:10] in t for t in texts) and not any(shas[0][:10] in t for t in texts), texts


# -- the review's cases (each failed on 2129e7c, the first version of D190) -----------------------------------------

SILENT = HERALD.replace("function deliver (text, item) {\n  say(text)",
                       "function deliver (text, item) {\n  if (/\\[SUSKUN\\]/.test(text)) return\n  say(text)")
WHY = QUESTION.split("?")[0] + "?"


def _ask(repo: Path, question: str, plan: dict | None = None) -> dict:
    st = open_store(repo)
    try:
        return analysis.analyze(st, repo, question, plan=plan) if plan else analysis.analyze(st, repo, question)
    finally:
        st.close()


@pytest.fixture(scope="module")
def since(tmp_path_factory):
    """The talk.set line changed once, by a commit that states no reason; no [SUSKUN] case."""
    return _history_repo(tmp_path_factory.mktemp("scope"), "since", [
        (BOT, HERALD, "bot: chat brain"),
        (BOT, HERALD.replace("talk.set(item.player, Date.now())", "talk.set(item.player, Date.now() + 0)"),
         "bot: keep the player's reply time")])


def test_a_lines_first_commit_is_a_lead_never_the_reason_of_a_why(since):
    # the claim's own words ("changed since") and the path's folder "bot" once read as a reason the commit stated
    repo, shas = since   # "write", not "call": no call path keeps it below met
    res = _ask(repo, f"In {BOT}, why does relay() write talk.set for the player?")
    assert _status(res, "q1") != "met"
    whys = [u for u in res["unknowns"] if u.get("sub_question") == "q1" and "reason was not found" in u["why"]]
    assert len(whys) == 1 and whys[0]["commits"][0].startswith(shas[0][:10]), whys


@pytest.fixture(scope="module")
def moved(tmp_path_factory):
    """[SUSKUN] first, then the talk.set line, then the bot moved under MyGame/."""
    repo = tmp_path_factory.mktemp("scope") / "moved"
    repo.mkdir()
    _git(repo, "init", "-q")
    _write(repo, "bot/herald.js", SILENT.replace("  if (item.player) talk.set(item.player, Date.now())\n", ""))
    shas = [_commit(repo, "bot: silent replies are not said")]
    _write(repo, "bot/herald.js", SILENT)
    shas.append(_commit(repo, "bot: remember who talked"))
    (repo / "MyGame").mkdir()
    _git(repo, "mv", "bot", "MyGame/bot")
    shas.append(_commit(repo, "move the bot under MyGame"))
    return _scanned(repo), shas


def test_a_case_older_than_the_line_stays_older_across_a_move(moved):
    repo, shas = moved   # without following the rename the move was the case's first commit, "later" than the line
    texts = [c["text"] for c in _ask(repo, WHY)["claims"] if "first appears" in c["text"]]
    assert texts and all("earlier" in t and shas[0][:10] in t for t in texts), texts


def test_another_part_of_the_message_keeps_its_own_subject(bot):
    repo, _ = bot   # "its title" carries q1's subject; the window finder of the other folder still answers it
    res = _ask(repo, f"Where is relay defined in {BOT}? And where is the game window found by its title?")
    assert any("find_window" in c["text"] for c in _answers(res, "q2")), _answers(res, "q2")


def test_a_part_about_another_file_is_answered_there(bot):
    repo, _ = bot
    window = _ask(repo, f"Where is relay defined in {BOT}? And where is the game window looked up by title?")
    spell = _ask(repo, f"In {BOT}, where is relay defined? Where is the spell duration in seconds computed?")
    assert any("find_window" in c["text"] for c in _answers(window, "q2")), _answers(window, "q2")
    assert any("seconds" in c["text"] for c in _answers(spell, "q2")) and _status(spell, "q2") != "unmet"


def test_a_host_plans_word_that_names_code_only_elsewhere_is_still_linked(bot):
    repo, _ = bot
    q = f"In {BOT}, why does relay() call talk.set? Where is the title lookup done?"
    plan = {"schema": "verinoda.question_plan/1", "user_message": q, "language": "en",
            "restated_goal": "why relay calls talk.set; where the title lookup is",
            "restated_goal_user_lang": "why relay calls talk.set; where the title lookup is",
            "sub_questions": [
                {"id": "q1", "text": f"In {BOT}, why does relay() call talk.set?", "intent": "why",
                 "mentions": ["m1", "m2"],
                 "done_when": {"kind": "claim_exists", "subjects": ["m2"], "min_status": "strong_inference",
                               "detail": "a commit or record that states the reason"}},
                {"id": "q2", "text": "Where is the title lookup done?", "intent": "locate", "mentions": ["m3"],
                 "done_when": {"kind": "location_verified", "subjects": ["m3"], "min_status": "statically_verified",
                               "detail": "file:line of the lookup"}}],
            # m3 leaves out "required" (so it is required): a plain word that names code only outside the named file
            "mentions": [{"id": "m1", "text": BOT, "kind": "file"}, {"id": "m2", "text": "relay()", "kind": "symbol"},
                         {"id": "m3", "text": "title", "kind": "domain_concept"}],
            "on_ambiguity": "answer_all", "host": "claude_code"}
    res = _ask(repo, q, plan)
    assert not any("matches 'title" in (u.get("why") or "") for u in res["unknowns"]), res["unknowns"]
    assert any("find_window" in c["text"] for c in _answers(res, "q2")), _answers(res, "q2")


def test_the_file_named_in_the_same_sentence_is_where_to_look_not_the_subject(bot):
    repo, _ = bot   # the path made the part "name code", and the capture helper was met
    res = _ask(repo, f"In {BOT}, when was the 60 second conversation window introduced?")
    texts = [c["text"] for c in _answers(res, "q1")]
    assert texts and not any("find_window" in t or "fxrun" in t for t in texts), texts
    assert any("talk" in t for t in texts)   # the window's own line, met: its commit says "conversation window"


@pytest.fixture(scope="module")
def trimmed(tmp_path_factory):
    """relay()'s message line changed twice after the bot came."""
    return _history_repo(tmp_path_factory.mktemp("scope"), "trimmed", [
        (BOT, HERALD, "bot: chat brain"),
        (BOT, HERALD.replace("const text = item.message", "const text = item.message.trim()"), "relay: trim the message"),
        (BOT, HERALD.replace("const text = item.message", "const text = String(item.message).trim()"),
         "relay: accept numbers")])


def test_a_name_written_with_parentheses_names_code(trimmed):
    repo, _ = trimmed   # `relay()` is linked as a plain word; written with "()" it is the question's subject
    assert _status(_ask(repo, "When was the message trimming in relay() added?"), "q1") == "met"


def test_turkish_cue_words_are_not_words_of_the_subject(tmp_path):
    # "zaman" and "eklendi" counted as words talk did not carry (a comment without them, as in the review's case)
    plain = HERALD.replace(" // oyuncu -> son cevap zamani (60 sn sohbet pencere)", "")
    repo, _ = _history_repo(tmp_path, "plain", [("bot/herald.js", plain, "bot: sohbet beyni"),
                                                ("bot/herald.js", plain.replace("60000", "90000"), "bot: pencere 90 sn")])
    assert _status(_ask(repo, "talk ne zaman eklendi?"), "q1") == "met"


def test_the_passages_keep_the_searchs_own_lines():
    lines = ["expanded: window->pencere", "## a.js:1-2 f", "1 function f () {", "## b.py:1-2 g", "1 def g():",
             "(calls / called by: name@line)", "… 3 more candidates", "next: verinoda query"]
    assert analysis._in_scope(lines, frozenset({"a.js"})) == [
        "expanded: window->pencere", "## a.js:1-2 f", "1 function f () {", "(calls / called by: name@line)",
        "… 3 more candidates", "next: verinoda query",
        "(+1 passage(s) of other files than the question names left out: `verinoda query` gives them)"]


# -- the second review's cases (each failed on 718c7d2, the review round) -------------------------------------------

BOT_PY = "MyGame/bot/herald.py"
HERALD_PY = '''TALK_MS = {"limit": 60000}  # oyuncu -> son cevap zamani (60 sn sohbet pencere)


def say(text):
    return text


def deliver(text, item):
    return say(text)  # the game window chat line


def relay(item):
    text = item["message"]
    deliver(text, item)
    return text
'''
FX_PY = '''def find_window(title):
    return title


def capture_game_window(title):
    return find_window(title)


def snapshot():
    return capture_game_window("game")
'''


def test_a_callers_part_is_not_seeded_with_the_named_files_candidates(tmp_path):
    # the named file's line "the game window chat line" made deliver() the target of a callers part, met
    repo, _ = _history_repo(tmp_path, "seeds", [(BOT_PY, HERALD_PY, "init"), ("MyGame/tools/fx.py", FX_PY, "fx")])
    res = _ask(repo, f"In {BOT_PY}, where is relay defined? What calls the game window capture?")
    texts = [c["text"] for c in _answers(res, "q2")]
    assert any("capture_game_window" in t for t in texts) and not any("deliver" in t for t in texts), texts


def test_a_when_about_a_value_keeps_the_newest_commits_beside_the_first(retry_policy):
    repo, shas = retry_policy   # "of 6" came with the last edit; the first commit alone was met
    texts = _when(repo, "When was the retry limit of 6 introduced?")
    assert any(shas[-1][:10] in t for t in texts), texts


def test_a_plain_word_question_naming_a_file_by_its_basename_is_not_met_by_one_word(bot):
    repo, _ = bot   # "fxrun.py" counted as a word find_window() carries
    res = _ask(repo, "In fxrun.py, when was the 60 second conversation window introduced?")
    assert any("find_window" in c["text"] for c in _answers(res, "q1")) and _status(res, "q1") == "met_with_inference"


def test_a_plan_link_is_printed_where_the_answer_is(bot):
    repo, _ = bot   # "window" was printed at the bot's comment while the part was answered by the helper
    text = analysis_view.render_text(
        _ask(repo, f"Where is relay defined in {BOT}? And where is the game window found by its title?"))
    links = next(ln for ln in text.splitlines() if ln.startswith("plan links:"))
    assert "window -> MyGame/tools/fxrun.py:1-3" in links or "window -> MyGame/tools/fxrun.py" in links, links


def test_two_named_files_share_a_words_candidates(tmp_path):
    # the first file (by name) spells the word in three functions: it took every place, and the second had none
    many = "".join(f"function f{i} () {{\n  return {i} // the window\n}}\n\n" for i in range(3))
    one = "function g () {\n  return 0 // the window\n}\n"
    other = "function openWindow () {\n  return 1\n}\n"   # a name elsewhere links the word in the whole project
    repo, _ = _history_repo(tmp_path, "two", [("a_first.js", many, "a"), ("b_second.js", one, "b"),
                                              ("c_other.js", other, "c")])
    g = index.load(repo)
    lex = lexicon.load(repo)
    plan = qp.draft("In a_first.js and b_second.js, where is the window handled?", g, lex)
    window = next(lk for lk in qp.check(plan, g, repo, lex)["links"] if lk["text"] == "window")
    assert {g.file(n) for n in window["in_scope"]} == {"a_first.js", "b_second.js"}, window["in_scope"]


@pytest.fixture(scope="module")
def orders(tmp_path_factory):
    """The orders example with a history whose commits state their reasons (the second review's repository)."""
    src = Path(__file__).resolve().parents[1] / "examples" / "orders_app"
    files = {p.relative_to(src).as_posix(): p.read_text(encoding="utf-8") for p in src.rglob("*")
             if p.is_file() and "__pycache__" not in p.parts and p.suffix in (".py", ".md", ".toml")}
    pricing, repository, config, service = (files[f"orders/{n}.py"] for n in ("pricing", "repository", "config",
                                                                               "service"))
    first = dict(files)
    first["orders/pricing.py"] = pricing.replace(
        "    # 10% off above the configured threshold.\n    if subtotal > DISCOUNT_THRESHOLD:\n"
        "        return round(subtotal * 0.9, 2)\n    return subtotal", "    return subtotal")
    first["orders/repository.py"] = repository.replace("        self.conn.commit()\n", "")
    first["orders/config.py"] = config.replace('float(os.environ.get("ORDERS_DISCOUNT_THRESHOLD", "100.0"))', "100.0")
    assert all(first[f] != files[f] for f in ("orders/pricing.py", "orders/repository.py", "orders/config.py"))
    repo = tmp_path_factory.mktemp("scope") / "orders"
    repo.mkdir()
    _git(repo, "init", "-q")
    for rel, text in first.items():
        _write(repo, rel, text)
    _commit(repo, "initial import")
    for rel, text, message in (
            ("orders/pricing.py", pricing,
             "pricing: 10% off above the threshold, because large orders were abandoned at checkout"),
            ("orders/config.py", config, "config: read the discount threshold from the environment"),
            ("orders/repository.py", repository, "repository: commit after every insert so that a crash loses no order"),
            ("orders/service.py", service.replace("    return repo.get(order_id)", "    return repo.get(int(order_id))"),
             "service: cast the id so that a string id from the URL works")):
        _write(repo, rel, text)
        _commit(repo, message)
    return _scanned(repo)


@pytest.mark.parametrize("question", ["Why does the repository commit after every insert?",
                                      "Where is the database connection opened?",
                                      "Where is the maximum number of items per order checked?"])
def test_the_cap_counts_what_the_answer_says_and_leaves_out_function_words(orders, question):
    # each was met on 2ad768f with a right answer, and capped by the first cap (claims one by one, without their
    # text, "after", "every", "per" counted)
    assert _status(_ask(orders, question), "q1") == "met"


def test_a_why_that_names_no_file_keeps_its_records_and_its_slashed_words(orders):
    # without a named file the decision records are matched as before; "None/dict" is no path to drop
    res = _ask(orders, "Why does fetch_order return None or a dict?")
    assert _status(res, "q1") == "met_with_inference" and any(
        c["text"].startswith("Decision record") for c in _answers(res, "q1")), _answers(res, "q1")
    slashed = _ask(orders, "Why does fetch_order return None/dict?")
    assert not any("cast the id" in c["text"] for c in _answers(slashed, "q1")), _answers(slashed, "q1")


def test_a_why_lists_the_lines_commit_once_and_a_moved_case_keeps_its_place(answer, moved):
    (why,) = [u for u in answer["unknowns"] if u.get("sub_question") == "q1" and "reason was not found" in u["why"]]
    shas = [x.split(" ", 1)[0] for x in why["commits"]]
    assert len(shas) == len(set(shas)), why["commits"]
    repo, moved_shas = moved
    (case,) = [c for c in _ask(repo, WHY)["claims"] if "first appears" in c["text"]]
    assert any(moved_shas[0] in e and "bot/herald.js:" in e for e in case.get("evidence") or []), case.get("evidence")
