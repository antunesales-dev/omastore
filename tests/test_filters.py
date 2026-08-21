from omastore.filters import Query, apply_query, cycle_status, matches_filters, parse_search
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
    shown = apply_query(items, Query(), "plugins")
    assert [item.name for item in shown] == ["Beta", "Clock", "Alpha", "Zebra"]


def test_plugins_sort_stars_among_uninstalled() -> None:
    items = [
        Item(kind="plugin", id="low", name="Low", stars=2),
        Item(kind="plugin", id="high", name="High", stars=40),
        Item(kind="plugin", id="mid", name="Mid", stars=10),
        Item(kind="plugin", id="on", name="On", stars=1, installed=True),
    ]
    shown = apply_query(items, Query(sort="stars"), "plugins")
    assert [item.name for item in shown] == ["On", "High", "Mid", "Low"]
