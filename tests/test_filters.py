from omastore.filters import (
    Query,
    apply_query,
    clamp_query,
    cycle_status,
    cycle_verified,
    matches_filters,
    parse_search,
    reset_filters,
    strip_filter_tokens,
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
    plugins = [
        Item(kind="plugin", id="behind", name="Behind", installed=True, outdated=True, repo="https://github.com/a/b"),
        Item(kind="plugin", id="fresh", name="Fresh", installed=True, outdated=False, repo="https://github.com/a/c"),
    ]
    assert [item.id for item in apply_query(plugins, Query(status="outdated"), "plugins")] == ["behind"]
    assert [item.id for item in apply_query(plugins, Query(status="updatable"), "plugins")] == ["behind", "fresh"]
    assert parse_search("is:upgrade").status == "upgrade"
    assert matches_filters(plugins[0], Query(status="upgrade"))


def test_cycle_status() -> None:
    from omastore.filters import STATUS_CYCLE

    query = cycle_status(Query())
    assert query.status == "installed"
    assert "current" not in STATUS_CYCLE
    assert "outdated" in STATUS_CYCLE
    walked = Query()
    seen: list[str] = []
    for _ in STATUS_CYCLE:
        walked = cycle_status(walked)
        seen.append(walked.status)
    assert seen[-1] == "all"
    assert "outdated" in seen


def test_plugin_status_cycle_skips_theme_only_states() -> None:
    query = cycle_status(Query(), "plugins")
    assert query.status == "installed"
    query = cycle_status(query, "plugins")
    assert query.status == "not-installed"
    query = cycle_status(query, "plugins")
    assert query.status == "outdated"
    query = cycle_status(query, "plugins")
    assert query.status == "all"
    extra = cycle_status(Query(status="extra"), "plugins")
    assert extra.status == "installed"
    installed_tab = cycle_status(Query(), "installed")
    assert installed_tab.status == "extra"
    installed_tab = cycle_status(installed_tab, "installed")
    assert installed_tab.status == "outdated"
    installed_tab = cycle_status(installed_tab, "installed")
    assert installed_tab.status == "all"


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


def test_pack_prefix_filters_verified_pins() -> None:
    stocks = Item(
        kind="plugin",
        id="io.github.5d0tal1gat0r.stocks",
        name="Stocks",
        verification="verified",
    )
    other = Item(kind="plugin", id="raw", name="Raw", verification="verified")
    query = parse_search("pack:finance")
    assert query.pack == "finance"
    shown = apply_query([stocks, other], query, "plugins")
    assert [item.id for item in shown] == ["io.github.5d0tal1gat0r.stocks"]
    missing = apply_query([stocks, other], parse_search("pack:missing"), "plugins")
    assert missing == []


def test_author_prefix_matches_name_or_github_owner() -> None:
    lime = Item(kind="theme", id="a", name="A", author="limehawk", repo="https://github.com/limehawk/theme-a")
    other = Item(kind="theme", id="b", name="B", author="someone", repo="https://github.com/other/theme-b")
    owned = Item(kind="plugin", id="c", name="C", author="", repo="https://github.com/OldJobobo/omarchy-retro-82-theme")
    query = parse_search("by:limehawk")
    assert query.author == "limehawk"
    assert apply_query([lime, other], query, "themes") == [lime]
    by_repo = parse_search("author:oldjobobo")
    assert apply_query([owned, other], by_repo, "plugins") == [owned]


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
    assert clamp_query(Query(status="outdated"), "plugins").status == "outdated"
    assert clamp_query(Query(status="outdated"), "installed").status == "outdated"
    assert clamp_query(Query(status="extra"), "installed").status == "extra"


def test_reset_filters_keeps_search_text() -> None:
    query = Query(
        text="clipboard",
        status="installed",
        source="community",
        verified="yes",
        sort="name",
        min_stars=10,
    )
    reset = reset_filters(query)
    assert reset.text == "clipboard"
    assert reset.status == "all"
    assert reset.source == "all"
    assert reset.verified == "all"
    assert reset.sort == "name"
    assert reset.min_stars == 0


def test_strip_filter_tokens() -> None:
    assert strip_filter_tokens("clipboard is:installed verified:yes src:community") == "clipboard"
    assert strip_filter_tokens("stars:10 overview") == "overview"
    assert strip_filter_tokens("") == ""


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


def test_installed_tab_hides_stock_and_groups() -> None:
    items = [
        Item(kind="theme", id="vantablack", name="Vantablack", installed=True, current=True, builtin=True),
        Item(kind="theme", id="catppuccin", name="Catppuccin", installed=True, builtin=True, stars=27107),
        Item(kind="theme", id="lumon", name="Lumon", installed=True, extra=True, stars=1),
        Item(kind="plugin", id="demo", name="Demo", installed=True, enabled=True),
        Item(kind="plugin", id="omarchy.clock", name="Clock", installed=True, first_party=True, builtin=True),
    ]
    shown = apply_query(items, Query(sort="stars"), "installed")
    assert [item.id for item in shown] == ["vantablack", "lumon", "demo", "omarchy.clock"]
    extra = apply_query(items, Query(status="extra"), "installed")
    assert [item.id for item in extra] == ["lumon", "demo"]
    stock = apply_query(items, Query(source="builtin"), "installed")
    assert "catppuccin" in [item.id for item in stock]


def test_outdated_sorts_first() -> None:
    items = [
        Item(kind="plugin", id="fresh", name="Fresh", installed=True, stars=50),
        Item(kind="plugin", id="behind", name="Behind", installed=True, outdated=True, stars=1),
        Item(kind="plugin", id="catalog", name="Catalog", stars=99),
    ]
    shown = apply_query(items, Query(sort="stars"), "plugins")
    assert [item.id for item in shown] == ["behind", "catalog", "fresh"]


def test_plugins_sort_stars_among_uninstalled() -> None:
    items = [
        Item(kind="plugin", id="low", name="Low", stars=2),
        Item(kind="plugin", id="high", name="High", stars=40),
        Item(kind="plugin", id="mid", name="Mid", stars=10),
        Item(kind="plugin", id="on", name="On", stars=1, installed=True),
    ]
    shown = apply_query(items, Query(sort="stars"), "plugins")
    assert [item.name for item in shown] == ["High", "Mid", "Low", "On"]
