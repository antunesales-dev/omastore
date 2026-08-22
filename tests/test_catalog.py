from omastore.catalog import Catalogs, catalog_cache_age_label
from omastore.local import LocalState, overlay
from omastore.models import Item


def test_catalog_cache_age_label(tmp_path, monkeypatch) -> None:
    from omastore import catalog as catalog_mod

    monkeypatch.setattr(catalog_mod, "cache_dir", lambda: tmp_path)
    assert catalog_cache_age_label(now=1_000_000) == ""
    (tmp_path / "themes-data.json").write_text("[]", encoding="utf-8")
    (tmp_path / "plugins-catalog.json").write_text("{}", encoding="utf-8")
    now = 1_000_000.0
    for name in ("themes-data.json", "plugins-catalog.json"):
        os_utime = __import__("os").utime
        os_utime(tmp_path / name, (now - 5 * 3600, now - 5 * 3600))
    assert catalog_cache_age_label(now=now) == "5h old · r refresh"


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


def test_overlay_sets_omarchy_list_name_for_apostrophe_title() -> None:
    items = [
        Item(
            kind="theme",
            id="retro-82",
            name="Retro '82",
            repo="https://github.com/OldJobobo/omarchy-retro-82-theme",
        )
    ]
    local = LocalState(
        theme_names={"omarchy-retro-82-theme": "Retro 82"},
        extra_slugs={"omarchy-retro-82-theme"},
    )
    out = overlay(items, local)
    assert out[0].installed
    assert out[0].extra
    assert not out[0].builtin
    assert out[0].local_name == "Retro 82"
    from omastore.local import omarchy_theme_name

    assert omarchy_theme_name(out[0], local) == "Retro 82"


def test_overlay_title_does_not_inherit_stock() -> None:
    items = [
        Item(
            kind="theme",
            id="oldjobobo-retro-82",
            name="Retro '82",
            repo="https://github.com/OldJobobo/omarchy-retro-82-theme",
        )
    ]
    local = LocalState(
        theme_names={"retro-82": "Retro 82"},
        stock_slugs={"retro-82"},
    )
    out = overlay(items, local)
    catalog = next(item for item in out if not item.local_only)
    assert catalog.id == "oldjobobo-retro-82"
    assert catalog.installed is False
    assert catalog.builtin is False
    assert any(item.local_only and item.id == "retro-82" for item in out)
    assert len([item for item in out if item.key == "theme:retro-82"]) == 1
    assert len([item for item in out if item.key == "theme:oldjobobo-retro-82"]) == 1


def test_overlay_same_id_as_stock_is_one_row() -> None:
    items = [
        Item(
            kind="theme",
            id="lumon",
            name="Lumon",
            repo="https://github.com/OldJobobo/omarchy-lumon-theme",
        )
    ]
    local = LocalState(
        theme_names={"lumon": "Lumon"},
        stock_slugs={"lumon"},
    )
    out = overlay(items, local)
    assert [item.id for item in out] == ["lumon"]
    assert out[0].installed
    assert out[0].builtin
    assert not out[0].local_only


def test_overlay_clears_removed_plugins_and_skips_local_only_dupes() -> None:
    plugin = Item(kind="plugin", id="demo", name="Demo")
    local = LocalState(plugins={"demo": {"id": "demo", "enabled": True, "name": "Demo"}})
    once = overlay([plugin], local)
    assert once[0].installed is True
    assert once[0].enabled is True
    gone = overlay(once, LocalState(plugins={}))
    catalog = [item for item in gone if item.id == "demo"]
    assert len(catalog) == 1
    assert catalog[0].installed is False
    assert catalog[0].enabled is False
    extra = LocalState(theme_names={"secret": "Secret"}, extra_slugs={"secret"})
    first = overlay([], extra)
    assert [item.id for item in first] == ["secret"]
    second = overlay(first, extra)
    assert [item.id for item in second] == ["secret"]


def test_overlay_matches_slugified_directory_name() -> None:
    items = [Item(kind="theme", id="tokyo-night", name="Tokyo Night")]
    local = LocalState(extra_slugs={"tokyo night", "tokyo-night"})
    out = overlay(items, local)
    assert [item.id for item in out] == ["tokyo-night"]
    assert out[0].installed
    assert out[0].extra
    assert not out[0].local_only
