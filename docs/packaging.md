# Packaging

omastore is a **client** for catalogs other people already built. It reads the public [limehawk](https://omarchytheme.com) theme catalog and the [HANCORE](https://omarchyplugins.com) plugin catalog, then runs the official `omarchy` commands those sites already document.

It is **not** official Omarchy, not a competing store, and not affiliated with Omarchy, 37signals, limehawk, or HANCORE.

Needs Python 3.12+ and the `omarchy` CLI.

## 1. Install from git (venv)

This is the development checkout:

```bash
git clone https://github.com/antunesales-dev/omastore.git
cd omastore
python3 -m venv .venv
.venv/bin/pip install -e .
ln -sf "$PWD/bin/omastore" ~/.local/bin/omastore
```

`pip install -e .` already pulls `textual` and `textual-image` from `pyproject.toml`. If you created the venv before those deps existed, install the screenshot renderer:

```bash
.venv/bin/pip install textual-image
```

Or run it from the repo without a symlink:

```bash
./bin/omastore
```

## 2. Install with the PKGBUILD (Arch / Omarchy)

The files under [`aur/`](../aur) build an AUR-style VCS package (`omastore-git`) from `git+https://github.com/antunesales-dev/omastore.git`. You do not need the package to be published on the AUR.

Depends: `python>=3.12`, `python-textual`, and `python-pillow` (all in extra). The TUI also needs `textual-image` for Sixel (Foot) / Kitty graphics (Ghostty) screenshots. That module is not in extra yet; pacman will not install the wheel's PyPI requires. Until it is packaged, install it from PyPI if `import textual_image` fails:

```bash
.venv/bin/pip install textual-image
```

There is an AUR package named `python-textual-image` you can use instead.

```bash
git clone https://github.com/antunesales-dev/omastore.git
cd omastore/aur
makepkg -si
```

`makepkg` clones the GitHub source, sets `pkgver` from that git history, builds a wheel, and installs it with `python -m installer`. Desktop and icon files ship inside the wheel (`omastore/share/…`); `omastore desktop` copies them into `~/.local/share`.

If these files are later uploaded to the AUR, the same package is:

```bash
yay -S omastore-git
```

## 3. Put it next to Omacalc

After either install, register the user launcher entry:

```bash
omastore desktop
```

That copies the desktop file and icon into `~/.local/share` so Omastore appears next to Omacalc / Omacut / Omawrite. Super + Space and type **Omastore**, or Super + Ctrl + O.
