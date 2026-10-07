"""Plain-text summary of the ledger for /proof-of-green:report."""
import glob
import os
from collections import Counter

from . import bashparse, ledger, tiers


def data_dirs(explicit=None):
    """Every proof-of-green data folder. Desktop-app sessions write to `-inline`, terminal ones to
    `-<marketplace>`, so one report has to look in all of them."""
    if explicit and not explicit.startswith("${"):
        return [explicit]
    dirs = ([ledger.data_dir()] if ledger.data_dir() else []) + \
        sorted(glob.glob(os.path.expanduser("~/.claude/plugins/data/proof-of-green*")))
    out = []
    for d in dirs:
        if os.path.realpath(d) not in [os.path.realpath(x) for x in out]:
            out.append(d)
    return out


def find_data_dir(explicit=None):
    """Kept for callers that need one folder: the one written most recently."""
    dirs = data_dirs(explicit)
    return max(dirs, key=_newest, default=None)


def _newest(path):
    files = glob.glob(os.path.join(path, "sessions", "*.jsonl"))
    return max([os.path.getmtime(f) for f in files] + [0])


def project_of(records):
    """Short project id for a session. Old ledgers stored the path; it is hashed here, never shown."""
    for r in records:
        if r.get("kind") == "session":
            if r.get("project"):
                return r["project"][:6]
            if r.get("cwd"):
                return ledger.project_hash(r["cwd"])[:6]
    return "------"


def unparsed_prefix(command):
    _, seg = bashparse.detect_runner(command or "")
    return " ".join((seg or command or "?").split()[:2])


def summarize(sessions):
    """sessions: list of (session_name, records). Returns dict of numbers."""
    s = {"sessions": len(sessions), "turns": 0, "edit_turns": 0, "edit_turns_no_claim": 0,
         "claims": Counter(), "tiers": Counter(), "warnings": 0, "flags": Counter(), "examples": [],
         "unparsed": Counter(), "projects": Counter()}
    for name, records in sessions:
        project = project_of(records)
        s["projects"][project] += 1
        s["turns"] += ledger.current_turn(records)
        edit_turns = {r.get("turn") for r in tiers.code_edits(records)}
        claim_turns = set()
        for r in records:
            if r.get("kind") == "test_run":
                s["flags"].update(r.get("flags") or [])
                if r.get("collected") is None:
                    s["unparsed"][unparsed_prefix(r.get("command"))] += 1
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
                    s["examples"].append((project, name, r.get("turn"), c.get("type"), c.get("tier")))
        s["edit_turns"] += len(edit_turns)
        s["edit_turns_no_claim"] += len(edit_turns - claim_turns)
    return s


def render(s, label):
    pct = (100.0 * s["edit_turns_no_claim"] / s["edit_turns"]) if s["edit_turns"] else 0.0
    claims = ", ".join("%s %d" % (k, v) for k, v in sorted(s["claims"].items())) or "none"
    tier_line = "  ".join("%s %d" % (t, s["tiers"].get(t, 0)) for t in "ABCD")
    flags = ", ".join("%s ×%d" % kv for kv in s["flags"].most_common()) or "none"
    unparsed = ", ".join("%s ×%d" % kv for kv in s["unparsed"].most_common(3)) or "none"
    lines = [
        "proof-of-green report — %s" % label,
        "",
        "turns with code edits      %d of %d" % (s["edit_turns"], s["turns"]),
        "claims by type             %s" % claims,
        "evidence tiers             %s" % tier_line,
        "warnings issued            %d" % s["warnings"],
        "edit turns with no claim   %.0f%%" % pct,
        "suspicious test flags      %d (%s)" % (sum(s["flags"].values()), flags),
        "unparsed test runs         %d (%s)" % (sum(s["unparsed"].values()), unparsed),
        "",
        "stale / unsupported claims (latest 3):",
    ]
    examples = s["examples"][-3:]
    for project, name, turn, ctype, tier in examples:
        where = "turn %s" % turn if s["sessions"] == 1 else "project %s session %s turn %s" % (project, name[:8], turn)
        lines.append("  %s  %s  tier %s" % (where, ctype, tier))
    if not examples:
        lines.append("  none")
    lines += ["", "A full run after last edit · B partial run · C only before last edit · D none/failed/masked"]
    return "\n".join(lines)


def _arg(argv, name):
    if name in argv and argv.index(name) + 1 < len(argv):
        value = argv[argv.index(name) + 1]
        return None if value.startswith("${") or value.startswith("-") else value
    return None


def main(argv):
    dirs = data_dirs(_arg(argv, "--data"))
    session = _arg(argv, "--session")
    files = sorted((f for d in dirs for f in glob.glob(os.path.join(d, "sessions", "*.jsonl"))),
                   key=os.path.getmtime)
    folders = ", ".join(ledger.home_to_tilde(d) for d in dirs) or "~/.claude/plugins/data/proof-of-green-*"
    if "--all" not in argv and session:
        files = [f for f in files if os.path.basename(f) == session + ".jsonl"]
        if not files:
            print("proof-of-green: this session (%s) has no record. It most likely started before the plugin "
                  "was installed or updated, so its hooks are not loaded. Restart it: /exit, then "
                  "claude --resume %s\nData folders checked: %s" % (session[:8], session, folders))
            return 0
    elif "--all" not in argv:
        files = files[-1:]
    if not files:
        print("proof-of-green: no sessions recorded yet. Data folders: %s" % folders)
        return 0
    sessions = [(os.path.basename(f)[:-6], ledger.read(f)) for f in files]
    summary = summarize(sessions)
    ids = {name for name, _ in sessions}
    if len(ids) > 1:
        label = "%d sessions in %d projects (%s)" % (len(ids), len(summary["projects"]), ", ".join(
            "%s ×%d" % kv for kv in summary["projects"].most_common()))
    else:
        label = "session %s, project %s" % (sessions[0][0][:8], project_of(sessions[-1][1]))
        if len(files) > 1:
            label += " (recorded in %d data folders)" % len(files)
    print(render(summary, label))
    used = sorted({os.path.dirname(os.path.dirname(f)) for f in files})
    print("data: %s" % ", ".join(ledger.home_to_tilde(d) for d in used))
    return 0
