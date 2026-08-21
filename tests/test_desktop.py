from pathlib import Path

from omastore import desktop


def _stub_home(monkeypatch, tmp_path: Path) -> Path:
    home = tmp_path / "home"
    monkeypatch.setattr(desktop.Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(desktop.subprocess, "run", lambda *args, **kwargs: None)
    return home


def test_install_desktop_chmod_644(tmp_path, monkeypatch) -> None:
    home = _stub_home(monkeypatch, tmp_path)
    src_dir = tmp_path / "fixtures"
    src_dir.mkdir()
    desktop_src = src_dir / "Omastore.desktop"
    icon_src = src_dir / "omastore.svg"
    desktop_src.write_text("[Desktop Entry]\nName=Omastore\n")
    icon_src.write_text("<svg xmlns='http://www.w3.org/2000/svg'/>")
    desktop_src.chmod(0o755)

    def fake_share(relpath: str) -> Path:
        if relpath == "applications/Omastore.desktop":
            return desktop_src
        if relpath == "icons/omastore.svg":
            return icon_src
        raise FileNotFoundError(relpath)

    monkeypatch.setattr(desktop, "_share_file", fake_share)

    written = desktop.install_desktop()
    dest = home / ".local/share/applications/Omastore.desktop"
    icon_dest = home / ".local/share/icons/hicolor/scalable/apps/omastore.svg"
    assert dest in written
    assert icon_dest in written
    assert dest.is_file()
    assert icon_dest.is_file()
    assert dest.stat().st_mode & 0o777 == 0o644


def test_install_desktop_from_repo_share(tmp_path, monkeypatch) -> None:
    home = _stub_home(monkeypatch, tmp_path)
    module_dir = tmp_path / "src" / "omastore"
    module_dir.mkdir(parents=True)
    monkeypatch.setattr(desktop, "__file__", str(module_dir / "desktop.py"))

    class Missing:
        def __truediv__(self, other):
            return self

        def is_file(self) -> bool:
            return False

    monkeypatch.setattr(desktop.resources, "files", lambda name: Missing())

    desktop_src = tmp_path / "share" / "applications" / "Omastore.desktop"
    icon_src = tmp_path / "share" / "icons" / "omastore.svg"
    desktop_src.parent.mkdir(parents=True)
    icon_src.parent.mkdir(parents=True)
    desktop_src.write_text("[Desktop Entry]\nName=Omastore\n")
    icon_src.write_text("<svg xmlns='http://www.w3.org/2000/svg'/>")

    written = desktop.install_desktop()
    dest = home / ".local/share/applications/Omastore.desktop"
    assert dest in written
    assert dest.read_text() == desktop_src.read_text()
    assert dest.stat().st_mode & 0o777 == 0o644


def test_share_file_prefers_packaged_beside_module(tmp_path, monkeypatch) -> None:
    module_dir = tmp_path / "omastore"
    packaged = module_dir / "share" / "applications" / "Omastore.desktop"
    packaged.parent.mkdir(parents=True)
    packaged.write_text("packaged")
    repo = tmp_path / "share" / "applications" / "Omastore.desktop"
    repo.parent.mkdir(parents=True)
    repo.write_text("repo")
    monkeypatch.setattr(desktop, "__file__", str(module_dir / "desktop.py"))

    found = desktop._share_file("applications/Omastore.desktop")
    assert found == packaged


def test_share_file_uses_importlib_when_not_beside_module(tmp_path, monkeypatch) -> None:
    module_dir = tmp_path / "omastore"
    module_dir.mkdir()
    monkeypatch.setattr(desktop, "__file__", str(module_dir / "desktop.py"))

    resource_root = tmp_path / "res"
    target = resource_root / "share" / "icons" / "omastore.svg"
    target.parent.mkdir(parents=True)
    target.write_text("from-resources")

    class Traversable:
        def __init__(self, path: Path) -> None:
            self._path = path

        def __truediv__(self, other: str) -> "Traversable":
            return Traversable(self._path / other)

        def is_file(self) -> bool:
            return self._path.is_file()

        def __str__(self) -> str:
            return str(self._path)

    monkeypatch.setattr(desktop.resources, "files", lambda name: Traversable(resource_root))

    found = desktop._share_file("icons/omastore.svg")
    assert found == target
