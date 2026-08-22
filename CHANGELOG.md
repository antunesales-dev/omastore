# Changelog

## Unreleased

## 0.2.6 — 2026-08-22

Installed groups, scan-on-update, bulk outdated, credits.

- Credits screen shows the version and a changelog tab (`?`, then `l`).
- Filter and list outdated extras: `f` includes outdated, yellow **↑**, `is:outdated` / `is:updatable`, `omastore list --outdated`.
- Apply/try uses the `omarchy theme list` name, so catalog titles like Retro '82 actually switch.
- TUI follows the current theme and installed plugins while open (colors + list, about every 2s) without stealing list focus.
- Installed tab groups current / extra themes / community plugins / built-in plugins; stock themes stay off the default dump.
- Catalog age on the status line. Overlay does not mark a catalog listing stock just because the title slug-collides.
- Updates run the same no-execute scan as install. hyprctl/Process/fetch are warn; curl|bash and secrets stay block. Last scan verdict on the detail pane. MCP `outdated` and `pack_install`.
- `g` / `by:author` / `--author` lists more from the same catalog author or GitHub owner. Stays on the current tab (`1` / `2` for the other kind).
- `omastore update --outdated` and Installed/`f outdated` then `u` scan every outdated extra, then update (one `omarchy theme update` for extra git themes; plugins one by one). Stop on the first block.
- Settling on a row pre-scans into `~/.cache/omastore/scans/` when the last verdict is missing or stale.
- Pack member names jump to the plugins tab; `g` on a pack lists those plugins.

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
