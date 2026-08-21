from __future__ import annotations

import hashlib
import subprocess
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from omastore.catalog import USER_AGENT, cache_dir

PLUGIN_SITE = "https://omarchyplugins.com"
PREVIEW_TTL = 7 * 24 * 60 * 60
_REPO_BRANCHES = ("main", "master")
_REPO_FILES = (
    "preview.png",
    "preview.webp",
    "preview.jpg",
    "screenshot.png",
    "screenshot.webp",
    "docs/screenshot.png",
    "demo.png",
)
_MAX_DOWNLOAD = 12 * 1024 * 1024


def _http_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _result(*, ok: bool, url: str, path: str, message: str) -> dict:
    return {"ok": ok, "url": url, "path": path, "message": message}


def catalog_preview_urls(item) -> list[str]:
    """If item.preview_url is already http(s), use it.

    If it's a relative path like assets/img/plugins/foo.webp, prefix PLUGIN_SITE.
    """
    raw = getattr(item, "preview_url", None)
    if raw is None:
        return []
    text = str(raw).strip()
    if not text:
        return []
    if _http_url(text):
        return [text]
    if urlparse(text).scheme:
        return []
    return [f"{PLUGIN_SITE.rstrip('/')}/{text.lstrip('/')}"]


def _github_owner_repo(repo: object) -> str:
    if not repo:
        return ""
    text = str(repo).strip()
    marker = "github.com/"
    lowered = text.lower()
    if marker not in lowered:
        return ""
    path = text[lowered.index(marker) + len(marker) :]
    path = path.split("?", 1)[0].split("#", 1)[0].strip("/").removesuffix(".git")
    if "/tree/" in path:
        return ""
    parts = [part for part in path.split("/") if part]
    if len(parts) < 2:
        return ""
    return f"{parts[0]}/{parts[1]}"


def repo_preview_urls(item) -> list[str]:
    """From item.repo GitHub URL, candidates on main/master.

    preview.png, preview.webp, preview.jpg, screenshot.png, screenshot.webp,
    docs/screenshot.png, demo.png
    """
    owner_repo = _github_owner_repo(getattr(item, "repo", None))
    if not owner_repo:
        return []
    return [
        f"https://raw.githubusercontent.com/{owner_repo}/{branch}/{name}"
        for branch in _REPO_BRANCHES
        for name in _REPO_FILES
    ]


def preview_candidates(item) -> list[str]:
    """catalog urls first, then repo urls. Dedupe."""
    seen: set[str] = set()
    urls: list[str] = []
    for url in [*catalog_preview_urls(item), *repo_preview_urls(item)]:
        if url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def cache_path_for(url: str) -> Path:
    """~/.cache/omastore/previews/<sha256[:16]>.<ext> using cache_dir() from catalog."""
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    ext = Path(urlparse(url).path).suffix.lower().lstrip(".") or "bin"
    return cache_dir() / "previews" / f"{digest}.{ext}"


def image_ext(data: bytes) -> str:
    """Return png/jpg/webp/gif/bmp if `data` looks like an image, else ''."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data.startswith(b"GIF8"):
        return "gif"
    if data.startswith(b"BM"):
        return "bmp"
    return ""


def _reject_payload(data: bytes) -> bool:
    head = data.lstrip()[:48].lower()
    return head.startswith((b"<", b"{", b"404", b"not found", b"error"))


def local_preview_path(item) -> Path | None:
    """Installed theme/plugin preview.png on disk, if any."""
    from omastore.local import plugin_preview_file, theme_preview_file

    kind = getattr(item, "kind", "")
    ident = str(getattr(item, "id", "") or "")
    if kind == "theme":
        return theme_preview_file(ident)
    if kind == "plugin":
        return plugin_preview_file(ident)
    return None


def _cached_files(url: str) -> list[Path]:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    direct = cache_path_for(url)
    found: list[Path] = []
    seen: set[Path] = set()
    candidates = [direct]
    if direct.parent.is_dir():
        candidates.extend(sorted(direct.parent.glob(f"{digest}.*")))
    for path in candidates:
        if path.suffix == ".tmp" or not path.is_file() or path in seen:
            continue
        seen.add(path)
        found.append(path)
    return found


def _fresh_cache(url: str, ttl: int) -> Path | None:
    now = time.time()
    for path in _cached_files(url):
        if (now - path.stat().st_mtime) < ttl:
            return path
    return None


def _any_cache(url: str) -> Path | None:
    files = _cached_files(url)
    return files[0] if files else None


def _default_fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read()


def ensure_cached(url: str, *, fetch_bytes=None, ttl: int = PREVIEW_TTL) -> Path | None:
    """Download if missing/stale. fetch_bytes(url)->bytes injectable. Never raise. Return path or None."""
    try:
        if not _http_url(url):
            return None
        fresh = _fresh_cache(url, ttl)
        if fresh is not None:
            return fresh
        data = (fetch_bytes or _default_fetch_bytes)(url)
        if not data or len(data) > _MAX_DOWNLOAD or _reject_payload(data):
            return _any_cache(url)
        ext = image_ext(data)
        path = cache_path_for(url)
        if ext and path.suffix.lower().lstrip(".") != ext:
            path = path.with_suffix(f".{ext}")
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
        return path
    except Exception:
        return _any_cache(url)


def resolve_preview_path(item, *, head=None, fetch_bytes=None) -> Path | None:
    """Local preview file if present, otherwise a cached catalog/repo image."""
    local = local_preview_path(item)
    if local is not None:
        return local
    url = resolve_preview(item, head=head, fetch_bytes=fetch_bytes)
    if not url:
        return None
    return ensure_cached(url, fetch_bytes=fetch_bytes)


def resolve_preview(item, *, head=None, fetch_bytes=None) -> str:
    """Return first candidate URL that exists (optional head(url)->ok bool).

    If no head, return first catalog url or first repo url (don't hit network in
    default resolve except if head provided). Prefer returning
    catalog_preview_urls first item if any, else first repo candidate.
    """
    del fetch_bytes
    if head is None:
        catalog = catalog_preview_urls(item)
        if catalog:
            return catalog[0]
        repo = repo_preview_urls(item)
        return repo[0] if repo else ""
    for url in preview_candidates(item):
        try:
            if head(url):
                return url
        except Exception:
            continue
    return ""


def _xdg_open(target: str) -> None:
    try:
        completed = subprocess.run(
            ["xdg-open", target],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("xdg-open is not available") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "xdg-open failed").strip()
        raise RuntimeError(detail)


def open_preview(item, *, opener=None, fetch_bytes=None) -> dict:
    """{ok, url, path, message}. Prefer a local preview, then a cached catalog/repo file.

    opener(url_or_path) injectable. Refuse non-http remote URLs.
    """
    local = local_preview_path(item)
    if local is not None:
        try:
            (opener or _xdg_open)(local.as_uri())
        except Exception as exc:
            return _result(ok=False, url="", path=str(local), message=str(exc))
        return _result(ok=True, url="", path=str(local), message=f"opened {local}")
    url = resolve_preview(item)
    if not url:
        return _result(ok=False, url="", path="", message="no preview image")
    if not _http_url(url):
        return _result(ok=False, url=url, path="", message="only http(s) URLs can be opened")
    path = ensure_cached(url, fetch_bytes=fetch_bytes)
    if path is None:
        return _result(ok=False, url=url, path="", message="could not download preview")
    try:
        (opener or _xdg_open)(path.as_uri())
    except Exception as exc:
        return _result(ok=False, url=url, path=str(path), message=str(exc))
    return _result(ok=True, url=url, path=str(path), message=f"opened {path}")
