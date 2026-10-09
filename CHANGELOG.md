# Changelog

## 0.2.0 (2026-10-09, frozen: observe and report only)

- Released from branch `v0.2`. No warning rules were added after the history study (DECISIONS.md D7 to D10): `observe` stays the default and warn mode is not recommended.
- Analysis scripts for the study: `analysis/claim_study.py` (each claim labelled by the next test run on unchanged code), `analysis/hidden_failures.py` (runs with failures in the output but exit code 0), `analysis/baseline_cost.py` (time and tokens agents spend re-running tests on the old code).

- Edits made through the shell count as code edits (DECISIONS.md D6). This covers `>` / `>>` into a code file (also `cat > f <<EOF`), `tee`, `sed -i` and `perl -i` on a code file, `git apply` / `patch`, and a python/node/ruby/perl heredoc script that writes a code file. The target is taken from `open(..., "w")`, `Path(...).write_text` or `writeFileSync`, with simple variable resolution. Edit and Write rules still apply: inside the project, not a test, not a doc. When one command both edits and runs tests, the order in the command decides which came first.
- Warn condition: a code edit since the previous Stop, instead of in this turn (DECISIONS.md D1). Work by a background subagent that comes back as a new prompt now counts.
- Pipe-masked exit codes. When a test command is piped into another command without `pipefail` (`npm test | tail -20`, `pytest | grep -c FAIL`), the exit code belongs to the last command. Such runs are now judged by the counts in the output only: failures shown means failed, clean counts means passed, no counts means "result not visible" (B at most, with that reason). The report shows how many runs were masked. In the Claude Code history 3,925 of 4,510 test runs were piped this way. 60 of them had been marked failed only because of `grep`'s or `tail`'s exit code.
- Codex support. `hooks.json` now uses the shell form (`"command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/x.py\""`). Codex runs only `command` and ignores an `args` list, so under 0.1.x every hook in Codex ran a bare `python3` and recorded nothing. A new PostToolUse group covers Codex tool names (`exec_command`, `shell`, `apply_patch`, code-mode `exec`), read by `proof_of_green/codex.py`. The report also reads `~/.codex/plugins/data/proof-of-green*`. Checked live in Claude Code. Not yet checked live in Codex: that needs the hooks trusted again in the Codex app.
- Parser: pytest `-q` summary without the `====` banner, pytest "Interrupted: N errors during collection", and node:test summaries echoed onto one line.
- Test runners found missing in the warning review (2026-10-08): `python -B -m unittest` and other interpreter flags before `-m`, a test file run directly (`python3 tools/test_x.py`, partial scope), project wrappers such as `./scripts/node.sh npm test`, `npm run verify` / `npm run e2e` (unknown scope), and `playwright test`. For unittest and pytest a named module now means partial scope; only build tools (gradle, maven, make, xcodebuild, fastlane) treat a `test…` word as the task name.
- Shell edit detection (D6) no longer reads text as commands. Heredoc bodies are data, so `> x.py` inside one is not a write. `patch` and `git apply` count only as the command itself, not as a word in a heredoc or commit message, and `git apply --check` / `--stat` only read. In the Codex history this removed 365 false code edits.
- Codex: a command whose `cmd` string contains `})` (a heredoc with JavaScript in it) was dropped; about 5,000 commands in the Codex history were lost this way. Results are now paired with calls in order, including `write_stdin` polls, so a test run that was still going when its call returned gets its real result from the later poll and counts from where it started. Before, the backfill marked such runs `run_in_background` (tier D) and the hook counted them as unknown.
- If no prompt was ever recorded (Codex starts the hooks mid-turn once they are approved), a claim is recorded but not graded or warned on; the report lists it as "not graded". The report's turn count includes turn 0, so it no longer says "1 of 0".
- Warning review, two samples of 27 would-warn cases from the history, judged by Claude, not by the user: precision 2 of 25 judged before these fixes, 1 of 21 after the runner fixes. The rest is in DECISIONS.md D7 to D9. Would-warn cases in the history (since 2024): Claude Code 222 → 155, Codex 153 → 65.
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
