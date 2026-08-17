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
