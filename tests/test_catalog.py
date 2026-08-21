from omastore.catalog import Catalogs
from omastore.local import LocalState, overlay
from omastore.models import Item


def test_find_by_kind_and_name() -> None:
    catalogs = Catalogs(
        themes=[Item(kind="theme", id="lumon", name="Lumon")],
        plugins=[Item(kind="plugin", id="omarchy-overview", name="Overview")],
    )
    assert catalogs.find("lumon").kind == "theme"
    assert catalogs.find("theme:lumon").name == "Lumon"
    assert catalogs.find("plugin:omarchy-overview").name == "Overview"
    assert catalogs.find("missing") is None


def test_overlay_marks_current_and_extra() -> None:
    items = [
        Item(kind="theme", id="vantablack", name="Vantablack", builtin=True),
        Item(kind="theme", id="lumon", name="Lumon"),
        Item(kind="plugin", id="omarchy.clock", name="Clock", first_party=True),
    ]
    local = LocalState(
        current_theme="Vantablack",
        current_slug="vantablack",
        theme_names={"vantablack": "Vantablack", "lumon": "Lumon"},
        extra_slugs={"lumon"},
        stock_slugs={"vantablack"},
        plugins={"omarchy.clock": {"id": "omarchy.clock", "enabled": True, "firstParty": True, "name": "Clock"}},
    )
    out = {item.id: item for item in overlay(items, local)}
    assert out["vantablack"].current
    assert out["vantablack"].installed
    assert out["lumon"].extra
    assert out["omarchy.clock"].enabled


def test_overlay_matches_repo_basename_without_duplicate() -> None:
    items = [
        Item(
            kind="theme",
            id="lumon",
            name="Lumon",
            repo="https://github.com/OldJobobo/omarchy-lumon-theme",
        ),
    ]
    local = LocalState(extra_slugs={"omarchy-lumon-theme"})
    out = overlay(items, local)
    assert [item.id for item in out] == ["lumon"]
    assert out[0].installed
    assert out[0].extra
    assert not out[0].local_only
    assert not out[0].current


def test_overlay_matches_slugified_directory_name() -> None:
    items = [Item(kind="theme", id="tokyo-night", name="Tokyo Night")]
    local = LocalState(extra_slugs={"tokyo night", "tokyo-night"})
    out = overlay(items, local)
    assert [item.id for item in out] == ["tokyo-night"]
    assert out[0].installed
    assert out[0].extra
    assert not out[0].local_only
