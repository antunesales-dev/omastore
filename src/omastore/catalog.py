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
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_text(url: str, timeout: float = 20) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def load_cached(name: str, url: str, *, force: bool = False, ttl: int = DEFAULT_TTL) -> Any:
    path = cache_dir() / name
    if path.exists() and not force:
        age = time.time() - path.stat().st_mtime
        if age < ttl:
            try:
                return _read_json(path)
            except json.JSONDecodeError:
                pass
    try:
        payload = fetch_json(url)
        _write_json(path, payload)
        return payload
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        if path.exists():
            try:
                return _read_json(path)
            except json.JSONDecodeError:
                pass
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
        raw_themes = load_cached("themes-data.json", THEME_CATALOG_URL, force=force)
        if isinstance(raw_themes, list):
            themes = [parse_theme(row) for row in raw_themes if isinstance(row, dict)]
        else:
            theme_error = "unexpected theme catalog shape"
    except CatalogError as exc:
        theme_error = str(exc)

    try:
        raw_plugins = load_cached("plugins-catalog.json", PLUGIN_CATALOG_URL, force=force)
        rows = raw_plugins.get("plugins") if isinstance(raw_plugins, dict) else raw_plugins
        if isinstance(rows, list):
            plugins = [parse_plugin(row) for row in rows if isinstance(row, dict) and row.get("id")]
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
