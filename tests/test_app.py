from omastore.app import (
    action_groups,
    action_hints,
    confirm_prompt,
    filter_bar,
    format_action_hints,
    format_status,
    item_markdown,
    next_shot_zoom,
    pack_prompt,
    shot_crop_box,
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


def test_click_never_activates() -> None:
    """Click on the list only selects; it does not call _act."""
    from types import SimpleNamespace

    from omastore.app import OmaStoreApp

    app = OmaStoreApp()
    app.selected = Item(
        kind="theme",
        id="void",
        name="Void",
        install_url="https://github.com/x/void",
        install_available=True,
    )
    acts: list[str] = []
    app._act = lambda name: acts.append(name)  # type: ignore[method-assign]
    app._select_key = lambda *args, **kwargs: None  # type: ignore[method-assign]

    app._click_list()
    assert app._list_pointer is True
    event = SimpleNamespace(option_id="theme__void")
    app.on_option_selected(event)  # type: ignore[arg-type]
    assert acts == []
    assert app._list_pointer is False

    app.on_option_selected(event)  # type: ignore[arg-type]
    assert acts == ["install"]


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
    from omastore.app import OmaStoreApp, ShotScreen

    assert any(binding.key == "p" and binding.action == "open_preview" for binding in OmaStoreApp.BINDINGS)
    shot_keys = ",".join(binding.key for binding in ShotScreen.BINDINGS)
    assert "p" not in shot_keys.split(",")
    assert any(binding.action == "open_file" and "o" in binding.key.split(",") for binding in ShotScreen.BINDINGS)


def test_shot_zoom_steps() -> None:
    assert next_shot_zoom(1.0, 1) == 1.5
    assert next_shot_zoom(1.5, 1) == 2.0
    assert next_shot_zoom(4.0, 1) == 4.0
    assert next_shot_zoom(2.0, -1) == 1.5
    assert next_shot_zoom(1.0, -1) == 1.0


def test_shot_bar_lists_keys() -> None:
    from omastore.app import ShotScreen

    bar = ShotScreen("/tmp/preview.png", "Localhost")._bar()
    assert "Localhost" in bar
    lines = bar.split("\n")
    assert len(lines) == 2
    assert "[+] in" in lines[1]
    assert "[arrows] pan" in lines[1]
    assert "[o] open" in lines[1]
    assert "[esc] close" in lines[1]


def test_shot_crop_box_pans_from_center() -> None:
    assert shot_crop_box(100, 80, 1.0, 0, 0) == (0, 0, 100, 80)
    assert shot_crop_box(100, 80, 2.0, 0, 0) == (25, 20, 75, 60)
    left, top, right, bottom = shot_crop_box(100, 80, 2.0, 1.0, 0)
    assert left == 50 and right == 100
    left, top, right, bottom = shot_crop_box(100, 80, 2.0, -1.0, -1.0)
    assert (left, top) == (0, 0)
    left, top, right, bottom = shot_crop_box(100, 80, 2.0, 1.0, 1.0)
    assert right == 100 and bottom == 80


def test_shot_arrow_bindings_pan() -> None:
    from omastore.app import ShotScreen

    actions = {binding.action: binding.key for binding in ShotScreen.BINDINGS}
    assert "left" in actions["pan_left"].split(",")
    assert "right" in actions["pan_right"].split(",")
    assert "up" in actions["pan_up"].split(",")
    assert "down" in actions["pan_down"].split(",")
    screen = ShotScreen("/tmp/preview.png")
    screen.zoom = 2.0
    screen._apply_zoom = lambda: None  # type: ignore[method-assign]
    screen.action_pan_right()
    assert screen.pan_x > 0
    screen.action_pan_left()
    screen.action_pan_left()
    assert screen.pan_x < 0
    screen.action_zoom_fit()
    assert screen.zoom == 1.0
    assert screen.pan_x == 0.0
    assert screen.pan_y == 0.0


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


def test_filter_bar_is_readable() -> None:
    assert "is:all" not in filter_bar(Query())
    assert "stars" in filter_bar(Query())
    assert "0 reset" in filter_bar(Query())
    bar = filter_bar(Query(status="installed", sort="name"))
    assert "installed" in bar
    assert "name" in bar
    plugins = filter_bar(Query(), "plugins")
    assert "0 reset" in plugins
    assert " y " in plugins or plugins.endswith(" y") or "  y  " in plugins
    not_installed = filter_bar(Query(status="not-installed"), "plugins")
    assert "not installed" in not_installed
    assert "limehawk" not in filter_bar(Query())
    assert "HANCORE" not in filter_bar(Query(), "plugins")


def test_status_line_skips_credits_and_stays_short() -> None:
    line = format_status(
        "304 themes  ·  828 plugins  ·  69 installed",
        785,
        trying="Spacex",
        previous="Spacex",
        outdated=1,
    )
    assert "limehawk" not in line
    assert "HANCORE" not in line
    assert "?" not in line
    assert "trying Spacex" in line
    assert "[b] back" in line
    assert "back to Spacex" not in line
    assert "1 outdated" in line
    assert "785 shown" in line


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
    assert "[p] zoom" in look
    assert "[p] zoom" not in do


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
    assert "[p] zoom" in hints
    packed = format_action_hints(hints, width=40)
    assert "\n" in packed
    lines = packed.split("\n")
    assert 2 <= len(lines) <= 3
    assert all(len(line) <= 48 for line in lines)
    assert "    " not in packed


def test_render_detail_hides_empty_shots() -> None:
    from rich.text import Text

    from omastore.app import OmaStoreApp

    app = OmaStoreApp()
    stubs: dict[str, _ShotStub] = {}

    class _ShotStub:
        def __init__(self, key: str) -> None:
            self.key = key
            self.image = None
            self.display = True

        def update(self, value: object = "") -> None:
            self.value = value

    def query_one(selector, cls=None):
        if selector not in stubs:
            stubs[selector] = _ShotStub(selector)
        return stubs[selector]

    app.query_one = query_one  # type: ignore[method-assign]
    item = Item(kind="theme", id="demo", name="Demo")

    app._shots[item.key] = ""
    app._render_detail(item, settled=True)
    assert stubs["#shot"].image is None
    assert stubs["#shot"].display is False

    app._shots[item.key] = "/tmp/preview.png"
    app._render_detail(item, settled=True)
    assert stubs["#shot"].image == "/tmp/preview.png"
    assert stubs["#shot"].display is True

    meta = stubs["#meta"].value
    assert "[p] zoom" in (meta.plain if isinstance(meta, Text) else str(meta))


def test_confirm_prompt_covers_install_enable_and_warnings() -> None:
    item = Item(
        kind="plugin",
        id="x",
        name="X[bold]",
        repo="https://github.com/a/x",
        verification="unverified",
        warnings=["runs unsandboxed code"],
        installed=True,
    )
    install = confirm_prompt("install", item)
    assert 'install plugin “X[bold]”?' in install
    assert "https://github.com/a/x" in install
    assert "verification: unverified" in install
    assert "warnings:" in install
    assert "- runs unsandboxed code" in install
    assert "Community plugins and themes run unsandboxed." in install
    assert "This uses the official omarchy command." in install

    enable = confirm_prompt("enable", item)
    assert 'enable plugin “X[bold]”?' in enable
    assert "Community plugins and themes run unsandboxed." in enable
    assert "official omarchy command" not in enable


def test_theme_update_confirm_covers_all_extra_git_themes() -> None:
    item = Item(kind="theme", id="lumon", name="Lumon", extra=True, install_url="https://github.com/x/lumon")
    prompt = confirm_prompt("update", item)
    assert "update all extra git themes?" in prompt
    assert "Lumon" in prompt


def test_confirm_screen_disables_markup() -> None:
    from omastore.app import ConfirmScreen

    screen = ConfirmScreen('install plugin “X[bold]”?')
    static = next(screen.compose())
    assert static._render_markup is False
    assert "[y] yes   [n] no" in str(static._Static__content)


def test_act_confirms_enable_not_apply_or_disable() -> None:
    from omastore.app import ConfirmScreen, OmaStoreApp

    pushed: list[object] = []
    ran: list[str] = []
    app = OmaStoreApp()
    app.push_screen = lambda screen, callback=None: pushed.append(screen)  # type: ignore[method-assign]
    app._run_action = lambda name, item: ran.append(name)  # type: ignore[method-assign]

    app.selected = Item(kind="plugin", id="x", name="X", installed=True, enabled=False)
    app._act("enable")
    assert len(pushed) == 1
    assert isinstance(pushed[0], ConfirmScreen)
    assert "enable plugin" in pushed[0].prompt
    assert ran == []

    pushed.clear()
    app.selected = Item(kind="theme", id="tokyo", name="Tokyo", installed=True)
    app._act("apply")
    assert pushed == []
    assert ran == ["apply"]

    app.selected = Item(kind="plugin", id="x", name="X", installed=True, enabled=True)
    app._act("disable")
    assert pushed == []
    assert ran == ["apply", "disable"]


def test_search_change_is_debounced() -> None:
    from types import SimpleNamespace

    from omastore.app import OmaStoreApp

    app = OmaStoreApp()
    rebuilt: list[str] = []
    app._rebuild_list = lambda: rebuilt.append("rebuild")  # type: ignore[method-assign]
    timers: list[object] = []

    class _Timer:
        def stop(self) -> None:
            timers.append("stop")

    def set_timer(delay: float, callback):
        timers.append((delay, callback))
        return _Timer()

    app.set_timer = set_timer  # type: ignore[method-assign]
    app.on_search_changed(SimpleNamespace(value="lumon"))  # type: ignore[arg-type]
    assert rebuilt == []
    assert timers[-1][0] == 0.2  # type: ignore[index]
    app.on_search_changed(SimpleNamespace(value="lumon night"))  # type: ignore[arg-type]
    assert "stop" in timers
    assert rebuilt == []
    app._settle_search()
    assert rebuilt == ["rebuild"]


def test_reset_filters_clears_cycles_and_prefixes() -> None:
    from types import SimpleNamespace

    from omastore.app import OmaStoreApp
    from omastore.filters import Query

    app = OmaStoreApp()
    app.search = "clipboard is:installed verified:yes"
    app.filters = Query(status="installed", source="community", verified="yes", sort="name", min_stars=5)
    rebuilt: list[str] = []
    notes: list[str] = []
    app._rebuild_list = lambda: rebuilt.append("rebuild")  # type: ignore[method-assign]
    app.notify = lambda message, **_kwargs: notes.append(str(message))  # type: ignore[method-assign]
    app.query_one = lambda *a, **k: SimpleNamespace(value="clipboard is:installed verified:yes")  # type: ignore[method-assign]
    app.action_reset_filters()
    assert app.search == "clipboard"
    assert app.filters.status == "all"
    assert app.filters.source == "all"
    assert app.filters.verified == "all"
    assert app.filters.sort == "stars"
    assert app.filters.min_stars == 0
    assert rebuilt == ["rebuild"]
    assert notes == ["filters reset"]


def test_escape_on_list_resets_filters() -> None:
    from types import SimpleNamespace

    from omastore.app import OmaStoreApp

    app = OmaStoreApp()
    reset: list[str] = []
    app.action_reset_filters = lambda: reset.append("reset")  # type: ignore[method-assign]
    focused: list[str] = []
    app.query_one = lambda *a, **k: SimpleNamespace(has_focus=False, focus=lambda: focused.append("list"))  # type: ignore[method-assign]
    app.action_blur_or_reset()
    assert reset == ["reset"]
    assert focused == []

    reset.clear()
    app.query_one = lambda *a, **k: SimpleNamespace(has_focus=True, focus=lambda: focused.append("list"))  # type: ignore[method-assign]
    app.action_blur_or_reset()
    assert reset == []
    assert focused == ["list"]


def test_shot_open_file_uses_path_uri(monkeypatch) -> None:
    from pathlib import Path

    from omastore.app import ShotScreen

    opened: list[str] = []
    monkeypatch.setattr("omastore.previews._xdg_open", lambda uri: opened.append(uri))
    screen = ShotScreen("/tmp/preview.png", "Localhost")
    notes: list[str] = []
    screen.notify = lambda message, **_kwargs: notes.append(str(message))  # type: ignore[method-assign]
    screen.action_open_file()
    assert opened == [Path("/tmp/preview.png").as_uri()]


def test_workers_exclusive_groups() -> None:
    import inspect

    from omastore.app import OmaStoreApp

    try_src = inspect.getsource(OmaStoreApp._run_try)
    revert_src = inspect.getsource(OmaStoreApp._run_revert)
    action_src = inspect.getsource(OmaStoreApp._run_action)
    pack_src = inspect.getsource(OmaStoreApp._run_pack_install)
    pack_remove_src = inspect.getsource(OmaStoreApp._run_pack_remove)
    rebuild_src = inspect.getsource(OmaStoreApp._rebuild_list)
    assert 'exclusive=True' in try_src and 'group="theme-preview"' in try_src
    assert 'exclusive=False' in revert_src and 'group="theme-preview"' in revert_src
    assert 'exclusive=True' in action_src and 'group="action"' in action_src
    assert 'exclusive=True' in pack_src and 'group="action"' in pack_src
    assert 'exclusive=True' in pack_remove_src and 'group="action"' in pack_remove_src
    assert "preview_status" not in rebuild_src


def test_pack_binding_exists() -> None:
    from omastore.app import OmaStoreApp

    assert any(binding.key == "4" and "packs" in binding.action for binding in OmaStoreApp.BINDINGS)


def test_pack_prompt_counts() -> None:
    from omastore.packs import get_pack

    pack = get_pack("finance")
    open_ = Item(
        kind="plugin",
        id="io.github.5d0tal1gat0r.stocks",
        name="Stocks",
        verification="verified",
        description="stock widget",
        category="Widgets",
        install_url="https://github.com/a/stocks",
    )
    have = Item(
        kind="plugin",
        id="io.github.guettoblasterr.crypto-market-pulse",
        name="Crypto",
        verification="verified",
        description="crypto",
        category="Widgets",
        installed=True,
    )
    line = pack_prompt(pack, [open_, have], width=28).plain
    assert "Finance" in line
    assert "1/2 on" in line
    assert "●" in line


def test_pack_click_never_installs() -> None:
    from types import SimpleNamespace

    from omastore.app import OmaStoreApp
    from omastore.packs import get_pack

    app = OmaStoreApp(start_tab="packs")
    app.tab = "packs"
    app.selected_pack = get_pack("everyday")
    acts: list[str] = []
    app._act_pack = lambda *_args, **_kwargs: acts.append("pack")  # type: ignore[method-assign]
    app._select_key = lambda *args, **kwargs: None  # type: ignore[method-assign]

    app._click_list()
    event = SimpleNamespace(option_id="pack__everyday")
    app.on_option_selected(event)  # type: ignore[arg-type]
    assert acts == []
    app.on_option_selected(event)  # type: ignore[arg-type]
    assert acts == ["pack"]


def test_act_pack_confirms_all_members() -> None:
    from omastore.app import ConfirmScreen, OmaStoreApp
    from omastore.packs import get_pack

    app = OmaStoreApp()
    app.tab = "packs"
    app.selected_pack = get_pack("finance")
    app.items = [
        Item(
            kind="plugin",
            id="io.github.5d0tal1gat0r.stocks",
            name="Stocks",
            verification="verified",
            description="stock widget",
            category="Widgets",
            install_url="https://github.com/a/stocks",
            repo="https://github.com/a/stocks",
        )
    ]
    pushed: list[object] = []
    ran: list[object] = []
    app.push_screen = lambda screen, callback=None: pushed.append(screen)  # type: ignore[method-assign]
    app._run_pack_install = lambda *args: ran.append(args)  # type: ignore[method-assign]
    app._act_pack()
    assert len(pushed) == 1
    assert isinstance(pushed[0], ConfirmScreen)
    assert "Stocks" in pushed[0].prompt
    assert "https://github.com/a/stocks" in pushed[0].prompt
    assert "HANCORE" in pushed[0].prompt
    assert ran == []


def test_act_pack_remove_confirms_installed_members() -> None:
    from omastore.app import ConfirmScreen, OmaStoreApp
    from omastore.packs import get_pack

    app = OmaStoreApp()
    app.tab = "packs"
    app.selected_pack = get_pack("finance")
    app.items = [
        Item(
            kind="plugin",
            id="io.github.5d0tal1gat0r.stocks",
            name="Stocks",
            verification="verified",
            description="stock widget",
            category="Widgets",
            installed=True,
            repo="https://github.com/a/stocks",
        )
    ]
    pushed: list[object] = []
    ran: list[object] = []
    app.push_screen = lambda screen, callback=None: pushed.append(screen)  # type: ignore[method-assign]
    app._run_pack_remove = lambda *args: ran.append(args)  # type: ignore[method-assign]
    app._act_pack("remove")
    assert len(pushed) == 1
    assert isinstance(pushed[0], ConfirmScreen)
    assert "remove 1 plugin from Finance?" in pushed[0].prompt
    assert "Stocks" in pushed[0].prompt
    assert "https://github.com/a/stocks" in pushed[0].prompt
    assert "also in another pack" in pushed[0].prompt
    assert ran == []


def test_act_pack_nothing_to_remove() -> None:
    from omastore.app import OmaStoreApp
    from omastore.packs import get_pack

    app = OmaStoreApp()
    app.tab = "packs"
    app.selected_pack = get_pack("finance")
    app.items = [
        Item(
            kind="plugin",
            id="io.github.5d0tal1gat0r.stocks",
            name="Stocks",
            verification="verified",
            description="stock widget",
            category="Widgets",
            install_url="https://github.com/a/stocks",
        )
    ]
    notes: list[str] = []
    pushed: list[object] = []
    app.notify = lambda message, **_kwargs: notes.append(str(message))  # type: ignore[method-assign]
    app.push_screen = lambda screen, callback=None: pushed.append(screen)  # type: ignore[method-assign]
    app._act_pack("remove")
    assert pushed == []
    assert notes
    assert "nothing to remove" in notes[0]


def test_act_pack_nothing_to_install() -> None:
    from omastore.app import OmaStoreApp
    from omastore.packs import get_pack

    app = OmaStoreApp()
    app.tab = "packs"
    app.selected_pack = get_pack("finance")
    app.items = [
        Item(
            kind="plugin",
            id="io.github.5d0tal1gat0r.stocks",
            name="Stocks",
            verification="verified",
            description="stock widget",
            category="Widgets",
            installed=True,
        )
    ]
    notes: list[str] = []
    pushed: list[object] = []
    app.notify = lambda message, **_kwargs: notes.append(str(message))  # type: ignore[method-assign]
    app.push_screen = lambda screen, callback=None: pushed.append(screen)  # type: ignore[method-assign]
    app._act_pack()
    assert pushed == []
    assert notes
    assert "nothing to install" in notes[0]


def test_notice_screen_disables_markup() -> None:
    from omastore.app import NoticeScreen

    screen = NoticeScreen()
    static = next(screen.compose())
    assert static._render_markup is False
    body = str(static._Static__content)
    assert "unsandboxed" in body.lower()
    assert "limehawk" in body.lower()
    assert "HANCORE" in body
    assert "[y] continue" in body
    assert "[e] everyday pack" in body


def test_maybe_notice_skipped_when_seen(monkeypatch) -> None:
    from omastore.app import OmaStoreApp
    from omastore import notice

    monkeypatch.setattr(notice, "seen", lambda: True)
    app = OmaStoreApp()
    pushed: list[object] = []
    app.push_screen = lambda *args, **kwargs: pushed.append(args)  # type: ignore[method-assign]
    app._maybe_notice()
    assert pushed == []


def test_maybe_notice_shows_when_unseen(monkeypatch) -> None:
    from omastore.app import NoticeScreen, OmaStoreApp
    from omastore import notice

    monkeypatch.setattr(notice, "seen", lambda: False)
    app = OmaStoreApp()
    pushed: list[object] = []
    app.push_screen = lambda screen, callback=None: pushed.append(screen)  # type: ignore[method-assign]
    app._maybe_notice()
    assert len(pushed) == 1
    assert isinstance(pushed[0], NoticeScreen)


def test_notice_everyday_opens_packs_tab(monkeypatch) -> None:
    from omastore.app import OmaStoreApp
    from omastore import notice

    marked: list[str] = []
    monkeypatch.setattr(notice, "mark_seen", lambda: marked.append("seen"))
    app = OmaStoreApp()
    tabs: list[str] = []
    selected: list[str] = []
    app.action_set_tab = lambda tab: tabs.append(tab)  # type: ignore[method-assign]
    app._select_pack = lambda pack: selected.append(pack.id if pack else "")  # type: ignore[method-assign]
    app._notice_done("everyday")
    assert marked == ["seen"]
    assert tabs == ["packs"]
    assert selected == ["everyday"]
