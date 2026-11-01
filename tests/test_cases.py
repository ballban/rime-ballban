# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 ballban
"""Types every case of tests/cases.tsv into the built schema (build/rime) through librime.

Needs python tools/fetch_deps.py and python tools/build.py first. The first run compiles the dictionaries (about 20s).
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from rime_api import BUILD, Rime  # noqa: E402

PAGE = 5


def read_cases() -> list[tuple[int, str, str, str]]:
    cases = []
    lines = (ROOT / "tests" / "cases.tsv").read_text(encoding="utf-8").splitlines()
    for number, line in enumerate(lines, 1):
        if not line.strip() or line.startswith("#"):
            continue
        fields = line.split("\t")
        keys, expected = fields[0], fields[1]
        check = fields[2] if len(fields) > 2 else "first"
        if check not in ("first", "page", "commit", "gap"):
            raise ValueError(f"cases.tsv:{number}: unknown check {check!r}")
        cases.append((number, keys, expected, check))
    return cases


@unittest.skipUnless((BUILD / "ballban.schema.yaml").is_file(), "run python tools/build.py first")
class CaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # A separate user folder keeps what tools/try.py learned out of the results; forget makes runs repeatable.
        cls.rime = Rime(user=ROOT / "build" / "test-run", forget=True)

    @classmethod
    def tearDownClass(cls):
        cls.rime.close()

    def test_deploys_without_errors(self):
        self.assertEqual([], self.rime.errors())

    def test_cases(self):
        for number, keys, expected, check in read_cases():
            with self.subTest(line=number, keys=keys):
                if check == "commit":
                    self.assertEqual(expected, self.rime.commit(keys))
                    continue
                texts = [text for text, _ in self.rime.type(keys, PAGE)[1]]
                if check == "page":
                    self.assertIn(expected, texts)
                elif check == "gap":
                    self.assertNotEqual(expected, texts[0] if texts else None, "gap fixed: mark the case first")
                else:
                    self.assertEqual(expected, texts[0] if texts else None, f"first page: {texts}")


if __name__ == "__main__":
    unittest.main()
