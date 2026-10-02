# Install

The repo is its own plugin marketplace (`.claude-plugin/marketplace.json`). The marketplace is called `proof-of-green` and holds one plugin, also called `proof-of-green`, so the install id is `proof-of-green@proof-of-green`.

## Install

From GitHub:

```bash
claude plugin marketplace add vitamin33/proof-of-green
claude plugin install proof-of-green@proof-of-green
```

From a local clone:

```bash
git clone https://github.com/vitamin33/proof-of-green ~/src/proof-of-green
claude plugin marketplace add ~/src/proof-of-green
claude plugin install proof-of-green@proof-of-green
```

Use a clean clone for a local install. Claude Code copies the folder as it is into its plugin cache, including git-ignored files. A dev folder with a `.venv/` made the copy 28 MB. The tracked files alone are about 300 KB.

Both commands default to user scope, so the plugin runs in every project. To try it in one project only, run both commands from that project with `--scope local`.

The install prints `2 userConfig options not yet set`. That is expected. Unset means observe mode and no `test_command`.

Restart Claude Code after installing.

## Turn on warnings

This release starts in observe mode. To switch to warn, inside Claude Code:

```
/plugin configure proof-of-green@proof-of-green
```

Or from a terminal:

```bash
echo '{"mode": "warn"}' | claude plugin configure proof-of-green@proof-of-green --values-stdin
```

Back to observe: the same command with `"observe"`. Restart Claude Code after the change.

## Update after a git pull

Claude Code updates the plugin only when the `version` in `.claude-plugin/plugin.json` changes. Pulling new commits with the same version does nothing.

```bash
cd ~/src/proof-of-green && git pull        # local clone only
claude plugin marketplace update proof-of-green
claude plugin update proof-of-green@proof-of-green
```

With a new version it prints `updated from 0.1.0 to 0.1.1 … Restart to apply changes.` With the same version it prints `already at the latest version`. Add `--scope local` if you installed with it.

## Where the data goes

```
~/.claude/plugins/data/proof-of-green-proof-of-green/sessions/<session_id>.jsonl
~/.claude/plugins/data/proof-of-green-proof-of-green/errors.log      (only if a hook failed)
```

The folder name is the install id with `@` replaced by `-`. A `--plugin-dir` run writes to `proof-of-green-inline` instead. `/proof-of-green:report` prints the folder on its last line.

## Uninstall

```bash
claude plugin uninstall proof-of-green@proof-of-green
claude plugin marketplace remove proof-of-green
```

Uninstall deletes the data folder. To keep your recorded sessions, add `--keep-data` to the uninstall command, or copy the folder first.

The cached copy of the plugin stays in `~/.claude/plugins/cache/proof-of-green/` after uninstall. Delete it by hand if you want the space back:

```bash
rm -rf ~/.claude/plugins/cache/proof-of-green
```

## What was checked, 2026-10-02, Claude Code 2.1.287

Run from a scratch repo with `--scope local`, from the local repo path:

- `marketplace add` printed `Successfully added marketplace: proof-of-green (declared in local settings)`.
- `install` printed `Successfully installed plugin: proof-of-green@proof-of-green (scope: local)` and `2 userConfig options not yet set`. The copy landed in `~/.claude/plugins/cache/proof-of-green/proof-of-green/0.1.0/`.
- A headless `claude -p` session with no `--plugin-dir` wrote `~/.claude/plugins/data/proof-of-green-proof-of-green/sessions/<id>.jsonl`. It recorded the failing test run, the edit and a verdict with `"mode":"observe","acted":false`, and no `errors.log`.
- `update` with the same version printed `already at the latest version (0.1.0)`. After changing the version to 0.1.1 it printed `updated from 0.1.0 to 0.1.1`, and the new file was in the `0.1.1` cache folder.
- `uninstall` removed the data folder and the install record. The cache folder stayed.

Not checked: adding the marketplace from GitHub (the repo is not pushed yet), user scope, `/plugin configure` and `--values-stdin` (both write your user settings file), and whether the data folder survives an update.
