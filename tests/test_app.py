from omastore.app import (
    action_groups,
    action_hints,
    filter_bar,
    format_action_hints,
    item_markdown,
    palette_text,
    sort_items,
)
from omastore.filters import Query
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


def test_list_prompt_marks_installed_themes() -> None:
    from omastore.app import list_prompt

    current = Item(kind="theme", id="spacex", name="Spacex", installed=True, current=True)
    extra = Item(kind="theme", id="lumon", name="Lumon", installed=True, extra=True)
    catalog = Item(kind="theme", id="void", name="Void")
    on = list_prompt(current)
    have = list_prompt(extra)
    missing = list_prompt(catalog)
    assert "●" in on.plain
    assert "●" in have.plain
    assert "○" in missing.plain
    assert "green" in str(on.spans)
    assert "cyan" in str(have.spans)
    assert "dim" in str(missing.spans)


def test_try_requires_installed_theme() -> None:
    from omastore.app import OmaStoreApp

    app = OmaStoreApp()
    app.selected = Item(kind="theme", id="void", name="Void")
    notes: list[str] = []
    app.notify = lambda message, **_kwargs: notes.append(str(message))  # type: ignore[method-assign]
    app.action_try_theme()
    assert notes
    assert "not installed" in notes[0]


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


def test_shot_pixels_are_even_16_by_9() -> None:
    from omastore.app import OmaStoreApp

    width, height = OmaStoreApp()._shot_pixels()
    assert width >= 24
    assert height % 2 == 0
    assert 20 <= height <= 40


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


def test_filter_bar_is_readable() -> None:
    assert "is:all" not in filter_bar(Query())
    assert "stars" in filter_bar(Query())
    assert "f filter" in filter_bar(Query())
    bar = filter_bar(Query(status="installed", sort="name"))
    assert "installed" in bar
    assert "name" in bar


def test_action_groups_split_do_and_open() -> None:
    item = Item(
        kind="theme",
        id="lumon",
        name="Lumon",
        installed=True,
        extra=True,
        install_url="https://github.com/example/lumon",
    )
    do, look = action_groups(item)
    assert "[t] try" in do
    assert "[p] preview" in look
    assert "[p] preview" not in do


def test_action_hints_wrap_onto_two_lines() -> None:
    item = Item(
        kind="theme",
        id="lumon",
        name="Lumon",
        installed=True,
        extra=True,
        install_url="https://github.com/example/lumon",
    )
    hints = action_hints(item)
    assert "[t] try" in hints
    assert "[p] preview" in hints
    packed = format_action_hints(hints, width=40)
    assert "\n" in packed
    lines = packed.split("\n")
    assert 2 <= len(lines) <= 3
    assert all(len(line) <= 48 for line in lines)
    assert "    " not in packed


def test_render_detail_hides_empty_shots() -> None:
    from rich.text import Text

    from omastore.app import OmaStoreApp, ShotVisual

    app = OmaStoreApp()
    updates: dict[str, object] = {}

    class _Stub:
        def __init__(self, key: str) -> None:
            self.key = key

        def update(self, value: object = "") -> None:
            updates[self.key] = value

    app.query_one = lambda selector, cls=None: _Stub(selector)  # type: ignore[method-assign]
    item = Item(kind="theme", id="demo", name="Demo")

    app._shots[item.key] = []
    app._render_detail(item, settled=True)
    assert updates["#shot"] == ""

    cells = [[((255, 0, 0), (0, 0, 255)), ((0, 255, 0), (255, 255, 255))]]
    app._shots[item.key] = cells
    app._render_detail(item, settled=True)
    visual = updates["#shot"]
    assert isinstance(visual, ShotVisual)
    strips = visual.render_strips(2, None, None, None)  # type: ignore[arg-type]
    assert len(strips) == 1
    assert strips[0].text == "▀▀"

    meta = updates["#meta"]
    assert "[p] preview" in (meta.plain if isinstance(meta, Text) else str(meta))
