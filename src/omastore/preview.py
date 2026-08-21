from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from omastore.safety import safe_cli_arg

Runner = Callable[..., Any]

_OMARCHY_MISSING = "omarchy CLI not found on PATH"
_NO_SESSION = "no preview session to revert"


def _default_state_path() -> Path:
    root = os.environ.get("XDG_STATE_HOME")
    if root:
        return Path(root) / "omastore" / "preview.json"
    return Path.home() / ".local" / "state" / "omastore" / "preview.json"


STATE_PATH = _default_state_path()


def _state_file() -> Path:
    return Path(STATE_PATH)


_THEME_SET_TIMEOUT = 120


def _invoke(runner: Runner | None, *cli: str) -> subprocess.CompletedProcess[str] | None:
    command = ["omarchy", *cli]
    invoke = subprocess.run if runner is None else runner
    kwargs: dict[str, Any] = {
        "check": False,
        "text": True,
        "capture_output": True,
        "stdin": subprocess.DEVNULL,
    }
    if runner is None:
        kwargs["start_new_session"] = True
        if len(cli) >= 2 and cli[0] == "theme" and cli[1] == "set":
            kwargs["timeout"] = _THEME_SET_TIMEOUT
    try:
        return invoke(command, **kwargs)
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(command, 1, "", "omarchy theme set timed out")


def _load_session() -> dict[str, Any] | None:
    path = _state_file()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or "previous" not in data:
        return None
    return data


def _save_session(previous: str) -> None:
    path = _state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "previous": previous,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _clear_session() -> None:
    try:
        _state_file().unlink(missing_ok=True)
    except OSError:
        pass


def _result(*, ok: bool, previous: str, current: str, message: str) -> dict[str, bool | str]:
    return {"ok": ok, "previous": previous, "current": current, "message": message}


def current_theme_name(*, runner: Runner | None = None) -> str:
    """Run `omarchy theme current`, return stripped name or ''."""
    completed = _invoke(runner, "theme", "current")
    if completed is None or completed.returncode != 0:
        return ""
    return (completed.stdout or "").strip()


def remember_and_apply(theme_name: str, *, runner: Runner | None = None) -> dict:
    """If no preview session is active, save current theme as previous.

    Then `omarchy theme set <theme_name>`.
    Return {ok, previous, current, message}.
    If a session is already active, do NOT overwrite previous — just set the new theme.
    """
    name = safe_cli_arg(theme_name)
    if not name:
        return _result(ok=False, previous="", current="", message="refused theme name")

    session = _load_session()
    if session is None:
        completed = _invoke(runner, "theme", "current")
        if completed is None:
            return _result(ok=False, previous="", current="", message=_OMARCHY_MISSING)
        if completed.returncode != 0:
            message = (completed.stderr or completed.stdout or "could not read current theme").strip()
            return _result(ok=False, previous="", current="", message=message)
        previous = (completed.stdout or "").strip()
        if not safe_cli_arg(previous):
            return _result(ok=False, previous="", current="", message="could not read current theme")
        _save_session(previous)
    else:
        previous = str(session.get("previous") or "")
        if not safe_cli_arg(previous):
            return _result(ok=False, previous=previous, current="", message="could not read current theme")

    completed = _invoke(runner, "theme", "set", name)
    if completed is None:
        return _result(ok=False, previous=previous, current=current_theme_name(runner=runner), message=_OMARCHY_MISSING)
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "failed to apply theme").strip()
        return _result(ok=False, previous=previous, current=current_theme_name(runner=runner), message=message)
    return _result(ok=True, previous=previous, current=name, message=f"previewing {name}")


def revert(*, runner: Runner | None = None) -> dict:
    """Restore previous theme from state and clear the session.

    If no session, return ok=False and a clear message.
    """
    session = _load_session()
    if session is None:
        return _result(
            ok=False,
            previous="",
            current=current_theme_name(runner=runner),
            message=_NO_SESSION,
        )
    previous = str(session.get("previous") or "")
    previous_safe = safe_cli_arg(previous)
    if not previous_safe:
        return _result(
            ok=False,
            previous=previous,
            current=current_theme_name(runner=runner),
            message="could not read current theme",
        )
    completed = _invoke(runner, "theme", "set", previous_safe)
    if completed is None:
        return _result(ok=False, previous=previous, current=current_theme_name(runner=runner), message=_OMARCHY_MISSING)
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "failed to restore theme").strip()
        return _result(ok=False, previous=previous, current=current_theme_name(runner=runner), message=message)
    _clear_session()
    return _result(ok=True, previous=previous, current=previous, message=f"restored {previous}")


def preview_status(*, runner: Runner | None = None) -> dict:
    """{active: bool, previous: str, current: str}"""
    session = _load_session()
    current = current_theme_name(runner=runner)
    if session is None:
        return {"active": False, "previous": "", "current": current}
    return {
        "active": True,
        "previous": str(session.get("previous") or ""),
        "current": current,
    }
