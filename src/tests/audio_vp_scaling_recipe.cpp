#include "audio_vp_scaling_recipe.h"

#include <cstring>

namespace AudioTorture {
namespace {
bool Valid(const WorkloadSpec &spec, std::string &error) {
  if (spec.format != SampleFormat::kS16 || spec.source_rate_hz != 48000 ||
      (spec.channels != 1 && spec.channels != 2) || spec.voice_count > 256) {
    error = "S16 scaling requires 0..256 voices, mono/stereo, and 48 kHz";
    return false;
  }
  error.clear();
  return true;
}
}

uint16_t ScalingVoiceHandle(uint32_t ordinal) {
  return ordinal < 256 ? static_cast<uint16_t>((64 + ordinal) % 256) : 0xFFFF;
}

bool BuildS16ScalingSource(const WorkloadSpec &spec, std::vector<uint8_t> &source,
                           std::string &error) {
  source.clear();
  if (!Valid(spec, error)) return false;
  if (!spec.voice_count) return true;
  const int16_t amplitude = static_cast<int16_t>(4096 / spec.voice_count);
  source.resize(kS16ScalingSourceFrames * spec.channels * 2);
  for (uint32_t frame = 0; frame < kS16ScalingSourceFrames; ++frame) {
    for (uint32_t channel = 0; channel < spec.channels; ++channel) {
      const uint16_t value = static_cast<uint16_t>(channel ? -amplitude : amplitude);
      const size_t offset = (frame * spec.channels + channel) * 2;
      source[offset] = static_cast<uint8_t>(value);
      source[offset + 1] = static_cast<uint8_t>(value >> 8);
    }
  }
  return true;
}

bool PrepareS16ScalingVoiceTable(const WorkloadSpec &spec, uint8_t *voice_memory,
                                 size_t voice_bytes, uint32_t source_frames,
                                 std::string &error) {
  if (!Valid(spec, error)) return false;
  if (!voice_memory || voice_bytes < 256 * 128 || source_frames != 257) {
    error = "S16 scaling requires a complete voice table and 257-frame source";
    return false;
  }
  std::memset(voice_memory, 0, 256 * 128);
  for (uint32_t ordinal = 0; ordinal < spec.voice_count; ++ordinal) {
    uint8_t *voice = voice_memory + ScalingVoiceHandle(ordinal) * 128;
    auto word = [voice](size_t offset, uint32_t value) {
      std::memcpy(voice + offset, &value, sizeof(value));
    };
    // The lower 64 slots reserve routes 0..3 for global HRTF submixes even
    // with a null filter handle. Use ordinary routes 4/5 there, preserving
    // left/right channel parity without touching write-only global state.
    const bool low_slot = ScalingVoiceHandle(ordinal) < 64;
    word(0x00, low_slot ? 31U | (31U << 5) | (31U << 10) |
                   (31U << 16) | (1U << 26) :
                   (1U << 5) | (31U << 10) | (31U << 16) |
                   (31U << 21) | (31U << 26));
    word(0x04, 0x520003FFU | (spec.channels == 2 ? 0x08010000U : 0));
    word(0x0C, 0xFF000000U);
    word(0x14, 0xFF000000U);
    word(0x1C, 0xFFFFU);
    word(0x54, (1U << 21) | (5U << 24) | (5U << 28));
    word(0x58, 0xFF000000U);
    word(0x5C, 0xFF000000U | (source_frames - 1));
    word(0x60, low_slot ? 0xFFFFFFFFU : 0x000F000FU);
    word(0x64, 0xFFFFFFFFU);
    word(0x68, low_slot ? 0x000F000FU : 0xFFFFFFFFU);
    word(0x7C, ordinal + 1 == spec.voice_count ? 0xFFFFU :
                   ScalingVoiceHandle(ordinal + 1));
  }
  return true;
}

}  // namespace AudioTorture
