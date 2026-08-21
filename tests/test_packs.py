from omastore.models import Item
from omastore.packs import PACK_CREDIT, PACK_LIMIT, PACKS, get_pack

STOCKS = "io.github.5d0tal1gat0r.stocks"
CRYPTO = "io.github.guettoblasterr.crypto-market-pulse"


def _plugin(**kwargs) -> Item:
    data = {
        "kind": "plugin",
        "id": "x",
        "name": "X",
        "verification": "verified",
        "stars": 1,
    }
    data.update(kwargs)
    return Item(**data)


def test_pack_ids() -> None:
    for pack_id in ("everyday", "developer", "finance", "designer", "music", "artist", "gamer"):
        assert get_pack(pack_id) is not None
    assert get_pack("musician") is None
    assert get_pack("missing") is None
    assert "HANCORE" in PACK_CREDIT
    assert "omarchy" in PACK_CREDIT.lower()
    assert all(pack.pins for pack in PACKS)
    assert all(len(pack.pins) <= PACK_LIMIT for pack in PACKS)


def test_unverified_pin_is_dropped() -> None:
    pack = get_pack("everyday")
    items = [
        _plugin(id="omarchy-overview", name="Overview", verification="unverified", stars=999),
        _plugin(id="better.displays", name="Better Displays", stars=1),
    ]
    assert [item.id for item in pack.members(items)] == ["better.displays"]


def test_pin_order_not_stars() -> None:
    pack = get_pack("everyday")
    items = [
        _plugin(id="better.displays", name="Better Displays", stars=90),
        _plugin(id="omarchy-overview", name="Overview", stars=1),
    ]
    assert [item.id for item in pack.members(items)] == ["omarchy-overview", "better.displays"]


def test_cap_stops_at_limit() -> None:
    pack = get_pack("everyday")
    items = [_plugin(id=pin, name=pin, stars=i) for i, pin in enumerate(pack.pins)]
    extra = _plugin(id="random-extra", name="Random", stars=999, tags=["workspaces"], category="Widgets")
    members = pack.members([*items, extra], limit=3)
    assert len(members) == 3
    assert [item.id for item in members] == list(pack.pins[:3])
    assert "random-extra" not in [item.id for item in pack.members([*items, extra])]


def test_packs_do_not_cross_contaminate() -> None:
    overview = _plugin(id="omarchy-overview", name="Overview")
    git = _plugin(id="dev.git", name="Git")
    stocks = _plugin(id=STOCKS, name="Stocks")
    wall = _plugin(id="dizziee.auto-wallpaper", name="Auto Wallpaper")
    yt = _plugin(id="levi.youtube-music", name="YouTube Music")
    solitaire = _plugin(id="nosignal.quattrolitaire", name="Quattrolitaire", stars=22)
    items = [overview, git, stocks, wall, yt, solitaire]
    assert [item.id for item in get_pack("everyday").members(items)] == ["omarchy-overview"]
    assert [item.id for item in get_pack("developer").members(items)] == ["dev.git"]
    assert [item.id for item in get_pack("finance").members(items)] == [STOCKS]
    assert [item.id for item in get_pack("designer").members(items)] == ["dizziee.auto-wallpaper"]
    assert [item.id for item in get_pack("music").members(items)] == ["levi.youtube-music"]
    assert [item.id for item in get_pack("gamer").members(items)] == ["nosignal.quattrolitaire"]
    assert "levi.youtube-music" not in [item.id for item in get_pack("gamer").members(items)]
    assert "omarchy-overview" not in [item.id for item in get_pack("designer").members(items)]


def test_pending_skips_installed() -> None:
    pack = get_pack("finance")
    open_ = _plugin(id=STOCKS, name="Stocks", install_url="https://github.com/a/b")
    have = _plugin(id=CRYPTO, name="Crypto Pulse", installed=True)
    pending = pack.pending([open_, have])
    assert [item.id for item in pending] == [STOCKS]


def test_removable_only_installed() -> None:
    pack = get_pack("finance")
    open_ = _plugin(id=STOCKS, name="Stocks", install_url="https://github.com/a/b")
    have = _plugin(id=CRYPTO, name="Crypto Pulse", installed=True)
    builtin = _plugin(id="omarchy.clock", name="Clock", first_party=True, builtin=True, installed=True)
    assert [item.id for item in pack.removable([open_, have, builtin])] == [CRYPTO]


def test_builtin_excluded() -> None:
    pack = get_pack("everyday")
    clock = _plugin(id="omarchy-overview", name="Overview", first_party=True, builtin=True, stars=99)
    assert pack.members([clock]) == []


def test_random_high_star_plugin_stays_out() -> None:
    pack = get_pack("finance")
    bing = _plugin(
        id="io.github.jestemkarol.bing-wallpaper",
        name="Bing Wallpaper",
        description="configurable market",
        category="Appearance",
        stars=99,
    )
    stats = _plugin(id="alvarosaavedra.market-stats", name="Market Stats", stars=80)
    stocks = _plugin(id=STOCKS, name="Stocks")
    assert [item.id for item in pack.members([bing, stats, stocks])] == [STOCKS]


def test_artist_not_solitaire_or_battery() -> None:
    pack = get_pack("artist")
    game = _plugin(id="nosignal.quattrolitaire", name="Solitaire", stars=99)
    battery = _plugin(id="tomv.battery-usage", name="Battery Usage", description="battery draw (watts)", stars=9)
    draw = _plugin(id="io.github.taha.draw-it", name="Draw-It")
    assert [item.id for item in pack.members([game, battery, draw])] == ["io.github.taha.draw-it"]


def test_gamer_not_youtube_music() -> None:
    pack = get_pack("gamer")
    yt = _plugin(id="levi.youtube-music", name="YouTube Music", stars=99)
    steam = _plugin(id="io.github.daventhedude.steam-friends", name="Steam Friends")
    assert [item.id for item in pack.members([yt, steam])] == ["io.github.daventhedude.steam-friends"]


def test_music_not_wwan_radio() -> None:
    pack = get_pack("music")
    lte = _plugin(id="lte", name="LTE", description="Toggle the WWAN radio")
    yt = _plugin(id="levi.youtube-music", name="YouTube Music")
    assert [item.id for item in pack.members([lte, yt])] == ["levi.youtube-music"]


def test_pack_matches_title_and_members() -> None:
    from omastore.packs import pack_matches

    pack = get_pack("finance")
    items = [_plugin(id=STOCKS, name="Stocks")]
    assert pack_matches(pack, "")
    assert pack_matches(pack, "FINANCE")
    assert pack_matches(pack, "stocks", items)
    assert not pack_matches(pack, "compiler")


def test_pack_markdown_marks_installed_first() -> None:
    from omastore.packs import pack_markdown

    pack = get_pack("finance")
    open_ = _plugin(id=STOCKS, name="Stocks", stars=9)
    have = _plugin(id=CRYPTO, name="Crypto Pulse", stars=1, installed=True, enabled=True)
    text = pack_markdown(pack, [open_, have])
    assert "HANCORE" in text
    assert "○ to install" in text
    assert text.index("● installed · on") < text.index("○ to install")
    assert text.index("**Crypto Pulse**") < text.index("**Stocks**")


def test_describe_pack_remove_lists_installed() -> None:
    from omastore.packs import describe_pack_remove

    pack = get_pack("finance")
    item = _plugin(
        id=STOCKS,
        name="Stocks[bold]",
        repo="https://github.com/a/stocks",
        installed=True,
    )
    text = describe_pack_remove(pack, [item])
    assert "remove 1 plugin from Finance?" in text
    assert "HANCORE" in text
    assert f"plugin:{STOCKS}" in text
    assert "plugin “Stocks[bold]”" in text
    assert "https://github.com/a/stocks" in text
    assert "omarchy plugin remove" in text
    assert "also in another pack" in text
    assert "official omarchy command" in text


def test_describe_pack_install_lists_repos() -> None:
    from omastore.packs import describe_pack_install

    pack = get_pack("finance")
    item = _plugin(
        id=STOCKS,
        name="Stocks[bold]",
        repo="https://github.com/a/stocks",
        warnings=["talks to the network"],
    )
    text = describe_pack_install(pack, [item])
    assert "install 1 plugin from Finance?" in text
    assert "HANCORE" in text
    assert f"plugin:{STOCKS}" in text
    assert "plugin “Stocks[bold]”" in text
    assert "https://github.com/a/stocks" in text
    assert "verification: verified" in text
    assert "- talks to the network" in text
    assert "unsandboxed" in text.lower()
    assert "official omarchy command" in text
