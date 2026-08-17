from __future__ import annotations

import shutil
import subprocess
from importlib import resources
from pathlib import Path


def _share_file(name: str) -> Path:
    packaged = resources.files("omastore") / "share" / name
    if packaged.is_file():
        return Path(str(packaged))
    root = Path(__file__).resolve().parents[2]
    return root / "share" / name


def install_desktop() -> list[Path]:
    written: list[Path] = []
    apps = Path.home() / ".local/share/applications"
    icons = Path.home() / ".local/share/icons/hicolor/scalable/apps"
    apps.mkdir(parents=True, exist_ok=True)
    icons.mkdir(parents=True, exist_ok=True)

    desktop_src = Path(__file__).resolve().parents[2] / "share/applications/Omastore.desktop"
    icon_src = Path(__file__).resolve().parents[2] / "share/icons/omastore.svg"
    if not desktop_src.is_file():
        raise FileNotFoundError("Omastore.desktop is missing from the repo share/")
    if not icon_src.is_file():
        raise FileNotFoundError("omastore.svg is missing from the repo share/")

    desktop_dst = apps / "Omastore.desktop"
    icon_dst = icons / "omastore.svg"
    shutil.copy2(desktop_src, desktop_dst)
    desktop_dst.chmod(0o755)
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
