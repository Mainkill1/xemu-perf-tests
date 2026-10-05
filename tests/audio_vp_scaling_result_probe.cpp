#include <cassert>
#include <set>
#include <string>

#include "audio_vp_scaling_result.h"
#include "audio_vp_scaling_route.h"

int main() {
  using AudioTorture::BuildScalingLeafMetadata;
  using AudioTorture::WorkloadResult;
  const auto &descriptor = *AudioTorture::FindAudioCase("audio.vp_scaling.s16_mono.v001");
  unsigned registered = 0;
  std::set<std::string> names;
  for (size_t i = 0; i < AudioTorture::AudioCaseCount(); ++i) {
    const auto &d = AudioTorture::AudioCaseAt(i);
    if (d.family != AudioTorture::AudioFamily::kVpScaling) continue;
    const auto name = AudioTorture::ScalingLegacyName(d);
    assert(!name.empty());
    assert(names.insert(name).second);
    assert(name == (d.expected_allocation_denial ? "S16MonoAllocationV257" :
           std::string("S16") + (d.workload.channels == 1 ? "Mono" : "Stereo") +
           'V' + std::string(d.id).substr(std::string(d.id).size() - 3)));
    ++registered;
  }
  assert(registered == 45);
  WorkloadResult setup{};
  const std::string setup_json = BuildScalingLeafMetadata(descriptor, false, setup, "fixture missing");
  assert(setup_json.find("\"oracle_status\":\"FAIL\"") != std::string::npos);
  assert(setup_json.find("\"failure_phase\":\"setup\"") != std::string::npos);

  WorkloadResult output{};
  output.submitted_sample_frames = 256;
  output.observed_engine_frames = 8;
  output.cleanup_passed = true;
  output.cleanup_counter_quiet = true;
  output.observed_mix_words[0] = 0x123456;
  const std::string output_json = BuildScalingLeafMetadata(descriptor, false, output, "wrong mix");
  assert(output_json.find("\"failure_phase\":\"observation\"") != std::string::npos);
  assert(output_json.find("\"observed_mix_words\":[1193046,") != std::string::npos);
  assert(output_json.find("\"cleanup_counter_quiet\":true") != std::string::npos);

  WorkloadResult teardown = output;
  teardown.output_oracle_passed = true;
  teardown.cleanup_passed = false;
  const std::string teardown_json = BuildScalingLeafMetadata(descriptor, false, teardown, "stop failed");
  assert(teardown_json.find("\"failure_phase\":\"teardown\"") != std::string::npos);
  assert(teardown_json.find("\"cleanup_passed\":false") != std::string::npos);

  WorkloadResult good = output;
  good.output_oracle_passed = true;
  good.requested_voice_count = good.accepted_voice_count = good.observed_voice_count = 1;
  const std::string good_json = BuildScalingLeafMetadata(descriptor, true, good, "");
  assert(good_json.find("\"oracle_status\":\"PASS\"") != std::string::npos);
  assert(good_json.find("\"completed_sample_frames\":0") != std::string::npos);
  for (const auto *id : {"audio.vp_scaling.s16_mono.v000", "audio.vp_scaling.s16_mono.allocation_v257"}) {
    const auto &d = *AudioTorture::FindAudioCase(id);
    WorkloadResult control{};
    control.resource_control_passed = control.output_oracle_passed = control.cleanup_passed = true;
    control.requested_voice_count = d.expected_allocation_denial ? 257 : 0;
    control.accepted_voice_count = d.expected_allocation_denial ? 256 : 0;
    control.refused_voice_count = d.expected_allocation_denial ? 1 : 0;
    assert(BuildScalingLeafMetadata(d, true, control, "").find("\"oracle_status\":\"PASS\"") != std::string::npos);
    control.resource_control_passed = false;
    assert(BuildScalingLeafMetadata(d, true, control, "").find("\"oracle_status\":\"FAIL\"") != std::string::npos);
  }
  good.observed_voice_count = 0;
  assert(BuildScalingLeafMetadata(descriptor, true, good, "").find("\"oracle_status\":\"FAIL\"") != std::string::npos);
}
