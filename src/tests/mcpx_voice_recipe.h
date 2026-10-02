// SPDX-License-Identifier: Unlicense
#ifndef XEMU_PERF_TESTS_MCPX_VOICE_RECIPE_H
#define XEMU_PERF_TESTS_MCPX_VOICE_RECIPE_H

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <vector>

namespace McpxVoiceRecipe {
static constexpr size_t kPageBytes = 4096;
static constexpr size_t kLogicalPages = 3;
static constexpr size_t kPhysicalPages = 5;

inline uint32_t LoopSamples(bool page_crossing) { return page_crossing ? 64 : 4096; }

inline bool MixValueMatches(uint32_t word, int16_t predictor) {
  if (word & 0xff000000) return false;
  const int32_t actual = (word & 0x800000) ? static_cast<int32_t>(word) - 0x1000000 : static_cast<int32_t>(word);
  const int32_t expected = static_cast<int32_t>(predictor) * 256;
  const int32_t difference = actual - expected;
  return difference >= -32 && difference <= 32;
}

inline std::vector<uint8_t> EncodedBlock(bool stereo) {
  const size_t channels = stereo ? 2 : 1;
  std::vector<uint8_t> bytes(36 * channels, 0);
  // Signed little-endian predictors +4096 / -4096. Index, reserved byte,
  // and all encoded nibbles remain zero: every decoded value is constant.
  bytes[1] = 0x10;
  if (stereo) bytes[5] = 0xf0;
  return bytes;
}

inline bool CopyLogicalBytes(uint8_t *allocation, size_t allocation_bytes, size_t logical_offset, const uint8_t *input,
                             size_t bytes) {
  if (!allocation || (bytes && !input) || allocation_bytes < kPhysicalPages * kPageBytes ||
      logical_offset > kLogicalPages * kPageBytes || bytes > kLogicalPages * kPageBytes - logical_offset) {
    return false;
  }
  while (bytes) {
    const size_t page = logical_offset / kPageBytes;
    const size_t offset = logical_offset % kPageBytes;
    const size_t count = std::min(bytes, kPageBytes - offset);
    std::memcpy(allocation + page * 2 * kPageBytes + offset, input, count);
    logical_offset += count;
    input += count;
    bytes -= count;
  }
  return true;
}
}  // namespace McpxVoiceRecipe

#endif  // XEMU_PERF_TESTS_MCPX_VOICE_RECIPE_H
