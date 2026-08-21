import json
from pathlib import Path

from omastore import notice


def test_notice_text_credits_catalogs() -> None:
    assert "unsandboxed" in notice.NOTICE.lower()
    assert "limehawk" in notice.NOTICE.lower()
    assert "HANCORE" in notice.NOTICE
    assert "without running" in notice.NOTICE.lower() or "scans" in notice.NOTICE.lower()


def test_seen_and_mark(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "notice.json"
    monkeypatch.setattr(notice, "STATE_PATH", path)
    assert notice.seen() is False
    notice.mark_seen()
    assert notice.seen() is True
    assert json.loads(path.read_text(encoding="utf-8"))["unsandboxed"] is True


def test_corrupt_notice_is_unseen(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "notice.json"
    path.write_text("{nope", encoding="utf-8")
    monkeypatch.setattr(notice, "STATE_PATH", path)
    assert notice.seen() is False
