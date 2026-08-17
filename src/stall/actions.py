from __future__ import annotations

from dataclasses import dataclass

from stall.local import run_omarchy
from stall.models import Item


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


def _run(args: list[str], *, dry_run: bool = False) -> ActionResult:
    if dry_run:
        return ActionResult(ok=True, command=args, stdout="dry-run: " + " ".join(args), stderr="")
    completed = run_omarchy(*args)
    return ActionResult(
        ok=completed.returncode == 0,
        command=["omarchy", *args],
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def install(item: Item, *, dry_run: bool = False) -> ActionResult:
    if not item.install_url:
        return ActionResult(False, [], "", f"{item.name} has no install URL")
    if item.kind == "theme":
        return _run(["theme", "install", item.install_url], dry_run=dry_run)
    return _run(["plugin", "add", item.install_url, "--enable", "--yes"], dry_run=dry_run)


def apply_theme(item: Item, *, dry_run: bool = False) -> ActionResult:
    return _run(["theme", "set", item.name], dry_run=dry_run)


def enable_plugin(item: Item, *, dry_run: bool = False) -> ActionResult:
    return _run(["plugin", "enable", item.id], dry_run=dry_run)


def disable_plugin(item: Item, *, dry_run: bool = False) -> ActionResult:
    return _run(["plugin", "disable", item.id], dry_run=dry_run)


def update(item: Item, *, dry_run: bool = False) -> ActionResult:
    if item.kind == "theme":
        return _run(["theme", "update"], dry_run=dry_run)
    return _run(["plugin", "update", item.id, "--yes"], dry_run=dry_run)


def remove(item: Item, *, dry_run: bool = False) -> ActionResult:
    if item.kind == "theme":
        return _run(["theme", "remove", item.id], dry_run=dry_run)
    return _run(["plugin", "remove", item.id, "--yes"], dry_run=dry_run)
