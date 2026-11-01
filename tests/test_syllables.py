# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 ballban

import time
import unittest
from pathlib import Path

from lupa.lua54 import LuaRuntime


ROOT = Path(__file__).resolve().parents[1]
LUA_DIR = ROOT / "rime" / "lua"


class SyllableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lua = LuaRuntime(unpack_returned_tuples=True)
        lua_path = str(LUA_DIR).replace("\\", "/").replace('"', '\\"')
        cls.lua.execute(f'package.path = "{lua_path}/?.lua;" .. package.path')
        required = cls.lua.eval('require("ballban_syllables")')
        cls.module = required[0] if isinstance(required, tuple) else required

    def call(self, function_name, value, partial=None):
        if partial is None:
            ok, values = self.module[function_name](value)
        else:
            ok, values = self.module[function_name](value, partial)
        return bool(ok), [values[i] for i in range(1, len(values) + 1)]

    def assertPinyin(self, value, expected=True):
        ok, _ = self.call("pinyin", value)
        self.assertEqual(expected, ok, value)

    def assertRomaji(self, value, expected=True):
        ok, _ = self.call("romaji", value)
        self.assertEqual(expected, ok, value)

    def test_pinyin_valid(self):
        for value in (
            "nihao",
            "zhongguo",
            "xiawu",
            "xiaji",
            "shanghai",
            "lvse",
            "nve",
            "xi'an",
            "jiayou",
            "women",
            "zhuangtai",
        ):
            self.assertPinyin(value)

    def test_pinyin_invalid(self):
        for value in (
            "konnichiha",
            "gakkou",
            "tsukue",
            "gksrmf",
            "hello",
            "shinbun",
            "",
            "ni hao",
            "NIHAO",
        ):
            self.assertPinyin(value, False)

    def test_pinyin_aliases_and_split_preference(self):
        for value in ("lve", "lue", "nve", "nue"):
            self.assertPinyin(value)
        ok, syllables = self.call("pinyin", "xi'an")
        self.assertTrue(ok)
        self.assertEqual(["xi", "an"], syllables)
        ok, syllables = self.call("pinyin", "zhuangtai")
        self.assertTrue(ok)
        self.assertEqual(["zhuang", "tai"], syllables)

    def test_pinyin_partial(self):
        ok, syllables = self.call("pinyin", "zhongg", True)
        self.assertTrue(ok)
        self.assertEqual(["zhong", "g"], syllables)
        ok, syllables = self.call("pinyin", "x", True)
        self.assertTrue(ok)
        self.assertEqual(["x"], syllables)
        ok, syllables = self.call("pinyin", "ni'h", True)
        self.assertTrue(ok)
        self.assertEqual(["ni", "h"], syllables)
        ok, syllables = self.call("pinyin", "nihao", True)
        self.assertTrue(ok)
        self.assertEqual(["ni", "hao"], syllables)
        self.assertPinyin("zhongg", False)
        ok, _ = self.call("pinyin", "zhongv", True)
        self.assertFalse(ok)
        ok, _ = self.call("pinyin", "kq", True)
        self.assertFalse(ok)

    def test_romaji_valid(self):
        for value in (
            "konnichiha",
            "kyouhaiitenki",
            "gakkou",
            "shinbun",
            "tsukue",
            "matcha",
            "kitte",
            "nihongo",
            "ramen",
            "kon'nichiha",
            "sakura",
            "fairu",
            "ra-men",
        ):
            self.assertRomaji(value)

    def test_romaji_invalid(self):
        for value in ("zhongguo", "xiawu", "xiaji", "gksrmf", "hello", ""):
            self.assertRomaji(value, False)

    def test_romaji_n_and_sokuon_units(self):
        ok, units = self.call("romaji", "kon'nichiha")
        self.assertTrue(ok)
        self.assertEqual(["ko", "n'", "ni", "chi", "ha"], units)
        ok, units = self.call("romaji", "gakkou")
        self.assertTrue(ok)
        self.assertEqual(["ga", "k", "ko", "u"], units)
        ok, units = self.call("romaji", "ra-men")
        self.assertTrue(ok)
        self.assertEqual(["ra", "-", "me", "n"], units)

    def test_romaji_l_is_long_vowel_after_kana(self):
        ok, units = self.call("romaji", "kolhil")
        self.assertTrue(ok)
        self.assertEqual(["ko", "l", "hi", "l"], units)
        self.assertRomaji("ralmen")
        for value in ("lamen", "kl", "kkl", "sale", "kolla"):
            self.assertRomaji(value, False)

    def test_romaji_partial(self):
        ok, units = self.call("romaji", "kyouh", True)
        self.assertTrue(ok)
        self.assertEqual(["kyo", "u", "h"], units)
        ok, units = self.call("romaji", "ts", True)
        self.assertTrue(ok)
        self.assertEqual(["ts"], units)
        ok, units = self.call("romaji", "ky", True)
        self.assertTrue(ok)
        self.assertEqual(["ky"], units)
        ok, units = self.call("romaji", "kk", True)
        self.assertTrue(ok)
        self.assertEqual(["k", "k"], units)
        ok, units = self.call("romaji", "n", True)
        self.assertTrue(ok)
        self.assertEqual(["n"], units)
        ok, units = self.call("romaji", "konnichi", True)
        self.assertTrue(ok)
        self.assertEqual(["ko", "nn", "i", "chi"], units)
        self.assertRomaji("kyouh", False)
        ok, _ = self.call("romaji", "kq", True)
        self.assertFalse(ok)
        ok, _ = self.call("romaji", "hello", True)
        self.assertFalse(ok)

    def test_documented_ambiguities_are_valid_in_both(self):
        # These are deliberately lexical ambiguities: both splitters accept the letters.
        for value in ("yue", "baba", "egao", "fuyu", "buji", "ganshou"):
            self.assertPinyin(value)
            self.assertRomaji(value)

    def test_rejects_non_lowercase_and_bad_boundaries(self):
        for value in ("Nihao", "ni''hao", "'nihao", "nihao'", "n h"):
            self.assertPinyin(value, False)
        for value in ("Konnichiha", "n''", "n-", "xya", "ltu", "xtu"):
            self.assertRomaji(value, False)

    def test_40_letters_use_memoized_splits(self):
        pinyin_input = "zhongguo" * 5
        romaji_input = "konnichiha" * 4
        started = time.perf_counter()
        self.assertPinyin(pinyin_input)
        self.assertRomaji(romaji_input)
        self.assertLess(time.perf_counter() - started, 1.0)


if __name__ == "__main__":
    unittest.main()
