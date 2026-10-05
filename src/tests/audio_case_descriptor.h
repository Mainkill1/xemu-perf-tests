#ifndef XEMU_PERF_TESTS_AUDIO_CASE_DESCRIPTOR_H
#define XEMU_PERF_TESTS_AUDIO_CASE_DESCRIPTOR_H

#include <cstddef>
#include <cstdint>
#include <cstring>

#include "audio_torture_backend.h"

namespace AudioTorture {

enum class AudioFamily : uint8_t {
  kAc97Dma,
  kVpScaling,
  kFormatRate,
  kPitchResample,
  kBufferBoundary,
  kStreamingDma,
  kMixbinFanout,
  kFilterEnvelope,
  kHrtf3d,
  kVoiceModes,
  kVoiceControl,
  kVoiceChurn,
  kMemoryLocality,
  kGpEp,
  kEverythingMax,
};

enum class OracleProfile : uint8_t {
  kAc97Dma,
  kVpScaling,
  kFormatRate,
  kPitchResample,
  kBufferBoundary,
  kStreamingDma,
  kMixbinFanout,
  kFilterEnvelope,
  kHrtf3d,
  kVoiceModes,
  kVoiceControl,
  kVoiceChurn,
  kMemoryLocality,
  kGpEp,
  kEverythingMax,
};

struct AudioCaseDescriptor {
  const char *id;
  AudioFamily family;
  BackendKind backend;
  WorkloadSpec workload;
  bool expected_allocation_denial;
  uint32_t allocation_attempt_count;
  bool optional_ceiling;
  OracleProfile oracle_profile;
  const char *intended_paths_json;
  bool executable;
};

#include "../generated/audio_case_catalog.inc"

inline size_t AudioCaseCount() { return sizeof(kAudioCases) / sizeof(kAudioCases[0]); }
inline const AudioCaseDescriptor &AudioCaseAt(size_t index) { return kAudioCases[index]; }
inline const char *AudioCaseManifestDigest() { return kAudioCaseManifestDigest; }
inline const AudioCaseDescriptor *FindAudioCase(const char *id) {
  if (!id) return nullptr;
  for (const auto &item : kAudioCases) {
    if (std::strcmp(item.id, id) == 0) return &item;
  }
  return nullptr;
}

}  // namespace AudioTorture

#endif  // XEMU_PERF_TESTS_AUDIO_CASE_DESCRIPTOR_H
