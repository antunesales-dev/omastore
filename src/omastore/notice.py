from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

NOTICE = (
    "Community plugins and themes run unsandboxed inside omarchy-shell.\n"
    "Listings come from limehawk (omarchytheme.com) and HANCORE "
    "(omarchyplugins.com). omastore does not approve what they publish.\n"
    "Before install, omastore fetches a copy of the repo and scans it "
    "without running it. That is not a sandbox and not proof of safety.\n"
    "Read the repo before you install."
)


def _default_path() -> Path:
    root = os.environ.get("XDG_STATE_HOME")
    if root:
        return Path(root) / "omastore" / "notice.json"
    return Path.home() / ".local" / "state" / "omastore" / "notice.json"


STATE_PATH = _default_path()


def _path() -> Path:
    return Path(STATE_PATH)


def seen() -> bool:
    path = _path()
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(isinstance(data, dict) and data.get("unsandboxed"))


def mark_seen() -> None:
    try:
        path = _path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {"unsandboxed": True}
        path.write_text(json.dumps(payload), encoding="utf-8")
    except OSError:
        return
