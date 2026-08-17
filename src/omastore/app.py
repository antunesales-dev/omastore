from __future__ import annotations

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.events import Click
from textual.screen import ModalScreen
from textual.widgets import Footer, Input, Markdown, OptionList, Static
from textual.widgets.option_list import Option
from rich.text import Text

from omastore.actions import (
    ActionResult,
    apply_theme,
    disable_plugin,
    enable_plugin,
    install,
    remove,
    update,
)
from omastore.catalog import fetch_readme, load_store
from omastore.credits import ABOUT, STATUS_CREDIT
from omastore.filters import Query, apply_query, cycle_sort, cycle_source, cycle_status, parse_search
from omastore.models import Item, Tab

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


def list_prompt(item: Item) -> Text:
    text = Text()
    mark = "●" if item.current or (item.kind == "plugin" and item.enabled) else "○"
    style = "green" if mark == "●" else "dim"
    text.append(f"{mark} ", style=style)
    text.append(item.name)
    if item.stars:
        text.append(f"  ★{item.stars}", style="dim")
    status = item.status_label
    if status:
        text.append(f"  {status}", style="dim italic")
    return text


def palette_text(colors: dict[str, str]) -> Text:
    text = Text()
    seen: set[str] = set()
    for key in PALETTE_KEYS:
        hex_color = colors.get(key)
        if not hex_color or not hex_color.startswith("#") or hex_color.lower() in seen:
            continue
        seen.add(hex_color.lower())
        text.append("  ", style=f"on {hex_color}")
    if not seen:
        text.append("no palette", style="dim")
    else:
        text.append("  ")
        text.append(" ".join(sorted(seen)[:6]), style="dim")
    return text


def item_markdown(item: Item, readme: str | None = None) -> str:
    bits = [f"# {item.name}", ""]
    meta = [item.kind]
    if item.author:
        meta.append(item.author)
    if item.category:
        meta.append(item.category)
    if item.hue:
        meta.append(item.hue)
    if item.version:
        meta.append(item.version)
    if item.stars is not None:
        meta.append(f"★ {item.stars}")
    if item.status_label:
        meta.append(item.status_label)
    bits.append(" · ".join(meta))
    bits.append("")
    if item.tags:
        bits.append(" ".join(f"`{tag}`" for tag in item.tags))
        bits.append("")
    if item.description:
        bits.append(item.description)
        bits.append("")
    if item.repo:
        bits.append(f"Repo: {item.repo}")
    if item.install_url:
        bits.append(f"Install: `{item.install_url}`")
    if item.verification:
        bits.append(f"Verification: `{item.verification}`")
    if item.license:
        bits.append(f"License: {item.license}")
    if item.install_note:
        bits.append("")
        bits.append(item.install_note)
    if item.warnings:
        bits.append("")
        bits.append("**Warnings**")
        bits.extend(f"- {warning}" for warning in item.warnings)
    bits.append("")
    if item.author:
        bits.append(f"By {item.author}. Listed in a community catalog; the work is theirs.")
    bits.append("Community plugins and themes run as unsandboxed code. Review the repo before installing.")
    body = readme if readme is not None else item.readme
    if body:
        bits.extend(["", "---", "", body])
    return "\n".join(bits)


class ConfirmScreen(ModalScreen[bool]):
    BINDINGS = [
        Binding("y,enter", "yes", "Yes", show=False),
        Binding("n,escape", "no", "No", show=False),
    ]

    def __init__(self, prompt: str) -> None:
        super().__init__()
        self.prompt = prompt

    def compose(self) -> ComposeResult:
        yield Static(self.prompt + "\n\n[y] yes   [n] no", id="confirm")

    def action_yes(self) -> None:
        self.dismiss(True)

    def action_no(self) -> None:
        self.dismiss(False)


class CreditsScreen(ModalScreen[None]):
    BINDINGS = [
        Binding("escape,q,enter,question_mark", "close", "Close", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Markdown(ABOUT, id="credits")

    def action_close(self) -> None:
        self.dismiss()


class OmaStoreApp(App[None]):
    TITLE = "omastore"
    SUB_TITLE = "omarchy store"
    CSS_PATH = "app.tcss"
    BINDINGS = [
        Binding("slash", "focus_search", "Search", show=True),
        Binding("escape", "blur_search", "Back", show=False),
        Binding("1", "set_tab('themes')", "Themes", show=True),
        Binding("2", "set_tab('plugins')", "Plugins", show=True),
        Binding("3", "set_tab('installed')", "Installed", show=True),
        Binding("i", "do_install", "Install", show=True),
        Binding("a", "do_apply", "Apply", show=True),
        Binding("e", "do_enable", "Enable", show=False),
        Binding("d", "do_disable", "Disable", show=False),
        Binding("u", "do_update", "Update", show=True),
        Binding("x", "do_remove", "Remove", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("f", "cycle_status", "Filter", show=True),
        Binding("v", "cycle_source", "Source", show=True),
        Binding("s", "cycle_sort", "Sort", show=True),
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
        self.selected: Item | None = None
        self.status_text = "loading catalogs…"
        self._readme_key = ""

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("omastore  ·  the omarchy store", id="brand"),
            Horizontal(
                Static("themes", id="tab-themes", classes="tab active"),
                Static("plugins", id="tab-plugins", classes="tab"),
                Static("installed", id="tab-installed", classes="tab"),
                Input(
                    placeholder="search  ·  hue:blue  tag:bar  is:available",
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
            Vertical(
                Static(id="meta"),
                Static(id="palette"),
                Markdown(id="readme"),
                id="detail",
            ),
            id="body",
        )
        yield Static(self.status_text, id="status")
        yield Static(STATUS_CREDIT, id="credits-line")
        yield Footer()

    def on_mount(self) -> None:
        self.tab = self.start_tab
        self._paint_tabs()
        if self.search:
            self.query_one("#search", Input).value = self.search
        self.query_one("#list", OptionList).focus()
        self.load_items()

    def action_focus_search(self) -> None:
        self.query_one("#search", Input).focus()

    def action_blur_search(self) -> None:
        self.query_one("#list", OptionList).focus()

    def action_set_tab(self, tab: Tab) -> None:
        self.tab = tab
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

    def action_refresh(self) -> None:
        self.status_text = "refreshing catalogs…"
        self._status()
        self.load_items(force=True)

    def action_credits(self) -> None:
        self.push_screen(CreditsScreen())

    def action_cycle_status(self) -> None:
        self.filters = cycle_status(self.filters)
        self._rebuild_list()

    def action_cycle_source(self) -> None:
        self.filters = cycle_source(self.filters)
        self._rebuild_list()

    def action_cycle_sort(self) -> None:
        self.filters = cycle_sort(self.filters)
        self._rebuild_list()

    def action_do_install(self) -> None:
        self._act("install")

    def action_do_apply(self) -> None:
        self._act("apply")

    def action_do_enable(self) -> None:
        self._act("enable")

    def action_do_disable(self) -> None:
        self._act("disable")

    def action_do_update(self) -> None:
        self._act("update")

    def action_do_remove(self) -> None:
        self._act("remove")

    @on(Input.Changed, "#search")
    def on_search_changed(self, event: Input.Changed) -> None:
        self.search = event.value
        self._rebuild_list()

    def _active_query(self) -> Query:
        return parse_search(self.search, defaults=self.filters)

    @on(Input.Submitted, "#search")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        self.query_one("#list", OptionList).focus()

    @on(OptionList.OptionHighlighted, "#list")
    def on_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_id:
            self._select_key(event.option_id)

    @on(OptionList.OptionSelected, "#list")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
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
        self._rebuild_list()
        self._status()

    def _paint_tabs(self) -> None:
        for name in ("themes", "plugins", "installed"):
            widget = self.query_one(f"#tab-{name}", Static)
            widget.set_class(name == self.tab, "active")

    def _rebuild_list(self) -> None:
        previous = self.selected.key if self.selected else ""
        self.shown = apply_query(self.items, self._active_query(), self.tab)
        options = [Option(list_prompt(item), id=item.key.replace(":", "__")) for item in self.shown]
        listing = self.query_one("#list", OptionList)
        listing.clear_options()
        if options:
            listing.add_options(options)
            index = next((i for i, item in enumerate(self.shown) if item.key == previous), 0)
            listing.highlighted = index
            self._select_key(self.shown[index].key.replace(":", "__"))
        else:
            self.selected = None
            self._render_detail(None)
        active = self._active_query()
        self.query_one("#filters", Static).update(
            f"filter  {active.label()}    [f] status  [v] source  [s] sort"
        )
        self.query_one("#status", Static).update(
            f"{self.status_text}  ·  {len(self.shown)} shown"
        )

    def _select_key(self, key: str) -> None:
        key = key.replace("__", ":", 1)
        item = next((row for row in self.shown if row.key == key), None)
        self.selected = item
        self._render_detail(item)
        if item and not item.readme:
            self._load_readme(item.key)

    def _render_detail(self, item: Item | None) -> None:
        meta = self.query_one("#meta", Static)
        palette = self.query_one("#palette", Static)
        readme = self.query_one("#readme", Markdown)
        if item is None:
            meta.update("No matches.")
            palette.update("")
            readme.update("_Try another search or switch tabs._")
            return
        actions = []
        if item.can_install:
            actions.append("[i] install")
        if item.can_apply:
            actions.append("[a] apply")
        if item.can_enable:
            actions.append("[e] enable")
        if item.can_disable:
            actions.append("[d] disable")
        if item.can_update:
            actions.append("[u] update")
        if item.can_remove:
            actions.append("[x] remove")
        header = Text()
        header.append(item.name, style="bold")
        header.append("\n")
        header.append(item.status_label or item.kind, style="dim")
        if actions:
            header.append("\n")
            header.append("   ".join(actions), style="green")
        meta.update(header)
        palette.update(palette_text(item.colors) if item.colors else Text(""))
        readme.update(item_markdown(item))

    @work(thread=True, exclusive=True, group="readme")
    def _load_readme(self, key: str) -> None:
        item = next((row for row in self.items if row.key == key), None)
        if item is None or item.readme:
            return
        text = fetch_readme(item)
        self.call_from_thread(self._apply_readme, key, text)

    def _apply_readme(self, key: str, text: str) -> None:
        item = next((row for row in self.items if row.key == key), None)
        if item is None:
            return
        item.readme = text
        if self.selected and self.selected.key == key:
            self.query_one("#readme", Markdown).update(item_markdown(item, text))

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
        prompt = f"{name} {item.kind} “{item.name}”?"
        if name == "install":
            prompt += "\nThis clones the repo with the official omarchy command."
        if name in {"install", "remove", "update"}:

            def confirmed(ok: bool | None, action=name, target=item) -> None:
                if ok:
                    self._run_action(action, target)

            self.push_screen(ConfirmScreen(prompt), confirmed)
            return
        self._run_action(name, item)

    @work(thread=True)
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
