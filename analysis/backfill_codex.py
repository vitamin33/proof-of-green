#!/usr/bin/env python3
"""Backfill for Codex: replay local Codex rollouts through the same logic as the Claude backfill.

Codex runs tools from JavaScript (`text(await tools.exec_command({cmd: "..."}))`), so this
adapter pulls the shell commands and apply_patch calls out of that code, pairs each command
with its JSON result (exit_code, output) and rebuilds plugin-like records:

  task_started                 -> new turn
  apply_patch Update/Add File  -> edit record (same classification as Edit/Write)
  exec_command                 -> test_run / other via the plugin's parser, plus v0.2 shell-write edits
  task_complete                -> a Stop, claims from last_agent_message

Everything runs locally. Output: aggregates and project hashes only.
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
from proof_of_green import bashparse, claims, hooks, ledger  # noqa: E402
import backfill  # noqa: E402

CODEX = [os.path.expanduser("~/.codex/sessions"), os.path.expanduser("~/.codex/archived_sessions")]
EXCLUDE_CWD = ("/private/tmp/", "/tmp/", os.path.expanduser("~/.cache/"))
EXCLUDE_NAMES = {"fx4", "fx6", "fx7", "fx8", "scratchpad"}


def js_string(src, i):
    """Read a JS string literal starting at src[i] (one of ' " `). Returns (value, end) or (None, i)."""
    if i >= len(src) or src[i] not in "'\"`":
        return None, i
    q, j, out = src[i], i + 1, []
    while j < len(src):
        ch = src[j]
        if ch == "\\" and j + 1 < len(src):
            nxt = src[j + 1]
            out.append({"n": "\n", "t": "\t", "r": "\r", "0": "\0"}.get(nxt, nxt))
            j += 2
            continue
        if ch == q:
            return "".join(out), j + 1
        out.append(ch)
        j += 1
    return None, i


def strings_in(src):
    """All string literals in a JS fragment, in order."""
    out, i = [], 0
    while i < len(src):
        if src[i] in "'\"`":
            s, j = js_string(src, i)
            if s is not None:
                out.append(s)
                i = j
                continue
        i += 1
    return out


def commands_in(code):
    """[(cmd, workdir)] for every exec_command in the code, in source order.
    Handles cmd:"..." and the loop form: for (const cmd of ["a", "b"]) ... exec_command({cmd, ...})."""
    out = []
    loops = [(m.start(), m.group(1), strings_in(code[m.end():m.end() + code[m.end():].find("]")]))
             for m in re.finditer(r"for\s*\(\s*(?:const|let|var)\s+(\w+)\s+of\s*\[", code)]
    for m in re.finditer(r"exec_command\s*\(\s*\{", code):
        start = m.end()
        body_end = code.find("})", start)
        body = code[start:body_end if body_end > 0 else start + 2000]
        wd = re.search(r"[\"']?workdir[\"']?\s*:\s*", body)
        workdir = js_string(body, wd.end())[0] if wd else None
        c = re.search(r"[\"']?cmd[\"']?\s*:\s*", body)
        if c:
            val, _ = js_string(body, c.end())
            out.append((val, workdir) if val is not None else (None, workdir))
            continue
        if re.match(r"\s*cmd\s*[,}]", body):
            loop = [lp for lp in loops if lp[0] < m.start() and lp[1] == "cmd"]
            if loop:
                out.extend((s, workdir) for s in loop[-1][2])
                continue
        out.append((None, workdir))
    return out


def patch_files(code):
    """Files touched by apply_patch calls in the code."""
    files = []
    for m in re.finditer(r"apply_patch\s*\(\s*", code):
        text, _ = js_string(code, m.end())
        if text:
            files += re.findall(r"^\*\*\* (?:Update|Add|Delete) File: (.+)$", text, re.M)
            files += re.findall(r"^\*\*\* Move to: (.+)$", text, re.M)
    return [f.strip() for f in files]


def results_in(output):
    """Command results from an exec output list, in order: dicts with exit_code / output."""
    out = []
    for item in output[1:] if isinstance(output, list) else []:
        t = item.get("text", "") if isinstance(item, dict) else ""
        try:
            j = json.loads(t)
        except ValueError:
            continue
        if isinstance(j, dict) and isinstance(j.get("value"), dict):
            j = j["value"]  # Promise.allSettled
        if isinstance(j, dict) and "output" in j and ("exit_code" in j or "session_id" in j):
            out.append(j)
    return out


def ts_of(e):
    t = e.get("timestamp")
    if not t:
        return None
    return datetime.datetime.strptime(t[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=datetime.timezone.utc).timestamp()


def replay(path, stats):
    recs, stops, calls = [], [], {}
    seq, turn = [0], [0]
    meta = {"cwd": None}

    def add(rec, ts):
        seq[0] += 1
        rec.update(seq=seq[0], turn=turn[0], ts=ts)
        recs.append(rec)

    for line in open(path, encoding="utf-8", errors="replace"):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        p = e.get("payload") or {}
        ts = ts_of(e) or 0
        if e.get("type") == "session_meta" and meta["cwd"] is None:
            meta["cwd"] = p.get("cwd")
            meta["project"] = ledger.project_hash(p["cwd"]) if p.get("cwd") else None
            meta["first"] = ts
            meta["forked"] = any("fork" in k.lower() and p.get(k) for k in p)
            continue
        if meta.get("forked") and ts and ts < meta["first"] - 1:
            stats["forked: copied parent items skipped"] += 1
            continue  # a fork starts with a copy of the parent's history; the parent is counted on its own
        meta["last"] = ts
        t = p.get("type")
        if t == "task_started":
            turn[0] += 1
        elif t == "task_complete":
            seq[0] += 1
            msg = p.get("last_agent_message")
            stops.append({"seq": seq[0], "turn": turn[0], "ts": ts,
                          "claims": claims.extract(msg) if isinstance(msg, str) else []})
        elif t == "custom_tool_call" and p.get("name") == "exec":
            calls[p.get("call_id")] = p.get("input") or ""
        elif t == "custom_tool_call_output" and p.get("call_id") in calls:
            code = calls.pop(p["call_id"])
            project = meta.get("project")
            for f in patch_files(code):
                _, is_test, is_code = hooks.classify(f, project)
                add({"kind": "edit", "via": "tool", "is_test": is_test, "code": is_code}, ts)
                stats["apply_patch files"] += 1
            cmds = commands_in(code)
            res = results_in(p.get("output"))
            out = p.get("output") if isinstance(p.get("output"), list) else []
            raw = "\n".join(x.get("text", "") for x in out[1:] if isinstance(x, dict))
            stats["exec_command calls"] += len(cmds)
            if len(cmds) == len(res):
                pairs = list(zip(cmds, res))
                stats["commands paired with a JSON result"] += len(cmds)
            elif len(cmds) == 1 and not res and raw:
                pairs = [(cmds[0], {"output": raw, "exit_code": None})]
                stats["command with raw text result (exit code unknown)"] += 1
            else:
                pairs = [(c, None) for c in cmds]
                stats["commands without a usable result (runs skipped, edits kept)"] += len(cmds)
            for (cmd, workdir), r in pairs:
                if cmd is None:
                    stats["command not readable (variable)"] += 1
                    continue
                here = workdir or meta["cwd"] or ""
                if r is None or (r.get("exit_code") is None and "session_id" not in r):
                    # result unknown or raw text: keep edits; keep a test run only if its output shows counts
                    rec = None
                    if bashparse.detect_runner(cmd)[0]:
                        # the test command ran; its result is unknown unless the raw text shows counts
                        rec = bashparse.parse_bash({"tool_input": {"command": cmd}, "cwd": here,
                                                    "tool_response": {"stdout": r["output"] if r else "", "exit_code": 0}})
                        if rec.get("failed"):
                            rec["exit_code"] = 1
                        stats["test runs with unknown exit code (B at most)"] += 1
                    writes, patch, _ = bashparse.write_targets(cmd)
                    for wpath, cd in writes:
                        full = os.path.expanduser(wpath)
                        if not os.path.isabs(full):
                            full = os.path.normpath(os.path.join(here, os.path.expanduser(cd), full))
                        _, is_test, is_code = hooks.classify(full, project)
                        add({"kind": "edit", "via": "bash", "is_test": is_test, "code": is_code}, ts)
                    if patch:
                        add({"kind": "edit", "via": "bash", "is_test": False, "code": True}, ts)
                    if rec is not None:
                        rec.pop("command", None)
                        add(rec, ts)
                    continue
                if "exit_code" not in r:
                    stats["still running at result (write_stdin)"] += 1
                    payload = {"tool_input": {"command": cmd, "run_in_background": True}, "cwd": here}
                else:
                    code_ = r.get("exit_code")
                    payload = {"tool_input": {"command": cmd}, "cwd": here,
                               "hook_event_name": "PostToolUseFailure" if code_ else "PostToolUse",
                               "tool_response": {"stdout": r.get("output") or "", "exit_code": code_}}
                rec = bashparse.parse_bash(payload)
                rec.pop("command", None)
                if rec["kind"] == "test_run":
                    rec["piped"] = bool(backfill.PIPE_MASK.search(cmd)) and "pipefail" not in cmd
                edits = []
                writes, patch, first = bashparse.write_targets(cmd)
                for wpath, cd in writes:
                    full = os.path.expanduser(wpath)
                    if not os.path.isabs(full):
                        full = os.path.normpath(os.path.join(here, os.path.expanduser(cd), full))
                    _, is_test, is_code = hooks.classify(full, project)
                    edits.append({"kind": "edit", "via": "bash", "is_test": is_test, "code": is_code})
                if patch:
                    edits.append({"kind": "edit", "via": "bash", "is_test": False, "code": True})
                after = False
                if edits and rec["kind"] == "test_run":
                    _, seg = bashparse.detect_runner(cmd)
                    at = cmd.find(seg) if seg else -1
                    after = 0 <= at < (first or 0)
                for r2 in ([rec] + edits if after else edits + [rec]):
                    add(r2, ts)
    meta["project6"] = (meta.get("project") or "------")[:6]
    return recs, stops, meta


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--since", default="2026-09-01")
    ap.add_argument("--json", help="also write the aggregates (numbers only) to this file")
    args = ap.parse_args()
    since = datetime.datetime.strptime(args.since, "%Y-%m-%d").timestamp()
    stats, skipped = collections.Counter(), collections.Counter()
    groups = collections.defaultdict(collections.Counter)
    projects = collections.defaultdict(collections.Counter)
    for base in CODEX:
        for f in sorted(glob.glob(os.path.join(base, "**", "*.jsonl"), recursive=True)):
            if os.path.getmtime(f) < since:
                skipped["older than --since"] += 1
                continue
            recs, stops, meta = replay(f, stats)
            cwd = meta.get("cwd") or ""
            if not cwd or cwd.startswith(EXCLUDE_CWD) or os.path.basename(cwd) in EXCLUDE_NAMES \
                    or meta["project6"] in backfill.EXCLUDE_PROJECTS:
                skipped["scratch, test or builder"] += 1
                continue
            if not recs and not any(s["claims"] for s in stops):
                skipped["no tool use and no claims"] += 1
                continue
            for rule in ("v0.1", "v0.2"):
                groups[rule]["sessions"] += 1
                backfill.grade(recs, stops, rule, groups[rule])
            backfill.grade(recs, stops, "v0.2", projects[meta["project6"]])
            projects[meta["project6"]]["sessions"] += 1
    print("skipped rollouts:", dict(skipped))
    print("\nparsing coverage")
    for k in sorted(stats):
        print("  %-42s %d" % (k, stats[k]))
    a, b = groups["v0.1"], groups["v0.2"]
    print("\n== Codex, since %s" % args.since)
    print("  %-30s %8s %8s" % ("", "v0.1", "v0.2"))
    for label, k in [("sessions", "sessions"), ("turns", "turns"), ("turns with a code edit", "edit_turns"),
                     ("  code edits via apply_patch", "tool_code_edits"), ("  code edits via shell", "bash_code_edits"),
                     ("test runs", "test_runs"), ("  unparsed", "unparsed_runs"), ("claims", "claims"),
                     ("  tier A", "tier_A"), ("  tier B", "tier_B"), ("  tier C", "tier_C"), ("  tier D", "tier_D"),
                     ("claims in edit turns", "edit_claims"), ("would warn (warn mode)", "would_warn"),
                     ("  next test run then failed", "confirmed_false_green")]:
        print("  %-30s %8d %8d" % (label, a[k], b[k]))
    for rule, c in (("v0.1", a), ("v0.2", b)):
        n, bad = c["edit_claims"], c["edit_tier_C"] + c["edit_tier_D"]
        ab = c["tier_A"] + c["tier_B"]
        print("  %s: unsupported in edit turns %s; A/B share of all claims %s" % (
            rule, "%d of %d (%.0f%%)" % (bad, n, 100.0 * bad / n) if n else "n/a",
            "%d of %d (%.0f%%)" % (ab, c["claims"], 100.0 * ab / c["claims"]) if c["claims"] else "n/a"))
    print("\n== by project (v0.2 rule)")
    print("  %-8s %8s %8s %10s %8s %8s %10s" % ("project", "sessions", "turns", "edit turns", "claims", "C or D", "would warn"))
    for p, c in sorted(projects.items(), key=lambda kv: -kv[1]["turns"])[:15]:
        print("  %-8s %8d %8d %10d %8d %8d %10d" % (p, c["sessions"], c["turns"], c["edit_turns"], c["claims"],
                                                  c["tier_C"] + c["tier_D"], c["would_warn"]))
    if args.json:
        with open(os.path.expanduser(args.json), "w") as fh:
            json.dump({"generated": datetime.datetime.now().isoformat(timespec="seconds"), "since": args.since,
                       "skipped": dict(skipped), "coverage": dict(stats),
                       "groups": {k: dict(v) for k, v in groups.items()},
                       "projects": {k: dict(v) for k, v in projects.items()}}, fh, indent=1, sort_keys=True)
        print("\nwrote", args.json)


if __name__ == "__main__":
    main()
