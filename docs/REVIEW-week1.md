# Go / no-go review after the observe week (2026-10-04 to 2026-10-11)

Project types are inferred from the folders behind each hash (client: 0be0e3, e97509, eb5d09; autonomous: sessions started by the SDK or `codex exec`; personal: the rest; excluded: 8499de plugin repo, 7a063d test fixture). Correct the mapping in `analysis/week_review.py` if any is wrong.

Hand verdicts below were made by Claude, not by Vitalii. That is a limit on every precision number in this file.

## Sources

| | Command | Covers |
|---|---|---|
| S1 | `python3 analysis/week_review.py` | live ledgers copied to `~/research/pog-data/sessions` |
| S2 | `python3 analysis/backfill.py --since 2026-10-04` | same week, Claude Code transcripts, v0.2 rules |
| S3 | `python3 analysis/backfill_codex.py --since 2026-10-04` | same week, Codex rollouts |
| S4 | `python3 analysis/claim_sample.py` + verdicts in `review/claim-sample.md` | 30 claims, matched sentence |
| S5 | `python3 analysis/score_review.py <warnings-sample.md / -2.md>` | two samples of would-warn cases |
| S6 | `python3 analysis/claim_study.py --since 2024-01-01` / `--since 2026-10-04` | claims labelled by the next test run |
| S7 | `python3 analysis/hidden_failures.py` | runs with failures but exit 0 |

## Part 1. What the week showed

**1. Volume (S1).** 100 sessions, 1,628 turns, 111 turns with code edits, 219 graded claims: tests_pass 42, fixed 60, done 33, verified 75, deployed 9. By type: client 22 sessions / 165 claims, personal 71 / 54, autonomous 7 / 0. The transcripts hold more than the ledger saw: 336 claims in Claude Code (S2) and 612 in Codex (S3) for the same week.

n: S1 gives C+D = 99 of 219 = 45%, 95% CI ±7 points. ±10 points needs 96 claims if claims were independent, 2 to 3 times that because they cluster by session. So the C+D share is measured well enough. The number that matters, the share of flags that are fair (item 4), rests on 46 hand-checked cases.

**2. Tiers (S1).** Overall A 26, B 94, C 36, D 63. Client A 26 / B 70 / C 21 / D 48 (C+D 42%); personal A 0 / B 24 / C 15 / D 15 (56%); autonomous: no claims. Retro, same week, v0.2 rules: Claude Code A 18 / B 152 / C 65 / D 101 (49% C+D, S2); Codex A 33 / B 430 / C 130 / D 19 (24%, S3); together 315 of 948 (33%).

**3. Headline candidates.**
- C+D share, 45% (S1). Not defensible as "unsupported claims". It counts claims with no test run after the last code edit, and hand checks show those are mostly fine (item 4).
- tests_pass contradicted by a failed run: 3 of 42 (S1). On the stricter label (next run on unchanged code failed): 2 of 18 this week, 5 of 52 over two months (S6). Read by hand, the two-month cases were all deliberate red runs, other repos or environment errors. In S7, 0 of 40 sampled hidden failures were real false greens. Not defensible as a lie rate.
- Edit turns with no claim: 86 of 111 = 77% (S1). Defensible as a description: most turns that change code do not end with "done" or "tests pass".

**4. Detector honesty.** Claim patterns (S4): 26 of 30 matched sentences are real completion claims, precision 0.87 (Wilson 95% CI 0.70 to 0.95). The 4 false hits were a past event, descriptive text, another person's CI, and another agent's work. 5 of the 26 real claims are about non-code work (data, review, text), where a test run is the wrong evidence. Warning precision (S5): 2 fair of 25 judged, then 1 of 21 after parser fixes. That is 3 of 46, about 7% (CI 2% to 18%). Below 0.9 on both counts: no headline number is publishable yet.

**5. Trust in the week's data.**
- D1 (S1): would warn 17 under "edit this turn", 21 under "edit since last stop". Retro: 8 vs 32 (S2), 15 vs 61 (S3).
- Unparsed runs: 217 of 410 (53%, S1).
- errors.log is empty. 6 of 100 sessions have no `session` record.
- Three plugin versions wrote the week (0.1.2/0.1.3, then 0.2.0 from 10-09). Before 0.2.0 shell edits were invisible.
- Codex records before 2026-10-11 missed every `apply_patch` and assumed exit 0 (fixed in 0.2.1). So the ledger under-counts edits, which biases tiers toward A/B. Use S2/S3 for the week, not S1 tiers.

## Part 2. Who would pay (all HYPOTHESIS)

| | Buyer | Paid artefact | Why not build it in an evening | Budget line | Kill test, ≤ 2 weeks, no calls |
|---|---|---|---|---|---|
| H1 | AI engineers, Claude Code power users | none | they can | none | Directory listing + post. GitHub traffic (no telemetry): fewer than 20 unique cloners or 0 voluntarily shared `report --all` outputs kills it as a channel |
| H2 | Eng lead, 5–20 devs on coding agents | weekly team report of what agents claimed vs ran | needs parsers for two agents, calibration, upkeep | dev tooling / AI tooling seats | Lead-angle post + form "one-page report from your team's sessions, runs locally". Fewer than 5 requests from leads with ≥5 devs kills it |
| H3 | Regulated teams (IEC 62304, SOC 2, EU AI Act) | signed export of the agent action log | auditor-acceptable format, tamper evidence | compliance / QA | Post to regulated-industry engineers + form. Fewer than 3 replies from regulated orgs kills it. Reach via current channels is weak |
| H4 | Non-technical founders told "done" | report via their dev agency | not in Claude Code at all | outsourcing budget | Not reachable directly; ask 5 agencies in DMs if they would show it to clients. 0 yes kills it |
| H5 | Mobile/Flutter teams | H2 with device checks | — | — | Own data: the mobile project has 323 shell commands, 11 test runs, 3 device/build/e2e commands (one-off count over transcripts). n too small. Treat as H2 until another team's data says otherwise |

Rank: (pain × pay × reach). H2 first: reachable on LinkedIn, plausible budget, pain unproven. H3 has the best ability to pay but the weakest reach. H1 does not pay, H4 cannot be reached, H5 is H2. Test H2 first because it is the only one where the post itself is the test.

## Part 3. "Anyone can build this in an evening"

The objection holds for the code. Hooks, a regex list, a JSONL ledger and a report are an evening's work.

Not reproducible in an evening:
- two months of claims across two agents labelled by what happened next (S2, S3, S6);
- measured precision (0.87 for claims, about 7% for warnings);
- Codex payload quirks found only by live capture: no exit codes, nested calls sent as `Bash` and `apply_patch`;
- the negative result itself;
- upkeep as hook formats change. Codex changed format inside this week.

The defensible asset is the data and the author's position, not the code. HYPOTHESIS: pricing follows the service or recurring report, not a tool. Kill test: the H2 form. If requests ask "can I just install it", it is a free tool. If they ask "can you look at ours", it is a service.

## Part 4. Thesis

**1. Mapping.**
- (a) Agents claim completion without fresh evidence often enough to matter. Contradicted in its strong form. Claims without a run after the last edit are common (45%), but hand-read cases show almost no real false greens, and none reached a commit, merge or deploy (S6).
- (b) Detectable deterministically from actions alone. Partly. The actions are recorded reliably. Claim extraction is 0.87, but turning that into a correct "unsupported" verdict is about 7%.
- (c) Untested: observe mode only, no intervention ran.
- (d) Autonomous vs hands-on: untested. The ledger has 7 autonomous sessions and 0 claims. Client vs personal C+D (42% vs 56%) is the only split, and it may reflect project type, not supervision.

**2. Why C+D is high but real false greens are rare: competing explanations.**
1. The harness already verifies (mutation checks, review gates, merge gates). Separate it: run the same audit on another team's sessions or on own projects without gates; compare the fair-flag rate.
2. The detector misses differently phrased claims (recall). Separate it: read 50 Stop messages with no detected claim and count missed completion claims.
3. These models rarely false-green. Separate it: same audit on other engineers' sessions with other setups.
4. The label is blind. A failure that shows up later in CI or production never reaches the next local test run. Separate it: link claims to reverts or fix commits on the same files within 48 h (git history is local).

**3. Post #1.** First draft: "Agents claim 'done' without evidence in 45% of my sessions." Hostile senior engineer:
- "n = 1 engineer with an unusual harness."
- "45% of what? A claim with no test run after the edit is not a false claim."
- "Who checked the checks? Your own model graded your own detector."

The 45% gets attacked, and it should be.

Rewrite that survives: "I checked 948 completion claims from one week of my own Claude Code and Codex sessions against what the agents ran. A rule-based check flagged 315 of them (a third) as unverified. When I read 46 flagged cases from the last two months one by one, 3 held up."

Angles:
- For engineers: "what my agent did when I wasn't looking". The data supports this well: it is one engineer's sessions, read closely.
- For leads: "what you can't see in your team's sessions". Not supported yet: there is no team data.

**4. Orientation.**
- Detection ("catching lies") is not supported: 3 of 46 flags fair.
- "Cost of unverified done" is not supported: no rework found; manual baseline checks cost 0.8 h of test time and 0.2% of output tokens over two months (`python3 analysis/baseline_cost.py`).
- "Evidence trail" is what the plugin does reliably today (S1: 100 sessions recorded, errors.log empty).

The data point that decides it: would a team lead or auditor ask for the trail (H2/H3 test). The week does not contain it.

## Part 5. Verdict and missing data

**PIVOT.** The detector is not the product. The fact that drives it: 3 of 46 hand-checked warnings were fair (S5), while the claim patterns themselves are right 26 of 30 times (S4). The idea fails at "unsupported", not at "claim". Keep the recorder and the measurement. Stop investing in warnings. Test the evidence-trail / team-report angle.

**Missing data:**
1. Other people's sessions: 3 to 5 engineers run `analysis/backfill.py` and `claim_sample.py` locally and share counts only. Get it in 2 weeks through the post and DMs. Flips the verdict toward detection if their fair-flag rate is 30% or higher.
2. Human verdicts: Vitalii re-judges 20 of the 46 flags. 1 hour. Flips if he finds 30% or more fair (Claude's judging was wrong).
3. Downstream outcome: reverts or fix commits on the same files within 48 h of "done" claims, from local git. 1 day. Flips toward "cost of unverified done" if 10% or more of done/fixed claims are followed by such a fix.

**Post #1 claims:** "In one week of my own Claude Code and Codex sessions, a rule-based check flagged a third of 948 completion claims as unverified (S2, S3), and only 3 of 46 flags read by hand held up (S5)."

**It must NOT claim:**
- a rate of agent lying or false greens;
- anything about teams, autonomous pipelines or other models;
- that the plugin catches lies;
- that the hand check was independent.

**Warn mode:** no. Precision is about 7% against a 0.9 bar. Do not list in the directory as a warning tool. If listed, list as an observe-and-report recorder, and decide after missing data item 1 (2 weeks).
