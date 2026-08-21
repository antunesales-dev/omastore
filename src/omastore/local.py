from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from omastore.models import Item, slugify
from omastore.safety import contained_child, theme_aliases


def _home() -> Path:
    return Path.home()


def user_themes_dir() -> Path:
    return _home() / ".config" / "omarchy" / "themes"


def user_plugins_dir() -> Path:
    return _home() / ".config" / "omarchy" / "plugins"


def shell_json_path() -> Path:
    root = os.environ.get("XDG_CONFIG_HOME")
    if root:
        return Path(root) / "omarchy" / "shell.json"
    return _home() / ".config" / "omarchy" / "shell.json"


def _layout_entry_id(entry: object) -> str:
    if isinstance(entry, str):
        return entry.strip()
    if isinstance(entry, dict):
        return str(entry.get("id") or "").strip()
    return ""


def _hidden_ids(entry: object) -> list[str]:
    if not isinstance(entry, dict):
        return []
    hidden = entry.get("hiddenEntries")
    if not isinstance(hidden, list):
        return []
    ids: list[str] = []
    seen: set[str] = set()
    for row in hidden:
        ident = _layout_entry_id(row)
        if not ident or ident in seen:
            continue
        seen.add(ident)
        ids.append(ident)
    return ids


def _read_shell_json(path: Path | None = None) -> dict | None:
    target = path or shell_json_path()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _walk_hidden(raw: dict, plugin_id: str | None = None) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    def add(owner: str, hid: str) -> None:
        if not owner or not hid:
            return
        rows = out.setdefault(owner, [])
        if hid not in rows:
            rows.append(hid)

    layout = raw.get("bar")
    sections = layout.get("layout") if isinstance(layout, dict) else None
    bags: list[object] = []
    if isinstance(sections, dict):
        bags.extend(sections.values())
    plugins = raw.get("plugins")
    if isinstance(plugins, list):
        bags.append(plugins)
    for rows in bags:
        if not isinstance(rows, list):
            continue
        for entry in rows:
            owner = _layout_entry_id(entry)
            if plugin_id is not None and owner != plugin_id:
                continue
            for hid in _hidden_ids(entry):
                add(owner, hid)
    return out


def hidden_bar_widgets(plugin_id: str, *, path: Path | None = None, data: dict | None = None) -> list[str]:
    """Read-only: widget ids stashed in this plugin's hiddenEntries. Never writes."""
    ident = (plugin_id or "").strip()
    if not ident:
        return []
    raw = data if isinstance(data, dict) else _read_shell_json(path)
    if not raw:
        return []
    return _walk_hidden(raw, ident).get(ident, [])


def hidden_entries_by_plugin(*, path: Path | None = None, data: dict | None = None) -> dict[str, list[str]]:
    """Read-only map of plugin id -> hiddenEntries widget ids. Never writes."""
    raw = data if isinstance(data, dict) else _read_shell_json(path)
    if not raw:
        return {}
    return _walk_hidden(raw)


HIDDEN_WIDGET_WARN = (
    "These widgets are hidden inside this plugin. "
    "They will be put back on the bar first"
)
_HIDDEN_LIST_CAP = 12


def layout_remove_warnings(plugin_id: str, *, path: Path | None = None) -> list[str]:
    hidden = hidden_bar_widgets(plugin_id, path=path)
    if not hidden:
        return []
    shown = hidden[:_HIDDEN_LIST_CAP]
    listing = ", ".join(shown)
    extra = len(hidden) - len(shown)
    if extra:
        listing += f", and {extra} more"
    return [f"{HIDDEN_WIDGET_WARN}: {listing}"]


def _as_layout_entry(row: object) -> dict | None:
    ident = _layout_entry_id(row)
    if not ident:
        return None
    if isinstance(row, dict):
        return dict(row)
    return {"id": ident}


def _ids_in_layout(sections: dict) -> set[str]:
    ids: set[str] = set()
    for rows in sections.values():
        if not isinstance(rows, list):
            continue
        for entry in rows:
            ident = _layout_entry_id(entry)
            if ident:
                ids.add(ident)
    return ids


def _write_shell_json(path: Path, data: dict) -> bool:
    tmp = path.with_name(path.name + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
        return True
    except OSError:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def _take_hidden_rows(entry: dict, plugin_id: str, present: set[str]) -> list[dict]:
    hidden = entry.get("hiddenEntries")
    if not isinstance(hidden, list) or not hidden:
        return []
    rows: list[dict] = []
    for row in hidden:
        obj = _as_layout_entry(row)
        if obj is None:
            continue
        hid = _layout_entry_id(obj)
        if hid == plugin_id or hid in present:
            continue
        present.add(hid)
        rows.append(obj)
    return rows


def restore_hidden_bar_widgets(plugin_id: str, *, path: Path | None = None) -> list[str]:
    """Move hiddenEntries back onto the bar section, then clear them. Returns restored ids."""
    ident = (plugin_id or "").strip()
    if not ident:
        return []
    target = path or shell_json_path()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return []
    if not isinstance(raw, dict):
        return []
    bar = raw.get("bar")
    if not isinstance(bar, dict):
        return []
    sections = bar.get("layout")
    if not isinstance(sections, dict):
        return []
    present = _ids_in_layout(sections)
    restored: list[str] = []
    changed = False
    for section_name, rows in list(sections.items()):
        if not isinstance(rows, list):
            continue
        new_rows: list[object] = []
        section_changed = False
        for entry in rows:
            if _layout_entry_id(entry) != ident or not isinstance(entry, dict):
                new_rows.append(entry)
                continue
            taken = _take_hidden_rows(entry, ident, present)
            entry = dict(entry)
            if "hiddenEntries" in entry:
                entry.pop("hiddenEntries", None)
                section_changed = True
            new_rows.append(entry)
            if taken:
                new_rows.extend(taken)
                restored.extend(_layout_entry_id(row) for row in taken)
                section_changed = True
        if section_changed:
            sections[section_name] = new_rows
            changed = True
    plugins = raw.get("plugins")
    if isinstance(plugins, list):
        right = sections.get("right")
        if not isinstance(right, list):
            right = []
        plugin_changed = False
        new_plugins: list[object] = []
        extra_right: list[dict] = []
        for entry in plugins:
            if _layout_entry_id(entry) != ident or not isinstance(entry, dict):
                new_plugins.append(entry)
                continue
            taken = _take_hidden_rows(entry, ident, present)
            entry = dict(entry)
            if "hiddenEntries" in entry:
                entry.pop("hiddenEntries", None)
                plugin_changed = True
            new_plugins.append(entry)
            extra_right.extend(taken)
            restored.extend(_layout_entry_id(row) for row in taken)
        if plugin_changed or extra_right:
            raw["plugins"] = new_plugins
            sections["right"] = [*right, *extra_right]
            changed = True
    if not changed:
        return []
    if not _write_shell_json(target, raw):
        return []
    return restored


def stock_themes_dir() -> Path:
    omarchy = os.environ.get("OMARCHY_PATH", "/usr/share/omarchy")
    return Path(omarchy) / "themes"


def _git_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def git_head(path: Path) -> str:
    try:
        if not path.exists():
            return ""
        completed = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            check=False,
            text=True,
            capture_output=True,
            timeout=10,
            env=_git_env(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def _existing_child(root: Path, name: str) -> Path | None:
    if not name:
        return None
    direct = contained_child(root, name)
    if direct is not None and (direct.is_dir() or direct.is_symlink()):
        return direct
    if not root.is_dir():
        return None
    needle = name.lower()
    for entry in root.iterdir():
        child = contained_child(root, entry.name)
        if child is None:
            continue
        if entry.name.lower() == needle and (entry.is_dir() or entry.is_symlink()):
            return child
    return None


def installed_theme_path(slug: str) -> Path | None:
    return _existing_child(user_themes_dir(), slug)


def installed_plugin_path(plugin_id: str) -> Path | None:
    return _existing_child(user_plugins_dir(), plugin_id)


_PREVIEW_NAMES = ("preview.png", "preview.webp", "preview.jpg", "preview.jpeg")


def _preview_in(folder: Path | None) -> Path | None:
    if folder is None or not folder.is_dir():
        return None
    for name in _PREVIEW_NAMES:
        path = folder / name
        if path.is_file():
            return path
    return None


def theme_preview_file(slug: str) -> Path | None:
    """User theme preview first, then the stock Omarchy copy."""
    found = _preview_in(installed_theme_path(slug))
    if found:
        return found
    return _preview_in(_existing_child(stock_themes_dir(), slug))


def plugin_preview_file(plugin_id: str) -> Path | None:
    return _preview_in(installed_plugin_path(plugin_id))


def run_omarchy(*args: str, check: bool = False, timeout: float = 30) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["omarchy", *args],
            check=check,
            text=True,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        raise
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(["omarchy", *args], 1, "", "omarchy timed out")


@dataclass
class LocalState:
    current_theme: str = ""
    current_slug: str = ""
    theme_names: dict[str, str] = field(default_factory=dict)  # slug -> display
    extra_slugs: set[str] = field(default_factory=set)
    stock_slugs: set[str] = field(default_factory=set)
    plugins: dict[str, dict] = field(default_factory=dict)
    omarchy_ok: bool = True
    error: str = ""

    def theme_display(self, slug: str) -> str:
        return self.theme_names.get(slug, slug)


def _dir_slugs(path: Path) -> set[str]:
    if not path.is_dir():
        return set()
    slugs: set[str] = set()
    for entry in path.iterdir():
        if not (entry.is_dir() or entry.is_symlink()):
            continue
        if contained_child(path, entry.name) is None:
            continue
        slugs.add(entry.name.lower())
        slugs.add(slugify(entry.name))
    return slugs


def load_local() -> LocalState:
    state = LocalState()
    state.extra_slugs = _dir_slugs(user_themes_dir())
    state.stock_slugs = _dir_slugs(stock_themes_dir())

    try:
        listed = run_omarchy("theme", "list")
        current = run_omarchy("theme", "current")
        plugins = run_omarchy("plugin", "list", "--json")
    except FileNotFoundError:
        state.omarchy_ok = False
        state.error = "omarchy CLI not found on PATH"
        return state

    if listed.returncode == 0:
        for line in listed.stdout.splitlines():
            name = line.strip()
            if name:
                state.theme_names[slugify(name)] = name
    if current.returncode == 0:
        state.current_theme = current.stdout.strip()
        state.current_slug = slugify(state.current_theme)
    if plugins.returncode == 0 and plugins.stdout.strip():
        try:
            rows = json.loads(plugins.stdout)
        except json.JSONDecodeError:
            rows = []
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict) and row.get("id"):
                    state.plugins[str(row["id"])] = row
    elif plugins.returncode != 0:
        state.error = plugins.stderr.strip() or "could not list plugins"
    return state


def overlay(items: list[Item], local: LocalState) -> list[Item]:
    known_theme_slugs: set[str] = set()
    known_plugin_ids = {item.id for item in items if item.kind == "plugin"}
    local_slugs = set(local.theme_names) | local.extra_slugs | local.stock_slugs
    result: list[Item] = []

    for item in items:
        if item.kind == "theme":
            aliases = theme_aliases(item)
            known_theme_slugs.update(aliases)
            if item.id:
                known_theme_slugs.add(item.id)
            item.installed = bool(aliases & local_slugs)
            item.current = local.current_slug in aliases
            item.extra = bool(aliases & local.extra_slugs)
            item.builtin = item.builtin or (bool(aliases & local.stock_slugs) and not item.extra)
        else:
            row = local.plugins.get(item.id)
            if row:
                item.installed = True
                item.enabled = bool(row.get("enabled"))
                item.first_party = bool(row.get("firstParty")) or item.first_party
        result.append(item)

    for slug, name in local.theme_names.items():
        if slug in known_theme_slugs or slugify(slug) in known_theme_slugs:
            continue
        known_theme_slugs.add(slug)
        if slugify(slug):
            known_theme_slugs.add(slugify(slug))
        result.append(
            Item(
                kind="theme",
                id=slug,
                name=name,
                installed=True,
                current=slug == local.current_slug,
                extra=slug in local.extra_slugs,
                builtin=slug in local.stock_slugs and slug not in local.extra_slugs,
                local_only=True,
                description="Installed locally. Not listed in the community catalog.",
            )
        )
    for slug in local.extra_slugs | local.stock_slugs:
        if slug in known_theme_slugs or slugify(slug) in known_theme_slugs or slug in local.theme_names:
            continue
        known_theme_slugs.add(slug)
        if slugify(slug):
            known_theme_slugs.add(slugify(slug))
        result.append(
            Item(
                kind="theme",
                id=slug,
                name=slug,
                installed=True,
                current=slug == local.current_slug,
                extra=slug in local.extra_slugs,
                builtin=slug in local.stock_slugs and slug not in local.extra_slugs,
                local_only=True,
                description="Installed locally. Not listed in the community catalog.",
            )
        )
    for plugin_id, row in local.plugins.items():
        if plugin_id in known_plugin_ids:
            continue
        result.append(
            Item(
                kind="plugin",
                id=plugin_id,
                name=str(row.get("name") or plugin_id),
                installed=True,
                enabled=bool(row.get("enabled")),
                first_party=bool(row.get("firstParty")),
                builtin=bool(row.get("firstParty")),
                local_only=True,
                tags=list(row.get("kinds") or []),
                description="Installed locally. Not listed in the community catalog.",
            )
        )
    return result
