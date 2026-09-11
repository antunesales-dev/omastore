# Changelog

## 0.2.8 — 2026-09-11

Sandboxed scans, warn does not refuse install, and hide inactive community plugins.

**Sandboxed scan.** The pre-install audit runs in bubblewrap (no network, no HOME, no extra capabilities) after the GitHub fetch. Plugin code is still never executed; this is not a runtime sandbox for installed plugins. The scan skips `tests/`, `spec/`, `e2e/`, `*.test.js`, `*.spec.*`, and `test_*.py`, plus `.github/` and `.svg`.

**Warn does not refuse install.** Scan **warn** (network `fetch`, QML `Process`, `hyprctl`, `bash -c`, `/bin/bash`, `child_process`, unknown https hosts) goes to the normal confirm; `--yes` is enough. Not an abort-default trap. **Block** stays refuse: `curl | bash`, secrets (`~/.ssh`, tokens, shadow), obfuscation, crashed fetch. `--i-accept-scan-risks` still cannot override a failed scan. Generic `cookie` / `api token` word hits are no longer blocks.

**Hide inactive plugins.** Plugins with no GitHub update in 90 days (`repositoryUpdatedAt`) are hidden on the plugins tab by default. Installed extras stay visible. This is a client filter, not a HANCORE delist. `m` cycles active / inactive / all. Search `is:inactive` / `is:active` / `maintained:all`. CLI: `--inactive` / `--include-inactive`. None of today's contest listings are 90 days old yet; the default still shows the current dump.

## 0.2.6 — 2026-08-22

Installed groups, scan-on-update, bulk outdated, credits.

**Credits.** `?` shows the version, catalog credits, and a changelog tab (`l`).

**Installed.** Grouped as current theme, extra themes, community plugins, then built-in plugins. Stock palettes stay off the default dump. Yellow **↑** means git HEAD is behind — `f` cycles to outdated, or search `is:outdated` / `is:updatable`. CLI: `omastore list --outdated`. Catalog age sits on the status line. A catalog listing is not marked stock just because the title slug-collides.

**Apply.** Apply and try use the `omarchy theme list` name, so titles like Retro '82 actually switch.

**Live.** While open, the TUI follows the current theme (including colors) and installed plugins, about every 2s, without stealing list focus.

**Scan.** Updates use the same no-execute scan as install. `hyprctl`, QML `Process`, and `fetch` are warn; `curl | bash` and secrets stay block. The detail pane shows the last verdict. Settling on a row pre-scans into `~/.cache/omastore/scans/` when that verdict is missing or stale.

**Update.** `omastore update --outdated` and Installed (or Plugins) with `f` outdated, then `u`, scan every listed extra, then update. Extra git themes share one `omarchy theme update`. Plugins update one by one. Stop on the first block.

**Author.** `g`, `by:author`, and `--author` list more from the same catalog author or GitHub owner, on the current tab. Press `1` / `2` for the other kind.

**Packs.** Click a member name to open it on the plugins tab. `g` on a pack lists those plugins.

**MCP.** Read-only `outdated`. `pack_install` still needs mutate, `confirm=true`, and a clean scan.

## 0.2.5 — 2026-08-21

Pre-install scan and MCP catalog client.

- Scan a copy of the repo before `omarchy plugin add` / `theme install`. Never executes plugin code.
- Fail closed if the fetch or parse fails. `--yes` does not skip a failed scan; `--i-accept-scan-risks` only covers pattern hits.
- TUI: abort (default), report a draft, or install anyway after a second confirm.
- Pack install stops on the first blocked plugin.
- MCP: read-only `scan`; install needs `confirm=true` and a clean scan (or `accept_scan_risks`).
- Restore hidden bar widgets to the parent section before plugin remove or disable.

## 0.2.4 — 2026-08-21

Stop filter keys from emptying or resetting the TUI.

- Escape only leaves search. `0` resets when a filter is actually on, and keeps the current sort.
- `y` (verified) only applies on the plugins tab.

## 0.2.3 — 2026-08-21

Reset filters, cleaner status, pan zoomed previews.

- Status bar no longer wraps catalog credits; those stay on `?`.
- Zoomed screenshots pan with the arrow keys.

## 0.2.2 — 2026-08-21

Plugin packs, first-run notice, and plugin filters.

- Suggested packs are hand-picked verified plugins from the HANCORE catalog, not a new store.
- First launch explains that community plugins run unsandboxed.

## 0.2.1 — 2026-08-21

Harden catalog trust and fix listed bugs.

- Install URLs must be https GitHub repos. Fetches stay on an allowlist and a byte cap.

## 0.2.0 — 2026-08-21

Screenshots, TUI, and local catalog client.

- Browse limehawk themes and HANCORE plugins from the terminal, then install with official `omarchy` commands.
