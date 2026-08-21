# omastore

A terminal client for catalogs other people already built.

This is not a competing store. [omarchytheme.com](https://omarchytheme.com) (limehawk) and [omarchyplugins.com](https://omarchyplugins.com) (HANCORE) remain the catalogs. omastore is another way to look at the same public listings from the keyboard, then install with the official `omarchy theme` and `omarchy plugin` commands those sites already document.

```
$ omastore
```

```
Omastore  1 themes  2 plugins  3 installed  4 packs     Search  ·  /

 stars     f filter   v source   s sort

 ● Spacex
 ● Tokyo Night                              [t] try  [b] back  [a] apply
 ○ Lumon                              *164  [o] repo  [c] catalog  [p] zoom
```

Not affiliated with Omarchy, 37signals, or the community catalog sites. Those sites stay the galleries. omastore is a terminal client for the same catalogs.

## How it works

It is meant to stay simple.

1. Open `omastore`.
2. Type `/` and search, or press `1` / `2` / `3` / `4` for themes, plugins, installed, or suggested packs.
3. Filter with `f` (installed / available / extra / stock), `v` (community / built-in), and `s` (stars / name / recent). You can also type prefixes in the search box: `hue:blue`, `tag:bar`, `is:available`, `src:community`.
4. Installed themes show a filled **●** (green if it is the current theme, cyan otherwise) and sort above catalog-only rows. Plugin rows show a green **✓** when the HANCORE catalog verified them, or a yellow **−** when they are unverified. On the plugins tab, `f` is installed / not installed, `v` is community / built-in, `y` is verified / unverified, and `s` sorts by rating. You can also type `is:installed`, `is:not-installed`, `src:builtin`, `verified:yes`, `stars:10`.
5. Press `enter` (or `i`) to install. omastore first scans a copy of the repo without running it (`checking repo…`). Clean listings get the usual confirm (repo, verified, catalog warnings), then the official `omarchy` command. Hits stop the install: abort, open a prefilled report draft, or install anyway after a second confirm. Packs are hand-picked verified plugins from the HANCORE catalog (Everyday, Developer, Finance, Designer, Music, Artist, Gamer), not a keyword dump and not a new store. In a pack, **●** is already installed and **○** is still to install. `i` scans every remaining plugin, confirms if they are all clean, then installs them one by one. A blocked member fails the whole pack. `x` confirms every installed member, then removes them one by one. A plugin that also sits in another pack is still removed.

You do not browse a new store. You browse **their** catalogs, then Omarchy does the install. How we relate to those projects is in [COMMUNITY.md](COMMUNITY.md).

## Credits

omastore does not create or host the listings.

| What you see | Who made it |
| --- | --- |
| Theme catalog | **[limehawk](https://github.com/limehawk)** — [omarchytheme.com](https://omarchytheme.com) · [omarchy-theme-website](https://github.com/limehawk/omarchy-theme-website) |
| Plugin catalog | **[HANCORE](https://github.com/HANCORE-linux)** — [omarchyplugins.com](https://omarchyplugins.com) · [omarchy-plugin-marketplace](https://github.com/HANCORE-linux/omarchy-plugin-marketplace) |
| Each theme or plugin | The author named on the item (and their GitHub repo) |
| Install / enable / remove | Official **Omarchy** CLI |

The plugin marketplace itself credits [bjarneo](https://github.com/bjarneo) for interface inspiration and limehawk's theme site for its submission workflow.

Press `?` in the TUI, or run `omastore about`. Full third-party rights notes are in [NOTICE.md](NOTICE.md). How this relates to the catalogs, and a note you can send the authors, is in [COMMUNITY.md](COMMUNITY.md).

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
omastore tui --tab packs
omastore packs                    # list suggested plugin packs
omastore pack everyday            # show the Everyday pack
omastore pack install everyday --yes
omastore pack install everyday --yes --i-accept-scan-risks
omastore pack remove everyday --yes
omastore scan plugin:omarchy-overview
omastore search lumon
omastore search overview --kind plugin
omastore search hue:blue is:available --sort stars
omastore search --category widgets --tag bar --available
omastore list --installed --source community
omastore outdated
omastore try theme:lumon
omastore revert
omastore open theme:lumon
omastore open plugin:omarchy-overview --catalog
omastore preview plugin:omarchy-overview
omastore info theme:lumon --readme
omastore install theme:lumon
omastore apply lumon
omastore install plugin:omarchy-overview
omastore install plugin:omarchy-overview --yes
omastore install plugin:omarchy-overview --yes --i-accept-scan-risks
omastore remove plugin:omarchy-overview
omastore list --installed
omastore refresh
omastore about
omastore mcp                      # stdio MCP (browse/audit; mutate off unless OMASTORE_MCP_ALLOW_MUTATE=1)
```

### MCP (agents)

`omastore mcp` is a stdio MCP server over the **same** limehawk and HANCORE catalogs. It is an agent client, not a new store.

Read-only tools: `search`, `info`, `installed`, `packs`, `pack`, `audit`, `hidden_widgets`, `scan`.

Install/remove/enable/disable are **not registered** unless `OMASTORE_MCP_ALLOW_MUTATE=1`. Even then they require `confirm: true` and use official `omarchy` commands. Install also runs the no-execute scan; `confirm` is not enough when the scan reports issues (`accept_scan_risks`), and a failed scan cannot be overridden. They never execute catalog `installCommand` strings.

Example Cursor/Claude config:

```json
{
  "mcpServers": {
    "omastore": {
      "command": "omastore",
      "args": ["mcp"]
    }
  }
}
```

### TUI keys

| Key | Action |
| --- | --- |
| `/` | search (also `hue:blue`, `tag:bar`, `is:available`) |
| `1` `2` `3` `4` | themes / plugins / installed / packs |
| `f` | installed / not-installed / all |
| `v` | community / built-in / all |
| `y` | verified / unverified / all (plugins tab only) |
| `s` | sort: stars, name, recent |
| `0` | reset filters (keeps the current sort) |
| `enter` | install, apply, or enable |
| `i` | install |
| `t` / `b` | try an installed theme (does not freeze the list) / restore the previous one |
| `o` / `c` | open the author repo / catalog site |
| `p` | enlarge the screenshot (`+`/`−` zoom, arrows pan, `o` opens the file) |
| `a` | apply theme |
| `e` / `d` | enable / disable plugin |
| `u` | update |
| `x` | remove (on a pack: every installed member) |
| `r` | refresh catalogs |
| `?` | credits |
| `q` | quit |

Theme detail shows the catalog palette. After you settle on a row, omastore also shows a 16:9 screenshot: the theme's own `preview.png` if it is installed, otherwise a catalog or GitHub image, rendered with Sixel (Foot) or Kitty graphics (Ghostty) via textual-image, with half-block as fallback (`p` opens the file). Thin plugin listings fill empty fields from the author's `manifest.json` without overwriting catalog text. Plugin about is still the marketplace listing plus the upstream README.

## Catalogs

- Themes: [limehawk/omarchy-theme-website](https://github.com/limehawk/omarchy-theme-website) `themes-data.json` (the data behind [omarchytheme.com](https://omarchytheme.com))
- Plugins: [HANCORE-linux/omarchy-plugin-marketplace](https://github.com/HANCORE-linux/omarchy-plugin-marketplace) `site/catalog.json` (the data behind [omarchyplugins.com](https://omarchyplugins.com))

Catalogs cache under `~/.cache/omastore/` for six hours. `omastore refresh` fetches them again.

## Safety

Community themes and plugins are third-party code. Plugins run unsandboxed inside `omarchy-shell`. omastore is not a sandbox, and a clean scan is not proof of safety. HANCORE's verified badge is a signal; we still scan.

Before `omarchy plugin add` / `omarchy theme install`, omastore fetches a GitHub archive or a hookless shallow clone to a temp dir, then statically audits it (manifest vs files, network, process, secrets/paths, obfuscation). It never imports QML and never runs `qmlscene`. If the fetch or parse fails, install is refused (fail closed). `--yes` alone does not skip a failed scan; `--i-accept-scan-risks` only covers pattern hits, not a crashed scan.

Findings can be turned into a **draft** GitHub issue (HANCORE listing repo and/or the plugin repo). omastore never POSTs that issue.

```bash
omarchy theme install <url>
omarchy plugin add <url> --enable --yes
```

Review the repository before you confirm. The first launch shows this once; `[y]` continues, `[e]` opens the Everyday pack.

## Develop

PRs only — `main` does not take direct pushes. See [CONTRIBUTING.md](CONTRIBUTING.md).

```bash
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
```

## License

MIT
