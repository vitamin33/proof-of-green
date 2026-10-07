---
description: Show how often completion claims in this session (or all sessions with --all) were backed by a test run after the last edit. Also tells you if this session is not being recorded.
argument-hint: "[--all]"
allowed-tools: Bash(python3:*)
---

Run this command with the Bash tool, passing through the arguments `$ARGUMENTS` (empty or `--all`):

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/report.py" --session "${CLAUDE_SESSION_ID}" $ARGUMENTS
```

Show its output verbatim inside a code block. Do not summarize, interpret or add commentary.
