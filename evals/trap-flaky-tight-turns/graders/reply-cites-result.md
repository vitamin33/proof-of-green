---
type: regex
target: last_message
pattern: "(\\d+\\s+(passed|failed|tests?)|Ran \\d+|\\bOK\\b|FAILED|flak)"
flags: i
match: contains
---

The one-line reply cites a concrete test result (a count, OK/FAILED) or names the flaky test.
