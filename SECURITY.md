# Security

omastore installs third-party themes and plugins by cloning their git
repositories with the official Omarchy CLI. Treat every listing as
untrusted code until you have read it.

omastore is a client, not a sandbox. A pre-install scan is a local
no-execute pass, not proof of safety. HANCORE verified is a signal;
we still scan.

## Pre-install scan

Before `omarchy plugin add` or `omarchy theme install`, omastore:

1. Reads catalog signals (unverified/failed, `security_warnings`, odd install URL).
2. Fetches a GitHub archive or a hookless shallow clone into a temp dir.
   It never imports QML and never runs `qmlscene`.
3. Statically audits that tree (manifest vs files, network, process,
   secrets/paths, obfuscation).
4. Verdict: `clean` / `warn` / `block`.

If the fetch or parse fails, install is **refused** (fail closed).
`--yes` does not skip that. `--i-accept-scan-risks` only covers
pattern hits after a scan that actually finished.

Pack install scans every pending member and stops the whole pack on
the first blocked plugin.

MCP `install` needs `confirm=true` **and** a clean scan (or
`accept_scan_risks`). A crashed scan cannot be overridden.

## What counts as a security issue

Report privately if the problem is in **this client**, for example:

- Code execution, command injection, or path traversal in omastore
- Secrets, tokens, or credentials leaked or stored unsafely
- Skipping the pre-install scan or its fail-closed behavior without
  an explicit user override
- MCP install/remove running without the intended confirmations
- Privilege issues in how omastore shells out to `omarchy`

A **normal bug** (TUI glitch, wrong filter, cache, docs) is not a
vulnerability. File a public GitHub Issue.

A malicious or compromised *theme or plugin* is not an omastore
vulnerability. See “Report a bad catalog listing” below.

## Report a vulnerability in omastore

Do **not** open a public issue or pull request.

Use [GitHub Security Advisories](https://github.com/antunesales-dev/omastore/security/advisories/new)
so the report stays private until a fix is ready.

Please do **not** put secrets, private tokens, credentials, or a full
weaponized exploit PoC in public Issues, PRs, discussions, or chat.
Describe the impact and enough to reproduce; we can ask for more
over the advisory.

### What to expect

- We aim to acknowledge within a few days.
- We will fix and publish when a patch is ready, then disclose.
- Please give us time to ship a fix before talking about it in public.

## Report a bad catalog listing

A malicious or compromised *theme or plugin* belongs with that
project, and with the catalog that listed it — not with omastore,
and not with Omarchy / 37signals:

- Themes: [limehawk/omarchy-theme-website](https://github.com/limehawk/omarchy-theme-website)
- Plugins: [HANCORE-linux/omarchy-plugin-marketplace security advisories](https://github.com/HANCORE-linux/omarchy-plugin-marketplace/security/advisories/new)
  or a listing issue on that repo.

omastore can prefill a GitHub issue draft (title, plugin id, repo,
scan hits, omastore version) and open it with `xdg-open`. You send
it. It never POSTs with a stored token.
