from pathlib import Path

from omastore import __version__
from omastore.credits import ABOUT, OMASTORE_REPO, PLUGIN_STORE_AUTHOR, THEME_STORE_AUTHOR, changelog_text


def test_about_names_catalog_authors() -> None:
    assert THEME_STORE_AUTHOR in ABOUT
    assert PLUGIN_STORE_AUTHOR in ABOUT
    assert "omarchytheme.com" in ABOUT
    assert "omarchyplugins.com" in ABOUT
    assert "does not host" in ABOUT or "not a competing store" in ABOUT.lower()
    assert "not a competing store" in ABOUT.lower()
    assert OMASTORE_REPO in ABOUT
    assert "HANCORE" in ABOUT
    assert "suggested" in ABOUT.lower() or "packs" in ABOUT.lower()
    assert __version__ in ABOUT


def test_changelog_lists_releases() -> None:
    text = changelog_text()
    assert f"## {__version__}" in text or f"## {__version__} " in text or f"## {__version__} —" in text
    assert "0.2.5" in text
    assert "0.2.0" in text
    assert "pre-install" in text.lower() or "scan" in text.lower()
    root = Path(__file__).resolve().parents[1] / "CHANGELOG.md"
    packaged = Path(__file__).resolve().parents[1] / "src" / "omastore" / "CHANGELOG.md"
    assert root.is_file()
    assert packaged.is_file()
    assert root.read_text(encoding="utf-8") == packaged.read_text(encoding="utf-8")
    assert changelog_text() == root.read_text(encoding="utf-8")
