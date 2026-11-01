-- SPDX-License-Identifier: GPL-3.0-or-later
-- Copyright (C) 2026 ballban

local M = {}

local gmatch = string.gmatch
local sub = string.sub
local byte = string.byte
local input_type = type

local function append_all(destination, source)
    for i = 1, #source do
        destination[#destination + 1] = source[i]
    end
end

local function add_prefixes(prefixes, value)
    for length = 1, #value - 1 do
        prefixes[sub(value, 1, length)] = true
    end
end

local PINYIN_DATA = [[
de shi yi ji wo ta you zai zhi ren li zhe ge zi zhei qi
xiang wei di da dao lai jiu zhong shang qing shen jian ye xiao ma huo
guo na hui shuo mei jing xi he er wu sheng dan yao yu hai fang
jin xia en si shou hou qu eng jie hao ba yan xing fu kan jia
zuo hua dui ran tian yuan dei bu zhang xie chang cheng xian fa qian bei
zhu zheng ming a lian jiao gong bian an liang chu dian yin ru ci wen
xin wang dong tou shu bi zhen tong gan duo ying hu wan mian fan ju
hen ke guan yang jiang kai ban xue yong jue bao cai le feng ting ling
fen bai lao suo dang dai fei nan xu bing gao nian gu o mo la
shan zhao mu liu ding shai zui tai cong shui lu ti que chi quan nv
san ya zhan zou rang sui ben gei hang du tu deng huan yue shao man
guang su ai kou zen han kong luo chen qiang gen chuan zu yun kuai qin
gai wai tiao lin lei tan ping mi huang gui zao qie se ni e bie
zhou chao duan cha hong zong gang qiu long ri xiu zhuan geng bo ku zhuang
sha biao che meng chong pai tao dou xiong she hei xuan song ze po gou
pa rong pi nei men diao pian bang suan mao tuo mang te tui kuang hun
leng xun wa pao qiao jun mai lan guai shuang lun nao lv min can chan
ruo lang shei chuang ceng cao pu cuo chou lou pin pang cun pei ha chun
dun nu liao nai zhuo zhun pan piao nong tang peng re luan tie miao tuan
lie shun zan heng cang ce zha juan mou niang kao zhui ning qun sun niu
ken ao kang reng gua rou sai nin ka huai cui kui shuai fo ou die
fou chui lve teng kun rao sao cu rui kuo sang mie zun kuan bin gun
nuo zhai zeng ruan sa sou sen niao kua zang qiong chai diu ne ca za
nie pen tun beng shua zei zhua nuan ga zuan jiong run ang cou weng keng
cuan pie seng nang nen neng yo chuai zhuai chuo nve miu shuan cen pou qia
me lo cei dia ei nou kei lia den chua rua sei
]]

local PINYIN = {}
local PINYIN_PREFIX = {}
for syllable in gmatch(PINYIN_DATA, "%S+") do
    PINYIN[syllable] = true
    add_prefixes(PINYIN_PREFIX, syllable)
end

-- Rime also accepts these spellings for ü after l and n.
PINYIN.lue = true
PINYIN.nue = true
add_prefixes(PINYIN_PREFIX, "lue")
add_prefixes(PINYIN_PREFIX, "nue")

local function has_only(input, allow_apostrophe, allow_hyphen)
    if input_type(input) ~= "string" or #input == 0 then
        return false
    end
    for i = 1, #input do
        local c = byte(input, i)
        if c < 97 or c > 122 then
            if not (allow_apostrophe and c == 39) and not (allow_hyphen and c == 45) then
                return false
            end
        end
    end
    return true
end

local function split_pinyin_part(part)
    local length = #part
    local counts = {}
    local next_positions = {}

    local function solve(position)
        if position == length + 1 then
            return 0
        end
        local cached = counts[position]
        if cached ~= nil then
            return cached
        end

        local best_count
        local best_next
        local last = position + 5
        if last > length then
            last = length
        end

        -- Descending end positions make the tie-break prefer a longer first syllable.
        for finish = last, position, -1 do
            if PINYIN[sub(part, position, finish)] then
                local rest = solve(finish + 1)
                if rest ~= false then
                    local count = rest + 1
                    if best_count == nil or count < best_count then
                        best_count = count
                        best_next = finish + 1
                    end
                end
            end
        end

        if best_count == nil then
            counts[position] = false
        else
            counts[position] = best_count
            next_positions[position] = best_next
        end
        return counts[position]
    end

    if solve(1) == false then
        return nil
    end

    local result = {}
    local position = 1
    while position <= length do
        local next_position = next_positions[position]
        result[#result + 1] = sub(part, position, next_position - 1)
        position = next_position
    end
    return result
end

local function split_pinyin_strict(input)
    if not has_only(input, true, false) then
        return nil
    end
    local result = {}
    local start = 1
    local length = #input
    for position = 1, length + 1 do
        if position == length + 1 or byte(input, position) == 39 then
            if position == start then
                return nil
            end
            local pieces = split_pinyin_part(sub(input, start, position - 1))
            if pieces == nil then
                return nil
            end
            append_all(result, pieces)
            start = position + 1
        end
    end
    return result
end

local function split_pinyin_partial_part(part)
    for cut = #part - 1, 0, -1 do
        local trailing = sub(part, cut + 1)
        if PINYIN_PREFIX[trailing] then
            local prefix = {}
            if cut > 0 then
                prefix = split_pinyin_part(sub(part, 1, cut))
            end
            if prefix ~= nil then
                append_all(prefix, { trailing })
                return prefix
            end
        end
    end
    return nil
end

local function split_pinyin_partial(input)
    local last_boundary = 0
    for position = 1, #input do
        if byte(input, position) == 39 then
            last_boundary = position
        end
    end

    local prefix = {}
    local final_start = last_boundary + 1
    if last_boundary > 0 then
        prefix = split_pinyin_strict(sub(input, 1, last_boundary - 1))
        if prefix == nil then
            return nil
        end
    end

    local trailing = split_pinyin_partial_part(sub(input, final_start))
    if trailing == nil then
        return nil
    end
    append_all(prefix, trailing)
    return prefix
end

function M.pinyin(input, partial)
    local strict = split_pinyin_strict(input)
    if strict ~= nil then
        return true, strict
    end
    if not partial or not has_only(input, true, false) then
        return false, {}
    end
    local result = split_pinyin_partial(input)
    if result == nil then
        return false, {}
    end
    return true, result
end

local ROMAJI_DATA = [[
a i yi u whu wu e o ka ki ku ke ko kya kyu kyo
sa shi si su se ce so sha sya shu syu sho syo she sye ta
chi ti tsu tu te to cha tya cya chu tyu cyu cho tyo cyo che
tye cye tha thu tho na ni nu ne no nya nyu nyo nyi nye ha
hi fu hu he ho hya hyu hyo fa fi fyi fe fye fo fya fyu
fyo ma mi mu me mo mya myu myo ya yu yo ra ri ru re
ro rya ryu ryo wa wo who wha ga gi gu ge go gya gyu gyo
za ji zi zu ze zo ja jya zya ju jyu zyu jo jyo zyo je
jye zye da di du de do dha dhu dho dya dyu dyo ba bi bu
be bo bya byu byo pa pi pu pe po pya pyu pyo twa twi twe
twu dwa dwi dwe dwu kye gye pye mye kwi kwu kwe gwi gwu gwe zwa
zwi zwu zwe va vi vu ve vo ye wi whi we whe wyi wye thi
dhi the dhe qi qe qo ca ci cu co cyi tyi kwa kwo gwa tsa
tsi tse tso
vya vyi vyu vye vyo fwa fwi fwu fwe fwo
qa qu qya qyi qyu qye qyo qwa qwi qwu qwe qwo
dye
]]

local ROMAJI = {}
local ROMAJI_PREFIX = {}
for unit in gmatch(ROMAJI_DATA, "%S+") do
    ROMAJI[unit] = true
    add_prefixes(ROMAJI_PREFIX, unit)
end

local function is_vowel(c)
    return c == 97 or c == 105 or c == 117 or c == 101 or c == 111
end

local function is_consonant(c)
    return c ~= nil and c >= 97 and c <= 122 and not is_vowel(c)
end

local function choose_romaji(input)
    local length = #input
    local counts = {}
    local next_positions = {}

    local function solve(position)
        if position == length + 1 then
            return 0
        end
        local cached = counts[position]
        if cached ~= nil then
            return cached
        end

        local best_count
        local best_next

        local function consider(finish)
            local rest = solve(finish + 1)
            if rest ~= false then
                local count = rest + 1
                if best_count == nil or count < best_count then
                    best_count = count
                    best_next = finish + 1
                end
            end
        end

        local last = position + 3
        if last > length then
            last = length
        end
        -- Longest ordinary units are considered first for deterministic output.
        for finish = last, position, -1 do
            if ROMAJI[sub(input, position, finish)] then
                consider(finish)
            end
        end

        local current = byte(input, position)
        local following = byte(input, position + 1)
        if current == 110 then
            if following == 110 then
                consider(position + 1)
            elseif following == 39 then
                consider(position + 1)
            elseif following == nil or (is_consonant(following) and following ~= 121) then
                consider(position)
            end
        elseif current == 45 then
            consider(position)
        elseif current == 108 then
            -- jaroomaji spells the long vowel mark ー as "l" too. Only accept it after a vowel or ん and before a
            -- consonant or the end, so English words such as "hello" or "sale" do not read as romaji.
            local previous = position > 1 and byte(input, position - 1) or nil
            if previous ~= nil and (is_vowel(previous) or previous == 110)
                and (following == nil or (is_consonant(following) and following ~= 108)) then
                consider(position)
            end
        elseif is_consonant(current) and current ~= 110 and
            (following == current or (current == 116 and following == 99 and byte(input, position + 2) == 104)) then
            -- The second consonant must still start a valid path; solve() enforces that.
            consider(position)
        end

        if best_count == nil then
            counts[position] = false
        else
            counts[position] = best_count
            next_positions[position] = best_next
        end
        return counts[position]
    end

    if solve(1) == false then
        return nil
    end

    local units = {}
    local position = 1
    while position <= length do
        local next_position = next_positions[position]
        units[#units + 1] = sub(input, position, next_position - 1)
        position = next_position
    end
    return units
end

local function add_partial_candidate(best, consumed, prefix, trailing)
    if consumed <= best.consumed then
        return best
    end
    local result = {}
    append_all(result, prefix)
    result[#result + 1] = trailing[1]
    if trailing[2] ~= nil then
        result[#result + 1] = trailing[2]
    end
    best.consumed = consumed
    best.units = result
    return best
end

local function split_romaji_partial(input)
    local best = { consumed = -1, units = nil }
    for cut = #input - 1, 0, -1 do
        local trailing = sub(input, cut + 1)
        if ROMAJI_PREFIX[trailing] then
            local prefix = {}
            if cut > 0 then
                prefix = choose_romaji(sub(input, 1, cut))
            end
            if prefix ~= nil then
                best = add_partial_candidate(best, cut, prefix, { trailing })
            end
        end
    end

    -- A repeated consonant can end as っ plus the next unit's unfinished prefix.
    for start = #input - 1, 1, -1 do
        local current = byte(input, start)
        local following = byte(input, start + 1)
        local is_sokuon = is_consonant(current) and current ~= 110 and
            (following == current or (current == 116 and following == 99 and byte(input, start + 2) == 104))
        if is_sokuon then
            local trailing = sub(input, start + 1)
            if ROMAJI_PREFIX[trailing] then
                local prefix = {}
                if start > 1 then
                    prefix = choose_romaji(sub(input, 1, start - 1))
                end
                if prefix ~= nil then
                    best = add_partial_candidate(
                        best,
                        start - 1,
                        prefix,
                        { sub(input, start, start), trailing })
                end
            end
        end
    end
    return best.units
end

function M.romaji(input, partial)
    if not has_only(input, true, true) then
        return false, {}
    end
    local units = choose_romaji(input)
    if units ~= nil then
        return true, units
    end
    if not partial then
        return false, {}
    end
    units = split_romaji_partial(input)
    if units == nil then
        return false, {}
    end
    return true, units
end

return M
