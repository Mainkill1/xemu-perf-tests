#include "audio_torture_support.h"

#include <algorithm>
#include <cstdint>

namespace AudioTorture {
namespace {

uint32_t NextNoise(uint32_t value) {
  // 32-bit Galois LFSR for deterministic wide-spectrum source data.
  // Polynomial: x^32 + x^22 + x^2 + x + 1.
  if (value == 0) {
    value = kDefaultSeed;
  }
  const uint32_t lsb = value & 1U;
  value >>= 1U;
  if (lsb) {
    value ^= 0x80200003U;
  }
  return value;
}

int16_t ClampAmplitude(int32_t value) {
  value = std::max<int32_t>(value, -32768);
  value = std::min<int32_t>(value, 32767);
  return static_cast<int16_t>(value);
}

}  // namespace

uint32_t PhaseStep(uint32_t frequency_hz, uint32_t sample_rate_hz) {
  if (sample_rate_hz == 0) {
    return 0;
  }
  return static_cast<uint32_t>(
      (static_cast<uint64_t>(frequency_hz) << 32U) / sample_rate_hz);
}

int16_t NextS16(SignalKind kind, SignalState &state, uint32_t frequency_hz,
                uint32_t sample_rate_hz, int16_t amplitude) {
  const int32_t magnitude =
      std::min<int32_t>(amplitude < 0 ? -static_cast<int32_t>(amplitude)
                                     : static_cast<int32_t>(amplitude),
                        32767);
  int32_t value = 0;

  switch (kind) {
    case SignalKind::kSilence:
      value = 0;
      break;
    case SignalKind::kDcPositive:
      value = magnitude;
      break;
    case SignalKind::kDcNegative:
      value = -magnitude;
      break;
    case SignalKind::kImpulse:
      value = state.sample_index == 0 ? magnitude : 0;
      break;
    case SignalKind::kSquare:
      value = (state.phase & 0x80000000U) ? -magnitude : magnitude;
      state.phase += PhaseStep(frequency_hz, sample_rate_hz);
      break;
    case SignalKind::kLfsrNoise: {
      state.noise = NextNoise(state.noise);
      const int32_t signed_noise =
          static_cast<int32_t>(static_cast<int16_t>(state.noise >> 16U));
      value = (signed_noise * magnitude) / 32767;
      break;
    }
  }

  ++state.sample_index;
  return ClampAmplitude(value);
}

void FillInterleavedS16(int16_t *destination, size_t frame_count,
                        uint32_t channel_count, SignalKind kind,
                        SignalState &state, uint32_t frequency_hz,
                        uint32_t sample_rate_hz, int16_t amplitude) {
  if (!destination || channel_count == 0) {
    return;
  }

  for (size_t frame = 0; frame < frame_count; ++frame) {
    const int16_t sample =
        NextS16(kind, state, frequency_hz, sample_rate_hz, amplitude);
    for (uint32_t channel = 0; channel < channel_count; ++channel) {
      *destination++ = sample;
    }
  }
}

void ConvertS16ToU8(const int16_t *source, uint8_t *destination,
                    size_t sample_count) {
  if (!source || !destination) {
    return;
  }
  for (size_t i = 0; i < sample_count; ++i) {
    const int32_t biased = static_cast<int32_t>(source[i]) + 32768;
    destination[i] = static_cast<uint8_t>(biased >> 8);
  }
}

uint64_t Fnv1a64(const void *data, size_t size) {
  constexpr uint64_t kOffset = 14695981039346656037ULL;
  constexpr uint64_t kPrime = 1099511628211ULL;
  const auto *bytes = static_cast<const uint8_t *>(data);
  uint64_t value = kOffset;
  for (size_t i = 0; i < size; ++i) {
    value ^= bytes[i];
    value *= kPrime;
  }
  return value;
}

}  // namespace AudioTorture
