#include <cassert>
#include <string>

#include "audio_vp_scaling_result.h"

int main() {
  using AudioTorture::BuildS16LeafMetadata;
  using AudioTorture::WorkloadResult;
  WorkloadResult setup{};
  const std::string setup_json = BuildS16LeafMetadata(false, setup, "fixture missing");
  assert(setup_json.find("\"oracle_status\":\"FAIL\"") != std::string::npos);
  assert(setup_json.find("\"failure_phase\":\"setup\"") != std::string::npos);

  WorkloadResult output{};
  output.submitted_sample_frames = 256;
  output.observed_engine_frames = 8;
  output.cleanup_passed = true;
  output.cleanup_counter_quiet = true;
  output.observed_mix_words[0] = 0x123456;
  const std::string output_json = BuildS16LeafMetadata(false, output, "wrong mix");
  assert(output_json.find("\"failure_phase\":\"observation\"") != std::string::npos);
  assert(output_json.find("\"observed_mix_words\":[1193046,") != std::string::npos);
  assert(output_json.find("\"cleanup_counter_quiet\":true") != std::string::npos);

  WorkloadResult teardown = output;
  teardown.output_oracle_passed = true;
  teardown.cleanup_passed = false;
  const std::string teardown_json = BuildS16LeafMetadata(false, teardown, "stop failed");
  assert(teardown_json.find("\"failure_phase\":\"teardown\"") != std::string::npos);
  assert(teardown_json.find("\"cleanup_passed\":false") != std::string::npos);

  WorkloadResult good = output;
  good.output_oracle_passed = true;
  const std::string good_json = BuildS16LeafMetadata(true, good, "");
  assert(good_json.find("\"oracle_status\":\"PASS\"") != std::string::npos);
  assert(good_json.find("\"completed_sample_frames\":0") != std::string::npos);
}
