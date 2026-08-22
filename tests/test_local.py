import json
import subprocess
from pathlib import Path

import pytest

from omastore.local import (
    _dir_slugs,
    _existing_child,
    hidden_bar_widgets,
    installed_plugin_path,
    layout_remove_warnings,
    restore_hidden_bar_widgets,
    run_omarchy,
)


def test_local_fingerprint_changes_with_mtime(tmp_path: Path, monkeypatch) -> None:
    from omastore import local as local_mod

    monkeypatch.setattr(local_mod, "_home", lambda: tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    theme = tmp_path / ".local/state/omarchy/current/theme"
    theme.parent.mkdir(parents=True)
    theme.symlink_to(tmp_path / "a")
    first = local_mod.local_fingerprint()
    theme.unlink()
    theme.symlink_to(tmp_path / "b")
    second = local_mod.local_fingerprint()
    assert first != second


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


def test_hidden_bar_widgets_read_only(tmp_path: Path) -> None:
    shell = tmp_path / "shell.json"
    payload = {
        "bar": {
            "layout": {
                "right": [
                    {
                        "id": "groups.plugin",
                        "hiddenEntries": [
                            {"id": "omarchy.clock"},
                            "omarchy.audio",
                            {"id": "omarchy.clock"},
                        ],
                    },
                    {"id": "omarchy.tray"},
                ]
            }
        }
    }
    shell.write_text(json.dumps(payload), encoding="utf-8")
    before = shell.read_text(encoding="utf-8")
    hidden = hidden_bar_widgets("groups.plugin", path=shell)
    assert hidden == ["omarchy.clock", "omarchy.audio"]
    assert hidden_bar_widgets("omarchy.tray", path=shell) == []
    assert hidden_bar_widgets("missing", path=shell) == []
    assert shell.read_text(encoding="utf-8") == before
    warn = layout_remove_warnings("groups.plugin", path=shell)
    assert len(warn) == 1
    assert "They will be put back on the bar first" in warn[0]
    assert "omarchy.clock" in warn[0]
    assert "omarchy.audio" in warn[0]


def test_hidden_bar_widgets_corrupt_or_missing(tmp_path: Path) -> None:
    missing = tmp_path / "nope.json"
    assert hidden_bar_widgets("x", path=missing) == []
    bad = tmp_path / "bad.json"
    bad.write_text("{nope", encoding="utf-8")
    assert hidden_bar_widgets("x", path=bad) == []
    assert layout_remove_warnings("x", path=bad) == []


def test_hidden_entries_by_plugin(tmp_path: Path) -> None:
    from omastore.local import hidden_entries_by_plugin

    shell = tmp_path / "shell.json"
    shell.write_text(
        json.dumps(
            {
                "bar": {
                    "layout": {
                        "right": [
                            {"id": "hider", "hiddenEntries": [{"id": "omarchy.clock"}, "omarchy.audio"]},
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    mapping = hidden_entries_by_plugin(path=shell)
    assert mapping == {"hider": ["omarchy.clock", "omarchy.audio"]}


def test_restore_hidden_bar_widgets_puts_them_back(tmp_path: Path) -> None:
    shell = tmp_path / "shell.json"
    payload = {
        "bar": {
            "layout": {
                "right": [
                    {"id": "keep.me"},
                    {
                        "id": "groups.plugin",
                        "hiddenEntries": [
                            {"id": "omarchy.clock"},
                            "omarchy.audio",
                            {"id": "keep.me"},
                            {"id": "groups.plugin"},
                        ],
                    },
                    {"id": "omarchy.tray"},
                ]
            }
        }
    }
    shell.write_text(json.dumps(payload), encoding="utf-8")
    restored = restore_hidden_bar_widgets("groups.plugin", path=shell)
    assert restored == ["omarchy.clock", "omarchy.audio"]
    data = json.loads(shell.read_text(encoding="utf-8"))
    right = data["bar"]["layout"]["right"]
    ids = [row["id"] for row in right]
    assert ids == ["keep.me", "groups.plugin", "omarchy.clock", "omarchy.audio", "omarchy.tray"]
    hider = next(row for row in right if row["id"] == "groups.plugin")
    assert "hiddenEntries" not in hider
    assert restore_hidden_bar_widgets("groups.plugin", path=shell) == []


def test_restore_hidden_bar_widgets_skips_corrupt(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{nope", encoding="utf-8")
    assert restore_hidden_bar_widgets("x", path=bad) == []
    assert bad.read_text(encoding="utf-8") == "{nope"
