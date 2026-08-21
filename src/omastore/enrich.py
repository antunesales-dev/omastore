from __future__ import annotations

import json
from typing import Any, Callable

from omastore.catalog import fetch_text
from omastore.models import Item

_SHORT_DESCRIPTION = 40
_PLACEHOLDER_LICENSE = "See repository"

Fetch = Callable[[str], str]


def github_raw_candidates(repo: str, relpath: str) -> list[str]:
    """GitHub https repo -> raw.githubusercontent.com/{owner}/{name}/{main,master}/{relpath}"""
    if not repo:
        return []
    cleaned = str(repo).strip().split("#", 1)[0].split("?", 1)[0]
    cleaned = cleaned.rstrip("/").removesuffix(".git")
    if "github.com/" not in cleaned:
        return []
    path = cleaned.split("github.com/", 1)[1]
    if "/tree/" in path:
        return []
    parts = [part for part in path.split("/") if part]
    if len(parts) < 2:
        return []
    owner, name = parts[0], parts[1]
    rel = str(relpath or "").lstrip("/")
    if not rel:
        return []
    return [
        f"https://raw.githubusercontent.com/{owner}/{name}/main/{rel}",
        f"https://raw.githubusercontent.com/{owner}/{name}/master/{rel}",
    ]


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value).strip()
    return ""


def _str_list(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = _text(item)
        if text:
            out.append(text)
    return out


def _blank(value: object) -> bool:
    return not str(value or "").strip()


def _license_missing(value: object) -> bool:
    text = str(value or "").strip()
    return text == "" or text == _PLACEHOLDER_LICENSE


def _name_is_placeholder(item: Item) -> bool:
    name = (item.name or "").strip()
    return name == "" or name == item.id


def _needs_enrichment(item: Item) -> bool:
    description = (item.description or "").strip()
    license_ = (item.license or "").strip()
    version = (item.version or "").strip()
    return (
        len(description) < _SHORT_DESCRIPTION
        or license_ in {"", _PLACEHOLDER_LICENSE}
        or not version
    )


def apply_manifest(item: Item, manifest: dict) -> None:
    """Fill EMPTY fields only. Never overwrite a non-empty catalog value."""
    if not isinstance(manifest, dict):
        return
    filled = False

    description = _text(manifest.get("description"))
    if description and _blank(item.description):
        item.description = description
        filled = True

    version = _text(manifest.get("version"))
    if version and _blank(item.version):
        item.version = version
        filled = True

    license_ = _text(manifest.get("license"))
    if license_ and _license_missing(item.license):
        item.license = license_
        filled = True

    author = _text(manifest.get("author"))
    if author and _blank(item.author):
        item.author = author
        filled = True

    name = _text(manifest.get("name"))
    if name and _name_is_placeholder(item) and name != item.name:
        item.name = name
        filled = True

    kinds = _str_list(manifest.get("kinds"))
    if kinds and not item.kinds:
        item.kinds = list(kinds)
        filled = True

    tags = _str_list(manifest.get("tags")) or list(kinds)
    if tags and not item.tags:
        item.tags = list(tags)
        filled = True

    category = _text(manifest.get("category"))
    if category and _blank(item.category):
        item.category = category
        filled = True

    if filled:
        item.extra_details = True


def enrich_item(item: Item, *, fetch: Fetch | None = None) -> None:
    """Fill thin catalog rows from the author's GitHub manifest.json. Never raise."""
    try:
        if item.first_party or item.builtin:
            return
        if not item.repo or "github.com/" not in item.repo:
            return
        if not _needs_enrichment(item):
            return
        getter = fetch or fetch_text
        for url in github_raw_candidates(item.repo, "manifest.json"):
            try:
                text = getter(url)
            except Exception:
                continue
            if not isinstance(text, str):
                continue
            stripped = text.strip()
            if not stripped or stripped.startswith("404"):
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            apply_manifest(item, payload)
            return
    except Exception:
        return
