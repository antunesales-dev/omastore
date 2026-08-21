import json
import os

from omastore.mcp import (
    call_tool,
    handle_rpc,
    list_tools,
    mutate_allowed,
)
from omastore.models import Item


def _plugin(**kwargs) -> Item:
    data = {
        "kind": "plugin",
        "id": "demo",
        "name": "Demo",
        "verification": "verified",
        "stars": 3,
        "install_url": "https://github.com/a/demo",
        "repo": "https://github.com/a/demo",
    }
    data.update(kwargs)
    return Item(**data)


def test_mutate_allowed_default_off(monkeypatch) -> None:
    monkeypatch.delenv("OMASTORE_MCP_ALLOW_MUTATE", raising=False)
    monkeypatch.delenv("OMSTORE_MCP_ALLOW_MUTATE", raising=False)
    assert mutate_allowed() is False
    names = {tool["name"] for tool in list_tools()}
    assert "search" in names
    assert "audit" in names
    assert "scan" in names
    assert "install" not in names
    assert "remove" not in names


def test_mutate_tools_listed_when_flag_on(monkeypatch) -> None:
    monkeypatch.setenv("OMASTORE_MCP_ALLOW_MUTATE", "1")
    names = {tool["name"] for tool in list_tools()}
    assert "install" in names
    assert "remove" in names


def test_search_and_packs_with_fake_items() -> None:
    items = [
        _plugin(id="stocks", name="Stocks", description="stock widget", verification="unverified", stars=1),
        _plugin(id="dev.git", name="Git", category="Developer Tools", verification="verified", stars=8),
        Item(kind="theme", id="lumon", name="Lumon", stars=4),
    ]
    result = call_tool("search", {"query": "git", "kind": "plugin"}, items=items)
    payload = json.loads(result["content"][0]["text"])
    assert payload["ok"] is True
    assert payload["credits"]["plugins"]["author"] == "HANCORE"
    assert payload["credits"]["themes"]["author"] == "limehawk"
    assert payload["items"][0]["id"] == "dev.git"
    packs = json.loads(call_tool("packs", {}, items=items)["content"][0]["text"])
    ids = [row["id"] for row in packs["packs"]]
    assert "everyday" in ids
    assert "developer" in ids


def test_audit_flags_unverified_and_hidden(monkeypatch) -> None:
    items = [
        _plugin(id="raw", name="Raw", verification="unverified", installed=True, enabled=True),
        _plugin(id="ok", name="Ok", verification="verified", installed=True, warnings=["talks to the network"]),
        _plugin(id="old", name="Old", installed=True, extra=True, outdated=True),
    ]
    monkeypatch.setattr(
        "omastore.local.hidden_entries_by_plugin",
        lambda **_k: {"groups.plugin": ["omarchy.clock"]},
    )
    payload = json.loads(call_tool("audit", {}, items=items)["content"][0]["text"])
    assert [row["id"] for row in payload["unverified_installed"]] == ["raw"]
    assert [row["id"] for row in payload["installed_with_warnings"]] == ["ok"]
    assert [row["id"] for row in payload["outdated"]] == ["old"]
    assert payload["hidden_entries"] == {"groups.plugin": ["omarchy.clock"]}
    assert payload["credits"]["note"].startswith("omastore does not approve")


def test_hidden_widgets_does_not_write(monkeypatch, tmp_path) -> None:
    from omastore import local

    path = tmp_path / "shell.json"
    path.write_text('{"bar":{"layout":{"right":[{"id":"hider","hiddenEntries":["omarchy.clock"]}]}}}', encoding="utf-8")
    monkeypatch.setattr(local, "shell_json_path", lambda: path)
    before = path.read_text(encoding="utf-8")
    payload = json.loads(call_tool("hidden_widgets", {"id": "hider"}, items=[])["content"][0]["text"])
    assert payload["hidden"] == ["omarchy.clock"]
    assert path.read_text(encoding="utf-8") == before


def test_install_refused_without_confirm(monkeypatch) -> None:
    monkeypatch.setenv("OMASTORE_MCP_ALLOW_MUTATE", "1")
    item = _plugin(id="demo", name="Demo")
    called: list[str] = []
    monkeypatch.setattr("omastore.actions.install", lambda *a, **k: called.append("install"))
    payload = json.loads(call_tool("install", {"id": "plugin:demo"}, items=[item])["content"][0]["text"])
    assert payload["need_confirm"] is True
    assert "https://github.com/a/demo" in payload["preview"]
    assert called == []


def _clean_scan(item):
    from omastore.scan import ScanResult

    return ScanResult(
        item_key=item.key,
        item_id=item.id,
        item_name=item.name,
        kind=item.kind,
        repo=item.repo or "",
        verdict="clean",
        source="tree",
    )


def _dirty_scan(item, *, failed: bool = False):
    from omastore.scan import Finding, ScanResult

    return ScanResult(
        item_key=item.key,
        item_id=item.id,
        item_name=item.name,
        kind=item.kind,
        repo=item.repo or "",
        verdict="block",
        findings=[Finding("block", "network", "main.qml", 1, "fetch(")],
        source="failed" if failed else "tree",
        error="nope" if failed else "",
    )


def test_install_confirm_still_scans(monkeypatch) -> None:
    monkeypatch.setenv("OMASTORE_MCP_ALLOW_MUTATE", "1")
    item = _plugin()
    called: list[str] = []
    monkeypatch.setattr("omastore.scan.scan_item", lambda target, **_k: _dirty_scan(target))
    monkeypatch.setattr("omastore.actions.install", lambda *a, **k: called.append("install"))
    payload = json.loads(
        call_tool("install", {"id": "plugin:demo", "confirm": True}, items=[item])["content"][0]["text"]
    )
    assert payload["ok"] is False
    assert payload["need_accept_scan_risks"] is True
    assert payload["scan"]["verdict"] == "block"
    assert called == []


def test_install_accept_scan_risks_with_confirm(monkeypatch) -> None:
    monkeypatch.setenv("OMASTORE_MCP_ALLOW_MUTATE", "1")
    item = _plugin()
    called: list[str] = []

    class _Ok:
        ok = True
        message = "installed"
        command = ["omarchy", "plugin", "add"]

    monkeypatch.setattr("omastore.scan.scan_item", lambda target, **_k: _dirty_scan(target))
    monkeypatch.setattr("omastore.actions.install", lambda *a, **k: called.append("install") or _Ok())
    payload = json.loads(
        call_tool(
            "install",
            {"id": "plugin:demo", "confirm": True, "accept_scan_risks": True},
            items=[item],
        )["content"][0]["text"]
    )
    assert payload["ok"] is True
    assert called == ["install"]


def test_install_failed_scan_cannot_be_overridden(monkeypatch) -> None:
    monkeypatch.setenv("OMASTORE_MCP_ALLOW_MUTATE", "1")
    item = _plugin()
    called: list[str] = []
    monkeypatch.setattr("omastore.scan.scan_item", lambda target, **_k: _dirty_scan(target, failed=True))
    monkeypatch.setattr("omastore.actions.install", lambda *a, **k: called.append("install"))
    payload = json.loads(
        call_tool(
            "install",
            {"id": "plugin:demo", "confirm": True, "accept_scan_risks": True},
            items=[item],
        )["content"][0]["text"]
    )
    assert payload["ok"] is False
    assert payload["scan_failed"] is True
    assert called == []


def test_scan_tool_is_read_only(monkeypatch) -> None:
    item = _plugin()
    monkeypatch.setattr("omastore.scan.scan_item", lambda target, **_k: _clean_scan(target))
    payload = json.loads(call_tool("scan", {"id": "plugin:demo"}, items=[item])["content"][0]["text"])
    assert payload["ok"] is True
    assert payload["verdict"] == "clean"


def test_install_unknown_when_mutate_off(monkeypatch) -> None:
    monkeypatch.delenv("OMASTORE_MCP_ALLOW_MUTATE", raising=False)
    monkeypatch.delenv("OMSTORE_MCP_ALLOW_MUTATE", raising=False)
    result = call_tool("install", {"id": "plugin:demo", "confirm": True}, items=[_plugin()])
    payload = json.loads(result["content"][0]["text"])
    assert payload["ok"] is False
    assert "unknown tool" in payload["error"]
    assert result["isError"] is True


def test_handle_rpc_initialize_and_list() -> None:
    init = handle_rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert init["result"]["serverInfo"]["name"] == "omastore"
    assert "limehawk" in init["result"]["instructions"]
    assert "unsandboxed" in init["result"]["instructions"]
    assert "juancasanueva" not in init["result"]["instructions"]
    assert "plugin-manager" not in init["result"]["instructions"]
    listed = handle_rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = {tool["name"] for tool in listed["result"]["tools"]}
    assert "audit" in names
    assert "scan" in names
    assert handle_rpc({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_mcp_subcommand_wired() -> None:
    from omastore.cli import build_parser, cmd_mcp

    args = build_parser().parse_args(["mcp"])
    assert args.func is cmd_mcp