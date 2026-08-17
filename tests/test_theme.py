from omastore.theme import load_omarchy_colors, omarchy_theme_css


def test_theme_css_uses_hex_colors() -> None:
    colors = load_omarchy_colors()
    css = omarchy_theme_css()
    assert colors["background"].startswith("#")
    assert colors["background"] in css
    assert colors["accent"] in css
