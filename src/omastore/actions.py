from __future__ import annotations

import subprocess
from dataclasses import dataclass

from omastore.local import run_omarchy
from omastore.models import Item
from omastore.safety import allowed_install_url, safe_cli_arg


@dataclass
class ActionResult:
    ok: bool
    command: list[str]
    stdout: str
    stderr: str

    @property
    def message(self) -> str:
        text = (self.stdout or self.stderr).strip()
        if text:
            return text
        return "ok" if self.ok else "command failed"


def _run(args: list[str], *, dry_run: bool = False, timeout: int = 30) -> ActionResult:
    if dry_run:
        return ActionResult(ok=True, command=args, stdout="dry-run: " + " ".join(args), stderr="")
    try:
        completed = run_omarchy(*args, timeout=timeout)
    except FileNotFoundError:
        return ActionResult(False, ["omarchy", *args], "", "omarchy CLI not found on PATH")
    except subprocess.TimeoutExpired:
        return ActionResult(False, ["omarchy", *args], "", "omarchy timed out")
    return ActionResult(
        ok=completed.returncode == 0,
        command=["omarchy", *args],
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _operand(value: object, *, error: str) -> str | ActionResult:
    text = safe_cli_arg(value)
    if not text:
        return ActionResult(False, [], "", error)
    return text


def install_pack(
    items: list[Item],
    *,
    dry_run: bool = False,
    accept_scan_risks: bool = False,
    scans: dict[str, object] | None = None,
) -> list[tuple[Item, ActionResult]]:
    """Install pending pack members one by one. Stop on the first failure."""
    results: list[tuple[Item, ActionResult]] = []
    for item in items:
        if not item.can_install:
            continue
        prior = None if scans is None else scans.get(item.key)
        result = install(
            item,
            dry_run=dry_run,
            scan_result=prior,
            accept_scan_risks=accept_scan_risks,
        )
        results.append((item, result))
        if not result.ok:
            break
    return results


def remove_pack(items: list[Item], *, dry_run: bool = False) -> list[tuple[Item, ActionResult]]:
    """Remove installed pack members one by one. Stop on the first failure."""
    results: list[tuple[Item, ActionResult]] = []
    for item in items:
        if not item.can_remove:
            continue
        result = remove(item, dry_run=dry_run)
        results.append((item, result))
        if not result.ok:
            break
    return results


def install(
    item: Item,
    *,
    dry_run: bool = False,
    scan_result: object | None = None,
    accept_scan_risks: bool = False,
) -> ActionResult:
    if not item.install_url:
        return ActionResult(False, [], "", f"{item.name} has no install URL")
    url = safe_cli_arg(item.install_url)
    if not url or not allowed_install_url(url):
        return ActionResult(False, [], "", "refused install url")
    if scan_result is None:
        from omastore.scan import scan_item

        scan_result = scan_item(item)
    allows = getattr(scan_result, "allows_install", None)
    if allows is None or not allows(accept_scan_risks):
        message = getattr(scan_result, "cli_block_message", lambda: "scan found issues")()
        return ActionResult(False, [], "", message)
    if item.kind == "theme":
        return _run(["theme", "install", url], dry_run=dry_run, timeout=180)
    return _run(["plugin", "add", url, "--enable", "--yes"], dry_run=dry_run, timeout=180)


def apply_theme(item: Item, *, dry_run: bool = False) -> ActionResult:
    if item.kind != "theme":
        return ActionResult(False, [], "", "apply is for themes")
    from omastore.local import omarchy_theme_name

    operand = safe_cli_arg(omarchy_theme_name(item)) or safe_cli_arg(item.id)
    if not operand:
        return ActionResult(False, [], "", "refused theme name")
    return _run(["theme", "set", operand], dry_run=dry_run, timeout=120)


def enable_plugin(item: Item, *, dry_run: bool = False) -> ActionResult:
    operand = _operand(item.id, error="refused plugin id")
    if isinstance(operand, ActionResult):
        return operand
    return _run(["plugin", "enable", operand], dry_run=dry_run, timeout=30)


def disable_plugin(item: Item, *, dry_run: bool = False) -> ActionResult:
    operand = _operand(item.id, error="refused plugin id")
    if isinstance(operand, ActionResult):
        return operand
    if not dry_run:
        from omastore.local import restore_hidden_bar_widgets

        restore_hidden_bar_widgets(item.id)
    return _run(["plugin", "disable", operand], dry_run=dry_run, timeout=30)


def _scan_allows(scan_result: object | None, item: Item, *, accept_scan_risks: bool) -> tuple[object, ActionResult | None]:
    if scan_result is None:
        from omastore.scan import scan_item

        scan_result = scan_item(item)
    allows = getattr(scan_result, "allows_install", None)
    if allows is None or not allows(accept_scan_risks):
        message = getattr(scan_result, "cli_block_message", lambda: "scan found issues")()
        return scan_result, ActionResult(False, [], "", message)
    return scan_result, None


def describe_outdated_update(items: list[Item]) -> str:
    """Confirm copy for bulk outdated update. Themes share one omarchy command."""
    rows = [item for item in items if item.can_update]
    n = len(rows)
    noun = "extra" if n == 1 else "extras"
    lines = [f"update {n} outdated {noun}?"]
    if any(item.kind == "theme" for item in rows):
        lines.append("omarchy theme update runs once for every extra git theme, not only the listed ones.")
    lines.append("Community plugins and themes run unsandboxed.")
    for item in rows:
        lines.append("")
        lines.append(item.key)
        loc = item.repo or item.install_url
        if loc:
            lines.append(str(loc))
        if item.verification_label:
            lines.append(f"verification: {item.verification_label}")
        if item.installed_rev or item.latest_rev:
            left = (item.installed_rev or "?")[:8]
            right = (item.latest_rev or "?")[:8]
            lines.append(f"{left} → {right}")
    return "\n".join(lines)


def update(
    item: Item,
    *,
    dry_run: bool = False,
    scan_result: object | None = None,
    accept_scan_risks: bool = False,
) -> ActionResult:
    _, blocked = _scan_allows(scan_result, item, accept_scan_risks=accept_scan_risks)
    if blocked is not None:
        return blocked
    if item.kind == "theme":
        return _run(["theme", "update"], dry_run=dry_run, timeout=180)
    operand = _operand(item.id, error="refused plugin id")
    if isinstance(operand, ActionResult):
        return operand
    return _run(["plugin", "update", operand, "--yes"], dry_run=dry_run, timeout=180)


def update_outdated(
    items: list[Item],
    *,
    dry_run: bool = False,
    accept_scan_risks: bool = False,
    scans: dict[str, object] | None = None,
) -> list[tuple[Item, ActionResult]]:
    """Update outdated extras. Scan every member first; stop on the first block.

    Extra themes share one `omarchy theme update`. Plugins update one by one.
    """
    targets = [item for item in items if item.can_update]
    if not targets:
        return []
    by_key = dict(scans or {})
    missing = [item for item in targets if item.key not in by_key]
    if missing:
        from omastore.scan import scan_item

        for item in missing:
            by_key[item.key] = scan_item(item)
    results: list[tuple[Item, ActionResult]] = []
    for item in targets:
        _, blocked = _scan_allows(by_key.get(item.key), item, accept_scan_risks=accept_scan_risks)
        if blocked is not None:
            results.append((item, blocked))
            return results
    themes = [item for item in targets if item.kind == "theme"]
    plugins = [item for item in targets if item.kind != "theme"]
    if themes:
        result = _run(["theme", "update"], dry_run=dry_run, timeout=180)
        for item in themes:
            results.append((item, result))
        if not result.ok:
            return results
    for item in plugins:
        result = update(
            item,
            dry_run=dry_run,
            scan_result=by_key.get(item.key),
            accept_scan_risks=accept_scan_risks,
        )
        results.append((item, result))
        if not result.ok:
            break
    return results


def remove(item: Item, *, dry_run: bool = False) -> ActionResult:
    operand = _operand(item.id, error="refused id")
    if isinstance(operand, ActionResult):
        return operand
    if item.kind == "theme":
        return _run(["theme", "remove", operand], dry_run=dry_run, timeout=180)
    if not dry_run:
        from omastore.local import restore_hidden_bar_widgets

        restore_hidden_bar_widgets(item.id)
    return _run(["plugin", "remove", operand, "--yes"], dry_run=dry_run, timeout=180)
