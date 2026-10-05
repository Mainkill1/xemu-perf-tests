#ifndef XEMU_PERF_TESTS_AUDIO_S16_CONTROL_ORACLE_H
#define XEMU_PERF_TESTS_AUDIO_S16_CONTROL_ORACLE_H

#include <array>
#include <cstddef>
#include <cstdint>

namespace AudioTorture {

struct S16ControlObservation {
  const uint8_t *source{nullptr};
  size_t source_bytes{0};
  std::array<uint32_t, 32> mix_words{};
  uint32_t observed_engine_frames{0};
};

class S16ControlOracle {
 public:
  static bool Check(const S16ControlObservation &observation) {
    if (!observation.source || observation.source_bytes != 512 ||
        observation.observed_engine_frames < 8) return false;
    // A stopped mix buffer may retain a frame captured at any sample offset,
    // not just a source-aligned 32-sample boundary. The 24-bit fixed-point
    // mix path permits at most 32 S16 levels of numerical error per sample.
    // Still require all 32 consecutive source samples, not a checksum or a
    // permissive aggregate error.
    constexpr int32_t kMaxMixError = 32 * 256;
    for (size_t base = 0; base < 256; ++base) {
      bool window_matches = true;
      for (size_t i = 0; i < 32; ++i) {
        const size_t index = (base + i) % 256;
        const uint16_t bits = static_cast<uint16_t>(observation.source[2 * index]) |
                              (static_cast<uint16_t>(observation.source[2 * index + 1]) << 8U);
        const int32_t expected = static_cast<int16_t>(bits) * 256;
        const uint32_t word = observation.mix_words[i];
        if (word & 0xFF000000U) { window_matches = false; break; }
        const int32_t actual = (word & 0x800000U) ?
            static_cast<int32_t>(word) - 0x1000000 : static_cast<int32_t>(word);
        const int32_t difference = actual - expected;
        if (difference < -kMaxMixError || difference > kMaxMixError) {
          window_matches = false;
          break;
        }
      }
      if (window_matches) return true;
    }
    return false;
  }
};

}  // namespace AudioTorture

#endif  // XEMU_PERF_TESTS_AUDIO_S16_CONTROL_ORACLE_H
