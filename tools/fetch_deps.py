#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 ballban
"""Download the pinned dependencies into deps/.

  deps/rime-ice        iDvel/rime-ice (GPL-3.0): Chinese pinyin and English schemas, dictionaries and Lua
  deps/rime-jaroomaji  lazyfoxchan/rime-jaroomaji (Apache-2.0): Japanese romaji schema and dictionaries
  deps/librime         librime release build (BSD-3-Clause) with librime-lua built in; only the tests use it

Git repositories are fetched at a fixed commit, which also verifies their content. The librime archive is
checked by SHA-256. Linux has no librime release build: install the distribution's librime with librime-lua
and point RIME_LIB at librime.so.1 instead.

    python tools/fetch_deps.py
"""

import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEPS = ROOT / "deps"

REPOS = {
    "rime-ice": ("https://github.com/iDvel/rime-ice", "99662ba01e3affa6a0f009174ca530b887bac3b6"),
    "rime-jaroomaji": ("https://github.com/lazyfoxchan/rime-jaroomaji", "b743307c0251f388976662ee2f9e267043785116"),
}

LIBRIME_TAG = "1.17.0"
LIBRIME_ASSETS = {
    "Windows": ("rime-33e7814-Windows-msvc-x64.7z", "7478c7caa4ff6b37de86daba1f7ce4a994a4f5ba24872a820fb2b3a9b01fed15"),
    "Darwin": ("rime-33e7814-macOS-universal.tar.bz2", "11d8dc663c6ec06d5ccb6111ba664a9e7b631b703ac6acd07cffbac664021850"),
}


def git(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def fetch_repo(name: str, url: str, commit: str) -> None:
    target = DEPS / name
    if (target / ".git").is_dir():
        if git("rev-parse", "HEAD", cwd=target) == commit:
            print(f"{name}: {commit[:7]} (up to date)")
            return
    else:
        target.mkdir(parents=True, exist_ok=True)
        git("init", "-q", cwd=target)
    # Rime reads the dictionaries line by line; keep the upstream LF endings whatever the global Git setting is.
    git("config", "core.autocrlf", "false", cwd=target)
    print(f"{name}: fetching {commit[:7]} from {url}")
    git("fetch", "-q", "--depth", "1", url, commit, cwd=target)
    git("checkout", "-q", "--force", "--detach", "FETCH_HEAD", cwd=target)
    git("clean", "-q", "-fdx", cwd=target)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch_librime() -> None:
    system = platform.system()
    if system not in LIBRIME_ASSETS:
        print(f"librime: no release build for {system}; set RIME_LIB to the system librime.so.1 to run the tests")
        return
    name, expected = LIBRIME_ASSETS[system]
    target = DEPS / "librime"
    stamp = target / ".asset"
    if stamp.is_file() and stamp.read_text(encoding="utf-8").strip() == name:
        print(f"librime: {LIBRIME_TAG} (up to date)")
        return

    downloads = DEPS / ".downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    archive = downloads / name
    if not archive.is_file() or sha256(archive) != expected:
        url = f"https://github.com/rime/librime/releases/download/{LIBRIME_TAG}/{name}"
        print(f"librime: downloading {url}")
        partial = archive.with_suffix(archive.suffix + ".part")
        urllib.request.urlretrieve(url, partial)
        actual = sha256(partial)
        if actual != expected:
            partial.unlink()
            sys.exit(f"librime: SHA-256 mismatch for {name} (expected {expected}, got {actual})")
        partial.replace(archive)

    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    if name.endswith(".7z"):
        # Windows' own tar (libarchive) reads .7z; Git's GNU tar, which may come first in PATH, cannot.
        tar = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "tar.exe"
        subprocess.run([str(tar), "-xf", str(archive), "-C", str(target)], check=True)
    else:
        with tarfile.open(archive) as bundle:
            bundle.extractall(target, filter="data")
    stamp.write_text(name + "\n", encoding="utf-8")
    print(f"librime: {LIBRIME_TAG} extracted to {target.relative_to(ROOT)}")


def main() -> None:
    for name, (url, commit) in REPOS.items():
        fetch_repo(name, url, commit)
    fetch_librime()


if __name__ == "__main__":
    main()
