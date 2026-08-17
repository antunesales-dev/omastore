from __future__ import annotations

import subprocess
from urllib.parse import urlparse

THEME_CATALOG = "https://omarchytheme.com"
PLUGIN_CATALOG = "https://omarchyplugins.com"


def _clean_url(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip().rstrip("/").removesuffix(".git")
    return text.strip()


def _http_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def repo_url(item) -> str:
    """item.repo or item.install_url, cleaned, or ''."""
    for attr in ("repo", "install_url"):
        cleaned = _clean_url(getattr(item, attr, None))
        if cleaned:
            return cleaned
    return ""


def catalog_url(item) -> str:
    """Marketplace homepage for this kind. Do not invent per-item paths."""
    kind = getattr(item, "kind", None)
    if kind == "theme":
        return THEME_CATALOG
    if kind == "plugin":
        return PLUGIN_CATALOG
    return ""


def urls_for(item) -> dict:
    """{repo, catalog, label} — catalog homepage and author GitHub."""
    name = getattr(item, "name", None)
    ident = getattr(item, "id", None)
    label = str(name or ident or "").strip()
    return {
        "repo": repo_url(item),
        "catalog": catalog_url(item),
        "label": label,
    }


def _xdg_open(url: str) -> None:
    try:
        completed = subprocess.run(
            ["xdg-open", url],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("xdg-open is not available") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "xdg-open failed").strip()
        raise RuntimeError(detail)


def open_url(url: str, *, opener=None) -> dict:
    """Open with xdg-open (Linux). opener(url) injectable for tests."""
    cleaned = _clean_url(url)
    if not cleaned:
        return {"ok": False, "url": "", "message": "no URL to open"}
    if not _http_url(cleaned):
        return {"ok": False, "url": cleaned, "message": "only http(s) URLs can be opened"}
    try:
        (opener or _xdg_open)(cleaned)
    except Exception as exc:
        return {"ok": False, "url": cleaned, "message": str(exc)}
    return {"ok": True, "url": cleaned, "message": f"opened {cleaned}"}


def open_item(item, target: str = "repo", *, opener=None) -> dict:
    """target is 'repo' or 'catalog'."""
    choice = (target or "repo").strip().lower()
    if choice == "repo":
        return open_url(repo_url(item), opener=opener)
    if choice == "catalog":
        return open_url(catalog_url(item), opener=opener)
    return {"ok": False, "url": "", "message": "target must be 'repo' or 'catalog'"}
