#include <array>
#include <cassert>
#include <cstring>
#include <iostream>
#include <set>
#include <string>

#include "audio_case_descriptor.h"

int main() {
  using namespace AudioTorture;
  const std::array<unsigned, 15> expected{{10, 45, 29, 2, 9, 8, 4, 3, 4, 8, 4, 4, 3, 4, 1}};
  std::array<unsigned, 15> counts{};
  std::set<std::string> ids;
  unsigned ac97 = 0;
  unsigned raw = 0;
  unsigned executable = 0;
  for (size_t i = 0; i < AudioCaseCount(); ++i) {
    const auto &item = AudioCaseAt(i);
    assert(ids.insert(item.id).second);
    const auto family = static_cast<size_t>(item.family);
    assert(family < counts.size());
    ++counts[family];
    assert(item.oracle_profile == static_cast<OracleProfile>(family));
    ac97 += item.backend == BackendKind::kAc97Dma;
    raw += item.backend == BackendKind::kMcpxApuRaw;
    executable += item.executable;
    assert(item.executable == (item.family == AudioFamily::kVpScaling));
  }
  assert(AudioCaseCount() == 138);
  assert(counts == expected);
  assert(ac97 == 10 && raw == 128 && executable == 45);
  const auto *control = FindAudioCase("audio.vp_scaling.s16_mono.v001");
  assert(control && control->workload.voice_count == 1);
  assert(control->executable);
  assert(control->workload.channels == 1);
  assert(control->workload.format == SampleFormat::kS16);
  const auto *zero = FindAudioCase("audio.vp_scaling.s16_mono.v000");
  assert(zero && zero->workload.voice_count == 0);
  const auto *denial = FindAudioCase("audio.vp_scaling.s16_mono.allocation_v257");
  assert(denial && denial->workload.voice_count == 256);
  assert(denial->allocation_attempt_count == 257 && denial->expected_allocation_denial);
  const auto *ceiling = FindAudioCase("audio.everything_max.ceiling");
  assert(ceiling && ceiling->optional_ceiling && !ceiling->executable);
  assert(ceiling->workload.three_d_voice_count == 64);
  assert(ceiling->workload.mixed_formats && ceiling->workload.mixed_rates);
  assert(ceiling->workload.pipeline_mode == PipelineMode::kVpGpEpSurround);
  const auto *hrtf = FindAudioCase("audio.hrtf_3d.v064");
  assert(hrtf && hrtf->workload.three_d_voice_count == 64);
  const auto *stream_loop = FindAudioCase("audio.voice_modes.stream_loop");
  assert(stream_loop && (stream_loop->workload.voice_mode_flags & kVoiceModeStream));
  assert(stream_loop->workload.voice_mode_flags & kVoiceModeLoop);
  const auto *pitch = FindAudioCase("audio.pitch_resample.near_nyquist_049");
  assert(pitch && pitch->workload.signal == SignalKind::kNearNyquist049);
  assert(FindAudioCase("audio.not_a_case") == nullptr);
  assert(std::strlen(AudioCaseManifestDigest()) == 64);
  std::cout << "138 descriptors, 15 families, 45 executable\n";
}
