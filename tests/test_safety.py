from pathlib import Path

from omastore.models import Item
from omastore.safety import (
    allowed_fetch_url,
    allowed_install_url,
    contained_child,
    is_http_url,
    safe_cli_arg,
    theme_aliases,
)


def test_safe_cli_arg_rejects_flags_and_blank() -> None:
    assert safe_cli_arg("lumon") == "lumon"
    assert safe_cli_arg("  Tokyo Night ") == "Tokyo Night"
    assert safe_cli_arg("-evil") == ""
    assert safe_cli_arg("--help") == ""
    assert safe_cli_arg("") == ""
    assert safe_cli_arg("a\nb") == ""
    assert safe_cli_arg(None) == ""


def test_is_http_url() -> None:
    assert is_http_url("https://github.com/a/b")
    assert not is_http_url("javascript:alert(1)")
    assert not is_http_url("file:///etc/passwd")


def test_allowed_install_url_github_https_only() -> None:
    assert allowed_install_url("https://github.com/OldJobobo/omarchy-lumon-theme")
    assert not allowed_install_url("https://github.com/basecamp/omarchy/tree/quattro/themes/x")
    assert not allowed_install_url("http://github.com/a/b")
    assert not allowed_install_url("https://evil.example/a/b")
    assert not allowed_install_url("https://github.com/onlyone")
    assert allowed_fetch_url("https://codeload.github.com/a/demo/tar.gz/refs/heads/main")
    assert not allowed_install_url("https://codeload.github.com/a/demo/tar.gz/refs/heads/main")


def test_contained_child_stays_under_root(tmp_path: Path) -> None:
    root = tmp_path / "themes"
    root.mkdir()
    (root / "lumon").mkdir()
    assert contained_child(root, "lumon") == (root / "lumon").resolve()
    assert contained_child(root, "../etc") is None
    assert contained_child(root, "/etc") is None
    assert contained_child(root, "..") is None
    assert contained_child(root, "-flag") is None
    assert contained_child(root, "") is None


def test_theme_aliases_include_repo_basename() -> None:
    item = Item(
        kind="theme",
        id="lumon",
        name="Lumon",
        repo="https://github.com/OldJobobo/omarchy-lumon-theme.git",
    )
    aliases = theme_aliases(item)
    assert "lumon" in aliases
    assert "omarchy-lumon-theme" in aliases
