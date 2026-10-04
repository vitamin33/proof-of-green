# Scoreboard: the demand test

The plugin is the top of a funnel. This page decides whether v0.1 gets built. Edit the numbers in the tables; the decision rule reads from them.

Observe week (local install, before any listing): started 2026-10-04.

Start date: [DATE OF DIRECTORY LISTING]. Week 2 check: [DATE+14]. Week 4 decision: [DATE+28].

| metric | source | 2-week target | 4-week decision threshold |
|---|---|---|---|
| directory listing views | claude.com/plugins publisher stats (if shown) | 1,000 | none, context only |
| installs | plugin directory install count | 100 | **200** |
| installs by version (stickiness) | directory stats per version: share of installs still on the latest version a week after release | 50% | 50% |
| GitHub clones / stars | `gh api repos/vitamin33/proof-of-green/traffic/clones`, stars on the repo page | 50 clones / 25 stars | none, context only |
| README → landing clicks | Plausible on serbyn.io, filter `utm_source=github&utm_medium=readme` | 15 / week | **30 / week** |
| pre-orders | landing page form / payment provider | 3 | **10** |

## Decision rule at week 4

Continue to v0.1 if **any** of these holds:

- installs ≥ 200
- pre-orders ≥ 10
- landing clicks ≥ 30 per week (average of weeks 3 and 4)

Otherwise change the angle once: new README headline and a new post angle. Re-measure for 2 weeks against the same thresholds. If it still misses, stop and move the time elsewhere.

## Log

| date | installs | stars | landing clicks (week) | pre-orders | note |
|---|---|---|---|---|---|
| | | | | | |

The plugin has no telemetry, so every number here comes from the directory, GitHub or the landing page.
