#!/usr/bin/env python3
"""Sample claims with the sentence that matched, for a manual check of the claim patterns.

Replays Claude Code and Codex sessions since --since, grades every claim with the v0.2 rules,
draws --n claims spread over tiers A-D (fixed seed), and writes them with the matched sentence
to a private file (mode 600). Prints counts only. Mark each `VERDICT:` line `real` (the agent
says it finished this kind of work), `false` (the pattern fired on something else), or `unsure`.
"""
import argparse
import collections
import datetime
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "analysis"))
import backfill  # noqa: E402
import claim_study  # noqa: E402
from proof_of_green import claims, tiers  # noqa: E402

backfill.KEEP_DETAIL = True


def matched_sentence(message, ctype):
    rxs = [rx for t, rx in claims.COMPILED if t == ctype]
    for s in claims.sentences(message):
        if not claims._skip(s) and any(rx.search(s) for rx in rxs):
            return s.strip()
    return ""


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--since", default="2026-10-04")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--out", default="~/research/pog-data/review/claim-sample.md")
    args = ap.parse_args()
    since = datetime.datetime.strptime(args.since, "%Y-%m-%d").timestamp()
    pool = []
    for gen in (claim_study.claude_sessions(since), claim_study.codex_sessions(since)):
        for agent, project, recs, stops, _ in gen:
            for s in stops:
                if (s.get("ts") or 0) < since:
                    continue
                upto = [r for r in recs if r["seq"] < s["seq"]]
                for cl in s.get("claims") or []:
                    tier, reason = tiers.evidence(upto, cl["type"])
                    pool.append((tier, agent, cl["type"], reason, matched_sentence(s.get("message") or "", cl["type"])))
    by = collections.defaultdict(list)
    for p in pool:
        by[p[0]].append(p)
    random.seed(17)
    pick, per = [], args.n // 4
    for t in "ABCD":
        pick += random.sample(by[t], min(per, len(by[t])))
    rest = [p for p in pool if p not in pick]
    pick += random.sample(rest, args.n - len(pick))
    path = os.path.expanduser(args.out)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        for i, (tier, agent, ctype, reason, sent) in enumerate(pick, 1):
            fh.write("## C%02d %s · %s · tier %s\n%s\n\nreason: %s\n\nVERDICT: ?\n\n" % (i, agent, ctype, tier, sent[:400], reason))
    print("claims in pool: %d %s; sampled %d -> %s (mode 600)" % (
        len(pool), dict(collections.Counter(p[0] for p in pool)), len(pick), args.out))


if __name__ == "__main__":
    main()
