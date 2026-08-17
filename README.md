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

Not affiliated with Omarchy, 37signals, or the community catalog sites. Those sites stay the galleries. omastore is a terminal client for the same catalogs.

## How it works

It is meant to stay simple.

1. Open `omastore`.
2. Type `/` and search, or press `1` / `2` / `3` for themes, plugins, or what you already have.
3. Filter with `f` (installed / available / extra / stock), `v` (community / built-in), and `s` (stars / name / recent). You can also type prefixes in the search box: `hue:blue`, `tag:bar`, `is:available`, `src:community`.
4. Read the name, author, palette or README on the right.
5. Press `enter` (or `i`) to install. omastore asks first, then runs the official `omarchy` command.

You do not browse a new store. You browse **their** catalogs, then Omarchy does the install.

## Credits

omastore does not create or host the listings.

| What you see | Who made it |
| --- | --- |
| Theme catalog | **[limehawk](https://github.com/limehawk)** — [omarchytheme.com](https://omarchytheme.com) · [omarchy-theme-website](https://github.com/limehawk/omarchy-theme-website) |
| Plugin catalog | **[HANCORE](https://github.com/HANCORE-linux)** — [omarchyplugins.com](https://omarchyplugins.com) · [omarchy-plugin-marketplace](https://github.com/HANCORE-linux/omarchy-plugin-marketplace) |
| Each theme or plugin | The author named on the item (and their GitHub repo) |
| Install / enable / remove | Official **Omarchy** CLI |

The plugin marketplace itself credits [bjarneo](https://github.com/bjarneo) for interface inspiration and limehawk's theme site for its submission workflow.

Press `?` in the TUI, or run `omastore about`. Full third-party rights notes are in [NOTICE.md](NOTICE.md).

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

Put it next to Omacalc / Omacut / Omawrite in the Omarchy app launcher:

```bash
omastore desktop
```

Then Super + Space and type **Omastore**, or Super + Ctrl + O. It opens as a floating Omarchy TUI and follows the current theme colors.

## Use

```bash
omastore                          # TUI
omastore plugins                  # TUI on the plugins tab
omastore tui --tab plugins
omastore search lumon
omastore search overview --kind plugin
omastore search hue:blue is:available --sort stars
omastore search --category widgets --tag bar --available
omastore list --installed --source community
omastore info theme:lumon --readme
omastore install theme:lumon
omastore apply lumon
omastore install plugin:omarchy-overview
omastore remove plugin:omarchy-overview
omastore list --installed
omastore refresh
omastore about
```

### TUI keys

| Key | Action |
| --- | --- |
| `/` | search (also `hue:blue`, `tag:bar`, `is:available`) |
| `1` `2` `3` | themes / plugins / installed |
| `f` | cycle status filter |
| `v` | cycle community / built-in |
| `s` | cycle sort |
| `enter` | install, apply, or enable |
| `i` | install |
| `a` | apply theme |
| `e` / `d` | enable / disable plugin |
| `u` | update |
| `x` | remove |
| `r` | refresh catalogs |
| `?` | credits |
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

PRs only — `main` does not take direct pushes. See [CONTRIBUTING.md](CONTRIBUTING.md).

```bash
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
```

## License

MIT
