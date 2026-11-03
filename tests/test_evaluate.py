# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 ballban

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from evaluate import read_cases, score  # noqa: E402


class EvaluateTests(unittest.TestCase):
    def test_reads_required_columns_and_preserves_input_order(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "cases.tsv"
            path.write_text("id\texpected\tkeys_rime\n2\tb\txi'an\n1\ta\tra-men\n", encoding="utf-8")
            self.assertEqual(["2", "1"], [row["id"] for row in read_cases(path)])

    def test_rejects_empty_ambiguous_or_stateful_sets(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "cases.tsv"
            for body in ("", "id\texpected\n1\ta\n", "id\texpected\tkeys_rime\n",
                         "id\texpected\tkeys_rime\n1\ta\ta\n1\tb\tb\n",
                         "id\texpected\tkeys_rime\n1\t\ta\n",
                         "id\texpected\tkeys_rime\n1\ta\ta{space}\n"):
                with self.subTest(body=body):
                    path.write_text(body, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        read_cases(path)

    def test_separates_first_choice_top_five_and_character_accuracy(self):
        rime = Mock()
        rime.type.side_effect = [
            ("", [("cat", "")]),
            ("", [("cab", ""), ("cat", "")]),
            ("", []),
        ]
        result = score(rime, [{"id": str(i), "expected": "cat", "keys_rime": "cat"} for i in range(3)])
        self.assertAlmostEqual(1 / 3, result["exact"])
        self.assertAlmostEqual(2 / 3, result["top5"])
        self.assertAlmostEqual(5 / 9, result["char_accuracy"])
        self.assertEqual("", result["cases"][2]["top1"])


if __name__ == "__main__":
    unittest.main()
