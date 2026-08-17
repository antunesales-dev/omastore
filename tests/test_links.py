from types import SimpleNamespace

from omastore.links import (
    PLUGIN_CATALOG,
    THEME_CATALOG,
    catalog_url,
    open_item,
    open_url,
    repo_url,
    urls_for,
)


def _item(**kwargs) -> SimpleNamespace:
    data = {
        "kind": "theme",
        "id": "lumon",
        "name": "Lumon",
        "repo": "https://github.com/OldJobobo/omarchy-lumon-theme",
        "install_url": "https://github.com/OldJobobo/omarchy-lumon-theme",
    }
    data.update(kwargs)
    return SimpleNamespace(**data)


def test_repo_url_prefers_repo_then_install_url() -> None:
    item = _item(repo="https://github.com/author/theme.git/", install_url="https://example.com/other")
    assert repo_url(item) == "https://github.com/author/theme"
    fallback = _item(repo="", install_url="https://github.com/author/plugin.git")
    assert repo_url(fallback) == "https://github.com/author/plugin"
    assert repo_url(_item(repo=None, install_url=None)) == ""
    assert repo_url(SimpleNamespace(kind="theme", id="x", name="X")) == ""


def test_catalog_url_is_marketplace_homepage() -> None:
    theme = _item(kind="theme", id="arc-blueberry", name="Arc Blueberry")
    plugin = _item(kind="plugin", id="omarchy-overview", name="Overview")
    assert catalog_url(theme) == THEME_CATALOG == "https://omarchytheme.com"
    assert catalog_url(plugin) == PLUGIN_CATALOG == "https://omarchyplugins.com"
    assert catalog_url(theme) == "https://omarchytheme.com"
    assert "/themes/" not in catalog_url(theme)
    assert theme.id not in catalog_url(theme)
    assert catalog_url(SimpleNamespace(kind="other", id="x", name="X")) == ""


def test_urls_for_returns_repo_catalog_and_label() -> None:
    item = _item()
    urls = urls_for(item)
    assert urls == {
        "repo": "https://github.com/OldJobobo/omarchy-lumon-theme",
        "catalog": THEME_CATALOG,
        "label": "Lumon",
    }
    unnamed = _item(name="", id="void", repo="")
    assert urls_for(unnamed)["label"] == "void"
    assert urls_for(unnamed)["repo"] == unnamed.install_url.rstrip("/")


def test_open_url_uses_opener_and_refuses_bad_urls() -> None:
    seen: list[str] = []
    result = open_url("https://github.com/author/repo/", opener=seen.append)
    assert result["ok"] is True
    assert result["url"] == "https://github.com/author/repo"
    assert seen == ["https://github.com/author/repo"]
    assert "opened" in result["message"]

    empty = open_url("  ", opener=seen.append)
    assert empty == {"ok": False, "url": "", "message": "no URL to open"}
    assert open_url("javascript:alert(1)", opener=seen.append)["ok"] is False
    assert open_url("file:///etc/passwd", opener=seen.append)["ok"] is False
    assert open_url("ftp://example.com/x", opener=seen.append)["ok"] is False
    assert seen == ["https://github.com/author/repo"]

    def boom(_url: str) -> None:
        raise RuntimeError("browser missing")

    failed = open_url("https://omarchytheme.com", opener=boom)
    assert failed["ok"] is False
    assert failed["url"] == "https://omarchytheme.com"
    assert failed["message"] == "browser missing"


def test_open_url_defaults_to_xdg_open(monkeypatch) -> None:
    calls: list[list[str]] = []

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(args, **_kwargs):
        calls.append(list(args))
        return Result()

    monkeypatch.setattr("omastore.links.subprocess.run", fake_run)
    result = open_url("https://omarchyplugins.com")
    assert result["ok"] is True
    assert calls == [["xdg-open", "https://omarchyplugins.com"]]


def test_open_item_repo_or_catalog() -> None:
    item = _item()
    seen: list[str] = []
    repo = open_item(item, opener=seen.append)
    catalog = open_item(item, "catalog", opener=seen.append)
    assert repo["ok"] is True
    assert repo["url"] == item.repo
    assert catalog["ok"] is True
    assert catalog["url"] == THEME_CATALOG
    assert seen == [item.repo, THEME_CATALOG]

    missing = open_item(_item(repo="", install_url=""), opener=seen.append)
    assert missing["ok"] is False
    assert missing["url"] == ""

    bad = open_item(item, "website", opener=seen.append)
    assert bad == {"ok": False, "url": "", "message": "target must be 'repo' or 'catalog'"}
    assert seen == [item.repo, THEME_CATALOG]
