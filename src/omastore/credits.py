"""Attribution for catalogs and third-party work omastore reads."""

THEME_STORE_NAME = "omarchytheme.com"
THEME_STORE_AUTHOR = "limehawk"
THEME_STORE_REPO = "https://github.com/limehawk/omarchy-theme-website"
THEME_STORE_URL = "https://omarchytheme.com"

PLUGIN_STORE_NAME = "omarchyplugins.com"
PLUGIN_STORE_AUTHOR = "HANCORE"
PLUGIN_STORE_REPO = "https://github.com/HANCORE-linux/omarchy-plugin-marketplace"
PLUGIN_STORE_URL = "https://omarchyplugins.com"

STATUS_CREDIT = (
    f"catalogs: {THEME_STORE_NAME} ({THEME_STORE_AUTHOR})  ·  "
    f"{PLUGIN_STORE_NAME} ({PLUGIN_STORE_AUTHOR})  ·  ? credits"
)

ABOUT = f"""# Credits

omastore does not host themes or plugins. It is a terminal client
that reads public community catalogs, then calls the official
`omarchy` commands to install or manage what you pick.

## Theme catalog

**{THEME_STORE_NAME}** by **{THEME_STORE_AUTHOR}**
{THEME_STORE_URL}
{THEME_STORE_REPO}

Public theme listings, palettes, and README text come from that
project's `themes-data.json`. MIT licensed marketplace code.
Themes themselves remain the work of their authors.

## Plugin catalog

**{PLUGIN_STORE_NAME}** by **{PLUGIN_STORE_AUTHOR}**
{PLUGIN_STORE_URL}
{PLUGIN_STORE_REPO}

Public plugin listings come from that project's `site/catalog.json`.
MIT licensed marketplace code. See their NOTICE: plugin code,
names, logos, and previews stay with their owners.

The plugin marketplace credits [bjarneo](https://github.com/bjarneo)
for interface inspiration and limehawk's theme site for its
submission workflow.

## Authors

Every theme and plugin belongs to the person who published it.
omastore shows their name and GitHub repo on the detail pane.
Installing clones *their* repository.

## Omarchy

Omarchy is by DHH / 37signals / omacom. omastore is an independent
community client and is not affiliated with, sponsored by, or
endorsed by Omarchy, 37signals, {THEME_STORE_NAME}, or
{PLUGIN_STORE_NAME}.
"""
