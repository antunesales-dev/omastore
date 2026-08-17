from __future__ import annotations

import argparse
import sys
from typing import Sequence

from omastore import __version__
from omastore.actions import apply_theme, disable_plugin, enable_plugin, install, remove, update
from omastore.catalog import load_store
from omastore.models import Item, Tab


def _load(force: bool = False) -> tuple[list[Item], object]:
    catalogs, items, local = load_store(force=force)
    for err in (catalogs.theme_error, catalogs.plugin_error, getattr(local, "error", "")):
        if err:
            print(err, file=sys.stderr)
    return items, catalogs


def _find(items: list[Item], token: str) -> Item:
    from omastore.catalog import Catalogs

    catalogs = Catalogs(
        themes=[item for item in items if item.kind == "theme"],
        plugins=[item for item in items if item.kind == "plugin"],
    )
    item = catalogs.find(token)
    if item is None:
        raise SystemExit(f"nothing named {token!r}. Try: omastore search {token}")
    return item


def _print_item(item: Item, *, verbose: bool = False) -> None:
    stars = f" ★{item.stars}" if item.stars is not None else ""
    status = f"  [{item.status_label}]" if item.status_label else ""
    print(f"{item.kind:7}  {item.name}{stars}{status}")
    print(f"         {item.key}")
    if item.author:
        print(f"         by {item.author}")
    if item.description:
        print(f"         {item.description}")
    if item.repo:
        print(f"         {item.repo}")
    if verbose:
        if item.tags:
            print(f"         tags: {', '.join(item.tags)}")
        if item.install_url:
            print(f"         install: {item.install_url}")
        if item.install_note:
            print(f"         note: {item.install_note}")
        if item.readme:
            print()
            print(item.readme)


def cmd_search(args: argparse.Namespace) -> int:
    items, _ = _load(force=args.refresh)
    query = " ".join(args.query)
    hits = [item for item in items if item.matches(query)]
    if args.kind:
        hits = [item for item in hits if item.kind == args.kind]
    hits.sort(key=lambda item: (-(item.stars or -1), item.name.lower()))
    if not hits:
        print("no matches")
        return 1
    for item in hits[: args.limit]:
        _print_item(item)
        print()
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    items, _ = _load(force=args.refresh)
    item = _find(items, args.id)
    if args.readme and not item.readme:
        from omastore.catalog import fetch_readme

        item.readme = fetch_readme(item)
    _print_item(item, verbose=True)
    return 0


def _act(args: argparse.Namespace, name: str) -> int:
    items, _ = _load(force=args.refresh)
    item = _find(items, args.id)
    runners = {
        "install": install,
        "apply": apply_theme,
        "enable": enable_plugin,
        "disable": disable_plugin,
        "update": update,
        "remove": remove,
    }
    result = runners[name](item, dry_run=args.dry_run)
    print(result.message)
    return 0 if result.ok else 1


def cmd_list(args: argparse.Namespace) -> int:
    items, _ = _load(force=args.refresh)
    rows = items
    if args.installed:
        rows = [item for item in rows if item.installed]
    if args.kind:
        rows = [item for item in rows if item.kind == args.kind]
    rows.sort(key=lambda item: (item.kind, item.name.lower()))
    for item in rows:
        _print_item(item)
    return 0


def cmd_about(_args: argparse.Namespace) -> int:
    from omastore.credits import ABOUT

    print(ABOUT)
    return 0


def cmd_tui(args: argparse.Namespace) -> int:
    from omastore.app import run_tui

    tab: Tab = args.tab
    run_tui(tab=tab, query=" ".join(args.query))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="omastore",
        description="Search, preview, and install Omarchy themes and plugins without a browser.",
    )
    parser.add_argument("--version", action="version", version=f"omastore {__version__}")
    parser.add_argument("--refresh", action="store_true", help="ignore cached catalogs")
    parser.add_argument("--dry-run", action="store_true", help="print omarchy commands without running them")
    sub = parser.add_subparsers(dest="cmd")

    tui = sub.add_parser("tui", help="open the store TUI (default)")
    tui.add_argument("query", nargs="*", help="optional initial search")
    tui.add_argument("--tab", choices=("themes", "plugins", "installed"), default="themes")
    tui.set_defaults(func=cmd_tui)

    for tab in ("themes", "plugins", "installed"):
        shortcut = sub.add_parser(tab, help=f"open the TUI on the {tab} tab")
        shortcut.add_argument("query", nargs="*")
        shortcut.set_defaults(func=cmd_tui, tab=tab)

    search = sub.add_parser("search", help="search the catalogs")
    search.add_argument("query", nargs="+")
    search.add_argument("--kind", choices=("theme", "plugin"))
    search.add_argument("--limit", type=int, default=20)
    search.set_defaults(func=cmd_search)

    info = sub.add_parser("info", help="show one theme or plugin")
    info.add_argument("id")
    info.add_argument("--readme", action="store_true")
    info.set_defaults(func=cmd_info)

    listing = sub.add_parser("list", help="list catalog and local items")
    listing.add_argument("--installed", action="store_true")
    listing.add_argument("--kind", choices=("theme", "plugin"))
    listing.set_defaults(func=cmd_list)

    for name, help_text in (
        ("install", "install a catalog item with omarchy"),
        ("apply", "apply an installed theme"),
        ("enable", "enable an installed plugin"),
        ("disable", "disable an installed plugin"),
        ("update", "update an installed extra theme or plugin"),
        ("remove", "remove an extra theme or community plugin"),
    ):
        cmd = sub.add_parser(name, help=help_text)
        cmd.add_argument("id")
        cmd.set_defaults(func=lambda args, action=name: _act(args, action))

    refresh = sub.add_parser("refresh", help="download fresh catalogs")
    refresh.set_defaults(func=lambda args: (_load(force=True), print("catalogs refreshed"))[1] or 0)

    about = sub.add_parser("about", help="print catalog credits")
    about.set_defaults(func=cmd_about)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd is None:
        args.cmd = "tui"
        args.query = []
        args.tab = "themes"
        args.func = cmd_tui
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
