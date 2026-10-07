#!/usr/bin/env python3
"""Score the review file: warning precision by agent and claim type. Prints counts only."""
import collections
import os
import re
import sys

path = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "~/research/pog-data/review/warnings-sample.md")
text = open(path, encoding="utf-8").read()
cases = re.split(r"\n## W\d\d  ", text)[1:]
c = collections.Counter()
for case in cases:
    agent = case.split(" · ")[0].strip()
    verdict = (re.search(r"^VERDICT:\s*(\w+|\?)", case, re.M) or [None, "?"])[1].lower()
    first = re.search(r"Claims: (.+)", case).group(1)
    worst = next((m.group(1) for m in re.finditer(r"(\w+) \(tier ([CD])\)", first)), "?")
    c[(agent, verdict)] += 1
    c[("type:" + worst, verdict)] += 1
for group in sorted({k[0] for k in c}):
    fair, unfair, unsure, todo = (c[(group, v)] for v in ("fair", "unfair", "unsure", "?"))
    judged = fair + unfair
    print("%-22s fair %2d  unfair %2d  unsure %2d  not judged %2d  precision %s" % (
        group, fair, unfair, unsure, todo, "%.0f%%" % (100.0 * fair / judged) if judged else "n/a"))
