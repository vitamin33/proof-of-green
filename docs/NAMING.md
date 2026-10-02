# Naming

Plugin names cannot change after publish. Checked on 2026-10-02.

Sources: `gh search repos "<name>"` and `gh search repos "<name> claude"`; the official directory list in `anthropics/claude-plugins-official/.claude-plugin/marketplace.json` (315 plugins, grepped for each name and for the stems green, proof, claim, receipt, done, verif, evidence, prove); `gh search code "<name>" --repo anthropics/claude-plugins-official`; claude.com/plugins (only about 24 featured plugins render, no search endpoint); web search; `https://pypi.org/pypi/<name>/json` and `https://registry.npmjs.org/<name>` (200 = taken).

| name | GitHub | official directory | PyPI / npm | verdict |
|---|---|---|---|---|
| `falsegreen` (first working name) | vinicq/falsegreen (3★) "Find false-green tests", plus -js, -docs, -skill (an LLM skill) and robotframework- variants | no | PyPI taken (vinicq) / npm free | Risky. Same name, close concept, existing LLM skill under it |
| `proof-of-green` (**chosen**) | nothing relevant | no | free / free | Clean |
| `done-check` | nothing relevant | no | free / free | Clean but generic, does not say "tests" |
| `show-your-work` | allenai/show-your-work (18★, a paper) | no exact match; Gotcha plugin and athola's proof-of-work skill pitch the same idea | free / free | Usable, long |
| `claimcheck` | metareflection/claimcheck (29★), CatNebulaaaa/ClaimCheck-Skill (47★, a Claude skill) | no | taken / taken | Avoid |
| `receipts` | chrishutchinson/claude-receipts (628★) | **yes**, an official `receipts` plugin exists | taken / taken | Blocked |

Also checked: `prove-it` collides with searlsco/prove_it (198★, "The verification harness that Claude Code should have shipped with"), a direct competitor. `greencheck` has PyPI taken.

## Decision

Renamed to `proof-of-green` on 2026-10-02, before any publish. The plugin is `proof-of-green`, the command is `/proof-of-green:report`, the data folder is `~/.claude/plugins/data/proof-of-green-<marketplace>/` and the Python package is `proof_of_green` (Python names cannot hold hyphens). "False green" stays as the name of the problem in the README, not of the product.

Re-check the table right before submitting: a name can be taken between now and then.

## Same space, for positioning

prove_it (198★), Gotcha, dod-guard (npm, a "Definition of Done" checker for Claude Code), athola's proof-of-work skill, synrail and stopproof all target "agent says done without proof". proof-of-green's angle: it checks the claim against what the session actually ran, after the last edit, and stays quiet otherwise.
