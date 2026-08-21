from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

NO_PREVIEW = "no preview"
_HALF_BLOCK = "▀"
_RESET = "\x1b[0m"
_TIMEOUT = 8
_WS = b" \t\r\n"


def parse_ppm(data: bytes) -> tuple[int, int, list[tuple[int, int, int]]]:
    """Parse PPM P6 or P3 bytes into (width, height, RGB pixels)."""
    if not data:
        raise ValueError("empty ppm")
    i = 0
    n = len(data)

    def skip_ws_comments() -> None:
        nonlocal i
        while i < n:
            c = data[i]
            if c in _WS:
                i += 1
                continue
            if c == 35:  # '#'
                i += 1
                while i < n and data[i] not in b"\n":
                    i += 1
                continue
            break

    def read_token() -> bytes:
        nonlocal i
        skip_ws_comments()
        start = i
        while i < n and data[i] not in _WS and data[i] != 35:
            i += 1
        if start == i:
            raise ValueError("truncated ppm header")
        return data[start:i]

    magic = read_token()
    if magic not in (b"P3", b"P6"):
        raise ValueError("not a ppm")
    width = int(read_token())
    height = int(read_token())
    maxval = int(read_token())
    if width <= 0 or height <= 0 or maxval <= 0 or width > 4096 or height > 4096:
        raise ValueError("invalid ppm dimensions")

    def scale(value: int) -> int:
        if value < 0:
            value = 0
        elif value > maxval:
            value = maxval
        if maxval == 255:
            return value
        return (value * 255 + maxval // 2) // maxval

    count = width * height
    pixels: list[tuple[int, int, int]] = []
    if magic == b"P6":
        if i >= n or data[i] not in _WS:
            raise ValueError("missing ppm raster separator")
        if data[i] == 13:
            i += 1
            if i < n and data[i] == 10:
                i += 1
        else:
            i += 1
        sample = 1 if maxval < 256 else 2
        need = count * 3 * sample
        raster = data[i : i + need]
        if len(raster) < need:
            raise ValueError("truncated ppm raster")
        off = 0
        for _ in range(count):
            rgb: list[int] = []
            for _ch in range(3):
                if sample == 1:
                    value = raster[off]
                    off += 1
                else:
                    value = (raster[off] << 8) | raster[off + 1]
                    off += 2
                rgb.append(scale(value))
            pixels.append((rgb[0], rgb[1], rgb[2]))
    else:
        values: list[int] = []
        while len(values) < count * 3:
            values.append(int(read_token()))
        for k in range(0, count * 3, 3):
            pixels.append((scale(values[k]), scale(values[k + 1]), scale(values[k + 2])))
    return width, height, pixels


def _magick() -> str | None:
    return shutil.which("magick") or shutil.which("convert")


def _ppm_bytes(path: Path, width: int, height: int) -> bytes | None:
    binary = _magick()
    if binary is None:
        return None
    cmd = [binary, str(path), "-resize", f"{width}x{height}!", "ppm:-"]
    try:
        completed = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            timeout=_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0 or not completed.stdout:
        return None
    return completed.stdout


def _sgr(fg: tuple[int, int, int], bg: tuple[int, int, int]) -> str:
    return (
        f"\x1b[38;2;{fg[0]};{fg[1]};{fg[2]}m"
        f"\x1b[48;2;{bg[0]};{bg[1]};{bg[2]}m"
    )


def _render_ansi(width: int, height: int, pixels: list[tuple[int, int, int]]) -> str:
    lines: list[str] = []
    for y in range(0, height, 2):
        parts: list[str] = []
        for x in range(width):
            upper = pixels[y * width + x]
            lower = pixels[(y + 1) * width + x] if y + 1 < height else upper
            parts.append(_sgr(upper, lower))
            parts.append(_HALF_BLOCK)
        parts.append(_RESET)
        lines.append("".join(parts))
    return "\n".join(lines)


def to_ansi(path: str | Path, *, width: int = 40, height: int = 12) -> str:
    """Render image as unicode half-block ANSI (or a plain fallback message)."""
    try:
        image = Path(path)
        if not image.is_file():
            return NO_PREVIEW
        data = _ppm_bytes(image, int(width), int(height))
        if not data:
            return NO_PREVIEW
        ppm_w, ppm_h, pixels = parse_ppm(data)
        if not pixels or ppm_w <= 0 or ppm_h <= 0:
            return NO_PREVIEW
        return _render_ansi(ppm_w, ppm_h, pixels) or NO_PREVIEW
    except Exception:
        return NO_PREVIEW


def to_rich(path: str | Path, *, width: int = 40, height: int = 12):
    """Return rich.text.Text for the ANSI preview (or 'no preview')."""
    from rich.text import Text

    try:
        return Text.from_ansi(to_ansi(path, width=width, height=height))
    except Exception:
        return Text(NO_PREVIEW)
