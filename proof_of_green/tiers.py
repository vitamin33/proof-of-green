"""Evidence tiers for a claim, computed from the session ledger.

A  full-scope test run after the last code edit: exit 0, collected > 0, clean flags
B  partial/unknown-scope run after the last code edit, passing
C  only runs from before the last code edit (stale)
D  no run, last run after the edit failed, 0 collected, or suspicious flags
"""

LABELS = {"tests_pass": "tests pass", "done": "done", "fixed": "fixed",
          "verified": "verified", "deployed": "deployed"}


def code_edits(records):
    return [r for r in records if r.get("kind") == "edit" and r.get("code", True) and not r.get("is_test")]


def last_edit_seq(records):
    edits = code_edits(records)
    return max(r["seq"] for r in edits) if edits else 0


def _failed(run):
    if run.get("exit_masked"):
        # piped without pipefail: the exit code is not the tests'; only the counts can say "failed"
        return (run.get("failed") or 0) > 0
    code = run.get("exit_code")
    return code is None or code != 0 or (run.get("failed") or 0) > 0


def _counts(run):
    if run.get("failed"):
        return "%s failed" % run["failed"]
    if run.get("exit_code") not in (0, None):
        return "exit %s" % run["exit_code"]
    if run.get("collected") == 0:
        return "0 tests collected"
    return "passed"


def evidence(records, claim_type):
    """Return (tier, reason). `reason` is short and human-readable."""
    edit = last_edit_seq(records)
    if claim_type == "deployed":
        runs = [r for r in records if r.get("kind") == "other" and r.get("deploy")]
        noun = "deploy command"
    else:
        runs = [r for r in records if r.get("kind") == "test_run"]
        noun = "test run"
    after = [r for r in runs if r["seq"] > edit]
    before = [r for r in runs if r["seq"] <= edit]
    if not after:
        if before:
            return "C", "no %s after your last edit (last run: before edit, %s)" % (noun, _counts(before[-1]))
        return "D", "no %s in this session" % noun
    last = after[-1]
    if claim_type == "deployed":
        return ("D", "last deploy command failed (%s)" % _counts(last)) if _failed(last) else ("A", "deployed after edit")
    if last.get("flags"):
        return "D", "last test run used %s" % ", ".join(last["flags"])
    if _failed(last):
        return "D", "last test run after your edit failed (%s)" % _counts(last)
    good = [r for r in after if not r.get("flags") and not _failed(r) and r.get("collected") != 0]
    if not good:
        return "D", "last test run collected 0 tests"
    if all(r.get("exit_masked") and r.get("collected") is None for r in good):
        return "B", "test result not visible: exit code masked by a pipe (| tail, | grep) and no counts in the output"
    if any(r.get("scope") == "all" and (r.get("collected") or 0) > 0 for r in good):
        return "A", "full test run passed after edit"
    return "B", "only a partial test run after your edit"


def satisfied(claim, tier):
    if tier == "A":
        return True
    if tier == "B":
        return claim["type"] != "tests_pass" or claim.get("scope") == "partial"
    return False


def warning(claims_with_tiers):
    """Pick the worst unsupported claim; return (systemMessage, additionalContext) or None."""
    bad = [c for c in claims_with_tiers if c["tier"] in ("C", "D")]
    if not bad:
        return None
    worst = sorted(bad, key=lambda c: (c["tier"] != "D", c["type"] != "tests_pass"))[0]
    msg = "proof-of-green: claim '%s' — %s" % (LABELS[worst["type"]], worst["reason"])
    partial = [c for c in claims_with_tiers if c["type"] == "tests_pass" and c["tier"] == "B"]
    if partial and partial[0] is not worst:
        msg += "; 'tests pass' has partial evidence only"
    if worst["type"] == "deployed":
        ctx = ("proof-of-green: before concluding, show the deploy command you ran after the last edit "
               "and its result (exit status and the deployed URL or version).")
    else:
        ctx = ("proof-of-green: before concluding, run the project's full test command after your last edit "
               "and report the exact result (command, passed and failed counts).")
    return msg, ctx
