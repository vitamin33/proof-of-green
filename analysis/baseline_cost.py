#!/usr/bin/env python3
"""Baseline cost: how much time and tokens agents spend checking whether a test failure is new.

A baseline comparison is a test command that runs the old code: after `git stash`, on main or
master, in a worktree of another ref, or labelled pre-existing / unpatched / baseline. Helper
commands (stash, checkout, stash pop without a test run) are counted as extra steps.

Claude Code: wall time from the tool call to its result, output tokens of the step that issued
it, input tokens of the next step (it reads the result). Codex: wall time from the exec result.
Prints aggregates only; --sample N prints N matched commands (redacted, cut to 160 chars) so the
pattern can be checked by eye.
"""
import argparse
import collections
import glob
import json
import os
import random
import re
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "analysis"))
import backfill  # noqa: E402
from proof_of_green import bashparse, codex  # noqa: E402

BASE = re.compile(
    r"git\s+stash\b(?!\s+(?:list|show|drop|pop|apply))|"
    r"git\s+(?:-C\s+\S+\s+)?checkout\s+(?:-q\s+)?(?:--detach\s+)?(?:origin/)?(?:main|master|HEAD~\d*|HEAD\^)\b|"
    r"git\s+(?:-C\s+\S+\s+)?worktree\s+add\b[^\n;&]*\s(?:origin/)?(?:main|master)\b|"
    r"git\s+archive\s+(?:origin/)?(?:main|master)\b|git\s+show\s+(?:origin/)?(?:main|master|HEAD~\d*):|"
    r"\bbaseline[\w-]*/|before (?:my|the) (?:patch|fix|change)|pre-?existing|unpatched", re.I)
HELPER = re.compile(r"^\s*(?:git\s+stash(?:\s+pop|\s+apply)?|git\s+(?:-C\s+\S+\s+)?checkout\s+\S+)\s*$")


def is_test(cmd):
    return bashparse.detect_runner(bashparse.blank_heredocs(cmd))[0] is not None


def is_base(cmd):
    return bool(BASE.search(bashparse.blank_heredocs(cmd)))


def ts(e):
    return backfill.ts_of(e)


def claude(stats, samples):
    files = glob.glob(os.path.join(backfill.TRANSCRIPTS, "*", "*.jsonl")) + \
        glob.glob(os.path.join(backfill.TRANSCRIPTS, "*", "*", "subagents", "*.jsonl"))
    for f in files:
        ents = []
        for line in open(f, errors="replace"):
            try:
                ents.append(json.loads(line))
            except ValueError:
                continue
        cwd = next((e.get("cwd") for e in ents if e.get("cwd")), "") or ""
        entry = next((e.get("entrypoint") for e in ents if e.get("entrypoint")), None)
        if not cwd or cwd.startswith(backfill.EXCLUDE_CWD) or cwd.startswith("/private/var/folders/") \
                or entry == "sdk-cli" or backfill.ledger.project_hash(cwd)[:6] in backfill.EXCLUDE_PROJECTS:
            continue
        # one usage per assistant message id, in order
        steps, seen = [], set()
        for i, e in enumerate(ents):
            m = e.get("message") or {}
            if e.get("type") == "assistant" and m.get("id") and m["id"] not in seen:
                seen.add(m["id"])
                steps.append((i, m.get("id"), m.get("usage") or {}))
        step_of = {}
        for i, e in enumerate(ents):
            m = e.get("message") or {}
            if e.get("type") == "assistant":
                step_of[i] = m.get("id")
        order = [sid for _, sid, _ in steps]
        usage = {sid: u for _, sid, u in steps}
        uses = {}
        for i, e in enumerate(ents):
            c = (e.get("message") or {}).get("content")
            if e.get("type") == "assistant" and isinstance(c, list):
                for b in c:
                    if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Bash":
                        uses[b.get("id")] = (i, (b.get("input") or {}).get("command") or "")
            if e.get("type") == "user" and isinstance(c, list):
                for b in c:
                    if not (isinstance(b, dict) and b.get("tool_use_id") in uses):
                        continue
                    ui, cmd = uses.pop(b["tool_use_id"])
                    t0, t1 = ts(ents[ui]), ts(e)
                    dur = (t1 - t0) if t0 and t1 and t1 >= t0 else None
                    test = is_test(cmd)
                    if test:
                        stats["all test commands"] += 1
                        if dur is not None:
                            stats["all test seconds"] += dur
                    if not is_base(cmd):
                        continue
                    if not test:
                        if HELPER.match(cmd):
                            stats["helper steps (stash, checkout)"] += 1
                        continue
                    stats["baseline test commands"] += 1
                    stats["_sessions"].add(f)
                    if dur is not None:
                        stats["baseline seconds"] += dur
                        stats["_durations"].append(dur)
                    sid = step_of.get(ui)
                    u = usage.get(sid) or {}
                    stats["output tokens (issuing step)"] += u.get("output_tokens") or 0
                    k = order.index(sid) + 1 if sid in order else None
                    if k is not None and k < len(order):
                        nu = usage.get(order[k]) or {}
                        stats["input tokens, fresh (next step)"] += (nu.get("input_tokens") or 0) + \
                            (nu.get("cache_creation_input_tokens") or 0)
                        stats["input tokens, cached (next step)"] += nu.get("cache_read_input_tokens") or 0
                    samples.append(bashparse.redact(cmd, cwd, 160))
        for _, _, u in steps:
            stats["session output tokens (all steps)"] += u.get("output_tokens") or 0


def codex_runs(stats, samples):
    for f in glob.glob(os.path.expanduser("~/.codex/sessions/**/*.jsonl"), recursive=True) + \
            glob.glob(os.path.expanduser("~/.codex/archived_sessions/**/*.jsonl"), recursive=True):
        calls, cwd = {}, ""
        for line in open(f, errors="replace"):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            p = e.get("payload") or {}
            if e.get("type") == "session_meta":
                cwd = p.get("cwd") or ""
            if p.get("type") == "custom_tool_call" and p.get("name") == "exec":
                calls[p.get("call_id")] = p.get("input") or ""
            elif p.get("type") == "custom_tool_call_output" and p.get("call_id") in calls:
                code = calls.pop(p["call_id"])
                if cwd.startswith(backfill.EXCLUDE_CWD):
                    continue
                res = codex.results_in(p.get("output"))
                walls = {i: r.get("wall_time_seconds") for i, r in enumerate(res)}
                for n, ev in enumerate(codex.calls_in(code)):
                    if ev[0] != "exec" or not ev[1]:
                        continue
                    cmd = ev[1]
                    if not is_test(cmd):
                        continue
                    stats["all test commands"] += 1
                    w = walls.get(n) if len(res) == len(codex.calls_in(code)) else None
                    stats['_paired'] += 1 if w is not None else 0
                    if isinstance(w, (int, float)):
                        stats["all test seconds"] += w
                    if is_base(cmd):
                        stats["baseline test commands"] += 1
                        stats["_sessions"].add(f)
                        if isinstance(w, (int, float)):
                            stats["baseline seconds"] += w
                            stats["_durations"].append(w)
                        samples.append(bashparse.redact(cmd, cwd, 160))


def show(name, s):
    d = s.pop("_durations")
    sessions = s.pop("_sessions")
    print("\n== %s" % name)
    for k in ("all test commands", "baseline test commands", "helper steps (stash, checkout)"):
        if k in s:
            print("  %-40s %10d" % (k, s[k]))
    print("  %-40s %10d" % ("transcripts with a baseline comparison", len(sessions)))
    if s["all test commands"]:
        print("  %-40s %9.1f%%" % ("share of test commands", 100.0 * s["baseline test commands"] / s["all test commands"]))
    print("  %-40s %10.1f h" % ("wall time of baseline runs", s["baseline seconds"] / 3600.0))
    if s["all test seconds"]:
        print("  %-40s %9.1f%%" % ("share of all test-run wall time", 100.0 * s["baseline seconds"] / s["all test seconds"]))
    if d:
        q = statistics.quantiles(d, n=10) if len(d) >= 10 else [max(d)] * 9
        print("  %-40s %6.0f s / %.0f s / %.0f s" % ("per run: median / p90 / max", statistics.median(d), q[8], max(d)))
    for k in ("output tokens (issuing step)", "input tokens, fresh (next step)", "input tokens, cached (next step)",
              "session output tokens (all steps)"):
        if k in s:
            print("  %-40s %10d" % (k, s[k]))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sample", type=int, default=0)
    args = ap.parse_args()
    for name, fn in (("Claude Code", claude), ("Codex", codex_runs)):
        s = collections.Counter()
        s["_sessions"], s["_durations"] = set(), []
        samples = []
        fn(s, samples)
        show(name, s)
        if args.sample:
            random.seed(3)
            print("  sample of matched commands:")
            for c in random.sample(samples, min(args.sample, len(samples))):
                print("   -", c)


if __name__ == "__main__":
    main()
