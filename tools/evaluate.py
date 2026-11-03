#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 ballban
"""Evaluate TSV sets (id, expected, keys_rime) in an isolated, untrained Rime session.

    python tools/evaluate.py --set dev.tsv --set zh-dev.tsv --out build/scores.json
"""

import argparse
import csv
import hashlib
import json
import string
import tempfile
import time
from pathlib import Path

from rime_api import BUILD, ROOT, Rime, find_library


def read_cases(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if not {"id", "expected", "keys_rime"}.issubset(reader.fieldnames or []):
            raise ValueError(f"{path}: required columns are id, expected, keys_rime")
        rows = list(reader)
    if not rows:
        raise ValueError(f"{path}: no cases")
    seen = set()
    for number, row in enumerate(rows, 2):
        if not all(row.get(field) for field in ("id", "expected", "keys_rime")):
            raise ValueError(f"{path}:{number}: empty required field")
        if row["id"] in seen:
            raise ValueError(f"{path}:{number}: duplicate id {row['id']}")
        if any(char not in string.ascii_letters + "'-" for char in row["keys_rime"]):
            raise ValueError(f"{path}:{number}: keys_rime must contain letters, apostrophes or hyphens (no commits)")
        seen.add(row["id"])
    return rows


def edit_distance(actual: str, expected: str) -> int:
    previous = list(range(len(expected) + 1))
    for i, a in enumerate(actual, 1):
        current = [i]
        for j, b in enumerate(expected, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (a != b)))
        previous = current
    return previous[-1]


def score(rime: Rime, cases: list[dict[str, str]]) -> dict:
    rows = []
    elapsed = 0.0
    for case in cases:
        started = time.perf_counter()
        _, candidates = rime.type(case["keys_rime"], 5)
        elapsed += time.perf_counter() - started
        texts = [text for text, _ in candidates]
        actual = texts[0] if texts else ""
        rows.append({
            "id": case["id"], "expected": case["expected"], "keys": case["keys_rime"],
            "top1": actual, "top5": texts,
            "char_accuracy": max(0.0, 1 - edit_distance(actual, case["expected"]) / len(case["expected"])),
        })
    count = len(rows)
    return {
        "count": count,
        "exact": sum(row["top1"] == row["expected"] for row in rows) / count,
        "top5": sum(row["expected"] in row["top5"] for row in rows) / count,
        "char_accuracy": sum(row["char_accuracy"] for row in rows) / count,
        "ms_per_input": elapsed * 1000 / count,
        "cases": rows,
    }


def fingerprint(path: Path) -> dict:
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": digest}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--shared", type=Path, default=BUILD)
    parser.add_argument("--set", dest="sets", type=Path, action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("--out already exists; choose a new result file")
    if len({path.stem for path in args.sets}) != len(args.sets):
        parser.error("evaluation sets must have different file stems")
    inputs = [(path, read_cases(path)) for path in args.sets]
    result = {
        "library": fingerprint(find_library()),
        "models": [fingerprint(path) for path in sorted(args.shared.glob("*.gram"))],
        "sets": {},
    }
    work = ROOT / "build"
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="evaluate-", dir=work) as temporary:
        rime = Rime(shared=args.shared.resolve(), user=Path(temporary))
        try:
            if errors := rime.errors():
                raise RuntimeError("\n".join(errors))
            compiled = Path(temporary) / "build"
            result["compiled_inputs"] = [
                fingerprint(path) for path in sorted(compiled.iterdir())
                if path.suffix in (".yaml", ".bin")
            ]
            for path, cases in inputs:
                metrics = score(rime, cases)
                result["sets"][path.stem] = {"source": fingerprint(path), **metrics}
                print(f"{path.stem}: n={metrics['count']} exact={metrics['exact']:.2%} "
                      f"top5={metrics['top5']:.2%} char_acc={metrics['char_accuracy']:.2%} "
                      f"ms/input={metrics['ms_per_input']:.2f}", flush=True)
            if errors := rime.errors():
                raise RuntimeError("\n".join(errors))
        finally:
            rime.close()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
        output.write("\n")


if __name__ == "__main__":
    main()
