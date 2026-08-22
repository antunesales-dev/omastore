from omastore.cli import build_parser, cmd_changelog, cmd_info, cmd_pack, cmd_packs, cmd_preview, cmd_scan
from omastore.models import Item
from omastore.scan import Finding, ScanResult


class _Result:
    def __init__(self, ok: bool = True, message: str = "ok") -> None:
        self.ok = ok
        self.message = message


def _item(**kwargs) -> Item:
    data = {
        "kind": "plugin",
        "id": "foo",
        "name": "Foo",
    }
    data.update(kwargs)
    return Item(**data)


def _clean_scan(item: Item | None = None) -> ScanResult:
    target = item or _item()
    return ScanResult(
        item_key=target.key,
        item_id=target.id,
        item_name=target.name,
        kind=target.kind,
        repo=target.repo or target.install_url or "",
        verdict="clean",
        source="tree",
    )


def _dirty_scan(item: Item | None = None, *, failed: bool = False) -> ScanResult:
    target = item or _item()
    if failed:
        return ScanResult(
            item_key=target.key,
            item_id=target.id,
            item_name=target.name,
            kind=target.kind,
            repo=target.repo or "",
            verdict="block",
            findings=[Finding("block", "fetch", "", None, "scan failed: nope")],
            source="failed",
            error="nope",
        )
    return ScanResult(
        item_key=target.key,
        item_id=target.id,
        item_name=target.name,
        kind=target.kind,
        repo=target.repo or "",
        verdict="block",
        findings=[Finding("block", "network", "main.qml", 4, "fetch(")],
        source="tree",
    )


def _patch_clean_scan(monkeypatch) -> None:
    monkeypatch.setattr("omastore.scan.scan_item", lambda item, **_k: _clean_scan(item))
    monkeypatch.setattr("omastore.scan.scan_items", lambda items: [_clean_scan(item) for item in items])


def test_about_and_changelog_subcommands(capsys) -> None:
    from omastore import __version__

    about = build_parser().parse_args(["about"])
    assert about.func(about) == 0
    out = capsys.readouterr().out
    assert f"omastore {__version__}" in out
    assert "HANCORE" in out

    changelog = build_parser().parse_args(["changelog"])
    assert changelog.func is cmd_changelog
    assert changelog.func(changelog) == 0
    log = capsys.readouterr().out
    assert "0.2.5" in log
    assert "0.2.0" in log


def test_search_author_flag_parses() -> None:
    args = build_parser().parse_args(["search", "--author", "OldJobobo", "--kind", "theme"])
    from omastore.cli import _query_from_args

    query = _query_from_args(args)
    assert query.author == "oldjobobo"
    assert query.kind == "theme"


def test_list_outdated_flag_parses() -> None:
    args = build_parser().parse_args(["list", "--outdated", "--kind", "plugin"])
    assert args.outdated is True
    from omastore.cli import _query_from_args

    query = _query_from_args(args)
    assert query.status == "outdated"
    assert query.kind == "plugin"


def test_preview_subcommand_wires_cmd_preview() -> None:
    args = build_parser().parse_args(["preview", "plugin:foo"])
    assert args.func is cmd_preview
    assert args.id == "plugin:foo"


def test_info_subcommand_wires_cmd_info() -> None:
    args = build_parser().parse_args(["info", "plugin:x"])
    assert args.func is cmd_info
    assert args.id == "plugin:x"
    assert args.readme is False


def test_cmd_preview_opens_preview_offline(monkeypatch, capsys) -> None:
    item = _item()
    monkeypatch.setattr("omastore.cli._load", lambda force=False: ([item], object()))
    monkeypatch.setattr("omastore.cli._find", lambda items, token: item)
    monkeypatch.setattr(
        "omastore.previews.open_preview",
        lambda _item: {"ok": True, "message": "opened /tmp/x.png"},
    )
    args = build_parser().parse_args(["preview", "plugin:foo"])
    assert cmd_preview(args) == 0
    assert capsys.readouterr().out.strip() == "opened /tmp/x.png"


def test_cmd_preview_returns_error_when_open_fails(monkeypatch, capsys) -> None:
    item = _item()
    monkeypatch.setattr("omastore.cli._load", lambda force=False: ([item], object()))
    monkeypatch.setattr("omastore.cli._find", lambda items, token: item)
    monkeypatch.setattr(
        "omastore.previews.open_preview",
        lambda _item: {"ok": False, "message": "no preview image"},
    )
    args = build_parser().parse_args(["preview", "plugin:foo"])
    assert cmd_preview(args) == 1
    assert capsys.readouterr().out.strip() == "no preview image"


def test_cmd_info_enriches_thin_catalog(monkeypatch, capsys) -> None:
    item = _item(
        id="x",
        name="x",
        description="",
        version="",
        license="",
        category="",
        tags=[],
    )
    called: list[Item] = []

    def fake_enrich(target: Item) -> None:
        called.append(target)
        target.version = "1.2.3"
        target.license = "MIT"
        target.category = "Appearance"
        target.tags = ["hyprland"]
        target.extra_details = True

    monkeypatch.setattr("omastore.cli._load", lambda force=False: ([item], object()))
    monkeypatch.setattr("omastore.cli._find", lambda items, token: item)
    monkeypatch.setattr("omastore.enrich.enrich_item", fake_enrich)
    args = build_parser().parse_args(["info", "plugin:x"])
    assert cmd_info(args) == 0
    assert called == [item]
    out = capsys.readouterr().out
    assert "version: 1.2.3" in out
    assert "license: MIT" in out
    assert "category: Appearance" in out
    assert "tags: hyprland" in out
    assert "extra details from repository manifest" in out


def test_cmd_info_readme_fetches_when_empty(monkeypatch, capsys) -> None:
    item = _item(id="x", name="x", readme="")

    monkeypatch.setattr("omastore.cli._load", lambda force=False: ([item], object()))
    monkeypatch.setattr("omastore.cli._find", lambda items, token: item)
    monkeypatch.setattr("omastore.enrich.enrich_item", lambda _item: None)
    monkeypatch.setattr("omastore.catalog.fetch_readme", lambda _item: "# About\n")
    args = build_parser().parse_args(["info", "plugin:x", "--readme"])
    assert cmd_info(args) == 0
    out = capsys.readouterr().out
    assert "# About" in out


def test_apply_plugin_does_not_call_apply_theme(monkeypatch, capsys) -> None:
    item = _item(kind="plugin", id="foo", name="Foo", installed=True)
    called: list[object] = []
    monkeypatch.setattr("omastore.cli._load", lambda force=False: ([item], object()))
    monkeypatch.setattr("omastore.cli._find", lambda items, token: item)
    monkeypatch.setattr(
        "omastore.cli.apply_theme",
        lambda *a, **k: called.append((a, k)) or _Result(),
    )
    args = build_parser().parse_args(["apply", "plugin:foo"])
    assert args.func(args) == 1
    assert called == []
    assert capsys.readouterr().out.strip() == "cannot apply plugin:foo"


def test_install_without_yes_returns_2(monkeypatch, capsys) -> None:
    item = _item(
        id="foo",
        name="Foo",
        install_url="https://github.com/example/foo",
        repo="https://github.com/example/foo",
    )
    called: list[object] = []
    _patch_clean_scan(monkeypatch)
    monkeypatch.setattr("omastore.cli._load", lambda force=False: ([item], object()))
    monkeypatch.setattr("omastore.cli._find", lambda items, token: item)
    monkeypatch.setattr("omastore.cli.install", lambda *a, **k: called.append(item) or _Result())
    args = build_parser().parse_args(["install", "plugin:foo"])
    assert args.yes is False
    assert args.func(args) == 2
    assert called == []
    out = capsys.readouterr().out
    assert "plugin:foo" in out
    assert "pass --yes to proceed" in out


def test_remove_without_yes_warns_hidden_widgets(monkeypatch, capsys) -> None:
    item = _item(id="groups.plugin", name="Groups", installed=True)
    monkeypatch.setattr("omastore.cli._load", lambda force=False: ([item], object()))
    monkeypatch.setattr("omastore.cli._find", lambda items, token: item)
    monkeypatch.setattr(
        "omastore.local.layout_remove_warnings",
        lambda plugin_id, *, path=None: [
            "These widgets are hidden inside this plugin. They will be put back on the bar first: omarchy.clock"
        ],
    )
    called: list[object] = []
    monkeypatch.setattr("omastore.cli.remove", lambda *a, **k: called.append(item) or _Result())
    args = build_parser().parse_args(["remove", "plugin:groups.plugin"])
    assert args.func(args) == 2
    assert called == []
    out = capsys.readouterr().out
    assert "They will be put back on the bar first" in out
    assert "omarchy.clock" in out
    assert "pass --yes to proceed" in out


def test_install_with_yes_calls_install(monkeypatch, capsys) -> None:
    item = _item(
        id="foo",
        name="Foo",
        install_url="https://github.com/example/foo",
        repo="https://github.com/example/foo",
    )
    called: list[object] = []
    _patch_clean_scan(monkeypatch)
    monkeypatch.setattr("omastore.cli._load", lambda force=False: ([item], object()))
    monkeypatch.setattr("omastore.cli._find", lambda items, token: item)
    monkeypatch.setattr("omastore.cli.install", lambda *a, **k: called.append(item) or _Result(message="installed"))
    args = build_parser().parse_args(["--yes", "install", "plugin:foo"])
    assert args.yes is True
    assert args.func(args) == 0
    assert called == [item]
    assert capsys.readouterr().out.strip() == "installed"


def test_install_yes_alone_does_not_skip_failed_scan(monkeypatch, capsys) -> None:
    item = _item(
        id="foo",
        name="Foo",
        install_url="https://github.com/example/foo",
        repo="https://github.com/example/foo",
    )
    called: list[object] = []
    monkeypatch.setattr("omastore.scan.scan_item", lambda _item, **_k: _dirty_scan(item))
    monkeypatch.setattr("omastore.cli._load", lambda force=False: ([item], object()))
    monkeypatch.setattr("omastore.cli._find", lambda items, token: item)
    monkeypatch.setattr("omastore.cli.install", lambda *a, **k: called.append(item) or _Result())
    args = build_parser().parse_args(["--yes", "install", "plugin:foo"])
    assert args.func(args) == 2
    assert called == []
    out = capsys.readouterr().out
    assert "fetch(" in out
    assert "--i-accept-scan-risks" in out
    assert "pass --yes to proceed" not in out


def test_install_accept_scan_risks_still_needs_yes_when_dirty(monkeypatch, capsys) -> None:
    item = _item(
        id="foo",
        name="Foo",
        install_url="https://github.com/example/foo",
        repo="https://github.com/example/foo",
    )
    called: list[object] = []
    monkeypatch.setattr("omastore.scan.scan_item", lambda _item, **_k: _dirty_scan(item))
    monkeypatch.setattr("omastore.cli._load", lambda force=False: ([item], object()))
    monkeypatch.setattr("omastore.cli._find", lambda items, token: item)
    monkeypatch.setattr("omastore.cli.install", lambda *a, **k: called.append(item) or _Result())
    args = build_parser().parse_args(["--i-accept-scan-risks", "install", "plugin:foo"])
    assert args.func(args) == 2
    assert called == []
    assert "pass --yes to proceed" in capsys.readouterr().out


def test_install_yes_and_accept_scan_risks_proceeds(monkeypatch, capsys) -> None:
    item = _item(
        id="foo",
        name="Foo",
        install_url="https://github.com/example/foo",
        repo="https://github.com/example/foo",
    )
    called: list[object] = []
    monkeypatch.setattr("omastore.scan.scan_item", lambda _item, **_k: _dirty_scan(item))
    monkeypatch.setattr("omastore.cli._load", lambda force=False: ([item], object()))
    monkeypatch.setattr("omastore.cli._find", lambda items, token: item)
    monkeypatch.setattr("omastore.cli.install", lambda *a, **k: called.append(item) or _Result(message="installed"))
    args = build_parser().parse_args(["--yes", "--i-accept-scan-risks", "install", "plugin:foo"])
    assert args.accept_scan_risks is True
    assert args.func(args) == 0
    assert called == [item]


def test_install_crashed_scan_cannot_be_overridden(monkeypatch, capsys) -> None:
    item = _item(
        id="foo",
        name="Foo",
        install_url="https://github.com/example/foo",
        repo="https://github.com/example/foo",
    )
    called: list[object] = []
    monkeypatch.setattr("omastore.scan.scan_item", lambda _item, **_k: _dirty_scan(item, failed=True))
    monkeypatch.setattr("omastore.cli._load", lambda force=False: ([item], object()))
    monkeypatch.setattr("omastore.cli._find", lambda items, token: item)
    monkeypatch.setattr("omastore.cli.install", lambda *a, **k: called.append(item) or _Result())
    args = build_parser().parse_args(["--yes", "--i-accept-scan-risks", "install", "plugin:foo"])
    assert args.func(args) == 2
    assert called == []
    out = capsys.readouterr().out
    assert "fail closed" in out
    assert "scan failed" in out


def test_packs_subcommand_wires_cmd_packs() -> None:
    args = build_parser().parse_args(["packs"])
    assert args.func is cmd_packs


def test_pack_show_and_install_parse() -> None:
    show = build_parser().parse_args(["pack", "everyday"])
    assert show.func is cmd_pack
    assert show.target == "everyday"
    assert show.id is None
    install_cmd = build_parser().parse_args(["--yes", "pack", "install", "everyday"])
    assert install_cmd.func is cmd_pack
    assert install_cmd.target == "install"
    assert install_cmd.id == "everyday"
    assert install_cmd.yes is True
    tui = build_parser().parse_args(["tui", "--tab", "packs"])
    assert tui.tab == "packs"


def test_cmd_packs_lists_verified_only(monkeypatch, capsys) -> None:
    everyday = _item(
        id="omarchy-overview",
        name="Overview",
        verification="verified",
        tags=["workspaces"],
        category="Appearance",
        install_url="https://github.com/a/overview",
        repo="https://github.com/a/overview",
    )
    unverified = _item(
        id="raw",
        name="Raw",
        verification="unverified",
        tags=["workspaces"],
        category="Widgets",
        stars=99,
        install_url="https://github.com/a/raw",
    )
    monkeypatch.setattr("omastore.cli._load", lambda force=False: ([everyday, unverified], object()))
    args = build_parser().parse_args(["packs"])
    assert args.func(args) == 0
    out = capsys.readouterr().out
    assert "HANCORE" in out
    assert "everyday" in out
    assert "developer" in out
    assert "1 listed" in out
    assert "Raw" not in out


def test_pack_install_without_yes_returns_2(monkeypatch, capsys) -> None:
    item = _item(
        id="io.github.5d0tal1gat0r.stocks",
        name="Stocks",
        verification="verified",
        description="stock widget",
        category="Widgets",
        install_url="https://github.com/a/stocks",
        repo="https://github.com/a/stocks",
    )
    called: list[object] = []
    _patch_clean_scan(monkeypatch)
    monkeypatch.setattr("omastore.cli._load", lambda force=False: ([item], object()))
    monkeypatch.setattr("omastore.actions.install", lambda *a, **k: called.append(item) or _Result())
    args = build_parser().parse_args(["pack", "install", "finance"])
    assert args.func(args) == 2
    assert called == []
    out = capsys.readouterr().out
    assert "Finance" in out
    assert "plugin:io.github.5d0tal1gat0r.stocks" in out
    assert "https://github.com/a/stocks" in out
    assert "pass --yes to proceed" in out


def test_pack_install_with_yes_calls_install(monkeypatch, capsys) -> None:
    item = _item(
        id="io.github.5d0tal1gat0r.stocks",
        name="Stocks",
        verification="verified",
        description="stock widget",
        category="Widgets",
        install_url="https://github.com/a/stocks",
        repo="https://github.com/a/stocks",
    )
    called: list[object] = []
    _patch_clean_scan(monkeypatch)
    monkeypatch.setattr("omastore.cli._load", lambda force=False: ([item], object()))
    monkeypatch.setattr(
        "omastore.actions.install",
        lambda *a, **k: called.append(item) or _Result(message="installed"),
    )
    args = build_parser().parse_args(["--yes", "pack", "install", "finance"])
    assert args.func(args) == 0
    assert called == [item]
    assert "plugin:io.github.5d0tal1gat0r.stocks: installed" in capsys.readouterr().out


def test_pack_install_stops_on_first_blocked_member(monkeypatch, capsys) -> None:
    item = _item(
        id="io.github.5d0tal1gat0r.stocks",
        name="Stocks",
        verification="verified",
        description="stock widget",
        category="Widgets",
        install_url="https://github.com/a/stocks",
        repo="https://github.com/a/stocks",
    )
    called: list[object] = []
    monkeypatch.setattr("omastore.scan.scan_items", lambda items: [_dirty_scan(row) for row in items])
    monkeypatch.setattr("omastore.cli._load", lambda force=False: ([item], object()))
    monkeypatch.setattr("omastore.actions.install", lambda *a, **k: called.append(item) or _Result())
    args = build_parser().parse_args(["--yes", "pack", "install", "finance"])
    assert args.func(args) == 2
    assert called == []
    out = capsys.readouterr().out
    assert "finance blocked at plugin:io.github.5d0tal1gat0r.stocks" in out
    assert "fetch(" in out
    assert "--i-accept-scan-risks" in out


def test_pack_remove_without_yes_returns_2(monkeypatch, capsys) -> None:
    item = _item(
        id="io.github.5d0tal1gat0r.stocks",
        name="Stocks",
        verification="verified",
        description="stock widget",
        category="Widgets",
        installed=True,
        repo="https://github.com/a/stocks",
    )
    called: list[object] = []
    monkeypatch.setattr("omastore.cli._load", lambda force=False: ([item], object()))
    monkeypatch.setattr("omastore.actions.remove", lambda *a, **k: called.append(item) or _Result())
    args = build_parser().parse_args(["pack", "remove", "finance"])
    assert args.func(args) == 2
    assert called == []
    out = capsys.readouterr().out
    assert "remove 1 plugin from Finance?" in out
    assert "plugin:io.github.5d0tal1gat0r.stocks" in out
    assert "pass --yes to proceed" in out


def test_pack_remove_with_yes_calls_remove(monkeypatch, capsys) -> None:
    item = _item(
        id="io.github.5d0tal1gat0r.stocks",
        name="Stocks",
        verification="verified",
        description="stock widget",
        category="Widgets",
        installed=True,
        repo="https://github.com/a/stocks",
    )
    called: list[object] = []
    monkeypatch.setattr("omastore.cli._load", lambda force=False: ([item], object()))
    monkeypatch.setattr(
        "omastore.actions.remove",
        lambda *a, **k: called.append(item) or _Result(message="removed"),
    )
    args = build_parser().parse_args(["--yes", "pack", "uninstall", "finance"])
    assert args.target == "uninstall"
    assert args.func(args) == 0
    assert called == [item]
    assert "plugin:io.github.5d0tal1gat0r.stocks: removed" in capsys.readouterr().out


def test_pack_remove_nothing_installed(monkeypatch, capsys) -> None:
    item = _item(
        id="io.github.5d0tal1gat0r.stocks",
        name="Stocks",
        verification="verified",
        description="stock widget",
        category="Widgets",
        install_url="https://github.com/a/stocks",
    )
    monkeypatch.setattr("omastore.cli._load", lambda force=False: ([item], object()))
    args = build_parser().parse_args(["--yes", "pack", "remove", "finance"])
    assert args.func(args) == 0
    assert capsys.readouterr().out.strip() == "nothing to remove"


def test_scan_subcommand_wires_cmd_scan() -> None:
    args = build_parser().parse_args(["scan", "plugin:foo"])
    assert args.func is cmd_scan
    assert args.id == "plugin:foo"


def test_cmd_scan_prints_verdict(monkeypatch, capsys) -> None:
    item = _item(id="foo", name="Foo", install_url="https://github.com/example/foo", repo="https://github.com/example/foo")
    monkeypatch.setattr("omastore.cli._load", lambda force=False: ([item], object()))
    monkeypatch.setattr("omastore.cli._find", lambda items, token: item)
    monkeypatch.setattr("omastore.scan.scan_item", lambda _item, **_k: _dirty_scan(item))
    args = build_parser().parse_args(["scan", "plugin:foo"])
    assert args.func(args) == 2
    out = capsys.readouterr().out
    assert "verdict" in out or "block" in out
    assert "fetch(" in out


def test_pack_install_unknown_pack(capsys) -> None:
    args = build_parser().parse_args(["pack", "install", "gardening"])
    assert args.func(args) == 1
    assert "unknown pack" in capsys.readouterr().out


def test_pack_install_missing_id(capsys) -> None:
    args = build_parser().parse_args(["pack", "install"])
    assert args.func(args) == 2
    assert "usage: omastore pack install" in capsys.readouterr().out


def test_install_when_not_can_install_returns_1(monkeypatch, capsys) -> None:
    item = _item(
        id="foo",
        name="Foo",
        installed=True,
        install_url="https://github.com/example/foo",
    )
    called: list[object] = []
    monkeypatch.setattr("omastore.cli._load", lambda force=False: ([item], object()))
    monkeypatch.setattr("omastore.cli._find", lambda items, token: item)
    monkeypatch.setattr("omastore.cli.install", lambda *a, **k: called.append(item) or _Result())
    args = build_parser().parse_args(["--yes", "install", "plugin:foo"])
    assert args.func(args) == 1
    assert called == []
    assert capsys.readouterr().out.strip() == "cannot install plugin:foo"


def _outdated_plugin() -> Item:
    return _item(
        id="old",
        name="Old",
        installed=True,
        outdated=True,
        repo="https://github.com/a/old",
        install_url="https://github.com/a/old",
    )


def test_update_outdated_flag_parses() -> None:
    args = build_parser().parse_args(["update", "--outdated"])
    assert args.outdated is True
    assert args.id is None
    single = build_parser().parse_args(["update", "plugin:old"])
    assert single.id == "plugin:old"
    assert single.outdated is False


def test_update_without_id_or_outdated_prints_usage(capsys) -> None:
    args = build_parser().parse_args(["update"])
    assert args.func(args) == 2
    assert "usage: omastore update" in capsys.readouterr().out


def test_update_outdated_without_yes_returns_2(monkeypatch, capsys) -> None:
    item = _outdated_plugin()
    called: list[object] = []
    _patch_clean_scan(monkeypatch)
    monkeypatch.setattr("omastore.cli._load", lambda force=False: ([item], object()))
    monkeypatch.setattr("omastore.cli.update_outdated", lambda *a, **k: called.append(item) or [])
    args = build_parser().parse_args(["update", "--outdated"])
    assert args.func(args) == 2
    assert called == []
    out = capsys.readouterr().out
    assert "update 1 outdated extra?" in out
    assert "plugin:old" in out
    assert "pass --yes to proceed" in out


def test_update_outdated_with_yes_calls_helper(monkeypatch, capsys) -> None:
    item = _outdated_plugin()
    _patch_clean_scan(monkeypatch)
    monkeypatch.setattr("omastore.cli._load", lambda force=False: ([item], object()))
    monkeypatch.setattr(
        "omastore.cli.update_outdated",
        lambda items, **k: [(items[0], _Result(message="updated"))],
    )
    args = build_parser().parse_args(["--yes", "update", "--outdated"])
    assert args.func(args) == 0
    assert "plugin:old: updated" in capsys.readouterr().out


def test_update_outdated_blocked_scan_does_not_run(monkeypatch, capsys) -> None:
    item = _outdated_plugin()
    called: list[object] = []
    monkeypatch.setattr("omastore.scan.scan_items", lambda items: [_dirty_scan(row) for row in items])
    monkeypatch.setattr("omastore.cli._load", lambda force=False: ([item], object()))
    monkeypatch.setattr("omastore.cli.update_outdated", lambda *a, **k: called.append(item) or [])
    args = build_parser().parse_args(["--yes", "update", "--outdated"])
    assert args.func(args) == 2
    assert called == []
    out = capsys.readouterr().out
    assert "update --outdated blocked at plugin:old" in out
    assert "--i-accept-scan-risks" in out


def test_update_outdated_nothing(monkeypatch, capsys) -> None:
    monkeypatch.setattr("omastore.cli._load", lambda force=False: ([], object()))
    args = build_parser().parse_args(["--yes", "update", "--outdated"])
    assert args.func(args) == 0
    assert capsys.readouterr().out.strip() == "nothing outdated"
