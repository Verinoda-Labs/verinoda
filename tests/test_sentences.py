"""Sentences that answer a question (verinoda/sentences.py, D180): `query --sentences`, MCP format "sentences"."""

from __future__ import annotations

import os

os.environ.setdefault("GRAPHIFY_OUT", ".verinoda/index")

import json  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

from verinoda import cli, index, sentences, workflow  # noqa: E402
from verinoda.store import open_store  # noqa: E402


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")


@pytest.fixture(scope="module")
def kb(tmp_path_factory):
    root = tmp_path_factory.mktemp("kb") / "biyoloji"
    _write(root, "konular/hucre.md", "# Hücre\n\nHücre canlıların temel yapı birimidir. Dokuları öğrenmeden önce "
                                     "hücreyi\nöğrenmek gerekir.\nHücre zarı seçici geçirgendir.\n")
    _write(root, "konular/doku.md", "# Doku\n\nDoku, benzer hücrelerin oluşturduğu topluluktur. Doku konusu hücre "
                                    "konusunun üzerine kurulur.\nOrganlar dokulardan oluşur; organ konusundan önce "
                                    "doku konusu işlenir.\n")
    _write(root, "konular/organ.md", "# Organ\n\nOrgan, birden fazla dokunun bir araya gelmesiyle oluşur. Sindirim "
                                     "sistemi bir organ sistemidir.\n\n- Organ sistemleri ayrı bir konudur.\n")
    _write(root, "ozet/tekrar.md", "Sindirim sistemi bir organ sistemidir.\n")
    _write(root, "topics.json", '{"topics": ["hucre", "doku", "organ"], "order": "hucre before doku organ"}\n')
    workflow.init(root)
    st = open_store(root)
    try:
        workflow.scan(st, root)
    finally:
        st.close()
    return root


def test_split_keeps_sentences_whole_and_says_their_lines():
    text = ("# Hücre\n\nHücre canlıların temel birimidir. Dokuları öğrenmeden önce hücreyi\nöğrenmek gerekir! "
            "Örn. bitki hücresi farklıdır.\n\n- Mitoz, e.g. somatic cells, is covered in 9. sınıf.\n- Mayoz ikinci "
            "konudur.\n\n```\ncode. Not a sentence.\n```\n\nThe value is 3.5 kg. Then \"quoted end.\" Next one.\n")
    got = [(s.line, s.end_line, s.text) for s in sentences.split(text.splitlines())]
    assert got == [
        (1, 1, "# Hücre"),
        (3, 3, "Hücre canlıların temel birimidir."),
        (3, 4, "Dokuları öğrenmeden önce hücreyi öğrenmek gerekir!"),  # a sentence across two lines
        (4, 4, "Örn. bitki hücresi farklıdır."),                         # an abbreviation does not end it
        (6, 6, "- Mitoz, e.g. somatic cells, is covered in 9. sınıf."),  # nor does "e.g." or an ordinal
        (7, 7, "- Mayoz ikinci konudur."),                               # a list item is its own block
        (13, 13, "The value is 3.5 kg."),                                # fenced code is left out
        (13, 13, 'Then "quoted end."'),                                  # the closing quote stays
        (13, 13, "Next one."),
    ]


def test_a_turkish_question_finds_the_sentences_through_its_suffixes(kb):
    res = sentences.find(index.load(kb), "dokudan önce hangi konu öğrenilmeli")
    got = [(s["file"], s["line"], s["text"]) for s in res["sentences"]]
    assert got[0] == ("konular/hucre.md", 3, "Dokuları öğrenmeden önce hücreyi öğrenmek gerekir.")
    assert ("konular/doku.md", 4, "Organlar dokulardan oluşur; organ konusundan önce doku konusu işlenir.") in got
    assert res["needed"] == 2 and res["sentences"][0]["end_line"] == 4
    assert all(not s["text"].startswith("#") for s in res["sentences"])  # headings are not sentences
    assert res["files_not_prose"] == 1  # topics.json is ranked, not read


def test_a_sentence_is_listed_once_and_the_list_is_capped(kb):
    res = sentences.find(index.load(kb), "organ sistemi")
    [only] = res["sentences"]
    assert only["text"] == "Sindirim sistemi bir organ sistemidir."
    assert {f"{only['file']}:{only['line']}", *only["also_at"]} == {"konular/organ.md:3", "ozet/tekrar.md:1"}
    assert sentences.render(res).startswith("sentences holding 2 or more of: organ, sistemi")
    capped = sentences.find(index.load(kb), "organ", max_items=1)
    assert len(capped["sentences"]) == 1 and capped["more"] >= 2
    assert "(+" in sentences.render(capped) and "--max-items" in sentences.render(capped)


def test_filters_narrow_the_files_read(kb):
    res = sentences.find(index.load(kb), "organ path:ozet/**")
    assert [s["file"] for s in res["sentences"]] == ["ozet/tekrar.md"]
    assert res["filters"]


def test_cli_and_mcp_return_sentences(kb, capsys):
    capsys.readouterr()
    assert cli.main(["query", "dokudan önce hangi konu öğrenilmeli", "--sentences", "--repo", str(kb)]) == 0
    out = capsys.readouterr().out
    assert "konular/hucre.md:3-4  Dokuları öğrenmeden önce hücreyi öğrenmek gerekir." in out
    assert "## " not in out  # no passages
    assert cli.main(["query", "organ", "--sentences", "--json", "--max-items", "2", "--repo", str(kb)]) == 0
    res = json.loads(capsys.readouterr().out)
    assert len(res["sentences"]) == 2 and res["sentences"][0]["file"].endswith(".md")
    from verinoda.mcp.server import AtlasTools

    t = AtlasTools(kb)
    m = t.project_query("dokudan önce hangi konu öğrenilmeli", format="sentences")
    assert m["format"] == "text" and m["text"].splitlines()[1].startswith("konular/hucre.md:3-4")
