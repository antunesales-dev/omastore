"""stdio MCP server: browse and audit the same catalogs. Not a store."""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Callable

from omastore import __version__
from omastore.credits import (
    OMASTORE_REPO,
    PLUGIN_STORE_AUTHOR,
    PLUGIN_STORE_NAME,
    PLUGIN_STORE_URL,
    THEME_STORE_AUTHOR,
    THEME_STORE_NAME,
    THEME_STORE_URL,
)
from omastore.filters import Query, apply_query, parse_search
from omastore.models import Item
from omastore.packs import PACKS, get_pack

PROTOCOL = "2024-11-05"
CREDITS = {
    "note": "omastore does not approve listings and is not a competing store.",
    "themes": {"author": THEME_STORE_AUTHOR, "site": THEME_STORE_NAME, "url": THEME_STORE_URL},
    "plugins": {"author": PLUGIN_STORE_AUTHOR, "site": PLUGIN_STORE_NAME, "url": PLUGIN_STORE_URL},
    "omastore": OMASTORE_REPO,
}

_TRUE = {"1", "true", "yes", "on"}


def mutate_allowed() -> bool:
    for key in ("OMASTORE_MCP_ALLOW_MUTATE", "OMSTORE_MCP_ALLOW_MUTATE"):
        if os.environ.get(key, "").strip().lower() in _TRUE:
            return True
    return False


def load_items(*, force: bool = False) -> list[Item]:
    from omastore.catalog import load_store

    _catalogs, items, _local = load_store(force=force)
    return items


def _find(items: list[Item], token: str) -> Item | None:
    from omastore.catalog import Catalogs

    catalogs = Catalogs(
        themes=[item for item in items if item.kind == "theme"],
        plugins=[item for item in items if item.kind == "plugin"],
    )
    return catalogs.find(token)


def item_payload(item: Item, *, compact: bool = True) -> dict[str, Any]:
    source = "builtin" if (item.first_party or item.builtin) else "community"
    row: dict[str, Any] = {
        "key": item.key,
        "kind": item.kind,
        "id": item.id,
        "name": item.name,
        "author": item.author,
        "description": item.description,
        "repo": item.repo,
        "stars": item.stars,
        "verification": item.verification_label,
        "warnings": list(item.warnings),
        "installed": item.installed,
        "enabled": item.enabled,
        "builtin": bool(item.builtin or item.first_party),
        "source": source,
        "outdated": bool(item.outdated),
        "category": item.category,
        "kind_hint": "bar-widget" if item.kind == "plugin" and "bar" in " ".join(item.tags).lower() else item.kind,
    }
    if not compact:
        row["version"] = item.version
        row["license"] = item.license
        row["tags"] = list(item.tags)
        row["install_url"] = item.install_url
        row["readme"] = item.readme
        row["status"] = item.status_label
    return row


def _ok(payload: dict[str, Any]) -> dict[str, Any]:
    payload.setdefault("credits", CREDITS)
    return {
        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}],
        "isError": False,
    }


def _err(message: str) -> dict[str, Any]:
    return _ok({"ok": False, "error": message}) | {"isError": True}


def _limit(value: object, default: int = 20, cap: int = 50) -> int:
    try:
        n = int(value) if value is not None else default
    except (TypeError, ValueError):
        n = default
    return max(1, min(cap, n))


def tool_search(args: dict[str, Any], items: list[Item]) -> dict[str, Any]:
    text = str(args.get("query") or args.get("text") or "").strip()
    query = parse_search(text)
    kind = str(args.get("kind") or query.kind or "all").lower()
    if args.get("installed") is True:
        query = query.with_status("installed")
    if args.get("verified") is True or str(args.get("verified") or "").lower() in {"yes", "true"}:
        query = Query(**{**query.__dict__, "verified": "yes"})
    if args.get("verified") is False or str(args.get("verified") or "").lower() in {"no", "unverified"}:
        query = Query(**{**query.__dict__, "verified": "no"})
    stars = args.get("stars")
    if stars is not None:
        try:
            query = Query(**{**query.__dict__, "min_stars": max(0, int(stars))})
        except (TypeError, ValueError):
            pass
    if kind == "plugin":
        hits = apply_query(items, query, "plugins")
    elif kind == "theme":
        hits = apply_query(items, query, "themes")
    else:
        hits = apply_query(items, query, "themes") + apply_query(items, query, "plugins")
    limit = _limit(args.get("limit"))
    return _ok({"ok": True, "count": min(len(hits), limit), "total": len(hits), "items": [item_payload(i) for i in hits[:limit]]})


def tool_info(args: dict[str, Any], items: list[Item]) -> dict[str, Any]:
    token = str(args.get("id") or "").strip()
    if not token:
        return _err("id is required (theme:slug or plugin:id)")
    item = _find(items, token)
    if item is None:
        return _err(f"nothing named {token!r}")
    if args.get("readme"):
        from omastore.catalog import fetch_readme
        from omastore.enrich import enrich_item

        enrich_item(item)
        if not item.readme:
            item.readme = fetch_readme(item)
    return _ok({"ok": True, "item": item_payload(item, compact=False)})


def tool_installed(args: dict[str, Any], items: list[Item]) -> dict[str, Any]:
    kind = str(args.get("kind") or "all").lower()
    rows = [item for item in items if item.installed]
    if kind in {"theme", "plugin"}:
        rows = [item for item in rows if item.kind == kind]
    rows = sorted(rows, key=lambda item: (item.kind, item.name.lower(), item.id.lower()))
    return _ok({"ok": True, "count": len(rows), "items": [item_payload(item) for item in rows]})


def tool_packs(args: dict[str, Any], items: list[Item]) -> dict[str, Any]:
    rows = []
    for pack in PACKS:
        listed, pending = pack.counts(items)
        installed = sum(1 for item in pack.members(items) if item.installed)
        rows.append(
            {
                "id": pack.id,
                "title": pack.title,
                "blurb": pack.blurb,
                "listed": listed,
                "installed": installed,
                "to_install": pending,
            }
        )
    return _ok({"ok": True, "packs": rows})


def tool_pack(args: dict[str, Any], items: list[Item]) -> dict[str, Any]:
    pack_id = str(args.get("id") or "").strip()
    if not pack_id:
        return tool_packs(args, items)
    pack = get_pack(pack_id)
    if pack is None:
        return _err(f"unknown pack {pack_id!r}")
    members = pack.listed(items)
    return _ok(
        {
            "ok": True,
            "id": pack.id,
            "title": pack.title,
            "blurb": pack.blurb,
            "items": [
                {**item_payload(item), "mark": "installed" if item.installed else "to_install"}
                for item in members
            ],
        }
    )


def tool_audit(_args: dict[str, Any], items: list[Item]) -> dict[str, Any]:
    from omastore.local import hidden_entries_by_plugin
    from omastore.updates import outdated_items

    unverified = [
        item_payload(item)
        for item in items
        if item.kind == "plugin"
        and item.installed
        and not item.first_party
        and not item.builtin
        and item.verification_label == "unverified"
    ]
    warned = [
        item_payload(item)
        for item in items
        if item.installed and item.warnings
    ]
    outdated = [item_payload(item) for item in outdated_items(items)]
    hidden = hidden_entries_by_plugin()
    return _ok(
        {
            "ok": True,
            "unverified_installed": unverified,
            "installed_with_warnings": warned,
            "outdated": outdated,
            "hidden_entries": hidden,
        }
    )


def tool_hidden_widgets(args: dict[str, Any], _items: list[Item]) -> dict[str, Any]:
    from omastore.local import hidden_bar_widgets

    plugin_id = str(args.get("id") or "").strip()
    if not plugin_id:
        return _err("id is required")
    hidden = hidden_bar_widgets(plugin_id)
    return _ok({"ok": True, "id": plugin_id, "hidden": hidden})


def tool_outdated(_args: dict[str, Any], items: list[Item]) -> dict[str, Any]:
    from omastore.updates import outdated_items

    rows = outdated_items(items)
    return _ok({"ok": True, "count": len(rows), "items": [item_payload(item) for item in rows]})


def tool_pack_install(args: dict[str, Any], items: list[Item]) -> dict[str, Any]:
    if not mutate_allowed():
        return _err("mutate disabled; set OMASTORE_MCP_ALLOW_MUTATE=1 to enable install/remove")
    pack_id = str(args.get("id") or "").strip()
    pack = get_pack(pack_id)
    if pack is None:
        return _err(f"unknown pack {pack_id!r}")
    pending = pack.pending(items)
    if not pending:
        return _ok({"ok": True, "message": "nothing to install", "id": pack.id})
    if not args.get("confirm"):
        return _ok(
            {
                "ok": False,
                "need_confirm": True,
                "id": pack.id,
                "preview": "\n".join(item.key for item in pending) + "\npass confirm=true to proceed",
            }
        )
    from omastore.actions import install_pack
    from omastore.scan import first_issue, scan_items

    scans = scan_items(pending)
    issue = first_issue(scans)
    accept = bool(args.get("accept_scan_risks"))
    if issue is not None and not issue.allows_install(accept):
        from omastore.scan import scan_payload

        return _ok(
            {
                "ok": False,
                "scan_failed": bool(issue.error or issue.source == "failed"),
                "need_accept_scan_risks": not bool(issue.error or issue.source == "failed"),
                "blocked": issue.item_key,
                "scan": scan_payload(issue),
                "message": issue.cli_block_message(),
            }
        )
    by_key = {row.item_key: row for row in scans}
    results = install_pack(pending, dry_run=bool(args.get("dry_run")), accept_scan_risks=accept, scans=by_key)
    failed = next((item for item, result in results if not result.ok), None)
    return _ok(
        {
            "ok": failed is None,
            "id": pack.id,
            "stopped_at": failed.key if failed else "",
            "count": len(results),
        }
    )


def tool_scan(args: dict[str, Any], items: list[Item]) -> dict[str, Any]:
    from omastore.scan import scan_item, scan_payload

    token = str(args.get("id") or "").strip()
    if not token:
        return _err("id is required (theme:slug or plugin:id)")
    item = _find(items, token)
    if item is None:
        return _err(f"nothing named {token!r}")
    result = scan_item(item)
    payload = scan_payload(result)
    payload["ok"] = True
    return _ok(payload)


def _confirm_preview(action: str, item: Item) -> str:
    lines = [f"{action} {item.key}"]
    if item.repo:
        lines.append(item.repo)
    if item.verification_label:
        lines.append(f"verification: {item.verification_label}")
    for warning in item.warnings:
        lines.append(warning)
    if action in {"remove", "disable"}:
        from omastore.local import layout_remove_warnings

        lines.extend(layout_remove_warnings(item.id))
    lines.append("Community plugins and themes run unsandboxed.")
    lines.append("pass confirm=true to proceed")
    return "\n".join(lines)


def _mutate(action: str, args: dict[str, Any], items: list[Item]) -> dict[str, Any]:
    if not mutate_allowed():
        return _err("mutate disabled; set OMASTORE_MCP_ALLOW_MUTATE=1 to enable install/remove")
    token = str(args.get("id") or "").strip()
    if not token:
        return _err("id is required")
    item = _find(items, token)
    if item is None:
        return _err(f"nothing named {token!r}")
    allowed = {
        "install": item.can_install,
        "remove": item.can_remove,
        "enable": item.can_enable,
        "disable": item.can_disable,
    }
    if not allowed.get(action):
        return _err(f"cannot {action} {item.key}")
    if not args.get("confirm"):
        preview = _confirm_preview(action, item)
        if action == "install":
            preview += "\nPre-install scan still runs when confirm=true. Fetch/parse failure cannot be overridden."
        return _ok(
            {
                "ok": False,
                "need_confirm": True,
                "action": action,
                "item": item_payload(item),
                "preview": preview,
            }
        )
    from omastore.actions import disable_plugin, enable_plugin, install, remove

    dry = bool(args.get("dry_run"))
    if action == "install":
        from omastore.scan import scan_item, scan_payload

        scanned = scan_item(item)
        accept = bool(args.get("accept_scan_risks"))
        if not scanned.allows_install(accept):
            return _ok(
                {
                    "ok": False,
                    "need_accept_scan_risks": not bool(scanned.error or scanned.source == "failed"),
                    "scan_failed": bool(scanned.error or scanned.source == "failed"),
                    "action": action,
                    "item": item_payload(item),
                    "scan": scan_payload(scanned),
                    "message": scanned.cli_block_message(),
                }
            )
        result = install(
            item,
            dry_run=dry,
            scan_result=scanned,
            accept_scan_risks=accept,
        )
    else:
        runners = {
            "remove": remove,
            "enable": enable_plugin,
            "disable": disable_plugin,
        }
        result = runners[action](item, dry_run=dry)
    return _ok(
        {
            "ok": result.ok,
            "action": action,
            "item": item_payload(item),
            "message": result.message,
            "command": result.command,
        }
    )


def tool_install(args: dict[str, Any], items: list[Item]) -> dict[str, Any]:
    return _mutate("install", args, items)


def tool_remove(args: dict[str, Any], items: list[Item]) -> dict[str, Any]:
    return _mutate("remove", args, items)


def tool_enable(args: dict[str, Any], items: list[Item]) -> dict[str, Any]:
    return _mutate("enable", args, items)


def tool_disable(args: dict[str, Any], items: list[Item]) -> dict[str, Any]:
    return _mutate("disable", args, items)


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    spec: dict[str, Any] = {"type": "object", "properties": properties, "additionalProperties": False}
    if required:
        spec["required"] = required
    return spec


_READ_TOOLS = {
    "search": (
        "Search limehawk theme and HANCORE plugin catalogs. Same listings as omastore CLI.",
        _schema(
            {
                "query": {"type": "string", "description": "words or prefixes like hue:blue is:installed"},
                "kind": {"type": "string", "enum": ["theme", "plugin", "all"]},
                "installed": {"type": "boolean"},
                "verified": {"type": ["boolean", "string"]},
                "stars": {"type": "integer", "description": "minimum star rating"},
                "limit": {"type": "integer"},
            }
        ),
        tool_search,
    ),
    "info": (
        "Show one theme or plugin: repo, verification, warnings, description.",
        _schema({"id": {"type": "string"}, "readme": {"type": "boolean"}}, ["id"]),
        tool_info,
    ),
    "installed": (
        "List installed themes and plugins (builtin vs community, on/off, outdated).",
        _schema({"kind": {"type": "string", "enum": ["theme", "plugin", "all"]}}),
        tool_installed,
    ),
    "packs": (
        "List hand-picked verified plugin packs from the HANCORE catalog.",
        _schema({}),
        tool_packs,
    ),
    "pack": (
        "Show one pack and its members (installed vs to install).",
        _schema({"id": {"type": "string"}}, ["id"]),
        tool_pack,
    ),
    "audit": (
        "Flag risk: unverified installed plugins, catalog warnings, outdated extras, hiddenEntries on the bar. Use scan for a no-execute tree audit before install.",
        _schema({}),
        tool_audit,
    ),
    "hidden_widgets": (
        "Read hiddenEntries for one plugin id from shell.json. Does not write.",
        _schema({"id": {"type": "string"}}, ["id"]),
        tool_hidden_widgets,
    ),
    "outdated": (
        "List installed extras whose git HEAD is behind upstream.",
        _schema({}),
        tool_outdated,
    ),
    "scan": (
        "Static pre-install scan of one theme or plugin. Fetches a copy, never executes QML or install commands. Fail closed.",
        _schema({"id": {"type": "string"}}, ["id"]),
        tool_scan,
    ),
}

_MUTATE_TOOLS = {
    "install": (
        "Install with official omarchy after a no-execute scan. Requires confirm=true and a clean scan (or accept_scan_risks). Fetch/parse failure cannot be overridden. Off unless OMASTORE_MCP_ALLOW_MUTATE=1.",
        _schema(
            {
                "id": {"type": "string"},
                "confirm": {"type": "boolean"},
                "dry_run": {"type": "boolean"},
                "accept_scan_risks": {
                    "type": "boolean",
                    "description": "Proceed despite scan findings. Ignored if the scan itself failed.",
                },
            },
            ["id"],
        ),
        tool_install,
    ),
    "pack_install": (
        "Install a suggested pack with official omarchy. Requires confirm=true and a clean scan per member (or accept_scan_risks). Stops on the first blocked plugin.",
        _schema(
            {
                "id": {"type": "string", "description": "pack id, e.g. everyday"},
                "confirm": {"type": "boolean"},
                "dry_run": {"type": "boolean"},
                "accept_scan_risks": {"type": "boolean"},
            },
            ["id"],
        ),
        tool_pack_install,
    ),
    "remove": (
        "Remove with official omarchy after restoring hiddenEntries. Requires confirm=true.",
        _schema({"id": {"type": "string"}, "confirm": {"type": "boolean"}, "dry_run": {"type": "boolean"}}, ["id"]),
        tool_remove,
    ),
    "enable": (
        "Enable an installed plugin. Requires confirm=true.",
        _schema({"id": {"type": "string"}, "confirm": {"type": "boolean"}, "dry_run": {"type": "boolean"}}, ["id"]),
        tool_enable,
    ),
    "disable": (
        "Disable a plugin after restoring hiddenEntries. Requires confirm=true.",
        _schema({"id": {"type": "string"}, "confirm": {"type": "boolean"}, "dry_run": {"type": "boolean"}}, ["id"]),
        tool_disable,
    ),
}


def tool_map() -> dict[str, tuple[str, dict[str, Any], Callable[..., dict[str, Any]]]]:
    tools = dict(_READ_TOOLS)
    if mutate_allowed():
        tools.update(_MUTATE_TOOLS)
    return tools


def list_tools() -> list[dict[str, Any]]:
    return [
        {"name": name, "description": desc, "inputSchema": schema}
        for name, (desc, schema, _fn) in tool_map().items()
    ]


def call_tool(name: str, arguments: dict[str, Any] | None = None, *, items: list[Item] | None = None) -> dict[str, Any]:
    tools = tool_map()
    if name not in tools:
        return _err(f"unknown tool {name!r}")
    args = arguments or {}
    if not isinstance(args, dict):
        return _err("arguments must be an object")
    if items is None:
        items = load_items()
    _desc, _schema, fn = tools[name]
    return fn(args, items)


def handle_rpc(message: dict[str, Any], *, items: list[Item] | None = None) -> dict[str, Any] | None:
    method = message.get("method")
    msg_id = message.get("id")
    if method is None:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32600, "message": "invalid request"}}
    if str(method).startswith("notifications/"):
        return None
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": PROTOCOL,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "omastore", "version": __version__},
                "instructions": (
                    "Browse limehawk (omarchytheme.com) and HANCORE (omarchyplugins.com) catalogs. "
                    "omastore does not approve listings. Community plugins run unsandboxed. "
                    "Install still scans a copy of the repo without executing it; confirm=true is not enough "
                    "when the scan finds issues (pass accept_scan_risks) and a failed scan cannot be overridden."
                ),
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": list_tools()}}
    if method == "tools/call":
        params = message.get("params") or {}
        name = str(params.get("name") or "")
        arguments = params.get("arguments") or {}
        result = call_tool(name, arguments, items=items)
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"method not found: {method}"}}


def _write_message(payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
    sys.stdout.buffer.flush()


def _read_message() -> dict[str, Any] | None:
    headers: dict[str, str] = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        stripped = line.decode("ascii", errors="replace").rstrip("\r\n")
        if stripped == "":
            break
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    length = int(headers.get("content-length") or "0")
    if length <= 0:
        return None
    body = sys.stdin.buffer.read(length)
    if not body:
        return None
    data = json.loads(body.decode("utf-8"))
    return data if isinstance(data, dict) else None


def run_stdio() -> None:
    while True:
        try:
            message = _read_message()
        except (OSError, json.JSONDecodeError, UnicodeError, ValueError):
            return
        if message is None:
            return
        reply = handle_rpc(message)
        if reply is not None:
            _write_message(reply)
