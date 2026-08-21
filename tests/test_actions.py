import subprocess

from omastore.actions import apply_theme, enable_plugin, install
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


def test_apply_plugin_fails(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise AssertionError("omarchy should not run when apply is for a plugin")

    monkeypatch.setattr("omastore.actions.run_omarchy", fail)
    result = apply_theme(_plugin())
    assert result.ok is False
    assert result.message == "apply is for themes"
