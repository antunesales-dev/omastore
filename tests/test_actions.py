import subprocess

from omastore.actions import ActionResult, apply_theme, enable_plugin, install, install_pack, remove_pack
from omastore.models import Item


def _theme(**kwargs) -> Item:
    data = {
        "kind": "theme",
        "id": "lumon",
        "name": "Lumon",
        "install_url": "https://github.com/example/lumon",
    }
    data.update(kwargs)
    return Item(**data)


def _plugin(**kwargs) -> Item:
    data = {
        "kind": "plugin",
        "id": "foo",
        "name": "Foo",
        "install_url": "https://github.com/example/foo",
    }
    data.update(kwargs)
    return Item(**data)


def test_file_not_found_maps_to_missing_cli(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise FileNotFoundError("omarchy")

    monkeypatch.setattr("omastore.actions.run_omarchy", boom)
    result = enable_plugin(_plugin())
    assert result.ok is False
    assert result.stderr == "omarchy CLI not found on PATH"
    assert result.message == "omarchy CLI not found on PATH"


def test_timeout_maps_to_omarchy_timed_out(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise subprocess.TimeoutExpired("omarchy", kwargs.get("timeout") or 30)

    monkeypatch.setattr("omastore.actions.run_omarchy", boom)
    result = enable_plugin(_plugin())
    assert result.ok is False
    assert result.message == "omarchy timed out"


def test_install_refuses_disallowed_url(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise AssertionError("omarchy should not run for a refused install url")

    monkeypatch.setattr("omastore.actions.run_omarchy", fail)
    tree = _theme(install_url="https://github.com/basecamp/omarchy/tree/quattro/themes/x")
    result = install(tree)
    assert result.ok is False
    assert result.message == "refused install url"

    remote = _plugin(install_url="https://evil.example/a/b")
    result = install(remote)
    assert result.ok is False
    assert result.message == "refused install url"


def test_install_pack_stops_on_failure(monkeypatch) -> None:
    calls: list[str] = []

    def fake_install(item, *, dry_run=False):
        calls.append(item.id)
        if item.id == "b":
            return ActionResult(False, [], "", "boom")
        return ActionResult(True, [], "ok", "")

    monkeypatch.setattr("omastore.actions.install", fake_install)
    a = _plugin(id="a", name="A")
    b = _plugin(id="b", name="B")
    c = _plugin(id="c", name="C")
    results = install_pack([a, b, c])
    assert [item.id for item, _ in results] == ["a", "b"]
    assert calls == ["a", "b"]
    assert results[1][1].ok is False
    assert results[1][1].message == "boom"


def test_install_pack_skips_already_installed(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        "omastore.actions.install",
        lambda item, *, dry_run=False: calls.append(item.id) or ActionResult(True, [], "ok", ""),
    )
    have = _plugin(id="have", name="Have", installed=True)
    open_ = _plugin(id="open", name="Open")
    results = install_pack([have, open_])
    assert [item.id for item, _ in results] == ["open"]
    assert calls == ["open"]


def test_remove_pack_stops_on_failure(monkeypatch) -> None:
    calls: list[str] = []

    def fake_remove(item, *, dry_run=False):
        calls.append(item.id)
        if item.id == "b":
            return ActionResult(False, [], "", "boom")
        return ActionResult(True, [], "ok", "")

    monkeypatch.setattr("omastore.actions.remove", fake_remove)
    a = _plugin(id="a", name="A", installed=True)
    b = _plugin(id="b", name="B", installed=True)
    c = _plugin(id="c", name="C", installed=True)
    results = remove_pack([a, b, c])
    assert [item.id for item, _ in results] == ["a", "b"]
    assert calls == ["a", "b"]
    assert results[1][1].ok is False


def test_remove_pack_skips_not_installed(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        "omastore.actions.remove",
        lambda item, *, dry_run=False: calls.append(item.id) or ActionResult(True, [], "ok", ""),
    )
    missing = _plugin(id="missing", name="Missing")
    have = _plugin(id="have", name="Have", installed=True)
    results = remove_pack([missing, have])
    assert [item.id for item, _ in results] == ["have"]
    assert calls == ["have"]


def test_apply_plugin_fails(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise AssertionError("omarchy should not run when apply is for a plugin")

    monkeypatch.setattr("omastore.actions.run_omarchy", fail)
    result = apply_theme(_plugin())
    assert result.ok is False
    assert result.message == "apply is for themes"
