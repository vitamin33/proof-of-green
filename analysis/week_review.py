#!/usr/bin/env python3
"""Observe-week numbers for docs/REVIEW-week1.md, from the ledger copies in ~/research/pog-data.

Reads ~/research/pog-data/sessions/{claude-terminal,claude-desktop,codex}/*.jsonl, keeps records
from 2026-10-04 on, drops the plugin's own repo and test fixtures, and splits sessions by type:
  autonomous   Claude Code sessions started by the SDK (entrypoint sdk-cli) or `codex exec` runs
  client       the two client projects
  personal     everything else (own products, own harness, own site)
The type of a project comes from TYPES below (hashes only). Claude entrypoints and Codex sources
are looked up in the local transcripts by session id. Reasons for C/D are recomputed with the
current tier code over the records that came before each verdict.
"""
import collections
import datetime
import glob
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from proof_of_green import tiers  # noqa: E402

DATA = os.path.expanduser("~/research/pog-data/sessions")
SINCE = datetime.datetime(2026, 10, 4).timestamp()
EXCLUDE = {"8499de", "7a063d"}           # the plugin's own repo, a test fixture
CLIENT = {"0be0e3", "e97509", "eb5d09"}  # client projects (eb5d09: a client checkout)


def entry_points():
    out = {}
    for f in glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl")):
        sid = os.path.basename(f)[:-6]
        for line in open(f, errors="replace"):
            if '"entrypoint"' in line:
                out[sid] = json.loads(line).get("entrypoint")
                break
    for f in glob.glob(os.path.expanduser("~/.codex/sessions/**/*.jsonl"), recursive=True):
        try:
            p = json.loads(open(f, errors="replace").readline()).get("payload") or {}
        except ValueError:
            continue
        src = p.get("source")
        out[p.get("id") or ""] = "codex-exec" if src == "exec" else ("codex-subagent" if isinstance(src, dict) else "codex")
    return out


def main():
    eps = entry_points()
    rows = []  # one per session
    for src in ("claude-terminal", "claude-desktop", "codex"):
        for f in glob.glob(os.path.join(DATA, src, "*.jsonl")):
            sid = os.path.basename(f)[:-6]
            recs = [json.loads(l) for l in open(f)]
            proj = next((r.get("project") for r in recs if r.get("kind") == "session" and r.get("project")), None)
            p6 = (proj or "------")[:6]
            if p6 in EXCLUDE:
                continue
            week = [r for r in recs if (r.get("ts") or 0) >= SINCE]
            if not week:
                continue
            ep = eps.get(sid, "?")
            typ = "autonomous" if ep in ("sdk-cli", "codex-exec") else ("client" if p6 in CLIENT else "personal")
            rows.append((src, sid, p6, typ, ep, recs, week))

    def agg(group):
        c = collections.Counter()
        for src, sid, p6, typ, ep, recs, week in group:
            c["sessions"] += 1
            c["no session record"] += not any(r.get("kind") == "session" for r in recs)
            c["turns"] += len({r.get("turn") for r in week if r.get("kind") == "turn"})
            edits = tiers.code_edits(recs)
            edit_turns = {e.get("turn") for e in edits if (e.get("ts") or 0) >= SINCE}
            c["turns with code edits"] += len(edit_turns)
            claim_turns = set()
            prev_stop = 0
            for r in recs:
                if r.get("kind") == "test_run" and (r.get("ts") or 0) >= SINCE:
                    c["test runs"] += 1
                    c["test runs unparsed"] += r.get("collected") is None
                if r.get("kind") not in ("verdict", "stop"):
                    continue
                if r.get("kind") == "verdict" and (r.get("ts") or 0) >= SINCE and not r.get("partial"):
                    claim_turns.add(r.get("turn"))
                    upto = [x for x in recs if x["seq"] < r["seq"]]
                    in_turn = any(e.get("turn") == r.get("turn") and e["seq"] < r["seq"] for e in edits)
                    since = any(prev_stop < e["seq"] < r["seq"] for e in edits)
                    graded = []
                    for cl in r.get("claims") or []:
                        tier, reason = tiers.evidence(upto, cl["type"])
                        graded.append((cl, tier))
                        c["claims"] += 1
                        c["claim " + cl["type"]] += 1
                        c["tier " + tier] += 1
                        if cl["type"] == "tests_pass":
                            c["tests_pass"] += 1
                            c["tests_pass failed-run"] += "failed" in reason
                    bad = any(t in "CD" for _, t in graded)
                    c["would warn v0.1 (edit this turn)"] += bad and in_turn
                    c["would warn v0.2 (edit since last stop)"] += bad and since
                prev_stop = r["seq"]
            c["edit turns with no claim"] += len(edit_turns - claim_turns)
        return c

    groups = collections.OrderedDict([("all", rows)])
    for t in ("autonomous", "client", "personal"):
        groups[t] = [r for r in rows if r[3] == t]
    keys = ["sessions", "no session record", "turns", "turns with code edits", "edit turns with no claim",
            "claims", "claim tests_pass", "claim fixed", "claim done", "claim verified", "claim deployed",
            "tier A", "tier B", "tier C", "tier D", "tests_pass failed-run", "test runs", "test runs unparsed",
            "would warn v0.1 (edit this turn)", "would warn v0.2 (edit since last stop)"]
    res = {g: agg(v) for g, v in groups.items()}
    print("%-40s" % "" + "".join("%12s" % g for g in groups))
    for k in keys:
        print("%-40s" % k + "".join("%12d" % res[g][k] for g in groups))
    a = res["all"]
    n = a["claims"]
    cd = a["tier C"] + a["tier D"]
    if n:
        p = cd / float(n)
        half = 1.96 * math.sqrt(p * (1 - p) / n)
        print("\nC+D share: %d of %d = %.0f%% (95%% CI ±%.0f points, claims treated as independent)" % (cd, n, 100 * p, 100 * half))
        print("n for ±10 points at this p: %d claims (×2 to ×3 if claims cluster by session)" % math.ceil(1.96 ** 2 * p * (1 - p) / 0.01))
    if a["turns with code edits"]:
        print("edit turns with no claim: %d of %d = %.0f%%" % (a["edit turns with no claim"], a["turns with code edits"],
                                                            100.0 * a["edit turns with no claim"] / a["turns with code edits"]))
    if a["tests_pass"]:
        print("tests_pass claims whose last run after the edit failed: %d of %d" % (a["tests_pass failed-run"], a["tests_pass"]))
    print("\nprojects by type:", {t: sorted(collections.Counter(r[2] for r in v).items()) for t, v in groups.items() if t != "all"})
    print("sources:", dict(collections.Counter(r[0] for r in rows)), " entry points:", dict(collections.Counter(r[4] for r in rows)))


if __name__ == "__main__":
    main()
