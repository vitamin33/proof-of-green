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
from proof_of_green.codex import exec_events  # noqa: E402
import backfill  # noqa: E402

CODEX = [os.path.expanduser("~/.codex/sessions"), os.path.expanduser("~/.codex/archived_sessions")]
EXCLUDE_CWD = ("/private/tmp/", "/tmp/", os.path.expanduser("~/.cache/"))
EXCLUDE_NAMES = {"fx4", "fx6", "fx7", "fx8", "scratchpad"}


def ts_of(e):
    t = e.get("timestamp")
    if not t:
        return None
    return datetime.datetime.strptime(t[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=datetime.timezone.utc).timestamp()


def replay(path, stats):
    recs, stops, calls, pending = [], [], {}, {}
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
            meta["id"] = p.get("id") or p.get("session_id")  # thread id; session_id is shared by a thread family
            meta["parent"] = p.get("parent_thread_id")
            meta["subagent"] = p.get("source") == "subagent" or bool(p.get("parent_thread_id"))
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
        if t == "user_message" and backfill.KEEP_DETAIL:
            meta.setdefault("prompts", []).append((ts, str(p.get("message") or "")))
        if t == "task_started":
            turn[0] += 1
        elif t == "task_complete":
            seq[0] += 1
            msg = p.get("last_agent_message")
            stops.append(dict({"seq": seq[0], "turn": turn[0], "ts": ts,
                               "claims": claims.extract(msg) if isinstance(msg, str) else []},
                              **({"message": msg} if backfill.KEEP_DETAIL else {})))
        elif t == "custom_tool_call" and p.get("name") == "exec":
            calls[p.get("call_id")] = p.get("input") or ""
        elif t == "custom_tool_call_output" and p.get("call_id") in calls:
            code = calls.pop(p["call_id"])
            project = meta.get("project")
            for ev in exec_events(code, p.get("output")):
                if ev[0] == "patch":
                    _, is_test, is_code = hooks.classify(ev[1], project)
                    add(dict({"kind": "edit", "via": "tool", "is_test": is_test, "code": is_code},
                             **({"path": ev[1]} if backfill.KEEP_DETAIL else {})), ts)
                    stats["apply_patch files"] += 1
                    continue
                if ev[0] == "finish":
                    start = pending.pop(ev[1], None)
                    if start is None:
                        continue
                    res = ev[2]
                    passed, failed, collected = bashparse.parse_counts(res["output"])
                    rec = {k: start[k] for k in ("command", "runner", "scope", "flags", "exit_masked", "piped")
                           if k in start}
                    rec.update(kind="test_run", exit_code=res["exit_code"], passed=passed, failed=failed,
                               collected=collected, started_seq=start["seq"])
                    add(rec, ts)
                    stats["test runs finished in a later poll (write_stdin)"] += 1
                    continue
                _, cmd, workdir, res = ev
                stats["exec_command calls"] += 1
                if cmd is None:
                    stats["command not readable (variable)"] += 1
                    continue
                here = workdir or meta["cwd"] or ""
                if res is None:
                    stats["commands without a usable result (outcome unknown)"] += 1
                elif res["process"] is not None:
                    stats["still running when the call returned"] += 1
                elif res["exit_code"] is None:
                    stats["command with raw text result (exit code unknown)"] += 1
                else:
                    stats["commands paired with a JSON result"] += 1
                known = res is not None and res["exit_code"] is not None
                payload = {"tool_input": {"command": cmd}, "cwd": here,
                           "hook_event_name": "PostToolUseFailure" if known and res["exit_code"] else "PostToolUse",
                           # unknown outcome: the command ran; a test run counts as passing unless its counts say not
                           "tool_response": {"stdout": (res or {}).get("output") or "",
                                             "exit_code": res["exit_code"] if known else 0}}
                rec = bashparse.parse_bash(payload)
                if rec["kind"] == "test_run":
                    rec["piped"] = bool(backfill.PIPE_MASK.search(cmd)) and "pipefail" not in cmd
                    if res is not None and res["process"] is not None:
                        rec.update(pending=True, exit_code=None)
                    elif not known:
                        stats["test runs with unknown exit code (B at most)"] += 1
                        if rec.get("failed"):
                            rec["exit_code"] = 1
                if not backfill.KEEP_DETAIL:
                    rec.pop("command", None)
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
                if rec.get("pending"):
                    pending[res["process"]] = rec
    meta["project6"] = (meta.get("project") or "------")[:6]
    return recs, stops, meta


def roots(since, stats, skipped):
    """Yield (root thread id, records, stops, meta) with subagent threads merged into their root."""
    threads = {}
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
            threads[meta.get("id") or f] = (recs, stops, meta)
    # subagent threads report to their parent agent, not to you: their edits and test runs join
    # the root thread's timeline (as Claude subagents do), their final messages are not claims
    def root_of(tid, seen=()):
        meta = threads[tid][2]
        parent = meta.get("parent")
        if meta.get("subagent") and parent in threads and parent not in seen:
            return root_of(parent, seen + (tid,))
        return tid
    merged = {}
    for tid, (recs, stops, meta) in threads.items():
        root = root_of(tid)
        if threads[root][2].get("subagent"):
            skipped["subagent thread whose parent is not on disk"] += 1
            continue
        m = merged.setdefault(root, {"own": [], "sub": [], "stops": [], "meta": threads[root][2]})
        if tid == root:
            m["own"] += recs
            m["stops"] += stops
        else:
            m["sub"] += recs
            stats["subagent threads merged into a root thread"] += 1
    for root, m in merged.items():
        # the root's turn at any moment = turn of its latest own record or stop at that time
        marks = sorted([(r["ts"], r["turn"]) for r in m["own"]] + [(x["ts"], x["turn"]) for x in m["stops"]])
        def turn_at(ts):
            t = 0
            for mts, mturn in marks:
                if mts > ts:
                    break
                t = mturn
            return t
        items = [("r", dict(r)) for r in m["own"]] + [("r", dict(r, turn=turn_at(r["ts"]))) for r in m["sub"]] + \
                [("s", dict(x)) for x in m["stops"]]
        items.sort(key=lambda kx: (kx[1]["ts"], kx[0] == "s"))
        recs, stops2 = [], []
        for n, (kind, x) in enumerate(items, 1):
            x["seq"] = n
            (stops2 if kind == "s" else recs).append(x)
        yield root, recs, stops2, m["meta"]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--since", default="2026-09-01")
    ap.add_argument("--json", help="also write the aggregates (numbers only) to this file")
    args = ap.parse_args()
    since = datetime.datetime.strptime(args.since, "%Y-%m-%d").timestamp()
    stats, skipped = collections.Counter(), collections.Counter()
    groups = collections.defaultdict(collections.Counter)
    projects = collections.defaultdict(collections.Counter)
    for root, recs_, stops_, meta in roots(since, stats, skipped):
        if not recs_ and not any(s_["claims"] for s_ in stops_):
            skipped["no tool use and no claims"] += 1
            continue
        for rule in ("v0.1", "v0.2"):
            groups[rule]["sessions"] += 1
            backfill.grade(recs_, stops_, rule, groups[rule])
        backfill.grade(recs_, stops_, "v0.2", projects[meta["project6"]])
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
