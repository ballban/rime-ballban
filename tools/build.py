#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 ballban
"""Assemble build/rime: a complete Rime user folder made of rime-ice, rime-jaroomaji and this repository's rime/.

Copy the contents of build/rime into a Rime frontend's user folder (Weasel: %APPDATA%\\Rime, Squirrel: ~/Library/Rime,
fcitx5-rime: ~/.local/share/fcitx5/rime, Trime: /sdcard/rime) and deploy.

    python tools/fetch_deps.py   # once, or after changing a pin
    python tools/build.py
"""

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEPS = ROOT / "deps"
OUT = ROOT / "build" / "rime"

# Repository files of rime-ice that are not Rime data.
RIME_ICE_SKIP = {".git", ".github", ".gitignore", "AGENTS.md", "README.md", "LICENSE", "build", "others", "recipe.yaml"}


def copy_tree(source: Path, target: Path, skip: set[str] = frozenset(), owner: dict[Path, str] | None = None, name: str = "") -> None:
    for item in sorted(source.iterdir()):
        if item.name in skip:
            continue
        destination = target / item.name
        if item.is_dir():
            destination.mkdir(exist_ok=True)
            copy_tree(item, destination, owner=owner, name=name)
            continue
        relative = destination.relative_to(OUT)
        if owner is not None:
            if relative in owner:
                sys.exit(f"{relative} comes from both {owner[relative]} and {name}; rename one of them")
            owner[relative] = name
        # copy, not copy2: Rime redeploys only sources newer than its last build, so the copies must be new.
        shutil.copy(item, destination)


def main() -> None:
    for name in ("rime-ice", "rime-jaroomaji"):
        if not (DEPS / name / ".git").is_dir():
            sys.exit(f"deps/{name} is missing; run python tools/fetch_deps.py first")
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    owner: dict[Path, str] = {}
    copy_tree(DEPS / "rime-ice", OUT, RIME_ICE_SKIP, owner, "rime-ice")
    jaroomaji = DEPS / "rime-jaroomaji"
    for item in sorted(jaroomaji.glob("*.yaml")):
        relative = Path(item.name)
        if relative in owner:
            sys.exit(f"{relative} comes from both {owner[relative]} and rime-jaroomaji")
        owner[relative] = "rime-jaroomaji"
        shutil.copy(item, OUT / item.name)
    copy_tree(ROOT / "rime", OUT, owner=owner, name="rime-ballban")

    licenses = OUT / "licenses"
    licenses.mkdir()
    shutil.copy(DEPS / "rime-ice" / "LICENSE", licenses / "rime-ice.txt")
    shutil.copy(jaroomaji / "LICENSE", licenses / "rime-jaroomaji.txt")
    shutil.copy(ROOT / "LICENSE", licenses / "rime-ballban.txt")
    print(f"built {OUT.relative_to(ROOT)} ({sum(1 for p in OUT.rglob('*') if p.is_file())} files)")


if __name__ == "__main__":
    main()
