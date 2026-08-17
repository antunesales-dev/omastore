from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from omastore.catalog import DEFAULT_TTL, cache_dir
from omastore.local import git_head, installed_plugin_path, installed_theme_path
from omastore.models import Item

CACHE_NAME = "upstream-revs.json"
GIT_TIMEOUT = 20
CATALOG_COMMIT_ATTRS = (
    "listingValidatedCommit",
    "listing_validated_commit",
    "upstreamObservedCommit",
    "upstream_observed_commit",
)


def outdated_items(items: list[Item]) -> list[Item]:
    return [item for item in items if getattr(item, "outdated", False)]


def mark_outdated(items: list[Item], local: Any | None = None) -> list[Item]:
    """Set item.outdated / installed_rev / latest_rev on installed extras.

    For extra themes: compare `git rev-parse HEAD` in ~/.config/omarchy/themes/<slug>
    to the catalog listing commit if present, else `git ls-remote <repo> HEAD` (cache
    in ~/.cache/omastore/upstream-revs.json for 6 hours).

    For community plugins (not first_party): same against
    ~/.config/omarchy/plugins/<id>.

    Skip builtin/stock/first_party. Never raise on git failures — leave outdated=False.
    """
    for item in items:
        try:
            _mark_one(item, local)
        except Exception:
            item.outdated = False
    return items


def _mark_one(item: Item, local: Any | None) -> None:
    item.outdated = False
    if not _eligible(item, local):
        return
    path = _install_path(item)
    if path is None:
        return
    installed = git_head(path)
    if not installed:
        return
    item.installed_rev = installed
    latest = _catalog_commit(item) or git_ls_remote(_repo_url(item))
    if not latest:
        return
    item.latest_rev = latest
    item.outdated = not _revs_match(installed, latest)


def _eligible(item: Item, local: Any | None) -> bool:
    if item.first_party:
        return False
    if item.kind == "theme":
        extra = item.extra
        if local is not None:
            extra_slugs = getattr(local, "extra_slugs", None)
            if extra_slugs is not None:
                extra = item.id in extra_slugs
        return bool(extra)
    if item.builtin:
        return False
    installed = item.installed
    if local is not None:
        plugins = getattr(local, "plugins", None) or {}
        row = plugins.get(item.id)
        if isinstance(row, dict):
            installed = True
            if row.get("firstParty") or row.get("first_party"):
                return False
    return bool(installed)


def _install_path(item: Item) -> Path | None:
    if item.kind == "theme":
        return installed_theme_path(item.id)
    return installed_plugin_path(item.id)


def _catalog_commit(item: Item) -> str:
    for name in CATALOG_COMMIT_ATTRS:
        value = getattr(item, name, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _repo_url(item: Item) -> str:
    return (item.repo or item.install_url or "").strip()


def _revs_match(left: str, right: str) -> bool:
    a = left.lower().strip()
    b = right.lower().strip()
    if not a or not b:
        return False
    if a == b:
        return True
    return min(len(a), len(b)) >= 7 and (a.startswith(b) or b.startswith(a))


def git_ls_remote(repo: str, *, ttl: int = DEFAULT_TTL) -> str:
    if not repo:
        return ""
    cached = _cached_rev(repo, ttl=ttl)
    if cached:
        return cached
    try:
        completed = subprocess.run(
            ["git", "ls-remote", repo, "HEAD"],
            check=False,
            text=True,
            capture_output=True,
            timeout=GIT_TIMEOUT,
            env=_git_env(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if completed.returncode != 0:
        return ""
    rev = _parse_ls_remote(completed.stdout)
    if rev:
        _store_rev(repo, rev)
    return rev


def _git_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def _parse_ls_remote(stdout: str) -> str:
    for line in stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "HEAD":
            return parts[0]
        if parts:
            return parts[0]
    return ""


def _cache_file() -> Path:
    return cache_dir() / CACHE_NAME


def _load_cache() -> dict[str, Any]:
    path = _cache_file()
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_cache(payload: dict[str, Any]) -> None:
    path = _cache_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(path)


def _cached_rev(repo: str, *, ttl: int) -> str:
    row = _load_cache().get(repo)
    if not isinstance(row, dict):
        return ""
    rev = str(row.get("rev") or "").strip()
    try:
        checked = float(row.get("ts") or 0)
    except (TypeError, ValueError):
        return ""
    if not rev or time.time() - checked >= ttl:
        return ""
    return rev


def _store_rev(repo: str, rev: str) -> None:
    payload = _load_cache()
    payload[repo] = {"rev": rev, "ts": time.time()}
    try:
        _write_cache(payload)
    except OSError:
        return
