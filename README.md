# rime-ballban

A [Rime](https://rime.im) schema for typing Chinese, Japanese, Korean and English from the same Latin keys,
without switching input modes.

| Keys            | First candidate | How it is read          |
| --------------- | --------------- | ----------------------- |
| `nihao`         | 你好            | Chinese pinyin          |
| `zhongguo`      | 中国            | Chinese pinyin          |
| `konnnichiha`   | こんにちは      | Japanese romaji         |
| `woxiangyaobeikafei` | 我想要杯咖啡 | Chinese pinyin          |
| `gakkou`        | 学校            | Japanese romaji         |
| `kolhil`        | コーヒー        | Japanese romaji         |
| `watashihanihonnniikitai` | 私は日本に行きたい | Japanese romaji |
| `gksrmf`        | 한글            | Korean Dubeolsik layout |
| `dkssudgktpdy`  | 안녕하세요      | Korean Dubeolsik layout |
| `google`        | Google          | English                 |

The other languages' readings stay in the candidate list, so a wrong first guess costs a few keystrokes, not a mode
switch.

This repository holds configuration, Lua and a grammar model. The engine and dictionaries come from other projects,
pinned to fixed commits and assembled at build time; nothing is forked:

- [librime](https://github.com/rime/librime) runs on every platform through its frontends. Its
  [librime-octagram](https://github.com/lotem/librime-octagram) plugin applies the grammar model.
- [rime-ice](https://github.com/iDvel/rime-ice) provides Chinese pinyin, English and most of the schema. `ballban` includes
  `rime_ice.schema` as it is.
- [rime-jaroomaji](https://github.com/lazyfoxchan/rime-jaroomaji) provides Japanese romaji and its dictionaries. `ballban`
  mounts it as an extra translator.
- Korean is composed by `rime/lua/ballban_hangul.lua` and needs no dictionary.
- `models/ballban.gram` is a Chinese and Japanese grammar model trained for this schema. It decides how dictionary words
  combine into sentences; see [Grammar model](#grammar-model).

## Layout

| Path                            | Contents                                                                    |
| ------------------------------- | --------------------------------------------------------------------------- |
| `rime/ballban.schema.yaml`      | The schema: rime-ice plus the Japanese translator and the language filter   |
| `rime/default.custom.yaml`      | Schema list: `ballban`, then plain `rime_ice` and `jaroomaji`               |
| `rime/lua/ballban_language.lua` | Filter that decides which language goes first and adds the Korean candidate |
| `rime/lua/ballban_syllables.lua`| Checks whether keys spell pinyin or Japanese romaji                         |
| `rime/lua/ballban_hangul.lua`   | Dubeolsik keys to Hangul                                                    |
| `models/ballban.gram`           | Chinese and Japanese grammar model (40 MB), copied into `build/rime/`       |
| `models/jaroomaji-lm.tsv.gz`    | Japanese language model scores for every jaroomaji word                     |
| `tools/fetch_deps.py`           | Downloads the pinned dependencies into `deps/`                              |
| `tools/build.py`                | Assembles a complete Rime user folder in `build/rime/`                      |
| `tools/jaroomaji_weights.py`    | Rewrites jaroomaji's dictionary weights from `models/jaroomaji-lm.tsv.gz`   |
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

`fetch_deps.py` also downloads a librime nightly build for Windows or macOS into `deps/librime`, with librime-lua and
librime-octagram built in. Only `try.py` and the tests use it. It is a nightly because no librime release has the
octagram fix the Japanese grammar needs yet (see [Install](#install)). librime replaces its nightly archives on every
push, so when the download fails, pin the current ones in `fetch_deps.py`. On Linux, install your distribution's librime
with librime-lua and librime-octagram and set `RIME_LIB` to `librime.so.1`.

`build.py` takes a few seconds, most of it spent rewriting jaroomaji's weights. `build/rime/` is about 180 MB.

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

The frontend's librime needs two plugins:

- librime-lua, which rime-ice needs anyway.
- librime-octagram at commit [c030e30](https://github.com/lotem/librime-octagram/commit/c030e30) or later. Older
  versions read every kana as the same character, so the Japanese half of the grammar never matches. No librime release
  includes the fix yet; librime 1.17.0 and Weasel 0.17.4's librime 1.13.1 both predate it. Without the fix, or without
  octagram at all, the schema still works but builds worse sentences (see [Grammar model](#grammar-model)).

1. Run `python tools/build.py`.
2. Back up the frontend's user folder, then copy the contents of `build/rime/` into it. This overwrites files of the same
   name, including `default.custom.yaml`.
   - Weasel (Windows): `%APPDATA%\Rime`
   - Squirrel (macOS): `~/Library/Rime`
   - fcitx5-rime (Linux): `~/.local/share/fcitx5/rime`
   - ibus-rime (Linux): `~/.config/ibus/rime`
   - Trime (Android): `/sdcard/rime`
3. Deploy from the frontend and select **Ballban CJK**.

On Weasel, replace its `rime.dll` with the nightly that `fetch_deps.py` downloads:

1. Quit Weasel: run `WeaselServer.exe /q` in its install folder, such as `C:\Program Files\Rime\weasel-0.17.4`.
2. Back up that folder's `rime.dll`, then copy `deps\librime\dist\lib\rime.dll` over it (needs administrator rights).
3. Start `WeaselServer.exe` again and deploy.

A Weasel update puts its own `rime.dll` back, so repeat this after updating.

Other frontends bundle their own librime and have not been checked for a fixed octagram. Trime 3.3.13 builds
librime-octagram bd12863, which predates the fix. iOS frontends are unchecked.

The schema has been tested through librime directly (the nightly above and 1.17.0). By hand, it has been used in Weasel
0.17.4 only.

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

## Grammar model

Rime builds a sentence from dictionary words. Without a grammar it only adds up the words' weights, so it strings
together the most frequent words. `models/ballban.gram` is a librime-octagram grammar: it gives a bonus to word sequences
that a language model saw together. It covers Chinese and Japanese in one file, because a schema loads one grammar.

How it was made:

- Chinese: Wikipedia (zh, 2023-11-01 dump) and CC-100 (zh-Hans), 519 million words segmented by jieba with rime-ice's
  dictionary.
- Japanese: Wikipedia (ja, 2023-11-01 dump) and CC-100 (ja), segmented by MeCab with IPAdic.
- One KenLM 3-gram model per language, pruned with `--prune 0 32 64`: bigrams seen 32 times or fewer and trigrams seen
  64 times or fewer are dropped.
- Each remaining word sequence becomes a key, scored by how much more often its words occur together than apart
  (pointwise mutual information). Japanese keys written only in characters of the Chinese dictionary are dropped, so
  they do not rank Chinese sentences.

jaroomaji's weights are Mozc costs, which rank single words but are not probabilities. `build.py` replaces them with the
Japanese model's log probability of each word, stored in `models/jaroomaji-lm.tsv.gz`.

Accuracy on [Tatoeba](https://tatoeba.org) sentences typed whole: the share whose first candidate is exactly the
sentence. The dev sets were used for tuning; the test sets only for this table.

| Build                                  | Chinese dev | Chinese test | Japanese dev | Japanese test |
| -------------------------------------- | ----------: | -----------: | -----------: | ------------: |
| v0.1.0 (no grammar)                    | 60.3%       | 59.6%        | 18.0%        | 21.0%         |
| v0.2.0, librime nightly                | 63.0%       | 63.2%        | 60.0%        | 65.6%         |
| v0.2.0, librime 1.17.0 (old octagram)  |             | 63.2%        |              | 30.4%         |
| v0.2.0 with the grammar removed        |             | 60.0%        |              | 37.4%         |

The dev sets have 300 sentences per language and the test sets 500. A less pruned model (146 MB) scored 66.6% and
67.8% on the test sets. The training scripts and the evaluation sets are not in this repository yet.

## Known limitations

- Keys that are valid pinyin and valid romaji (`hashi`, `kani`, `sushi`) follow Rime's ranking, which puts Chinese
  first. Choosing a Japanese candidate does not change that: Rime learns the choice inside the Japanese dictionary,
  but the language order is not learned yet.
- About a third of whole sentences still come out wrong. For example, `kyouha` gives 教派 before 今日は, and
  `kyouhaiitenki` gives 橋はいい天気.
- A single input is read as one language; mixed sentences such as 今日はgoogle are not split.
- The full Japanese grammar needs the librime nightly, which only Weasel with a swapped `rime.dll` has been tried with.
- jaroomaji's dictionaries (91 MB of source, 67 MB compiled) and the grammar (40 MB) are large, which may matter on
  phones.
- iOS frontends have not been checked for librime-lua or librime-octagram support.

## License

GPL-3.0-or-later, see [LICENSE](LICENSE). `build/rime/licenses/` carries the licenses of the bundled projects:
rime-ice (GPL-3.0) and rime-jaroomaji (Apache-2.0).

The files in `models/` are derived from text in Wikipedia (CC BY-SA 4.0) and CC-100, which is drawn from Common Crawl
(Common Crawl terms of use).
