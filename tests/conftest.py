import copy
import io
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from proof_of_green import hooks, ledger  # noqa: E402

FIXTURES = os.path.join(ROOT, "tests", "fixtures")


def load(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture
def data(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path / "data"))
    monkeypatch.delenv("CLAUDE_PLUGIN_OPTION_MODE", raising=False)
    monkeypatch.delenv("CLAUDE_PLUGIN_OPTION_TEST_COMMAND", raising=False)
    return tmp_path / "data"


class Session:
    """Drive the hook handlers the way Claude Code would, without Claude Code."""

    def __init__(self, sid="s1", cwd="/repo"):
        self.sid, self.cwd = sid, cwd

    def fire(self, name, payload):
        payload = dict(copy.deepcopy(payload), session_id=self.sid, cwd=self.cwd)
        out = io.StringIO()
        assert hooks.run(name, stdin=io.StringIO(json.dumps(payload)), stdout=out) == 0
        text = out.getvalue()
        return json.loads(text) if text else None

    def start(self):
        return self.fire("SessionStart", load("session_start.json"))

    def prompt(self, text="Fix the failing test"):
        return self.fire("UserPromptSubmit", {"hook_event_name": "UserPromptSubmit", "prompt": text})

    def edit(self, path="/repo/calc.py"):
        return self.fire("PostToolUse:edit", {"hook_event_name": "PostToolUse", "tool_name": "Edit",
                                              "tool_input": {"file_path": path}, "tool_response": {}})

    def bash(self, command, output="", exit_code=0):
        if exit_code:
            payload = {"hook_event_name": "PostToolUseFailure", "tool_name": "Bash",
                       "tool_input": {"command": command}, "error": "Exit code %d\n%s" % (exit_code, output)}
        else:
            payload = {"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": command},
                       "tool_response": {"stdout": output, "stderr": "", "interrupted": False}}
        return self.fire("PostToolUse:bash", payload)

    def stop(self, message, active=False):
        return self.fire("Stop", {"hook_event_name": "Stop", "stop_hook_active": active,
                                  "last_assistant_message": message})

    def records(self):
        return ledger.read(ledger.session_path(self.sid))

    def verdicts(self):
        return [r for r in self.records() if r["kind"] == "verdict"]


@pytest.fixture
def session(data):
    s = Session()
    s.start()
    return s
