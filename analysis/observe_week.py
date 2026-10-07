#!/usr/bin/env python3
"""Observe-week analysis: re-parse unparsed test runs, then grade every claim under three edit rules.

Reads the plugin ledgers (both data folders) and, only to re-parse test output, the local
Claude Code transcripts of the same sessions. Prints aggregates only: no commands, no output.

Edit rules:
  current   only Edit / Write / MultiEdit count as code edits (what the plugin does today)
  best      also a Bash command that writes a file AND names a code file in the project
  upper     also any Bash command that looks like it writes a file
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
from proof_of_green import bashparse, hooks, ledger, tiers  # noqa: E402

DATA = [os.path.expanduser("~/.claude/plugins/data/proof-of-green-proof-of-green"),
        os.path.expanduser("~/.claude/plugins/data/proof-of-green-inline")]
TRANSCRIPTS = os.path.expanduser("~/.claude/projects")
EXCLUDE = {"8499de", "7a063d"}  # the plugin's own repo (builder session), an old test session

WRITES = re.compile(
    r"\bsed\s+(?:-\S+\s+)*-i\b|\bperl\s+-\w*i|(?<![<>&\d])>{1,2}\s*(?!&|/dev/null)[\w.~/-]|\btee\b|"
    r"\bpatch\b|\bgit\s+apply\b|\.write_text\(|\.write_bytes\(|open\([^)]*['\"][wa]\+?['\"]|writeFile")
HEREDOC_SCRIPT = re.compile(r"\b(?:python3?|node|ruby|perl)\s+-\s*<<")
CODE_PATH = re.compile(r"(?<![\w<>])((?:[\w-]+/)*[\w.-]+\.(?:py|ts|tsx|js|jsx|mjs|cjs|dart|swift|kt|kts|java|go|rs|"
                       r"rb|php|cs|vue|svelte|sql))\b")


def code_paths(cmd):
    return [p for p in CODE_PATH.findall(cmd) if not hooks.is_test_path(p) and not hooks.DOC_PATH.search(p)]


REDIRECT_TARGET = re.compile(r"(?<![<>&\d])>{1,2}\s*([\w.~/-]+)")
TEE_TARGET = re.compile(r"\btee\s+(?:-a\s+)?([\w.~/-]+)")
INPLACE = re.compile(r"\bsed\s+(?:-\S+\s+)*-i\b|\bperl\s+-\w*i")
SCRIPT_WRITE = re.compile(r"\.write_text\(|\.write_bytes\(|open\([^)]*['\"][wa]\+?['\"]|writeFile")
APPLY = re.compile(r"\bpatch\b|\bgit\s+apply\b")
TRIGGERS = collections.Counter()


def _is_code(path):
    return bool(CODE_PATH.fullmatch(path)) and not hooks.is_test_path(path) and not hooks.DOC_PATH.search(path)


def write_kind(cmd):
    """None, 'code' (a write whose target is a code file in the project) or 'any' (writes something else
    or the target is not visible, e.g. truncated or outside the project)."""
    cmd = cmd or ""
    if any(_is_code(t) for t in REDIRECT_TARGET.findall(cmd)):
        TRIGGERS["redirect into code file"] += 1
        return "code"
    if any(_is_code(t) for t in TEE_TARGET.findall(cmd)):
        TRIGGERS["tee into code file"] += 1
        return "code"
    if INPLACE.search(cmd) and code_paths(cmd):
        TRIGGERS["sed -i / perl -i on code file"] += 1
        return "code"
    if HEREDOC_SCRIPT.search(cmd) and SCRIPT_WRITE.search(cmd) and code_paths(cmd):
        TRIGGERS["script heredoc writing, code path named"] += 1
        return "code"
    if APPLY.search(cmd):
        TRIGGERS["patch / git apply"] += 1
        return "code"
    if WRITES.search(cmd) or HEREDOC_SCRIPT.search(cmd):
        TRIGGERS["other write or script (upper bound only)"] += 1
        return "any"
    return None


def iso(ts):
    return datetime.datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S").replace(
        tzinfo=datetime.timezone.utc).timestamp()


def transcript_results(sid):
    """[(epoch, runner, text)] for every Bash test command in this session's transcripts."""
    out, uses = [], {}
    for f in glob.glob(os.path.join(TRANSCRIPTS, "*", sid + ".jsonl")) + \
            glob.glob(os.path.join(TRANSCRIPTS, "*", sid, "**", "*.jsonl"), recursive=True):
        for line in open(f, encoding="utf-8", errors="replace"):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            for c in (e.get("message") or {}).get("content") or []:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "tool_use" and c.get("name") == "Bash":
                    runner = bashparse.detect_runner((c.get("input") or {}).get("command", ""))[0]
                    if runner:
                        uses[c["id"]] = runner
                elif c.get("type") == "tool_result" and c.get("tool_use_id") in uses and e.get("timestamp"):
                    body = c.get("content")
                    text = body if isinstance(body, str) else "\n".join(
                        x.get("text", "") for x in body or [] if isinstance(x, dict))
                    out.append((iso(e["timestamp"]), uses[c["tool_use_id"]], text))
    return out


def sessions():
    for base in DATA:
        for f in sorted(glob.glob(os.path.join(base, "sessions", "*.jsonl"))):
            recs = ledger.read(f)
            first = next((r for r in recs if r.get("kind") == "session"), {})
            proj = (first.get("project") or (ledger.project_hash(first["cwd"]) if first.get("cwd") else "------"))[:6]
            if proj in EXCLUDE:
                continue
            yield os.path.basename(base), os.path.basename(f)[:-6], proj, recs


def reparse(all_sessions):
    stats = collections.Counter()
    by_runner = collections.Counter()
    left = collections.Counter()
    for _, sid, _, recs in all_sessions:
        todo = [r for r in recs if r.get("kind") == "test_run" and r.get("collected") is None]
        if not todo:
            continue
        results = transcript_results(sid)
        for r in todo:
            stats["unparsed"] += 1
            if "run_in_background" in (r.get("flags") or []):
                stats["background (no output to parse)"] += 1
                continue
            near = [x for x in results if x[1] == r.get("runner") and abs(x[0] - r["ts"]) < 20]
            if not near:
                stats["no matching output in transcript"] += 1
                continue
            text = min(near, key=lambda x: abs(x[0] - r["ts"]))[2]
            p, f, c = bashparse.parse_counts(text)
            if c is None:
                stats["still unparsed"] += 1
                left[r.get("runner")] += 1
                continue
            stats["recovered"] += 1
            by_runner[r.get("runner")] += 1
            r.update({"passed": p, "failed": f, "collected": c, "_reparsed": True})
    return stats, by_runner, left


def grade(all_sessions):
    rules = ("current", "best", "upper")
    res = {k: collections.Counter() for k in rules}
    moved = collections.Counter()
    for _, sid, proj, recs in all_sessions:
        bash = [r for r in recs if r.get("kind") in ("other", "test_run")]
        extra = {"current": [], "best": [], "upper": []}
        for r in bash:
            kind = write_kind(r.get("command"))
            fake = {"kind": "edit", "seq": r["seq"] - 0.5, "turn": r.get("turn"), "code": True, "is_test": False}
            if kind == "code":
                extra["best"].append(fake)
            if kind:
                extra["upper"].append(fake)
        for rule in rules:
            rs = recs + extra[rule]
            edit_turns = {r.get("turn") for r in tiers.code_edits(rs)}
            res[rule]["turns"] += ledger.current_turn(recs)
            res[rule]["edit_turns"] += len(edit_turns)
            res[rule]["bash_code_writes"] += len(extra[rule])
            for v in (r for r in recs if r.get("kind") == "verdict"):
                upto = [r for r in rs if r["seq"] < v["seq"]]
                for c in v.get("claims") or []:
                    tier, _ = tiers.evidence(upto, c["type"])
                    res[rule]["claims"] += 1
                    res[rule]["tier_" + tier] += 1
                    if v.get("turn") in edit_turns:
                        res[rule]["edit_claims"] += 1
                        res[rule]["edit_" + tier] += 1
                    if rule != "current":
                        before, _ = tiers.evidence([r for r in recs if r["seq"] < v["seq"]], c["type"])
                        if before in "AB" and tier in "CD":
                            moved[rule] += 1
    return res, moved


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-reparse", action="store_true", help="skip reading transcripts")
    args = ap.parse_args()
    all_sessions = list(sessions())
    projects = collections.Counter(p for _, _, p, _ in all_sessions)
    print("sessions %d in %d projects (%s); excluded projects %s" % (
        len(all_sessions), len(projects), ", ".join("%s x%d" % kv for kv in projects.most_common()), sorted(EXCLUDE)))
    if not args.no_reparse:
        stats, by_runner, left = reparse(all_sessions)
        print("\nre-parse of unparsed test runs (current parser, output read locally, not printed)")
        for k in ("unparsed", "recovered", "still unparsed", "no matching output in transcript",
                  "background (no output to parse)"):
            print("  %-34s %d" % (k, stats[k]))
        print("  recovered by runner                %s" % dict(by_runner))
        print("  still unparsed by runner           %s" % dict(left))
    res, moved = grade(all_sessions)
    print("\nclaims graded under three edit rules")
    print("  %-26s %10s %10s %10s" % ("", "current", "best", "upper"))
    rows = [("turns", "turns"), ("turns with a code edit", "edit_turns"), ("bash writes counted", "bash_code_writes"),
            ("claims (all turns)", "claims"), ("  tier A", "tier_A"), ("  tier B", "tier_B"), ("  tier C", "tier_C"),
            ("  tier D", "tier_D"), ("claims in edit turns", "edit_claims"), ("  of them C or D", None)]
    for label, key in rows:
        if key is None:
            vals = [res[r]["edit_C"] + res[r]["edit_D"] for r in ("current", "best", "upper")]
        else:
            vals = [res[r][key] for r in ("current", "best", "upper")]
        print("  %-26s %10d %10d %10d" % (label, vals[0], vals[1], vals[2]))
    for r in ("current", "best", "upper"):
        n = res[r]["edit_claims"]
        bad = res[r]["edit_C"] + res[r]["edit_D"]
        print("  unsupported-claim rate (%s): %s" % (r, "%d of %d = %.0f%%" % (bad, n, 100.0 * bad / n) if n else "n/a"))
    print("  claims that drop from A/B to C/D: best %d, upper %d" % (moved["best"], moved["upper"]))
    print("\nwhat counted as a Bash write (each command counted once per rule pass)")
    for k, v in TRIGGERS.most_common():
        print("  %-44s %d" % (k, v))


if __name__ == "__main__":
    main()
