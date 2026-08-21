from omastore.cli import build_parser, cmd_info, cmd_preview
from omastore.models import Item


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
