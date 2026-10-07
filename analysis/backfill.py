#!/usr/bin/env python3
"""Backfill: replay local Claude Code transcripts through the plugin's own logic.

Covers sessions the plugin never saw (started before the install, old terminals) and the
history before the install, so there is a baseline. Everything runs locally. Output is
aggregates and project hashes only: no prompt, reply, command or tool output is printed or stored.

What a replay does per session, in transcript order:
  your prompt                      -> new turn
  Edit / Write / MultiEdit (ok)    -> edit record, classified like the plugin does
  Bash                             -> test_run / other record (same parser), plus v0.2 shell-write edits
  last assistant text of a turn    -> a Stop: claims extracted, graded under two rules

Rules compared:
  v0.1  edits = Edit/Write/MultiEdit only, warn needs a code edit in this turn
  v0.2  edits also include shell writes into code files, warn needs a code edit since the previous Stop
"""
import argparse
import collections
import datetime
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from proof_of_green import bashparse, claims, hooks, ledger, tiers  # noqa: E402

TRANSCRIPTS = os.path.expanduser("~/.claude/projects")
DATA = [os.path.expanduser("~/.claude/plugins/data/proof-of-green-proof-of-green"),
        os.path.expanduser("~/.claude/plugins/data/proof-of-green-inline")]
INSTALL = datetime.datetime(2026, 10, 2, 17, 29, tzinfo=datetime.timezone.utc).timestamp()  # user-scope install
EXCLUDE_PROJECTS = {"8499de"}  # the plugin's own repo
EXCLUDE_CWD = ("/private/tmp/", "/tmp/", os.path.expanduser("~/.cache/"))  # scratch fixtures and test runs
EDIT_TOOLS = {"Edit", "Write", "MultiEdit"}
KEEP_DETAIL = False  # review_sample.py turns this on to build a local review file; aggregates never use it
PIPE_MASK = __import__("re").compile(r"\|\s*(?:tail|head|grep|sed|awk|cut|wc|tee)\b")  # exit code becomes the last command's


def ts_of(e):
    t = e.get("timestamp")
    if not t:
        return None
    return datetime.datetime.strptime(t[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=datetime.timezone.utc).timestamp()


def read_entries(path, sidechain):
    out = []
    for line in open(path, encoding="utf-8", errors="replace"):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        t = ts_of(e)
        if t is None:
            continue
        queued = e.get("type") == "attachment" and (e.get("attachment") or {}).get("type") == "queued_command"
        if e.get("type") in ("user", "assistant") or queued:
            out.append((t, sidechain, e))
    return out


def is_prompt(e):
    if e.get("type") != "user" or e.get("isMeta") or e.get("isCompactSummary") or e.get("isVisibleInTranscriptOnly"):
        return False
    c = (e.get("message") or {}).get("content")
    if isinstance(c, str):
        return bool(c.strip())
    if isinstance(c, list):
        return any(isinstance(x, dict) and x.get("type") == "text" for x in c) and \
            not any(isinstance(x, dict) and x.get("type") == "tool_result" for x in c)
    return False


def result_text(block, e):
    body = block.get("content")
    text = body if isinstance(body, str) else "\n".join(
        x.get("text", "") for x in body or [] if isinstance(x, dict))
    return text


def replay(sid, files):
    """Build plugin-like records for one session. Returns (records, stops, meta)."""
    entries = []
    for f, side in files:
        entries += read_entries(f, side)
    entries.sort(key=lambda x: x[0])
    main = [e for _, side, e in entries if not side]
    cwd = next((e.get("cwd") for e in main if e.get("cwd")), None)
    entrypoint = next((e.get("entrypoint") for e in main if e.get("entrypoint")), None)
    meta = {"cwd": cwd, "project": ledger.project_hash(cwd)[:6] if cwd else "------", "entrypoint": entrypoint,
            "automation": entrypoint == "sdk-cli" or (cwd or "").startswith("/private/var/folders/"),
            "first": entries[0][0] if entries else None, "last": entries[-1][0] if entries else None}
    project = ledger.project_hash(cwd) if cwd else None
    recs, stops, pending = [], [], {}
    seq, turn = [0], [0]
    messages = {}  # assistant message id -> its stop, filled in as the message's entries arrive

    def add(rec, ts):
        seq[0] += 1
        rec.update(seq=seq[0], turn=turn[0], ts=ts)
        recs.append(rec)

    for ts, side, e in entries:
        content = (e.get("message") or {}).get("content")
        if not side and (is_prompt(e) or e.get("type") == "attachment"):
            turn[0] += 1  # your prompt, or a message you queued while Claude was working
            continue
        if e.get("type") == "assistant" and not side:
            m = e.get("message") or {}
            mid = m.get("id") or id(e)
            texts = [b.get("text") or "" for b in content or [] if isinstance(b, dict) and b.get("type") == "text"]
            st = messages.get(mid)
            if st is None and m.get("stop_reason") in ("end_turn", "stop_sequence"):
                # Claude finished its reply: this is where the Stop hook fires
                seq[0] += 1
                st = {"seq": seq[0], "turn": turn[0], "ts": ts, "texts": []}
                messages[mid] = st
                stops.append(st)
            elif st is None:
                messages[mid] = st = {"texts": [], "pending": True}
            st["texts"] += texts
        if e.get("type") == "assistant" and isinstance(content, list):
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    pending[b.get("id")] = (b.get("name"), b.get("input") or {}, e.get("cwd") or cwd)
        if e.get("type") == "user" and isinstance(content, list):
            for b in content:
                if not (isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") in pending):
                    continue
                name, tin, here = pending.pop(b["tool_use_id"])
                failed = bool(b.get("is_error"))
                if name in EDIT_TOOLS and not failed:
                    path = tin.get("file_path") or ""
                    if path:
                        rel, is_test, code = hooks.classify(path, project)
                        add(dict({"kind": "edit", "via": "tool", "is_test": is_test, "code": code},
                                 **({"path": rel} if KEEP_DETAIL else {})), ts)
                elif name == "Bash":
                    cmd = tin.get("command") or ""
                    tur = e.get("toolUseResult")
                    payload = {"tool_input": tin, "cwd": here,
                               "hook_event_name": "PostToolUseFailure" if failed else "PostToolUse"}
                    if failed:
                        payload["error"] = result_text(b, e)
                    else:
                        payload["tool_response"] = tur if isinstance(tur, dict) else result_text(b, e)
                    rec = bashparse.parse_bash(payload)
                    if not KEEP_DETAIL:
                        rec.pop("command", None)  # nothing from the command is kept
                    if rec["kind"] == "test_run":
                        rec["piped"] = bool(PIPE_MASK.search(cmd)) and "pipefail" not in cmd
                    edits = []
                    writes, patch, first = bashparse.write_targets(cmd)
                    for path, cd in writes:
                        full = os.path.expanduser(path)
                        if not os.path.isabs(full):
                            full = os.path.normpath(os.path.join(here or "", os.path.expanduser(cd), full))
                        _, is_test, code = hooks.classify(full, project)
                        edits.append({"kind": "edit", "via": "bash", "is_test": is_test, "code": code})
                    if patch:
                        edits.append({"kind": "edit", "via": "bash", "is_test": False, "code": True})
                    after = False
                    if edits and rec["kind"] == "test_run":
                        _, seg = bashparse.detect_runner(cmd)
                        at = cmd.find(seg) if seg else -1
                        after = 0 <= at < (first or 0)
                    for r in ([rec] + edits if after else edits + [rec]):
                        add(r, ts)
    for st in stops:
        msg = "\n".join(st.pop("texts"))
        st["claims"] = claims.extract(msg)
        if KEEP_DETAIL:
            st["message"] = msg
    return recs, stops, meta


def grade(recs, stops, rule, c):
    rs = [r for r in recs if rule == "v0.2" or r.get("via") != "bash"]
    edits = tiers.code_edits(rs)
    edit_turns = {e["turn"] for e in edits}
    c["turns"] += max([r["turn"] for r in recs] + [s["turn"] for s in stops] + [0])
    c["edit_turns"] += len(edit_turns)
    prev = 0
    for s in stops:
        found = s["claims"]
        if not found:
            prev = s["seq"]
            continue
        upto = [r for r in rs if r["seq"] < s["seq"]]
        graded = []
        for cl in found:
            tier, reason = tiers.evidence(upto, cl["type"])
            graded.append(dict(cl, tier=tier, reason=reason))
            c["claims"] += 1
            c["claim_" + cl["type"]] += 1
            c["tier_" + tier] += 1
            if s["turn"] in edit_turns:
                c["edit_claims"] += 1
                c["edit_tier_" + tier] += 1
        bad = tiers.warning(graded) is not None
        in_turn = any(e["turn"] == s["turn"] and e["seq"] < s["seq"] for e in edits)
        since = any(prev < e["seq"] < s["seq"] for e in edits)
        if bad and (in_turn if rule == "v0.1" else since):
            c["would_warn"] += 1
            for g in graded:
                if g["tier"] in "CD":
                    c["warn_type_" + g["type"]] += 1
            nxt = next((r for r in rs if r["seq"] > s["seq"] and r.get("kind") == "test_run"
                        and r.get("exit_code") is not None), None)
            if nxt is not None and (nxt.get("exit_code") or (nxt.get("failed") or 0) > 0):
                c["confirmed_false_green"] += 1
        prev = s["seq"]
    c["test_runs"] += sum(1 for r in rs if r.get("kind") == "test_run")
    c["test_runs_piped"] += sum(1 for r in rs if r.get("kind") == "test_run" and r.get("piped"))
    c["piped_exit0_but_failed"] += sum(1 for r in rs if r.get("kind") == "test_run" and r.get("piped")
                                       and r.get("exit_code") == 0 and (r.get("failed") or 0) > 0)
    c["unparsed_runs"] += sum(1 for r in rs if r.get("kind") == "test_run" and r.get("collected") is None)
    c["bash_code_edits"] += sum(1 for r in rs if r.get("via") == "bash" and r.get("code") and not r.get("is_test"))
    c["tool_code_edits"] += sum(1 for r in rs if r.get("via") == "tool" and r.get("code") and not r.get("is_test"))


def recorded_ids():
    ids = set()
    for d in DATA:
        ids |= {os.path.basename(f)[:-6] for f in glob.glob(os.path.join(d, "sessions", "*.jsonl"))}
    return ids


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--since", default="2026-09-01", help="only sessions active on or after this date (YYYY-MM-DD)")
    ap.add_argument("--until", help="only sessions last active before this date (YYYY-MM-DD)")
    ap.add_argument("--json", help="also write the aggregates (numbers only) to this file")
    args = ap.parse_args()
    since = datetime.datetime.strptime(args.since, "%Y-%m-%d").timestamp()
    until = datetime.datetime.strptime(args.until, "%Y-%m-%d").timestamp() if args.until else None
    recorded = recorded_ids()
    groups = collections.defaultdict(lambda: collections.Counter())
    projects = collections.defaultdict(lambda: collections.Counter())
    skipped = collections.Counter()
    for main_file in sorted(glob.glob(os.path.join(TRANSCRIPTS, "*", "*.jsonl"))):
        if os.path.getmtime(main_file) < since:
            skipped["older than --since"] += 1
            continue
        if until and os.path.getmtime(main_file) >= until:
            skipped["newer than --until"] += 1
            continue
        sid = os.path.basename(main_file)[:-6]
        subs = glob.glob(os.path.join(os.path.dirname(main_file), sid, "subagents", "*.jsonl"))
        recs, stops, meta = replay(sid, [(main_file, False)] + [(s, True) for s in subs])
        if not meta["cwd"] or meta["cwd"].startswith(EXCLUDE_CWD) or meta["project"] in EXCLUDE_PROJECTS:
            skipped["scratch, test or builder session"] += 1
            continue
        if not stops and not recs:
            skipped["empty"] += 1
            continue
        if meta["automation"]:
            period = "automation (SDK runs, temp review workspaces)"
        else:
            period = "before install" if (meta["last"] or 0) < INSTALL else \
                ("after install, recorded by plugin" if sid in recorded else "after install, NOT recorded by plugin")
        for rule in ("v0.1", "v0.2"):
            c = groups[(period, rule)]
            c["sessions"] += 1
            grade(recs, stops, rule, c)
            if not meta["automation"]:
                grade(recs, stops, rule, groups[("all", rule)])
                if rule == "v0.2":
                    grade(recs, stops, rule, projects[meta["project"]])
        if not meta["automation"]:
            groups[("all", "v0.1")]["sessions"] += 1
            groups[("all", "v0.2")]["sessions"] += 1
            projects[meta["project"]]["sessions"] += 1

    print("skipped transcripts:", dict(skipped))
    print("'all' = your interactive sessions (terminal and desktop); automation is listed separately")
    keys = [("sessions", "sessions"), ("turns", "turns"), ("turns with a code edit", "edit_turns"),
            ("  code edits via Edit/Write", "tool_code_edits"), ("  code edits via shell", "bash_code_edits"),
            ("test runs", "test_runs"), ("  unparsed", "unparsed_runs"), ("claims", "claims"),
            ("  tier A", "tier_A"), ("  tier B", "tier_B"), ("  tier C", "tier_C"), ("  tier D", "tier_D"),
            ("claims in edit turns", "edit_claims"), ("  C or D", None), ("would warn (warn mode)", "would_warn"),
            ("  next test run then failed", "confirmed_false_green")]
    for period in ("all", "before install", "after install, recorded by plugin", "after install, NOT recorded by plugin",
                   "automation (SDK runs, temp review workspaces)"):
        a, b = groups[(period, "v0.1")], groups[(period, "v0.2")]
        if not a["sessions"]:
            continue
        print("\n== %s" % period)
        print("  %-30s %8s %8s" % ("", "v0.1", "v0.2"))
        for label, k in keys:
            va = a["edit_tier_C"] + a["edit_tier_D"] if k is None else a[k]
            vb = b["edit_tier_C"] + b["edit_tier_D"] if k is None else b[k]
            print("  %-30s %8d %8d" % (label, va, vb))
        for rule, c in (("v0.1", a), ("v0.2", b)):
            n, bad = c["edit_claims"], c["edit_tier_C"] + c["edit_tier_D"]
            ab = c["tier_A"] + c["tier_B"]
            print("  %s: unsupported in edit turns %s; A/B share of all claims %s" % (
                rule, "%d of %d (%.0f%%)" % (bad, n, 100.0 * bad / n) if n else "n/a",
                "%d of %d (%.0f%%)" % (ab, c["claims"], 100.0 * ab / c["claims"]) if c["claims"] else "n/a"))
    print("\n== by project (v0.2 rule; project = hash of the session's folder)")
    print("  %-8s %8s %8s %10s %8s %8s %10s" % ("project", "sessions", "turns", "edit turns", "claims", "C or D", "would warn"))
    for p, c in sorted(projects.items(), key=lambda kv: -kv[1]["turns"]):
        print("  %-8s %8d %8d %10d %8d %8d %10d" % (p, c["sessions"], c["turns"], c["edit_turns"], c["claims"],
                                                  c["tier_C"] + c["tier_D"], c["would_warn"]))
    if args.json:
        out = {"generated": datetime.datetime.now().isoformat(timespec="seconds"), "since": args.since,
               "skipped": dict(skipped),
               "groups": {"%s | %s" % k: dict(v) for k, v in groups.items()},
               "projects": {k: dict(v) for k, v in projects.items()}}
        with open(os.path.expanduser(args.json), "w") as fh:
            json.dump(out, fh, indent=1, sort_keys=True)
        print("\nwrote", args.json)


if __name__ == "__main__":
    main()
