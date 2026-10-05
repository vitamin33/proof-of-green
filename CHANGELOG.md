# Changelog

## 0.1.2 (2026-10-05, completes the 0.1.1 parser fix)

- node:test results filtered down to `# pass N` and `# fail N` (no `# tests` line) are now counted as pass + fail. The Vitelle sessions often use `grep -E "^# (pass|fail)"`. Re-parsing that session's real outputs locally: 0.1.0 counted 0 of 14 test runs, 0.1.1 counted 4, 0.1.2 counts 12. The other 2 print no summary at all.
- A lone `# pass` or `# fail` line, or bare `ok` / `not ok` lines, still stay unknown.

## 0.1.1 (2026-10-05, mid-observe-week parser fix)

- Parse node:test results: the TAP summary (`# tests / # pass / # fail / # cancelled`) and the spec reporter (`ℹ tests …`). This also works when the output is piped through `grep` for those lines, as in the Vitelle sessions. Before this, such runs were stored with `collected = null` and could reach tier B at most.
- Recognize `node --test` as a test runner (`--test-name-pattern` or file arguments make it partial).
- Tiers, claim patterns and what counts as a code edit are unchanged.

## 0.1.0 (unreleased, observe-week build)

First version. Runs in observe mode by default.

- Hooks for SessionStart, UserPromptSubmit, PostToolUse / PostToolUseFailure (Edit, Write, MultiEdit, Bash) and Stop. Python 3.9+ standard library only. Every hook fails open.
- Per-session JSONL ledger in `${CLAUDE_PLUGIN_DATA}/sessions/`. `seq` and `turn` are read from the last line under an exclusive lock.
- Claim detection for tests_pass, done, fixed, verified and deployed, in English and Ukrainian. The corpus is 53 positive and 54 negative examples.
- Evidence tiers A to D measured from the last code edit. A code edit is an Edit, Write or MultiEdit on a non-test, non-doc file inside the session's start folder.
- Test runner parsing for pytest, unittest, npm/pnpm/yarn/bun test (incl. `test:*` and `pnpm -r`), vitest, jest, go, cargo, flutter, dart, dotnet, gradle, maven, make test/check, xcodebuild, swift, fastlane test/scan, rspec and phpunit.
- `mode` option: `observe` (default) or `warn`. Warn shows one line and asks Claude once to run the full test command. Never blocks.
- `test_command` option to mark the project's full test command.
- `/proof-of-green:report [--all]`: tiers, warnings, edit turns with no claim, suspicious flags, unparsed test runs with their top 3 command prefixes, and stale claims by turn. Projects are shown by hash.
- Privacy: no network calls, no transcript reading, no raw output stored. Each project is stored as a hash of its folder. Edited files are stored relative to the project, or as `(outside project)`. In commands, paths outside the project become `<path>`. Secrets are redacted (`-p`/`--password` unless the value is an existing path, `token=`, credential URLs, secret env vars, bearer tokens, known key prefixes).
- Subagent records carry `agent_id`. Every Stop without a claim leaves a `stop` record, so the D1 rule can be scored after the observe week.
- The repo is its own marketplace: `claude plugin install proof-of-green@proof-of-green`.
