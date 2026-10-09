# Decisions

Each item changes what a turn, a session or a code edit means. Decided 2026-10-02: D1 agreed but waits for the end of the observe week, D2 done, D3 to D6 kept as they are. Evidence comes from headless runs on 2026-10-02 (Claude Code 2.1.287) with a probe plugin that logged event names, ids and payload field names only.

## D1. A background subagent's result starts a new "turn"

Seen: the parent launched a general-purpose subagent and stopped (Stop #1, no claim) before the subagent edited `calc.py`. The subagent's Edit arrived with the parent's `session_id` plus `agent_id` and `agent_type`, so the ledger recorded it under the parent at turn 1. Then the result came back as a second `UserPromptSubmit` (`prompt_len` 906, no field marks it as synthetic). That made turn 2. The parent replied "Done. All tests pass." The verdict was tier D for both claims, but `acted: false` in warn mode, because the rule "≥1 code edit in this turn" looked at turn 2.

Effect: a missed warning (never a wrong one).

Options:
1. Keep as is. Document that background subagent work can slip past the warning.
2. Change the warn condition from "a code edit in this turn" to "a code edit since the previous Stop".
3. Keep turns, but do not count a `UserPromptSubmit` as a turn boundary while a subagent started after the last Stop has not reached `SubagentStop`.

My suggestion: 2. It is one line, it needs no new event, and it covers this case.

**Decision (2026-10-02): option 2 agreed in principle. Not implemented until the observe week ends.** Update 2026-10-07: implemented on branch `v0.2` (not installed). The week's data will be scored under both rules: "a code edit in this turn" (current) and "a code edit since the previous Stop" (option 2). Both can be computed from the ledger afterwards, because every record carries its `turn` and `seq`. To make option 2 computable, every Stop now leaves a record: a `verdict` when the reply has a claim, a `stop` record otherwise. This is data only and does not change when a warning fires.

## D2. Store `agent_id` on records from subagents

Subagent tool calls carry `agent_id` and `agent_type`. The ledger drops them now. Storing them would let the report say "3 of 5 edits came from subagents". This is data only. Tiers would not change. It needs `SubagentStart`/`SubagentStop` only if we also want to show start and stop.

**Decision: yes. Done:** `edit` and `test_run`/`other` records from a subagent carry `agent_id`. Start and stop events are not recorded.

## D3. `/clear` and `--fork-session` start an empty ledger

Seen: `/clear` fires `SessionEnd` (`reason: clear`), then `SessionStart` (`source: clear`) with a new `session_id`. `--resume <id> --fork-session` also gets a new `session_id` (`source: fork`). Each new id gets a new ledger file. Edits from before are not carried over, so a claim right after `/clear` about earlier work falls under "zero code edits in the session" and never warns.

Options:
1. Keep. Simple, and it matches what Claude itself still knows after a clear.
2. Carry the last code edit and the test runs after it into the new file when `source` is `clear` or `fork`. For `clear` there is no link back to the old id in the payload. Matching by cwd and time would be a guess.

My suggestion: 1. For fork the old id is known (it was passed with `--resume`), but hooks do not see it.

**Decision: keep as is.**

## D4. Resume and compact continue the same ledger

Seen: `--resume <id>` and `--continue` keep the `session_id` (`source: resume`). `/compact` keeps it too: `PreCompact` (`trigger: manual`), then `SessionStart` (`source: compact`). The ledger appends a `session` record each time, and turns and the last code edit carry on.

Current behaviour seems right: a test run before compaction still counts, and an edit before a resume still makes later claims checkable. No change proposed. Written down so it is a decision and not an accident.

**Decision: keep as is.**

## D5. Edits inside a worktree folder under the project

An Edit to `<project>/.claude/worktrees/<name>/src/a.py` is inside the session's start folder, so it counts as a code edit. A worktree outside the project (`git worktree add ../wt`) does not count. And the classification always uses the folder from the first `session` record, even if later payloads report another `cwd`. The commands themselves (`git worktree add/remove`, `git stash`, `git checkout`, `git restore`) never count, which is tested.

Question: should edits under `.claude/worktrees/` count? Counting them is right when Claude works there on purpose. Not counting them is right when the main checkout is what gets tested.

**Decision: keep as is.** Since 0.1.0 the ledger stores a hash of the start folder instead of its path. Classification walks up the edited file's folders and compares hashes, which gives the same result.

## D6. Edits made through Bash do not count

`sed -i`, `cat > file`, `patch`, `python - <<EOF` that writes files: none of these create an edit record, because only Edit, Write and MultiEdit hooks record edits. So a session where Claude edits only through Bash never warns. The README states this. Detecting it would mean guessing from command text.

**Decision: keep for v0.** Listed in LATER.md as a known blind spot. Update 2026-10-07: implemented on branch `v0.2` after the interim analysis showed it was the largest source of error. Under the old rule 65 of 95 claims were A/B; counting shell writes into code files, 36 to 37 are.

## D7. Deploys that do not use a deploy CLI (proposal, 2026-10-08)

Seen in the warning review (two samples of 27 would-warn cases each): 5 of the 54 cases claim "deployed" after `gh pr merge` (the merge triggers the deploy) or `docker compose up -d` / `docker compose build` on the host that serves the app. The DEPLOY list only knows platform CLIs (vercel, fly, firebase, kubectl, …), so those claims get "no deploy command in this session".

Proposal: count `docker compose up` (without `--dry-run`), `docker compose build` followed by `up`, and `gh pr merge` as deploy commands. Risk: a merge does not always deploy, and a local `docker compose up` is not production. Alternative: leave `deployed` out of warnings until it can be checked better.

**Decision (2026-10-09): no change.** `deployed` claims are recorded and shown in the report, never warned on.

## D8. "verified" and "done" about work that is not code (proposal, 2026-10-08)

Seen in the same review: in about 10 of 54 cases the claim is about something tests cannot show. The agent checked a document, a data analysis, a rendered video, a message draft or a research result, or "done" closes a task list. The turn also touched a code file, so the claim is graded against test runs and the warning is unfair.

Options: (a) warn on `verified` and `done` only when the same reply also names tests, a build or code behaviour; (b) never warn on `verified`, still record it; (c) keep as is and accept the noise. (a) is a claim-pattern change; (b) is simpler.

**Decision (2026-10-09): option (b).** `verified` and `done` are recorded and shown in the report, never warned on.

## D9. One-off scripts are not code edits (proposal, 2026-10-08)

After the parser fixes, the biggest remaining source of unfair warnings is the code-edit side. Of the 20 unfair cases in the second sample, 12 have a "code edit" that is a one-off script or a note, not a change to the product. Examples: `cat > private/jobs/…/verify.py`, `cat > private/maintenance/apply.py`, a scratch file in a temp folder, a handoff note, or an edit that `git checkout --` later reverted. Two plain bugs behind some of them are fixed on `v0.2` (see CHANGELOG): the word "patch" in text, and heredoc bodies read as shell.

Proposal: a file the project's git ignores (`git check-ignore`) is not a code edit. `private/`, `tmp/` and run folders are usually ignored; product code never is. One `git check-ignore` call per edited file, with a short timeout, failing open (treated as code). Reverts stay out of scope.

**Decision (2026-10-09): not implemented.** The plugin is frozen (see below); one-off scripts still count as code edits in the data, and the report says so.

## D10. Freeze at 0.2.0: observe and report only (2026-10-09)

The history study (`analysis/claim_study.py`, `analysis/hidden_failures.py`, `analysis/baseline_cost.py`) found no real false "tests pass" claim in about 2,070 claims from Claude Code and Codex: every case that looked false on paper was a deliberate red run (mutation check, new test written to fail first, old code), a failure the agent then fixed, or a failure that was already there before the change. Two hand-checked samples of would-warn cases had 2 of 25 and 1 of 21 fair warnings. A warning with that precision breaks the "never annoys" rule.

**Decision:** 0.2.0 ships with the v0.2 parser and Codex fixes, `observe` stays the default, no new warning rules. The plugin records and reports; it does not speak. Warn mode stays available but is not recommended.

## Not a decision, but you asked for it

In the 2.1.287 CLI code, plugin options are set through `/plugin configure <plugin>` (also `/plugin` → plugin → "Configure options"), `claude plugin configure <plugin> --values-stdin` and `claude plugin install … --config KEY=VALUE`. I found no sign of them in `/config`, but I did not open `/config` to check. README and INSTALL.md describe the `/plugin configure` route.
