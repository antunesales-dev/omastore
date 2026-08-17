# omastore

The Omarchy store in your terminal.

Search, preview, read about, and install [community themes](https://omarchytheme.com) and [community plugins](https://omarchyplugins.com) without opening a browser. Installs go through the official `omarchy theme` and `omarchy plugin` commands.

```
$ omastore
```

```
omastore  ·  the omarchy store
 themes   plugins   installed     / search…

 ● Vantablack          stock · current     VANTABLACK
 ○ Lumon         ★164  extra               OldJobobo · theme · blue
 ○ Tokyo Night         stock               [i] install   [a] apply
 ○ Overview      ★7    plugin
                                           A cold corporate Omarchy theme…
```

Not affiliated with Omarchy, 37signals, [omarchythemes.com](https://omarchythemes.com), or [omarchyplugins.com](https://omarchyplugins.com). Those sites stay the galleries. omastore is a terminal client for the same catalogs.

## Why

Omarchy already knows how to install a theme or plugin from a git URL. The missing piece is finding one without leaving the keyboard: search, read the README, see the palette, then install.

## Install

Needs Python 3.12+ and the `omarchy` CLI.

```bash
git clone https://github.com/antunesales-dev/omastore.git
cd omastore
python3 -m venv .venv
.venv/bin/pip install -e .
ln -sf "$PWD/bin/omastore" ~/.local/bin/omastore
```

Or run it from the repo:

```bash
./bin/omastore
```

## Use

```bash
omastore                          # TUI
omastore plugins                  # TUI on the plugins tab
omastore tui --tab plugins
omastore search lumon
omastore search overview --kind plugin
omastore info theme:lumon --readme
omastore install theme:lumon
omastore apply lumon
omastore install plugin:omarchy-overview
omastore remove plugin:omarchy-overview
omastore list --installed
omastore refresh
```

### TUI keys

| Key | Action |
| --- | --- |
| `/` | search |
| `1` `2` `3` | themes / plugins / installed |
| `enter` | install, apply, or enable |
| `i` | install |
| `a` | apply theme |
| `e` / `d` | enable / disable plugin |
| `u` | update |
| `x` | remove |
| `r` | refresh catalogs |
| `q` | quit |

Theme preview is the 16-color palette from the catalog. Plugin detail is the marketplace listing plus the upstream README.

## Catalogs

- Themes: [limehawk/omarchy-theme-website](https://github.com/limehawk/omarchy-theme-website) `themes-data.json` (the data behind [omarchytheme.com](https://omarchytheme.com))
- Plugins: [HANCORE-linux/omarchy-plugin-marketplace](https://github.com/HANCORE-linux/omarchy-plugin-marketplace) `site/catalog.json` (the data behind [omarchyplugins.com](https://omarchyplugins.com))

Catalogs cache under `~/.cache/omastore/` for six hours. `omastore refresh` fetches them again.

## Safety

Community themes and plugins are third-party code. Plugins run unsandboxed inside `omarchy-shell`. omastore shows the repo, verification status, and any catalog warnings, then calls:

```bash
omarchy theme install <url>
omarchy plugin add <url> --enable --yes
```

Review the repository before you confirm.

## Develop

```bash
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
```

## License

MIT
