from __future__ import annotations

import os
import tomllib
from pathlib import Path


def current_theme_dir() -> Path | None:
    linked = Path.home() / ".local/state/omarchy/current/theme"
    if linked.is_dir():
        return linked
    omarchy = Path(os.environ.get("OMARCHY_PATH", "/usr/share/omarchy"))
    fallback = omarchy / "themes"
    if fallback.is_dir():
        return fallback
    return None


def load_omarchy_colors() -> dict[str, str]:
    defaults = {
        "background": "#111111",
        "foreground": "#e8e8e8",
        "accent": "#8d8d8d",
        "muted": "#7a7a7a",
        "lighter_background": "#1a1a1a",
        "darker_background": "#070707",
        "yellow": "#cecece",
    }
    theme_dir = current_theme_dir()
    if theme_dir is None:
        return defaults
    colors_path = theme_dir / "colors.toml"
    if not colors_path.is_file():
        return defaults
    try:
        data = tomllib.loads(colors_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return defaults
    for key in defaults:
        value = data.get(key)
        if isinstance(value, str) and value.startswith("#"):
            defaults[key] = value
    return defaults


def omarchy_theme_css() -> str:
    c = load_omarchy_colors()
    return f"""
Screen {{
    background: {c["background"]};
    color: {c["foreground"]};
}}

Header, Footer, #chrome, #status, #credits-line {{
    background: {c["darker_background"]};
}}

#brand {{
    color: {c["accent"]};
}}

.tab {{
    color: {c["muted"]};
}}

.tab.active {{
    color: {c["background"]};
    background: {c["accent"]};
}}

#search {{
    background: {c["lighter_background"]};
    color: {c["foreground"]};
}}

#search:focus {{
    background: {c["lighter_background"]};
}}

#filters, #status, #credits-line, .muted {{
    color: {c["muted"]};
}}

#list {{
    border-right: tall {c["lighter_background"]};
}}

#list:focus {{
    border-right: tall {c["accent"]};
}}

#credits, #confirm {{
    background: {c["lighter_background"]};
    border: tall {c["accent"]};
}}

.badge {{
    color: {c["accent"]};
}}

#warning {{
    color: {c["yellow"]};
}}
"""
