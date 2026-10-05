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
    // The scaling control uses S16 +4096 throughout its source. A constant
    // input avoids phase/filter transients while proving nonzero decoding,
    // routing, and amplitude. Waveform/rate tests use separate oracles.
    constexpr int32_t kMaxMixError = 32 * 256;
    for (size_t i = 0; i < 256; ++i) {
      if (observation.source[2 * i] != 0 ||
          observation.source[2 * i + 1] != 0x10) return false;
    }
    for (uint32_t word : observation.mix_words) {
      if (word & 0xFF000000U) return false;
      const int32_t actual = (word & 0x800000U) ?
          static_cast<int32_t>(word) - 0x1000000 : static_cast<int32_t>(word);
      const int32_t difference = actual - 0x100000;
      if (difference < -kMaxMixError || difference > kMaxMixError) return false;
    }
    return true;
  }
};

}  // namespace AudioTorture

#endif  // XEMU_PERF_TESTS_AUDIO_S16_CONTROL_ORACLE_H
