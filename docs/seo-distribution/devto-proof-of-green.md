---
title: "I built a tool to catch agents saying \"tests pass\" without proof. It was wrong 43 times out of 46."
published: false
description: "A Claude Code and Codex plugin flagged a third of my agents' done claims as unverified. Read one by one, 3 of 46 flags held up. What the week measured, where the rule fails, and what is worth keeping."
tags: ai, claudecode, testing, agents
canonical_url: https://serbyn.io/blog/proof-of-green-checks-every-done
---

*proof-of-green · observe week 2026-10-04 to 10-11 · Claude Code and Codex*

In one week my coding agents wrote "done", "fixed" or "tests pass" 948 times. A rule I wrote flagged 315 of those as unverified: no test run after the agent's last code change. Then the flagged cases were read one by one, with the full session open. 3 of 46 held up.

So the tool I built to catch agents lying about tests mostly caught itself being wrong. I think that result is more useful than the one I expected, and this post is about why.

## The short version

**What I built:** a plugin that records what the agent edits and runs, and checks each "done" against that record. Nothing leaves the machine. It never blocks the agent.

**What the week measured:** 948 claims, 315 flagged, 3 of 46 flags real after a hand check. The stricter check on two months of history found no real false green either.

**Why the rule fails:** half the time the tests did run and the rule did not recognise the command. A quarter of the time the claim was about a document or data, where a test run is the wrong proof.

**What stays:** the record. The warning does not.

## Why I wanted the number

A false green is a success message with nothing behind it. The agent says "all tests pass" and no test passed after its last change. I have written about this before in my own pipelines, and every time the fix was a check that the agent could not skip.

What I did not have was a rate. How often does an agent in normal work say "done" without proof? Everyone has a story. I did not have a count from my own sessions. So I built the counter first and let it run for a week on my real work. Two client projects and a few of my own, with Claude Code and Codex.

## What the plugin does

Claude Code and Codex run small scripts at fixed points in a session. The plugin listens to four of those points. Three only write facts down: which file changed, which test command ran, its exit code and its pass and fail counts. The fourth runs when the agent finishes a reply. It looks for a claim in the reply and checks it against the record.

*Figure (see the diagram in the original post): The record is one file per session with parsed facts only. Raw output and prompt text are never stored. The check runs at the end of a reply. In observe mode it only records the verdict. In warn mode it shows one line and asks the agent once to rerun the tests.*

The rule is simple on purpose. A test run counts as proof only if it ran after the last change to code. Code means a file inside the project that is not a test and not a doc. The same claim gets a different grade depending on what happened after that change.

*Figure (see the diagram in the original post): Same claim, same failing run before the edit, four endings. A full passing run after the edit is A, a partial one is B, no run is C, a failed or hidden run is D. The rule flags C and D.*

I ran it in observe mode for the whole week. It recorded and said nothing. Then I replayed the week's transcripts through the same rules, because the plugin had missed sessions that started before it was installed.

## What came out

*Figure (see the diagram in the original post): 948 claims, 315 flagged, 46 read with the full session open, 3 real. The 46 were sampled from two months of flags, across both agents and all grades, so the week's 315 would not get a different answer.*

Three of 46. Before the hand check, the rule-based number looked like a headline: a third of completion claims with no fresh test run. After it, the headline is that the rule is right about 1 time in 15.

The three real ones were ordinary. The agent changed code after its last green run and wrote "done" without running again, or wrote "tests pass" while the last run in front of it showed failures. The other 43 broke down like this.

*Figure (see the diagram in the original post): In 22 of 43 cases the tests ran and the rule did not see them: a test file run directly with python, a project wrapper script around npm test, a runner piped through grep. In 12 the claim was about a document, a data check or a review. The rest were throwaway scripts counted as code, deploys done through a merge or docker compose, and runs that were meant to fail.*

I fixed the parser for the first group and sampled again. The second sample came back at 1 of 21. Then the same 20 cases were read a second time with the complete turn in front of the reader, and the count went to 0, with 2 unsure. The fixes moved the wrong flags from one bucket to another. They did not find more real ones.

## The stricter check found the same thing

A flag says "no proof". It does not say "wrong". So I also looked for claims that were wrong on the face of it. The agent says "tests pass", nothing changes, and the next test run on the same code fails.

Over two months of history, with about 2,070 claims, that happened 5 times out of 52 cases where the next run was known. All 5 were read with the session open. Each was a run that was supposed to fail. A mutation check that breaks the code on purpose, a new test written to fail first, a run against an old copy of the code. None reached a commit, a merge or a deploy. No message from me afterwards said anything was broken.

One more angle. In 684 test runs the output showed failures while the exit code said 0, usually because the command was piped into `tail` or `grep`. That looked like a real hiding place. 40 of them, the ones followed by a claim, were read. 0 were hidden false greens. The agent had read the output and said so, or the failures were there before the change and the agent had checked that on the main branch.

## What the hooks could not see

The biggest surprise was where the work happens.

*Figure (see the diagram in the original post): Two months of Claude Code history. 67% of code edits came through shell commands such as `sed -i`, `cat > file` or a Python script writing the file, which the first version did not count as edits. 56% of test runs printed in a form the parser could not read, so they counted as unknown, never as a pass.*

Codex added one more. It sends the hook the command's output and nothing else. No exit code. A command that exits with 3 arrives looking like any other. The plugin now judges Codex runs by the counts in the output, and says "not visible" when there are none.

## What this does not show

The hand checks were done by Claude, the same model that writes most of the replies being judged. I have not yet gone through the 46 myself. Until I do, 3 of 46 means "about 1 in 15" and nothing more exact.

The week is one engineer's work. Around my agents there is a review step, a mutation check and a merge check that runs the tests again. A false claim rarely gets far here, so the rate I measured is a rate for a guarded setup. A team with agents and no tests would get a different picture. The tool could not help them either way, because it needs test runs to have anything to check.

Autonomous runs, where no one reads the replies, gave 7 sessions and 0 claims. I cannot say whether the problem is bigger there.

And the claim detection itself is right 26 times out of 30. A few of the 948 were not claims at all.

## What a team can do on Monday

Pick a recent session from one of your agents and find its last "tests pass". Look for a test run after the last code edit. If there is none, read what the agent did instead. In my sessions the answer was usually a run the rule could not read. That is a parser bug.

If you lead a team on coding agents, the same audit runs on each developer's laptop in under a minute and prints counts only. The script and what the numbers mean are in `docs/AUDIT.md` in the repository. I would like to see the same block from a team that works without a review step around its agents. Open an issue in the repository or use the contact form on this site.

**Is the tool useless, then?** As a warning, yes, at 1 fair flag in 15. As a record of what the agent ran before it said "done", it does what I wanted and it costs nothing. It stays installed in observe mode.

**Why not fix the parser until the flags are right?** I did, twice. Each round moved wrong flags into another bucket. The claims that are not about code and the throwaway scripts are not parser problems.

**Did the agents lie?** Not in any case that was read. They skipped a rerun a few times. The word "lie" was my guess before I had the data, and the data does not support it.

**Would warn mode have helped the 3 real cases?** Probably. A one-line reminder to rerun is cheap. But it would have fired 43 other times that week, and I would have uninstalled it.

The lesson I keep from this. A rule that looks obvious on a whiteboard, "no test after the edit means no proof", was right in 1 case out of 15 on real sessions. The cheap way to learn that was to run it silently for a week before letting it speak. I would do the silent week again for any check I put in front of an agent.

The check for your own system this week: take one agent session, find the last "done", and count the test runs after the last code edit. Then read the ones the count missed.

Repository and raw numbers: `github.com/vitamin33/proof-of-green`, `docs/REVIEW-week1.md` and `analysis/`. Earlier posts in the false-green series: [Six False-Greens in a Self-Auditing Agent Pipeline](https://serbyn.io/blog/six-false-greens-in-a-self-auditing-agent-pipeline), [The Check the Agent Cannot Skip](https://serbyn.io/blog/enforced-checkpoint-0-of-40-silent-failures-vs-22-of-40).

*Originally published at [serbyn.io](https://serbyn.io/blog/proof-of-green-checks-every-done).*
