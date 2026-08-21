from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from omastore.models import Item, slugify


def _home() -> Path:
    return Path.home()


def user_themes_dir() -> Path:
    return _home() / ".config" / "omarchy" / "themes"


def user_plugins_dir() -> Path:
    return _home() / ".config" / "omarchy" / "plugins"


def stock_themes_dir() -> Path:
    omarchy = os.environ.get("OMARCHY_PATH", "/usr/share/omarchy")
    return Path(omarchy) / "themes"


def _git_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def git_head(path: Path) -> str:
    try:
        if not path.exists():
            return ""
        completed = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            check=False,
            text=True,
            capture_output=True,
            timeout=10,
            env=_git_env(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def _existing_child(root: Path, name: str) -> Path | None:
    if not name:
        return None
    direct = root / name
    if direct.is_dir() or direct.is_symlink():
        return direct
    if not root.is_dir():
        return None
    needle = name.lower()
    for entry in root.iterdir():
        if entry.name.lower() == needle and (entry.is_dir() or entry.is_symlink()):
            return entry
    return None


def installed_theme_path(slug: str) -> Path | None:
    return _existing_child(user_themes_dir(), slug)


def installed_plugin_path(plugin_id: str) -> Path | None:
    return _existing_child(user_plugins_dir(), plugin_id)


_PREVIEW_NAMES = ("preview.png", "preview.webp", "preview.jpg", "preview.jpeg")


def _preview_in(folder: Path | None) -> Path | None:
    if folder is None or not folder.is_dir():
        return None
    for name in _PREVIEW_NAMES:
        path = folder / name
        if path.is_file():
            return path
    return None


def theme_preview_file(slug: str) -> Path | None:
    """User theme preview first, then the stock Omarchy copy."""
    found = _preview_in(installed_theme_path(slug))
    if found:
        return found
    return _preview_in(_existing_child(stock_themes_dir(), slug))


def plugin_preview_file(plugin_id: str) -> Path | None:
    return _preview_in(installed_plugin_path(plugin_id))


def run_omarchy(*args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["omarchy", *args],
        check=check,
        text=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )


@dataclass
class LocalState:
    current_theme: str = ""
    current_slug: str = ""
    theme_names: dict[str, str] = field(default_factory=dict)  # slug -> display
    extra_slugs: set[str] = field(default_factory=set)
    stock_slugs: set[str] = field(default_factory=set)
    plugins: dict[str, dict] = field(default_factory=dict)
    omarchy_ok: bool = True
    error: str = ""

    def theme_display(self, slug: str) -> str:
        return self.theme_names.get(slug, slug)


def _dir_slugs(path: Path) -> set[str]:
    if not path.is_dir():
        return set()
    return {entry.name.lower() for entry in path.iterdir() if entry.is_dir() or entry.is_symlink()}


def load_local() -> LocalState:
    state = LocalState()
    state.extra_slugs = _dir_slugs(user_themes_dir())
    state.stock_slugs = _dir_slugs(stock_themes_dir())

    try:
        listed = run_omarchy("theme", "list")
        current = run_omarchy("theme", "current")
        plugins = run_omarchy("plugin", "list", "--json")
    except FileNotFoundError:
        state.omarchy_ok = False
        state.error = "omarchy CLI not found on PATH"
        return state

    if listed.returncode == 0:
        for line in listed.stdout.splitlines():
            name = line.strip()
            if name:
                state.theme_names[slugify(name)] = name
    if current.returncode == 0:
        state.current_theme = current.stdout.strip()
        state.current_slug = slugify(state.current_theme)
    if plugins.returncode == 0 and plugins.stdout.strip():
        try:
            rows = json.loads(plugins.stdout)
        except json.JSONDecodeError:
            rows = []
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict) and row.get("id"):
                    state.plugins[str(row["id"])] = row
    elif plugins.returncode != 0:
        state.error = plugins.stderr.strip() or "could not list plugins"
    return state


def overlay(items: list[Item], local: LocalState) -> list[Item]:
    known_theme_slugs = {item.id for item in items if item.kind == "theme"}
    known_plugin_ids = {item.id for item in items if item.kind == "plugin"}
    result: list[Item] = []

    for item in items:
        if item.kind == "theme":
            item.installed = item.id in local.theme_names or item.id in local.extra_slugs or item.id in local.stock_slugs
            item.current = item.id == local.current_slug
            item.extra = item.id in local.extra_slugs
            item.builtin = item.builtin or (item.id in local.stock_slugs and item.id not in local.extra_slugs)
        else:
            row = local.plugins.get(item.id)
            if row:
                item.installed = True
                item.enabled = bool(row.get("enabled"))
                item.first_party = bool(row.get("firstParty")) or item.first_party
        result.append(item)

    for slug, name in local.theme_names.items():
        if slug in known_theme_slugs:
            continue
        result.append(
            Item(
                kind="theme",
                id=slug,
                name=name,
                installed=True,
                current=slug == local.current_slug,
                extra=slug in local.extra_slugs,
                builtin=slug in local.stock_slugs and slug not in local.extra_slugs,
                local_only=True,
                description="Installed locally. Not listed in the community catalog.",
            )
        )
    for slug in local.extra_slugs | local.stock_slugs:
        if slug in known_theme_slugs or slug in local.theme_names:
            continue
        result.append(
            Item(
                kind="theme",
                id=slug,
                name=slug,
                installed=True,
                current=slug == local.current_slug,
                extra=slug in local.extra_slugs,
                builtin=slug in local.stock_slugs and slug not in local.extra_slugs,
                local_only=True,
                description="Installed locally. Not listed in the community catalog.",
            )
        )
    for plugin_id, row in local.plugins.items():
        if plugin_id in known_plugin_ids:
            continue
        result.append(
            Item(
                kind="plugin",
                id=plugin_id,
                name=str(row.get("name") or plugin_id),
                installed=True,
                enabled=bool(row.get("enabled")),
                first_party=bool(row.get("firstParty")),
                builtin=bool(row.get("firstParty")),
                local_only=True,
                tags=list(row.get("kinds") or []),
                description="Installed locally. Not listed in the community catalog.",
            )
        )
    return result
