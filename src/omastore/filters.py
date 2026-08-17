from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from omastore.models import Item, Tab

STATUS_CYCLE = ("all", "installed", "available", "extra", "stock", "current")
SOURCE_CYCLE = ("all", "community", "builtin")
SORT_CYCLE = ("stars", "name", "recent")
PREFIXES = {
    "is": "status",
    "src": "source",
    "source": "source",
    "hue": "hue",
    "cat": "category",
    "category": "category",
    "tag": "tag",
    "kind": "kind",
    "verified": "verified",
    "sort": "sort",
}


@dataclass(frozen=True)
class Query:
    text: str = ""
    status: str = "all"
    source: str = "all"
    hue: str = "all"
    category: str = "all"
    tag: str = "all"
    kind: str = "all"
    verified: str = "all"
    sort: str = "stars"

    def with_status(self, status: str) -> Query:
        return replace(self, status=status)

    def with_source(self, source: str) -> Query:
        return replace(self, source=source)

    def with_sort(self, sort: str) -> Query:
        return replace(self, sort=sort)

    def label(self) -> str:
        parts = [f"is:{self.status}"]
        if self.source != "all":
            parts.append(f"src:{self.source}")
        if self.hue != "all":
            parts.append(f"hue:{self.hue}")
        if self.category != "all":
            parts.append(f"cat:{self.category}")
        if self.tag != "all":
            parts.append(f"tag:{self.tag}")
        if self.verified != "all":
            parts.append(f"verified:{self.verified}")
        parts.append(f"sort:{self.sort}")
        if self.text:
            parts.insert(0, self.text)
        return "  ".join(parts)


def _next(cycle: tuple[str, ...], current: str) -> str:
    if current not in cycle:
        return cycle[0]
    return cycle[(cycle.index(current) + 1) % len(cycle)]


def cycle_status(query: Query) -> Query:
    return query.with_status(_next(STATUS_CYCLE, query.status))


def cycle_source(query: Query) -> Query:
    return query.with_source(_next(SOURCE_CYCLE, query.source))


def cycle_sort(query: Query) -> Query:
    return query.with_sort(_next(SORT_CYCLE, query.sort))


def parse_search(raw: str, *, defaults: Query | None = None) -> Query:
    query = defaults or Query()
    text_parts: list[str] = []
    for token in raw.split():
        if ":" not in token:
            text_parts.append(token)
            continue
        prefix, value = token.split(":", 1)
        field = PREFIXES.get(prefix.lower())
        if not field or not value:
            text_parts.append(token)
            continue
        value = value.lower()
        if field == "status":
            query = replace(query, status=value)
        elif field == "source":
            query = replace(query, source=value)
        elif field == "hue":
            query = replace(query, hue=value)
        elif field == "category":
            query = replace(query, category=value)
        elif field == "tag":
            query = replace(query, tag=value)
        elif field == "kind":
            query = replace(query, kind=value)
        elif field == "verified":
            query = replace(query, verified=value)
        elif field == "sort":
            query = replace(query, sort=value)
    return replace(query, text=" ".join(text_parts))


def _source_of(item: Item) -> str:
    if item.first_party or item.builtin or item.source_type == "builtin":
        return "builtin"
    return "community"


def _verified(item: Item) -> bool:
    return item.verification.lower() in {"verified", "passed"}


def matches_filters(item: Item, query: Query) -> bool:
    if query.kind not in {"", "all"} and item.kind != query.kind:
        return False
    if query.status == "installed" and not item.installed:
        return False
    if query.status == "available" and (item.installed or not item.can_install):
        return False
    if query.status == "extra" and not item.extra:
        return False
    if query.status == "stock" and not (item.builtin and not item.extra):
        return False
    if query.status == "current" and not item.current:
        return False
    if query.source not in {"", "all"} and _source_of(item) != query.source:
        return False
    if query.hue not in {"", "all"} and query.hue not in item.hue.lower():
        return False
    if query.category not in {"", "all"} and query.category not in item.category.lower():
        return False
    if query.tag not in {"", "all"} and query.tag not in " ".join(item.tags).lower():
        return False
    if query.verified == "yes" and not _verified(item):
        return False
    if query.verified in {"no", "unverified"} and _verified(item):
        return False
    if query.text and not item.matches(query.text):
        return False
    return True


def for_tab(items: list[Item], tab: Tab) -> list[Item]:
    if tab == "themes":
        return [item for item in items if item.kind == "theme"]
    if tab == "plugins":
        return [item for item in items if item.kind == "plugin"]
    return [item for item in items if item.installed or item.current]


def _stamp(value: str) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def sort_key(item: Item, sort: str) -> tuple:
    community = not item.first_party and item.source_type != "builtin"
    base = (
        0 if item.current else 1,
        0 if item.installed and community else 1,
        0 if community else 1,
    )
    if sort == "name":
        return (*base, item.name.lower())
    if sort == "recent":
        return (*base, -_stamp(item.listed_at), item.name.lower())
    stars = item.stars if item.stars is not None else -1
    return (*base, -stars, item.name.lower())


def apply_query(items: list[Item], query: Query, tab: Tab) -> list[Item]:
    scoped = for_tab(items, tab)
    matched = [item for item in scoped if matches_filters(item, query)]
    return sorted(matched, key=lambda item: sort_key(item, query.sort))
