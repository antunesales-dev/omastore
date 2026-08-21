import json
from datetime import datetime
from pathlib import Path
import subprocess
from subprocess import CompletedProcess

import omastore.preview as preview


def _patch_state(monkeypatch, tmp_path: Path) -> Path:
    path = tmp_path / "preview.json"
    monkeypatch.setattr(preview, "STATE_PATH", path)
    return path


class FakeOmarchy:
    def __init__(self, current: str = "Vantablack") -> None:
        self.current = current
        self.calls: list[list[str]] = []
        self.fail_set: str | None = None
        self.missing = False

    def __call__(self, cmd, **kwargs):
        if self.missing:
            raise FileNotFoundError("omarchy")
        argv = list(cmd)
        self.calls.append(argv)
        if argv[:3] == ["omarchy", "theme", "current"]:
            return CompletedProcess(argv, 0, stdout=f"{self.current}\n", stderr="")
        if argv[:3] == ["omarchy", "theme", "set"]:
            if self.fail_set is not None:
                return CompletedProcess(argv, 1, stdout="", stderr=self.fail_set)
            self.current = argv[3]
            return CompletedProcess(argv, 0, stdout="", stderr="")
        return CompletedProcess(argv, 1, stdout="", stderr="unexpected command")


def test_state_path_default_is_xdg() -> None:
    path = Path(preview.STATE_PATH)
    assert path.name == "preview.json"
    assert path.parent.name == "omastore"
    assert str(path).endswith("omastore/preview.json")


def test_default_state_path_uses_xdg_state_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    assert preview._default_state_path() == tmp_path / "omastore" / "preview.json"


def test_default_state_path_falls_back_to_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.setattr(preview.Path, "home", staticmethod(lambda: tmp_path))
    assert preview._default_state_path() == tmp_path / ".local" / "state" / "omastore" / "preview.json"


def test_current_theme_name_strips_output() -> None:
    runner = FakeOmarchy("  Lumon  ")
    assert preview.current_theme_name(runner=runner) == "Lumon"


def test_theme_set_timeout_is_an_error(monkeypatch, tmp_path: Path) -> None:
    _patch_state(monkeypatch, tmp_path)

    def boom(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout") or 120)

    monkeypatch.setattr(preview.subprocess, "run", boom)
    result = preview.remember_and_apply("Tokyo Night")
    assert result["ok"] is False
    assert "timed out" in result["message"]


def test_current_theme_name_empty_when_omarchy_missing() -> None:
    runner = FakeOmarchy()
    runner.missing = True
    assert preview.current_theme_name(runner=runner) == ""


def test_remember_and_apply_saves_previous_then_sets(monkeypatch, tmp_path: Path) -> None:
    state = _patch_state(monkeypatch, tmp_path)
    runner = FakeOmarchy("Vantablack")
    result = preview.remember_and_apply("Tokyo Night", runner=runner)
    assert result == {
        "ok": True,
        "previous": "Vantablack",
        "current": "Tokyo Night",
        "message": "previewing Tokyo Night",
    }
    assert runner.current == "Tokyo Night"
    assert ["omarchy", "theme", "set", "Tokyo Night"] in runner.calls
    data = json.loads(state.read_text(encoding="utf-8"))
    assert data["previous"] == "Vantablack"
    datetime.fromisoformat(data["started_at"])


def test_second_preview_does_not_overwrite_previous(monkeypatch, tmp_path: Path) -> None:
    state = _patch_state(monkeypatch, tmp_path)
    runner = FakeOmarchy("Vantablack")
    first = preview.remember_and_apply("Tokyo Night", runner=runner)
    started = json.loads(state.read_text(encoding="utf-8"))["started_at"]
    second = preview.remember_and_apply("Catppuccin", runner=runner)
    assert first["previous"] == "Vantablack"
    assert second["ok"] is True
    assert second["previous"] == "Vantablack"
    assert second["current"] == "Catppuccin"
    data = json.loads(state.read_text(encoding="utf-8"))
    assert data["previous"] == "Vantablack"
    assert data["started_at"] == started
    assert runner.current == "Catppuccin"


def test_remember_and_apply_missing_omarchy(monkeypatch, tmp_path: Path) -> None:
    state = _patch_state(monkeypatch, tmp_path)
    runner = FakeOmarchy()
    runner.missing = True
    result = preview.remember_and_apply("Tokyo Night", runner=runner)
    assert result["ok"] is False
    assert result["previous"] == ""
    assert result["current"] == ""
    assert "omarchy" in result["message"].lower()
    assert not state.exists()


def test_failed_set_keeps_session(monkeypatch, tmp_path: Path) -> None:
    state = _patch_state(monkeypatch, tmp_path)
    runner = FakeOmarchy("Vantablack")
    runner.fail_set = "theme not found"
    result = preview.remember_and_apply("Nope", runner=runner)
    assert result["ok"] is False
    assert result["previous"] == "Vantablack"
    assert result["current"] == "Vantablack"
    assert "theme not found" in result["message"]
    assert json.loads(state.read_text(encoding="utf-8"))["previous"] == "Vantablack"


def test_remember_and_apply_refuses_empty_current(monkeypatch, tmp_path: Path) -> None:
    state = _patch_state(monkeypatch, tmp_path)
    runner = FakeOmarchy("")
    result = preview.remember_and_apply("Tokyo Night", runner=runner)
    assert result["ok"] is False
    assert "could not read current theme" in result["message"]
    assert not state.exists()
    assert not any(argv[:3] == ["omarchy", "theme", "set"] for argv in runner.calls)


def test_revert_refuses_empty_previous(monkeypatch, tmp_path: Path) -> None:
    state = _patch_state(monkeypatch, tmp_path)
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps({"previous": ""}), encoding="utf-8")
    runner = FakeOmarchy("Tokyo Night")
    result = preview.revert(runner=runner)
    assert result["ok"] is False
    assert not any(argv[:3] == ["omarchy", "theme", "set"] for argv in runner.calls)
    assert state.exists()


def test_revert_restores_previous_and_clears_session(monkeypatch, tmp_path: Path) -> None:
    state = _patch_state(monkeypatch, tmp_path)
    runner = FakeOmarchy("Vantablack")
    preview.remember_and_apply("Tokyo Night", runner=runner)
    result = preview.revert(runner=runner)
    assert result["ok"] is True
    assert result["previous"] == "Vantablack"
    assert result["current"] == "Vantablack"
    assert "restored" in result["message"].lower()
    assert runner.current == "Vantablack"
    assert ["omarchy", "theme", "set", "Vantablack"] in runner.calls
    assert not state.exists()


def test_revert_without_session(monkeypatch, tmp_path: Path) -> None:
    _patch_state(monkeypatch, tmp_path)
    runner = FakeOmarchy("Vantablack")
    result = preview.revert(runner=runner)
    assert result["ok"] is False
    assert "session" in result["message"].lower()
    assert runner.calls == [["omarchy", "theme", "current"]]


def test_revert_keeps_session_when_set_fails(monkeypatch, tmp_path: Path) -> None:
    state = _patch_state(monkeypatch, tmp_path)
    runner = FakeOmarchy("Vantablack")
    preview.remember_and_apply("Tokyo Night", runner=runner)
    runner.fail_set = "could not restore"
    result = preview.revert(runner=runner)
    assert result["ok"] is False
    assert result["previous"] == "Vantablack"
    assert "could not restore" in result["message"]
    assert state.exists()


def test_preview_status_inactive_without_session(monkeypatch, tmp_path: Path) -> None:
    _patch_state(monkeypatch, tmp_path)
    runner = FakeOmarchy("Vantablack")
    assert preview.preview_status(runner=runner) == {
        "active": False,
        "previous": "",
        "current": "Vantablack",
    }


def test_preview_status_active_during_preview(monkeypatch, tmp_path: Path) -> None:
    _patch_state(monkeypatch, tmp_path)
    runner = FakeOmarchy("Vantablack")
    preview.remember_and_apply("Tokyo Night", runner=runner)
    assert preview.preview_status(runner=runner) == {
        "active": True,
        "previous": "Vantablack",
        "current": "Tokyo Night",
    }


def test_corrupt_state_is_treated_as_inactive(monkeypatch, tmp_path: Path) -> None:
    state = _patch_state(monkeypatch, tmp_path)
    state.write_text("{not-json", encoding="utf-8")
    runner = FakeOmarchy("Vantablack")
    assert preview.preview_status(runner=runner)["active"] is False
    result = preview.remember_and_apply("Tokyo Night", runner=runner)
    assert result["ok"] is True
    assert result["previous"] == "Vantablack"
