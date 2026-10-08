"""Codex hook payloads (v0.2): same envelope as Claude Code, different tools."""
import json

PASS4 = "4 passed in 0.10s"
PATCH = ("*** Begin Patch\n*** Update File: /repo/src/calc.py\n@@\n-a\n+b\n"
         "*** Add File: /repo/tests/test_calc.py\n+x\n*** End Patch")


def fire(session, name, tin, resp):
    return session.fire("PostToolUse:codex", {"hook_event_name": "PostToolUse", "tool_name": name,
                                              "tool_input": tin, "tool_response": resp})


def kinds(session):
    return [(r["kind"], r.get("path"), r.get("collected"), r.get("exit_code")) for r in session.records()
            if r["kind"] in ("edit", "test_run", "other")]


def test_exec_command_with_cmd(session):
    session.prompt()
    fire(session, "exec_command", {"cmd": "pytest -q", "workdir": "/repo"}, {"output": PASS4, "exit_code": 0})
    assert kinds(session) == [("test_run", None, 4, 0)]


def test_shell_argv_list(session):
    session.prompt()
    fire(session, "shell", {"command": ["bash", "-lc", "pytest -q"]},
         {"output": "1 failed, 3 passed in 0.1s", "exit_code": 1})
    assert kinds(session) == [("test_run", None, 4, 1)]


def test_apply_patch_records_edits(session):
    session.prompt()
    fire(session, "apply_patch", {"input": PATCH}, {"output": "Success"})
    edits = [(r["path"], r["is_test"], r["code"], r.get("via")) for r in session.records() if r["kind"] == "edit"]
    assert edits == [("src/calc.py", False, True, "patch"), ("tests/test_calc.py", True, True, "patch")]


def test_code_mode_exec_then_claim(session):
    session.prompt()
    code = ("text(await tools.apply_patch(" + json.dumps("*** Begin Patch\n*** Update File: /repo/calc.py\n*** End Patch") +
            "));text(await tools.exec_command({cmd:\"python3 -m unittest\",\"max_output_tokens\":4000}));")
    out = [{"type": "input_text", "text": "Script completed"},
           {"type": "input_text", "text": "Success. Updated the following files: M calc.py"},
           {"type": "input_text", "text": json.dumps({"chunk_id": "a", "exit_code": 0, "original_token_count": 3,
                                                       "output": "Ran 4 tests in 0.01s\n\nOK", "wall_time_seconds": 0.2})}]
    fire(session, "exec", {"input": code}, out)
    assert [(k, p) for k, p, _, _ in kinds(session)] == [("edit", "calc.py"), ("test_run", None)]
    assert session.stop("Fixed. All tests pass.") is None
    assert {c["type"]: c["tier"] for c in session.verdicts()[-1]["claims"]} == {"tests_pass": "A", "fixed": "A"}


def test_code_mode_unreadable_result_counts_as_unknown_run(session):
    session.prompt()
    session.edit()
    code = "const r = await tools.exec_command({cmd:\"npm test\"}); text(r.output.slice(-200));"
    out = [{"type": "input_text", "text": "Script completed"}, {"type": "input_text", "text": "...tail of output..."}]
    fire(session, "exec", {"input": code}, out)
    session.stop("All tests pass.")
    assert session.verdicts()[-1]["claims"][0]["tier"] == "B"


def test_unknown_codex_tool_is_ignored(session):
    session.prompt()
    fire(session, "exec", {"input": "text(await tools.web__run({q: 'x'}))"},
         [{"type": "input_text", "text": "Script completed"}])
    assert kinds(session) == []


def running(proc):
    return {"type": "input_text", "text": json.dumps({"chunk_id": "a", "session_id": proc, "output": "",
                                                       "original_token_count": 0, "wall_time_seconds": 1.0})}


def exited(code, output):
    return {"type": "input_text", "text": json.dumps({"chunk_id": "b", "exit_code": code, "output": output,
                                                       "original_token_count": 9, "wall_time_seconds": 0.1})}


DONE = {"type": "input_text", "text": "Script completed"}


def test_cmd_containing_close_brace_is_read_whole(session):
    """A heredoc with JS in it holds "})": the command must not be cut there."""
    session.prompt()
    session.edit()
    cmd = "python3 - <<'PY'\nx = '(()=>{a})()'\nPY\npytest -q"
    code = "text(await tools.exec_command({cmd:" + json.dumps(cmd) + ", workdir:\"/repo\"}))"
    fire(session, "exec", {"input": code}, [DONE, exited(0, PASS4)])
    assert [k for k, *_ in kinds(session)][-1] == "test_run"


def test_run_finishing_in_a_later_poll_counts(session):
    """Codex: the test command was still running when exec returned; write_stdin later gets the result."""
    session.prompt()
    session.edit()
    fire(session, "exec", {"input": "text(await tools.exec_command({cmd:\"pytest -q\",yield_time_ms:1000}))"},
         [DONE, running(25917)])
    fire(session, "exec", {"input": "text(await tools.write_stdin({session_id:25917,chars:\"\"}))"},
         [DONE, exited(0, PASS4)])
    session.stop("All tests pass.")
    assert session.verdicts()[-1]["claims"][0]["tier"] == "A"


def test_run_finishing_with_failure_is_d(session):
    session.prompt()
    session.edit()
    fire(session, "exec", {"input": "text(await tools.exec_command({cmd:\"pytest -q\"}))"}, [DONE, running(7)])
    fire(session, "exec", {"input": "text(await tools.exec_command({cmd:\"ls\"}));"
                                    "text(await tools.write_stdin({session_id:7,chars:\"\"}))"},
         [DONE, exited(0, "a b"), exited(1, "1 failed, 3 passed in 0.1s")])
    session.stop("All tests pass.")
    assert session.verdicts()[-1]["claims"][0]["tier"] == "D"


def test_still_running_at_stop_is_b_not_d(session):
    session.prompt()
    session.edit()
    fire(session, "exec", {"input": "text(await tools.exec_command({cmd:\"pytest -q\"}))"}, [DONE, running(8)])
    session.stop("Fixed it.")
    v = session.verdicts()[-1]["claims"][0]
    assert v["tier"] == "B"


def test_edit_while_run_was_going_makes_it_stale(session):
    """The run started before the last edit, so it says nothing about that edit, even if it finished after."""
    session.prompt()
    fire(session, "exec", {"input": "text(await tools.exec_command({cmd:\"pytest -q\"}))"}, [DONE, running(9)])
    session.edit()
    fire(session, "write_stdin", {"session_id": 9, "chars": ""}, {"exit_code": 0, "output": PASS4})
    session.stop("All tests pass.")
    assert session.verdicts()[-1]["claims"][0]["tier"] == "C"
