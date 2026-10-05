#include "audio_nxaudio_backend.h"

#include <cstdint>

#include "audio_nxaudio_bridge.h"

namespace AudioTorture {
namespace {

bool ResolveBridgeFormat(SampleFormat format, AudioNxBridgeFormat &bridge_format) {
  switch (format) {
    case SampleFormat::kU8:
      bridge_format = AUDIO_NX_BRIDGE_U8;
      return true;
    case SampleFormat::kS16:
      bridge_format = AUDIO_NX_BRIDGE_S16;
      return true;
    case SampleFormat::kS24:
      bridge_format = AUDIO_NX_BRIDGE_S24_B32;
      return true;
    case SampleFormat::kS32:
      bridge_format = AUDIO_NX_BRIDGE_S32;
      return true;
    case SampleFormat::kAdpcm:
      bridge_format = AUDIO_NX_BRIDGE_ADPCM;
      return true;
  }
  return false;
}

bool SourceSizeIsValid(const WorkloadSpec &spec, size_t source_size) {
  if (spec.channels != 1 && spec.channels != 2) {
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
  // This is the reference allocator policy, not a raw MCPX hardware limit.
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
  initialized_ = AudioNxBridgeInitialize();
  return initialized_;
}

bool NxAudioBackend::Run(const WorkloadSpec &spec, const void *source_data,
                         size_t source_size, WorkloadResult &result) {
  result = {};
  if (!initialized_ || !source_data || source_size == 0 ||
      source_size > UINT32_MAX || spec.voice_count == 0 ||
      spec.voice_count > kVpMaxVoices || spec.source_rate_hz == 0 ||
      !SourceSizeIsValid(spec, source_size)) {
    result.backend_errors = 1;
    return false;
  }

  // The first reference path intentionally implements only static workloads.
  // Streaming, HRTF/filter motion, explicit fanout, and churn/control are
  // promoted only after their own correctness observations exist.
  if ((spec.voice_mode_flags & kVoiceModeStream) != 0 ||
      spec.enable_filter || spec.enable_hrtf || spec.mutate_voice_state ||
      spec.mixbin_fanout != 1 ||
      spec.control_sequence != VoiceControlSequence::kNone) {
    result.backend_errors = 1;
    return false;
  }

  const uint32_t reference_limit =
      spec.enable_3d ? kVpMax3dVoices : (kVpMaxVoices - kVpMax3dVoices);
  if (spec.voice_count > reference_limit) {
    result.backend_errors = 1;
    return false;
  }

  AudioNxBridgeFormat bridge_format{};
  if (!ResolveBridgeFormat(spec.format, bridge_format)) {
    result.backend_errors = 1;
    return false;
  }

  AudioNxBridgeRequest request{};
  request.format = bridge_format;
  request.channels = spec.channels;
  request.sample_rate_hz = spec.source_rate_hz;
  request.voice_count = spec.voice_count;
  request.audio_frames = spec.audio_frames;
  request.enable_3d = spec.enable_3d;
  request.loop = (spec.voice_mode_flags & kVoiceModeLoop) != 0;

  AudioNxBridgeResult bridge_result{};
  const bool ok = AudioNxBridgeRun(
      &request, source_data, static_cast<uint32_t>(source_size),
      &bridge_result);

  result.source_checksum = Fnv1a64(source_data, source_size);
  result.peak_active_voices = bridge_result.started_voices;
  result.completion_timeouts = bridge_result.completion_timeouts;
  result.backend_errors = bridge_result.backend_error;
  result.completed_sample_frames = bridge_result.completed_frames_per_voice;
  result.submitted_sample_frames =
      result.completed_sample_frames * static_cast<uint64_t>(spec.voice_count);
  return ok;
}

void NxAudioBackend::Reset() {
  AudioNxBridgeShutdown();
  initialized_ = AudioNxBridgeInitialize();
}

void NxAudioBackend::Shutdown() {
  if (!initialized_) {
    return;
  }
  AudioNxBridgeShutdown();
  initialized_ = false;
}

}  // namespace AudioTorture
