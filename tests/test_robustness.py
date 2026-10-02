"""Edge cases for the one-week observe run: git commands, worktrees, outside-cwd writes, concurrent writers."""
import json
import os
from multiprocessing import Pool

from proof_of_green import ledger

PASS_ALL = "Ran 4 tests in 0.01s\n\nOK"
GIT_COMMANDS = ["git stash", "git stash pop", "git checkout main -- calc.py", "git checkout -b fix/add",
                "git worktree add ../wt feature", "git worktree remove ../wt", "git restore calc.py"]


def _code_edits(session):
    return [r for r in session.records() if r["kind"] == "edit" and r["code"] and not r["is_test"]]


def test_git_and_worktree_commands_are_not_edits(session):
    session.prompt()
    for cmd in GIT_COMMANDS:
        session.bash(cmd)
    assert _code_edits(session) == []
    assert {r["kind"] for r in session.records() if r.get("command") in GIT_COMMANDS} == {"other"}
    assert session.stop("Done. All tests pass.") is None
    assert session.verdicts()[-1]["acted"] is False


def test_git_commands_after_a_full_run_keep_tier_a(session):
    session.prompt()
    session.edit()
    session.bash("python3 -m unittest", PASS_ALL)
    for cmd in GIT_COMMANDS:
        session.bash(cmd)
    assert session.stop("All tests pass.") is None
    assert session.verdicts()[-1]["claims"][0]["tier"] == "A"


def test_write_outside_cwd_is_not_a_code_edit(session):
    session.prompt()
    for path in ("/tmp/scratch/fix.py", "/Users/someone/.claude/plans/plan.md", "/repo-other/calc.py",
                 "/repo/../elsewhere/calc.py"):
        session.edit(path)
    assert _code_edits(session) == []
    assert session.stop("Fixed. All tests pass.") is None


def _append_big(args):
    base, writer, n = args
    os.environ["CLAUDE_PLUGIN_DATA"] = base
    for i in range(n):
        ledger.append("torn", {"kind": "other", "writer": writer, "i": i, "pad": "x" * 20000})


def test_two_writers_never_tear_a_line(data):
    # 20 KB records, far above PIPE_BUF. Measured 2026-10-02 on macOS with the lock switched off:
    # 0 torn lines (O_APPEND kept each write whole) but only 261 unique seq of 300.
    # The flock is what keeps seq unique; this test checks both.
    with Pool(2) as pool:
        pool.map(_append_big, [(str(data), w, 150) for w in ("parent", "subagent")])
    with open(ledger.session_path("torn"), encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    assert lines[-1] == ""
    recs = [json.loads(line) for line in lines[:-1]]  # raises on any torn line
    assert len(recs) == 300
    assert sorted(r["seq"] for r in recs) == list(range(1, 301))
    assert all(len(r["pad"]) == 20000 for r in recs)


def test_tail_read_matches_full_read(data):
    for i in range(30):
        ledger.append("tail", {"kind": "turn"} if i % 7 == 0 else {"kind": "other", "pad": "y" * (i * 900)},
                      new_turn=(i % 7 == 0))
    recs = ledger.read(ledger.session_path("tail"))
    assert [r["seq"] for r in recs] == list(range(1, 31))
    assert recs[-1]["turn"] == ledger.current_turn(recs) == 5
    assert max(len(json.dumps(r)) for r in recs) > 4096  # last-line read had to grow past one block


def test_damaged_last_line_falls_back_to_full_read(data):
    ledger.append("dmg", {"kind": "turn"}, new_turn=True)
    ledger.append("dmg", {"kind": "other"})
    with open(ledger.session_path("dmg"), "a", encoding="utf-8") as fh:
        fh.write('{"seq": 99, "kind": "oth')  # torn write from a crashed process, no newline
    rec = ledger.append("dmg", {"kind": "other"})
    assert (rec["seq"], rec["turn"]) == (3, 1)
    assert [r["seq"] for r in ledger.read(ledger.session_path("dmg"))] == [1, 2, 3]


def test_edit_uses_first_session_cwd(data):
    from conftest import Session
    s = Session(sid="cwd", cwd="/repo")
    s.start()
    s.cwd = "/repo/.claude/worktrees/wt"  # later payloads report another cwd
    s.edit("/repo/calc.py")
    assert s.records()[-1]["path"] == "calc.py" and s.records()[-1]["code"] is True


def test_background_subagent_case_can_be_scored_under_both_rules(session):
    """Event order from the 2026-10-02 probe (session a8a4577f): parent stops before the subagent edits,
    the result arrives as a new prompt, then the parent claims. Current rule stays silent (D1)."""
    session.prompt("Use a subagent to fix calc.py")
    assert session.stop("I've launched a subagent to make the change.") is None   # Stop 1, no claim
    session.fire("PostToolUse:edit", {"hook_event_name": "PostToolUse", "tool_name": "Edit",
                                      "agent_id": "a30aca86184812420", "tool_input": {"file_path": "/repo/calc.py"}})
    session.prompt("x" * 906)                                                       # subagent result
    assert session.stop("Done. All tests pass.") is None                            # Stop 2
    recs = session.records()
    verdict = recs[-1]
    assert verdict["kind"] == "verdict" and verdict["acted"] is False
    assert {c["tier"] for c in verdict["claims"]} == {"D"}
    # rule "code edit in this turn" (current): no edit in the verdict's turn
    assert not any(r["kind"] == "edit" and r["turn"] == verdict["turn"] for r in recs)
    # rule "code edit since the previous Stop" (D1 option 2): computable from the stop marker
    prev_stop = max(r["seq"] for r in recs if r["kind"] in ("stop", "verdict") and r["seq"] < verdict["seq"])
    assert any(r["kind"] == "edit" and r["code"] and prev_stop < r["seq"] < verdict["seq"] for r in recs)
