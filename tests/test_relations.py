"""Relations between the topics of a prose corpus (verinoda/relations.py, D181): the topics file, the topics a
sentence names, the rules (with sentences that are not the synthetic corpus's templates), and the view."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from verinoda import cli, relations

TOPICS = ["Hücre", "Doku", "Organ", "Organeller", "Gen", "Kromozom", "Mitoz", "Mayoz", "DNA", "RNA", "Hücre zarı",
          "Ekosistem", "Besin zinciri"]


@pytest.fixture(scope="module")
def matcher():
    return relations._Matcher(relations.parse_topics(json.dumps({"topics": TOPICS}, ensure_ascii=False)))


@pytest.mark.parametrize("sentence,file_topic,want,rule", [
    # Turkish: the order is read from the endings and the cue, not from word order
    ("Dokuları öğrenmeden önce hücreyi öğrenmek gerekir.", None, ("Hücre", "Doku"), "tr-meden-once"),
    ("Hücreyi bilmeden dokuya geçilmez.", None, ("Hücre", "Doku"), "tr-meden-negated"),
    ("Hücreyi öğrenmeden önce dokuya geçilmez.", None, ("Hücre", "Doku"), "tr-meden-once"),   # negation flips
    ("Önce hücre, sonra doku işlenir.", None, ("Hücre", "Doku"), "tr-once-sonra"),
    ("Doku, hücrenin üzerine kurulur.", None, ("Hücre", "Doku"), "tr-uzerine-kurulur"),
    ("Mitoz için kromozom bilgisi gereklidir.", None, ("Kromozom", "Mitoz"), "tr-onkosul"),
    ("Ekosistem, besin zincirinin temelidir.", None, ("Ekosistem", "Besin zinciri"), "tr-onkosul"),
    ("DNA'dan sonra RNA'ya geçilir.", None, ("DNA", "RNA"), "tr-ablative-sonra"),
    ("Organ konusu, doku konusunu gerektirir.", None, ("Doku", "Organ"), "tr-gerektirir"),
    ("Kromozomu anlamak için geni bilmek gerekir.", None, ("Gen", "Kromozom"), "tr-anlamak-icin"),
    ("Hücre zarı konusundan önce Hücre konusu öğrenilmelidir.", None, ("Hücre", "Hücre zarı"), "tr-ablative-once"),
    ("Doku konusundan önce Hücre konusu öğrenilmelidir; Organ konusu da önemlidir.", None, ("Hücre", "Doku"),
     "tr-ablative-once"),
    # one end is the file's own topic: "bu konu", or the subject Turkish leaves out
    ("Bu konudan önce hücre konusu öğrenilmelidir.", "Doku", ("Hücre", "Doku"), "tr-ablative-once"),
    ("Hücre konusundan sonra gelir.", "Doku", ("Hücre", "Doku"), "tr-ablative-sonra"),
    # English
    ("Learn DNA before RNA.", None, ("DNA", "RNA"), "en-before"),
    ("Before RNA, students should know DNA.", None, ("DNA", "RNA"), "en-before-initial"),
    ("RNA builds on DNA.", None, ("DNA", "RNA"), "en-requires"),
    ("DNA is a prerequisite for RNA.", None, ("DNA", "RNA"), "en-prerequisite"),
])
def test_the_order_a_sentence_states(matcher, sentence, file_topic, want, rule):
    rel, _ = relations.read_sentence(sentence, matcher, file_topic)
    assert rel is not None and (rel.earlier.topic, rel.later.topic) == want and rel.rule == rule
    assert rel.kind == "prerequisite"
    assert rel.negated == ("geçilmez" in sentence)
    assert (rel.earlier.implicit or rel.later.implicit) == (file_topic is not None)


@pytest.mark.parametrize("sentence,named", [
    ("Organ konusu, doku konusunu gerektirmez.", 2),           # a negated requirement states none
    ("RNA doesn't require DNA.", 2),
    ("Doku konusu ile organ konusu sınavlarda birlikte sorulabilir.", 2),   # asked together is not a relation
    ("Organeller konusu önemlidir ve hücre ile ilgilidir.", 2),
    ("Genetik bilgisi kromozom konusunda geçer.", 1),          # "Gen" is not in "Genetik"
])
def test_no_relation_without_a_cue_or_with_a_negated_requirement(matcher, sentence, named):
    rel, n = relations.read_sentence(sentence, matcher)
    assert rel is None and n == named


def test_words_that_only_look_like_cues(matcher):
    # bare "temel" is the adjective "basic", not "the basis of"
    assert relations.read_sentence("Hücrenin temel kavramları önemlidir.", matcher, "Doku")[0] is None
    # "maden" (mineral) is a noun, not a verb's "-meden"
    assert relations.read_sentence("Hücre ve doku maden yataklarında incelenmez.", matcher)[0] is None
    # a negation turns only its own clause
    rel, _ = relations.read_sentence("Doku konusundan önce Hücre konusu öğrenilmelidir; Organ konusu bilinmez.",
                                     matcher)
    assert (rel.earlier.topic, rel.later.topic) == ("Hücre", "Doku") and not rel.negated
    rel, _ = relations.read_sentence("Organ konusu, doku konusunu gerektirir, ama mitoz bilinmez.", matcher)
    assert (rel.earlier.topic, rel.later.topic) == ("Doku", "Organ") and not rel.negated


def test_names_are_matched_with_noun_endings_only_and_the_longest_first(matcher):
    def named(s):
        return [m.topic for m in relations.mentions(s, matcher)[0]]

    assert named("Organeller ve organlar") == ["Organeller", "Organ"]
    assert named("genel bir genetik bilgisi ve genlerin dizilişi") == ["Gen"]
    assert named("Hücre zarının yapısı ve hücrenin çekirdeği") == ["Hücre zarı", "Hücre"]
    assert named("DNA'nın kopyası RNA'dır") == ["DNA", "RNA"]
    roles = [(m.topic, m.role) for m in relations.mentions("Doku konusundan önce hücreyi", matcher)[0]]
    assert roles == [("Doku", "source"), ("Hücre", "object")]   # the head noun's case when the name is bare


def test_shared_needs_its_own_cue(matcher):
    rel, _ = relations.read_sentence("Mitoz ve mayoz ortak kavramlara sahiptir.", matcher)
    assert rel.kind == "shared" and {rel.earlier.topic, rel.later.topic} == {"Mitoz", "Mayoz"}


@pytest.mark.parametrize("text,suffix,names,aliases", [
    ('["Hücre", "Doku"]', ".json", ["Hücre", "Doku"], {}),
    ('[{"title": "Hücre", "synonyms": "hücreler, cell"}]', ".json", ["Hücre"], {"Hücre": 3}),
    ('{"topics": [{"name": "DNA", "aliases": ["deoksiribonükleik asit"]}], "order": []}', ".json", ["DNA"],
     {"DNA": 2}),
    ('{"Hücre": ["cell"], "Doku": null}', ".json", ["Hücre", "Doku"], {"Hücre": 2}),
    ("# konular\nHücre | cell, hücreler\nDoku\n", ".txt", ["Hücre", "Doku"], {"Hücre": 3}),
])
def test_the_shapes_a_topics_file_may_have(text, suffix, names, aliases):
    topics = relations.parse_topics(text, suffix)
    assert [t.name for t in topics] == names
    for name, n in aliases.items():
        assert len(next(t for t in topics if t.name == name).forms) == n


@pytest.mark.parametrize("text", ['{"topics": 5}', "[1, 2]", "[]", "not json at all ["])
def test_a_topics_file_of_another_shape_is_refused_with_the_shapes_it_may_have(text):
    with pytest.raises(relations.TopicsError):
        relations.parse_topics(text, ".json")


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")


@pytest.fixture
def corpus(tmp_path):
    root = tmp_path / "kb"
    _write(root, "topics.txt", "Hücre | cell\nDoku\nOrgan\nMitoz\nMayoz\n")
    _write(root, "konular/doku.md", "# Doku\n\nDoku konusundan önce Hücre konusu öğrenilmelidir. Bu konu, organ "
                                    "konusunun ön koşuludur.\n")
    _write(root, "konular/organ.md", "# Organ\n\nOrgan konusu, doku konusunun üzerine kurulur.\n\nDoku konusundan "
                                     "sonra gelir.\n")
    _write(root, "konular/mitoz.md", "# Mitoz\n\nMitoz konusundan önce Mayoz konusu öğrenilmelidir.\n")
    _write(root, "konular/mayoz.md", "# Mayoz\n\nMayoz konusundan önce Mitoz konusu öğrenilmelidir. Mitoz ile "
                                     "mayoz sınavlarda birlikte sorulabilir.\n")
    _write(root, "notes.py", "# Doku konusundan önce Hücre konusu öğrenilmelidir.\n")   # not prose: not read
    return root


def test_the_view_joins_sources_marks_conflicts_and_the_files_own_topic(corpus):
    res = relations.find(corpus, topics_file="topics.txt")
    rows = {(r["from"], r["to"]): r for r in res["relations"]}
    assert rows[("Doku", "Organ")]["sources"] == 3 and rows[("Doku", "Organ")]["status"] == "strong_inference"
    assert {e["implicit"] for e in rows[("Doku", "Organ")]["evidence"]} == {True, False}
    assert rows[("Hücre", "Doku")]["evidence"][0] == {
        "file": "konular/doku.md", "line": 3, "end_line": 3, "rule": "tr-ablative-once", "implicit": False,
        "negated": False, "text": "Doku konusundan önce Hücre konusu öğrenilmelidir."}
    # two files give Mitoz and Mayoz opposite orders: both are kept, neither is taken at its word
    assert rows[("Mayoz", "Mitoz")]["conflict"] and rows[("Mitoz", "Mayoz")]["conflict"]
    assert rows[("Mayoz", "Mitoz")]["status"] == rows[("Mitoz", "Mayoz")]["status"] == "weak_inference"
    assert res["files_read"] == 4 and res["files_not_prose"] == 1 and res["co_mentions"] == 1
    assert res["topics_file"] == "topics.txt"   # read for its names, not as prose


def test_one_topic_kind_and_the_config(corpus, capsys):
    res = relations.find(corpus, "hücre", topics_file="topics.txt")   # a name in any case
    assert res["focus"] == "Hücre" and [(r["from"], r["to"]) for r in res["relations"]] == [("Hücre", "Doku")]
    assert relations.find(corpus, "cell", topics_file="topics.txt")["focus"] == "Hücre"   # an alias
    with pytest.raises(relations.TopicsError, match="not a topic"):
        relations.find(corpus, "Kalp", topics_file="topics.txt")
    with pytest.raises(relations.TopicsError, match="no topics file"):
        relations.find(corpus)
    (corpus / ".verinoda").mkdir()
    (corpus / ".verinoda" / "config.json").write_text(json.dumps({"corpus": {"topics": "topics.txt"}}),
                                                      encoding="utf-8")
    assert relations.find(corpus, kind="shared")["relations"] == []
    capsys.readouterr()
    assert cli.main(["relations", "Doku", "--repo", str(corpus)]) == 0
    out = capsys.readouterr().out
    assert out.startswith("relations for Doku (topics.txt: 5 topics; 4 prose file(s) read)")
    assert 'Hücre -> Doku  prerequisite  strong_inference  konular/doku.md:3  "Doku konusundan önce' in out
    assert cli.main(["relations", "--repo", str(corpus), "--json", "--co-mentions"]) == 0
    res = json.loads(capsys.readouterr().out)
    assert res["co_mention_examples"][0]["file"] == "konular/mayoz.md"


def test_a_topics_file_outside_the_project_is_refused(corpus, tmp_path):
    _write(tmp_path, "outside.txt", "Hücre\n")
    with pytest.raises(relations.TopicsError, match="not inside the project"):
        relations.find(corpus, topics_file=str(tmp_path / "outside.txt"))
    with pytest.raises(SystemExit, match="no such file"):
        cli.main(["relations", "--repo", str(corpus), "--topics", "missing.json"])
