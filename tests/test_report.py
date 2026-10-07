import os
import subprocess
import sys

from conftest import ROOT, Session
from proof_of_green import report


def _scripted(sid):
    s = Session(sid=sid)
    s.start()
    s.prompt()
    s.bash("pytest", "==== 1 failed, 3 passed in 0.1s ====", exit_code=1)
    s.edit()
    s.stop("Fixed. All tests pass.")          # turn 1: C, warned
    s.prompt()
    s.edit()
    s.bash("pytest || true", "==== 4 passed in 0.1s ====")
    s.stop("I changed the parser.")           # turn 2: edit, no claim
    s.prompt()
    s.stop("Done.")                           # turn 3: no edit
    return s


def test_report_numbers(data, capsys):
    _scripted("aaaa1111")
    assert report.main(["--data", str(data)]) == 0
    out = capsys.readouterr().out
    assert "turns with code edits      2 of 3" in out
    assert "claims by type             done 1, fixed 1, tests_pass 1" in out
    assert "warnings issued            1" in out
    assert "edit turns with no claim   50%" in out
    assert "suspicious test flags      1 (|| true ×1)" in out
    assert "turn 1  fixed  tier C" in out


def test_report_all_aggregates(data, capsys):
    _scripted("aaaa1111")
    _scripted("bbbb2222")
    report.main(["--all", "--data", str(data)])
    out = capsys.readouterr().out
    assert "proof-of-green report — 2 sessions" in out
    assert "warnings issued            2" in out
    assert "session bbbb2222 turn 1" in out


def test_report_empty(data, capsys):
    report.main(["--data", str(data)])
    assert "no sessions recorded yet" in capsys.readouterr().out


def test_report_script_uses_env(data):
    _scripted("cccc3333")
    env = dict(os.environ, CLAUDE_PLUGIN_DATA=str(data))
    proc = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "report.py")],
                          capture_output=True, text=True, env=env, timeout=10)
    assert proc.returncode == 0 and "session cccc3333" in proc.stdout


def test_unparsed_test_runs_line(data, capsys):
    s = Session(sid="unparsed1")
    s.start()
    s.prompt()
    s.bash("flutter test --coverage", "some output the parser does not know")
    s.bash("flutter test test/a_test.dart", "still unknown")
    s.bash("cd app && make check", "make: nothing to report")
    s.bash("fastlane ios test", "")
    s.bash("pytest -q", "==== 3 passed in 0.1s ====")          # parsed, not counted
    s.bash("ls -la", "total 0")                                # not a test run
    report.main(["--data", str(data)])
    out = capsys.readouterr().out
    assert "unparsed test runs         4 (flutter test ×2, make check ×1, fastlane ios ×1)" in out


def test_unparsed_none(data, capsys):
    _scripted("dddd4444")
    report.main(["--data", str(data)])
    assert "unparsed test runs         0 (none)" in capsys.readouterr().out


def test_report_current_session_by_id(data, capsys):
    _scripted("aaaa1111")
    _scripted("bbbb2222")          # newest file; the old behaviour would have shown this one
    report.main(["--data", str(data), "--session", "aaaa1111"])
    out = capsys.readouterr().out
    assert "session aaaa1111" in out and "bbbb2222" not in out


def test_report_unrecorded_session_says_restart(data, capsys):
    _scripted("aaaa1111")
    report.main(["--data", str(data), "--session", "zzzz9999-not-recorded"])
    out = capsys.readouterr().out
    assert "has no record" in out and "claude --resume zzzz9999-not-recorded" in out


def test_report_unsubstituted_session_placeholder_falls_back(data, capsys):
    _scripted("aaaa1111")
    report.main(["--data", str(data), "--session", "${CLAUDE_SESSION_ID}"])
    assert "session aaaa1111" in capsys.readouterr().out


def test_report_reads_all_data_folders(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)
    base = tmp_path / ".claude" / "plugins" / "data"
    for folder, sid in (("proof-of-green-proof-of-green", "term1111"), ("proof-of-green-inline", "desk2222")):
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(base / folder))
        _scripted(sid)
    monkeypatch.delenv("CLAUDE_PLUGIN_DATA")
    report.main(["--all"])
    out = capsys.readouterr().out
    assert "2 sessions" in out and "proof-of-green-inline" in out and "proof-of-green-proof-of-green" in out
    report.main(["--session", "desk2222"])
    assert "session desk2222" in capsys.readouterr().out


def test_report_counts_masked_runs(data, capsys):
    s = Session(sid="masked1")
    s.start()
    s.prompt()
    s.bash("npm test 2>&1 | tail -20", "Tests: 3 passed, 3 total")
    s.bash("pytest -q", "==== 2 passed in 0.1s ====")
    report.main(["--data", str(data), "--session", "masked1"])
    assert "exit code masked by pipe   1" in capsys.readouterr().out
