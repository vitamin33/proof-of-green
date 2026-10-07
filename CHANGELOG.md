# Changelog

## 0.2.0 (candidate on branch `v0.2`, not installed; the observe week runs 0.1.2)

- Edits made through the shell count as code edits (DECISIONS.md D6). This covers `>` / `>>` into a code file (also `cat > f <<EOF`), `tee`, `sed -i` and `perl -i` on a code file, `git apply` / `patch`, and a python/node/ruby/perl heredoc script that writes a code file. The target is taken from `open(..., "w")`, `Path(...).write_text` or `writeFileSync`, with simple variable resolution. Edit and Write rules still apply: inside the project, not a test, not a doc. When one command both edits and runs tests, the order in the command decides which came first.
- Warn condition: a code edit since the previous Stop, instead of in this turn (DECISIONS.md D1). Work by a background subagent that comes back as a new prompt now counts.
- Parser: pytest `-q` summary without the `====` banner, pytest "Interrupted: N errors during collection", and node:test summaries echoed onto one line.
- Checked offline against the observe week's real commands with `analysis/observe_week.py --v02` (22 sessions, 96 claims). Shell writes into code files: 136, plus 31 patches. Tiers moved from A 23 / B 42 / C 14 / D 17 to A 10 / B 27 / C 43 / D 16. Would-warn cases in warn mode went from 3 to 15. Whether those 15 are fair still needs a manual check.
## 0.1.3 (2026-10-07, report only)

- `/proof-of-green:report` shows the session you run it in (via `${CLAUDE_SESSION_ID}`). Before, it showed whichever session file was written last, often another session.
- If the current session has no record, the report says so and how to fix it: the session most likely started before the plugin was installed or updated, so restart it with `claude --resume <id>`.
- The report reads every proof-of-green data folder. Desktop-app sessions write to `proof-of-green-inline` and terminal sessions to `proof-of-green-proof-of-green`, so `--all` now covers both.
- Data collection is unchanged.

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
