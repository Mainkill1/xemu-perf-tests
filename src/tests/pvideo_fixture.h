#ifndef XEMU_PERF_TESTS_PVIDEO_FIXTURE_H
#define XEMU_PERF_TESTS_PVIDEO_FIXTURE_H

#include <cstddef>
#include <cstdint>

namespace PvideoFixture {
constexpr uint32_t kWindowBytes = 32768;
// Keep a guard page past both windows: xemu's decoder compares the
// one-past source end against the inclusive LIMIT register.
constexpr uint32_t kSourceBytes = 2 * kWindowBytes + 4096;
struct FrameState {
  uint32_t width, height, offset;
  bool enabled, inverted;
};
inline FrameState Frame(uint32_t index, bool resize) {
  uint32_t phase = (index / 64) % 8;
  uint32_t size = resize && phase == 3 ? 64 : 128;
  bool second = resize ? phase == 2 || phase == 3 || phase == 7 : ((phase / 2) & 1);
  return {size, size, second ? kWindowBytes : 0U, !resize || phase != 6, bool(phase & 1)};
}
inline bool Fill(uint8_t *bytes, size_t capacity, uint32_t width, uint32_t height, bool inverted) {
  if (!bytes || width < 2 || width > 128 || (width & 1) || height < 2 || height > 128 ||
      capacity < size_t(width) * height * 2) {
    return false;
  }
  for (uint32_t y = 0; y < height; ++y) {
    for (uint32_t x = 0; x < width; ++x) {
      bool white = ((x < width / 2) != (y < height / 2)) != inverted;
      bytes[(y * width + x) * 2] = white ? 235 : 16;
      bytes[(y * width + x) * 2 + 1] = 128;
    }
  }
  return true;
}
}  // namespace PvideoFixture
#endif
