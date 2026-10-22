# Audit: what your team's coding agents claimed, and what they ran

In one week of my own Claude Code and Codex sessions the agents wrote "done", "fixed" or "tests pass" 1,227 times. For 448 of those there was no test run after the last code change. When I read 46 such cases by hand, 3 held up as a real problem. The rest were fine: the agent had checked in a way the rule did not see, or the claim was about a document or data.

That is one engineer, with a strict review process around the agents. I do not know what the numbers look like for a team of 5 to 20 developers without that process. This audit is how to find out on your own machines, without sending me anything but counts.

## What you get

One block of numbers per developer, like this one from my own history:

```
proof-of-green audit, local history since 2026-10-04 (counts only, nothing uploaded)

  Claude Code    sessions   51  turns  4144  edit turns  505  claims  588  no fresh test run  294 (50%)  would warn  52  then failed   2
  Codex          sessions   27  turns  1120  edit turns  249  claims  639  no fresh test run  154 (24%)  would warn  63  then failed  11

  claims with no test run after the last code edit: 448 of 1227 (37%)
  would-warn cases: 115; of those, the next test run on the same code failed: 13
  test runs: 6403, output not parsed: 3851 (60%)
```

Send me the blocks and you get back a one-page read. It says how your team compares with my baseline and which agent and which kind of claim carry the risk. And whether a check at the moment of "done" would pay for itself for you. Open an issue in this repository with the blocks, or use the contact form on serbyn.io.

## What it reads, and what leaves the machine

Claude Code and Codex already keep a log of every session on the developer's laptop: `~/.claude/projects` and `~/.codex/sessions`. The audit reads those files and nothing else. It needs Python 3.9 or newer and no other packages. Tested on macOS and Linux. Windows is untested.

Nothing is uploaded. The script makes no network calls. The block above is the whole output: counts and short hashes of project folders. No prompt, no reply, no command, no file name and no code appears in it. You can read the script before you run it, it is one file, `analysis/audit.py`, plus the two it calls.

## How to run it

Each developer runs this on their own machine:

```
git clone https://github.com/vitamin33/proof-of-green
cd proof-of-green
python3 analysis/audit.py --since 2026-09-01 --out audit.txt
```

Two months of history take under a minute. `audit.txt` is the block to send. Pick `--since` so that it covers at least a few hundred claims, otherwise the percentages jump around.

## How to read the block

Every line is a count from the agent's own actions. Here is what each means.

"Edit turns" are the replies in which the agent changed code. Test files and docs do not count.

"Claims" are replies that end with "done", "fixed", "verified", "deployed" or "tests pass", in English or Ukrainian. The detection is strict on purpose. In a sample of 30 it found a real claim 26 times, so a few wrong hits are in the count.

"No fresh test run" means that after the agent's last code change in that stretch of work, no test command ran. This is only a flag. In my history about 1 in 15 such flags survived a hand check. The usual reasons a flag was wrong: the agent ran tests in a way the parser did not recognise. Or the claim was about a document or data. Or the "code change" was a throwaway script.

"Would warn" is the subset where the plugin, in warn mode, would have shown the agent a one-line notice.

"Then failed" is the strict signal. The agent claimed, and the next test run on the same code failed. Read those cases by hand before you draw a conclusion. In my history most of them were runs that were meant to fail, like a mutation check or a new test written to fail first.

"Output not parsed" tells you how much the tool could not read. Test runners print results in many formats, and a run the parser cannot read counts as unknown, never as a pass.

## What it does not show

It does not judge test quality. A weak suite that passes counts as a pass.

It misses claims phrased in other ways, and it misses checks done outside the session, in CI or by a reviewer.

It does not know what reached production. A claim with no test run can still be correct, and a passing run can still ship a bug.

And it is one rule applied to logs. The block tells you where to look. It does not tell you what you will find there.

## Where the numbers above come from

All the scripts, the decisions and the week's review are in this repository. The audit uses `analysis/backfill.py` and `analysis/backfill_codex.py`. The hand checks are described in `docs/REVIEW-week1.md`. Every number in this page exists in a file you can rerun.
