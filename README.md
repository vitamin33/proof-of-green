# falsegreen

falsegreen tells you when Claude says "tests pass", "done" or "fixed" but did not run the tests after its last code change.

```
Claude:      Fixed the add bug. All tests pass.
falsegreen:  claim 'tests pass' — no test run after your last edit (last run: before edit, 1 failed)
Claude:      Ran python3 -m unittest after the fix: 2 passed, 0 failed.
```

That is a real run on a small test repo, shortened. Claude ran the tests, saw 1 failure, fixed the code and said everything passes without running them again. The prompt told it to skip the second run, to set up the trap. falsegreen showed one line, Claude ran the tests, and this time they really passed.

## Install

```
/plugin install falsegreen@claude-plugins-official
```

Or from a clone: `claude --plugin-dir /path/to/falsegreen`. You need `python3` 3.9 or newer. On macOS it comes with the Xcode command line tools.

## How it works

Hooks write down what happens in the session: which files Claude edited, which test commands it ran, the exit code and the pass and fail counts. When Claude finishes a reply, falsegreen looks for a claim in it ("all tests pass", "fixed", "готово", "тести проходять") and checks the claim against that record.

It speaks only when all of this is true:

- the reply has a claim
- Claude edited code (not tests or docs) in this turn
- after the last code edit there was no test run, or the last run failed, ran 0 tests, or hid the exit code with something like `|| true`

Then you get one line, and Claude gets a short request to run the full test command and show the result. If nothing is wrong, you see nothing.

## What it does not do

Nothing leaves your machine. There are no network calls and no telemetry.

It never opens the conversation transcript. It sees hook events and the text of Claude's final reply, and it keeps only parsed facts: the command, the exit code, the counts. Raw tool output and your prompt text are never stored.

It never blocks Claude from stopping. When a claim has no proof, Claude gets one request to run the tests. That happens at most once per reply.

Test quality is out of scope. A weak suite that passes still counts as a pass.

And it misses some false claims on purpose. Claim detection is tuned so a wrong warning is rare, and the price is that some real claims slip through.

## Settings

Set these in `/plugin` under falsegreen.

- `mode`: `warn` (default) or `observe`. In observe mode it only records and never shows anything.
- `test_command`: your project's full test command, for example `make ci`. A run that contains it counts as a full run.

## Reading /falsegreen:report

```
/falsegreen:report          the latest session
/falsegreen:report --all    every session recorded
```

Example output:

```
turns with code edits      6 of 9
claims by type             done 2, fixed 3, tests_pass 4
evidence tiers             A 4  B 2  C 1  D 2
warnings issued            2
edit turns with no claim   33%
suspicious test flags      1 (|| true ×1)
```

Each claim gets a tier from what happened after the last code edit.

- A: the full test suite ran and passed.
- B: only some tests ran (a single file, `-k`, `--filter`) and they passed. That is enough for "fixed" and "done", and partial proof for "all tests pass".
- C: tests ran, but only before the last edit, so the result is out of date.
- D: no test run, the last run failed, it ran 0 tests, or its exit code was masked.

C and D are the claims worth a second look. "Edit turns with no claim" is how often Claude changed code and said nothing about whether it works. The last lines list turn numbers, so you can scroll back and see what happened.

## Team report (paid, coming)

If you want the same numbers across a team, per repo and per week, I am building a paid team report. The plugin itself stays free and complete without it. Details and early access: https://serbyn.io/falsegreen?utm_source=github&utm_medium=readme

## Privacy and your data

Everything is stored in the plugin's own data folder, one JSONL file per session:

```
~/.claude/plugins/data/falsegreen-<marketplace>/sessions/<session_id>.jsonl
~/.claude/plugins/data/falsegreen-<marketplace>/errors.log
```

`/falsegreen:report` prints the exact folder on its last line. To delete everything, delete that folder. Uninstalling the plugin also removes it.

## License

MIT
