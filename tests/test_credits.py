from omastore.credits import ABOUT, PLUGIN_STORE_AUTHOR, THEME_STORE_AUTHOR


def test_about_names_catalog_authors() -> None:
    assert THEME_STORE_AUTHOR in ABOUT
    assert PLUGIN_STORE_AUTHOR in ABOUT
    assert "omarchytheme.com" in ABOUT
    assert "omarchyplugins.com" in ABOUT
    assert "does not host" in ABOUT
