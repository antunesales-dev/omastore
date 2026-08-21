import json
import urllib.error

from omastore.enrich import apply_manifest, enrich_item, github_raw_candidates
from omastore.models import Item


def _item(**kwargs) -> Item:
    data = {
        "kind": "plugin",
        "id": "omarchy-overview",
        "name": "omarchy-overview",
        "repo": "https://github.com/AyushKr2003/omarchy-overview",
        "description": "",
        "version": "",
        "license": "",
        "author": "",
    }
    data.update(kwargs)
    return Item(**data)


def test_github_raw_candidates_main_then_master() -> None:
    urls = github_raw_candidates(
        "https://github.com/AyushKr2003/omarchy-overview.git/",
        "manifest.json",
    )
    assert urls == [
        "https://raw.githubusercontent.com/AyushKr2003/omarchy-overview/main/manifest.json",
        "https://raw.githubusercontent.com/AyushKr2003/omarchy-overview/master/manifest.json",
    ]
    assert github_raw_candidates("https://gitlab.com/group/repo", "manifest.json") == []
    assert github_raw_candidates("", "manifest.json") == []
    assert github_raw_candidates("https://example.com/not-github", "manifest.json") == []
    assert (
        github_raw_candidates(
            "https://github.com/basecamp/omarchy/tree/quattro/themes/catppuccin",
            "manifest.json",
        )
        == []
    )


def test_apply_manifest_fills_empty_fields_only() -> None:
    item = _item(license="See repository", category="", tags=[])
    apply_manifest(
        item,
        {
            "name": "Overview",
            "description": "Workspace overview",
            "version": "1.0.0",
            "license": "MIT",
            "author": "AyushKr2003",
            "category": "Appearance",
            "kinds": ["overlay"],
            "tags": ["hyprland"],
        },
    )
    assert item.name == "Overview"
    assert item.description == "Workspace overview"
    assert item.version == "1.0.0"
    assert item.license == "MIT"
    assert item.author == "AyushKr2003"
    assert item.category == "Appearance"
    assert item.tags == ["hyprland"]
    assert item.kinds == ["overlay"]
    assert item.extra_details is True


def test_apply_manifest_does_not_overwrite_catalog_values() -> None:
    item = _item(
        name="Overview",
        description="Catalog desc",
        version="0.1.0",
        license="Apache-2.0",
        author="Catalog Author",
        category="Desktop",
        tags=["bar"],
        kinds=["service"],
    )
    apply_manifest(
        item,
        {
            "name": "Other",
            "description": "Repo desc",
            "version": "9.9.9",
            "license": "MIT",
            "author": "Repo Author",
            "category": "Widgets",
            "kinds": ["overlay"],
            "tags": ["hyprland"],
        },
    )
    assert item.name == "Overview"
    assert item.description == "Catalog desc"
    assert item.version == "0.1.0"
    assert item.license == "Apache-2.0"
    assert item.author == "Catalog Author"
    assert item.category == "Desktop"
    assert item.tags == ["bar"]
    assert item.kinds == ["service"]
    assert item.extra_details is False


def test_apply_manifest_name_only_when_name_is_id() -> None:
    named = _item(name="Overview")
    apply_manifest(named, {"name": "Something Else"})
    assert named.name == "Overview"
    assert named.extra_details is False

    placeholder = _item(name="omarchy-overview")
    apply_manifest(placeholder, {"name": "Overview"})
    assert placeholder.name == "Overview"
    assert placeholder.extra_details is True


def test_apply_manifest_tags_from_kinds_when_tags_missing() -> None:
    item = _item()
    apply_manifest(item, {"kinds": ["bar-widget"]})
    assert item.tags == ["bar-widget"]
    assert item.kinds == ["bar-widget"]
    assert item.extra_details is True


def test_enrich_item_uses_fetch_and_skips_complete_listings() -> None:
    seen: list[str] = []

    def fetch(url: str) -> str:
        seen.append(url)
        return json.dumps(
            {
                "name": "Overview",
                "description": "from repo",
                "version": "1.2.3",
                "license": "MIT",
                "author": "Ayush",
            }
        )

    thin = _item(license="See repository")
    enrich_item(thin, fetch=fetch)
    assert thin.license == "MIT"
    assert thin.version == "1.2.3"
    assert thin.author == "Ayush"
    assert thin.name == "Overview"
    assert thin.extra_details is True
    assert seen[0].endswith("/main/manifest.json")

    seen.clear()
    full = _item(
        name="Overview",
        description="Hyprland workspace overview with live window previews.",
        version="1.0.0",
        license="MIT",
        author="AyushKr2003",
    )
    enrich_item(full, fetch=fetch)
    assert seen == []
    assert full.extra_details is False
    assert full.description == "Hyprland workspace overview with live window previews."


def test_enrich_item_tries_master_after_main_404() -> None:
    def fetch(url: str) -> str:
        if "/main/" in url:
            raise urllib.error.HTTPError(url, 404, "Not Found", hdrs=None, fp=None)
        return json.dumps({"version": "2.0.0", "license": "MIT"})

    item = _item()
    enrich_item(item, fetch=fetch)
    assert item.version == "2.0.0"
    assert item.license == "MIT"
    assert item.extra_details is True


def test_enrich_item_skips_builtin_and_first_party() -> None:
    def boom(_url: str) -> str:
        raise AssertionError("must not fetch")

    enrich_item(_item(builtin=True, description="", version=""), fetch=boom)
    enrich_item(_item(first_party=True, description="", version=""), fetch=boom)


def test_enrich_item_ignores_404_and_never_raises() -> None:
    def missing(url: str) -> str:
        raise urllib.error.HTTPError(url, 404, "Not Found", hdrs=None, fp=None)

    item = _item()
    enrich_item(item, fetch=missing)
    assert item.extra_details is False

    def explode(_url: str) -> str:
        raise RuntimeError("network down")

    enrich_item(item, fetch=explode)
    enrich_item(_item(repo="https://example.com/not-github"), fetch=explode)
    enrich_item(_item(repo=""), fetch=explode)
