# Distribution drafts, 2026-10-28

Links carry UTM so visits show in Vercel Analytics (UTM Parameters tab) and reach Calendly through the site's cookie. Scheme: utm_source=github|reddit, utm_medium=comment|post, utm_campaign=codex-hooks, utm_content=<thread>.

## A. openai/codex #34289, "PostToolUse payload carries no failure signal"

Adding a data point from real sessions rather than a probe, on codex-cli 0.163.0, macOS.

I run a small plugin in both Claude Code and Codex that records which files the agent edited and which test commands it ran, then checks each "done" or "tests pass" against that record. In Claude Code the exit code is in the PostToolUse payload, so the rule was "exit code non-zero means the run failed". In Codex that rule made every run look like a pass. For a shell command the hook gets the output text and nothing else. A command that exits with 3 arrives the same as one that exits with 0, as the issue says.

Two more things the same recording showed, in case they help whoever picks this up:

1. Nested calls arrive one by one under Claude-style names. A shell command comes as `Bash` with a `command` field. `apply_patch` comes with the whole patch text in the `command` field and a text response such as "Success. Updated the following files". So a hook can at least learn which files a patch touched, which is the gap the partial-apply comment above describes.
2. Each payload has a `turn_id`, which Claude Code payloads do not, so a shared hook can tell the two agents apart without the transcript.

Workaround I settled on: read pass and fail counts from the output text ("4 passed", "1 failed, 3 passed") and treat a result with no counts as unknown, never as a pass. That recovers test runs but nothing else, so a real exit code or a `PostToolUseFailure` event would still be the fix.

Write-up with the recorded payload shapes: https://serbyn.io/blog/does-codex-cli-have-hooks?utm_source=github&utm_medium=comment&utm_campaign=codex-hooks&utm_content=issue-34289

## B. openai/codex #54960, "Support direct executable hook commands with an args array"

One data point in support, from macOS rather than Windows. Today an `args` list in a command hook is not an error, it is ignored. My hooks.json was written for Claude Code with `"command": "python3"` and `"args": ["script.py"]`. In Codex every hook ran a bare `python3` with stdin from the payload, exited after reading it, and recorded nothing. `/hooks` listed the hooks as trusted and nothing warned. I only found it by recording the payloads. The fix on my side was to put the whole command into one string. An exec form with a real argument vector, as proposed here, would make that class of silent failure impossible. Until then, a warning when `args` is present would already save people a day.

Notes on what the Codex payloads contain: https://serbyn.io/blog/does-codex-cli-have-hooks?utm_source=github&utm_medium=comment&utm_campaign=codex-hooks&utm_content=issue-54960

## C. openai/codex #21753, "Full Claude Code Hook Parity" (optional, umbrella thread)

For the "every hook payload is stable, typed and documented" row, here is what a shared hooks.json saw on codex-cli 0.163.0 compared with Claude Code, recorded on real sessions:

- Shell commands arrive as `Bash` with `command` and the output text. No exit code, no failure field (#34289).
- `apply_patch` arrives with the patch text in `command`, not as a structured list of files.
- Every payload carries a `turn_id`; Claude Code payloads do not.
- An `args` list on a command hook is ignored without a warning (#54960).
- Hooks stay off until confirmed in the app, and that can happen in the middle of a turn, so the first events of a session can be missing.

None of these are blockers once you know them, but each one cost a day to find. A documented payload per event would remove all five. Recorded shapes: https://serbyn.io/blog/does-codex-cli-have-hooks?utm_source=github&utm_medium=comment&utm_campaign=codex-hooks&utm_content=issue-21753

## D. Reddit post, r/codex (fallback r/ChatGPTCoding)

Title: Does Codex CLI have hooks? I recorded what the payloads actually contain

Body:

Short answer: yes. The same hooks.json that works in Claude Code works in Codex, with four events: SessionStart, UserPromptSubmit, PostToolUse and Stop. I run a small plugin in both agents that records what the agent edited and ran, so I had a reason to record the payloads. Three differences matter if you share hooks between the two.

A shell command arrives as `Bash` with the output text and nothing else. No exit code. A command that exits with 3 looks the same as one that exits with 0, so a hook that reads pass or fail from the exit code sees every Codex run as a pass.

`apply_patch` arrives with the whole patch in the `command` field. You can still learn which files changed, you just have to read the patch.

An `args` list in the hook config is ignored with no warning. A hook written as `command: python3` plus `args: [script.py]` runs a bare `python3` and records nothing. Put the whole command in one string.

The write-up with the recorded shapes and the hooks.json that works in both: https://serbyn.io/blog/does-codex-cli-have-hooks?utm_source=reddit&utm_medium=post&utm_campaign=codex-hooks&utm_content=r-codex

Happy to answer questions about what else the payloads contain.
