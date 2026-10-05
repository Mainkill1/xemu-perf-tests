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
    // A looping 256-sample source can be captured at any of eight frame
    // boundaries. Accept only an entire 32-sample window, not one matching
    // sample or a nonzero checksum.
    for (size_t base = 0; base < 256; base += 32) {
      bool window_matches = true;
      for (size_t i = 0; i < 32; ++i) {
        const size_t index = base + i;
        const uint16_t bits = static_cast<uint16_t>(observation.source[2 * index]) |
                              (static_cast<uint16_t>(observation.source[2 * index + 1]) << 8U);
        const int32_t expected = static_cast<int16_t>(bits) * 256;
        const uint32_t word = observation.mix_words[i];
        if (word & 0xFF000000U) { window_matches = false; break; }
        const int32_t actual = (word & 0x800000U) ?
            static_cast<int32_t>(word) - 0x1000000 : static_cast<int32_t>(word);
        const int32_t difference = actual - expected;
        if (difference < -64 || difference > 64) { window_matches = false; break; }
      }
      if (window_matches) return true;
    }
    return false;
  }
};

}  // namespace AudioTorture

#endif  // XEMU_PERF_TESTS_AUDIO_S16_CONTROL_ORACLE_H
