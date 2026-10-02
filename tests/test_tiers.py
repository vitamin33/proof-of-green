"""Six scripted sessions, one per tier outcome, driven through the real hook handlers."""
from proof_of_green import tiers

PASS_ALL = "Ran 4 tests in 0.01s\n\nOK"
FAIL = "Ran 4 tests in 0.01s\n\nFAILED (failures=1)"
CLAIM = "Fixed the add bug. All tests pass."


def claim_tiers(session):
    return {c["type"]: c["tier"] for c in session.verdicts()[-1]["claims"]}


def test_tier_a_full_run_after_edit_is_silent(session):
    session.prompt()
    session.bash("python3 -m unittest", FAIL, exit_code=1)
    session.edit()
    session.bash("python3 -m unittest", PASS_ALL)
    assert session.stop(CLAIM) is None
    assert claim_tiers(session) == {"tests_pass": "A", "fixed": "A"}


def test_tier_b_partial_run_after_edit(session):
    session.prompt()
    session.edit()
    session.bash("pytest tests/test_calc.py", "==== 3 passed in 0.02s ====")
    assert session.stop(CLAIM) is None  # B never warns
    assert claim_tiers(session) == {"tests_pass": "B", "fixed": "B"}
    assert tiers.satisfied({"type": "fixed"}, "B")
    assert not tiers.satisfied({"type": "tests_pass", "scope": "all"}, "B")


def test_tier_c_stale_run_warns(session):
    session.prompt()
    session.bash("python3 -m unittest", FAIL, exit_code=1)
    session.edit()
    out = session.stop(CLAIM)
    assert claim_tiers(session) == {"tests_pass": "C", "fixed": "C"}
    assert out["systemMessage"] == ("proof-of-green: claim 'tests pass' — no test run after your last edit "
                                    "(last run: before edit, 1 failed)")
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "run the project's full test command" in ctx and "decision" not in out
    assert session.verdicts()[-1]["acted"] is True


def test_tier_d_failed_run_after_edit(session):
    session.prompt()
    session.edit()
    session.bash("python3 -m unittest", FAIL, exit_code=1)
    out = session.stop(CLAIM)
    assert claim_tiers(session)["tests_pass"] == "D"
    assert "failed (1 failed)" in out["systemMessage"]


def test_tier_d_no_run(session):
    session.prompt()
    session.edit()
    out = session.stop("Done. The endpoint is implemented.")
    assert claim_tiers(session) == {"done": "D"}
    assert out["systemMessage"] == "proof-of-green: claim 'done' — no test run in this session"


def test_zero_edits_never_warns(session):
    session.prompt("What does this repo do?")
    out = session.stop("All tests pass.")
    assert out is None
    assert session.verdicts()[-1]["acted"] is False


def test_suspicious_flag_is_d(session):
    session.prompt()
    session.edit()
    session.bash("pytest || true", "==== 1 failed, 3 passed in 0.02s ====")
    out = session.stop("All tests pass.")
    assert claim_tiers(session)["tests_pass"] == "D"
    assert "|| true" in out["systemMessage"]


def test_zero_collected_is_d(session):
    session.prompt()
    session.edit()
    session.bash("pytest", "==== no tests ran in 0.01s ====")
    assert claim_tiers_after(session, "All tests pass.") == "D"


def claim_tiers_after(session, message):
    session.stop(message)
    return claim_tiers(session)["tests_pass"]


def test_test_file_edits_do_not_make_runs_stale(session):
    session.prompt()
    session.edit()
    session.bash("python3 -m unittest", PASS_ALL)
    session.edit("/repo/tests/test_calc.py")
    session.edit("/repo/README.md")
    session.edit("/tmp/scratch/notes.py")
    assert session.stop(CLAIM) is None
    assert claim_tiers(session)["tests_pass"] == "A"


def test_no_edit_this_turn_means_silence(session):
    session.prompt()
    session.edit()
    session.stop("I changed calc.py.")
    session.prompt("are you done?")
    assert session.stop("Yes, done. All tests pass.") is None
    assert session.verdicts()[-1]["acted"] is False


def test_stop_hook_active_records_but_stays_silent(session):
    session.prompt()
    session.edit()
    assert session.stop(CLAIM, active=True) is None
    assert session.verdicts()[-1]["acted"] is False


def test_observe_mode_never_speaks(session, monkeypatch):
    monkeypatch.setenv("CLAUDE_PLUGIN_OPTION_MODE", "observe")
    session.prompt()
    session.edit()
    assert session.stop(CLAIM) is None
    assert session.verdicts()[-1]["mode"] == "observe"


def test_no_claim_records_nothing(session):
    session.prompt()
    session.edit()
    assert session.stop("I changed `add` to use +. Want me to run the tests?") is None
    assert session.verdicts() == []


def test_deploy_claim_uses_deploy_commands(session):
    session.prompt()
    session.edit()
    session.bash("vercel deploy --prod", "https://app.vercel.app")
    session.bash("python3 -m unittest", PASS_ALL)
    assert session.stop("Deployed to production.") is None
    assert claim_tiers(session) == {"deployed": "A"}


def test_custom_test_command_counts_as_full(session, monkeypatch):
    monkeypatch.setenv("CLAUDE_PLUGIN_OPTION_TEST_COMMAND", "make ci")
    session.prompt()
    session.edit()
    session.bash("make ci", "Ran 4 tests in 0.01s\n\nOK")
    session.stop("All tests pass.")
    assert claim_tiers(session)["tests_pass"] == "A"


def test_default_mode_is_observe(session, monkeypatch):
    for value in (None, "", "bogus"):
        if value is None:
            monkeypatch.delenv("CLAUDE_PLUGIN_OPTION_MODE", raising=False)
        else:
            monkeypatch.setenv("CLAUDE_PLUGIN_OPTION_MODE", value)
        session.prompt()
        session.edit()
        assert session.stop(CLAIM) is None
        assert session.verdicts()[-1]["mode"] == "observe"


def test_manifest_default_is_observe():
    import json
    import os
    from conftest import ROOT
    with open(os.path.join(ROOT, ".claude-plugin", "plugin.json")) as fh:
        assert json.load(fh)["userConfig"]["mode"]["default"] == "observe"
