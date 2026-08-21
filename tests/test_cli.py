from omastore.cli import build_parser, cmd_info, cmd_preview
from omastore.models import Item


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


def test_install_with_yes_calls_install(monkeypatch, capsys) -> None:
    item = _item(
        id="foo",
        name="Foo",
        install_url="https://github.com/example/foo",
        repo="https://github.com/example/foo",
    )
    called: list[object] = []
    monkeypatch.setattr("omastore.cli._load", lambda force=False: ([item], object()))
    monkeypatch.setattr("omastore.cli._find", lambda items, token: item)
    monkeypatch.setattr("omastore.cli.install", lambda *a, **k: called.append(item) or _Result(message="installed"))
    args = build_parser().parse_args(["--yes", "install", "plugin:foo"])
    assert args.yes is True
    assert args.func(args) == 0
    assert called == [item]
    assert capsys.readouterr().out.strip() == "installed"


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
