from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from omastore import __version__
from omastore.models import Item, parse_plugin, parse_theme

USER_AGENT = f"omastore/{__version__} (+https://github.com/antunesales-dev/omastore)"
THEME_CATALOG_URL = (
    "https://raw.githubusercontent.com/limehawk/omarchy-theme-website/"
    "main/src/data/themes-data.json"
)
PLUGIN_CATALOG_URL = (
    "https://raw.githubusercontent.com/HANCORE-linux/omarchy-plugin-marketplace/"
    "main/site/catalog.json"
)
DEFAULT_TTL = 6 * 60 * 60
# HANCORE site/catalog.json passed the 12 MiB repo-download cap (13.2 MiB on 2026-10-08).
# Catalog JSON only. Repo archives stay on safety.MAX_FETCH_BYTES.
CATALOG_MAX_BYTES = 32 * 1024 * 1024
_CACHE_FILES = ("themes-data.json", "plugins-catalog.json")
# Fields parse_theme / parse_plugin read. The HANCORE file also carries
# verification commits and fingerprints the TUI never shows.
_THEME_FIELDS = frozenset({
    "slug",
    "id",
    "name",
    "github_owner",
    "description",
    "github_url",
    "stars",
    "colors_json",
    "primary_hue",
    "readme_text",
    "preview_url",
    "security_warnings",
    "is_builtin",
    "is_curated",
    "updated_at",
    "last_scraped_at",
})
_PLUGIN_FIELDS = frozenset({
    "id",
    "name",
    "author",
    "description",
    "repo",
    "stars",
    "version",
    "category",
    "tags",
    "previewImage",
    "previewThumbnail",
    "installNote",
    "installAvailable",
    "verificationStatus",
    "license",
    "sourceType",
    "listedAt",
    "addedAt",
    "repositoryUpdatedAt",
    "repoUpdatedAt",
})


def catalog_cache_age_label(*, now: float | None = None) -> str:
    """Human age of the older catalog cache file, e.g. '5h old · r refresh'."""
    now = time.time() if now is None else now
    mtimes: list[float] = []
    root = cache_dir()
    for name in _CACHE_FILES:
        path = root / name
        try:
            mtimes.append(path.stat().st_mtime)
        except OSError:
            continue
    if not mtimes:
        return ""
    age = max(0.0, now - min(mtimes))
    if age < 90:
        return "just now"
    if age < 3600:
        return f"{int(age // 60)}m old"
    hours = int(age // 3600)
    return f"{hours}h old · r refresh"


def cache_dir() -> Path:
    root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    path = root / "omastore"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(path)


def fetch_json(url: str, timeout: float = 30) -> Any:
    from omastore.safety import fetch_bytes

    return json.loads(fetch_bytes(url, timeout=timeout, limit=CATALOG_MAX_BYTES).decode("utf-8"))


def fetch_text(url: str, timeout: float = 20) -> str:
    from omastore.safety import fetch_text as _fetch_text

    return _fetch_text(url, timeout=timeout)


def _slim_row(row: Any, fields: frozenset[str]) -> Any:
    if not isinstance(row, dict):
        return row
    return {key: row[key] for key in fields if key in row}


def slim_catalog(name: str, payload: Any) -> Any:
    """Drop catalog keys the TUI does not read."""
    if name.startswith("themes"):
        if isinstance(payload, list):
            return [_slim_row(row, _THEME_FIELDS) for row in payload]
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("plugins"), list):
        return {"plugins": [_slim_row(row, _PLUGIN_FIELDS) for row in payload["plugins"]]}
    if isinstance(payload, list):
        return [_slim_row(row, _PLUGIN_FIELDS) for row in payload]
    return payload


def _catalog_rows(name: str, payload: Any) -> list:
    if name.startswith("themes"):
        return payload if isinstance(payload, list) else []
    if isinstance(payload, dict):
        rows = payload.get("plugins")
        return rows if isinstance(rows, list) else []
    return payload if isinstance(payload, list) else []


def _needs_slim(name: str, payload: Any) -> bool:
    fields = _THEME_FIELDS if name.startswith("themes") else _PLUGIN_FIELDS
    if not name.startswith("themes") and isinstance(payload, dict) and set(payload) - {"plugins"}:
        return True
    for row in _catalog_rows(name, payload):
        if isinstance(row, dict) and set(row) - fields:
            return True
    return False


def _store_slim(name: str, path: Path, payload: Any) -> Any:
    if not _needs_slim(name, payload):
        return payload
    slim = slim_catalog(name, payload)
    _write_json(path, slim)
    return slim


def load_cached(name: str, url: str, *, force: bool = False, ttl: int = DEFAULT_TTL) -> tuple[Any, str]:
    """Return catalog JSON and a warning when the refresh failed and the cache was kept."""
    path = cache_dir() / name
    if path.exists() and not force:
        age = time.time() - path.stat().st_mtime
        if age < ttl:
            try:
                return _store_slim(name, path, _read_json(path)), ""
            except json.JSONDecodeError:
                pass
    try:
        payload = slim_catalog(name, fetch_json(url))
        _write_json(path, payload)
        return payload, ""
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError, OSError) as exc:
        if path.exists():
            try:
                cached = _store_slim(name, path, _read_json(path))
            except json.JSONDecodeError:
                cached = None
            if cached is not None:
                return cached, f"could not refresh {name}: {exc}"
        raise CatalogError(f"could not load {name}: {exc}") from exc


class CatalogError(RuntimeError):
    pass


@dataclass
class Catalogs:
    themes: list[Item]
    plugins: list[Item]
    theme_error: str = ""
    plugin_error: str = ""

    def all_items(self) -> list[Item]:
        return [*self.themes, *self.plugins]

    def find(self, token: str) -> Item | None:
        token = token.strip()
        if not token:
            return None
        kind = ""
        ident = token
        if ":" in token and token.split(":", 1)[0] in {"theme", "plugin"}:
            kind, ident = token.split(":", 1)
        matches = [
            item
            for item in self.all_items()
            if (not kind or item.kind == kind)
            and (item.id == ident or item.name.lower() == ident.lower() or item.key == token)
        ]
        if len(matches) == 1:
            return matches[0]
        if kind:
            exact = [item for item in matches if item.id == ident]
            return exact[0] if exact else (matches[0] if matches else None)
        exact = [item for item in matches if item.id == ident]
        if len(exact) == 1:
            return exact[0]
        return None


def load_catalogs(*, force: bool = False) -> Catalogs:
    themes: list[Item] = []
    plugins: list[Item] = []
    theme_error = ""
    plugin_error = ""
    try:
        raw_themes, theme_note = load_cached("themes-data.json", THEME_CATALOG_URL, force=force)
        if isinstance(raw_themes, list):
            themes = [parse_theme(row) for row in raw_themes if isinstance(row, dict)]
            theme_error = theme_note
        else:
            theme_error = "unexpected theme catalog shape"
    except CatalogError as exc:
        theme_error = str(exc)

    try:
        raw_plugins, plugin_note = load_cached("plugins-catalog.json", PLUGIN_CATALOG_URL, force=force)
        rows = raw_plugins.get("plugins") if isinstance(raw_plugins, dict) else raw_plugins
        if isinstance(rows, list):
            plugins = [parse_plugin(row) for row in rows if isinstance(row, dict) and row.get("id")]
            plugin_error = plugin_note
        else:
            plugin_error = "unexpected plugin catalog shape"
    except CatalogError as exc:
        plugin_error = str(exc)

    return Catalogs(themes=themes, plugins=plugins, theme_error=theme_error, plugin_error=plugin_error)


def load_store(*, force: bool = False) -> tuple[Catalogs, list[Item], object]:
    from omastore.local import load_local, overlay

    from omastore.updates import mark_outdated

    catalogs = load_catalogs(force=force)
    local = load_local()
    items = overlay(catalogs.all_items(), local)
    items = mark_outdated(items, local)
    return catalogs, items, local


def github_readme_urls(item: Item) -> list[str]:
    repo = item.repo
    if "github.com/" not in repo:
        return []
    path = repo.split("github.com/", 1)[1]
    if "/tree/" in path:
        return []
    owner_repo = "/".join(path.split("/")[:2])
    branches = ["main", "master"]
    names = ["README.md", "readme.md", "README.MD"]
    return [
        f"https://raw.githubusercontent.com/{owner_repo}/{branch}/{name}"
        for branch in branches
        for name in names
    ]


def fetch_readme(item: Item) -> str:
    if item.readme:
        return item.readme
    last_error = ""
    for url in github_readme_urls(item):
        try:
            text = fetch_text(url)
            if text.strip() and not text.startswith("404"):
                return text
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = str(exc)
            continue
    if last_error:
        return f"_Could not load README: {last_error}_"
    return "_No README found._"
