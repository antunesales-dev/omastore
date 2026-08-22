"""Pre-install static scan. Fetch a tree, never execute it, fail closed."""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import tarfile
import tempfile
import time
import urllib.error
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Literal
from urllib.parse import quote, urlparse

from omastore import __version__
from omastore.credits import PLUGIN_STORE_REPO, THEME_STORE_REPO
from omastore.models import Item
from omastore.safety import (
    FETCH_TIMEOUT,
    MAX_FETCH_BYTES,
    allowed_install_url,
    fetch_bytes,
)

Verdict = Literal["clean", "warn", "block"]
Severity = Literal["block", "warn"]

MAX_ARCHIVE_BYTES = MAX_FETCH_BYTES
MAX_EXTRACTED_FILES = 800
MAX_SCAN_FILE_BYTES = 256 * 1024
MAX_FINDINGS = 40
MAX_FINDINGS_PER_FILE = 8
CLONE_TIMEOUT = 60
BASE64_MIN = 400
SCAN_CACHE_TTL = 6 * 60 * 60

SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".tox",
    "dist",
    "build",
    "vendor",
    ".idea",
    ".vscode",
}

SKIP_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".eot",
    ".mp3",
    ".mp4",
    ".webm",
    ".wav",
    ".so",
    ".dll",
    ".dylib",
    ".wasm",
    ".zip",
    ".gz",
    ".bz2",
    ".xz",
    ".7z",
    ".pdf",
    ".bin",
    ".qmlc",
    ".pyc",
    ".pyo",
}

CODE_SUFFIXES = {
    ".qml",
    ".js",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".jsx",
    ".json",
    ".py",
    ".sh",
    ".bash",
    ".zsh",
    ".fish",
    ".desktop",
    ".xml",
    ".html",
    ".htm",
    ".css",
    ".conf",
    ".toml",
    ".yaml",
    ".yml",
    ".svg",
    ".qmlinc",
}

DOC_SUFFIXES = {".md", ".txt", ".rst"}

MANIFEST_NAMES = ("plugin.json", "manifest.json", "omarchy-plugin.json")

MANIFEST_FILE_KEYS = ("main", "qml", "entry", "source", "file", "module")
MANIFEST_FILE_LIST_KEYS = ("files", "qmlFiles", "components", "modules")

# Hosts a plugin may mention without counting as a mystery endpoint.
OK_HOSTS = {
    "github.com",
    "www.github.com",
    "raw.githubusercontent.com",
    "objects.githubusercontent.com",
    "codeload.github.com",
    "user-attachments.githubusercontent.com",
    "camo.githubusercontent.com",
    "api.github.com",
    "omarchytheme.com",
    "www.omarchytheme.com",
    "omarchyplugins.com",
    "www.omarchyplugins.com",
    "omarchy.org",
    "www.omarchy.org",
}

HANCORE_ISSUES_NEW = f"{PLUGIN_STORE_REPO}/issues/new"
HANCORE_ADVISORY_NEW = f"{PLUGIN_STORE_REPO}/security/advisories/new"
LIMEHAWK_ISSUES_NEW = f"{THEME_STORE_REPO}/issues/new"

_NETWORK_APIS = [
    (re.compile(r"\bfetch\s*\("), "fetch(", "network", "warn"),
    (re.compile(r"\bXMLHttpRequest\b"), "XMLHttpRequest", "network", "warn"),
    (re.compile(r"\bQNetworkAccessManager\b"), "QNetworkAccessManager", "network", "warn"),
    (re.compile(r"\bWebSocket\b"), "WebSocket", "network", "warn"),
    (re.compile(r"\bwget\b"), "wget", "network", "warn"),
    (re.compile(r"\bcurl\b"), "curl", "network", "warn"),
    (re.compile(r"\burllib\.request\b"), "urllib.request", "network", "warn"),
    (re.compile(r"\brequests\.(get|post|put|delete|request)\s*\("), "requests", "network", "warn"),
    (re.compile(r"\bhttpx\."), "httpx", "network", "warn"),
    (re.compile(r"\burlopen\s*\("), "urlopen", "network", "warn"),
]

_PROCESS_APIS = [
    (re.compile(r"\bProcess\s*\{"), "QML Process", "process", "warn"),
    (re.compile(r"\bQProcess\b"), "QProcess", "process", "warn"),
    (re.compile(r"\bsubprocess\b"), "subprocess", "process"),
    (re.compile(r"\bos\.system\s*\("), "os.system", "process"),
    (re.compile(r"\bos\.popen\s*\("), "os.popen", "process"),
    (re.compile(r"\bpopen\s*\("), "popen", "process"),
    (re.compile(r"\bexec\s*\("), "exec(", "process"),
    (re.compile(r"\bhyprctl\b"), "hyprctl", "process", "warn"),
    (re.compile(r"\bbash\s+-c\b"), "bash -c", "process"),
    (re.compile(r"/bin/sh\b"), "/bin/sh", "process"),
    (re.compile(r"/bin/bash\b"), "/bin/bash", "process"),
    (re.compile(r"\bchild_process\b"), "child_process", "process"),
    (re.compile(r"\bspawnSync\s*\("), "spawnSync", "process"),
    (re.compile(r"\bctypes\b"), "ctypes", "process"),
]

_SECRET_APIS = [
    (re.compile(r"~/\.ssh\b"), "~/.ssh", "secrets"),
    (re.compile(r"(^|[^\w.])\.ssh/"), ".ssh/", "secrets"),
    (re.compile(r"\bid_rsa\b"), "id_rsa", "secrets"),
    (re.compile(r"\bid_ed25519\b"), "id_ed25519", "secrets"),
    (re.compile(r"BEGIN OPENSSH PRIVATE KEY"), "OpenSSH private key", "secrets"),
    (re.compile(r"/etc/shadow\b"), "/etc/shadow", "secrets"),
    (re.compile(r"\b\.gnupg\b"), ".gnupg", "secrets"),
    (re.compile(r"\b\.netrc\b"), ".netrc", "secrets"),
    (re.compile(r"\bGH_TOKEN\b"), "GH_TOKEN", "secrets"),
    (re.compile(r"\bAWS_SECRET"), "AWS_SECRET", "secrets"),
    (re.compile(r"(^|[^\w])cookies?(\W|$)", re.IGNORECASE), "cookie", "secrets"),
    (re.compile(r"\bapi[_-]?token\b", re.IGNORECASE), "api token", "secrets"),
]

_SHELL_JSON_WRITE = re.compile(
    r"shell\.json.*(write|save|FileIO|setSource)|"
    r"(write|save|FileIO|setSource).*shell\.json",
    re.IGNORECASE,
)
_SHELL_JSON = re.compile(r"shell\.json")

_OBFUSCATION = [
    (re.compile(r"\beval\s*\("), "eval(", "obfuscation"),
    (re.compile(r"\bFunction\s*\("), "Function(", "obfuscation"),
    (re.compile(r"\batob\s*\("), "atob(", "obfuscation"),
    (re.compile(r"eval\s*\(\s*function\s*\(\s*p\s*,\s*a\s*,\s*c\s*,\s*k"), "packed JS", "obfuscation"),
    (re.compile(r"String\.fromCharCode\s*\("), "String.fromCharCode", "obfuscation"),
    (re.compile(rf"[A-Za-z0-9+/]{{{BASE64_MIN},}}={{0,2}}"), "huge base64 blob", "obfuscation"),
]

_DOC_EXEC = [
    (re.compile(r"curl[^\n]{0,80}\|\s*(bash|sh)\b"), "curl | bash", "process"),
    (re.compile(r"wget[^\n]{0,80}\|\s*(bash|sh)\b"), "wget | sh", "process"),
    (re.compile(r"\bbash\s+-c\b"), "bash -c", "process"),
    (re.compile(r"\bhyprctl\b"), "hyprctl", "process", "warn"),
    (re.compile(r"\bProcess\s*\{"), "QML Process", "process", "warn"),
]

_HOST_RE = re.compile(r"https?://([A-Za-z0-9.-]+)")

_GITHUB_REPO_RE = re.compile(
    r"^https://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
    re.IGNORECASE,
)


@dataclass
class Finding:
    severity: Severity
    category: str
    path: str
    line: int | None
    why: str
    snippet: str = ""


@dataclass
class ScanResult:
    item_key: str
    item_id: str
    item_name: str
    kind: str
    repo: str
    verdict: Verdict
    findings: list[Finding] = field(default_factory=list)
    scanned_files: int = 0
    source: str = "catalog"
    error: str = ""

    def allows_install(self, accept_scan_risks: bool = False) -> bool:
        """Fetch/parse failure cannot be overridden. Pattern hits can, with the flag."""
        if self.source == "failed" or self.error:
            return False
        if self.verdict == "clean":
            return True
        return bool(accept_scan_risks)

    def format_findings(self, *, limit: int = 20) -> str:
        if not self.findings:
            return "no findings"
        lines: list[str] = []
        for finding in self.findings[:limit]:
            loc = finding.path or "catalog"
            if finding.line:
                loc = f"{loc}:{finding.line}"
            lines.append(f"{finding.severity:5}  {finding.category:12}  {loc}")
            lines.append(f"       {finding.why}")
        extra = len(self.findings) - limit
        if extra > 0:
            lines.append(f"       … {extra} more")
        return "\n".join(lines)

    def format_full(self) -> str:
        bits = [
            f"scan  {self.item_key}  {self.verdict}",
        ]
        if self.repo:
            bits.append(self.repo)
        source = f"source: {self.source}"
        if self.error:
            source += f"  error: {self.error}"
        bits.append(source)
        bits.append("")
        bits.append(self.format_findings())
        bits.append("")
        bits.append(
            "Not a sandbox. Not proof of safety. "
            "HANCORE verified is a signal, not a skip."
        )
        return "\n".join(bits)

    def cli_block_message(self) -> str:
        if self.error:
            return f"scan failed (refused): {self.error}"
        return "scan found issues:\n" + self.format_findings()


def github_owner_repo(url: str) -> tuple[str, str] | None:
    cleaned = str(url or "").strip().split("#", 1)[0].split("?", 1)[0]
    cleaned = cleaned.rstrip("/").removesuffix(".git")
    match = _GITHUB_REPO_RE.match(cleaned)
    if match:
        return match.group(1), match.group(2)
    parsed = urlparse(cleaned)
    if (parsed.hostname or "").lower() != "github.com":
        return None
    parts = [p for p in (parsed.path or "").split("/") if p]
    if len(parts) < 2:
        return None
    return parts[0], parts[1].removesuffix(".git")


def github_archive_urls(url: str) -> list[str]:
    pair = github_owner_repo(url)
    if pair is None:
        return []
    owner, name = pair
    return [
        f"https://github.com/{owner}/{name}/archive/HEAD.tar.gz",
        f"https://github.com/{owner}/{name}/archive/refs/heads/main.tar.gz",
        f"https://github.com/{owner}/{name}/archive/refs/heads/master.tar.gz",
    ]


def plugin_issues_url(repo: str) -> str:
    pair = github_owner_repo(repo)
    if pair is None:
        return ""
    owner, name = pair
    return f"https://github.com/{owner}/{name}/issues/new"


def catalog_findings(item: Item) -> list[Finding]:
    """Odd install URL is a block. Verification/warnings stay on the confirm screen."""
    findings: list[Finding] = []
    url = (item.install_url or item.repo or "").strip()
    if not url:
        findings.append(
            Finding("block", "catalog", "catalog", None, "no install URL")
        )
        return findings
    if not allowed_install_url(url):
        findings.append(
            Finding(
                "block",
                "catalog",
                "catalog",
                None,
                f"odd install URL (not a https GitHub repo): {url}",
            )
        )
        return findings
    repo = (item.repo or "").strip().rstrip("/").removesuffix(".git")
    install = url.rstrip("/").removesuffix(".git")
    if repo and install and repo.lower() != install.lower():
        findings.append(
            Finding(
                "warn",
                "catalog",
                "catalog",
                None,
                f"install URL differs from repo ({install} vs {repo})",
            )
        )
    return findings


def _looks_like_archive(data: bytes) -> bool:
    if data.startswith(b"\x1f\x8b"):
        return True
    if data[:8] == b"ustar" or b"ustar" in data[:512]:
        return True
    if data[:2] == b"PK":
        return False
    if data.lstrip().startswith(b"<") or data.startswith(b"Not Found") or data.startswith(b"404"):
        return False
    return False


def extract_archive(data: bytes, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    if not _looks_like_archive(data):
        raise ValueError("response is not a gzip tar archive")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tar:
        members = tar.getmembers()
        if len(members) > MAX_EXTRACTED_FILES:
            raise ValueError(f"archive has too many files ({len(members)})")
        tar.extractall(dest, filter="data")
    entries = [p for p in dest.iterdir() if p.name not in {".", ".."}]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return dest


def shallow_clone(url: str, dest: Path) -> None:
    if not allowed_install_url(url):
        raise PermissionError(f"blocked url: {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = ""
    env["GCM_INTERACTIVE"] = "never"
    cmd = [
        "git",
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "protocol.file.allow=never",
        "-c",
        "clone.recurseSubmodules=false",
        "clone",
        "--depth",
        "1",
        "--single-branch",
        "--no-recurse-submodules",
        url,
        str(dest),
    ]
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=CLONE_TIMEOUT,
            env=env,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("git is not available") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("git clone timed out") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "git clone failed").strip()
        raise RuntimeError(detail)


@contextmanager
def fetched_tree(url: str) -> Iterator[tuple[Path, str]]:
    """Yield (root, source) for a GitHub archive or a hookless shallow clone."""
    if not allowed_install_url(url):
        raise PermissionError(f"blocked url: {url}")
    with tempfile.TemporaryDirectory(prefix="omastore-scan-") as tmp:
        dest = Path(tmp)
        last_error: Exception | None = None
        for archive_url in github_archive_urls(url):
            try:
                data = fetch_bytes(archive_url, timeout=FETCH_TIMEOUT, limit=MAX_ARCHIVE_BYTES)
                root = extract_archive(data, dest / "archive")
                yield root, "archive"
                return
            except (
                PermissionError,
                ValueError,
                OSError,
                tarfile.TarError,
                urllib.error.URLError,
                TimeoutError,
            ) as exc:
                last_error = exc
                continue
        clone_dir = dest / "git"
        try:
            shallow_clone(url, clone_dir)
            yield clone_dir, "clone"
        except (PermissionError, RuntimeError, OSError) as exc:
            detail = str(exc) or str(last_error) or "could not fetch repository"
            raise RuntimeError(detail) from exc


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except (ValueError, OSError):
        return path.name


def _is_under(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (ValueError, OSError):
        return False
    return True


def _text_lines(path: Path) -> list[str] | None:
    try:
        size = path.stat().st_size
    except OSError:
        return None
    if size > MAX_SCAN_FILE_BYTES:
        return None
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in raw[:2048]:
        return None
    text = raw.decode("utf-8", errors="replace")
    return text.splitlines()


def _snippet(line: str) -> str:
    text = line.strip().replace("\t", " ")
    if len(text) > 80:
        return text[:77] + "..."
    return text


def _add(
    findings: list[Finding],
    severity: Severity,
    category: str,
    path: str,
    line: int | None,
    why: str,
    snippet: str = "",
) -> None:
    if len(findings) >= MAX_FINDINGS:
        return
    findings.append(Finding(severity, category, path, line, why, snippet))


def audit_manifest(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    root = root.resolve()
    found = [root / name for name in MANIFEST_NAMES if (root / name).is_file()]
    if not found:
        return findings
    for manifest_path in found:
        rel = _rel(root, manifest_path)
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, json.JSONDecodeError) as exc:
            _add(
                findings,
                "block",
                "manifest",
                rel,
                None,
                f"could not parse manifest: {exc}",
            )
            continue
        if not isinstance(payload, dict):
            _add(findings, "block", "manifest", rel, None, "manifest is not an object")
            continue
        refs: list[str] = []
        for key in MANIFEST_FILE_KEYS:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                refs.append(value.strip())
        for key in MANIFEST_FILE_LIST_KEYS:
            value = payload.get(key)
            if isinstance(value, list):
                refs.extend(str(item).strip() for item in value if str(item).strip())
        command = payload.get("installCommand") or payload.get("install")
        if isinstance(command, str) and command.strip():
            _add(
                findings,
                "block",
                "process",
                rel,
                None,
                f"manifest lists an install command: {command.strip()[:80]}",
            )
        for ref in refs:
            if ref.startswith(("http://", "https://")):
                _add(
                    findings,
                    "block",
                    "network",
                    rel,
                    None,
                    f"manifest points at a URL instead of a local file: {ref}",
                )
                continue
            if ref.startswith("-") or "\x00" in ref:
                _add(findings, "block", "manifest", rel, None, f"unsafe path in manifest: {ref}")
                continue
            candidate = (root / ref).resolve()
            if not _is_under(root, candidate):
                _add(
                    findings,
                    "block",
                    "manifest",
                    rel,
                    None,
                    f"manifest path escapes the tree: {ref}",
                )
                continue
            if not candidate.is_file():
                _add(
                    findings,
                    "warn",
                    "manifest",
                    rel,
                    None,
                    f"manifest lists missing file: {ref}",
                )
    return findings


def _host_ok(host: str) -> bool:
    host = (host or "").strip().lower().rstrip(".")
    return host in OK_HOSTS


def _scan_line(
    findings: list[Finding],
    rel: str,
    lineno: int,
    line: str,
    *,
    code: bool,
    per_file: list[int],
) -> None:
    if per_file[0] >= MAX_FINDINGS_PER_FILE or len(findings) >= MAX_FINDINGS:
        return
    patterns = _NETWORK_APIS + _PROCESS_APIS + _SECRET_APIS + _OBFUSCATION if code else _DOC_EXEC
    for spec in patterns:
        regex, label, category = spec[0], spec[1], spec[2]
        severity: Severity = spec[3] if len(spec) > 3 else "block"  # type: ignore[misc]
        if regex.search(line):
            _add(
                findings,
                severity,
                category,
                rel,
                lineno,
                label,
                _snippet(line),
            )
            per_file[0] += 1
            if per_file[0] >= MAX_FINDINGS_PER_FILE or len(findings) >= MAX_FINDINGS:
                return
    if code:
        if _SHELL_JSON_WRITE.search(line):
            _add(
                findings,
                "block",
                "secrets",
                rel,
                lineno,
                "writes shell.json",
                _snippet(line),
            )
            per_file[0] += 1
        elif _SHELL_JSON.search(line):
            _add(
                findings,
                "warn",
                "secrets",
                rel,
                lineno,
                "touches shell.json",
                _snippet(line),
            )
            per_file[0] += 1
        for match in _HOST_RE.finditer(line):
            host = match.group(1)
            if _host_ok(host):
                continue
            _add(
                findings,
                "block",
                "network",
                rel,
                lineno,
                f"raw host {host}",
                _snippet(line),
            )
            per_file[0] += 1
            if per_file[0] >= MAX_FINDINGS_PER_FILE:
                return


def audit_tree(root: Path) -> tuple[list[Finding], int]:
    findings = audit_manifest(root)
    scanned = 0
    skipped_vendor = False
    root = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        kept: list[str] = []
        for name in dirnames:
            if name in SKIP_DIRS:
                skipped_vendor = True
                continue
            kept.append(name)
        dirnames[:] = kept
        for name in filenames:
            path = current / name
            if not _is_under(root, path):
                continue
            suffix = path.suffix.lower()
            if suffix in SKIP_SUFFIXES:
                continue
            rel = _rel(root, path)
            code = suffix in CODE_SUFFIXES or suffix == ""
            doc = suffix in DOC_SUFFIXES
            if not code and not doc:
                if suffix:
                    continue
            lines = _text_lines(path)
            if lines is None:
                continue
            scanned += 1
            per_file = [0]
            for lineno, line in enumerate(lines, 1):
                _scan_line(findings, rel, lineno, line, code=code or not doc, per_file=per_file)
                if per_file[0] >= MAX_FINDINGS_PER_FILE or len(findings) >= MAX_FINDINGS:
                    break
    if skipped_vendor:
        _add(
            findings,
            "warn",
            "catalog",
            "",
            None,
            "skipped vendor/node_modules/.git (not fully scanned)",
        )
    return findings, scanned


def _verdict(findings: list[Finding], *, error: str = "", source: str = "catalog") -> Verdict:
    if error or source == "failed":
        return "block"
    if any(finding.severity == "block" for finding in findings):
        return "block"
    if findings:
        return "warn"
    return "clean"


def _result(
    item: Item,
    findings: list[Finding],
    *,
    scanned_files: int = 0,
    source: str = "catalog",
    error: str = "",
) -> ScanResult:
    return ScanResult(
        item_key=item.key,
        item_id=item.id,
        item_name=item.name,
        kind=item.kind,
        repo=(item.repo or item.install_url or ""),
        verdict=_verdict(findings, error=error, source=source),
        findings=findings,
        scanned_files=scanned_files,
        source=source if not error else "failed",
        error=error,
    )


def scan_tree(item: Item, root: Path) -> ScanResult:
    """Audit an already-fetched tree. Used by tests and by scan_item."""
    findings = catalog_findings(item)
    extra, scanned = audit_tree(root)
    findings.extend(extra)
    source = "tree"
    if any(finding.category == "catalog" and finding.severity == "block" for finding in findings):
        source = "catalog"
    return _result(item, findings, scanned_files=scanned, source=source)


def _scan_cache_path(item: Item) -> Path:
    from omastore.catalog import cache_dir
    from omastore.models import slugify

    ident = slugify(item.key or item.id or "item") or "item"
    return cache_dir() / "scans" / f"{ident}.json"


def save_scan_cache(item: Item, result: ScanResult) -> None:
    path = _scan_cache_path(item)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = scan_payload(result)
        payload["saved_at"] = time.time()
        path.write_text(json.dumps(payload), encoding="utf-8")
    except OSError:
        return


def load_scan_cache(item: Item) -> dict | None:
    path = _scan_cache_path(item)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def scan_cache_fresh(
    item: Item,
    *,
    ttl: int = SCAN_CACHE_TTL,
    now: float | None = None,
) -> bool:
    """True when a cache row exists, is within ttl, and still matches this repo."""
    data = load_scan_cache(item)
    if not data:
        return False
    try:
        saved = float(data.get("saved_at") or 0)
    except (TypeError, ValueError):
        return False
    stamp = time.time() if now is None else now
    if saved <= 0 or stamp - saved >= ttl:
        return False
    repo = (item.repo or item.install_url or "").strip().rstrip("/")
    cached = str(data.get("repo") or "").strip().rstrip("/")
    if repo and cached and repo != cached:
        return False
    return True


def cached_scan_summary(item: Item) -> str:
    data = load_scan_cache(item)
    if not data:
        return "scan: not scanned"
    verdict = str(data.get("verdict") or "unknown")
    if not scan_cache_fresh(item):
        return f"scan: stale ({verdict})"
    return f"scan: {verdict}"


def scan_item(item: Item, *, tree: Path | None = None) -> ScanResult:
    """Catalog checks, then fetch-without-running, then static audit. Fail closed."""
    findings = catalog_findings(item)
    blocked_url = any(
        finding.category == "catalog" and finding.severity == "block" for finding in findings
    )
    if tree is not None:
        extra, scanned = audit_tree(tree)
        findings.extend(extra)
        return _result(item, findings, scanned_files=scanned, source="tree")
    if blocked_url:
        result = _result(item, findings, source="catalog")
        save_scan_cache(item, result)
        return result
    url = (item.install_url or item.repo or "").strip()
    try:
        with fetched_tree(url) as (root, source):
            extra, scanned = audit_tree(root)
            findings.extend(extra)
            result = _result(item, findings, scanned_files=scanned, source=source)
            save_scan_cache(item, result)
            return result
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as exc:
        why = str(exc).strip() or exc.__class__.__name__
        findings.append(
            Finding("block", "fetch", "", None, f"scan failed: {why}")
        )
        result = _result(item, findings, source="failed", error=why)
        save_scan_cache(item, result)
        return result


def scan_items(items: list[Item]) -> list[ScanResult]:
    """Scan each item. Always scans all members so a pack cannot skip a later one."""
    return [scan_item(item) for item in items]


def first_issue(results: list[ScanResult]) -> ScanResult | None:
    failed = next((row for row in results if row.source == "failed" or row.error), None)
    if failed is not None:
        return failed
    return next((row for row in results if row.verdict != "clean"), None)


def anyway_prompt(result: ScanResult, item: Item, *, extra: str = "") -> str:
    lines = [
        "Install anyway despite scan findings?",
        f"{item.key}",
    ]
    if item.repo or item.install_url:
        lines.append(str(item.repo or item.install_url))
    lines.append("")
    lines.append("This is not a sandbox. The scan is not proof of safety.")
    if extra:
        lines.append(extra)
    lines.append("")
    lines.append(result.format_findings())
    return "\n".join(lines)


def findings_prompt(result: ScanResult, item: Item, *, extra: str = "", allow_anyway: bool = True) -> str:
    lines = [
        f"scan {result.verdict}  {item.key}",
    ]
    if item.repo or item.install_url:
        lines.append(str(item.repo or item.install_url))
    if extra:
        lines.append(extra)
    if result.error:
        lines.append(f"error: {result.error}")
    lines.append("")
    lines.append(result.format_findings())
    lines.append("")
    lines.append("Not a sandbox. Not proof of safety. HANCORE verified is a signal, not a skip.")
    lines.append("")
    if allow_anyway:
        lines.append("[n] abort (default)   [r] report   [i] install anyway")
    else:
        lines.append("[n] abort (default)   [r] report")
        lines.append("Scan failed; install is refused (fail closed).")
    return "\n".join(lines)


def report_title(item: Item, result: ScanResult) -> str:
    name = (item.id or item.name or "plugin").strip()
    return f"omastore scan: {name} ({result.verdict})"


def report_body(item: Item, result: ScanResult) -> str:
    lines = [
        f"**Plugin:** `{item.key}` — {item.name}",
        f"**Repo:** {item.repo or item.install_url or '(none)'}",
        f"**Catalog verification:** {item.verification_label or item.verification or '(none)'}",
        f"**omastore:** {__version__}",
        "",
        "Pre-install static scan (no execute). This is **not** proof of malice; "
        "patterns false-positive. I am not auto-filing this.",
        "",
        f"**Verdict:** `{result.verdict}`  **Source:** `{result.source}`",
    ]
    if result.error:
        lines.append(f"**Error:** {result.error}")
    lines.append("")
    lines.append("### Findings")
    lines.append("")
    if not result.findings:
        lines.append("(none)")
    for finding in result.findings[:MAX_FINDINGS]:
        loc = finding.path or "catalog"
        if finding.line:
            loc = f"{loc}:{finding.line}"
        lines.append(f"- **{finding.severity}** `{finding.category}` `{loc}` — {finding.why}")
        if finding.snippet:
            lines.append(f"  `{finding.snippet}`")
    lines.append("")
    lines.append("Filed from omastore. Do not treat this as a sandbox report.")
    text = "\n".join(lines)
    # Never leak local temp paths.
    text = re.sub(r"/tmp/omastore-scan-[^\s]+", "<scan-tmp>", text)
    text = re.sub(r"/home/[^/\s]+", "~", text)
    return text


def _issue_url(base: str, title: str, body: str) -> str:
    # GitHub caps query strings; keep the draft usable.
    max_body = 5500
    if len(body) > max_body:
        body = body[: max_body - 20] + "\n\n…truncated"
    return (
        f"{base}?title={quote(title, safe='')}&body={quote(body, safe='')}"
    )


def report_urls(item: Item, result: ScanResult) -> dict[str, str]:
    """Prefill GitHub issue drafts. Never POST."""
    title = report_title(item, result)
    body = report_body(item, result)
    if item.kind == "theme":
        catalog = _issue_url(LIMEHAWK_ISSUES_NEW, title, body)
        advisory = ""
    else:
        catalog = _issue_url(HANCORE_ISSUES_NEW, title, body)
        advisory = HANCORE_ADVISORY_NEW
    plugin = ""
    issues = plugin_issues_url(item.repo or item.install_url or "")
    if issues:
        plugin = _issue_url(issues, title, body)
    return {
        "catalog_issue": catalog,
        "plugin_issue": plugin,
        "advisory": advisory,
        "title": title,
        "body": body,
    }


def copy_text(text: str) -> bool:
    payload = text.encode("utf-8")
    commands = (
        ["wl-copy"],
        ["xclip", "-selection", "clipboard"],
        ["xsel", "--clipboard", "--input"],
    )
    for cmd in commands:
        try:
            completed = subprocess.run(
                cmd,
                input=payload,
                check=False,
                capture_output=True,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            continue
        if completed.returncode == 0:
            return True
    return False


def open_report(item: Item, result: ScanResult, *, opener=None) -> dict:
    """Open a prefilled GitHub issue draft. Clipboard fallback. Never POST."""
    from omastore.links import open_url

    urls = report_urls(item, result)
    primary = urls["catalog_issue"]
    opened = open_url(primary, opener=opener)
    copied = False
    if not opened["ok"]:
        copied = copy_text(urls["body"])
    message = opened["message"]
    if copied and not opened["ok"]:
        message = f"copied report draft; open {primary}"
    elif urls.get("plugin_issue"):
        message = f"{opened['message']}; plugin issues: {urls['plugin_issue']}"
    return {
        "ok": bool(opened["ok"] or copied),
        "url": primary,
        "plugin_issue": urls.get("plugin_issue") or "",
        "advisory": urls.get("advisory") or "",
        "copied": copied,
        "message": message,
    }


def scan_payload(result: ScanResult) -> dict:
    return {
        "verdict": result.verdict,
        "allows_install": result.allows_install(False),
        "source": result.source,
        "error": result.error,
        "item": result.item_key,
        "repo": result.repo,
        "scanned_files": result.scanned_files,
        "findings": [
            {
                "severity": finding.severity,
                "category": finding.category,
                "path": finding.path,
                "line": finding.line,
                "why": finding.why,
            }
            for finding in result.findings
        ],
        "note": (
            "Static scan is not proof of safety. Plugins run unsandboxed. "
            "HANCORE verified is a signal, not a skip. Fetch/parse failure cannot be overridden."
        ),
    }
