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

## Not a decision, but you asked for it

In the 2.1.287 CLI code, plugin options are set through `/plugin configure <plugin>` (also `/plugin` → plugin → "Configure options"), `claude plugin configure <plugin> --values-stdin` and `claude plugin install … --config KEY=VALUE`. I found no sign of them in `/config`, but I did not open `/config` to check. README and INSTALL.md describe the `/plugin configure` route.
