from omastore.models import parse_plugin, parse_theme, slugify, theme_install_url


def test_slugify_display_names() -> None:
    assert slugify("Tokyo Night") == "tokyo-night"
    assert slugify("Vantablack") == "vantablack"
    assert slugify("omarchy-lumon-theme") == "omarchy-lumon-theme"


def test_theme_install_url_skips_tree_links() -> None:
    assert theme_install_url("https://github.com/basecamp/omarchy/tree/quattro/themes/catppuccin") is None
    assert theme_install_url("https://github.com/OldJobobo/omarchy-lumon-theme") == (
        "https://github.com/OldJobobo/omarchy-lumon-theme"
    )


def test_parse_theme_community() -> None:
    item = parse_theme(
        {
            "id": "lumon",
            "name": "Lumon",
            "slug": "lumon",
            "github_url": "https://github.com/OldJobobo/omarchy-lumon-theme",
            "github_owner": "OldJobobo",
            "description": "Severance-inspired",
            "colors_json": '{"accent":"#6fb8e3","background":"#1b2d40"}',
            "primary_hue": "blue",
            "is_builtin": 0,
            "is_curated": 1,
            "stars": 164,
            "security_warnings": "[]",
        }
    )
    assert item.kind == "theme"
    assert item.id == "lumon"
    assert item.can_install
    assert item.colors["accent"] == "#6fb8e3"
    assert item.matches("severance blue")


def test_parse_plugin_installable() -> None:
    item = parse_plugin(
        {
            "id": "omarchy-overview",
            "name": "Overview",
            "description": "Hyprland workspace overview",
            "author": "AyushKr2003",
            "repo": "https://github.com/AyushKr2003/omarchy-overview",
            "sourceType": "community",
            "installAvailable": True,
            "category": "Appearance",
            "tags": ["workspaces", "hyprland"],
            "stars": 7,
            "verificationStatus": "unverified",
        }
    )
    assert item.kind == "plugin"
    assert item.install_url.endswith("omarchy-overview")
    assert item.matches("workspace overview")
    assert not item.first_party
    assert item.verification_label == "unverified"


def test_verification_label_for_verified_and_builtin() -> None:
    verified = parse_plugin(
        {
            "id": "ok",
            "name": "Ok",
            "sourceType": "community",
            "installAvailable": True,
            "verificationStatus": "verified",
        }
    )
    builtin = parse_plugin(
        {
            "id": "omarchy.clock",
            "name": "Clock",
            "sourceType": "builtin",
            "verificationStatus": "",
        }
    )
    assert verified.verification_label == "verified"
    assert builtin.verification_label == ""


def test_status_label_includes_outdated() -> None:
    from omastore.models import Item

    plugin = Item(kind="plugin", id="x", name="X", installed=True, enabled=True, outdated=True)
    assert "on" in plugin.status_label
    assert "outdated" in plugin.status_label
    theme = Item(kind="theme", id="lumon", name="Lumon", extra=True, installed=True, outdated=True)
    assert "outdated" in theme.status_label
