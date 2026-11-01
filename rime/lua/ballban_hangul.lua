-- SPDX-License-Identifier: GPL-3.0-or-later
-- Copyright (C) 2026 ballban

local utf8 = utf8

local initials = {
    "ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ",
    "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ",
}

local medials = {
    "ㅏ", "ㅐ", "ㅑ", "ㅒ", "ㅓ", "ㅔ", "ㅕ", "ㅖ", "ㅗ", "ㅘ",
    "ㅙ", "ㅚ", "ㅛ", "ㅜ", "ㅝ", "ㅞ", "ㅟ", "ㅠ", "ㅡ", "ㅢ", "ㅣ",
}

local finals = {
    "", "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ",
    "ㄻ", "ㄼ", "ㄽ", "ㄾ", "ㄿ", "ㅀ", "ㅁ", "ㅂ", "ㅄ", "ㅅ",
    "ㅆ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ",
}

local function make_index(values)
    local index = {}
    for position, value in ipairs(values) do
        index[value] = position - 1
    end
    return index
end

local initial_index = make_index(initials)
local medial_index = make_index(medials)
local final_index = make_index(finals)

local key_to_jamo = {
    q = "ㅂ", w = "ㅈ", e = "ㄷ", r = "ㄱ", t = "ㅅ",
    y = "ㅛ", u = "ㅕ", i = "ㅑ", o = "ㅐ", p = "ㅔ",
    a = "ㅁ", s = "ㄴ", d = "ㅇ", f = "ㄹ", g = "ㅎ",
    h = "ㅗ", j = "ㅓ", k = "ㅏ", l = "ㅣ",
    z = "ㅋ", x = "ㅌ", c = "ㅊ", v = "ㅍ", b = "ㅠ",
    n = "ㅜ", m = "ㅡ",
    Q = "ㅃ", W = "ㅉ", E = "ㄸ", R = "ㄲ", T = "ㅆ",
    O = "ㅒ", P = "ㅖ",
}

local compound_vowels = {
    ["ㅗㅏ"] = "ㅘ",
    ["ㅗㅐ"] = "ㅙ",
    ["ㅗㅣ"] = "ㅚ",
    ["ㅜㅓ"] = "ㅝ",
    ["ㅜㅔ"] = "ㅞ",
    ["ㅜㅣ"] = "ㅟ",
    ["ㅡㅣ"] = "ㅢ",
}

local double_finals = {
    ["ㄱㅅ"] = "ㄳ",
    ["ㄴㅈ"] = "ㄵ",
    ["ㄴㅎ"] = "ㄶ",
    ["ㄹㄱ"] = "ㄺ",
    ["ㄹㅁ"] = "ㄻ",
    ["ㄹㅂ"] = "ㄼ",
    ["ㄹㅅ"] = "ㄽ",
    ["ㄹㅌ"] = "ㄾ",
    ["ㄹㅍ"] = "ㄿ",
    ["ㄹㅎ"] = "ㅀ",
    ["ㅂㅅ"] = "ㅄ",
}

local double_final_parts = {
    ["ㄳ"] = { "ㄱ", "ㅅ" },
    ["ㄵ"] = { "ㄴ", "ㅈ" },
    ["ㄶ"] = { "ㄴ", "ㅎ" },
    ["ㄺ"] = { "ㄹ", "ㄱ" },
    ["ㄻ"] = { "ㄹ", "ㅁ" },
    ["ㄼ"] = { "ㄹ", "ㅂ" },
    ["ㄽ"] = { "ㄹ", "ㅅ" },
    ["ㄾ"] = { "ㄹ", "ㅌ" },
    ["ㄿ"] = { "ㄹ", "ㅍ" },
    ["ㅀ"] = { "ㄹ", "ㅎ" },
    ["ㅄ"] = { "ㅂ", "ㅅ" },
}

local function is_vowel(jamo)
    return medial_index[jamo] ~= nil
end

local function is_final(jamo)
    local index = final_index[jamo]
    return index ~= nil and index > 0
end

local function syllable(initial, medial, final)
    local initial_position = initial_index[initial]
    local medial_position = medial_index[medial]
    local final_position = final and final_index[final] or 0
    local codepoint = 0xAC00
        + (initial_position * 21 + medial_position) * 28
        + final_position
    return utf8.char(codepoint)
end

local function split_final(final)
    local parts = double_final_parts[final]
    if parts then
        return parts[1], parts[2]
    end
    return nil, final
end

local function is_syllable(ch)
    if type(ch) ~= "string" or utf8.len(ch) ~= 1 then
        return false
    end
    local codepoint = utf8.codepoint(ch)
    return codepoint >= 0xAC00 and codepoint <= 0xD7A3
end

local M = {}

function M.is_hangul_syllable(ch)
    return is_syllable(ch)
end

function M.compose(keys)
    if type(keys) ~= "string" or keys == "" then
        return nil
    end

    for position = 1, #keys do
        if key_to_jamo[keys:sub(position, position)] == nil then
            return nil
        end
    end

    local done = {}
    local initial
    local medial
    local final

    local function flush()
        if initial and medial then
            done[#done + 1] = syllable(initial, medial, final)
        elseif initial or medial then
            done[#done + 1] = initial or medial
        end
        initial = nil
        medial = nil
        final = nil
    end

    for position = 1, #keys do
        local jamo = key_to_jamo[keys:sub(position, position)]
        if is_vowel(jamo) then
            if final then
                local kept, moved = split_final(final)
                final = kept
                flush()
                initial = moved
                medial = jamo
            elseif medial then
                local compound = compound_vowels[medial .. jamo]
                if compound then
                    medial = compound
                else
                    flush()
                    medial = jamo
                end
            else
                medial = jamo
            end
        else
            if initial and medial then
                if not final and is_final(jamo) then
                    final = jamo
                elseif final then
                    local joined = double_finals[final .. jamo]
                    if joined then
                        final = joined
                    else
                        flush()
                        initial = jamo
                    end
                else
                    flush()
                    initial = jamo
                end
            else
                flush()
                initial = jamo
            end
        end
    end

    local complete = true
    local result = {}
    for _, block in ipairs(done) do
        result[#result + 1] = block
        if not is_syllable(block) then
            complete = false
        end
    end

    if initial and medial then
        result[#result + 1] = syllable(initial, medial, final)
    elseif initial or medial then
        result[#result + 1] = initial or medial
        complete = false
    end

    return table.concat(result), complete
end

return M
