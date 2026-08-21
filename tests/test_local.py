import subprocess
from pathlib import Path

import pytest

from omastore.local import (
    _dir_slugs,
    _existing_child,
    installed_plugin_path,
    run_omarchy,
)


def test_dir_slugs_includes_lowercase_and_slugify(tmp_path: Path) -> None:
    (tmp_path / "Tokyo Night").mkdir()
    (tmp_path / "notes.txt").write_text("skip", encoding="utf-8")
    slugs = _dir_slugs(tmp_path)
    assert "tokyo night" in slugs
    assert "tokyo-night" in slugs
    assert "notes.txt" not in slugs


def test_dir_slugs_skips_unsafe_names(tmp_path: Path) -> None:
    (tmp_path / "safe").mkdir()
    (tmp_path / "-flag").mkdir()
    slugs = _dir_slugs(tmp_path)
    assert "safe" in slugs
    assert "-flag" not in slugs


def test_existing_child_rejects_path_escape(tmp_path: Path, monkeypatch) -> None:
    from omastore import local

    monkeypatch.setattr(local, "_home", lambda: tmp_path)
    plugins = tmp_path / ".config" / "omarchy" / "plugins"
    plugins.mkdir(parents=True)
    (tmp_path / ".config" / "omarchy" / "etc").mkdir()
    (plugins / "safe").mkdir()

    assert _existing_child(plugins, "../etc") is None
    assert _existing_child(plugins, "/etc") is None
    assert _existing_child(plugins, "..") is None
    assert installed_plugin_path("../etc") is None
    assert installed_plugin_path("/etc") is None
    found = installed_plugin_path("safe")
    assert found is not None
    assert found.resolve() == (plugins / "safe").resolve()


def test_run_omarchy_timeout_returns_failed_process(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["omarchy"], timeout=kwargs.get("timeout", 30))

    monkeypatch.setattr(subprocess, "run", boom)
    completed = run_omarchy("theme", "list")
    assert completed.args == ["omarchy", "theme", "list"]
    assert completed.returncode == 1
    assert completed.stdout == ""
    assert completed.stderr == "omarchy timed out"


def test_run_omarchy_missing_binary_reraises(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise FileNotFoundError("omarchy")

    monkeypatch.setattr(subprocess, "run", boom)
    with pytest.raises(FileNotFoundError):
        run_omarchy("theme", "current")
