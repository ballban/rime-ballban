# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 ballban
"""Rewrite the weights of jaroomaji's dictionaries from models/jaroomaji-lm.tsv.gz.

jaroomaji ships Mozc costs, which rank single words but are not probabilities, so sentences built from them ignore how
likely the words are. The table holds ln P of every NFKC-normalised jaroomaji text that a Japanese word 3-gram model
(the one models/ballban.gram comes from) can score. An entry's weight becomes:

- ln P(text) plus a reading term, when the model knows the text. The model does not know readings, so Mozc's cost gap
  between a text's readings stands in for P(reading | text); readings Mozc lacks lose READING_PENALTY.
- Otherwise the Mozc cost moved onto the model's scale (by the median gap over texts both know), minus OOV_PENALTY.
- Otherwise a fixed value per dictionary.

Rime reads a weight W as ln(W) - ln(1e8). The grammar charges every word non_collocation_penalty (-13.8), which suits
rime-ice's weights; SHIFT moves Japanese words back to the -3 per word their weights were tuned with.
"""

import gzip
import math
import statistics
import unicodedata
from pathlib import Path

MOZC = "jaroomaji.mozc.dict.yaml"
FILES = [
    "jaroomaji.kana_kigou.dict.yaml",
    MOZC,
    "jaroomaji.jmdict.dict.yaml",
    "jaroomaji.kanjidic2.dict.yaml",
    "jaroomaji.mozcemoji.dict.yaml",
]
FIXED = {"jaroomaji.jmdict.dict.yaml": -24.0, "jaroomaji.kanjidic2.dict.yaml": -25.0,
         "jaroomaji.mozcemoji.dict.yaml": -26.0}
MOZC_TOP = 68318.0  # the highest Mozc weight in jaroomaji
MOZC_SCALE = 500.0  # Mozc cost units per nat
OOV_PENALTY = 3.0
READING_PENALTY = 4.0
FLOOR = -30.0
SHIFT = 13.815510557964274 - 3.0


def entries(path: Path):
    """Yields (line, fields); fields is None for the header, comments and entries without a weight."""
    body = False
    with path.open(encoding="utf-8") as source:
        for line in source:
            if not body:
                body = line.startswith("...")
                yield line, None
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) >= 3 and fields[2].strip() and not line.startswith("#"):
                yield line, fields
            else:
                yield line, None


def load_scores(path: Path) -> dict[str, float]:
    scores = {}
    with gzip.open(path, "rt", encoding="utf-8") as source:
        for line in source:
            text, score = line.rstrip("\n").split("\t")
            scores[text] = float(score)
    return scores


def reweight(folder: Path, table: Path) -> None:
    """Rewrites the jaroomaji dictionaries in folder in place."""
    lm = load_scores(table)
    mozc: dict[str, float] = {}
    mozc_reading: dict[tuple[str, str], float] = {}
    for _line, fields in entries(folder / MOZC):
        if fields:
            score = (float(fields[2]) - MOZC_TOP) / MOZC_SCALE
            mozc[fields[0]] = max(mozc.get(fields[0], -math.inf), score)
            key = (fields[0], fields[1])
            mozc_reading[key] = max(mozc_reading.get(key, -math.inf), score)

    norm: dict[str, str] = {}

    def normalize(text: str) -> str:
        if text not in norm:
            norm[text] = unicodedata.normalize("NFKC", text)
        return norm[text]

    shift = statistics.median(lm[normalize(t)] - s for t, s in mozc.items() if normalize(t) in lm)

    def score(text: str, code: str, name: str) -> float:
        if (text, code) in mozc_reading:
            reading = mozc_reading[(text, code)] - mozc[text]
        elif text in mozc:
            reading = -READING_PENALTY
        else:
            reading = 0.0
        if (n := normalize(text)) in lm:
            return max(FLOOR, lm[n] + reading)
        if text in mozc:
            return max(FLOOR, mozc[text] + shift - OOV_PENALTY + reading)
        return FIXED.get(name, FLOOR)

    for name in FILES:
        path = folder / name
        lines = []
        for line, fields in entries(path):
            if fields:
                # kana_kigou marks rarely wanted symbols with weight 0 or 1.
                if name == "jaroomaji.kana_kigou.dict.yaml" and fields[2].strip() in ("0", "1"):
                    value = FLOOR
                else:
                    value = score(fields[0], fields[1], name)
                fields[2] = f"{math.exp(value + SHIFT) * 1e8:.6g}"
                line = "\t".join(fields) + "\n"
            lines.append(line)
        with path.open("w", encoding="utf-8", newline="\n") as target:
            target.writelines(lines)
