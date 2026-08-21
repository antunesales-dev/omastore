from omastore.theme import OMASTORE_ACCENT, load_omarchy_colors, omarchy_theme_css, polish_ui_colors


def test_theme_css_uses_hex_colors() -> None:
    colors = load_omarchy_colors()
    css = omarchy_theme_css()
    assert colors["background"].startswith("#")
    assert colors["background"] in css
    assert colors["accent"] in css


def test_grayscale_theme_keeps_a_colored_accent() -> None:
    polished = polish_ui_colors(
        {
            "background": "#000000",
            "foreground": "#FFFFFF",
            "accent": "#FFFFFF",
            "muted": "#FFFFFF",
            "lighter_background": "#000000",
            "darker_background": "#000000",
            "yellow": "#FFFFFF",
        }
    )
    assert polished["accent"] == OMASTORE_ACCENT
    assert polished["accent"] != "#FFFFFF"
    assert polished["muted"] != "#FFFFFF"
    assert polished["yellow"] != "#FFFFFF"
    assert polished["lighter_background"] != "#000000"
