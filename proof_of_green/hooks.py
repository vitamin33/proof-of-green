"""Hook handlers. Each takes the parsed stdin payload and returns a dict to print, or None.

`run()` is the only entry point: it reads stdin once and fails open on anything.
"""
import json
import os
import re
import subprocess
import sys

from . import bashparse, claims, ledger, tiers

TEST_PATH = re.compile(
    r"(?:^|/)(?:tests?|__tests__|spec|Tests)/|(?:^|/)test_[^/]*\.py$|_test\.(?:py|go|dart)$|"
    r"\.(?:spec|test)\.(?:[cm]?[jt]sx?)$|(?:^|/)conftest\.py$|_spec\.rb$|Tests?\.(?:java|kt|swift|cs)$")
DOC_PATH = re.compile(r"\.(?:md|mdx|rst|txt|adoc)$|(?:^|/)(?:LICENSE|CHANGELOG|NOTICE)[^/]*$", re.I)
CODEISH = re.compile(
    r"\b(?:tests?|bug|fix|error|exception|function|class|method|refactor|implement|build|compile|deploy|"
    r"api|endpoint|code|script|lint|merge|commit|stack\s*trace|module|package|import|crash)\b|"
    r"(?:тест|баг|помилк|виправ|функці|клас|рефактор|реаліз|деплой|код|скрипт|білд)|`|\w\.(?:py|ts|js|go|rs|dart|swift|kt|rb|php)\b",
    re.I | re.U)


def mode():
    """observe unless the user picked warn; an unset or unknown value never speaks."""
    return "warn" if os.environ.get("CLAUDE_PLUGIN_OPTION_MODE", "").strip().lower() == "warn" else "observe"


def is_test_path(path):
    return bool(TEST_PATH.search((path or "").replace("\\", "/")))


def classify(path, cwd):
    """Return (path relative to the project when inside it, is_test, is_code).

    Edits outside the session's cwd (scratch files, memory, plans) and docs are not code edits.
    """
    inside = True
    if cwd and os.path.isabs(path):
        root = os.path.realpath(cwd)
        real = os.path.realpath(path)
        inside = real.startswith(root.rstrip(os.sep) + os.sep)
        if inside:
            path = os.path.relpath(real, root)
    return path, is_test_path(path), inside and not DOC_PATH.search(path)


def _git_head(cwd):
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd or None, capture_output=True,
                             text=True, timeout=1)
        return out.stdout.strip()[:40] or None if out.returncode == 0 else None
    except Exception:
        return None


def _session_cwd(sid, payload):
    rec = ledger.first_session(ledger.session_path(sid))
    return rec["cwd"] if rec else payload.get("cwd")


def on_session_start(p):
    model = p.get("model")
    if isinstance(model, dict):
        model = model.get("id") or model.get("display_name")
    ledger.append(p.get("session_id"), {
        "kind": "session", "session_id": p.get("session_id"), "cwd": p.get("cwd"),
        "git_head": _git_head(p.get("cwd")), "model": model, "source": p.get("source")})


def on_user_prompt(p):
    prompt = p.get("prompt") if isinstance(p.get("prompt"), str) else ""
    ledger.append(p.get("session_id"), {"kind": "turn", "prompt_len": len(prompt),
                                        "coding": bool(CODEISH.search(prompt))}, new_turn=True)


def on_edit(p):
    tin = p.get("tool_input") or {}
    path = tin.get("file_path") or tin.get("path") or ""
    if not isinstance(path, str) or not path:
        return
    sid = p.get("session_id")
    path, is_test, code = classify(path, _session_cwd(sid, p))
    ledger.append(sid, {"kind": "edit", "path": path, "is_test": is_test, "code": code})


def on_bash(p):
    rec = bashparse.parse_bash(p, os.environ.get("CLAUDE_PLUGIN_OPTION_TEST_COMMAND"))
    rec["event"] = p.get("hook_event_name") or "PostToolUse"
    ledger.append(p.get("session_id"), rec)


def on_stop(p):
    message = p.get("last_assistant_message")
    if not isinstance(message, str) or not message.strip():
        return None
    sid = p.get("session_id")
    records = ledger.read(ledger.session_path(sid))
    found = claims.extract(message)
    if not found:
        return None
    turn = ledger.current_turn(records)
    graded = []
    for c in found:
        tier, reason = tiers.evidence(records, c["type"])
        graded.append(dict(c, tier=tier, reason=reason))
    m = mode()
    edited_this_turn = any(r.get("turn") == turn for r in tiers.code_edits(records))
    act = (m == "warn" and not p.get("stop_hook_active") and edited_this_turn
           and tiers.warning(graded) is not None)
    ledger.append(sid, {"kind": "verdict", "mode": m, "acted": act,
                        "claims": [{"type": c["type"], "scope": c["scope"], "tier": c["tier"]} for c in graded]})
    if not act:
        return None
    msg, ctx = tiers.warning(graded)
    return {"systemMessage": msg,
            "hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": ctx}}


HANDLERS = {"SessionStart": on_session_start, "UserPromptSubmit": on_user_prompt,
            "PostToolUse:edit": on_edit, "PostToolUse:bash": on_bash, "Stop": on_stop}


def run(name, stdin=None, stdout=None):
    """Read stdin once, dispatch, print JSON only when there is something to say. Always exit 0."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    try:
        payload = json.loads(stdin.read() or "{}")
        if not isinstance(payload, dict):
            raise ValueError("payload is not an object")
        out = HANDLERS[name](payload)
        if out:
            stdout.write(json.dumps(out, ensure_ascii=False))
            stdout.flush()
    except Exception as exc:  # fail open
        ledger.log_error(name, exc)
    return 0
