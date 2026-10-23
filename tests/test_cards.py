"""File cards (docs/DESIGN.md D189): one line per file a conversation read or edited, handed to Claude Code's
compaction so its summary keeps what the file is, not the file's text."""

from __future__ import annotations

import json
import struct
import sys
import zlib
from pathlib import Path

import pytest

from verinoda import cards

JAVA = """/*
 * Copyright (c) 2026 Somebody. Licensed under the MIT license.
 */
package tr.example.mod.iblis;

import tr.example.mod.build.TaskQueue;
import tr.example.mod.cekirdek.Ayar;
import net.minecraft.server.level.ServerLevel;
import static java.lang.Math.max;

/**
 * Builds the demon's castle in the world and resets it between rounds.
 * Used by the round controller.
 */
public class Kale {
    public static void initialize() {}

    public int konum() { return 1; }

    private void build(ServerLevel level) {}
}
"""

JS = """#!/usr/bin/env node
// Talks to the Claude API for the herald bot: one reply per chat line, under a daily budget.
const fs = require('fs');
import { dailyLeft } from './budget.js';
import 'dotenv/config';

function relay(line) { return dailyLeft() ? line : ''; }
async function pump() { return relay('x'); }
"""

PY = '''"""Path rules for the index: where its files live and which paths stay inside a root.

More text that is not the first sentence.
"""
import os
from pathlib import Path

from verinoda.store import open_store


def atlas_dir(repo):
    return Path(repo) / ".verinoda"


class Root:
    def inside(self, p):
        return True
'''

MD = """# Dünya 1:1 Planı - Lawrence, Kansas

Intro paragraph.

## Su

## Yol

## Arazi
"""


def _png(w: int, h: int) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IEND", b"")


@pytest.fixture()
def repo(tmp_path):
    r = tmp_path / "proj"
    (r / "src" / "iblis").mkdir(parents=True)
    (r / "tools").mkdir()
    (r / "docs").mkdir()
    (r / "art").mkdir()
    (r / "src" / "iblis" / "Kale.java").write_text(JAVA, encoding="utf-8")
    (r / "tools" / "herald.js").write_text(JS, encoding="utf-8")
    (r / "src" / "paths.py").write_text(PY, encoding="utf-8")
    (r / "docs" / "PLAN.md").write_text(MD, encoding="utf-8")
    (r / "art" / "wing.png").write_bytes(_png(640, 480))
    (r / "art" / "blob.bin").write_bytes(b"\x00\x01\x02binary\x00" * 50)
    (r / "build.sh").write_text("#!/bin/sh\n# Builds the plugin jar and copies it to the server.\n./gradlew jar\n",
                                encoding="utf-8")
    return r


def _one(repo, path):
    got = cards.cards(repo, [path])
    assert len(got["cards"]) == 1, got
    return got["cards"][0]


def test_a_java_card_skips_the_license_and_reads_the_class_javadoc(repo):
    c = _one(repo, "src/iblis/Kale.java")
    assert c["kind"] == "text" and c["path"] == "src/iblis/Kale.java" and c["lines"] == JAVA.count("\n")
    assert c["purpose"] == "Builds the demon's castle in the world and resets it between rounds."
    assert c["defines"] == ["Kale: initialize, konum, build"]
    assert c["imports"] == ["build.TaskQueue", "cekirdek.Ayar", "level.ServerLevel", "lang.Math"]
    line = cards.render(c)
    assert line.startswith("src/iblis/Kale.java (") and "Copyright" not in line and "Licensed" not in line, line


def test_a_js_card_reads_the_leading_comment_after_the_shebang_and_every_import_form(repo):
    c = _one(repo, "tools/herald.js")
    assert c["purpose"].startswith("Talks to the Claude API for the herald bot")
    assert c["imports"] == ["fs", "./budget.js", "dotenv/config"]
    assert set(c["defines"]) >= {"relay", "pump"}


def test_a_python_card_takes_the_docstring_first_sentence_top_level_names_and_imports(repo):
    c = _one(repo, "src/paths.py")
    assert c["purpose"] == "Path rules for the index: where its files live and which paths stay inside a root."
    assert c["defines"] == ["atlas_dir", "Root"]
    assert c["imports"] == ["os", "pathlib", "verinoda.store"]


def test_markdown_images_binaries_and_scripts_get_cards_of_their_own(repo):
    md = _one(repo, "docs/PLAN.md")
    assert md["purpose"] == "Dünya 1:1 Planı - Lawrence, Kansas" and md["defines"] == ["Su", "Yol", "Arazi"]
    png = _one(repo, "art/wing.png")
    assert png["kind"] == "image" and cards.render(png) == "art/wing.png: image 640x480"
    binary = _one(repo, "art/blob.bin")
    assert binary["kind"] == "binary" and "binary" in cards.render(binary)
    sh = _one(repo, "build.sh")
    assert sh["purpose"] == "Builds the plugin jar and copies it to the server." and not sh.get("defines")


def test_a_path_outside_the_project_is_refused_before_the_file_system_is_asked(repo, tmp_path, monkeypatch):
    outside = tmp_path / "secret.txt"
    outside.write_text("do not read\n", encoding="utf-8")
    asked: list[str] = []
    real_stat = Path.stat

    def watched(self, *a, **kw):
        if str(self).startswith("\\\\"):
            asked.append(str(self))
        return real_stat(self, *a, **kw)

    monkeypatch.setattr(Path, "stat", watched)
    for p in (str(outside), "../secret.txt", "\\\\server\\share\\x.java", "C:\\Windows\\win.ini", "a:stream"):
        c = _one(repo, p)
        assert c["kind"] == "outside" and "do not read" not in json.dumps(c), (p, c)
    assert asked == []  # a UNC path is never stat'ed: that alone would open the share


def test_an_absolute_path_under_the_project_is_carded_as_relative_and_a_deleted_file_said_so(repo):
    c = _one(repo, str(repo / "src" / "paths.py"))
    assert c["path"] == "src/paths.py" and c["kind"] == "text"
    gone = _one(repo, "src/removed.py")
    assert gone["kind"] == "missing" and cards.render(gone) == "src/removed.py: not on disk now"


def test_the_budget_keeps_whole_cards_and_counts_the_rest(repo):
    many = ["src/iblis/Kale.java", "tools/herald.js", "src/paths.py", "docs/PLAN.md", "art/wing.png", "build.sh"]
    got = cards.cards(repo, many, max_chars=260)
    assert 0 < len(got["cards"]) < len(many) and got["more"] == len(many) - len(got["cards"])
    assert len(got["text"]) <= 260 + 80 and got["text"].rstrip().endswith("more file(s): no card for the budget")
    # the same path twice is one card
    assert len(cards.cards(repo, ["build.sh", "./build.sh", str(repo / "build.sh")])["cards"]) == 1


def test_a_large_file_is_carded_from_its_size_alone(repo, monkeypatch):
    monkeypatch.setattr(cards, "MAX_BYTES", 100)
    c = _one(repo, "src/iblis/Kale.java")
    assert c["kind"] == "too_large" and "too large" in cards.render(c)


def test_the_cli_prints_the_cards_and_makes_no_project_state(repo, capsys):
    from verinoda import cli

    assert cli.main(["card", "--repo", str(repo), "src/paths.py", "art/wing.png"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0].startswith("src/paths.py (") and "art/wing.png: image 640x480" in out
    assert cli.main(["card", "--repo", str(repo), "--json", "--", "build.sh"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["cards"][0]["path"] == "build.sh" and "text" in data
    assert not (repo / ".verinoda").exists()


def test_import_verinoda_cli_does_not_load_the_card_code():
    import subprocess

    code = "import sys, verinoda.cli; print('verinoda.cards' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout.strip()
    assert out == "False"
