# LinkedIn: Featured link and post for the proof-of-green write-up

Link: https://serbyn.io/blog/proof-of-green-checks-every-done

## Featured link, three options (title / description)

1. My agents said "done" 948 times in a week. 3 of 46 flagged claims were a real problem. / What a silent week of recording Claude Code and Codex showed, and why the warning rule failed.

2. I built a false-green detector. It was wrong 43 times out of 46. / The counts, the reasons the rule failed, and the one part worth keeping.

3. How often does a coding agent say "tests pass" without proof? I counted. / One week, two agents, 948 claims, 3 confirmed. The numbers and the blind spots.

## Post text

In one week my coding agents wrote "done", "fixed" or "tests pass" 948 times.

A rule I wrote flagged 315 of those: no test run after the last code change.

Then the flagged cases were read one by one, with the full session open. 3 of 46 held up.

Half of the wrong flags were tests that did run, in a form the parser could not read. A quarter were claims about a document or data, where a test run is the wrong proof.

The tool stays installed in observe mode. The warning does not. The record of what the agent ran before it said "done" is the part that was worth building.

The write-up has the counts, the reasons the rule failed, and a one-command audit a team can run on its own laptops: https://serbyn.io/blog/proof-of-green-checks-every-done

#ClaudeCode #AIAgents
