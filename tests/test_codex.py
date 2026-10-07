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
