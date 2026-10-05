#ifndef XEMU_PERF_TESTS_AUDIO_TORTURE_BACKEND_H
#define XEMU_PERF_TESTS_AUDIO_TORTURE_BACKEND_H

#include <cstddef>
#include <cstdint>

#include "audio_torture_support.h"

namespace AudioTorture {

enum Capability : uint32_t {
  kCapabilityAc97Dma = 1U << 0,
  kCapabilityMono = 1U << 1,
  kCapabilityStereo = 1U << 2,
  kCapabilityPcmU8 = 1U << 3,
  kCapabilityPcmS16 = 1U << 4,
  kCapabilityPcmS24 = 1U << 5,
  kCapabilityPcmS32 = 1U << 6,
  kCapabilityAdpcm = 1U << 7,
  kCapabilitySgeSsl = 1U << 8,
  kCapabilityMixbins = 1U << 9,
  kCapabilityFilter = 1U << 10,
  kCapabilityHrtf = 1U << 11,
  kCapabilityGp = 1U << 12,
  kCapabilityEp = 1U << 13,
  kCapabilityVoiceModes = 1U << 14,
  kCapabilityVoiceControl = 1U << 15,
};

struct BackendCapabilities {
  const char *name{nullptr};
  uint32_t flags{0};
  uint32_t max_voices{0};
  uint32_t max_2d_voices{0};
  uint32_t max_3d_voices{0};
  uint32_t max_mixbins_per_voice{0};
  uint32_t nominal_output_rate_hz{kNominalOutputRateHz};
};

struct WorkloadSpec {
  SampleFormat format{SampleFormat::kS16};
  ContainerFormat container_format{ContainerFormat::kUnspecified};
  SourceLayout source_layout{SourceLayout::kShared};
  SignalKind signal{SignalKind::kSilence};
  uint32_t channels{2};
  uint32_t source_rate_hz{kNominalOutputRateHz};
  uint32_t voice_count{1};
  uint32_t audio_frames{1};
  uint32_t mixbin_fanout{1};
  uint32_t refill_bytes{0};
  uint32_t buffer_samples{0};
  uint32_t refill_samples{0};
  uint32_t three_d_voice_count{0};
  uint32_t allocation_attempt_count{0};
  uint32_t tone_frequency_hz{1000};
  uint32_t voice_mode_flags{kVoiceModeNone};
  VoiceControlSequence control_sequence{VoiceControlSequence::kNone};
  PipelineMode pipeline_mode{PipelineMode::kVpOnly};
  bool enable_3d{false};
  bool enable_hrtf{false};
  bool enable_filter{false};
  bool mutate_voice_state{false};
  bool mixed_formats{false};
  bool mixed_rates{false};
};

struct WorkloadResult {
  uint64_t source_checksum{0};
  uint64_t submitted_sample_frames{0};
  uint64_t completed_sample_frames{0};
  uint32_t peak_active_voices{0};
  uint32_t underruns{0};
  uint32_t completion_timeouts{0};
  uint32_t backend_errors{0};
  uint32_t observed_engine_frames{0};
  bool observed_voice_terminal{false};
  bool output_oracle_passed{false};
  bool cleanup_passed{false};
};

// Hardware backends must be explicit lifecycle owners. A backend must never
// report a successful Run() merely because source generation completed; the
// requested device work must have been submitted and observed complete.
//
// Shutdown() must restore enough device state that later non-audio suites are
// not affected. If safe restoration is unavailable, the backend must remain
// unregistered from the full suite.
class Backend {
 public:
  virtual ~Backend() = default;

  virtual BackendCapabilities Capabilities() const = 0;
  virtual bool Initialize() = 0;
  virtual bool Run(const WorkloadSpec &spec, const void *source_data,
                   size_t source_size, WorkloadResult &result) = 0;
  virtual void Reset() = 0;
  virtual void Shutdown() = 0;
};

}  // namespace AudioTorture

#endif  // XEMU_PERF_TESTS_AUDIO_TORTURE_BACKEND_H
