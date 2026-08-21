from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

NO_PREVIEW = "no preview"
_HALF_BLOCK = "▀"
_RESET = "\x1b[0m"
_TIMEOUT = 12
_WS = b" \t\r\n"
DEFAULT_WIDTH = 72
DEFAULT_HEIGHT = 40
_PAD = "#111111"
Cell = tuple[tuple[int, int, int], tuple[int, int, int]]
Cells = list[list[Cell]]


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


def _box(width: int, height: int) -> tuple[int, int]:
    cols = max(8, min(int(width), 120))
    rows = max(4, min(int(height), 80))
    if rows % 2:
        rows += 1
    return cols, rows


def _ppm_bytes(path: Path, width: int, height: int) -> bytes | None:
    binary = _magick()
    if binary is None:
        return None
    cols, rows = _box(width, height)
    geom = f"{cols}x{rows}"
    cmd = [
        binary,
        str(path),
        "-auto-orient",
        "-filter",
        "Lanczos",
        "-resize",
        geom,
        "-background",
        _PAD,
        "-gravity",
        "center",
        "-extent",
        geom,
        "-unsharp",
        "0x0.6+0.6+0.02",
        "ppm:-",
    ]
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


def _hex(rgb: tuple[int, int, int]) -> str:
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def _render_cells(width: int, height: int, pixels: list[tuple[int, int, int]]) -> Cells:
    rows: Cells = []
    for y in range(0, height, 2):
        row: list[Cell] = []
        for x in range(width):
            upper = pixels[y * width + x]
            lower = pixels[(y + 1) * width + x] if y + 1 < height else upper
            row.append((upper, lower))
        rows.append(row)
    return rows


def cells_to_ansi(rows: Cells) -> str:
    lines: list[str] = []
    for row in rows:
        parts: list[str] = []
        for fg, bg in row:
            parts.append(_sgr(fg, bg))
            parts.append(_HALF_BLOCK)
        parts.append(_RESET)
        lines.append("".join(parts))
    return "\n".join(lines)


def cells_to_rich(rows: Cells):
    from rich.style import Style
    from rich.text import Text

    text = Text()
    for index, row in enumerate(rows):
        if index:
            text.append("\n")
        for fg, bg in row:
            text.append(_HALF_BLOCK, style=Style(color=_hex(fg), bgcolor=_hex(bg)))
    return text


def to_cells(path: str | Path, *, width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT) -> Cells:
    """Decode an image into half-block cells. Empty list if it cannot be rendered."""
    try:
        image = Path(path)
        if not image.is_file():
            return []
        data = _ppm_bytes(image, int(width), int(height))
        if not data:
            return []
        ppm_w, ppm_h, pixels = parse_ppm(data)
        if not pixels or ppm_w <= 0 or ppm_h <= 0:
            return []
        return _render_cells(ppm_w, ppm_h, pixels)
    except Exception:
        return []


def to_ansi(path: str | Path, *, width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT) -> str:
    """Render image as unicode half-block ANSI (or a plain fallback message)."""
    rows = to_cells(path, width=width, height=height)
    return cells_to_ansi(rows) if rows else NO_PREVIEW


def to_rich(path: str | Path, *, width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT):
    """Return rich.text.Text for the preview (or 'no preview')."""
    from rich.text import Text

    rows = to_cells(path, width=width, height=height)
    return cells_to_rich(rows) if rows else Text(NO_PREVIEW)
