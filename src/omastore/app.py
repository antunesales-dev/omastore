from __future__ import annotations

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical, VerticalScroll
from textual.events import Click, MouseScrollDown, MouseScrollUp
from textual.screen import ModalScreen
from textual.widgets import Footer, Input, Markdown, OptionList, Static
from textual.widgets.option_list import Option
from textual_image.widget import Image as ShotImage
from rich.cells import set_cell_size
from rich.text import Text

from omastore.actions import (
    ActionResult,
    apply_theme,
    disable_plugin,
    enable_plugin,
    install,
    install_pack,
    remove,
    remove_pack,
    update,
)
from omastore.catalog import fetch_readme, load_store
from omastore.credits import ABOUT
from omastore.filters import (
    Query,
    apply_query,
    clamp_query,
    cycle_sort,
    cycle_source,
    cycle_status,
    cycle_verified,
    parse_search,
    reset_filters,
    strip_filter_tokens,
)
from omastore.models import Item, Tab
from omastore.notice import NOTICE
from omastore.packs import (
    PACKS,
    Pack,
    describe_pack_install,
    describe_pack_remove,
    get_pack,
    pack_markdown,
    pack_matches,
)
from omastore.theme import omarchy_theme_css

PALETTE_KEYS = [
    "background",
    "foreground",
    "accent",
    "color0",
    "color1",
    "color2",
    "color3",
    "color4",
    "color5",
    "color6",
    "color7",
    "color8",
    "color9",
    "color10",
    "color11",
    "color12",
    "color13",
    "color14",
    "color15",
]


def sort_items(items: list[Item], tab: Tab, query: Query | None = None) -> list[Item]:
    return apply_query(items, query or Query(), tab)


def pack_prompt(pack: Pack, items: list[Item], width: int = 40) -> Text:
    members = pack.members(items)
    listed = len(members)
    installed = sum(1 for item in members if item.installed)
    text = Text()
    if listed and installed == listed:
        mark, style = "●", "cyan"
    elif installed:
        mark, style = "●", "cyan"
    else:
        mark, style = "○", "dim"
    text.append(f"{mark} ", style=style)
    count = f"{installed}/{listed} on"
    name_width = max(8, width - 2 - (len(count) + 1))
    text.append(set_cell_size(pack.title, name_width))
    text.append(" ")
    text.append(count, style="dim")
    return text


def list_prompt(item: Item, width: int = 40) -> Text:
    text = Text()
    if item.current or (item.kind == "plugin" and item.enabled):
        mark, style = "●", "green"
    elif item.installed:
        mark, style = "●", "cyan"
    else:
        mark, style = "○", "dim"
    text.append(f"{mark} ", style=style)
    used = 2
    if item.kind == "plugin":
        badge = item.verification_label
        if badge == "verified":
            text.append("✓ ", style="green")
        elif badge == "unverified":
            text.append("- ", style="yellow")
        else:
            text.append("  ")
        used += 2
    if getattr(item, "outdated", False):
        text.append("↑ ", style="yellow")
        used += 2
    star = f"*{item.stars}" if item.stars is not None and item.stars > 0 else ""
    star_width = 6 if star else 0
    name_width = max(8, width - used - (star_width + 1 if star else 0))
    text.append(set_cell_size(item.name, name_width))
    if star:
        text.append(" ")
        text.append(f"{star:>{star_width}}", style="dim")
    return text


def action_groups(item: Item) -> tuple[list[str], list[str]]:
    do: list[str] = []
    if item.can_install:
        do.append("[i] install")
    if item.kind == "theme":
        if item.installed:
            do.append("[t] try")
        do.append("[b] back")
    if item.can_apply:
        do.append("[a] apply")
    if item.can_enable:
        do.append("[e] enable")
    if item.can_disable:
        do.append("[d] disable")
    if item.can_update:
        do.append("[u] update")
    if item.can_remove:
        do.append("[x] remove")
    look = ["[o] repo", "[c] catalog", "[p] zoom"]
    return do, look


def action_hints(item: Item) -> list[str]:
    do, look = action_groups(item)
    return [*do, *look]


def format_action_hints(actions: list[str], width: int = 48) -> str:
    """Pack key hints onto one or two short lines."""
    if not actions:
        return ""
    width = max(24, int(width))
    lines: list[str] = []
    current: list[str] = []
    size = 0
    for action in actions:
        extra = len(action) + (2 if current else 0)
        if current and size + extra > width:
            lines.append("  ".join(current))
            current = [action]
            size = len(action)
        else:
            current.append(action)
            size += extra
    if current:
        lines.append("  ".join(current))
    return "\n".join(lines)


def confirm_prompt(action: str, item: Item) -> str:
    if action == "update" and item.kind == "theme":
        lines = ["update all extra git themes?", f"{item.kind} “{item.name}”?"]
    else:
        lines = [f"{action} {item.kind} “{item.name}”?"]
    loc = item.repo or item.install_url
    if loc:
        lines.append(str(loc))
    if item.verification_label:
        lines.append(f"verification: {item.verification_label}")
    extra_warnings: list[str] = list(item.warnings)
    if action == "remove" and item.kind == "plugin":
        from omastore.local import layout_remove_warnings

        extra_warnings.extend(layout_remove_warnings(item.id))
    if extra_warnings:
        lines.append("warnings:")
        lines.extend(f"- {warning}" for warning in extra_warnings)
    if action in {"install", "enable"}:
        lines.append("Community plugins and themes run unsandboxed.")
    if action == "install":
        lines.append("This uses the official omarchy command.")
    return "\n".join(lines)


def filter_bar(query: Query, tab: Tab = "themes") -> str:
    status = {
        "all": "all",
        "installed": "installed",
        "not-installed": "not-installed",
        "uninstalled": "not-installed",
        "available": "available",
        "extra": "extra",
        "stock": "stock",
    }.get(query.status, query.status)
    source = {
        "all": "all",
        "community": "community",
        "builtin": "built-in",
    }.get(query.source, query.source)
    verified = {
        "all": "all",
        "yes": "verified",
        "no": "unverified",
        "unverified": "unverified",
    }.get(query.verified, query.verified)
    sort = f"{query.min_stars}+stars" if query.min_stars else query.sort
    parts = [f"f {status}", f"v {source}"]
    if tab == "plugins":
        parts.append(f"y {verified}")
    parts.append(f"s sort:{sort}")
    extras: list[str] = []
    if query.hue not in {"", "all"}:
        extras.append(f"hue:{query.hue}")
    if query.category not in {"", "all"}:
        extras.append(f"cat:{query.category}")
    if query.tag not in {"", "all"}:
        extras.append(f"tag:{query.tag}")
    extras.append("0 reset")
    return "   ".join(parts + extras)


def format_status(
    status_text: str,
    shown: int,
    *,
    label: str = "shown",
    trying: str = "",
    previous: str = "",
    outdated: int = 0,
) -> str:
    parts = [status_text, f"{shown} {label}"]
    if trying:
        extra = f"trying {trying}"
        if previous:
            extra += "  [b] back"
        parts.append(extra)
    if outdated:
        parts.append(f"{outdated} outdated")
    return "  ·  ".join(part for part in parts if part)


def palette_text(colors: dict[str, str]) -> Text:
    text = Text()
    seen: set[str] = set()
    for key in PALETTE_KEYS:
        hex_color = colors.get(key)
        if not hex_color or not hex_color.startswith("#") or hex_color.lower() in seen:
            continue
        seen.add(hex_color.lower())
        text.append("   ", style=f"on {hex_color}")
    if not seen:
        text.append("no palette", style="dim")
    return text


def item_markdown(
    item: Item,
    readme: str | None = None,
    *,
    include_readme: bool = True,
    loading: bool = False,
) -> str:
    bits: list[str] = []
    if item.description:
        bits.append(item.description)
        bits.append("")
    facts: list[str] = []
    if item.author:
        facts.append(f"By **{item.author}**")
    if item.category:
        facts.append(item.category)
    if item.hue:
        facts.append(item.hue)
    if item.version:
        facts.append(item.version)
    if item.stars is not None:
        facts.append(f"★ {item.stars}")
    if item.license:
        facts.append(item.license)
    if facts:
        bits.append(" · ".join(facts))
        bits.append("")
    if item.tags:
        bits.append(" ".join(f"`{tag}`" for tag in item.tags))
        bits.append("")
    if item.repo:
        bits.append(item.repo)
    if item.install_url and item.install_url != item.repo:
        bits.append(f"`{item.install_url}`")
    if item.verification:
        bits.append(f"Verification: `{item.verification}`")
    if item.install_note:
        bits.append("")
        bits.append(item.install_note)
    if item.warnings:
        bits.append("")
        bits.append("**Warnings**")
        bits.extend(f"- {warning}" for warning in item.warnings)
    if loading:
        bits.extend(["", "_Loading about…_"])
        return "\n".join(bits)
    if not include_readme:
        return "\n".join(bits)
    bits.append("")
    bits.append("Listed in a community catalog. The work belongs to its author.")
    bits.append("Community plugins and themes run unsandboxed. Read the repo before installing.")
    body = readme if readme is not None else item.readme
    if body:
        bits.extend(["", "---", "", "## About", "", body])
    return "\n".join(bits)


SHOT_ZOOMS = (1.0, 1.5, 2.0, 3.0, 4.0)
SHOT_PAN_STEP = 0.25


def next_shot_zoom(current: float, direction: int) -> float:
    """direction > 0 zooms in, < 0 zooms out. Clamped to SHOT_ZOOMS."""
    if direction > 0:
        for step in SHOT_ZOOMS:
            if step > current + 0.01:
                return step
        return SHOT_ZOOMS[-1]
    for step in reversed(SHOT_ZOOMS):
        if step < current - 0.01:
            return step
    return SHOT_ZOOMS[0]


def clamp_pan(value: float) -> float:
    return max(-1.0, min(1.0, value))


def shot_crop_box(
    width: int,
    height: int,
    zoom: float,
    pan_x: float = 0.0,
    pan_y: float = 0.0,
) -> tuple[int, int, int, int]:
    """Return (left, top, right, bottom). pan -1 is left/top, 1 is right/bottom."""
    if width < 1 or height < 1 or zoom <= 1.0:
        return (0, 0, max(0, width), max(0, height))
    crop_w = max(1, int(width / zoom))
    crop_h = max(1, int(height / zoom))
    max_left = max(0, width - crop_w)
    max_top = max(0, height - crop_h)
    left = int(round((clamp_pan(pan_x) + 1) / 2 * max_left))
    top = int(round((clamp_pan(pan_y) + 1) / 2 * max_top))
    left = min(max_left, max(0, left))
    top = min(max_top, max(0, top))
    return (left, top, left + crop_w, top + crop_h)


class NoticeScreen(ModalScreen[str | None]):
    BINDINGS = [
        Binding("y,enter", "continue", "Continue", show=False),
        Binding("e", "everyday", "Everyday", show=False),
        Binding("escape", "continue", "Continue", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Static(NOTICE + "\n\n[y] continue   [e] everyday pack", id="notice", markup=False)

    def action_continue(self) -> None:
        self.dismiss("ok")

    def action_everyday(self) -> None:
        self.dismiss("everyday")


class ConfirmScreen(ModalScreen[bool]):
    BINDINGS = [
        Binding("y,enter", "yes", "Yes", show=False),
        Binding("n,escape", "no", "No", show=False),
    ]

    def __init__(self, prompt: str) -> None:
        super().__init__()
        self.prompt = prompt

    def compose(self) -> ComposeResult:
        yield Static(self.prompt + "\n\n[y] yes   [n] no", id="confirm", markup=False)

    def action_yes(self) -> None:
        self.dismiss(True)

    def action_no(self) -> None:
        self.dismiss(False)


class ShotScreen(ModalScreen[None]):
    BINDINGS = [
        Binding("escape,q", "close", "Close", show=False),
        Binding("plus,equal", "zoom_in", "Zoom+", show=False),
        Binding("minus", "zoom_out", "Zoom−", show=False),
        Binding("0", "zoom_fit", "Fit", show=False),
        Binding("left,h", "pan_left", "Left", show=False),
        Binding("right,l", "pan_right", "Right", show=False),
        Binding("up,k", "pan_up", "Up", show=False),
        Binding("down,j", "pan_down", "Down", show=False),
        Binding("o", "open_file", "Open", show=False),
    ]

    def __init__(self, path: str, title: str = "") -> None:
        super().__init__()
        self.path = path
        self.shot_title = title
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0

    def compose(self) -> ComposeResult:
        yield Static(self._bar(), id="shot-bar", markup=False)
        yield ScrollableContainer(ShotImage(id="shot-full"), id="shot-scroll")

    def on_mount(self) -> None:
        self._apply_zoom()

    def _bar(self, width: int = 60) -> str:
        name = self.shot_title or "preview"
        extra = f"  ·  {self.zoom:g}×"
        room = max(8, int(width) - len(extra) - 2)
        if len(name) > room:
            name = name[: room - 1] + "…"
        title = f"{name}{extra}"
        keys = "[+] in  [-] out  [arrows] pan  [0] fit  [o] open  [esc] close"
        return f"{title}\n{keys}"

    def _view(self):
        from PIL import Image as PILImage

        image = PILImage.open(self.path).convert("RGB")
        box = shot_crop_box(*image.size, self.zoom, self.pan_x, self.pan_y)
        if box == (0, 0, image.size[0], image.size[1]):
            return image
        return image.crop(box)

    def _apply_zoom(self) -> None:
        image = self.query_one("#shot-full", ShotImage)
        image.styles.width = "1fr"
        image.styles.height = "1fr"
        image.image = self._view()
        width = self.size.width or 60
        self.query_one("#shot-bar", Static).update(self._bar(width))

    def _pan(self, dx: float, dy: float) -> None:
        if self.zoom <= 1.0:
            self.zoom = next_shot_zoom(self.zoom, 1)
        self.pan_x = clamp_pan(self.pan_x + dx)
        self.pan_y = clamp_pan(self.pan_y + dy)
        self._apply_zoom()

    def action_pan_left(self) -> None:
        self._pan(-SHOT_PAN_STEP, 0)

    def action_pan_right(self) -> None:
        self._pan(SHOT_PAN_STEP, 0)

    def action_pan_up(self) -> None:
        self._pan(0, -SHOT_PAN_STEP)

    def action_pan_down(self) -> None:
        self._pan(0, SHOT_PAN_STEP)

    def action_zoom_in(self) -> None:
        self.zoom = next_shot_zoom(self.zoom, 1)
        self._apply_zoom()

    def action_zoom_out(self) -> None:
        self.zoom = next_shot_zoom(self.zoom, -1)
        if self.zoom <= 1.0:
            self.pan_x = 0.0
            self.pan_y = 0.0
        self._apply_zoom()

    def action_zoom_fit(self) -> None:
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self._apply_zoom()

    def action_open_file(self) -> None:
        from pathlib import Path

        from omastore.previews import _xdg_open

        try:
            _xdg_open(Path(self.path).as_uri())
            self.notify(f"opened {self.path}")
        except Exception as exc:
            self.notify(str(exc), severity="error")

    def action_close(self) -> None:
        self.dismiss()

    def on_click(self, event: Click) -> None:
        if event.widget is not None and event.widget.id == "shot-full":
            if self.zoom < 2.0:
                self.action_zoom_in()
            else:
                self.action_zoom_fit()
            event.stop()

    def on_mouse_scroll_up(self, event: MouseScrollUp) -> None:
        self.action_zoom_in()
        event.stop()

    def on_mouse_scroll_down(self, event: MouseScrollDown) -> None:
        self.action_zoom_out()
        event.stop()


class CreditsScreen(ModalScreen[None]):
    BINDINGS = [
        Binding("escape,q,enter,question_mark", "close", "Close", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Markdown(ABOUT, id="credits")

    def action_close(self) -> None:
        self.dismiss()


class OmaStoreApp(App[None]):
    TITLE = "Omastore"
    SUB_TITLE = ""
    CSS_PATH = "app.tcss"
    BINDINGS = [
        Binding("slash", "focus_search", "Search", show=True),
        Binding("escape", "blur_search", "List", show=False),
        Binding("0", "reset_filters", "Reset", show=False),
        Binding("1", "set_tab('themes')", "Themes", show=False),
        Binding("2", "set_tab('plugins')", "Plugins", show=False),
        Binding("3", "set_tab('installed')", "Installed", show=False),
        Binding("4", "set_tab('packs')", "Packs", show=False),
        Binding("i", "do_install", "Install", show=False),
        Binding("t", "try_theme", "Try", show=False),
        Binding("b", "revert_theme", "Back", show=False),
        Binding("o", "open_repo", "Repo", show=False),
        Binding("c", "open_catalog", "Catalog", show=False),
        Binding("p", "open_preview", "Preview", show=False),
        Binding("a", "do_apply", "Apply", show=False),
        Binding("e", "do_enable", "Enable", show=False),
        Binding("d", "do_disable", "Disable", show=False),
        Binding("u", "do_update", "Update", show=False),
        Binding("x", "do_remove", "Remove", show=False),
        Binding("r", "refresh", "Refresh", show=False),
        Binding("f", "cycle_status", "Filter", show=True),
        Binding("v", "cycle_source", "Source", show=False),
        Binding("y", "cycle_verified", "Verified", show=False),
        Binding("s", "cycle_sort", "Sort", show=False),
        Binding("question_mark", "credits", "Credits", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    def __init__(self, start_tab: Tab = "themes", query: str = "") -> None:
        super().__init__()
        self.start_tab = start_tab
        self.tab: Tab = start_tab
        self.search = query
        self.filters = parse_search(query)
        self.search = self.filters.text
        self.items: list[Item] = []
        self.shown: list[Item] = []
        self.pack_shown: list[Pack] = []
        self.selected: Item | None = None
        self.selected_pack: Pack | None = None
        self.status_text = "loading catalogs…"
        self._readme_key = ""
        self._list_pointer = False
        self._about_timer = None
        self._search_timer = None
        self._pending_about_key = ""
        self._try_session: dict | None = None
        self._shots: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        yield Vertical(
            Horizontal(
                Static("Omastore", id="brand"),
                Static("1 themes", id="tab-themes", classes="tab active"),
                Static("2 plugins", id="tab-plugins", classes="tab"),
                Static("3 installed", id="tab-installed", classes="tab"),
                Static("4 packs", id="tab-packs", classes="tab"),
                Input(
                    placeholder="Search  ·  /  to type",
                    id="search",
                    value=self.search,
                ),
                id="tabs",
            ),
            Static(id="filters"),
            id="chrome",
        )
        yield Horizontal(
            OptionList(id="list"),
            VerticalScroll(
                Static(id="meta"),
                Static(id="palette"),
                ShotImage(id="shot"),
                Markdown(id="readme"),
                id="detail",
            ),
            id="body",
        )
        yield Static(self.status_text, id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.stylesheet.add_source(omarchy_theme_css())
        self.refresh_css()
        self.tab = self.start_tab
        self._paint_tabs()
        if self.search:
            self.query_one("#search", Input).value = self.search
        self.query_one("#list", OptionList).focus()
        self.load_items()
        self._maybe_notice()

    def _maybe_notice(self) -> None:
        from omastore import notice

        if notice.seen():
            return
        self.push_screen(NoticeScreen(), self._notice_done)

    def _notice_done(self, result: str | None) -> None:
        from omastore import notice

        notice.mark_seen()
        if result == "everyday":
            self.action_set_tab("packs")
            pack = get_pack("everyday")
            if pack is not None:
                self._select_pack(pack)

    def action_focus_search(self) -> None:
        self.query_one("#search", Input).focus()

    def action_blur_search(self) -> None:
        self.query_one("#list", OptionList).focus()

    def _search_focused(self) -> bool:
        try:
            return self.query_one("#search", Input).has_focus
        except Exception:
            return False

    def _filters_dirty(self) -> bool:
        query = self.filters
        if query.status != "all" or query.source != "all" or query.verified != "all":
            return True
        if query.min_stars or query.hue != "all":
            return True
        if query.category != "all" or query.tag != "all":
            return True
        return self.search != strip_filter_tokens(self.search)

    def action_reset_filters(self) -> None:
        if self._search_focused():
            return
        if not self._filters_dirty():
            return
        self.search = strip_filter_tokens(self.search)
        self.filters = reset_filters(Query(text=self.search, sort=self.filters.sort))
        box = self.query_one("#search", Input)
        if box.value != self.search:
            with self.prevent(Input.Changed):
                box.value = self.search
        self._rebuild_list()

    def action_cycle_status(self) -> None:
        if self._search_focused() or self.tab == "packs":
            return
        self.filters = cycle_status(self.filters, self.tab)
        self._rebuild_list()

    def action_cycle_source(self) -> None:
        if self._search_focused() or self.tab == "packs":
            return
        self.filters = cycle_source(self.filters)
        self._rebuild_list()

    def action_cycle_verified(self) -> None:
        if self._search_focused() or self.tab != "plugins":
            return
        self.filters = cycle_verified(self.filters)
        self._rebuild_list()

    def action_cycle_sort(self) -> None:
        if self._search_focused() or self.tab == "packs":
            return
        self.filters = cycle_sort(self.filters)
        self._rebuild_list()

    def action_set_tab(self, tab: Tab) -> None:
        self.tab = tab
        self.filters = clamp_query(self.filters, tab)
        self._paint_tabs()
        self._rebuild_list()
        self.query_one("#list", OptionList).focus()

    @on(Click, "#tab-themes")
    def _click_themes(self) -> None:
        self.action_set_tab("themes")

    @on(Click, "#tab-plugins")
    def _click_plugins(self) -> None:
        self.action_set_tab("plugins")

    @on(Click, "#tab-installed")
    def _click_installed(self) -> None:
        self.action_set_tab("installed")

    @on(Click, "#tab-packs")
    def _click_packs(self) -> None:
        self.action_set_tab("packs")

    def action_refresh(self) -> None:
        self.status_text = "refreshing catalogs…"
        self._status()
        self.load_items(force=True)

    def action_credits(self) -> None:
        self.push_screen(CreditsScreen())

    def action_do_install(self) -> None:
        if self.tab == "packs":
            self._act_pack("install")
            return
        self._act("install")

    def action_try_theme(self) -> None:
        item = self.selected
        if item is None or item.kind != "theme":
            return
        if not item.installed:
            self.notify(f"{item.name} is not installed yet. Install it, then try.", severity="warning")
            return
        self.notify(f"trying {item.name}…")
        self._run_try(item)

    def action_revert_theme(self) -> None:
        self.notify("restoring previous theme…")
        self._run_revert()

    @work(thread=True, exclusive=True, group="theme-preview")
    def _run_try(self, item: Item) -> None:
        from omastore.preview import remember_and_apply

        result = remember_and_apply(item.name)
        self.call_from_thread(self._preview_done, "try", result)

    @work(thread=True, exclusive=False, group="theme-preview")
    def _run_revert(self) -> None:
        from omastore.preview import revert

        result = revert()
        self.call_from_thread(self._preview_done, "revert", result)

    def _preview_done(self, name: str, result: dict) -> None:
        message = str(result.get("message") or name)
        if result.get("ok"):
            self.notify(message)
            if name == "try":
                self._try_session = {
                    "previous": str(result.get("previous") or ""),
                    "current": str(result.get("current") or ""),
                }
            elif name == "revert":
                self._try_session = None
        else:
            self.notify(message, severity="error")
        self.load_items()

    def action_open_repo(self) -> None:
        self._open_link("repo")

    def action_open_catalog(self) -> None:
        self._open_link("catalog")

    def action_open_preview(self) -> None:
        self._show_shot()

    @on(Click, "#shot")
    def _click_shot(self) -> None:
        self._show_shot()

    def _show_shot(self) -> None:
        item = self.selected
        if item is None:
            return
        path = self._shots.get(item.key) or ""
        if not path:
            from omastore.previews import resolve_preview_path

            found = resolve_preview_path(item)
            path = str(found) if found else ""
            if path:
                self._shots[item.key] = path
        if not path:
            self.notify("no preview image")
            return
        self.push_screen(ShotScreen(path, item.name))

    def _open_link(self, target: str) -> None:
        if self.tab == "packs" or (self.selected is None and self.selected_pack is not None):
            from omastore.links import PLUGIN_CATALOG, open_url

            result = open_url(PLUGIN_CATALOG)
            self.notify(str(result.get("message") or target))
            return
        item = self.selected
        if item is None:
            return
        from omastore.links import open_item

        result = open_item(item, target)
        self.notify(str(result.get("message") or target))

    def action_do_apply(self) -> None:
        self._act("apply")

    def action_do_enable(self) -> None:
        self._act("enable")

    def action_do_disable(self) -> None:
        self._act("disable")

    def action_do_update(self) -> None:
        self._act("update")

    def action_do_remove(self) -> None:
        if self.tab == "packs":
            self._act_pack("remove")
            return
        self._act("remove")

    @on(Input.Changed, "#search")
    def on_search_changed(self, event: Input.Changed) -> None:
        self.search = event.value
        if self._search_timer is not None:
            self._search_timer.stop()
            self._search_timer = None
        self._search_timer = self.set_timer(0.2, self._settle_search)

    def _settle_search(self) -> None:
        self._search_timer = None
        self._rebuild_list()

    def _active_query(self) -> Query:
        return parse_search(self.search, defaults=self.filters)

    @on(Input.Submitted, "#search")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        self.query_one("#list", OptionList).focus()

    @on(Click, "#list")
    def _click_list(self) -> None:
        self._list_pointer = True

    @on(OptionList.OptionHighlighted, "#list")
    def on_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_id:
            self._select_key(event.option_id, immediate=False)

    @on(OptionList.OptionSelected, "#list")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        pointer = self._list_pointer
        self._list_pointer = False
        if event.option_id:
            self._select_key(event.option_id, immediate=True)
        if pointer:
            return
        self._activate_selected()

    def _activate_selected(self) -> None:
        if self.tab == "packs":
            self._act_pack("install")
            return
        item = self.selected
        if item is None:
            return
        if item.can_apply:
            self._act("apply")
        elif item.can_install:
            self._act("install")
        elif item.can_enable:
            self._act("enable")

    @work(thread=True, exclusive=True)
    def load_items(self, force: bool = False) -> None:
        catalogs, items, local = load_store(force=force)
        errors = [err for err in (catalogs.theme_error, catalogs.plugin_error, getattr(local, "error", "")) if err]
        suffix = f"  ·  {errors[0]}" if errors else ""
        self.call_from_thread(self._set_items, items, suffix)

    def _set_items(self, items: list[Item], extra_status: str = "") -> None:
        self.items = items
        themes = sum(1 for item in items if item.kind == "theme")
        plugins = sum(1 for item in items if item.kind == "plugin")
        installed = sum(1 for item in items if item.installed)
        self.status_text = f"{themes} themes  ·  {plugins} plugins  ·  {installed} installed{extra_status}"
        try:
            from omastore.preview import _load_session

            self._try_session = _load_session()
        except Exception:
            pass
        self._rebuild_list()

    def _paint_tabs(self) -> None:
        for name in ("themes", "plugins", "installed", "packs"):
            widget = self.query_one(f"#tab-{name}", Static)
            widget.set_class(name == self.tab, "active")

    def _rebuild_list(self) -> None:
        if self.tab == "packs":
            self._rebuild_packs()
            return
        self.selected_pack = None
        previous = self.selected.key if self.selected else ""
        self.shown = apply_query(self.items, self._active_query(), self.tab)
        listing = self.query_one("#list", OptionList)
        row_width = listing.size.width or 40
        if row_width > 4:
            row_width -= 3
        options = [
            Option(list_prompt(item, row_width), id=item.key.replace(":", "__"))
            for item in self.shown
        ]
        listing.clear_options()
        if options:
            listing.add_options(options)
            index = next((i for i, item in enumerate(self.shown) if item.key == previous), 0)
            listing.highlighted = index
            self._select_key(self.shown[index].key.replace(":", "__"), immediate=False)
        else:
            self.selected = None
            self._cancel_about()
            self._render_detail(None)
        active = self._active_query()
        self.query_one("#filters", Static).update(filter_bar(active, self.tab))
        trying = ""
        previous_theme = ""
        session = self._try_session
        if session:
            previous_theme = str(session.get("previous") or "")
            trying = str(session.get("current") or "")
            if not trying:
                trying = next(
                    (item.name for item in self.items if item.kind == "theme" and item.current),
                    "",
                )
        outdated = 0
        try:
            from omastore.updates import outdated_items

            outdated = len(outdated_items(self.items))
        except Exception:
            pass
        self.query_one("#status", Static).update(
            format_status(
                self.status_text,
                len(self.shown),
                trying=trying,
                previous=previous_theme,
                outdated=outdated,
            )
        )

    def _rebuild_packs(self) -> None:
        previous = self.selected_pack.id if self.selected_pack else ""
        text = self._active_query().text
        shown_packs = [pack for pack in PACKS if pack_matches(pack, text, self.items)]
        self.pack_shown = shown_packs
        self.shown = []
        listing = self.query_one("#list", OptionList)
        row_width = listing.size.width or 40
        if row_width > 4:
            row_width -= 3
        options = [
            Option(pack_prompt(pack, self.items, row_width), id=f"pack__{pack.id}")
            for pack in shown_packs
        ]
        listing.clear_options()
        if options:
            listing.add_options(options)
            index = next((i for i, pack in enumerate(shown_packs) if pack.id == previous), 0)
            listing.highlighted = index
            self._select_pack(shown_packs[index])
        else:
            self.selected = None
            self.selected_pack = None
            self._cancel_about()
            self._render_pack_detail(None)
        self.query_one("#filters", Static).update("i install  x remove  / search  0 reset")
        self.query_one("#status", Static).update(
            format_status(self.status_text, len(shown_packs), label="packs")
        )

    def _select_pack(self, pack: Pack | None) -> None:
        self.selected = None
        self.selected_pack = pack
        self._cancel_about()
        self._render_pack_detail(pack)

    def _select_key(self, key: str, *, immediate: bool = False) -> None:
        if key.startswith("pack__") or self.tab == "packs":
            pack = get_pack(key.removeprefix("pack__"))
            self._select_pack(pack)
            return
        self.selected_pack = None
        key = key.replace("__", ":", 1)
        item = next((row for row in self.shown if row.key == key), None)
        self.selected = item
        self._render_detail(item, settled=immediate and bool(item and item.readme))
        if item is None:
            self._cancel_about()
            return
        if immediate:
            self._show_about(item)
        else:
            self._schedule_about(item.key)

    def _cancel_about(self) -> None:
        if self._about_timer is not None:
            self._about_timer.stop()
            self._about_timer = None
        self._pending_about_key = ""

    def _schedule_about(self, key: str) -> None:
        self._cancel_about()
        self._pending_about_key = key
        self._about_timer = self.set_timer(0.35, self._settle_about)

    def _settle_about(self) -> None:
        self._about_timer = None
        item = self.selected
        if item is None or item.key != self._pending_about_key:
            return
        self._show_about(item)

    def _show_about(self, item: Item) -> None:
        cached = item.key in self._shots
        if item.readme and cached:
            self._render_detail(item, settled=True)
            return
        self._load_about(item.key, fetch_image=not cached)

    def _set_shot(self, path: str = "") -> None:
        shot = self.query_one("#shot")
        if hasattr(shot, "image"):
            shot.image = path or None
        else:
            shot.update("")
        shot.display = bool(path)

    def _render_detail(self, item: Item | None, *, settled: bool = False) -> None:
        meta = self.query_one("#meta", Static)
        palette = self.query_one("#palette", Static)
        readme = self.query_one("#readme", Markdown)
        if item is None:
            meta.update("No matches.\nSearch, press 1 / 2 / 3 / 4, or f to filter.")
            palette.update("")
            palette.display = False
            self._set_shot("")
            readme.update("_Try another search or switch tabs._")
            return
        header = Text()
        header.append(item.name, style="bold")
        header.append("\n")
        subtitle = "  ·  ".join(
            part
            for part in (item.kind, item.author, item.status_label)
            if part
        )
        header.append(subtitle or item.kind, style="dim")
        pane_width = 48
        try:
            pane_width = max(32, int(self.query_one("#detail").size.width) - 6)
        except Exception:
            pass
        do, look = action_groups(item)
        blocks = [format_action_hints(group, width=pane_width) for group in (do, look) if group]
        if blocks:
            header.append("\n")
            header.append("\n".join(blocks), style="bold")
        meta.update(header)
        if item.colors:
            palette.update(palette_text(item.colors))
            palette.display = True
        else:
            palette.update("")
            palette.display = False
        if settled:
            self._set_shot(self._shots.get(item.key) or "")
            readme.update(item_markdown(item, item.readme, include_readme=True))
        else:
            self._set_shot("")
            readme.update(item_markdown(item, include_readme=False, loading=True))

    def _render_pack_detail(self, pack: Pack | None) -> None:
        meta = self.query_one("#meta", Static)
        palette = self.query_one("#palette", Static)
        readme = self.query_one("#readme", Markdown)
        palette.update("")
        palette.display = False
        self._set_shot("")
        if pack is None:
            meta.update("No packs match.\nPress 1 / 2 / 3 / 4, or / to search.")
            readme.update("_Try another search._")
            return
        listed, pending = pack.counts(self.items)
        removable = len(pack.removable(self.items))
        header = Text()
        header.append(pack.title, style="bold")
        header.append("\n")
        header.append(
            f"suggested pack  ·  {removable} installed of {listed}  ·  {pending} to install",
            style="dim",
        )
        header.append("\n")
        hints: list[str] = []
        if pending:
            hints.append("[i] install remaining")
        if removable:
            hints.append("[x] remove installed")
        hints.append("[c] catalog")
        header.append("  ".join(hints), style="bold")
        meta.update(header)
        readme.update(pack_markdown(pack, self.items))

    @work(thread=True, exclusive=True, group="about")
    def _load_about(self, key: str, fetch_image: bool = True) -> None:
        item = next((row for row in self.items if row.key == key), None)
        if item is None:
            return
        from omastore.enrich import enrich_item
        from omastore.previews import resolve_preview_path

        enrich_item(item)
        path = ""
        if fetch_image:
            found = resolve_preview_path(item)
            path = str(found) if found else ""
        if not item.readme:
            item.readme = fetch_readme(item)
        self.call_from_thread(self._apply_about, key, path, fetch_image)

    def _apply_about(self, key: str, path: str, fetch_image: bool = True) -> None:
        item = next((row for row in self.items if row.key == key), None)
        if item is None:
            return
        if fetch_image:
            self._shots[key] = path or ""
        if self.selected and self.selected.key == key:
            self._render_detail(item, settled=True)

    def _status(self) -> None:
        self.query_one("#status", Static).update(self.status_text)

    def _act(self, name: str) -> None:
        item = self.selected
        if item is None:
            return
        allowed = {
            "install": item.can_install,
            "apply": item.can_apply,
            "enable": item.can_enable,
            "disable": item.can_disable,
            "update": item.can_update,
            "remove": item.can_remove,
        }
        if not allowed.get(name):
            return
        if name in {"install", "remove", "update", "enable"}:

            def confirmed(ok: bool | None, action=name, target=item) -> None:
                if ok:
                    self._run_action(action, target)

            self.push_screen(ConfirmScreen(confirm_prompt(name, item)), confirmed)
            return
        self._run_action(name, item)

    def _act_pack(self, name: str = "install") -> None:
        pack = self.selected_pack
        if pack is None:
            return
        if name == "install":
            rows = pack.pending(self.items)
            prompt = describe_pack_install
            runner = self._run_pack_install
            empty = f"{pack.title}: nothing to install"
        elif name == "remove":
            rows = pack.removable(self.items)
            prompt = describe_pack_remove
            runner = self._run_pack_remove
            empty = f"{pack.title}: nothing to remove"
        else:
            return
        if not rows:
            self.notify(empty)
            return

        def confirmed(ok: bool | None, target=pack, members=rows, run=runner) -> None:
            if ok:
                run(target, members)

        self.push_screen(ConfirmScreen(prompt(pack, rows)), confirmed)

    @work(thread=True, exclusive=True, group="action")
    def _run_pack_install(self, pack: Pack, pending: list[Item]) -> None:
        results = install_pack(pending)
        self.call_from_thread(self._pack_action_done, pack, "install", results)

    @work(thread=True, exclusive=True, group="action")
    def _run_pack_remove(self, pack: Pack, rows: list[Item]) -> None:
        results = remove_pack(rows)
        self.call_from_thread(self._pack_action_done, pack, "remove", results)

    def _pack_action_done(
        self,
        pack: Pack,
        name: str,
        results: list[tuple[Item, ActionResult]],
    ) -> None:
        done = "installed" if name == "install" else "removed"
        empty = "install" if name == "install" else "remove"
        if not results:
            self.notify(f"{pack.title}: nothing to {empty}")
            return
        failed = next((item for item, result in results if not result.ok), None)
        if failed is not None:
            result = next(result for item, result in results if item is failed)
            self.notify(f"{pack.title} stopped at {failed.name}: {result.message}", severity="error")
        else:
            self.notify(f"{pack.title}: {done} {len(results)}")
        self.load_items()

    @work(thread=True, exclusive=True, group="action")
    def _run_action(self, name: str, item: Item) -> None:
        runners = {
            "install": install,
            "apply": apply_theme,
            "enable": enable_plugin,
            "disable": disable_plugin,
            "update": update,
            "remove": remove,
        }
        result: ActionResult = runners[name](item)
        self.call_from_thread(self._action_done, name, item, result)

    def _action_done(self, name: str, item: Item, result: ActionResult) -> None:
        if result.ok:
            self.notify(f"{name} {item.name}: {result.message}")
            self.load_items()
        else:
            self.notify(f"{name} failed: {result.message}", severity="error")


def run_tui(tab: Tab = "themes", query: str = "") -> None:
    OmaStoreApp(start_tab=tab, query=query).run()
