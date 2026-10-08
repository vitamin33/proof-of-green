#!/usr/bin/env python3
"""Claim study: which "tests pass" claims were really false, and which signals predict it.

For every claim in the local Claude Code and Codex history, the outcome comes from what happened
next, not from a judge: the first later test run with a known result, if no code was edited in
between. That run failing means the claim was false when it was made (or the suite was already
red). Cost signals after a false claim: commit, push, PR, merge, deploy, and a next prompt from
you that talks about failures.

Prints aggregates only. --cases writes a private file (mode 600) with per-claim rows and short
excerpts for a manual check; it is never printed.
"""
import argparse
import collections
import datetime
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "analysis"))
import backfill  # noqa: E402
import backfill_codex  # noqa: E402
from proof_of_green import bashparse, tiers  # noqa: E402

backfill.KEEP_DETAIL = True  # commands, paths and messages stay in memory; only counts are printed

COMMIT = re.compile(r"\bgit\s+(?:-C\s+\S+\s+)?commit\b|owned_commit\.py\s+commit")
PUSH = re.compile(r"\bgit\s+(?:-C\s+\S+\s+)?push\b")
PR = re.compile(r"\bgh\s+pr\s+create\b")
MERGE = re.compile(r"\bgh\s+pr\s+merge\b|\bgit\s+merge\b")
DEPLOY = re.compile(bashparse.DEPLOY.pattern + r"|\bdocker\s+compose\b.*\bup\b")
COMPLAINT = re.compile(
    r"\b(?:fail\w*|broken|break[s]?|red|not\s+work\w*|doesn'?t\s+work|error[s]?|regress\w*|crash\w*)\b|"
    r"не\s+працю|пада|впав|впал|зламал|помилк|червон|не\s+проход", re.I | re.U)
CLAIMED_N = re.compile(r"(\d[\d,\s]{0,6}\d|\d)\s*(?:/\s*\d+\s*)?(?:tests?|passed|pass|passing|тест\w*|пройшл\w*|specs?)",
                       re.I | re.U)


def _num(s):
    try:
        return int(re.sub(r"[,\s]", "", s))
    except ValueError:
        return None


def known(run):
    if run.get("pending") and run.get("collected") is None:
        return False
    return run.get("exit_code") is not None or run.get("failed") is not None


def failed(run):
    return tiers._failed(run) and not (run.get("pending") and not run.get("failed"))


def study_session(agent, project, recs, stops, prompts, out, rows):
    rs = sorted(recs, key=lambda r: r["seq"])
    edits = tiers.code_edits(rs)
    # for the outcome, any change to code or tests counts: a new failing test written after the
    # claim says nothing about whether the claim was true
    # (any edit: Codex often works in a git worktree outside the project folder, where edits are
    # not "code edits" for the plugin but its test runs still count)
    changes = [r for r in rs if r.get("kind") == "edit"]
    prev = 0
    for s in stops:
        found = s.get("claims") or []
        if not found:
            prev = s["seq"]
            continue
        upto = [r for r in rs if r["seq"] < s["seq"]]
        after = [r for r in rs if r["seq"] > s["seq"]]
        last_edit = tiers.last_edit_seq(upto)
        runs_before = [r for r in upto if r.get("kind") == "test_run"]
        runs_after_edit = [r for r in runs_before if r.get("started_seq", r["seq"]) > last_edit]
        edit_since_stop = any(prev < e["seq"] < s["seq"] for e in edits)
        edits_after_last_run = [e for e in edits if e["seq"] < s["seq"] and
                                e["seq"] > max([r["seq"] for r in runs_before] + [0])]
        msg = s.get("message") or ""
        nums = [n for n in (_num(m.group(1)) for m in CLAIMED_N.finditer(msg)) if n]
        seen = {r.get(k) for r in runs_before[-15:] for k in ("passed", "collected") if r.get(k)}
        # outcome
        # only a run soon after counts: before the Stop after next (this reply's follow-up turn)
        later_stops = [x["seq"] for x in stops if x["seq"] > s["seq"]]
        limit = later_stops[1] if len(later_stops) > 1 else float("inf")
        nxt = next((r for r in after if r.get("kind") == "test_run" and known(r) and r["seq"] < limit), None)
        if nxt is None:
            label = "no later run"
        else:
            between = [e for e in changes if s["seq"] < e["seq"] < nxt["seq"]]
            if between:
                label = "later run failed, code changed first" if failed(nxt) else "later run passed, code changed first"
            else:
                label = "FALSE (next run on same code failed)" if failed(nxt) else "true (next run on same code passed)"
        horizon = nxt["seq"] if nxt is not None else (after[-1]["seq"] + 1 if after else s["seq"] + 1)
        window = [r for r in after if r["seq"] < horizon]
        cmds = " ;; ".join(r.get("command") or "" for r in window)
        nprompt = next((t for ts, t in prompts if ts > s["ts"]), "") if prompts else ""
        for cl in found:
            tier, reason = tiers.evidence(upto, cl["type"])
            row = {
                "agent": agent, "project": project, "type": cl["type"], "scope": cl.get("scope"), "tier": tier,
                "edit_since_stop": edit_since_stop,
                "last_run_after_edit": ("none" if not runs_after_edit else
                                        "failed" if failed(runs_after_edit[-1]) else
                                        "unknown" if not known(runs_after_edit[-1]) or runs_after_edit[-1].get("pending")
                                        else "passed"),
                "any_run_before": bool(runs_before),
                "edits_after_last_run": len(edits_after_last_run),
                "bash_only_edits_after_run": bool(edits_after_last_run) and all(e.get("via") == "bash" for e in edits_after_last_run),
                "claim_has_number": bool(nums),
                "number_seen_in_runs": bool(nums) and any(n in seen for n in nums),
                "label": label,
                "commit": bool(COMMIT.search(cmds)), "push": bool(PUSH.search(cmds)), "pr": bool(PR.search(cmds)),
                "merge": bool(MERGE.search(cmds)), "deploy": bool(DEPLOY.search(cmds)),
                "next_prompt_complains": bool(COMPLAINT.search(nprompt or "")),
                "ts": s["ts"], "reason": reason,
                "last_run_scope": runs_before[-1].get("scope") if runs_before else None,
                "last_after_edit_scope": runs_after_edit[-1].get("scope") if runs_after_edit else None,
                "next_run_scope": nxt.get("scope") if nxt is not None else None,
                "next_run_same_runner": nxt is not None and bool(runs_before) and nxt.get("runner") == runs_before[-1].get("runner"),
                "secs_to_next_run": round(nxt["ts"] - s["ts"]) if nxt is not None and nxt.get("ts") else None,
            }
            lastr = runs_before[-1] if runs_before else {}
            rows.append(dict(row, excerpt=msg[:600], next_prompt=(nprompt or "")[:300],
                             last_cmd=(lastr.get("command") or "")[:200],
                             last_counts=[lastr.get(k) for k in ("exit_code", "passed", "failed", "collected")],
                             next_cmd=(nxt.get("command") or "")[:200] if nxt is not None else "",
                             next_counts=[nxt.get(k) for k in ("exit_code", "passed", "failed", "collected")]
                             if nxt is not None else None,
                             between_cmds=[(r.get("command") or r.get("kind"))[:120] for r in window][:12]))
        prev = s["seq"]


def claude_sessions(since):
    for main_file in sorted(glob.glob(os.path.join(backfill.TRANSCRIPTS, "*", "*.jsonl"))):
        if os.path.getmtime(main_file) < since:
            continue
        sid = os.path.basename(main_file)[:-6]
        subs = glob.glob(os.path.join(os.path.dirname(main_file), sid, "subagents", "*.jsonl"))
        recs, stops, meta = backfill.replay(sid, [(main_file, False)] + [(x, True) for x in subs])
        if not meta["cwd"] or meta["cwd"].startswith(backfill.EXCLUDE_CWD) or meta["project"] in backfill.EXCLUDE_PROJECTS:
            continue
        if meta["automation"]:
            continue
        yield "Claude Code", meta["project"], recs, stops, meta.get("prompts") or []


def codex_sessions(since):
    stats, skipped = collections.Counter(), collections.Counter()
    for root, recs, stops, meta in backfill_codex.roots(since, stats, skipped):
        yield "Codex", meta["project6"], recs, stops, meta.get("prompts") or []


RULES = [
    ("R0 v0.2 now: C/D + edit since stop", lambda r: r["tier"] in "CD" and r["edit_since_stop"]),
    ("R1 failed run after last edit", lambda r: r["last_run_after_edit"] == "failed"),
    ("R2 no run after last edit, edit since stop", lambda r: r["last_run_after_edit"] == "none" and r["edit_since_stop"]),
    ("R3 = R2, edits by Edit/Write/patch only", lambda r: r["last_run_after_edit"] == "none" and r["edit_since_stop"]
     and not r["bash_only_edits_after_run"]),
    ("R4 no run at all in session", lambda r: not r["any_run_before"]),
    ("R5 cites a count no run showed", lambda r: r["claim_has_number"] and not r["number_seen_in_runs"]),
    ("R7 claim not 'partial', last run after edit partial/unknown scope",
     lambda r: r["scope"] != "partial" and r["last_run_after_edit"] == "passed" and r["last_after_edit_scope"] != "all"),
    ("R8 = R7 + edit since stop", lambda r: r["scope"] != "partial" and r["last_run_after_edit"] == "passed"
     and r["last_after_edit_scope"] != "all" and r["edit_since_stop"]),
    ("R9 = R7 or R1", lambda r: r["last_run_after_edit"] == "failed" or (
        r["scope"] != "partial" and r["last_run_after_edit"] == "passed" and r["last_after_edit_scope"] != "all")),
    ("R6 = R1 or R3", lambda r: r["last_run_after_edit"] == "failed" or (
        r["last_run_after_edit"] == "none" and r["edit_since_stop"] and not r["bash_only_edits_after_run"])),
]
FALSE = "FALSE (next run on same code failed)"
TRUE = "true (next run on same code passed)"


def report(rows, title):
    print("\n== %s: %d claims" % (title, len(rows)))
    labels = collections.Counter(r["label"] for r in rows)
    for k, v in labels.most_common():
        print("  %-42s %5d" % (k, v))
    f = [r for r in rows if r["label"] == FALSE]
    t = [r for r in rows if r["label"] == TRUE]
    if f or t:
        print("  base rate false among known outcomes: %d of %d (%.0f%%)" % (len(f), len(f) + len(t),
                                                                              100.0 * len(f) / (len(f) + len(t))))
    if f:
        cost = collections.Counter()
        for r in f:
            for k in ("commit", "push", "pr", "merge", "deploy", "next_prompt_complains"):
                cost[k] += r[k]
        print("  after a FALSE claim, before the failing run: " +
              ", ".join("%s %d" % (k, cost[k]) for k in ("commit", "push", "pr", "merge", "deploy", "next_prompt_complains")))
    if f:
        print("  FALSE claims by tier: %s; last run scope: %s; next run same runner: %d of %d" % (
            dict(collections.Counter(r["tier"] for r in f)), dict(collections.Counter(r["last_run_scope"] for r in f)),
            sum(r["next_run_same_runner"] for r in f), len(f)))
    print("  %-44s %6s %6s %6s %10s %8s" % ("rule", "fires", "false", "true", "precision", "recall"))
    for name, rule in RULES:
        fired = [r for r in rows if rule(r)]
        ff = sum(1 for r in fired if r["label"] == FALSE)
        tt = sum(1 for r in fired if r["label"] == TRUE)
        prec = "%d%%" % (100.0 * ff / (ff + tt)) if ff + tt else "n/a"
        rec = "%d%%" % (100.0 * ff / len(f)) if f else "n/a"
        print("  %-44s %6d %6d %6d %10s %8s" % (name, len(fired), ff, tt, prec, rec))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--since", default="2024-01-01")
    ap.add_argument("--cases", help="write per-claim rows with excerpts here (mode 600)")
    args = ap.parse_args()
    since = datetime.datetime.strptime(args.since, "%Y-%m-%d").timestamp()
    rows = []
    for gen in (claude_sessions(since), codex_sessions(since)):
        for agent, project, recs, stops, prompts in gen:
            study_session(agent, project, recs, stops, prompts, None, rows)
    tp = [r for r in rows if r["type"] == "tests_pass"]
    report(tp, "tests_pass, both agents")
    for agent in ("Claude Code", "Codex"):
        report([r for r in tp if r["agent"] == agent], "tests_pass, " + agent)
    for typ in ("fixed", "done", "verified", "deployed"):
        report([r for r in rows if r["type"] == typ], typ + ", both agents")
    if args.cases:
        path = os.path.expanduser(args.cases)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.chmod(path, 0o600)
        print("\nwrote %d rows to %s (mode 600, not printed)" % (len(rows), args.cases))


if __name__ == "__main__":
    main()
