# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 ballban

import pathlib
import unittest

from lupa.lua54 import LuaRuntime


ROOT = pathlib.Path(__file__).resolve().parents[1]
LUA_DIRECTORY = ROOT / "rime" / "lua"


class HangulTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lua = LuaRuntime(unpack_returned_tuples=True)
        package = cls.lua.globals().package
        package.path = str(LUA_DIRECTORY / "?.lua") + ";" + package.path
        required = cls.lua.eval('require("ballban_hangul")')
        cls.hangul = required[0] if isinstance(required, tuple) else required

    def compose(self, keys):
        return self.hangul.compose(keys)

    def test_precomposed_words_are_complete(self):
        self.assertEqual(("한글", True), self.compose("gksrmf"))
        self.assertEqual(("안녕하세요", True), self.compose("dkssudgktpdy"))

    def test_csharp_composer_expectations(self):
        self.assertEqual(("안녀", True), self.compose("dkssu"))
        self.assertEqual(("값이", True), self.compose("rkqtdl"))
        self.assertEqual(("있다", True), self.compose("dlTek"))
        self.assertEqual(("광", True), self.compose("rhkd"))
        self.assertEqual(("안ㄴ", False), self.compose("dkss"))

    def test_syllable_and_lone_jamo_completion(self):
        self.assertEqual(("가", True), self.compose("rk"))
        self.assertEqual(("ㄱ", False), self.compose("r"))
        hangul, complete = self.compose("hi")
        self.assertEqual("ㅗㅑ", hangul)
        self.assertFalse(complete)

    def test_shifted_keys(self):
        self.assertEqual(("까", True), self.compose("Rk"))
        self.assertIsNone(self.compose("A"))

    def test_double_final_and_split_before_vowel(self):
        self.assertEqual(("읽", True), self.compose("dlfr"))
        self.assertEqual(("읽어", True), self.compose("dlfrdj"))

    def test_compound_vowel(self):
        self.assertEqual(("와", True), self.compose("dhk"))

    def test_invalid_and_empty_input(self):
        self.assertIsNone(self.compose(""))
        self.assertIsNone(self.compose("abc1"))

    def test_is_hangul_syllable(self):
        self.assertTrue(self.hangul.is_hangul_syllable("가"))
        self.assertTrue(self.hangul.is_hangul_syllable("힣"))
        self.assertFalse(self.hangul.is_hangul_syllable("ㄱ"))
        self.assertFalse(self.hangul.is_hangul_syllable("가나"))
        self.assertFalse(self.hangul.is_hangul_syllable("A"))


if __name__ == "__main__":
    unittest.main()
