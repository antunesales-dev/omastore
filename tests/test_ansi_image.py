import shutil
from pathlib import Path

from rich.text import Text

from omastore.ansi_image import parse_ppm, to_ansi, to_rich

FIXTURE = Path(__file__).parent / "fixtures" / "preview-tiny.png"


def _p6_2x2() -> bytes:
    return b"P6\n2 2\n255\n" + bytes(
        [
            255, 0, 0,
            0, 255, 0,
            0, 0, 255,
            255, 255, 255,
        ]
    )


def test_missing_file_returns_no_preview() -> None:
    assert to_ansi("/no/such/preview.png") == "no preview"


def test_missing_file_to_rich() -> None:
    result = to_rich("/no/such/preview.png")
    assert isinstance(result, Text)
    assert result.plain == "no preview"


def test_parse_ppm_p6_2x2() -> None:
    width, height, pixels = parse_ppm(_p6_2x2())
    assert (width, height) == (2, 2)
    assert pixels == [
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
        (255, 255, 255),
    ]


def test_parse_ppm_p3_2x2() -> None:
    data = b"P3\n2 2\n255\n255 0 0 0 255 0\n0 0 255 255 255 255\n"
    width, height, pixels = parse_ppm(data)
    assert (width, height) == (2, 2)
    assert pixels == [
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
        (255, 255, 255),
    ]


def test_parse_ppm_header_comment() -> None:
    data = b"P6\n# comment\n2 2\n255\n" + _p6_2x2()[11:]
    width, height, pixels = parse_ppm(data)
    assert (width, height) == (2, 2)
    assert pixels[0] == (255, 0, 0)


def test_to_ansi_without_magick(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("omastore.ansi_image.shutil.which", lambda _name: None)
    image = tmp_path / "x.png"
    image.write_bytes(b"not-an-image")
    assert to_ansi(image) == "no preview"


def test_to_ansi_half_blocks_from_ppm(monkeypatch, tmp_path: Path) -> None:
    image = tmp_path / "x.png"
    image.write_bytes(b"not-an-image")
    monkeypatch.setattr("omastore.ansi_image._ppm_bytes", lambda *_a, **_k: _p6_2x2())
    out = to_ansi(image, width=2, height=2)
    assert "▀" in out
    assert "38;2;255;0;0" in out
    assert "48;2;0;0;255" in out
    assert "38;2;0;255;0" in out
    assert "48;2;255;255;255" in out
    assert out.endswith("\x1b[0m")


def test_fixture_png_to_ansi() -> None:
    if not FIXTURE.is_file():
        return
    if not shutil.which("magick") and not shutil.which("convert"):
        assert to_ansi(FIXTURE, width=2, height=2) == "no preview"
        return
    out = to_ansi(FIXTURE, width=2, height=2)
    assert out != "no preview"
    assert "▀" in out
    assert "\x1b[38;2;" in out
