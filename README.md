# rime-ballban

A [Rime](https://rime.im) schema for typing Chinese, Japanese, Korean and English from the same Latin keys,
without switching input modes.

| Keys            | First candidate | How it is read          |
| --------------- | --------------- | ----------------------- |
| `nihao`         | 你好            | Chinese pinyin          |
| `zhongguo`      | 中国            | Chinese pinyin          |
| `konnnichiha`   | こんにちは      | Japanese romaji         |
| `gakkou`        | 学校            | Japanese romaji         |
| `kolhil`        | コーヒー        | Japanese romaji         |
| `gksrmf`        | 한글            | Korean Dubeolsik layout |
| `dkssudgktpdy`  | 안녕하세요      | Korean Dubeolsik layout |
| `google`        | Google          | English                 |

The other languages' readings stay in the candidate list, so a wrong first guess costs a few keystrokes, not a mode
switch.

This repository holds only configuration and Lua. The engine and dictionaries come from other projects, pinned to fixed
commits and assembled at build time; nothing is forked:

- [librime](https://github.com/rime/librime) runs on every platform through its frontends.
- [rime-ice](https://github.com/iDvel/rime-ice) provides Chinese pinyin, English and most of the schema. `ballban` includes
  `rime_ice.schema` as it is.
- [rime-jaroomaji](https://github.com/lazyfoxchan/rime-jaroomaji) provides Japanese romaji and its dictionaries. `ballban`
  mounts it as an extra translator.
- Korean is composed by `rime/lua/ballban_hangul.lua` and needs no dictionary.

## Layout

| Path                            | Contents                                                                    |
| ------------------------------- | --------------------------------------------------------------------------- |
| `rime/ballban.schema.yaml`      | The schema: rime-ice plus the Japanese translator and the language filter   |
| `rime/default.custom.yaml`      | Schema list: `ballban`, then plain `rime_ice` and `jaroomaji`               |
| `rime/lua/ballban_language.lua` | Filter that decides which language goes first and adds the Korean candidate |
| `rime/lua/ballban_syllables.lua`| Checks whether keys spell pinyin or Japanese romaji                         |
| `rime/lua/ballban_hangul.lua`   | Dubeolsik keys to Hangul                                                    |
| `tools/fetch_deps.py`           | Downloads the pinned dependencies into `deps/`                              |
| `tools/build.py`                | Assembles a complete Rime user folder in `build/rime/`                      |
| `tools/try.py`                  | Prints the candidates for typed keys through librime, without a frontend    |
| `tools/rime_api.py`             | Small ctypes binding to librime used by `try.py` and the tests              |
| `tests/`                        | Lua unit tests and end-to-end cases (`tests/cases.tsv`)                     |

## Build

Requires Python 3.12 or later and Git.

```sh
python -m venv .venv
.venv/bin/pip install lupa          # Windows: .venv\Scripts\pip install lupa
python tools/fetch_deps.py          # once, and again after changing a pin
python tools/build.py               # writes build/rime/
```

`fetch_deps.py` also downloads the librime 1.17.0 release build for Windows or macOS into `deps/librime`. Only `try.py`
and the tests use it. On Linux, install your distribution's librime with librime-lua and set `RIME_LIB` to `librime.so.1`.

## Try and test

```sh
python tools/try.py nihao konnnichiha gksrmf    # candidates for each input
python tools/try.py --debug kani                # tags every candidate [zh] / [ja] / [ko] / [en]
python tools/try.py "nihao{space}"              # librime key syntax: {space}, {Return}, {Shift+a}
.venv/bin/python -m unittest discover -s tests -p "test_*.py"
```

The first run compiles the dictionaries, which takes about 20 seconds; later runs reuse them. `try.py` deploys into
`build/test-user/` and the tests into `build/test-run/`, so neither touches your real Rime folder.

`tests/cases.tsv` lists the expected results. Add a line when you fix or notice a case. The `gap` check records a known
miss; that test fails once the miss is fixed, so the line can become a normal check.

## Install

The frontend must support librime-lua, which rime-ice needs anyway.

1. Run `python tools/build.py`.
2. Back up the frontend's user folder, then copy the contents of `build/rime/` into it. This overwrites files of the same
   name, including `default.custom.yaml`.
   - Weasel (Windows): `%APPDATA%\Rime`
   - Squirrel (macOS): `~/Library/Rime`
   - fcitx5-rime (Linux): `~/.local/share/fcitx5/rime`
   - ibus-rime (Linux): `~/.config/ibus/rime`
   - Trime (Android): `/sdcard/rime`
3. Deploy from the frontend and select **Ballban CJK**.

So far the schema has been tested only through librime 1.17.0 directly, not inside any frontend.

## Customize

Put changes in `ballban.custom.yaml` in the user folder, not in the copied files:

```yaml
patch:
  ballban_language/debug: true   # show [zh] / [ja] / [ko] / [en] after each candidate
  menu/page_size: 7
```

## Typing

- **Chinese**: full pinyin, as in rime-ice. rime-ice's other features, such as `v` symbols, still work.
- **Japanese**: romaji with jaroomaji's rules, which follow Mozc.
  - `nn` is ん, so こんにちは is `konnnichiha`; `konnichiha` reads こんいちは.
  - `l` after a vowel is ー (`kolhil` → コーヒー). rime-ice uses `-` for paging, so `-` cannot type ー here.
- **Korean**: the Dubeolsik layout on a QWERTY keyboard. Use Shift for the tense consonants and the ㅒ/ㅖ vowels
  (`Rk` → 까).
- **English**: words from rime-ice's `melt_eng` dictionary.

## How the language is chosen

Rime's translators all produce candidates for the same keys. `ballban_language.lua` then reorders them:

1. It checks which languages the keys could spell:
   - **Chinese**: the keys split into pinyin syllables.
   - **Japanese**: the keys split into romaji syllables.
   - **Korean**: the keys compose whole Hangul syllables, optionally followed by one unfinished consonant.
   - **English**: rime-ice offers an English word that covers all the keys.

   Pinyin and romaji may also end with an unfinished syllable.
2. Korean goes first when the keys make whole Hangul syllables and spell neither complete pinyin nor complete romaji.
   Otherwise, the first candidate that covers all the keys and belongs to a possible language goes first. Between
   possible languages, Rime's own ranking decides.
3. The other candidates of possible languages follow in Rime's order. Candidates of languages the keys cannot spell
   come last.
4. A Korean reading that is not first stays on the first page.

## Known limitations

- Keys that are valid pinyin and valid romaji (`hashi`, `kani`, `sushi`) follow Rime's ranking, which puts Chinese
  first. Choosing a Japanese candidate does not change that: Rime learns the choice inside the Japanese dictionary,
  but the language order is not learned yet.
- Japanese sentence quality is jaroomaji's. For example, `kyouha` gives 教派 before 今日は even in jaroomaji alone.
- A single input is read as one language; mixed sentences such as 今日はgoogle are not split.
- jaroomaji's dictionaries are large (85 MB of source, 67 MB compiled), which may matter on phones.
- Frontends other than librime itself are untested. iOS frontends have not been checked for librime-lua support.

## License

GPL-3.0-or-later, see [LICENSE](LICENSE). `build/rime/licenses/` carries the licenses of the bundled projects:
rime-ice (GPL-3.0) and rime-jaroomaji (Apache-2.0).
