#!/usr/bin/env python3
"""Build a local review file of would-warn cases, so a human can judge whether each warning is fair.

Picks about 24 cases where v0.2 in warn mode would have spoken, spread over agents and claim
types. For each it writes the agent's final reply, what changed since the previous Stop and
the test runs. The file holds client code and text: it is written with mode 600, is meant for
you to read, and this script prints counts only. Score it with analysis/score_review.py.
"""
import argparse
import collections
import datetime
import glob
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "analysis"))
import backfill  # noqa: E402
import backfill_codex  # noqa: E402
from proof_of_green import tiers  # noqa: E402

backfill.KEEP_DETAIL = True
PER_TYPE = {"Claude Code": 3, "Codex": 3}


def would_warn_cases(agent, project_name, sid, recs, stops):
    rs = recs  # v0.2 rule: shell edits included
    edits = tiers.code_edits(rs)
    prev = 0
    for s in stops:
        if not s["claims"]:
            prev = s["seq"]
            continue
        upto = [r for r in rs if r["seq"] < s["seq"]]
        graded = []
        for cl in s["claims"]:
            tier, reason = tiers.evidence(upto, cl["type"])
            graded.append(dict(cl, tier=tier, reason=reason))
        warn = tiers.warning(graded)
        if warn and any(prev < e["seq"] < s["seq"] for e in edits):
            window = [r for r in rs if prev < r["seq"] < s["seq"]]
            before = [r for r in rs if r["seq"] <= prev and r.get("kind") == "test_run"]
            yield {"agent": agent, "project": project_name, "session": sid, "ts": s["ts"], "graded": graded,
                   "warning": warn[0], "message": s.get("message") or "", "window": window,
                   "run_before": before[-1] if before else None}
        prev = s["seq"]


def describe(r):
    if r["kind"] == "edit":
        return "edit   %s (%s%s)" % (r.get("path") or "?", r.get("via"), ", test file" if r.get("is_test") else
                                     ("" if r.get("code") else ", not code"))
    if r["kind"] == "test_run":
        return "tests  %s -> exit %s, passed %s, failed %s, collected %s%s" % (
            (r.get("command") or "?")[:140], r.get("exit_code"), r.get("passed"), r.get("failed"), r.get("collected"),
            ", exit code masked by pipe" if r.get("exit_masked") else "")
    return "shell  %s -> exit %s" % ((r.get("command") or "?")[:140], r.get("exit_code"))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--since", default="2026-09-15")
    ap.add_argument("--out", default="~/research/pog-data/review/warnings-sample.md")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    since = datetime.datetime.strptime(args.since, "%Y-%m-%d").timestamp()
    cases = []
    for main_file in glob.glob(os.path.join(backfill.TRANSCRIPTS, "*", "*.jsonl")):
        if os.path.getmtime(main_file) < since:
            continue
        sid = os.path.basename(main_file)[:-6]
        subs = glob.glob(os.path.join(os.path.dirname(main_file), sid, "subagents", "*.jsonl"))
        recs, stops, meta = backfill.replay(sid, [(main_file, False)] + [(x, True) for x in subs])
        if not meta["cwd"] or meta["cwd"].startswith(backfill.EXCLUDE_CWD) or meta["automation"] \
                or meta["project"] in backfill.EXCLUDE_PROJECTS:
            continue
        cases += [c for c in would_warn_cases("Claude Code", os.path.basename(meta["cwd"]), sid, recs, stops)
                  if c["ts"] >= since]
    for root, recs, stops, meta in backfill_codex.roots(since, collections.Counter(), collections.Counter()):
        cases += list(would_warn_cases("Codex", os.path.basename(meta.get("cwd") or "?"), root, recs, stops))
    random.seed(args.seed)
    random.shuffle(cases)
    picked, taken = [], collections.Counter()
    for c in cases:
        worst = sorted((g for g in c["graded"] if g["tier"] in "CD"), key=lambda g: g["tier"] != "D")[0]["type"]
        if taken[(c["agent"], worst)] < PER_TYPE[c["agent"]]:
            taken[(c["agent"], worst)] += 1
            c["worst"] = worst
            picked.append(c)
    picked.sort(key=lambda c: (c["agent"], c["ts"]))
    out = os.path.expanduser(args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write("# proof-of-green v0.2: would-warn cases to judge\n\n")
        fh.write("For each case decide: would the one-line warning have been FAIR (the claim really had no proof "
                 "after the last code change), UNFAIR (the proof was there, or the claim was not about this "
                 "change), or UNSURE. Replace `?` after VERDICT with fair, unfair or unsure. Add a NOTE if useful.\n\n")
        for n, c in enumerate(picked, 1):
            when = datetime.datetime.fromtimestamp(c["ts"]).strftime("%Y-%m-%d %H:%M")
            fh.write("---\n\n## W%02d  %s · %s · %s · session %s\n\n" % (n, c["agent"], c["project"], when, c["session"][:8]))
            fh.write("Claims: %s\n\n" % ", ".join("%s (tier %s)" % (g["type"], g["tier"]) for g in c["graded"]))
            fh.write("Warning that would show: `%s`\n\n" % c["warning"])
            fh.write("Final reply (first 800 chars):\n\n```\n%s\n```\n\n" % c["message"][:800])
            fh.write("Since the previous Stop:\n\n```\n%s\n```\n\n" % ("\n".join(describe(r) for r in c["window"][-15:]) or "(nothing)"))
            fh.write("Last test run before that: %s\n\n" % (describe(c["run_before"]) if c["run_before"] else "none"))
            fh.write("VERDICT: ?\nNOTE:\n\n")
    print("would-warn cases found: %d (Claude Code %d, Codex %d)" % (
        len(cases), sum(c["agent"] == "Claude Code" for c in cases), sum(c["agent"] == "Codex" for c in cases)))
    print("picked for review: %d  %s" % (len(picked), dict(collections.Counter((c["agent"], c["worst"]) for c in picked))))
    print("wrote %s (mode 600). This script does not print its content." % args.out)


if __name__ == "__main__":
    main()
