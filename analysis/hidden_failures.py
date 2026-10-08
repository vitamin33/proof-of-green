#!/usr/bin/env python3
"""Hidden failures: test runs whose output shows failures while the shell exit code was 0.

Usually a pipe hides the exit code (`pytest | tail -5`). A human or the agent reading the output
can still see the failures; anything that only checks the exit code (CI step, orchestrator,
background agent) would take the run as green.

For each such run in the local Claude Code history this script records the command, counts,
a short tail of the output, the agent's next text, and the claims at the end of the turn.
Prints aggregates only; --cases writes a private file (mode 600) for a manual check.
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
from proof_of_green import bashparse, claims  # noqa: E402

# runs where failing is the point
EXPECTED = re.compile(r"mutat|mutant|witness|stash|baseline|before (?:my|the) (?:patch|fix)|red[- ]first|"
                      r"expect(?:ed)?[-_ ]fail|should fail|--self-mutate|xfail|negative control|"
                      r"git\s+checkout\s+\S+\s+--|git\s+show\s+\S+:", re.I)
ACK = re.compile(r"\bfail|падін|впав|впал|червон|broken|not\s+pass|pre-?existing|already\s+fail|regress|"
                 r"не\s+проход|помилк|error", re.I | re.U)


def runs_in(main_file, subs):
    entries = []
    for f, side in [(main_file, False)] + [(s, True) for s in subs]:
        entries += backfill.read_entries(f, side)
    entries.sort(key=lambda x: x[0])
    pending, out = {}, []
    texts = []  # (ts, side, text, is_end)
    for ts, side, e in entries:
        content = (e.get("message") or {}).get("content")
        if e.get("type") == "assistant" and isinstance(content, list):
            m = e.get("message") or {}
            t = "\n".join(b.get("text") or "" for b in content if isinstance(b, dict) and b.get("type") == "text")
            if t.strip():
                texts.append((ts, side, t, m.get("stop_reason") in ("end_turn", "stop_sequence")))
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Bash":
                    pending[b.get("id")] = (b.get("input") or {}, e.get("cwd"))
        if e.get("type") == "user" and isinstance(content, list):
            for b in content:
                if not (isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") in pending):
                    continue
                tin, cwd = pending.pop(b["tool_use_id"])
                if b.get("is_error"):
                    continue
                tur = e.get("toolUseResult")
                payload = {"tool_input": tin, "cwd": cwd, "hook_event_name": "PostToolUse",
                           "tool_response": tur if isinstance(tur, dict) else backfill.result_text(b, e)}
                rec = bashparse.parse_bash(payload)
                if rec["kind"] != "test_run" or not (rec.get("failed") or 0) > 0:
                    continue
                _, text = bashparse.response_text(payload)
                out.append({"file": main_file, "tool_use_id": b["tool_use_id"], "ts": ts, "side": side, "command": rec["command"], "runner": rec["runner"],
                            "passed": rec.get("passed"), "failed": rec.get("failed"),
                            "piped": bool(backfill.PIPE_MASK.search(tin.get("command") or "")),
                            "tail": text[-500:], "raw_cmd": tin.get("command") or ""})
    for r in out:
        nxt = next((t for ts, side, t, _ in texts if ts > r["ts"] and side == r["side"]), "")
        end = next((t for ts, side, t, end in texts if ts > r["ts"] and not side and end), "")
        r["next_text"] = nxt[:400]
        r["end_text"] = end[:400]
        r["end_claims"] = [c["type"] for c in claims.extract(end)] if end else []
    return out


def classify(r):
    if EXPECTED.search(r["raw_cmd"]):
        return "expected failure (mutation, witness, baseline, old code)"
    if r["next_text"] and ACK.search(r["next_text"]):
        return "agent saw it (next text names the failure)"
    if r["end_claims"]:
        return "not named next; turn ends with a claim"
    return "not named next; no claim at turn end"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--since", default="2024-01-01")
    ap.add_argument("--cases", help="private per-run file (mode 600)")
    args = ap.parse_args()
    since = datetime.datetime.strptime(args.since, "%Y-%m-%d").timestamp()
    rows = []
    for main_file in sorted(glob.glob(os.path.join(backfill.TRANSCRIPTS, "*", "*.jsonl"))):
        if os.path.getmtime(main_file) < since:
            continue
        sid = os.path.basename(main_file)[:-6]
        first = next((json.loads(l) for l in open(main_file, errors="replace") if '"cwd"' in l), {})
        cwd = first.get("cwd") or ""
        if not cwd or cwd.startswith(backfill.EXCLUDE_CWD) or cwd.startswith("/private/var/folders/") or \
                first.get("entrypoint") == "sdk-cli":
            continue
        if backfill.ledger.project_hash(cwd)[:6] in backfill.EXCLUDE_PROJECTS:
            continue
        subs = glob.glob(os.path.join(os.path.dirname(main_file), sid, "subagents", "*.jsonl"))
        for r in runs_in(main_file, subs):
            r["project"] = backfill.ledger.project_hash(cwd)[:6]
            r["class"] = classify(r)
            rows.append(r)
    piped = [r for r in rows if r["piped"]]
    print("test runs with failures in the output but exit code 0: %d (piped: %d)" % (len(rows), len(piped)))
    for name, group in (("all", rows), ("piped", piped)):
        print("\n== %s" % name)
        for k, v in collections.Counter(r["class"] for r in group).most_common():
            print("  %-58s %5d" % (k, v))
    print("\nby runner (piped):", dict(collections.Counter(r["runner"] for r in piped).most_common(8)))
    print("by project (piped):", dict(collections.Counter(r["project"] for r in piped).most_common(8)))
    claimed = [r for r in piped if r["class"].startswith("not named next; turn ends")]
    print("claims at turn end after an unnamed hidden failure:",
          dict(collections.Counter(c for r in claimed for c in r["end_claims"])))
    if args.cases:
        path = os.path.expanduser(args.cases)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            for r in rows:
                r = dict(r)
                r.pop("raw_cmd", None)
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.chmod(path, 0o600)
        print("\nwrote %d rows to %s (mode 600, not printed)" % (len(rows), args.cases))


if __name__ == "__main__":
    main()
