import subprocess

from omastore.actions import (
    ActionResult,
    apply_theme,
    describe_outdated_update,
    disable_plugin,
    enable_plugin,
    install,
    install_pack,
    remove,
    remove_pack,
    update_outdated,
)
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


def test_install_refuses_failed_scan_without_running_omarchy(monkeypatch) -> None:
    from omastore.scan import Finding, ScanResult

    def fail(*args, **kwargs):
        raise AssertionError("omarchy should not run when the scan fails")

    monkeypatch.setattr("omastore.actions.run_omarchy", fail)
    monkeypatch.setattr(
        "omastore.scan.scan_item",
        lambda item: ScanResult(
            item_key=item.key,
            item_id=item.id,
            item_name=item.name,
            kind=item.kind,
            repo=item.repo or "",
            verdict="block",
            findings=[Finding("block", "fetch", "", None, "scan failed: boom")],
            source="failed",
            error="boom",
        ),
    )
    result = install(_plugin())
    assert result.ok is False
    assert "scan failed" in result.message


def test_install_accept_scan_risks_still_runs_after_hits(monkeypatch) -> None:
    from omastore.scan import Finding, ScanResult

    class _Ok:
        returncode = 0
        stdout = "ok"
        stderr = ""

    monkeypatch.setattr("omastore.actions.run_omarchy", lambda *a, **k: _Ok())
    dirty = ScanResult(
        item_key="plugin:foo",
        item_id="foo",
        item_name="Foo",
        kind="plugin",
        repo="https://github.com/example/foo",
        verdict="block",
        findings=[Finding("block", "network", "a.qml", 1, "fetch(")],
        source="tree",
    )
    result = install(_plugin(), scan_result=dirty, accept_scan_risks=True)
    assert result.ok is True


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

    def fake_install(item, *, dry_run=False, **_kwargs):
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
        lambda item, *, dry_run=False, **_kwargs: calls.append(item.id) or ActionResult(True, [], "ok", ""),
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


def test_apply_theme_uses_omarchy_list_name(monkeypatch) -> None:
    seen: list[tuple] = []

    class _Ok:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake(*args, **kwargs):
        seen.append(args)
        return _Ok()

    monkeypatch.setattr("omastore.actions.run_omarchy", fake)
    monkeypatch.setattr(
        "omastore.local.load_local",
        lambda: (_ for _ in ()).throw(AssertionError("local_name should skip load_local")),
    )
    item = Item(
        kind="theme",
        id="retro-82",
        name="Retro '82",
        local_name="Retro 82",
        installed=True,
        builtin=True,
    )
    result = apply_theme(item)
    assert result.ok is True
    assert seen == [("theme", "set", "Retro 82")]


def test_update_refuses_failed_scan(monkeypatch) -> None:
    from omastore.actions import update
    from omastore.scan import Finding, ScanResult

    def fail(*args, **kwargs):
        raise AssertionError("omarchy should not run when the scan fails")

    monkeypatch.setattr("omastore.actions.run_omarchy", fail)
    dirty = ScanResult(
        item_key="plugin:foo",
        item_id="foo",
        item_name="Foo",
        kind="plugin",
        repo="https://github.com/example/foo",
        verdict="block",
        findings=[Finding("block", "fetch", "", None, "scan failed: boom")],
        source="failed",
        error="boom",
    )
    result = update(_plugin(installed=True, repo="https://github.com/example/foo"), scan_result=dirty)
    assert result.ok is False
    assert "scan failed" in result.message


def test_apply_plugin_fails(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise AssertionError("omarchy should not run when apply is for a plugin")

    monkeypatch.setattr("omastore.actions.run_omarchy", fail)
    result = apply_theme(_plugin())
    assert result.ok is False
    assert result.message == "apply is for themes"


class _Ok:
    returncode = 0
    stdout = "ok"
    stderr = ""


def test_remove_plugin_restores_hidden_first(monkeypatch) -> None:
    called: list[str] = []
    monkeypatch.setattr("omastore.local.restore_hidden_bar_widgets", lambda pid: called.append(pid) or [])
    monkeypatch.setattr("omastore.actions.run_omarchy", lambda *a, **k: _Ok())
    result = remove(_plugin(id="groups.plugin", installed=True))
    assert result.ok is True
    assert called == ["groups.plugin"]


def test_disable_plugin_restores_hidden_first(monkeypatch) -> None:
    called: list[str] = []
    monkeypatch.setattr("omastore.local.restore_hidden_bar_widgets", lambda pid: called.append(pid) or [])
    monkeypatch.setattr("omastore.actions.run_omarchy", lambda *a, **k: _Ok())
    result = disable_plugin(_plugin(id="groups.plugin", installed=True, enabled=True))
    assert result.ok is True
    assert called == ["groups.plugin"]


def _clean_scan(item: Item):
    from omastore.scan import ScanResult

    return ScanResult(
        item_key=item.key,
        item_id=item.id,
        item_name=item.name,
        kind=item.kind,
        repo=item.repo or item.install_url or "",
        verdict="clean",
        source="tree",
    )


def test_update_outdated_themes_share_one_command(monkeypatch) -> None:
    calls: list[tuple] = []

    class _Ok:
        returncode = 0
        stdout = "ok"
        stderr = ""

    monkeypatch.setattr("omastore.actions.run_omarchy", lambda *a, **k: calls.append(a) or _Ok())
    t1 = _theme(id="a", extra=True, installed=True, install_url="https://github.com/a/a")
    t2 = _theme(id="b", extra=True, installed=True, install_url="https://github.com/a/b")
    plugin = _plugin(id="c", installed=True, repo="https://github.com/a/c")
    rows = [t1, t2, plugin]
    results = update_outdated(rows, scans={item.key: _clean_scan(item) for item in rows})
    assert calls == [("theme", "update"), ("plugin", "update", "c", "--yes")]
    assert [item.id for item, _ in results] == ["a", "b", "c"]
    assert all(result.ok for _, result in results)


def test_update_outdated_stops_on_blocked_scan(monkeypatch) -> None:
    from omastore.scan import Finding, ScanResult

    def fail(*args, **kwargs):
        raise AssertionError("omarchy should not run when a member is blocked")

    monkeypatch.setattr("omastore.actions.run_omarchy", fail)
    a = _plugin(id="a", installed=True, repo="https://github.com/a/a")
    b = _plugin(id="b", installed=True, repo="https://github.com/a/b")
    dirty = ScanResult(
        item_key=b.key,
        item_id=b.id,
        item_name=b.name,
        kind=b.kind,
        repo=b.repo,
        verdict="block",
        findings=[Finding("block", "network", "a.qml", 1, "fetch(")],
        source="tree",
    )
    results = update_outdated([a, b], scans={a.key: _clean_scan(a), b.key: dirty})
    assert [item.id for item, _ in results] == ["b"]
    assert results[0][1].ok is False
    assert "fetch(" in results[0][1].message


def test_update_outdated_plugin_failure_stops(monkeypatch) -> None:
    calls: list[tuple] = []

    class _Ok:
        returncode = 0
        stdout = "ok"
        stderr = ""

    class _Bad:
        returncode = 1
        stdout = ""
        stderr = "boom"

    def fake(*args, **kwargs):
        calls.append(args)
        return _Bad() if args[:2] == ("plugin", "update") and args[2] == "b" else _Ok()

    monkeypatch.setattr("omastore.actions.run_omarchy", fake)
    a = _plugin(id="a", installed=True, repo="https://github.com/a/a")
    b = _plugin(id="b", installed=True, repo="https://github.com/a/b")
    c = _plugin(id="c", installed=True, repo="https://github.com/a/c")
    rows = [a, b, c]
    results = update_outdated(rows, scans={item.key: _clean_scan(item) for item in rows})
    assert [item.id for item, _ in results] == ["a", "b"]
    assert results[1][1].ok is False
    assert ("plugin", "update", "c", "--yes") not in calls


def test_describe_outdated_update_warns_about_theme_command() -> None:
    theme = _theme(id="lumon", extra=True, installed=True, install_url="https://github.com/a/lumon")
    plugin = _plugin(id="old", installed=True, repo="https://github.com/a/old", outdated=True)
    text = describe_outdated_update([theme, plugin])
    assert "update 2 outdated extras?" in text
    assert "every extra git theme" in text
    assert "theme:lumon" in text
    assert "plugin:old" in text


def test_remove_dry_run_does_not_restore(monkeypatch) -> None:
    called: list[str] = []
    monkeypatch.setattr("omastore.local.restore_hidden_bar_widgets", lambda pid: called.append(pid))
    remove(_plugin(id="groups.plugin", installed=True), dry_run=True)
    assert called == []
