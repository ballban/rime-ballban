-- SPDX-License-Identifier: GPL-3.0-or-later
-- Copyright (C) 2026 ballban
--
-- Decides which language the typed keys mean, so that one schema can type Chinese, Japanese, Korean and English.
--
-- Candidates are labelled by the dictionary they came from: rime-ice is Chinese, jaroomaji is Japanese and melt_eng
-- is English. Korean needs no dictionary, because Dubeolsik keys spell the syllables, so this filter makes the Korean
-- candidate itself. A language is plausible when the keys spell it: whole pinyin or romaji syllables (an unfinished
-- last syllable is fine while typing), Dubeolsik syllables, or a word from melt_eng.
--
-- The best candidate of the most likely language goes first. Candidates of languages the keys cannot spell, such as
-- rime-ice abbreviations of non-pinyin keys, move behind every plausible candidate. Everything else keeps the order
-- Rime gave it, which already puts longer matches and higher quality first.
--
-- Config (in the schema):
--   ballban_language/debug: true   appends the language to every comment

local syllables = require("ballban_syllables")
local hangul = require("ballban_hangul")

-- Rime lists candidates that cover all the keys first. Read all of those (at most MAX_READ) and at least MIN_READ in
-- total, so that the best candidate of every language and some partial matches can be reordered.
local MIN_READ = 30
local MAX_READ = 100

local DICTIONARY_LANGUAGE = {
    rime_ice = "zh",
    jaroomaji = "ja",
    melt_eng = "en",
}

local function language_of(cand)
    local genuine = cand:get_genuine()
    if genuine.type == "korean" then
        return "ko"
    end
    local phrase = genuine:to_phrase()
    if phrase then
        return DICTIONARY_LANGUAGE[phrase.lang_name]
    end
    return nil
end

local function is_syllable(code)
    return code >= 0xAC00 and code <= 0xD7A3
end

-- Returns the Hangul text and whether it is whole syllables. While typing, a last consonant may wait for its vowel;
-- any other loose jamo means the keys are not Korean.
local function korean_reading(keys)
    local text, complete = hangul.compose(keys)
    if not text then
        return nil
    end
    if complete then
        return text, true
    end
    local last
    for _, code in utf8.codes(text) do
        if last and not is_syllable(last) then
            return nil
        end
        last = code
    end
    if last and last >= 0x3131 and last <= 0x314E then
        return text, false
    end
    return nil
end

local function init(env)
    local config = env.engine.schema.config
    env.debug = config:get_bool("ballban_language/debug") or false
    env.page_size = config:get_int("menu/page_size") or 5
end

local function emit(cand, language, env)
    if env.debug then
        cand = cand:to_shadow_candidate(cand.type, cand.text, cand.comment .. " [" .. (language or "?") .. "]")
    end
    yield(cand)
end

local function pass_through(translation, env)
    for cand in translation:iter() do
        emit(cand, language_of(cand), env)
    end
end

local function filter(translation, env)
    local context = env.engine.context
    local seg = context.composition:back()
    if not seg or not seg:has_tag("abc") then
        pass_through(translation, env)
        return
    end
    local keys = context.input:sub(seg.start + 1, seg._end)

    local pinyin = syllables.pinyin(keys)
    local romaji = syllables.romaji(keys)
    local korean_text, korean_complete = korean_reading(keys)
    local plausible = {
        zh = pinyin or syllables.pinyin(keys, true),
        ja = romaji or syllables.romaji(keys, true),
        ko = korean_text ~= nil,
        en = false,
    }

    local buffer, languages = {}, {}
    for cand in translation:iter() do
        buffer[#buffer + 1] = cand
        languages[#buffer] = language_of(cand)
        if languages[#buffer] == "en" and cand._end == seg._end then
            plausible.en = true
        end
        if #buffer >= MAX_READ or (#buffer >= MIN_READ and cand._end ~= seg._end) then
            break
        end
    end

    if not (plausible.zh or plausible.ja or plausible.ko or plausible.en) then
        for i, cand in ipairs(buffer) do
            emit(cand, languages[i], env)
        end
        pass_through(translation, env)
        return
    end

    local korean
    if korean_text then
        korean = Candidate("korean", seg.start, seg._end, korean_text, "")
        korean.preedit = korean_text
        buffer[#buffer + 1] = korean
        languages[#buffer] = "ko"
    end

    -- Dubeolsik keys rarely spell pinyin or romaji, so whole Hangul syllables that are neither win over the
    -- abbreviations and corrections Chinese and Japanese offer for them.
    local lead
    if korean_complete and not pinyin and not romaji then
        lead = #buffer
    else
        for i, cand in ipairs(buffer) do
            local language = languages[i]
            if cand._end == seg._end and language and plausible[language] then
                lead = i
                break
            end
        end
    end

    local ordered, ordered_languages = {}, {}
    local function add(i)
        ordered[#ordered + 1] = buffer[i]
        ordered_languages[#ordered] = languages[i]
    end
    if lead then
        add(lead)
    end
    for i, cand in ipairs(buffer) do
        local language = languages[i]
        if i ~= lead and cand ~= korean and (language == nil or plausible[language]) then
            add(i)
        end
    end
    for i, cand in ipairs(buffer) do
        local language = languages[i]
        if i ~= lead and cand ~= korean and language ~= nil and not plausible[language] then
            add(i)
        end
    end
    -- A Korean reading that does not lead still belongs on the first page, after the matches of the whole keys.
    if korean and buffer[lead] ~= korean then
        local slot = 1
        while slot <= #ordered and slot < env.page_size and ordered[slot]._end == seg._end
            and (ordered_languages[slot] == nil or plausible[ordered_languages[slot]]) do
            slot = slot + 1
        end
        table.insert(ordered, slot, korean)
        table.insert(ordered_languages, slot, "ko")
    end

    for i, cand in ipairs(ordered) do
        emit(cand, ordered_languages[i], env)
    end
    pass_through(translation, env)
end

return { init = init, func = filter }
