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
