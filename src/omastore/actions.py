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


def install(item: Item, *, dry_run: bool = False) -> ActionResult:
    if not item.install_url:
        return ActionResult(False, [], "", f"{item.name} has no install URL")
    url = safe_cli_arg(item.install_url)
    if not url or not allowed_install_url(url):
        return ActionResult(False, [], "", "refused install url")
    if item.kind == "theme":
        return _run(["theme", "install", url], dry_run=dry_run, timeout=180)
    return _run(["plugin", "add", url, "--enable", "--yes"], dry_run=dry_run, timeout=180)


def apply_theme(item: Item, *, dry_run: bool = False) -> ActionResult:
    if item.kind != "theme":
        return ActionResult(False, [], "", "apply is for themes")
    operand = safe_cli_arg(item.name) or safe_cli_arg(item.id)
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
    return _run(["plugin", "disable", operand], dry_run=dry_run, timeout=30)


def update(item: Item, *, dry_run: bool = False) -> ActionResult:
    if item.kind == "theme":
        return _run(["theme", "update"], dry_run=dry_run, timeout=180)
    operand = _operand(item.id, error="refused plugin id")
    if isinstance(operand, ActionResult):
        return operand
    return _run(["plugin", "update", operand, "--yes"], dry_run=dry_run, timeout=180)


def remove(item: Item, *, dry_run: bool = False) -> ActionResult:
    operand = _operand(item.id, error="refused id")
    if isinstance(operand, ActionResult):
        return operand
    if item.kind == "theme":
        return _run(["theme", "remove", operand], dry_run=dry_run, timeout=180)
    return _run(["plugin", "remove", operand, "--yes"], dry_run=dry_run, timeout=180)
