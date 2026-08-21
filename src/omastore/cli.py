from __future__ import annotations

import argparse
import sys
from typing import Sequence

from omastore import __version__
from omastore.actions import apply_theme, disable_plugin, enable_plugin, install, remove, update
from omastore.catalog import load_store
from omastore.filters import Query, apply_query, parse_search
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


def _print_item(item: Item, *, verbose: bool = False, mark: str = "") -> None:
    stars = f" ★{item.stars}" if item.stars is not None else ""
    status = f"  [{item.status_label}]" if item.status_label else ""
    prefix = f"{mark} " if mark else ""
    print(f"{item.kind:7}  {prefix}{item.name}{stars}{status}")
    print(f"         {item.key}")
    if item.author:
        print(f"         by {item.author}")
    if item.description:
        print(f"         {item.description}")
    if item.repo:
        print(f"         {item.repo}")
    if verbose:
        if item.version:
            print(f"         version: {item.version}")
        if item.license:
            print(f"         license: {item.license}")
        if item.category:
            print(f"         category: {item.category}")
        if item.tags:
            print(f"         tags: {', '.join(item.tags)}")
        if item.extra_details:
            print("         extra details from repository manifest")
        if item.install_url:
            print(f"         install: {item.install_url}")
        if item.install_note:
            print(f"         note: {item.install_note}")
        if item.readme:
            print()
            print(item.readme)


def _query_from_args(args: argparse.Namespace, text: str = "") -> Query:
    query = parse_search(text)
    if getattr(args, "kind", None):
        query = Query(**{**query.__dict__, "kind": args.kind})
    if getattr(args, "installed", False):
        query = query.with_status("installed")
    if getattr(args, "available", False):
        query = query.with_status("available")
    if getattr(args, "hue", None):
        query = Query(**{**query.__dict__, "hue": args.hue.lower()})
    if getattr(args, "category", None):
        query = Query(**{**query.__dict__, "category": args.category.lower()})
    if getattr(args, "tag", None):
        query = Query(**{**query.__dict__, "tag": args.tag.lower()})
    if getattr(args, "source", None):
        query = query.with_source(args.source)
    if getattr(args, "sort", None):
        query = query.with_sort(args.sort)
    if getattr(args, "verified", False):
        query = Query(**{**query.__dict__, "verified": "yes"})
    if getattr(args, "builtin", False):
        query = query.with_source("builtin")
    if getattr(args, "stars", None):
        query = Query(**{**query.__dict__, "min_stars": max(0, int(args.stars))})
    return query


def _add_filter_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--kind", choices=("theme", "plugin"))
    parser.add_argument("--installed", action="store_true")
    parser.add_argument("--available", action="store_true", help="not installed and installable")
    parser.add_argument("--hue", help="theme hue, e.g. blue")
    parser.add_argument("--category", help="plugin category, e.g. widgets")
    parser.add_argument("--tag", help="plugin or theme tag")
    parser.add_argument("--source", choices=("community", "builtin"))
    parser.add_argument("--verified", action="store_true")
    parser.add_argument("--builtin", action="store_true", help="built-in / stock plugins")
    parser.add_argument("--stars", type=int, help="minimum star rating")
    parser.add_argument("--sort", choices=("stars", "name", "recent"), default="stars")


def cmd_search(args: argparse.Namespace) -> int:
    items, _ = _load(force=args.refresh)
    query = _query_from_args(args, " ".join(args.query))
    if query.kind == "plugin":
        hits = apply_query(items, query, "plugins")
    elif query.kind == "theme":
        hits = apply_query(items, query, "themes")
    else:
        hits = apply_query(items, query, "themes") + apply_query(items, query, "plugins")
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
    from omastore.enrich import enrich_item

    enrich_item(item)
    if args.readme and not item.readme:
        from omastore.catalog import fetch_readme

        item.readme = fetch_readme(item)
    _print_item(item, verbose=True)
    return 0


def _act(args: argparse.Namespace, name: str) -> int:
    items, _ = _load(force=args.refresh)
    item = _find(items, args.id)
    allowed = {
        "install": item.can_install,
        "apply": item.can_apply,
        "enable": item.can_enable,
        "disable": item.can_disable,
        "update": item.can_update,
        "remove": item.can_remove,
    }
    if not allowed.get(name):
        print(f"cannot {name} {item.key}")
        return 1
    if name in {"install", "remove", "update", "enable"} and not args.yes and not args.dry_run:
        print(item.key)
        if item.repo:
            print(item.repo)
        if item.verification_label:
            print(item.verification_label)
        for warning in item.warnings:
            print(warning)
        print("pass --yes to proceed")
        return 2
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
    query = _query_from_args(args)
    if args.kind == "plugin":
        rows = apply_query(items, query, "plugins")
    elif args.kind == "theme":
        rows = apply_query(items, query, "themes")
    else:
        rows = apply_query(items, query, "themes") + apply_query(items, query, "plugins")
    for item in rows:
        _print_item(item)
    return 0


def cmd_about(_args: argparse.Namespace) -> int:
    from omastore.credits import ABOUT

    print(ABOUT)
    return 0


def cmd_desktop(_args: argparse.Namespace) -> int:
    from omastore.desktop import install_desktop

    for path in install_desktop():
        print(path)
    print("Omastore is in the app launcher (Super + Space).")
    return 0


def cmd_outdated(args: argparse.Namespace) -> int:
    from omastore.updates import outdated_items

    items, _ = _load(force=args.refresh)
    rows = outdated_items(items)
    if not rows:
        print("nothing outdated")
        return 0
    for item in rows:
        print(f"{item.kind:7}  {item.name}  {item.installed_rev[:8]} -> {item.latest_rev[:8]}")
        print(f"         {item.key}")
    return 0


def cmd_try(args: argparse.Namespace) -> int:
    from omastore.preview import remember_and_apply

    items, _ = _load(force=args.refresh)
    item = _find(items, args.id)
    if item.kind != "theme":
        raise SystemExit("try is for themes")
    result = remember_and_apply(item.name)
    print(result.get("message") or result)
    return 0 if result.get("ok") else 1


def cmd_revert(_args: argparse.Namespace) -> int:
    from omastore.preview import revert

    result = revert()
    print(result.get("message") or result)
    return 0 if result.get("ok") else 1


def cmd_open(args: argparse.Namespace) -> int:
    from omastore.links import open_item

    items, _ = _load(force=args.refresh)
    item = _find(items, args.id)
    result = open_item(item, "catalog" if args.catalog else "repo")
    print(result.get("message") or result)
    return 0 if result.get("ok") else 1


def cmd_preview(args: argparse.Namespace) -> int:
    from omastore.previews import open_preview

    items, _ = _load(force=args.refresh)
    item = _find(items, args.id)
    result = open_preview(item)
    print(result.get("message") or result)
    return 0 if result.get("ok") else 1


def cmd_packs(args: argparse.Namespace) -> int:
    from omastore.packs import PACK_CREDIT, PACKS

    items, _ = _load(force=args.refresh)
    print(PACK_CREDIT)
    print()
    for pack in PACKS:
        listed, pending = pack.counts(items)
        installed = sum(1 for item in pack.members(items) if item.installed)
        print(f"{pack.id:10}  {pack.title}")
        print(f"            {pack.blurb}")
        print(f"            {listed} listed  ·  {installed} installed  ·  {pending} to install")
        print()
    return 0


def cmd_pack_show(args: argparse.Namespace, pack_id: str) -> int:
    from omastore.packs import PACK_CREDIT, get_pack

    pack = get_pack(pack_id)
    if pack is None:
        print(f"unknown pack {pack_id!r}. Try: omastore packs")
        return 1
    items, _ = _load(force=args.refresh)
    members = pack.listed(items)
    listed, pending = pack.counts(items)
    installed = sum(1 for item in members if item.installed)
    print(f"{pack.id:10}  {pack.title}")
    print(f"            {pack.blurb}")
    print(f"            {listed} listed  ·  {installed} installed  ·  {pending} to install")
    print(f"            {PACK_CREDIT}")
    print()
    if not members:
        print("no verified plugins matched")
        return 1
    for item in members:
        _print_item(item, mark="●" if item.installed else "○")
        print()
    return 0


def cmd_pack_install(args: argparse.Namespace, pack_id: str) -> int:
    from omastore.actions import install_pack
    from omastore.packs import describe_pack_install, get_pack

    pack = get_pack(pack_id)
    if pack is None:
        print(f"unknown pack {pack_id!r}. Try: omastore packs")
        return 1
    items, _ = _load(force=args.refresh)
    pending = pack.pending(items)
    if not pending:
        print("nothing to install")
        return 0
    if not args.yes and not args.dry_run:
        print(describe_pack_install(pack, pending))
        print("pass --yes to proceed")
        return 2
    failed = False
    for item, result in install_pack(pending, dry_run=args.dry_run):
        print(f"{item.key}: {result.message}")
        if not result.ok:
            failed = True
    return 1 if failed else 0


def cmd_pack_remove(args: argparse.Namespace, pack_id: str) -> int:
    from omastore.actions import remove_pack
    from omastore.packs import describe_pack_remove, get_pack

    pack = get_pack(pack_id)
    if pack is None:
        print(f"unknown pack {pack_id!r}. Try: omastore packs")
        return 1
    items, _ = _load(force=args.refresh)
    rows = pack.removable(items)
    if not rows:
        print("nothing to remove")
        return 0
    if not args.yes and not args.dry_run:
        print(describe_pack_remove(pack, rows))
        print("pass --yes to proceed")
        return 2
    failed = False
    for item, result in remove_pack(rows, dry_run=args.dry_run):
        print(f"{item.key}: {result.message}")
        if not result.ok:
            failed = True
    return 1 if failed else 0


def cmd_pack(args: argparse.Namespace) -> int:
    if args.target in {"install", "remove", "uninstall"}:
        if not args.id:
            print(f"usage: omastore pack {args.target} <pack>")
            return 2
        if args.target == "install":
            return cmd_pack_install(args, args.id)
        return cmd_pack_remove(args, args.id)
    return cmd_pack_show(args, args.target)


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
    parser.add_argument("--yes", action="store_true", help="confirm install/remove/update")
    sub = parser.add_subparsers(dest="cmd")

    tui = sub.add_parser("tui", help="open the store TUI (default)")
    tui.add_argument("query", nargs="*", help="optional initial search")
    tui.add_argument("--tab", choices=("themes", "plugins", "installed", "packs"), default="themes")
    tui.set_defaults(func=cmd_tui)

    for tab in ("themes", "plugins", "installed"):
        shortcut = sub.add_parser(tab, help=f"open the TUI on the {tab} tab")
        shortcut.add_argument("query", nargs="*")
        shortcut.set_defaults(func=cmd_tui, tab=tab)

    search = sub.add_parser("search", help="search and filter the catalogs")
    search.add_argument("query", nargs="*", help="words or prefixes like hue:blue is:available")
    search.add_argument("--limit", type=int, default=20)
    _add_filter_flags(search)
    search.set_defaults(func=cmd_search)

    info = sub.add_parser("info", help="show one theme or plugin")
    info.add_argument("id")
    info.add_argument("--readme", action="store_true")
    info.set_defaults(func=cmd_info)

    listing = sub.add_parser("list", help="list catalog and local items")
    _add_filter_flags(listing)
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

    desktop = sub.add_parser("desktop", help="install the Omarchy app launcher entry")
    desktop.set_defaults(func=cmd_desktop)

    outdated = sub.add_parser("outdated", help="list installed extras that can update")
    outdated.set_defaults(func=cmd_outdated)

    try_cmd = sub.add_parser("try", help="preview a theme; remember the previous one")
    try_cmd.add_argument("id")
    try_cmd.set_defaults(func=cmd_try)

    revert_cmd = sub.add_parser("revert", help="restore the theme from before try")
    revert_cmd.set_defaults(func=cmd_revert)

    open_cmd = sub.add_parser("open", help="open the author repo or catalog site")
    open_cmd.add_argument("id")
    open_cmd.add_argument("--catalog", action="store_true", help="open the catalog homepage")
    open_cmd.set_defaults(func=cmd_open)

    preview_cmd = sub.add_parser("preview", help="open a catalog or repo screenshot")
    preview_cmd.add_argument("id")
    preview_cmd.set_defaults(func=cmd_preview)

    packs = sub.add_parser("packs", help="list suggested plugin packs from the HANCORE catalog")
    packs.set_defaults(func=cmd_packs)

    pack = sub.add_parser("pack", help="show, install, or remove a suggested plugin pack")
    pack.add_argument("target", help="pack id, or install/remove")
    pack.add_argument("id", nargs="?", help="pack id when using install or remove")
    pack.set_defaults(func=cmd_pack)
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
