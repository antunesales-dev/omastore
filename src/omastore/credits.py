"""Attribution for catalogs and third-party work omastore reads."""

THEME_STORE_NAME = "omarchytheme.com"
THEME_STORE_AUTHOR = "limehawk"
THEME_STORE_REPO = "https://github.com/limehawk/omarchy-theme-website"
THEME_STORE_URL = "https://omarchytheme.com"

PLUGIN_STORE_NAME = "omarchyplugins.com"
PLUGIN_STORE_AUTHOR = "HANCORE"
PLUGIN_STORE_REPO = "https://github.com/HANCORE-linux/omarchy-plugin-marketplace"
PLUGIN_STORE_URL = "https://omarchyplugins.com"

OMASTORE_REPO = "https://github.com/antunesales-dev/omastore"

STATUS_CREDIT = (
    f"not a competing store  ·  catalogs by {THEME_STORE_AUTHOR} ({THEME_STORE_NAME}) "
    f"and {PLUGIN_STORE_AUTHOR} ({PLUGIN_STORE_NAME})  ·  ? more"
)

ABOUT = f"""# This is not a competing store

omastore does not replace {THEME_STORE_NAME} or {PLUGIN_STORE_NAME}.
Those sites are the catalogs. Their authors built the listings,
the submission flow, and the community around them.

omastore is only another way to *look at the same catalogs*
from a terminal, then run the official `omarchy` install
commands those sites already document.

If you want the full gallery, previews, and publishing tools,
use their websites. This app is a convenience client.

## This client

**omastore**
{OMASTORE_REPO}

Source, issues, and PRs for the terminal client live there.
It does not host themes or plugins.

## Theme catalog — thank you, {THEME_STORE_AUTHOR}

**{THEME_STORE_NAME}**
{THEME_STORE_URL}
{THEME_STORE_REPO}

Listings, palettes, and README text are read live from that
project's public `themes-data.json`. Marketplace code is MIT.
Each theme still belongs to its author.

## Plugin catalog — thank you, {PLUGIN_STORE_AUTHOR}

**{PLUGIN_STORE_NAME}**
{PLUGIN_STORE_URL}
{PLUGIN_STORE_REPO}

Listings are read live from that project's public
`site/catalog.json`. Marketplace code is MIT. Their NOTICE
still applies: plugin code, names, logos, and previews stay
with their owners.

The plugin marketplace credits [bjarneo](https://github.com/bjarneo)
for interface inspiration and limehawk's theme site for its
submission workflow.

## Authors

Every theme and plugin belongs to the person who published it.
Installing clones *their* GitHub repository with official Omarchy.

## Omarchy

Omarchy is by DHH / 37signals / omacom. omastore is an independent
community client. It is not affiliated with, sponsored by, or
endorsed by Omarchy, 37signals, {THEME_STORE_NAME}, or
{PLUGIN_STORE_NAME}.
"""
