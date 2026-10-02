import io
import json
import os
import subprocess
import sys
import time
from multiprocessing import Pool

import pytest

from conftest import FIXTURES, ROOT, Session, load
from proof_of_green import hooks, ledger

SCRIPTS = {
    "session_start.py": "session_start.json",
    "user_prompt.py": "user_prompt.json",
    "post_edit.py": "post_edit.tool_response.json",
    "post_bash.py": "post_bash_fail.failure.json",
    "stop.py": "stop.json",
}


def run_script(script, stdin_bytes, env):
    return subprocess.run([sys.executable, os.path.join(ROOT, "scripts", script)],
                          input=stdin_bytes, capture_output=True, env=env, timeout=10)


@pytest.fixture
def env(data):
    e = dict(os.environ)
    e["CLAUDE_PLUGIN_DATA"] = str(data)
    return e


@pytest.mark.parametrize("script", sorted(SCRIPTS))
@pytest.mark.parametrize("garbage", [b"", b"{not json", b"[1, 2]", b"\xff\xfe", b"null"])
def test_fail_open_on_malformed_stdin(script, garbage, env, data):
    proc = run_script(script, garbage, env)
    assert proc.returncode == 0
    assert proc.stdout == b""


def test_fail_open_logs_one_line(data):
    out = io.StringIO()
    assert hooks.run("Stop", stdin=io.StringIO("{oops"), stdout=out) == 0
    assert out.getvalue() == ""
    lines = (data / "errors.log").read_text().splitlines()
    assert len(lines) == 1 and "Stop" in lines[0] and "oops" not in lines[0]


def test_handler_exception_fails_open(data, monkeypatch):
    def boom(_):
        raise RuntimeError("kaboom")
    monkeypatch.setitem(hooks.HANDLERS, "Stop", boom)
    assert hooks.run("Stop", stdin=io.StringIO("{}"), stdout=io.StringIO()) == 0
    assert "RuntimeError: kaboom" in (data / "errors.log").read_text()


def test_no_plugin_data_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)
    monkeypatch.chdir(tmp_path)
    for name, fixture in [("SessionStart", "session_start.json"), ("Stop", "stop.json"),
                          ("PostToolUse:bash", "post_bash_pass.tool_response.json")]:
        hooks.run(name, stdin=io.StringIO(json.dumps(load(fixture))), stdout=io.StringIO())
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("script,fixture", sorted(SCRIPTS.items()))
def test_scripts_run_fast_and_quiet(script, fixture, env, data):
    payload = json.dumps(load(fixture)).encode()
    start = time.time()
    proc = run_script(script, payload, env)
    elapsed = time.time() - start
    assert proc.returncode == 0 and proc.stderr == b""
    assert elapsed < 1.0  # whole interpreter start-up included; hook body is a few ms


def test_stop_script_output_is_valid_json(env, data):
    sid_env = dict(env)
    for script, fixture in [("session_start.py", "session_start.json"), ("user_prompt.py", "user_prompt.json"),
                            ("post_bash.py", "post_bash_fail.failure.json"),
                            ("post_edit.py", "post_edit.tool_response.json")]:
        run_script(script, json.dumps(load(fixture)).encode(), sid_env)
    proc = run_script("stop.py", json.dumps(load("stop.json")).encode(), sid_env)
    out = json.loads(proc.stdout)
    assert set(out) == {"systemMessage", "hookSpecificOutput"}
    assert out["hookSpecificOutput"]["hookEventName"] == "Stop"


def test_writes_stay_inside_plugin_data(env, data, tmp_path):
    cwd = tmp_path / "project"
    cwd.mkdir()
    for script, fixture in SCRIPTS.items():
        subprocess.run([sys.executable, os.path.join(ROOT, "scripts", script)], cwd=str(cwd),
                       input=json.dumps(load(fixture)).encode(), env=env, capture_output=True, timeout=10)
    assert list(cwd.iterdir()) == []
    written = {p.relative_to(data).as_posix() for p in data.rglob("*") if p.is_file()}
    assert written == {"sessions/fixture-session.jsonl"}


def test_ledger_has_no_raw_output_or_prompt(data):
    s = Session(sid="privacy")
    s.prompt("my secret prompt words")
    s.fire("PostToolUse:bash", load("post_bash_other.tool_response.json"))
    s.fire("PostToolUse:bash", load("post_bash_fail.failure.json"))
    raw = open(ledger.session_path("privacy"), encoding="utf-8").read()
    assert "secret prompt" not in raw and "SENTINEL" not in raw and "FAIL: test_add" not in raw
    assert "ghp_" not in raw and "transcript" not in raw


def test_records_have_increasing_seq_and_turns(data):
    s = Session(sid="seq")
    s.start()
    s.prompt()
    s.edit()
    s.prompt()
    recs = s.records()
    assert [r["seq"] for r in recs] == [1, 2, 3, 4]
    assert [r["turn"] for r in recs] == [0, 1, 1, 2]


def _append(args):
    base, i = args
    os.environ["CLAUDE_PLUGIN_DATA"] = base
    ledger.append("conc", {"kind": "other", "i": i})


def test_concurrent_appends_keep_unique_seq(data):
    with Pool(8) as pool:
        pool.map(_append, [(str(data), i) for i in range(80)])
    recs = ledger.read(ledger.session_path("conc"))
    assert len(recs) == 80
    assert sorted(r["seq"] for r in recs) == list(range(1, 81))


def test_edit_fixture_variants(data):
    s = Session(sid="variants")
    for name in ("post_edit.tool_response.json", "post_edit.tool_output.json", "post_edit_test.tool_response.json"):
        s.fire("PostToolUse:edit", load(name))
    edits = [(r["path"], r["is_test"], r["code"]) for r in s.records()]
    assert edits == [("calc.py", False, True), ("calc.py", False, True), ("tests/test_calc.py", True, True)]


@pytest.mark.parametrize("path,is_test", [
    ("tests/test_api.py", True), ("src/test_utils.py", True), ("pkg/server_test.go", True),
    ("src/app.spec.ts", True), ("src/app.test.tsx", True), ("web/__tests__/x.js", True),
    ("test/helpers.rb", True), ("spec/models/user_spec.rb", True), ("lib/widget_test.dart", True),
    ("AppTests/LoginTests.swift", True), ("Tests/Foo.swift", True), ("conftest.py", True),
    ("src/app.ts", False), ("pkg/server.go", False), ("contest.py", False), ("src/testing_utils.py", False),
])
def test_is_test_path(path, is_test):
    assert hooks.is_test_path(path) is is_test


def test_hooks_json_shape():
    with open(os.path.join(ROOT, "hooks", "hooks.json")) as fh:
        cfg = json.load(fh)["hooks"]
    assert set(cfg) == {"SessionStart", "UserPromptSubmit", "PostToolUse", "PostToolUseFailure", "Stop"}
    for groups in cfg.values():
        for group in groups:
            for hook in group["hooks"]:
                assert hook["command"] == "python3"
                assert hook["args"][0].startswith("${CLAUDE_PLUGIN_ROOT}/scripts/")
                assert os.path.exists(hook["args"][0].replace("${CLAUDE_PLUGIN_ROOT}", ROOT))


def test_repo_rules():
    assert not os.path.exists(os.path.join(ROOT, "bin"))
    assert not os.path.exists(os.path.join(ROOT, "CLAUDE.md"))
    for dirpath, _, files in os.walk(os.path.join(ROOT, "proof_of_green")):
        for f in files:
            if f.endswith(".py"):
                src = open(os.path.join(dirpath, f), encoding="utf-8").read()
                for banned in ("urllib", "http.client", "socket", "requests", "transcript_path"):
                    assert banned not in src, (f, banned)
    assert os.path.isdir(FIXTURES)
