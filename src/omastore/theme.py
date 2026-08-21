from __future__ import annotations

import os
import tomllib
from pathlib import Path

OMASTORE_ACCENT = "#7dcea0"
OMASTORE_YELLOW = "#e0af68"
OMASTORE_MUTED = "#8a8a8a"
OMASTORE_LIGHTER = "#1a1a1a"


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
    return polish_ui_colors(defaults)


def _rgb(value: str) -> tuple[int, int, int]:
    text = value.lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def _chroma(value: str) -> int:
    red, green, blue = _rgb(value)
    return max(red, green, blue) - min(red, green, blue)


def _luma(value: str) -> float:
    red, green, blue = _rgb(value)
    return (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255.0


def polish_ui_colors(colors: dict[str, str]) -> dict[str, str]:
    """Keep chrome readable when the Omarchy theme is grayscale."""
    out = dict(colors)
    background = out["background"]
    foreground = out["foreground"]
    if _chroma(out["accent"]) < 40 or abs(_luma(out["accent"]) - _luma(background)) < 0.14:
        out["accent"] = OMASTORE_ACCENT
    if abs(_luma(out["muted"]) - _luma(background)) < 0.12 or abs(_luma(out["muted"]) - _luma(foreground)) < 0.08:
        out["muted"] = OMASTORE_MUTED
    if abs(_luma(out["lighter_background"]) - _luma(background)) < 0.04:
        out["lighter_background"] = (
            OMASTORE_LIGHTER if abs(_luma(OMASTORE_LIGHTER) - _luma(background)) > 0.04 else "#2a2a2a"
        )
    if _chroma(out.get("yellow", "#cecece")) < 40:
        out["yellow"] = OMASTORE_YELLOW
    return out


def omarchy_theme_css() -> str:
    c = load_omarchy_colors()
    return f"""
Screen {{
    background: {c["background"]};
    color: {c["foreground"]};
}}

Header, Footer, #chrome, #status, #credits-line, #shot-bar, #shot-modal {{
    background: {c["darker_background"]};
}}

#brand, #shot-bar {{
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
    background: {c["background"]};
    border: none;
    border-right: tall {c["lighter_background"]};
}}

#list:focus {{
    border: none;
    border-right: tall {c["accent"]};
}}

#list > .option-list--option-highlighted {{
    background: {c["lighter_background"]};
    color: {c["foreground"]};
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
