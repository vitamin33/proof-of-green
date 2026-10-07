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


OUTSIDE = "(outside project)"


def classify(path, project):
    """Return (path relative to the project, is_test, is_code); OUTSIDE for files elsewhere.

    `project` is the hash of the folder the session started in. A file is inside when one of
    its parent folders hashes to it, so no absolute path is ever stored. Edits outside that
    folder (scratch files, memory, plans) and docs are not code edits.
    """
    inside = True
    if project and os.path.isabs(path):
        real = os.path.realpath(path)
        inside = False
        parent = os.path.dirname(real)
        while True:
            if ledger.project_hash(parent) == project:
                path, inside = os.path.relpath(real, parent), True
                break
            up = os.path.dirname(parent)
            if up == parent:
                break
            parent = up
        if not inside:
            return OUTSIDE, False, False
    return path, is_test_path(path), inside and not DOC_PATH.search(path)


def _git_head(cwd):
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd or None, capture_output=True,
                             text=True, timeout=1)
        return out.stdout.strip()[:40] or None if out.returncode == 0 else None
    except Exception:
        return None


def _session_project(sid, payload):
    rec = ledger.first_session(ledger.session_path(sid))
    if rec:
        return rec.get("project") or ledger.project_hash(rec["cwd"])  # "cwd": ledgers before 0.1.0
    return ledger.project_hash(payload.get("cwd")) if payload.get("cwd") else None


def _agent(p, rec):
    if isinstance(p.get("agent_id"), str) and p["agent_id"]:
        rec["agent_id"] = p["agent_id"]
    return rec


def on_session_start(p):
    model = p.get("model")
    if isinstance(model, dict):
        model = model.get("id") or model.get("display_name")
    ledger.append(p.get("session_id"), {
        "kind": "session", "session_id": p.get("session_id"),
        "project": ledger.project_hash(p.get("cwd")) if p.get("cwd") else None,
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
    path, is_test, code = classify(path, _session_project(sid, p))
    ledger.append(sid, _agent(p, {"kind": "edit", "path": path, "is_test": is_test, "code": code}))


def _bash_edits(p, command, project):
    """Edit records for files the command writes (D6). Same rules as Edit/Write: inside the
    project, not a test, not a doc counts as code."""
    writes, patch, first = bashparse.write_targets(command)
    cwd = p.get("cwd") if isinstance(p.get("cwd"), str) else ""
    edits = []
    for path, cd in writes:
        full = os.path.expanduser(path)
        if not os.path.isabs(full):
            full = os.path.normpath(os.path.join(cwd, os.path.expanduser(cd), full))
        rel, is_test, code = classify(full, project)
        edits.append(_agent(p, {"kind": "edit", "via": "bash", "path": rel, "is_test": is_test, "code": code}))
    if patch:
        edits.append(_agent(p, {"kind": "edit", "via": "bash", "path": "(patch)", "is_test": False, "code": True}))
    return edits, first


def on_bash(p):
    test_command = os.environ.get("CLAUDE_PLUGIN_OPTION_TEST_COMMAND")
    rec = _agent(p, bashparse.parse_bash(p, test_command))
    rec["event"] = p.get("hook_event_name") or "PostToolUse"
    sid = p.get("session_id")
    tin = p.get("tool_input") if isinstance(p.get("tool_input"), dict) else {}
    command = tin.get("command") if isinstance(tin.get("command"), str) else ""
    edits, first = _bash_edits(p, command, _session_project(sid, p)) if command else ([], None)
    order = edits + [rec]
    if edits and rec["kind"] == "test_run":
        _, seg = bashparse.detect_runner(command, test_command)
        run_at = command.find(seg) if seg else -1
        if 0 <= run_at < (first or 0):  # "npm test && sed -i ...": the run came before the write
            order = [rec] + edits
    for r in order:
        ledger.append(sid, r)


def on_stop(p):
    sid = p.get("session_id")
    message = p.get("last_assistant_message")
    found = claims.extract(message) if isinstance(message, str) else []
    if not found:
        # Data only: marks where each Stop fell, so DECISIONS.md D1 can be scored after the observe week.
        ledger.append(sid, {"kind": "stop", "has_message": isinstance(message, str) and bool(message.strip())})
        return None
    records = ledger.read(ledger.session_path(sid))
    graded = []
    for c in found:
        tier, reason = tiers.evidence(records, c["type"])
        graded.append(dict(c, tier=tier, reason=reason))
    m = mode()
    # D1 (v0.2): a code edit since the previous Stop, so work that finished in a background
    # subagent and came back as a new prompt still counts.
    prev_stop = max([r["seq"] for r in records if r.get("kind") in ("stop", "verdict")] + [0])
    edited_since_stop = any(r["seq"] > prev_stop for r in tiers.code_edits(records))
    act = (m == "warn" and not p.get("stop_hook_active") and edited_since_stop
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
