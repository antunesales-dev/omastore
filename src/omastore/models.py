from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal

Kind = Literal["theme", "plugin"]
Tab = Literal["themes", "plugins", "installed", "packs"]


def slugify(value: str) -> str:
    text = value.strip().lower().replace("_", "-")
    text = re.sub(r"[\s/]+", "-", text)
    text = re.sub(r"[^a-z0-9.-]+", "", text)
    text = re.sub(r"-{2,}", "-", text)
    return text.strip("-.")


def parse_json_field(value: Any) -> Any:
    if value is None or value == "":
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def theme_install_url(github_url: str | None) -> str | None:
    if not github_url:
        return None
    if "/tree/" in github_url:
        return None
    return github_url.rstrip("/")


def normalize_repo(url: str | None) -> str:
    if not url:
        return ""
    return url.rstrip("/").removesuffix(".git")


@dataclass
class Item:
    kind: Kind
    id: str
    name: str
    author: str = ""
    description: str = ""
    repo: str = ""
    install_url: str | None = None
    stars: int | None = None
    version: str = ""
    category: str = ""
    tags: list[str] = field(default_factory=list)
    colors: dict[str, str] = field(default_factory=dict)
    hue: str = ""
    readme: str = ""
    preview_url: str = ""
    install_note: str = ""
    install_available: bool = True
    verification: str = ""
    license: str = ""
    warnings: list[str] = field(default_factory=list)
    builtin: bool = False
    curated: bool = False
    source_type: str = ""
    listed_at: str = ""
    # local overlay
    installed: bool = False
    enabled: bool = False
    current: bool = False
    extra: bool = False
    first_party: bool = False
    local_only: bool = False
    installed_rev: str = ""
    latest_rev: str = ""
    outdated: bool = False
    kinds: list[str] = field(default_factory=list)
    extra_details: bool = False

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.id}"

    @property
    def is_outdated(self) -> bool:
        return bool(self.outdated)

    @property
    def status_label(self) -> str:
        parts: list[str] = []
        if self.current:
            parts.append("current")
        elif self.installed and self.kind == "theme":
            parts.append("installed")
        if self.kind == "plugin":
            if self.first_party:
                parts.append("built-in")
            if self.installed:
                parts.append("on" if self.enabled else "off")
        elif self.builtin and not self.extra:
            parts.append("stock")
        elif self.extra:
            parts.append("extra")
        return " · ".join(parts)

    @property
    def verification_label(self) -> str:
        status = (self.verification or "").strip().lower()
        if status in {"verified", "passed"}:
            return "verified"
        if self.kind != "plugin" or self.first_party or self.builtin:
            return ""
        if status in {"", "unverified", "failed", "needs-fixes", "review-required"}:
            return "unverified"
        return status

    @property
    def can_install(self) -> bool:
        if self.installed or self.builtin or self.first_party:
            return False
        return bool(self.install_url) and self.install_available

    @property
    def can_apply(self) -> bool:
        return self.kind == "theme" and self.installed and not self.current

    @property
    def can_enable(self) -> bool:
        return self.kind == "plugin" and self.installed and not self.enabled

    @property
    def can_disable(self) -> bool:
        return self.kind == "plugin" and self.installed and self.enabled

    @property
    def can_update(self) -> bool:
        if self.first_party or self.builtin or self.local_only:
            return False
        if self.kind == "plugin":
            return self.installed and bool(self.repo)
        return self.extra and bool(self.install_url)

    @property
    def can_remove(self) -> bool:
        if self.first_party or self.builtin or self.current:
            return False
        if self.kind == "theme":
            return self.extra
        return self.installed and not self.first_party

    def matches(self, query: str) -> bool:
        if not query:
            return True
        hay = " ".join(
            [
                self.name,
                self.id,
                self.author,
                self.description,
                self.category,
                self.hue,
                " ".join(self.tags),
                self.repo,
            ]
        ).lower()
        return all(token in hay for token in query.lower().split())


def parse_theme(raw: dict[str, Any]) -> Item:
    colors = parse_json_field(raw.get("colors_json")) or {}
    if not isinstance(colors, dict):
        colors = {}
    warnings = parse_json_field(raw.get("security_warnings")) or []
    if isinstance(warnings, str):
        warnings = [warnings]
    github_url = raw.get("github_url") or ""
    slug = slugify(str(raw.get("slug") or raw.get("id") or raw.get("name") or ""))
    builtin = bool(raw.get("is_builtin"))
    return Item(
        kind="theme",
        id=slug,
        name=str(raw.get("name") or slug),
        author=str(raw.get("github_owner") or ""),
        description=str(raw.get("description") or "").strip(),
        repo=normalize_repo(github_url),
        install_url=None if builtin else theme_install_url(github_url),
        stars=raw.get("stars") if isinstance(raw.get("stars"), int) else None,
        colors={str(k): str(v) for k, v in colors.items() if isinstance(v, str)},
        hue=str(raw.get("primary_hue") or ""),
        readme=str(raw.get("readme_text") or "").strip(),
        preview_url=str(raw.get("preview_url") or ""),
        warnings=[str(w) for w in warnings],
        builtin=builtin,
        curated=bool(raw.get("is_curated")),
        source_type="builtin" if builtin else "community",
        listed_at=str(raw.get("updated_at") or raw.get("last_scraped_at") or ""),
        install_available=not builtin and theme_install_url(github_url) is not None,
    )


def parse_plugin(raw: dict[str, Any]) -> Item:
    tags = raw.get("tags") or []
    if not isinstance(tags, list):
        tags = []
    source = str(raw.get("sourceType") or "community")
    builtin = source == "builtin"
    repo = normalize_repo(raw.get("repo"))
    install_available = bool(raw.get("installAvailable", not builtin))
    preview = raw.get("previewImage") or raw.get("previewThumbnail") or ""
    preview_url = ""
    if preview:
        if str(preview).startswith("http"):
            preview_url = str(preview)
        else:
            preview_url = "https://omarchyplugins.com/" + str(preview).lstrip("/")
    return Item(
        kind="plugin",
        id=str(raw.get("id") or ""),
        name=str(raw.get("name") or raw.get("id") or ""),
        author=str(raw.get("author") or ""),
        description=str(raw.get("description") or "").strip(),
        repo=repo,
        install_url=None if builtin or not install_available else (repo or None),
        stars=raw.get("stars") if isinstance(raw.get("stars"), int) else None,
        version=str(raw.get("version") or ""),
        category=str(raw.get("category") or ""),
        tags=[str(t) for t in tags],
        preview_url=preview_url,
        install_note=str(raw.get("installNote") or ""),
        install_available=install_available and not builtin,
        verification=str(raw.get("verificationStatus") or ""),
        license=str(raw.get("license") or ""),
        builtin=builtin,
        first_party=builtin,
        source_type=source,
        listed_at=str(raw.get("listedAt") or raw.get("addedAt") or ""),
    )
