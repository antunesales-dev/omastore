from omastore.filters import (
    Query,
    apply_query,
    clamp_query,
    cycle_status,
    cycle_verified,
    matches_filters,
    parse_search,
)
from omastore.models import Item


def _theme(**kwargs) -> Item:
    data = {"kind": "theme", "id": "lumon", "name": "Lumon", "hue": "blue"}
    data.update(kwargs)
    return Item(**data)


def test_parse_search_prefixes() -> None:
    query = parse_search("severance hue:blue is:available src:community sort:name")
    assert query.text == "severance"
    assert query.hue == "blue"
    assert query.status == "available"
    assert query.source == "community"
    assert query.sort == "name"


def test_status_and_hue_filters() -> None:
    installed = _theme(id="tokyo-night", name="Tokyo Night", installed=True, builtin=True, hue="blue")
    available = _theme(id="void", name="Void", hue="red", install_url="https://github.com/x/void", install_available=True)
    assert matches_filters(installed, Query(status="installed"))
    assert not matches_filters(available, Query(status="installed"))
    assert matches_filters(available, Query(status="available", hue="red"))
    assert not matches_filters(available, Query(hue="blue"))


def test_apply_query_sorts_and_scopes() -> None:
    items = [
        _theme(id="a", name="Aether", stars=1, hue="green"),
        _theme(id="b", name="Blue", stars=9, hue="blue"),
        Item(kind="plugin", id="clock", name="Clock", first_party=True),
    ]
    shown = apply_query(items, Query(hue="blue", sort="stars"), "themes")
    assert [item.id for item in shown] == ["b"]
    named = apply_query(items, Query(sort="name"), "themes")
    assert [item.name for item in named] == ["Aether", "Blue"]


def test_outdated_filter() -> None:
    items = [
        Item(kind="theme", id="old", name="Old", extra=True, installed=True, outdated=True),
        Item(kind="theme", id="new", name="New", extra=True, installed=True, outdated=False),
    ]
    shown = apply_query(items, Query(status="outdated"), "themes")
    assert [item.id for item in shown] == ["old"]


def test_cycle_status() -> None:
    query = cycle_status(Query())
    assert query.status == "installed"


def test_plugin_status_cycle_skips_theme_only_states() -> None:
    query = cycle_status(Query(), "plugins")
    assert query.status == "installed"
    query = cycle_status(query, "plugins")
    assert query.status == "not-installed"
    query = cycle_status(query, "plugins")
    assert query.status == "all"
    extra = cycle_status(Query(status="extra"), "plugins")
    assert extra.status == "installed"


def test_plugin_not_installed_and_verified_and_builtin() -> None:
    have = Item(kind="plugin", id="have", name="Have", installed=True, verification="verified")
    open_ = Item(
        kind="plugin",
        id="open",
        name="Open",
        verification="unverified",
        install_url="https://github.com/a/open",
    )
    stock = Item(kind="plugin", id="clock", name="Clock", first_party=True, builtin=True, installed=True)
    items = [have, open_, stock]
    installed = apply_query(items, Query(status="installed", sort="name"), "plugins")
    assert [item.id for item in installed] == ["clock", "have"]
    missing = apply_query(items, Query(status="not-installed", sort="name"), "plugins")
    assert [item.id for item in missing] == ["open"]
    verified = apply_query(items, Query(verified="yes", sort="name"), "plugins")
    assert [item.id for item in verified] == ["have"]
    unverified = apply_query(items, Query(verified="no", sort="name"), "plugins")
    assert [item.id for item in unverified] == ["open"]
    builtin = apply_query(items, Query(source="builtin", sort="name"), "plugins")
    assert [item.id for item in builtin] == ["clock"]
    community = apply_query(items, Query(source="community", sort="name"), "plugins")
    assert [item.id for item in community] == ["have", "open"]


def test_stars_prefix_and_min_stars() -> None:
    query = parse_search("stars:10")
    assert query.min_stars == 10
    low = Item(kind="plugin", id="low", name="Low", stars=2)
    high = Item(kind="plugin", id="high", name="High", stars=40)
    shown = apply_query([low, high], Query(min_stars=10), "plugins")
    assert [item.id for item in shown] == ["high"]


def test_cycle_verified() -> None:
    query = cycle_verified(Query())
    assert query.verified == "yes"
    query = cycle_verified(query)
    assert query.verified == "no"
    query = cycle_verified(query)
    assert query.verified == "all"


def test_clamp_query_drops_theme_status_on_plugins() -> None:
    query = clamp_query(Query(status="current"), "plugins")
    assert query.status == "all"


def test_themes_sort_installed_before_catalog() -> None:
    items = [
        _theme(id="void", name="Void", stars=999),
        _theme(id="tokyo-night", name="Tokyo Night", stars=1, installed=True, builtin=True),
        _theme(id="lumon", name="Lumon", stars=2, installed=True, extra=True),
        _theme(id="spacex", name="Spacex", stars=0, installed=True, extra=True, current=True),
    ]
    shown = apply_query(items, Query(sort="stars"), "themes")
    assert [item.id for item in shown] == ["spacex", "lumon", "tokyo-night", "void"]


def test_plugins_sort_installed_then_az() -> None:
    items = [
        Item(kind="plugin", id="z", name="Zebra", installed=False),
        Item(kind="plugin", id="b", name="Beta", installed=True),
        Item(kind="plugin", id="a", name="Alpha", installed=False),
        Item(kind="plugin", id="c", name="Clock", installed=True),
    ]
    shown = apply_query(items, Query(sort="name"), "plugins")
    assert [item.name for item in shown] == ["Beta", "Clock", "Alpha", "Zebra"]


def test_packs_tab_lists_no_items() -> None:
    items = [
        Item(kind="plugin", id="clock", name="Clock", first_party=True),
        _theme(id="void", name="Void"),
    ]
    assert apply_query(items, Query(), "packs") == []


def test_plugins_sort_stars_among_uninstalled() -> None:
    items = [
        Item(kind="plugin", id="low", name="Low", stars=2),
        Item(kind="plugin", id="high", name="High", stars=40),
        Item(kind="plugin", id="mid", name="Mid", stars=10),
        Item(kind="plugin", id="on", name="On", stars=1, installed=True),
    ]
    shown = apply_query(items, Query(sort="stars"), "plugins")
    assert [item.name for item in shown] == ["High", "Mid", "Low", "On"]
