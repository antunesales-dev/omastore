from __future__ import annotations

import shutil
import subprocess
from importlib import resources
from pathlib import Path


def _share_file(relpath: str) -> Path:
    packaged = Path(__file__).resolve().parent / "share" / relpath
    if packaged.is_file():
        return packaged
    resource = resources.files("omastore") / "share" / relpath
    if resource.is_file():
        return Path(str(resource))
    return Path(__file__).resolve().parents[2] / "share" / relpath


def install_desktop() -> list[Path]:
    written: list[Path] = []
    apps = Path.home() / ".local/share/applications"
    icons = Path.home() / ".local/share/icons/hicolor/scalable/apps"
    apps.mkdir(parents=True, exist_ok=True)
    icons.mkdir(parents=True, exist_ok=True)

    desktop_src = _share_file("applications/Omastore.desktop")
    icon_src = _share_file("icons/omastore.svg")
    if not desktop_src.is_file():
        raise FileNotFoundError("Omastore.desktop is missing from share/")
    if not icon_src.is_file():
        raise FileNotFoundError("omastore.svg is missing from share/")

    desktop_dst = apps / "Omastore.desktop"
    icon_dst = icons / "omastore.svg"
    shutil.copy2(desktop_src, desktop_dst)
    desktop_dst.chmod(0o644)
    shutil.copy2(icon_src, icon_dst)
    written.extend([desktop_dst, icon_dst])

    subprocess.run(
        ["gtk-update-icon-cache", str(Path.home() / ".local/share/icons/hicolor")],
        check=False,
        capture_output=True,
    )
    subprocess.run(
        ["update-desktop-database", str(apps)],
        check=False,
        capture_output=True,
    )
    return written
