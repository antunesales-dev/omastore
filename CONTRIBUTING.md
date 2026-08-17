# Contributing

PRs are welcome. Direct pushes to `main` are not.

## How to send a change

1. Fork [antunesales-dev/omastore](https://github.com/antunesales-dev/omastore).
2. Create a branch from the latest `main`.
3. Make a focused change.
4. Run tests:

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -e ".[dev]"
   .venv/bin/pytest
   ```

5. Open a pull request against `main`.

The PR waits in line. CI must pass, review comments must be resolved, and a maintainer merges it. Do not expect merge on open.

## What will be rejected

- Pushes or PRs that rewrite `main` history
- Secrets, tokens, or credentials
- Changes that drop credit for the theme or plugin catalogs
- Unrelated drive-by refactors

## Security

Report vulnerabilities privately: [SECURITY.md](SECURITY.md).
