from __future__ import annotations

from dataclasses import dataclass

from omastore.models import Item

PACK_LIMIT = 8
PACK_CREDIT = (
    "Hand-picked from the HANCORE catalog. Verified only. "
    "You still install with the official omarchy commands."
)


def _verified_plugin(item: Item) -> bool:
    return (
        item.kind == "plugin"
        and not item.first_party
        and not item.builtin
        and item.verification_label == "verified"
    )


@dataclass(frozen=True)
class Pack:
    id: str
    title: str
    blurb: str
    pins: tuple[str, ...] = ()

    def members(self, items: list[Item], *, limit: int = PACK_LIMIT) -> list[Item]:
        verified = {item.id: item for item in items if _verified_plugin(item)}
        picked: list[Item] = []
        seen: set[str] = set()
        for pin in self.pins:
            if len(picked) >= limit:
                break
            item = verified.get(pin)
            if item is None or item.id in seen:
                continue
            picked.append(item)
            seen.add(item.id)
        return picked

    def pending(self, items: list[Item]) -> list[Item]:
        return [item for item in self.members(items) if item.can_install]

    def removable(self, items: list[Item]) -> list[Item]:
        return [item for item in self.members(items) if item.can_remove]

    def counts(self, items: list[Item]) -> tuple[int, int]:
        members = self.members(items)
        return len(members), sum(1 for item in members if item.can_install)

    def listed(self, items: list[Item]) -> list[Item]:
        """Members with installed rows first, for display."""
        return sorted(self.members(items), key=lambda item: (0 if item.installed else 1))


PACKS: tuple[Pack, ...] = (
    Pack(
        id="everyday",
        title="Everyday",
        blurb="The desktop basics: overview, displays, workspaces, clipboard, dock, tasks, calendar, 2FA.",
        pins=(
            "omarchy-overview",
            "better.displays",
            "io.github.thetrueferret.decent-workspaces",
            "io.github.vuhuy.clipboard-manager",
            "omadock",
            "io.github.aryan-techie.todoist",
            "tobiasz-p.next-event",
            "io.github.sasirulk.totp",
        ),
    ),
    Pack(
        id="developer",
        title="Developer",
        blurb="Git, review queues, Jira, Docker, and the AI coding widgets that actually belong together.",
        pins=(
            "dev.git",
            "syntaxboybe.git-switcher",
            "tmn73.jira",
            "io.github.this-is-npc.dockmarchy",
            "local.opencode-go",
            "tsouth89.omcp",
            "slcode777.omaconv",
            "io.github.chris.secret-canary",
        ),
    ),
    Pack(
        id="finance",
        title="Finance",
        blurb="Stocks, FX, portfolio, and crypto tickers — not wallpaper or plugin-marketplace stats.",
        pins=(
            "io.github.5d0tal1gat0r.stocks",
            "stappmus.stochi",
            "io.github.promaaa.omamoney",
            "io.github.simasrazinskas.trading212",
            "io.github.guettoblasterr.crypto-market-pulse",
            "gpatkinson.btc-price",
        ),
    ),
    Pack(
        id="designer",
        title="Designer",
        blurb="Wallpapers, day/night theme, opacity, color sampling, and CRT look. Not workspace widgets.",
        pins=(
            "dizziee.auto-wallpaper",
            "wolfgangrittner.omarchy-wallpapers",
            "io.github.smillunchick.aether-wallpapers",
            "mehiel.darky",
            "omarchy-window-opacity",
            "angus.caliper",
            "io.github.ejuro.phosphor",
        ),
    ),
    Pack(
        id="music",
        title="Music",
        blurb="Listen, see what's playing, visualize it, and play along — one of each, not five now-playing clones.",
        pins=(
            "levi.youtube-music",
            "andreasbylund.jellyfin",
            "io.github.bscott.cliamp",
            "io.github.sumdahl.media",
            "my.cava",
            "turner-ps.chillhop",
            "crmne.ultimate-guitar",
            "dlpwaters.metronome",
        ),
    ),
    Pack(
        id="artist",
        title="Artist",
        blurb="Draw on the screen, sample color, CRT look, Unsplash photos, and click highlights for recordings.",
        pins=(
            "io.github.taha.draw-it",
            "angus.caliper",
            "io.github.ejuro.phosphor",
            "wolfgangrittner.omarchy-wallpapers",
            "melonamin.flare",
            "nosignal.quattro4x4",
        ),
    ),
    Pack(
        id="gamer",
        title="Gamer",
        blurb="Steam friends, solitaire, minesweeper, snake, truco, esports. Not YouTube Music.",
        pins=(
            "nosignal.quattrolitaire",
            "io.github.daventhedude.steam-friends",
            "sebasgl23.minesweeper",
            "sebasgl23.snake",
            "omatruco",
            "contra.esports",
            "mka.asusrgb",
        ),
    ),
)


def get_pack(pack_id: str) -> Pack | None:
    needle = (pack_id or "").strip().lower()
    for pack in PACKS:
        if pack.id == needle:
            return pack
    return None


def pack_matches(pack: Pack, text: str, items: list[Item] | None = None) -> bool:
    needle = (text or "").strip().lower()
    if not needle:
        return True
    hay = f"{pack.id} {pack.title} {pack.blurb}"
    if items:
        for item in pack.members(items):
            hay += f" {item.name} {item.id}"
    lowered = hay.lower()
    return all(token in lowered for token in needle.split())


def pack_member_state(item: Item) -> str:
    if item.installed:
        if item.kind == "plugin":
            power = "on" if item.enabled else "off"
            return f"● installed · {power}"
        return "● installed"
    return "○ to install"


def pack_markdown(pack: Pack, items: list[Item]) -> str:
    members = pack.listed(items)
    bits = [pack.blurb, "", PACK_CREDIT, ""]
    if not members:
        bits.append("_No verified plugins from this pack are in the current catalog._")
        return "\n".join(bits)
    for item in members:
        stars = f" · *{item.stars}" if item.stars else ""
        bits.append(f"- {pack_member_state(item)}  **{item.name}**{stars}")
        loc = item.repo or item.install_url
        if loc:
            bits.append(f"  `{loc}`")
    return "\n".join(bits)


def describe_pack_action(action: str, pack: Pack, rows: list[Item]) -> str:
    n = len(rows)
    noun = "plugin" if n == 1 else "plugins"
    lines = [f"{action} {n} {noun} from {pack.title}?", PACK_CREDIT]
    if action == "remove":
        lines.append("This removes each listed plugin with omarchy plugin remove.")
        lines.append("A plugin that is also in another pack is still removed.")
    for item in rows:
        lines.append("")
        lines.append(f"{item.kind}:{item.id}")
        lines.append(f'plugin “{item.name}”')
        loc = item.repo or item.install_url
        if loc:
            lines.append(str(loc))
        if item.verification_label:
            lines.append(f"verification: {item.verification_label}")
        for warning in item.warnings:
            lines.append(f"- {warning}")
        if action == "remove" and item.kind == "plugin":
            from omastore.local import layout_remove_warnings

            for warning in layout_remove_warnings(item.id):
                lines.append(f"- {warning}")
    lines.append("")
    if action == "install":
        lines.append("Community plugins and themes run unsandboxed.")
    lines.append("This uses the official omarchy command.")
    return "\n".join(lines)


def describe_pack_install(pack: Pack, pending: list[Item]) -> str:
    return describe_pack_action("install", pack, pending)


def describe_pack_remove(pack: Pack, rows: list[Item]) -> str:
    return describe_pack_action("remove", pack, rows)
