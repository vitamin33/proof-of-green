# Later (not in v0)

Cut on purpose. Each item waits for the demand test in SCOREBOARD.md.

From the v0 brief:

- Block mode (`decision: "block"` until evidence exists).
- Proof-test: run the tests ourselves instead of asking Claude.
- Test-weakening detection (deleted asserts, `skip` added, expected values changed to match).
- Skills, subagents, MCP server.
- Telemetry of any kind. The scoreboard uses directory, GitHub and landing numbers only.
- Landing page, and a "machine" for many plugins.
- `/proof-of-green:report --purge`. v0 documents the folder to delete instead.

Found while building v0:

- Known blind spot: edits made through Bash (`sed -i`, `cat > file <<EOF`, `python - <<EOF` that writes files, `patch`) never count as code edits, so a session where the agent edits only that way never warns. Kept for v0 (DECISIONS.md D6).
- Warn condition "a code edit in this turn" misses work by background subagents, whose result starts a new turn. Agreed fix after the observe week: "a code edit since the previous Stop" (DECISIONS.md D1).

- Background test runs. `run_in_background` is flagged as suspicious because the result arrives later through another tool. Reading that tool's result would turn many D tiers into A.
- Model per session. The SessionStart payload in Claude Code 2.1.287 has no `model` field, so the ledger stores `null`.
- Matching claim scope to run scope. "test_login passes" is graded against any run, not a run that includes test_login.
- Hedged claims. "This should fix it" counts as a claim; "this might fix it" does not. Worth checking against real sessions.
- Ledger size. Each hook reads the whole session file (about 50 ms per hook at 1,000 records). A very long session may need a small state file or a tail read.
- Windows. Locking uses `fcntl`; on Windows appends still work but `seq` can repeat under concurrent subagents.
- `marketplace.json` in the repo, so people can install from GitHub before the directory listing.
