from __future__ import annotations

import ipaddress
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
)

from omastore.models import slugify

MAX_FETCH_BYTES = 12 * 1024 * 1024
FETCH_TIMEOUT = 20

ALLOWED_FETCH_HOSTS = {
    "raw.githubusercontent.com",
    "github.com",
    "codeload.github.com",
    "objects.githubusercontent.com",
    "user-attachments.githubusercontent.com",
    "camo.githubusercontent.com",
    "omarchytheme.com",
    "www.omarchytheme.com",
    "omarchyplugins.com",
    "www.omarchyplugins.com",
}

def safe_cli_arg(value: object) -> str:
    """Return a non-empty operand that cannot be parsed as a flag, else ''."""
    text = str(value or "").strip()
    if not text or text.startswith("-") or "\x00" in text:
        return ""
    if "\n" in text or "\r" in text:
        return ""
    return text


def is_http_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _host_allowed(host: str) -> bool:
    host = (host or "").strip().lower().rstrip(".")
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    if not host:
        return False
    if host in ALLOWED_FETCH_HOSTS:
        return True
    return False


def _literal_ip(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        return None


def allowed_fetch_url(url: str) -> bool:
    """True if url is http(s) to an allowlisted host (never a literal private IP)."""
    if not is_http_url(url):
        return False
    parsed = urlparse(url)
    host = parsed.hostname or ""
    ip = _literal_ip(host)
    if ip is not None:
        return False
    return _host_allowed(host)


def allowed_install_url(url: str) -> bool:
    """Installs are git clones; only https GitHub repos without /tree/."""
    if not allowed_fetch_url(url):
        return False
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    if host != "github.com":
        return False
    path = parsed.path or ""
    if "/tree/" in path:
        return False
    parts = [p for p in path.split("/") if p]
    return len(parts) >= 2


class _AllowlistRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_fetch_url(newurl):
            raise PermissionError(f"redirect blocked: {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_bytes(url: str, *, timeout: float = FETCH_TIMEOUT, limit: int = MAX_FETCH_BYTES) -> bytes:
    """GET url, follow only allowlisted redirects, cap bytes. Raises on failure."""
    if not allowed_fetch_url(url):
        raise PermissionError(f"blocked url: {url}")
    request = Request(url, headers={"User-Agent": _user_agent()})
    opener = build_opener(_AllowlistRedirects)
    with opener.open(request, timeout=timeout) as response:
        final = response.geturl()
        if final and not allowed_fetch_url(final):
            raise PermissionError(f"blocked url: {final}")
        chunks: list[bytes] = []
        total = 0
        while True:
            piece = response.read(64 * 1024)
            if not piece:
                break
            total += len(piece)
            if total > limit:
                raise ValueError("response too large")
            chunks.append(piece)
    return b"".join(chunks)


def fetch_text(url: str, *, timeout: float = FETCH_TIMEOUT, limit: int = MAX_FETCH_BYTES) -> str:
    return fetch_bytes(url, timeout=timeout, limit=limit).decode("utf-8", errors="replace")


def _user_agent() -> str:
    from omastore.catalog import USER_AGENT

    return USER_AGENT


def contained_child(root: Path, name: str) -> Path | None:
    """Join root/name only if name is a single safe path segment under root."""
    text = str(name or "").strip()
    if not text or text in {".", ".."} or text.startswith("-"):
        return None
    if "/" in text or "\\" in text or "\x00" in text:
        return None
    try:
        base = root.expanduser().resolve()
        path = (base / text).resolve()
    except OSError:
        return None
    try:
        path.relative_to(base)
    except ValueError:
        return None
    return path


def theme_repo_aliases(item) -> set[str]:
    """Slugs from the GitHub repo basename only (not the display title)."""
    aliases: set[str] = set()
    repo = str(getattr(item, "repo", "") or getattr(item, "install_url", "") or "")
    if not repo:
        return aliases
    cleaned = repo.strip().split("#", 1)[0].split("?", 1)[0]
    cleaned = cleaned.rstrip("/").removesuffix(".git")
    base = cleaned.rsplit("/", 1)[-1]
    if base:
        aliases.add(base.lower())
        aliases.add(slugify(base))
    return {a for a in aliases if a}


def theme_aliases(item) -> set[str]:
    """Slugs that may match an installed theme directory or `omarchy theme list` name."""
    aliases: set[str] = set()
    ident = slugify(str(getattr(item, "id", "") or ""))
    if ident:
        aliases.add(ident)
    name = slugify(str(getattr(item, "name", "") or ""))
    if name:
        aliases.add(name)
    aliases.update(theme_repo_aliases(item))
    return {a for a in aliases if a}
