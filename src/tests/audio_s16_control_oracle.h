#ifndef XEMU_PERF_TESTS_AUDIO_S16_CONTROL_ORACLE_H
#define XEMU_PERF_TESTS_AUDIO_S16_CONTROL_ORACLE_H

#include <array>
#include <cstddef>
#include <cstdint>

namespace AudioTorture {

struct S16ScalingObservation {
  const uint8_t *source{nullptr};
  size_t source_bytes{0};
  uint32_t channels{1};
  uint32_t requested_voice_count{0};
  uint32_t observed_voice_count{0};
  uint32_t observed_engine_frames{0};
  uint32_t left_gain_divisor{1};
  uint32_t right_gain_divisor{1};
  std::array<uint32_t, 32> left_mix_words{};
  std::array<uint32_t, 32> right_mix_words{};
};

class S16ScalingOracle {
 public:
  static bool Check(const S16ScalingObservation &o) {
    if (!o.source || (o.channels != 1 && o.channels != 2) ||
        !o.requested_voice_count || o.requested_voice_count > 256 ||
        o.observed_voice_count != o.requested_voice_count ||
        o.observed_engine_frames < 8 || o.source_bytes != 257 * o.channels * 2)
      return false;
    const int32_t amplitude = 4096 / o.requested_voice_count;
    for (size_t frame = 0; frame < 257; ++frame) {
      for (size_t channel = 0; channel < o.channels; ++channel) {
        const size_t offset = (frame * o.channels + channel) * 2;
        const uint16_t bits = static_cast<uint16_t>(o.source[offset]) |
                              (static_cast<uint16_t>(o.source[offset + 1]) << 8);
        if (static_cast<int16_t>(bits) != (channel ? -amplitude : amplitude))
          return false;
      }
    }
    const int32_t expected = amplitude * o.requested_voice_count * 256;
    const int32_t tolerance = o.requested_voice_count > 16 ?
        2 * o.requested_voice_count : 32;
    for (size_t channel = 0; channel < 2; ++channel) {
      const auto &words = channel ? o.right_mix_words : o.left_mix_words;
      const uint32_t divisor = channel ? o.right_gain_divisor : o.left_gain_divisor;
      if (!divisor || divisor > 128 || (divisor & (divisor - 1))) return false;
      const int32_t lane_tolerance = (tolerance + divisor - 1) / divisor;
      const int32_t want = (channel && o.channels == 2 ? -expected : expected) /
                           static_cast<int32_t>(divisor);
      for (uint32_t word : words) {
        if (word & 0xFF000000U) return false;
        const int32_t actual = word & 0x800000U ?
            static_cast<int32_t>(word) - 0x1000000 : static_cast<int32_t>(word);
        const int32_t delta = actual - want;
        if (delta < -lane_tolerance || delta > lane_tolerance) return false;
      }
    }
    return true;
  }
};

// Infer only an allowed power-of-two output gain from an independently
// observed one-voice +4096/-4096 reference. This is not a register readback.
inline bool InferS16ReferenceDivisors(const S16ScalingObservation &reference,
                                    uint32_t &left, uint32_t &right) {
  left = right = 0;
  if (reference.requested_voice_count != 1 || reference.observed_voice_count != 1 ||
      reference.observed_engine_frames < 8) return false;
  for (unsigned channel = 0; channel < 2; ++channel) {
    const auto &words = channel ? reference.right_mix_words : reference.left_mix_words;
    for (uint32_t divisor = 1; divisor <= 128; divisor *= 2) {
      const int32_t want = (channel && reference.channels == 2 ? -1048576 : 1048576) /
                           static_cast<int32_t>(divisor);
      const int32_t tolerance = (32 + divisor - 1) / divisor;
      bool match = true;
      for (uint32_t word : words) {
        const int32_t actual = word & 0x800000U ?
            static_cast<int32_t>(word & 0xFFFFFFU) - 0x1000000 : static_cast<int32_t>(word);
        match = match && !(word & 0xFF000000U) &&
                actual >= want - tolerance && actual <= want + tolerance;
      }
      if (match) { (channel ? right : left) = divisor; break; }
    }
  }
  if (!left || !right) return false;
  auto checked = reference;
  checked.left_gain_divisor = left;
  checked.right_gain_divisor = right;
  return S16ScalingOracle::Check(checked);
}

}  // namespace AudioTorture

#endif  // XEMU_PERF_TESTS_AUDIO_S16_CONTROL_ORACLE_H
