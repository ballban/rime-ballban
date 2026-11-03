// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 ballban
//
// Rebuild a Rime::Grammar/1.0 file with quantized log scores. Encoded keys stay opaque,
// so this does not change the octagram character encoding or require training data.
// Build with C++17 and darts-clone 87b71afd6cf784953e3c08f24c64203397f3b724's include directory.
// Usage: quantize_grammar INPUT.gram OUTPUT.gram [STEP_IN_NATS=0.05]

#include <darts.h>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace fs = std::filesystem;

struct Header {
  char format[32];
  std::uint32_t checksum;
  std::uint32_t units;
  std::uint32_t offset;
};
static_assert(sizeof(Header) == 44);

struct Entries {
  std::vector<std::string> keys;
  std::vector<int> values;
  std::uint32_t max_error = 0;
};

std::uint32_t quantize(std::uint32_t value, std::uint32_t step) {
  auto rounded = (std::uint64_t(value) + step / 2) / step * step;
  if (rounded > std::uint64_t(std::numeric_limits<int>::max()))
    throw std::runtime_error("quantized value exceeds the Darts value range");
  return static_cast<std::uint32_t>(rounded);
}

void collect(const std::vector<std::uint32_t>& units, std::size_t node,
             std::string& key, std::uint32_t step, Entries& entries) {
  auto unit = units.at(node);
  // Darts-clone's unit layout: bits 10..31 hold the XOR offset, bit 9 its scale,
  // bit 8 the terminal flag; a leaf has bit 31 set and stores a 31-bit value.
  auto base = node ^ ((unit >> 10) << ((unit & (1U << 9)) >> 6));
  if (base >= units.size())
    throw std::runtime_error("invalid Darts offset");
  if (unit & (1U << 8)) {
    if (key.empty() || !(units[base] & (1U << 31)))
      throw std::runtime_error("invalid Darts terminal");
    auto value = units[base] & 0x7FFFFFFFU;
    auto rounded = quantize(value, step);
    auto error = rounded > value ? rounded - value : value - rounded;
    if (error > entries.max_error)
      entries.max_error = error;
    entries.keys.push_back(key);
    entries.values.push_back(static_cast<int>(rounded));
  }
  for (std::uint32_t label = 1; label < 256; ++label) {
    auto child = base ^ label;
    if (child >= units.size() || (units[child] & 0x800000FFU) != label)
      continue;
    // Octagram queries at most eight four-byte encoded characters on each side.
    if (key.size() >= 64)
      throw std::runtime_error("key exceeds octagram's query limit or trie has a cycle");
    key.push_back(static_cast<char>(label));
    collect(units, child, key, step, entries);
    key.pop_back();
  }
}

int main(int argc, char** argv) {
  try {
    if (argc != 3 && argc != 4)
      throw std::runtime_error("usage: quantize_grammar INPUT.gram OUTPUT.gram [STEP_IN_NATS=0.05]");
    std::uint32_t endian = 1;
    if (*reinterpret_cast<unsigned char*>(&endian) != 1)
      throw std::runtime_error("only little-endian grammar files are supported");
    std::string step_text = argc == 4 ? argv[3] : "0.05";
    std::size_t consumed = 0;
    double step_nats = std::stod(step_text, &consumed);
    double scaled = step_nats * 10000;
    if (consumed != step_text.size() || !std::isfinite(scaled) || scaled < 1 ||
        scaled > std::numeric_limits<int>::max() || std::abs(scaled - std::round(scaled)) > 1e-6)
      throw std::runtime_error("step must be a positive multiple of 0.0001 nats");
    auto step = static_cast<std::uint32_t>(std::llround(scaled));
    fs::path input = argv[1], output = argv[2], temporary = output;
    temporary += ".tmp";
    if (fs::exists(output) || fs::exists(temporary))
      throw std::runtime_error("output or its .tmp file already exists; choose a new output");

    std::ifstream source(input, std::ios::binary);
    source.exceptions(std::ios::failbit | std::ios::badbit);
    Header header{};
    source.read(reinterpret_cast<char*>(&header), sizeof(header));
    const char format[32] = "Rime::Grammar/1.0";
    if (std::memcmp(header.format, format, sizeof(format)) != 0 ||
        header.offset != 4 || header.units < 256 ||
        fs::file_size(input) != sizeof(header) + std::uint64_t(header.units) * 4)
      throw std::runtime_error("unsupported or malformed Rime::Grammar/1.0 file");
    std::vector<std::uint32_t> units(header.units);
    source.read(reinterpret_cast<char*>(units.data()), units.size() * sizeof(units[0]));
    source.close();
    if (units[0] & 0x800001FFU)
      throw std::runtime_error("invalid Darts root");
    Entries entries;
    std::string key;
    collect(units, 0, key, step, entries);
    if (entries.keys.empty())
      throw std::runtime_error("grammar has no keys");

    std::vector<const char*> keys;
    keys.reserve(entries.keys.size());
    for (const auto& text : entries.keys)
      keys.push_back(text.c_str());
    Darts::DoubleArray trie;
    trie.build(keys.size(), keys.data(), nullptr, entries.values.data());
    for (std::size_t i = 0; i < keys.size(); ++i) {
      if (trie.exactMatchSearch<int>(keys[i]) != entries.values[i])
        throw std::runtime_error("rebuilt trie failed key/value verification");
    }
    if (trie.size() > std::numeric_limits<std::uint32_t>::max())
      throw std::runtime_error("rebuilt trie is too large");
    header.units = static_cast<std::uint32_t>(trie.size());
    std::ofstream target(temporary, std::ios::binary);
    target.exceptions(std::ios::failbit | std::ios::badbit);
    target.write(reinterpret_cast<const char*>(&header), sizeof(header));
    target.write(reinterpret_cast<const char*>(trie.array()), trie.total_size());
    target.close();
    fs::rename(temporary, output);
    std::cout << "keys=" << keys.size() << " step=" << step_nats
              << " max_score_error=" << entries.max_error / 10000.0
              << " input_bytes=" << fs::file_size(input)
              << " output_bytes=" << fs::file_size(output) << '\n';
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "quantize_grammar: " << error.what() << '\n';
    return 1;
  }
}
