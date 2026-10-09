"""The usage log (verinoda/usage.py, D178): one line per CLI command with what the agent read of it, totals."""

from __future__ import annotations

import json

import pytest

from verinoda import cli, usage


@pytest.fixture
def log(tmp_path, monkeypatch):
    p = tmp_path / "logs" / "usage.jsonl"
    monkeypatch.setenv("VERINODA_USAGE_LOG", str(p))
    return p


def _rows(p):
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()]


def test_no_variable_no_log(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("VERINODA_USAGE_LOG", raising=False)
    cli.main(["doctor", "--brief", "--repo", str(tmp_path)])
    assert usage.log_path() is None and not list(tmp_path.rglob("*.jsonl"))


def test_a_command_is_logged_with_its_output_and_errors(tmp_path, log, capsys):
    rc = cli.main(["doctor", "--brief", "--repo", str(tmp_path)])
    out = capsys.readouterr()
    rows = _rows(log)
    assert [(r["surface"], r["name"]) for r in rows] == [("cli", "doctor")]
    assert rows[0]["result_chars"] == len(out.out) + len(out.err) and rows[0]["stderr_chars"] == len(out.err)
    assert rows[0]["args_chars"] == len(" ".join(["doctor", "--brief", "--repo", str(tmp_path)]))
    assert ("error" in rows[0]) == bool(rc)
    with pytest.raises(SystemExit) as exc:  # an error that ends the command: its message counts too
        cli.main(["query", "x", "--repo", str(tmp_path / "nowhere"), "--read-only"])
    capsys.readouterr()
    last = _rows(log)[-1]
    assert last["name"] == "query" and last["error"] == "exit 1"
    assert last["stderr_chars"] == len(str(exc.value.code)) + 1


def test_totals_per_tool_and_the_usage_command(tmp_path, log, capsys):
    log.parent.mkdir(parents=True)
    log.write_text("\n".join([
        json.dumps({"surface": "mcp", "name": "analyze", "args_chars": 40, "result_chars": 4000, "seconds": 1.5}),
        json.dumps({"surface": "mcp", "name": "analyze", "args_chars": 30, "result_chars": 2000, "seconds": 0.5,
                    "error": "error"}),
        json.dumps({"surface": "cli", "name": "query", "args_chars": 20, "result_chars": 1000, "seconds": 0.25}),
        "not json",
    ]) + "\n", encoding="utf-8")
    res = usage.summarize(log)
    assert [(r["name"], r["calls"], r["result_chars"], r["errors"]) for r in res["rows"]] == [
        ("analyze", 2, 6000, 1), ("query", 1, 1000, 0)]
    assert res["total"] == {"calls": 3, "args_chars": 90, "result_chars": 7000, "errors": 1,
                            "result_tokens_est": 1750, "seconds": 2.25}
    assert res["unreadable_lines"] == 1 and "not the model's tokenizer" in res["tokens_est"]
    before = log.read_text(encoding="utf-8")
    assert cli.main(["usage", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["total"]["calls"] == 3
    assert log.read_text(encoding="utf-8") == before  # reading the log is not logged
    assert cli.main(["usage"]) == 0
    assert "3 call(s), 7000 result characters (~1750 tokens" in capsys.readouterr().out
