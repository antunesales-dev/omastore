from pathlib import Path

from omastore.local import LocalState, installed_plugin_path, installed_theme_path
from omastore.models import Item
from omastore import updates


OLD = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
NEW = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


def _theme(**kwargs) -> Item:
    data = {
        "kind": "theme",
        "id": "lumon",
        "name": "Lumon",
        "installed": True,
        "extra": True,
        "repo": "https://github.com/example/lumon",
    }
    data.update(kwargs)
    return Item(**data)


def _plugin(**kwargs) -> Item:
    data = {
        "kind": "plugin",
        "id": "omarchy-overview",
        "name": "Overview",
        "installed": True,
        "first_party": False,
        "repo": "https://github.com/example/overview",
    }
    data.update(kwargs)
    return Item(**data)


def test_is_outdated_property() -> None:
    item = _theme(outdated=True, installed_rev=OLD, latest_rev=NEW)
    assert item.is_outdated
    assert not _theme().is_outdated


def test_mark_outdated_theme_behind_ls_remote(tmp_path: Path, monkeypatch) -> None:
    theme_dir = tmp_path / "themes" / "lumon"
    theme_dir.mkdir(parents=True)
    monkeypatch.setattr(updates, "installed_theme_path", lambda slug: theme_dir if slug == "lumon" else None)
    monkeypatch.setattr(updates, "git_head", lambda path: OLD if path == theme_dir else "")
    monkeypatch.setattr(updates, "git_ls_remote", lambda repo, **kwargs: NEW)

    item = _theme()
    updates.mark_outdated([item])
    assert item.installed_rev == OLD
    assert item.latest_rev == NEW
    assert item.outdated
    assert updates.outdated_items([item]) == [item]


def test_mark_outdated_uses_catalog_commit_not_ls_remote(tmp_path: Path, monkeypatch) -> None:
    theme_dir = tmp_path / "themes" / "lumon"
    theme_dir.mkdir(parents=True)
    monkeypatch.setattr(updates, "installed_theme_path", lambda slug: theme_dir)
    monkeypatch.setattr(updates, "git_head", lambda path: OLD)

    def fail_remote(repo, **kwargs):
        raise AssertionError("ls-remote should not run when catalog commit is present")

    monkeypatch.setattr(updates, "git_ls_remote", fail_remote)
    item = _theme()
    item.listingValidatedCommit = NEW
    updates.mark_outdated([item])
    assert item.latest_rev == NEW
    assert item.outdated


def test_mark_outdated_same_rev_is_current(tmp_path: Path, monkeypatch) -> None:
    plugin_dir = tmp_path / "plugins" / "omarchy-overview"
    plugin_dir.mkdir(parents=True)
    monkeypatch.setattr(updates, "installed_plugin_path", lambda plugin_id: plugin_dir)
    monkeypatch.setattr(updates, "git_head", lambda path: OLD)
    monkeypatch.setattr(updates, "git_ls_remote", lambda repo, **kwargs: OLD[:12])

    item = _plugin()
    updates.mark_outdated([item])
    assert item.installed_rev == OLD
    assert item.latest_rev == OLD[:12]
    assert not item.outdated
    assert updates.outdated_items([item]) == []


def test_skips_builtin_stock_and_first_party(monkeypatch) -> None:
    monkeypatch.setattr(updates, "git_head", lambda path: OLD)
    monkeypatch.setattr(updates, "git_ls_remote", lambda repo, **kwargs: NEW)
    monkeypatch.setattr(updates, "installed_theme_path", lambda slug: Path("/tmp") / slug)
    monkeypatch.setattr(updates, "installed_plugin_path", lambda plugin_id: Path("/tmp") / plugin_id)

    stock = _theme(id="vantablack", name="Vantablack", extra=False, builtin=True)
    first = _plugin(id="omarchy.clock", name="Clock", first_party=True, builtin=True)
    updates.mark_outdated([stock, first])
    assert not stock.outdated
    assert stock.installed_rev == ""
    assert not first.outdated
    assert first.installed_rev == ""


def test_skips_uninstalled_community_plugin(monkeypatch) -> None:
    monkeypatch.setattr(updates, "git_head", lambda path: OLD)
    monkeypatch.setattr(updates, "git_ls_remote", lambda repo, **kwargs: NEW)
    item = _plugin(installed=False)
    updates.mark_outdated([item])
    assert not item.outdated
    assert item.installed_rev == ""


def test_local_state_marks_extra_theme_and_skips_first_party(tmp_path: Path, monkeypatch) -> None:
    theme_dir = tmp_path / "themes" / "void"
    theme_dir.mkdir(parents=True)
    monkeypatch.setattr(updates, "installed_theme_path", lambda slug: theme_dir if slug == "void" else None)
    monkeypatch.setattr(updates, "installed_plugin_path", lambda plugin_id: tmp_path / plugin_id)
    monkeypatch.setattr(updates, "git_head", lambda path: OLD)
    monkeypatch.setattr(updates, "git_ls_remote", lambda repo, **kwargs: NEW)

    extra = Item(kind="theme", id="void", name="Void", repo="https://github.com/example/void")
    plugin = _plugin(id="omarchy.clock", first_party=False, installed=False)
    local = LocalState(
        extra_slugs={"void"},
        plugins={"omarchy.clock": {"id": "omarchy.clock", "firstParty": True}},
    )
    updates.mark_outdated([extra, plugin], local)
    assert extra.outdated
    assert not plugin.outdated


def test_git_failure_leaves_not_outdated(tmp_path: Path, monkeypatch) -> None:
    theme_dir = tmp_path / "themes" / "lumon"
    theme_dir.mkdir(parents=True)
    monkeypatch.setattr(updates, "installed_theme_path", lambda slug: theme_dir)
    monkeypatch.setattr(updates, "git_head", lambda path: (_ for _ in ()).throw(RuntimeError("git exploded")))
    item = _theme()
    updates.mark_outdated([item])
    assert not item.outdated


def test_missing_path_or_head_is_not_outdated(monkeypatch) -> None:
    monkeypatch.setattr(updates, "installed_theme_path", lambda slug: None)
    monkeypatch.setattr(updates, "git_head", lambda path: OLD)
    monkeypatch.setattr(updates, "git_ls_remote", lambda repo, **kwargs: NEW)
    missing = _theme()
    updates.mark_outdated([missing])
    assert not missing.outdated

    monkeypatch.setattr(updates, "installed_theme_path", lambda slug: Path("/tmp/lumon"))
    monkeypatch.setattr(updates, "git_head", lambda path: "")
    no_git = _theme()
    updates.mark_outdated([no_git])
    assert not no_git.outdated
    assert no_git.installed_rev == ""


def test_git_ls_remote_uses_cache(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    calls = {"n": 0}

    def fake_run(*args, **kwargs):
        calls["n"] += 1
        return type("R", (), {"returncode": 0, "stdout": f"{NEW}\tHEAD\n", "stderr": ""})()

    monkeypatch.setattr(updates.subprocess, "run", fake_run)
    repo = "https://github.com/example/lumon"
    assert updates.git_ls_remote(repo) == NEW
    assert updates.git_ls_remote(repo) == NEW
    assert calls["n"] == 1
    cache = tmp_path / "cache" / "omastore" / "upstream-revs.json"
    assert cache.is_file()


def test_git_ls_remote_refreshes_expired_cache(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    repo = "https://github.com/example/lumon"
    cache_dir = tmp_path / "cache" / "omastore"
    cache_dir.mkdir(parents=True)
    (cache_dir / "upstream-revs.json").write_text(
        '{"https://github.com/example/lumon": {"rev": "%s", "ts": 1}}' % OLD,
        encoding="utf-8",
    )
    monkeypatch.setattr(updates.subprocess, "run", lambda *a, **k: type("R", (), {"returncode": 0, "stdout": f"{NEW}\tHEAD\n", "stderr": ""})())
    assert updates.git_ls_remote(repo) == NEW


def test_git_ls_remote_failure_is_empty(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setattr(updates.subprocess, "run", lambda *a, **k: type("R", (), {"returncode": 1, "stdout": "", "stderr": "fail"})())
    assert updates.git_ls_remote("https://github.com/example/lumon") == ""


def test_installed_paths(tmp_path: Path, monkeypatch) -> None:
    from omastore import local

    monkeypatch.setattr(local, "_home", lambda: tmp_path)
    theme = tmp_path / ".config" / "omarchy" / "themes" / "Lumon"
    plugin = tmp_path / ".config" / "omarchy" / "plugins" / "omarchy-overview"
    theme.mkdir(parents=True)
    plugin.mkdir(parents=True)
    assert installed_theme_path("lumon") == theme
    assert installed_plugin_path("omarchy-overview") == plugin
    assert installed_theme_path("missing") is None


def test_theme_preview_file_prefers_user_copy(tmp_path: Path, monkeypatch) -> None:
    from omastore import local
    from omastore.local import theme_preview_file

    monkeypatch.setattr(local, "_home", lambda: tmp_path)
    monkeypatch.setenv("OMARCHY_PATH", str(tmp_path / "omarchy"))
    user = tmp_path / ".config" / "omarchy" / "themes" / "tokyo-night"
    stock = tmp_path / "omarchy" / "themes" / "tokyo-night"
    user.mkdir(parents=True)
    stock.mkdir(parents=True)
    (stock / "preview.png").write_bytes(b"stock")
    assert theme_preview_file("tokyo-night").read_bytes() == b"stock"
    (user / "preview.png").write_bytes(b"user")
    assert theme_preview_file("tokyo-night").read_bytes() == b"user"
    assert theme_preview_file("missing") is None
