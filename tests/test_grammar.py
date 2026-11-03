# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 ballban
"""Tests for the optional native quantizer; build it into build/tools first."""

import os
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "build" / "tools" / ("quantize_grammar.exe" if os.name == "nt" else "quantize_grammar")
HEADER = struct.Struct("<32sIII")


def fixture(path):
    # Independent three-key trie: a, ab, b. Two original scores share a quantized bin.
    units = [0] * 1280
    units[0] = 256 << 10
    for node, base, label, value in ((353, 512, 97, 300121), (610, 768, 98, 300249), (354, 1024, 98, 300751)):
        units[node] = ((node ^ base) << 10) | 256 | label
        units[base] = 0x80000000 | value
    path.write_bytes(HEADER.pack(b"Rime::Grammar/1.0", 0, len(units), 4) + struct.pack(f"<{len(units)}I", *units))


def lookup(path, key):
    data = path.read_bytes()
    _, _, count, offset = HEADER.unpack_from(data)
    units = struct.unpack_from(f"<{count}I", data, 40 + offset)
    node = 0
    for label in key:
        unit = units[node]
        node ^= ((unit >> 10) << ((unit & 512) >> 6)) ^ label
        if node >= len(units) or units[node] & 0x800000FF != label:
            return None
    unit = units[node]
    if not unit & 256:
        return None
    return units[node ^ ((unit >> 10) << ((unit & 512) >> 6))] & 0x7FFFFFFF


@unittest.skipUnless(TOOL.is_file(), "build tools/quantize_grammar.cc into build/tools first")
class GrammarTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.source = self.folder / "source.gram"
        fixture(self.source)

    def run_tool(self, output, step="0.05"):
        return subprocess.run(
            [str(TOOL), str(self.source), str(output), step],
            capture_output=True, text=True, timeout=30,
        )

    def test_rounding_preserves_prefix_and_complete_keys(self):
        output = self.folder / "rounded.gram"
        result = self.run_tool(output)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([300000, 300000, 301000], [lookup(output, key) for key in (b"a", b"ab", b"b")])
        self.assertIsNone(lookup(output, b"aa"))
        self.assertIsNone(lookup(output, b"abc"))
        self.assertIn("keys=3", result.stdout)
        self.assertIn("max_score_error=0.0249", result.stdout)
        self.assertFalse(output.with_suffix(".gram.tmp").exists())

    def test_native_precision_is_lossless(self):
        output = self.folder / "lossless.gram"
        result = self.run_tool(output, "0.0001")
        self.assertEqual(0, result.returncode, result.stderr)
        for key in (b"a", b"ab", b"b"):
            self.assertEqual(lookup(self.source, key), lookup(output, key))

    def test_invalid_steps_and_existing_output_do_not_write(self):
        output = self.folder / "output.gram"
        for step in ("0", "-1", "nan", "inf", "0.00015", "0.05extra"):
            with self.subTest(step=step):
                result = self.run_tool(output, step)
                self.assertNotEqual(0, result.returncode)
                self.assertFalse(output.exists())
        before = self.source.read_bytes()
        self.assertNotEqual(0, self.run_tool(self.source).returncode)
        self.assertEqual(before, self.source.read_bytes())

    def test_malformed_header_and_invalid_offsets_fail(self):
        valid = self.source.read_bytes()
        for position, replacement in ((0, b"NotRime!"), (40, struct.pack("<I", 8)), (44, struct.pack("<I", 4096 << 10))):
            with self.subTest(position=position):
                broken = bytearray(valid)
                broken[position:position + len(replacement)] = replacement
                self.source.write_bytes(broken)
                output = self.folder / "invalid.gram"
                result = self.run_tool(output)
                self.assertNotEqual(0, result.returncode)
                self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
