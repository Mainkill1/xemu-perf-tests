#ifndef XEMU_PERF_TESTS_AUDIO_TORTURE_SUPPORT_H
#define XEMU_PERF_TESTS_AUDIO_TORTURE_SUPPORT_H

#include <cstddef>
#include <cstdint>

namespace AudioTorture {

constexpr uint32_t kDefaultSeed = 0x41554430U;  // "AUD0"
constexpr uint32_t kNominalOutputRateHz = 48000U;
constexpr uint32_t kVpSamplesPerFrame = 32U;
constexpr uint32_t kVpMaxVoices = 256U;
constexpr uint32_t kVpMax3dVoices = 64U;
constexpr uint32_t kVpMixbinCount = 32U;
constexpr uint32_t kVpMaxMixbinsPerVoice = 8U;

enum class BackendKind : uint8_t {
  kAc97Dma,
  kMcpxApuRaw,
};

enum class SampleFormat : uint8_t {
  kU8,
  kS16,
  kS24,
  kS32,
  kAdpcm,
};

enum class ContainerFormat : uint8_t {
  kUnspecified,
  kB8,
  kB16,
  kB32,
  kAdpcm,
};

enum class PipelineMode : uint8_t {
  kVpOnly,
  kVpGp,
  kVpGpEpStereo,
  kVpGpEpSurround,
};

enum class SourceLayout : uint8_t {
  kShared,
  kContiguousUnique,
  kScattered,
};

enum VoiceModeFlag : uint32_t {
  kVoiceModeNone = 0,
  kVoiceModeStream = 1U << 0,
  kVoiceModeLoop = 1U << 1,
  kVoiceModeLinked = 1U << 2,
  kVoiceModePersist = 1U << 3,
  kVoiceModeClearMix = 1U << 4,
  kVoiceModeMultipass = 1U << 5,
};

enum class VoiceControlSequence : uint8_t {
  kNone,
  kLockReconfigure,
  kOnOff,
  kPauseResume,
  kRelease,
};

enum class SignalKind : uint8_t {
  kSilence,
  kDcPositive,
  kDcNegative,
  kImpulse,
  kSquare,
  kLfsrNoise,
  kNearNyquist045,
  kNearNyquist049,
};

struct SignalState {
  uint32_t phase{0};
  uint32_t noise{kDefaultSeed};
  uint64_t sample_index{0};
};

// Integer-only signal generation keeps input deterministic across host/compiler
// differences and avoids FPU use in future audio refill callbacks.
uint32_t PhaseStep(uint32_t frequency_hz, uint32_t sample_rate_hz);
int16_t NextS16(SignalKind kind, SignalState &state, uint32_t frequency_hz,
                uint32_t sample_rate_hz, int16_t amplitude = 0x6000);
void FillInterleavedS16(int16_t *destination, size_t frame_count,
                        uint32_t channel_count, SignalKind kind,
                        SignalState &state, uint32_t frequency_hz,
                        uint32_t sample_rate_hz,
                        int16_t amplitude = 0x6000);

// MCPX U8 PCM is unsigned. This conversion is deterministic and keeps the
// runtime-generated U8 workload aligned with the same S16 integer source used
// by the checked-in fixtures.
void ConvertS16ToU8(const int16_t *source, uint8_t *destination,
                    size_t sample_count);

uint64_t Fnv1a64(const void *data, size_t size);

}  // namespace AudioTorture

#endif  // XEMU_PERF_TESTS_AUDIO_TORTURE_SUPPORT_H
