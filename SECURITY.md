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

## Report a vulnerability in omastore

Do not open a public issue for a vulnerability in this repository.
Use [GitHub private vulnerability reporting](https://github.com/antunesales-dev/omastore/security/advisories/new)
or email the maintainer.

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
