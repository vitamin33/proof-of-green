#!/usr/bin/env python3
"""One-command audit of your own Claude Code and Codex history. Nothing leaves your machine.

Runs the two backfills over local transcripts (~/.claude/projects, ~/.codex/sessions) and prints
one short block of counts: sessions, turns with code edits, completion claims, how many had a
test run after the last edit, and how many "tests pass" claims were followed by a failing run on
the same code. No prompt, reply, command, path or project name is printed or written; projects
appear as 6-character hashes. The block is what you can share.

    python3 analysis/audit.py --since 2026-09-01 [--out audit.txt]
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def run(script, since, out):
    r = subprocess.run([sys.executable, os.path.join(HERE, script), "--since", since, "--json", out],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None, r.stderr.strip().splitlines()[-1:] or ["failed"]
    try:
        return json.load(open(out)), []
    except (OSError, ValueError):
        return None, ["no output"]


def row(label, g):
    if not g:
        return "  %-14s no data" % label
    n, cd = g.get("claims", 0), g.get("tier_C", 0) + g.get("tier_D", 0)
    warn = g.get("would_warn", 0)
    return ("  %-14s sessions %4d  turns %5d  edit turns %4d  claims %4d  no fresh test run %4d (%s)  "
            "would warn %3d  then failed %3d" % (
                label, g.get("sessions", 0), g.get("turns", 0), g.get("edit_turns", 0), n, cd,
                "%.0f%%" % (100.0 * cd / n) if n else "n/a", warn, g.get("confirmed_false_green", 0)))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--since", default=(datetime.date.today() - datetime.timedelta(days=30)).isoformat())
    ap.add_argument("--out", help="also write the block to this file")
    args = ap.parse_args()
    tmp = tempfile.mkdtemp()
    claude, e1 = run("backfill.py", args.since, os.path.join(tmp, "c.json"))
    codex, e2 = run("backfill_codex.py", args.since, os.path.join(tmp, "x.json"))
    cg = (claude or {}).get("groups", {}).get("all | v0.2")
    xg = (codex or {}).get("groups", {}).get("v0.2")
    lines = ["proof-of-green audit, local history since %s (counts only, nothing uploaded)" % args.since,
             "", row("Claude Code", cg), row("Codex", xg), ""]
    both = {k: (cg or {}).get(k, 0) + (xg or {}).get(k, 0) for k in
            ("claims", "tier_C", "tier_D", "would_warn", "confirmed_false_green", "edit_turns", "test_runs", "unparsed_runs")}
    if both["claims"]:
        lines.append("  claims with no test run after the last code edit: %d of %d (%.0f%%)" % (
            both["tier_C"] + both["tier_D"], both["claims"], 100.0 * (both["tier_C"] + both["tier_D"]) / both["claims"]))
        lines.append("  would-warn cases: %d; of those, the next test run on the same code failed: %d" % (
            both["would_warn"], both["confirmed_false_green"]))
    if both["test_runs"]:
        lines.append("  test runs: %d, output not parsed: %d (%.0f%%)" % (
            both["test_runs"], both["unparsed_runs"], 100.0 * both["unparsed_runs"] / both["test_runs"]))
    if e1 or e2:
        lines.append("  notes: " + "; ".join(["Claude Code: " + x for x in e1] + ["Codex: " + x for x in e2]))
    lines.append("")
    lines.append("  how to read: 'no fresh test run' is a rule-based flag, not a verdict; in the author's own history")
    lines.append("  about 1 in 15 such flags held up when read by hand. The 'then failed' count is the stricter signal.")
    text = "\n".join(lines)
    print(text)
    if args.out:
        with open(os.path.expanduser(args.out), "w") as fh:
            fh.write(text + "\n")
    for f in ("c.json", "x.json"):
        try:
            os.remove(os.path.join(tmp, f))
        except OSError:
            pass
    os.rmdir(tmp)


if __name__ == "__main__":
    main()
