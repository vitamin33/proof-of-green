# Naming

Plugin names cannot change after publish. Checked on 2026-10-02.

Sources: `gh search repos "<name>"` and `gh search repos "<name> claude"`; the official directory list in `anthropics/claude-plugins-official/.claude-plugin/marketplace.json` (315 plugins, grepped for each name and for the stems green, proof, claim, receipt, done, verif, evidence, prove); `gh search code "<name>" --repo anthropics/claude-plugins-official`; claude.com/plugins (only about 24 featured plugins render, no search endpoint); web search; `https://pypi.org/pypi/<name>/json` and `https://registry.npmjs.org/<name>` (200 = taken).

| name | GitHub | official directory | PyPI / npm | verdict |
|---|---|---|---|---|
| `falsegreen` (current) | vinicq/falsegreen (3★) "Find false-green tests", plus -js, -docs, -skill (an LLM skill) and robotframework- variants | no | PyPI taken (vinicq) / npm free | Risky. Same name, close concept, existing LLM skill under it |
| `proof-of-green` | nothing relevant | no | free / free | Clean. Recommended |
| `done-check` | nothing relevant | no | free / free | Clean but generic, does not say "tests" |
| `show-your-work` | allenai/show-your-work (18★, a paper) | no exact match; Gotcha plugin and athola's proof-of-work skill pitch the same idea | free / free | Usable, long |
| `claimcheck` | metareflection/claimcheck (29★), CatNebulaaaa/ClaimCheck-Skill (47★, a Claude skill) | no | taken / taken | Avoid |
| `receipts` | chrishutchinson/claude-receipts (628★) | **yes**, an official `receipts` plugin exists | taken / taken | Blocked |

Also checked: `prove-it` collides with searlsco/prove_it (198★, "The verification harness that Claude Code should have shipped with"), a direct competitor. `greencheck` has PyPI taken.

## Decision needed before publish

The repo and plugin are built as `falsegreen`. If you pick `proof-of-green`, the rename touches `.claude-plugin/plugin.json` (`name`, URLs), `commands/report.md` is unaffected (the command becomes `/proof-of-green:report`), the `falsegreen*` glob in `falsegreen/report.py`, the README and the warning prefix in `falsegreen/tiers.py`. The Python package name can stay; it is never published.

## Same space, for positioning

prove_it (198★), Gotcha, dod-guard (npm, a "Definition of Done" checker for Claude Code), athola's proof-of-work skill, synrail and stopproof all target "agent says done without proof". falsegreen's angle: it checks the claim against what the session actually ran, after the last edit, and stays quiet otherwise.
