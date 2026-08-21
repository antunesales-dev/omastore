import hashlib
import os
import time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

import pytest

from omastore.previews import (
    PLUGIN_SITE,
    PREVIEW_TTL,
    cache_path_for,
    catalog_preview_urls,
    ensure_cached,
    image_ext,
    open_preview,
    preview_candidates,
    repo_preview_urls,
    resolve_preview,
    resolve_preview_path,
)
import omastore.previews as previews

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
_WEBP = b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * 4


def _item(**kwargs) -> SimpleNamespace:
    data = {
        "kind": "plugin",
        "id": "omarchy-overview",
        "preview_url": "",
        "repo": "https://github.com/AyushKr2003/omarchy-overview",
    }
    data.update(kwargs)
    return SimpleNamespace(**data)


def _patch_cache(monkeypatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(previews, "cache_dir", lambda: tmp_path)
    return tmp_path


def _digest(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


@pytest.fixture(autouse=True)
def _no_local_previews(monkeypatch) -> None:
    monkeypatch.setattr(previews, "local_preview_path", lambda _item: None)


def test_catalog_preview_urls_keeps_http() -> None:
    item = _item(preview_url="https://cdn.example/preview.png")
    assert catalog_preview_urls(item) == ["https://cdn.example/preview.png"]
    http = _item(preview_url="http://example.com/shot.jpg")
    assert catalog_preview_urls(http) == ["http://example.com/shot.jpg"]


def test_catalog_preview_urls_prefixes_relative_path() -> None:
    item = _item(preview_url="assets/img/plugins/foo.webp")
    assert catalog_preview_urls(item) == [f"{PLUGIN_SITE}/assets/img/plugins/foo.webp"]
    leading = _item(preview_url="/assets/img/plugins/foo.webp")
    assert catalog_preview_urls(leading) == [f"{PLUGIN_SITE}/assets/img/plugins/foo.webp"]


def test_catalog_preview_urls_empty_and_non_http() -> None:
    assert catalog_preview_urls(_item(preview_url="")) == []
    assert catalog_preview_urls(_item(preview_url=None)) == []
    assert catalog_preview_urls(SimpleNamespace(kind="plugin", id="x")) == []
    assert catalog_preview_urls(_item(preview_url="javascript:alert(1)")) == []
    assert catalog_preview_urls(_item(preview_url="file:///etc/passwd")) == []


def test_repo_preview_urls_on_main_and_master() -> None:
    urls = repo_preview_urls(_item())
    owner = "AyushKr2003/omarchy-overview"
    names = [
        "preview.png",
        "preview.webp",
        "preview.jpg",
        "screenshot.png",
        "screenshot.webp",
        "docs/screenshot.png",
        "demo.png",
    ]
    expected = [
        f"https://raw.githubusercontent.com/{owner}/{branch}/{name}"
        for branch in ("main", "master")
        for name in names
    ]
    assert urls == expected
    assert len(urls) == 14
    assert urls[0].endswith("/main/preview.png")
    assert "omarchyplugins.com" not in "".join(urls)


def test_repo_preview_urls_strips_git_suffix_and_skips_non_github() -> None:
    git = _item(repo="https://github.com/author/theme.git/")
    assert repo_preview_urls(git)[0] == (
        "https://raw.githubusercontent.com/author/theme/main/preview.png"
    )
    assert repo_preview_urls(_item(repo="https://gitlab.com/author/theme")) == []
    assert repo_preview_urls(_item(repo="")) == []
    tree = _item(repo="https://github.com/basecamp/omarchy/tree/quattro/themes/catppuccin")
    assert repo_preview_urls(tree) == []


def test_preview_candidates_catalog_first_then_repo_deduped() -> None:
    catalog = "https://omarchyplugins.com/assets/img/plugins/foo.webp"
    item = _item(preview_url="assets/img/plugins/foo.webp")
    urls = preview_candidates(item)
    assert urls[0] == catalog
    assert urls[1] == (
        "https://raw.githubusercontent.com/AyushKr2003/omarchy-overview/main/preview.png"
    )
    assert urls.count(catalog) == 1

    already = _item(
        preview_url="https://raw.githubusercontent.com/AyushKr2003/omarchy-overview/main/preview.png"
    )
    duped = preview_candidates(already)
    assert duped[0] == already.preview_url
    assert duped.count(already.preview_url) == 1


def test_cache_path_for_uses_sha_prefix_and_extension(monkeypatch, tmp_path: Path) -> None:
    _patch_cache(monkeypatch, tmp_path)
    url = "https://omarchyplugins.com/assets/img/plugins/foo.webp?v=1"
    path = cache_path_for(url)
    assert path == tmp_path / "previews" / f"{_digest(url)}.webp"
    assert path.name.startswith(_digest(url))
    bare = cache_path_for("https://example.com/noext")
    assert bare.suffix == ".bin"


def test_ensure_cached_downloads_when_missing(monkeypatch, tmp_path: Path) -> None:
    _patch_cache(monkeypatch, tmp_path)
    url = "https://example.com/preview.png"
    calls: list[str] = []

    def fetch(target: str) -> bytes:
        calls.append(target)
        return _PNG

    path = ensure_cached(url, fetch_bytes=fetch)
    assert path is not None
    assert path.read_bytes() == _PNG
    assert path == tmp_path / "previews" / f"{_digest(url)}.png"
    assert calls == [url]


def test_ensure_cached_skips_fetch_when_fresh(monkeypatch, tmp_path: Path) -> None:
    _patch_cache(monkeypatch, tmp_path)
    url = "https://example.com/preview.png"
    path = cache_path_for(url)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"OLD")

    def boom(_url: str) -> bytes:
        raise AssertionError("should not fetch")

    assert ensure_cached(url, fetch_bytes=boom).read_bytes() == b"OLD"


def test_ensure_cached_refetches_when_stale(monkeypatch, tmp_path: Path) -> None:
    _patch_cache(monkeypatch, tmp_path)
    url = "https://example.com/preview.png"
    path = cache_path_for(url)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"OLD")
    stale = time.time() - PREVIEW_TTL - 10
    os.utime(path, (stale, stale))
    calls: list[str] = []

    def fetch(target: str) -> bytes:
        calls.append(target)
        return _PNG

    got = ensure_cached(url, fetch_bytes=fetch, ttl=PREVIEW_TTL)
    assert got.read_bytes() == _PNG
    assert calls == [url]


def test_ensure_cached_never_raises(monkeypatch, tmp_path: Path) -> None:
    _patch_cache(monkeypatch, tmp_path)
    url = "https://example.com/preview.png"

    def boom(_url: str) -> bytes:
        raise RuntimeError("offline")

    assert ensure_cached(url, fetch_bytes=boom) is None
    assert ensure_cached("javascript:alert(1)", fetch_bytes=boom) is None
    assert ensure_cached("", fetch_bytes=boom) is None


def test_ensure_cached_keeps_stale_file_if_fetch_fails(monkeypatch, tmp_path: Path) -> None:
    _patch_cache(monkeypatch, tmp_path)
    url = "https://example.com/preview.png"
    path = cache_path_for(url)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"STALE")
    old = time.time() - PREVIEW_TTL - 5
    os.utime(path, (old, old))

    def boom(_url: str) -> bytes:
        raise RuntimeError("offline")

    got = ensure_cached(url, fetch_bytes=boom)
    assert got == path
    assert got.read_bytes() == b"STALE"


def test_resolve_preview_prefers_catalog_without_network() -> None:
    item = _item(preview_url="assets/img/plugins/foo.webp")

    def boom(_url: str):
        raise AssertionError("network")

    assert resolve_preview(item, fetch_bytes=boom) == f"{PLUGIN_SITE}/assets/img/plugins/foo.webp"
    repo_only = _item(preview_url="")
    assert resolve_preview(repo_only, fetch_bytes=boom).endswith("/main/preview.png")
    assert resolve_preview(_item(preview_url="", repo=""), fetch_bytes=boom) == ""


def test_resolve_preview_head_picks_first_existing() -> None:
    item = _item(preview_url="https://omarchyplugins.com/missing.webp")
    probed: list[str] = []

    def head(url: str) -> bool:
        probed.append(url)
        return url.endswith("/main/screenshot.png")

    assert resolve_preview(item, head=head).endswith("/main/screenshot.png")
    assert probed[0] == item.preview_url
    assert any(url.endswith("/main/preview.png") for url in probed)

    def none_ok(_url: str) -> bool:
        return False

    assert resolve_preview(item, head=none_ok) == ""

    def explode(_url: str) -> bool:
        raise RuntimeError("head failed")

    assert resolve_preview(item, head=explode) == ""


def test_open_preview_opens_cached_file_uri(monkeypatch, tmp_path: Path) -> None:
    _patch_cache(monkeypatch, tmp_path)
    url = "https://omarchyplugins.com/assets/img/plugins/foo.webp"
    item = _item(preview_url=url, repo="")
    opened: list[str] = []
    result = open_preview(item, opener=opened.append, fetch_bytes=lambda _u: _WEBP)
    path = cache_path_for(url)
    assert result == {
        "ok": True,
        "url": url,
        "path": str(path),
        "message": f"opened {path}",
    }
    assert opened == [path.as_uri()]
    assert urlparse(opened[0]).scheme == "file"
    assert path.read_bytes() == _WEBP


def test_open_preview_refuses_non_http_and_missing(monkeypatch, tmp_path: Path) -> None:
    _patch_cache(monkeypatch, tmp_path)
    opened: list[str] = []
    missing = open_preview(_item(preview_url="", repo=""), opener=opened.append, fetch_bytes=lambda _u: b"x")
    assert missing["ok"] is False
    assert missing["url"] == ""
    assert missing["path"] == ""
    assert "preview" in missing["message"].lower()
    assert opened == []

    def boom(_url: str) -> bytes:
        raise RuntimeError("offline")

    failed = open_preview(
        _item(preview_url="https://example.com/preview.png", repo=""),
        opener=opened.append,
        fetch_bytes=boom,
    )
    assert failed["ok"] is False
    assert failed["url"] == "https://example.com/preview.png"
    assert failed["path"] == ""
    assert opened == []

    monkeypatch.setattr(previews, "resolve_preview", lambda _item, **_kwargs: "file:///tmp/x.png")
    refused = open_preview(_item(), opener=opened.append, fetch_bytes=lambda _u: b"x")
    assert refused["ok"] is False
    assert refused["url"] == "file:///tmp/x.png"
    assert "http" in refused["message"]
    assert opened == []


def test_open_preview_opener_errors_surface_in_message(monkeypatch, tmp_path: Path) -> None:
    _patch_cache(monkeypatch, tmp_path)
    item = _item(preview_url="https://example.com/preview.png", repo="")

    def boom(_target: str) -> None:
        raise RuntimeError("viewer missing")

    result = open_preview(item, opener=boom, fetch_bytes=lambda _u: _PNG)
    assert result["ok"] is False
    assert result["url"] == "https://example.com/preview.png"
    assert result["path"]
    assert result["message"] == "viewer missing"


def test_open_preview_defaults_to_xdg_open(monkeypatch, tmp_path: Path) -> None:
    _patch_cache(monkeypatch, tmp_path)
    calls: list[list[str]] = []

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(args, **_kwargs):
        calls.append(list(args))
        return Result()

    monkeypatch.setattr(previews.subprocess, "run", fake_run)
    item = _item(preview_url="https://example.com/preview.png", repo="")
    result = open_preview(item, fetch_bytes=lambda _u: _PNG)
    assert result["ok"] is True
    assert calls == [["xdg-open", Path(result["path"]).as_uri()]]


def test_default_fetch_uses_safety_fetch_bytes(monkeypatch, tmp_path: Path) -> None:
    _patch_cache(monkeypatch, tmp_path)
    seen: list[str] = []

    def fake_fetch(url: str, **_kwargs) -> bytes:
        seen.append(url)
        return _PNG

    monkeypatch.setattr(previews, "allowed_fetch_url", lambda _url: True)
    monkeypatch.setattr(previews, "_safety_fetch_bytes", fake_fetch)
    url = "https://example.com/preview.png"
    path = ensure_cached(url)
    assert path is not None
    assert path.read_bytes() == _PNG
    assert seen == [url]


def test_image_ext_sniffs_magic() -> None:
    assert image_ext(b"\x89PNG\r\n\x1a\nrest") == "png"
    assert image_ext(b"\xff\xd8\xff\xdb") == "jpg"
    assert image_ext(b"RIFF....WEBP....") == "webp"
    assert image_ext(b"<html>404</html>") == ""
    assert image_ext(b"PNGDATA") == ""


def test_ensure_cached_rejects_html(monkeypatch, tmp_path: Path) -> None:
    _patch_cache(monkeypatch, tmp_path)
    url = "https://example.com/preview.png"
    assert ensure_cached(url, fetch_bytes=lambda _u: b"<!DOCTYPE html><html>404</html>") is None
    assert ensure_cached(url, fetch_bytes=lambda _u: b"404: Not Found") is None
    assert ensure_cached(url, fetch_bytes=lambda _u: b"PNGDATA") is None
    assert ensure_cached(url, fetch_bytes=lambda _u: b"x") is None
    assert not list(tmp_path.glob("previews/*"))


def test_ensure_cached_sniffs_extension_when_url_has_none(monkeypatch, tmp_path: Path) -> None:
    _patch_cache(monkeypatch, tmp_path)
    url = "https://github.com/user-attachments/assets/abc-def"
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
    path = ensure_cached(url, fetch_bytes=lambda _u: png)
    assert path is not None
    assert path.suffix == ".png"
    assert path.read_bytes() == png


def test_resolve_preview_path_prefers_local(monkeypatch, tmp_path: Path) -> None:
    shot = tmp_path / "preview.png"
    shot.write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setattr(previews, "local_preview_path", lambda _item: shot)

    def boom(_url: str) -> bytes:
        raise AssertionError("network")

    path = resolve_preview_path(_item(preview_url="https://example.com/preview.png"), fetch_bytes=boom)
    assert path == shot


def test_resolve_preview_path_tries_next_when_first_is_not_image(monkeypatch, tmp_path: Path) -> None:
    _patch_cache(monkeypatch, tmp_path)
    catalog = "https://omarchyplugins.com/missing.webp"
    item = _item(preview_url=catalog)
    calls: list[str] = []

    def fetch(url: str) -> bytes:
        calls.append(url)
        if url == catalog:
            return b"<!DOCTYPE html><html>404</html>"
        if url.endswith("/main/preview.png"):
            return _PNG
        return b"404: Not Found"

    path = resolve_preview_path(item, fetch_bytes=fetch)
    assert path is not None
    assert path.read_bytes() == _PNG
    assert calls[0] == catalog
    assert calls[1].endswith("/main/preview.png")
    assert catalog not in str(path)


def test_open_preview_opens_local_file(monkeypatch, tmp_path: Path) -> None:
    shot = tmp_path / "preview.png"
    shot.write_bytes(b"x")
    monkeypatch.setattr(previews, "local_preview_path", lambda _item: shot)
    opened: list[str] = []
    result = open_preview(_item(), opener=opened.append, fetch_bytes=lambda _u: b"nope")
    assert result["ok"] is True
    assert result["path"] == str(shot)
    assert opened == [shot.as_uri()]
