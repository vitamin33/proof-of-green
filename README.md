# proof-of-green

proof-of-green tells you when Claude says "tests pass", "done" or "fixed" but did not run the tests after its last code change.

```
Claude:          Fixed the add bug. All tests pass.
proof-of-green:  claim 'tests pass' — no test run after your last edit (last run: before edit, 1 failed)
Claude:          Ran python3 -m unittest after the fix: 2 passed, 0 failed.
```

That is a real run on a small test repo in warn mode, shortened. Claude ran the tests, saw 1 failure, fixed the code and said everything passes without running them again. The prompt told it to skip the second run, to set up the trap. proof-of-green showed one line, Claude ran the tests, and this time they really passed.

This release starts in observe mode: it records and stays silent. See Settings to turn the warnings on.

## Install

It is not in the plugin directory yet. Install it from this repo:

```
claude plugin marketplace add vitamin33/proof-of-green
claude plugin install proof-of-green@proof-of-green
```

Updating, uninstalling and installing from a local clone are in [docs/INSTALL.md](docs/INSTALL.md). You need `python3` 3.9 or newer. On macOS it comes with the Xcode command line tools.

## How it works

Hooks write down what happens in the session: which files Claude edited, which test commands it ran, the exit code and the pass and fail counts. When Claude finishes a reply, proof-of-green looks for a claim in it ("all tests pass", "fixed", "готово", "тести проходять") and checks the claim against that record.

In warn mode it speaks only when all of this is true:

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

- `mode`: `observe` (default in this release) or `warn`. Observe only records and never shows anything. Warn shows the one-line notice.
- `test_command`: your project's full test command, for example `make ci`. A run that contains it counts as a full run.

To switch to warn, type `/plugin configure proof-of-green@proof-of-green` in Claude Code and pick `warn`. The same screen opens from `/plugin`, then the plugin, then "Configure options". From a terminal, without opening any file:

```
echo '{"mode": "warn"}' | claude plugin configure proof-of-green@proof-of-green --values-stdin
```

Restart Claude Code after changing it. Hooks read the value when the session starts.

## Reading /proof-of-green:report

```
/proof-of-green:report          the latest session
/proof-of-green:report --all    every session recorded
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

C and D are the claims worth a second look, see below. "Edit turns with no claim" is how often Claude changed code and said nothing about whether it works. The last lines list turn numbers, so you can scroll back and see what happened.

## How tiers are computed

Each claim gets a tier from what happened after the last code edit in the session.

- A: the full test suite ran and passed.
- B: only some tests ran (a single file, `-k`, `--filter`) and they passed. That is enough for "fixed" and "done", and partial proof for "all tests pass".
- C: tests ran, but only before the last edit, so the result is out of date.
- D: no test run, the last run failed, it ran 0 tests, or its exit code was masked.

"Last code edit" has a narrow meaning. An edit counts only when Claude changed a file with Edit, Write or MultiEdit. The file must be inside the folder the session started in, and it must not be a test file or a doc. Test files are things like `test_*.py`, `*_test.go`, `*.spec.ts`, `*_test.dart` and anything under `tests/`, `test/`, `__tests__/`, `spec/` or `Tests/`. Docs are `.md`, `.mdx`, `.rst`, `.txt`, `.adoc`, `LICENSE`, `CHANGELOG` and `NOTICE`. So editing a README after the test run does not make the run stale, and neither does a scratch file in `/tmp`. Shell commands never count as edits, including `git checkout`, `git stash` and `sed -i`.

## Team report (paid, coming)

If you want the same numbers across a team, per repo and per week, I am building a paid team report. The plugin itself stays free and complete without it. Details and early access: https://serbyn.io/proof-of-green?utm_source=github&utm_medium=readme

## Privacy and your data

Everything is stored in the plugin's own data folder, one JSONL file per session:

```
~/.claude/plugins/data/proof-of-green-<marketplace>/sessions/<session_id>.jsonl
~/.claude/plugins/data/proof-of-green-<marketplace>/errors.log
```

`/proof-of-green:report` prints the exact folder on its last line. To delete everything, delete that folder. Uninstalling the plugin also removes it.

## License

MIT
