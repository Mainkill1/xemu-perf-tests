#include "audio_nxaudio_backend.h"

extern "C" {
#include <nxaudio.h>
}

#include <algorithm>
#include <cstdint>
#include <memory>
#include <vector>

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wignored-attributes"
#include <xboxkrnl/xboxkrnl.h>
#pragma clang diagnostic pop

namespace AudioTorture {
namespace {

constexpr uint32_t kCompletionTimeoutUs = 2000000U;

bool ResolveFormat(const WorkloadSpec &spec, nxAudioFormat &format) {
  if (spec.channels != 1 && spec.channels != 2) {
    return false;
  }
  if (spec.source_rate_hz == 0) {
    return false;
  }

  format = {};
  format.sample_rate = spec.source_rate_hz;
  format.channels = static_cast<uint8_t>(spec.channels);
  format.type = spec.enable_3d ? NX_VOICE_TYPE_3D_STATIC
                               : NX_VOICE_TYPE_2D_STATIC;

  switch (spec.format) {
    case SampleFormat::kU8:
      format.bytes_per_sample = 1;
      format.codec = NX_AUDIO_CODEC_PCM;
      return true;
    case SampleFormat::kS16:
      format.bytes_per_sample = 2;
      format.codec = NX_AUDIO_CODEC_PCM;
      return true;
    case SampleFormat::kS24:
      // nxdk-audio treats bytes_per_sample=3 as S24 carried in B32.
      format.bytes_per_sample = 3;
      format.codec = NX_AUDIO_CODEC_PCM;
      return true;
    case SampleFormat::kS32:
      format.bytes_per_sample = 4;
      format.codec = NX_AUDIO_CODEC_PCM;
      return true;
    case SampleFormat::kAdpcm:
      // bytes_per_sample is ignored for ADPCM by nxdk-audio's format helpers.
      format.bytes_per_sample = 2;
      format.codec = NX_AUDIO_CODEC_ADPCM;
      return true;
  }
  return false;
}

bool SourceSizeIsValid(const WorkloadSpec &spec, size_t source_size) {
  if (spec.channels == 0) {
    return false;
  }
  size_t bytes_per_frame = 0;
  switch (spec.format) {
    case SampleFormat::kU8:
      bytes_per_frame = spec.channels;
      break;
    case SampleFormat::kS16:
      bytes_per_frame = spec.channels * 2U;
      break;
    case SampleFormat::kS24:
    case SampleFormat::kS32:
      bytes_per_frame = spec.channels * 4U;
      break;
    case SampleFormat::kAdpcm:
      return source_size >= 36U * spec.channels &&
             (source_size % (36U * spec.channels)) == 0;
  }
  return bytes_per_frame != 0 && (source_size % bytes_per_frame) == 0;
}

bool WaitForStopped(nxAudioVoice &voice) {
  uint32_t remaining = kCompletionTimeoutUs;
  while (nxAudioVoiceGetState(&voice) != NX_STOPPED && remaining > 0) {
    KeStallExecutionProcessor(100);
    remaining -= std::min<uint32_t>(remaining, 100U);
  }
  return nxAudioVoiceGetState(&voice) == NX_STOPPED;
}

}  // namespace

NxAudioBackend::~NxAudioBackend() { Shutdown(); }

BackendCapabilities NxAudioBackend::Capabilities() const {
  BackendCapabilities capabilities{};
  capabilities.name = "nxaudio_reference";
  capabilities.flags =
      kCapabilityMono | kCapabilityStereo | kCapabilityPcmU8 |
      kCapabilityPcmS16 | kCapabilityPcmS24 | kCapabilityPcmS32 |
      kCapabilityAdpcm | kCapabilitySgeSsl;
  capabilities.max_voices = kVpMaxVoices;
  capabilities.max_2d_voices = kVpMaxVoices - kVpMax3dVoices;
  capabilities.max_3d_voices = kVpMax3dVoices;
  capabilities.max_mixbins_per_voice = kVpMaxMixbinsPerVoice;
  capabilities.nominal_output_rate_hz = kNominalOutputRateHz;
  return capabilities;
}

bool NxAudioBackend::Initialize() {
  if (initialized_) {
    return true;
  }
  nxAudioInitParams params{};
  initialized_ = nxAudioInit(&params);
  return initialized_;
}

bool NxAudioBackend::Run(const WorkloadSpec &spec, const void *source_data,
                         size_t source_size, WorkloadResult &result) {
  result = {};
  if (!initialized_ || !source_data || source_size == 0 ||
      spec.voice_count == 0 || spec.voice_count > kVpMaxVoices ||
      !SourceSizeIsValid(spec, source_size)) {
    result.backend_errors = 1;
    return false;
  }

  // The first executable reference path is intentionally static. Streaming,
  // HRTF motion, filter sweeps, multipass and churn are promoted separately
  // after their focused fixtures/oracles are proven.
  if ((spec.voice_mode_flags & kVoiceModeStream) != 0 ||
      spec.enable_filter || spec.mutate_voice_state ||
      spec.mixbin_fanout != 1) {
    result.backend_errors = 1;
    return false;
  }
  if (spec.enable_hrtf) {
    result.backend_errors = 1;
    return false;
  }

  nxAudioFormat format{};
  if (!ResolveFormat(spec, format)) {
    result.backend_errors = 1;
    return false;
  }

  // Hardware 3D voices occupy the first 64 slots. The upstream allocator
  // enforces that limit; rejecting impossible requests here keeps the failure
  // deterministic and independent of allocation order.
  if (spec.enable_3d && spec.voice_count > kVpMax3dVoices) {
    result.backend_errors = 1;
    return false;
  }
  if (!spec.enable_3d &&
      spec.voice_count > (kVpMaxVoices - kVpMax3dVoices)) {
    result.backend_errors = 1;
    return false;
  }

  if (source_size > UINT32_MAX) {
    result.backend_errors = 1;
    return false;
  }

  auto voices = std::make_unique<nxAudioVoice[]>(spec.voice_count);
  auto buffers = std::make_unique<nxAudioBuffer[]>(spec.voice_count);
  uint32_t created = 0;
  uint32_t started = 0;
  bool ok = true;

  for (uint32_t i = 0; i < spec.voice_count; ++i) {
    if (!nxAudioVoiceCreate(&voices[i], &format)) {
      ok = false;
      break;
    }
    ++created;

    if (!nxAudioBufferInitialize(
            &buffers[i], source_data, static_cast<uint32_t>(source_size)) ||
        !nxAudioBufferSubmit(&voices[i], &buffers[i])) {
      ok = false;
      break;
    }

    if ((spec.voice_mode_flags & kVoiceModeLoop) != 0 &&
        !nxAudioVoiceSetLooping(&voices[i], true)) {
      ok = false;
      break;
    }
  }

  if (ok) {
    // Start only after every voice is configured so the measured hardware
    // interval sees the requested concurrency rather than setup skew.
    for (uint32_t i = 0; i < created; ++i) {
      if (!nxAudioVoiceStart(&voices[i])) {
        ok = false;
        break;
      }
      ++started;
    }
  }

  result.source_checksum = Fnv1a64(source_data, source_size);
  result.peak_active_voices = started;

  if (ok && (spec.voice_mode_flags & kVoiceModeLoop) == 0) {
    for (uint32_t i = 0; i < started; ++i) {
      if (!WaitForStopped(voices[i])) {
        ok = false;
        ++result.completion_timeouts;
      }
    }
  } else if (ok) {
    // Looping stress is bounded by the requested APU-frame count. This is a
    // correctness/work-generation boundary; xemu-side path timers provide the
    // useful performance attribution rather than guest wall-clock duration.
    const uint64_t samples =
        static_cast<uint64_t>(std::max<uint32_t>(spec.audio_frames, 1U)) *
        kVpSamplesPerFrame;
    const uint64_t microseconds =
        (samples * 1000000ULL + kNominalOutputRateHz - 1) /
        kNominalOutputRateHz;
    uint64_t remaining = microseconds;
    while (remaining > 0) {
      const uint32_t slice =
          static_cast<uint32_t>(std::min<uint64_t>(remaining, 1000ULL));
      KeStallExecutionProcessor(slice);
      remaining -= slice;
    }
    result.completed_sample_frames = samples;
  }

  for (uint32_t i = 0; i < created; ++i) {
    nxAudioVoiceDestroy(&voices[i]);
  }

  if (!ok) {
    ++result.backend_errors;
    return false;
  }

  if ((spec.voice_mode_flags & kVoiceModeLoop) == 0) {
    uint32_t bytes_per_frame = 0;
    switch (spec.format) {
      case SampleFormat::kU8:
        bytes_per_frame = spec.channels;
        break;
      case SampleFormat::kS16:
        bytes_per_frame = spec.channels * 2U;
        break;
      case SampleFormat::kS24:
      case SampleFormat::kS32:
        bytes_per_frame = spec.channels * 4U;
        break;
      case SampleFormat::kAdpcm:
        // The codec fixture has a 65-frame decoded golden, while MCPX voice
        // programming consumes 64 frames for each 36-byte/channel block.
        result.completed_sample_frames =
            (source_size / (36U * spec.channels)) * 64U;
        break;
    }
    if (spec.format != SampleFormat::kAdpcm && bytes_per_frame != 0) {
      result.completed_sample_frames = source_size / bytes_per_frame;
    }
  }

  result.submitted_sample_frames =
      result.completed_sample_frames * static_cast<uint64_t>(spec.voice_count);
  return true;
}

void NxAudioBackend::Reset() {
  if (!initialized_) {
    return;
  }
  nxAudioShutdown();
  initialized_ = false;
  nxAudioInitParams params{};
  initialized_ = nxAudioInit(&params);
}

void NxAudioBackend::Shutdown() {
  if (!initialized_) {
    return;
  }
  nxAudioShutdown();
  initialized_ = false;
}

}  // namespace AudioTorture
