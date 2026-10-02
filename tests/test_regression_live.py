"""Replay of the live headless run on 2026-10-02 (Claude Code 2.1.287, session 61813435).

Stale "all tests pass" -> tier C, acted=true -> full rerun -> tier A, second Stop silent.
Payload shapes are the ones Claude Code sent in that run. This test must keep passing.
"""
import io
import json
import os

from conftest import FIXTURES
from proof_of_green import hooks, ledger

REPLAY = os.path.join(FIXTURES, "replay_live_2026-10-02.jsonl")


def test_replay_live_run(data, monkeypatch):
    monkeypatch.setenv("CLAUDE_PLUGIN_OPTION_MODE", "warn")
    outputs = []
    with open(REPLAY, encoding="utf-8") as fh:
        steps = [json.loads(line) for line in fh]
    for step in steps:
        out = io.StringIO()
        assert hooks.run(step["hook"], stdin=io.StringIO(json.dumps(step["payload"])), stdout=out) == 0
        outputs.append((step["expect"], out.getvalue()))

    warn, silent = [o for e, o in outputs if e == "warn"], [o for e, o in outputs if e == "silent"]
    assert [o for e, o in outputs if e is None] == ["", "", "", "", ""]
    first = json.loads(warn[0])
    assert first["systemMessage"] == ("proof-of-green: claim 'tests pass' — no test run after your last edit "
                                      "(last run: before edit, 2 failed)")
    assert "run the project's full test command" in first["hookSpecificOutput"]["additionalContext"]
    assert "decision" not in first
    assert silent == [""]

    recs = ledger.read(ledger.session_path(steps[0]["payload"]["session_id"]))
    slim = [(r["seq"], r["turn"], r["kind"]) for r in recs]
    assert slim == [(1, 0, "session"), (2, 1, "turn"), (3, 1, "test_run"), (4, 1, "edit"),
                    (5, 1, "verdict"), (6, 1, "test_run"), (7, 1, "verdict")]
    run1, edit, v1, run2, v2 = recs[2], recs[3], recs[4], recs[5], recs[6]
    assert (run1["event"], run1["exit_code"], run1["scope"], run1["failed"], run1["collected"]) == \
        ("PostToolUseFailure", 1, "all", 2, 3)
    assert (edit["path"], edit["is_test"], edit["code"]) == ("calc.py", False, True)
    assert v1["acted"] is True and v1["claims"] == [{"type": "tests_pass", "scope": "all", "tier": "C"},
                                                   {"type": "fixed", "scope": None, "tier": "C"}]
    assert (run2["event"], run2["exit_code"], run2["passed"], run2["collected"]) == ("PostToolUse", 0, 3, 3)
    assert v2["acted"] is False and v2["claims"] == [{"type": "tests_pass", "scope": "all", "tier": "A"}]
