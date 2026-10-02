"""Plain-text summary of the ledger for /falsegreen:report."""
import glob
import os
from collections import Counter

from . import ledger, tiers


def find_data_dir(explicit=None):
    if explicit and not explicit.startswith("${"):
        return explicit
    if ledger.data_dir():
        return ledger.data_dir()
    # The command's Bash call may not inherit CLAUDE_PLUGIN_DATA; look where Claude Code keeps it.
    candidates = glob.glob(os.path.expanduser("~/.claude/plugins/data/falsegreen*"))
    return max(candidates, key=_newest, default=None)


def _newest(path):
    files = glob.glob(os.path.join(path, "sessions", "*.jsonl"))
    return max([os.path.getmtime(f) for f in files] + [0])


def summarize(sessions):
    """sessions: list of (session_name, records). Returns dict of numbers."""
    s = {"sessions": len(sessions), "turns": 0, "edit_turns": 0, "edit_turns_no_claim": 0,
         "claims": Counter(), "tiers": Counter(), "warnings": 0, "flags": Counter(), "examples": []}
    for name, records in sessions:
        s["turns"] += ledger.current_turn(records)
        edit_turns = {r.get("turn") for r in tiers.code_edits(records)}
        claim_turns = set()
        for r in records:
            if r.get("kind") == "test_run":
                s["flags"].update(r.get("flags") or [])
            if r.get("kind") != "verdict":
                continue
            if r.get("acted"):
                s["warnings"] += 1
            if r.get("claims"):
                claim_turns.add(r.get("turn"))
            for c in r.get("claims") or []:
                s["claims"][c.get("type")] += 1
                s["tiers"][c.get("tier")] += 1
                if c.get("tier") in ("C", "D") and r.get("turn") in edit_turns:
                    s["examples"].append((name, r.get("turn"), c.get("type"), c.get("tier")))
        s["edit_turns"] += len(edit_turns)
        s["edit_turns_no_claim"] += len(edit_turns - claim_turns)
    return s


def render(s, label):
    pct = (100.0 * s["edit_turns_no_claim"] / s["edit_turns"]) if s["edit_turns"] else 0.0
    claims = ", ".join("%s %d" % (k, v) for k, v in sorted(s["claims"].items())) or "none"
    tier_line = "  ".join("%s %d" % (t, s["tiers"].get(t, 0)) for t in "ABCD")
    flags = ", ".join("%s ×%d" % kv for kv in s["flags"].most_common()) or "none"
    lines = [
        "falsegreen report — %s" % label,
        "",
        "turns with code edits      %d of %d" % (s["edit_turns"], s["turns"]),
        "claims by type             %s" % claims,
        "evidence tiers             %s" % tier_line,
        "warnings issued            %d" % s["warnings"],
        "edit turns with no claim   %.0f%%" % pct,
        "suspicious test flags      %d (%s)" % (sum(s["flags"].values()), flags),
        "",
        "stale / unsupported claims (latest 3):",
    ]
    examples = s["examples"][-3:]
    for name, turn, ctype, tier in examples:
        where = "turn %s" % turn if s["sessions"] == 1 else "session %s turn %s" % (name[:8], turn)
        lines.append("  %s  %s  tier %s" % (where, ctype, tier))
    if not examples:
        lines.append("  none")
    lines += ["", "A full run after last edit · B partial run · C only before last edit · D none/failed/masked"]
    return "\n".join(lines)


def main(argv):
    data = None
    if "--data" in argv and argv.index("--data") + 1 < len(argv):
        data = argv[argv.index("--data") + 1]
    base = find_data_dir(data)
    files = sorted(glob.glob(os.path.join(base, "sessions", "*.jsonl")), key=os.path.getmtime) if base else []
    if not files:
        print("falsegreen: no sessions recorded yet. Data folder: %s" % (base or "~/.claude/plugins/data/falsegreen-*"))
        return 0
    if "--all" not in argv:
        files = files[-1:]
    sessions = [(os.path.basename(f)[:-6], ledger.read(f)) for f in files]
    label = "%d sessions" % len(files) if len(files) > 1 else "session %s" % sessions[0][0][:8]
    print(render(summarize(sessions), label))
    print("data: %s" % base)
    return 0
