from omastore.app import item_markdown, palette_text, sort_items
from omastore.models import Item


def test_sort_puts_current_first() -> None:
    items = [
        Item(kind="theme", id="a", name="A", stars=10),
        Item(kind="theme", id="b", name="B", stars=1, installed=True, current=True),
        Item(kind="theme", id="c", name="C", stars=50, installed=True),
    ]
    ordered = sort_items(items, "themes")
    assert [item.id for item in ordered] == ["b", "c", "a"]


def test_click_does_not_activate_until_already_selected() -> None:
    import time

    from omastore.app import OmaStoreApp

    app = OmaStoreApp()
    app._highlighted_at = time.monotonic()
    assert app._should_activate() is False
    app._highlighted_at = time.monotonic() - 1
    assert app._should_activate() is True


def test_list_prompt_marks_verification() -> None:
    from omastore.app import list_prompt

    verified = Item(kind="plugin", id="ok", name="Ok", verification="verified")
    unverified = Item(kind="plugin", id="raw", name="Raw", verification="unverified")
    builtin = Item(kind="plugin", id="clock", name="Clock", first_party=True)
    ok = list_prompt(verified)
    raw = list_prompt(unverified)
    clock = list_prompt(builtin)
    assert "✓" in ok.plain
    assert "-" in raw.plain
    assert "verified" not in ok.plain
    assert "unverified" not in raw.plain
    assert "green" in str(ok.spans)
    assert "yellow" in str(raw.spans)
    assert "Clock" in clock.plain


def test_list_prompt_keeps_stars_off_the_name() -> None:
    from omastore.app import list_prompt

    item = Item(kind="plugin", id="x", name="Very Long Plugin Name", stars=25634, verification="verified")
    line = list_prompt(item, width=28).plain
    assert "*25634" in line
    assert "★" not in line
    assert line.index("Very") < line.index("*25634")


def test_palette_skips_duplicates() -> None:
    text = palette_text({"background": "#111111", "color0": "#111111", "accent": "#7dcea0"})
    styles = [span.style for span in text.spans]
    assert "on #7dcea0" in styles
    assert styles.count("on #111111") == 1


def test_markdown_can_skip_readme_and_show_loader() -> None:
    item = Item(kind="theme", id="x", name="X", description="hello", readme="# huge")
    light = item_markdown(item, include_readme=False, loading=True)
    assert "hello" in light
    assert "Loading about" in light
    assert "# huge" not in light
    full = item_markdown(item, include_readme=True)
    assert "# huge" in full


def test_markdown_includes_warnings() -> None:
    item = Item(
        kind="theme",
        id="x",
        name="X",
        description="hello",
        author="limehawk",
        warnings=["installs a vscode extension"],
    )
    md = item_markdown(item)
    assert "hello" in md
    assert "installs a vscode extension" in md
    assert "By **limehawk**" in md


def test_preview_binding_exists() -> None:
    from omastore.app import OmaStoreApp

    assert any(binding.key == "p" and binding.action == "open_preview" for binding in OmaStoreApp.BINDINGS)


def test_shots_cache_starts_empty() -> None:
    from omastore.app import OmaStoreApp

    assert OmaStoreApp()._shots == {}


def test_markdown_mentions_extra_details_not_required() -> None:
    for extra in (True, False):
        item = Item(
            kind="plugin",
            id="demo",
            name="Demo",
            description="workspace overview",
            version="1.2.3",
            license="MIT",
            extra_details=extra,
        )
        try:
            md = item_markdown(item, extra_details=extra)
        except TypeError:
            md = item_markdown(item)
        assert "workspace overview" in md
        assert "1.2.3" in md
        assert "MIT" in md


def _ansi_shot_visible(ansi: str) -> bool:
    """#shot stays empty for blank ANSI and the 'no preview' placeholder."""
    return bool(ansi and ansi.strip() and ansi.strip() != "no preview")


def test_render_detail_hides_no_preview_text() -> None:
    import inspect

    from rich.text import Text

    from omastore.app import OmaStoreApp

    assert _ansi_shot_visible("") is False
    assert _ansi_shot_visible("no preview") is False
    assert _ansi_shot_visible("  no preview  ") is False
    assert _ansi_shot_visible("\n") is False
    assert _ansi_shot_visible("\x1b[31mhi\x1b[0m") is True

    source = inspect.getsource(OmaStoreApp._render_detail)
    assert "[p] preview" in source
    assert "no preview" in source

    app = OmaStoreApp()
    updates: dict[str, object] = {}

    class _Stub:
        def __init__(self, key: str) -> None:
            self.key = key

        def update(self, value: object = "") -> None:
            updates[self.key] = value

    app.query_one = lambda selector, cls=None: _Stub(selector)  # type: ignore[method-assign]
    item = Item(kind="theme", id="demo", name="Demo")

    for ansi in ("", "no preview", "  no preview  "):
        app._shots[item.key] = ansi
        app._render_detail(item, settled=True)
        assert updates["#shot"] == ""

    app._shots[item.key] = "\x1b[32mok\x1b[0m"
    app._render_detail(item, settled=True)
    assert isinstance(updates["#shot"], Text)
    assert updates["#shot"].plain  # type: ignore[union-attr]

    meta = updates["#meta"]
    assert "[p] preview" in (meta.plain if isinstance(meta, Text) else str(meta))
