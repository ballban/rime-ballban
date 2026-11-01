#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 ballban
"""Show what the ballban schema offers for typed keys, using librime directly (no frontend needed).

    python tools/try.py nihao konnichiha gksrmf
    python tools/try.py --fresh nihao      # drop the test user folder first (forces a full redeploy)
"""

import argparse
import shutil
import sys
import time

from rime_api import USER, Rime


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("keys", nargs="+", help="keys to type (librime key sequence syntax, e.g. nihao{space})")
    parser.add_argument("-n", type=int, default=10, help="candidates to show (default 10)")
    parser.add_argument("--fresh", action="store_true", help="start from an empty test user folder")
    parser.add_argument("--debug", action="store_true", help="show the language ballban_language gives each candidate")
    args = parser.parse_args()

    if args.fresh and USER.exists():
        shutil.rmtree(USER)
    USER.mkdir(parents=True, exist_ok=True)
    custom = USER / "ballban.custom.yaml"
    if args.debug:
        custom.write_text("patch:\n  ballban_language/debug: true\n", encoding="utf-8")
    else:
        custom.unlink(missing_ok=True)

    started = time.perf_counter()
    rime = Rime()
    print(f"deployed in {time.perf_counter() - started:.1f}s")
    for keys in args.keys:
        preedit, candidates = rime.type(keys, args.n)
        print(f"\n{keys}  [{preedit}]")
        for index, (text, comment) in enumerate(candidates, 1):
            print(f"  {index:2}. {text}" + (f"  {comment}" if comment else ""))
    errors = rime.errors()
    rime.close()
    if errors:
        print("\nlibrime errors:", *errors, sep="\n  ")
        sys.exit(1)


if __name__ == "__main__":
    main()
