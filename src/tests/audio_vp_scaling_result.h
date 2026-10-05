#ifndef XEMU_PERF_TESTS_AUDIO_VP_SCALING_RESULT_H
#define XEMU_PERF_TESTS_AUDIO_VP_SCALING_RESULT_H

#include <sstream>
#include <string>

#include "audio_case_descriptor.h"

namespace AudioTorture {

inline std::string EscapeAudioResultString(const std::string &value) {
  std::ostringstream out;
  static const char hex[] = "0123456789abcdef";
  for (unsigned char ch : value) {
    if (ch == '"' || ch == '\\') {
      out << '\\' << ch;
    } else if (ch < 0x20) {
      out << "\\u00" << hex[ch >> 4] << hex[ch & 15];
    } else {
      out << ch;
    }
  }
  return out.str();
}

inline std::string BuildScalingLeafMetadata(const AudioCaseDescriptor &descriptor,
                                        bool ran, const WorkloadResult &result,
                                        const std::string &error) {
  const bool control = !descriptor.workload.voice_count || descriptor.expected_allocation_denial;
  const bool counts_ok = control ?
      result.resource_control_passed && result.observed_voice_count == 0 &&
      result.requested_voice_count == (descriptor.expected_allocation_denial ? 257U : 0U) &&
      result.accepted_voice_count == (descriptor.expected_allocation_denial ? 256U : 0U) &&
      result.refused_voice_count == (descriptor.expected_allocation_denial ? 1U : 0U) &&
      result.submitted_sample_frames == 0 && result.observed_engine_frames == 0 :
      result.reference_oracle_passed && result.reference_observed_voice_count == 1 &&
      result.reference_observed_engine_frames >= 8 && result.reference_submitted_sample_frames == 257 &&
      result.observed_engine_frames >= 8 && result.requested_voice_count == descriptor.workload.voice_count &&
      result.accepted_voice_count == descriptor.workload.voice_count && result.refused_voice_count == 0 &&
      result.observed_voice_count == descriptor.workload.voice_count;
  const bool passed = ran && counts_ok && result.output_oracle_passed && result.cleanup_passed;
  const char *phase = "none";
  if (!passed) {
    phase = result.submitted_sample_frames == 0 && result.reference_submitted_sample_frames == 0 ? "setup" :
            !result.cleanup_passed ? "teardown" : "observation";
  }
  std::ostringstream out;
  out << "{\"oracle_status\":\"" << (passed ? "PASS" : "FAIL")
      << "\",\"failure_phase\":\"" << phase
      << "\",\"error\":\"" << EscapeAudioResultString(error)
      << "\",\"source_checksum\":" << result.source_checksum
      << ",\"submitted_sample_frames\":" << result.submitted_sample_frames
      << ",\"reference_source_checksum\":" << result.reference_source_checksum
      << ",\"completed_sample_frames\":" << result.completed_sample_frames
      << ",\"observed_engine_frames\":" << result.observed_engine_frames
      << ",\"requested_voice_count\":" << result.requested_voice_count
      << ",\"accepted_voice_count\":" << result.accepted_voice_count
      << ",\"refused_voice_count\":" << result.refused_voice_count
      << ",\"observed_voice_count\":" << result.observed_voice_count
      << ",\"reference_submitted_sample_frames\":" << result.reference_submitted_sample_frames
      << ",\"reference_observed_engine_frames\":" << result.reference_observed_engine_frames
      << ",\"reference_observed_voice_count\":" << result.reference_observed_voice_count
      << ",\"reference_left_gain_divisor\":" << result.reference_left_gain_divisor
      << ",\"reference_right_gain_divisor\":" << result.reference_right_gain_divisor
      << ",\"reference_oracle_passed\":" << (result.reference_oracle_passed ? "true" : "false")
      << ",\"reference_gain_scope\":\"observed_single_voice_fixture\""
      << ",\"channels\":" << descriptor.workload.channels
      << ",\"resource_control_passed\":" << (result.resource_control_passed ? "true" : "false")
      << ",\"resource_control_scope\":\"guest_voice_slot_pool\""
      << ",\"observed_voice_terminal\":" << (result.observed_voice_terminal ? "true" : "false")
      << ",\"output_oracle_passed\":" << (result.output_oracle_passed ? "true" : "false")
      << ",\"cleanup_passed\":" << (result.cleanup_passed ? "true" : "false")
      << ",\"cleanup_stop_writes_passed\":" << (result.cleanup_stop_writes_passed ? "true" : "false")
      << ",\"cleanup_counter_quiet\":" << (result.cleanup_counter_quiet ? "true" : "false")
      << ",\"cleanup_registers_restored\":" << (result.cleanup_registers_restored ? "true" : "false")
      << ",\"cleanup_dma_guard_passed\":" << (result.cleanup_dma_guard_passed ? "true" : "false")
      << ",\"observed_mix_words\":[";
  for (size_t index = 0; index < result.observed_mix_words.size(); ++index) {
    if (index) out << ',';
    out << result.observed_mix_words[index];
  }
  out << "],\"observed_right_mix_words\":[";
  for (size_t index = 0; index < result.observed_right_mix_words.size(); ++index) {
    if (index) out << ',';
    out << result.observed_right_mix_words[index];
  }
  out << "],\"reference_left_mix_words\":[";
  for (size_t index = 0; index < result.reference_left_mix_words.size(); ++index) {
    if (index) out << ',';
    out << result.reference_left_mix_words[index];
  }
  out << "],\"reference_right_mix_words\":[";
  for (size_t index = 0; index < result.reference_right_mix_words.size(); ++index) {
    if (index) out << ',';
    out << result.reference_right_mix_words[index];
  }
  out << "],\"timing_comparable\":false}";
  return out.str();
}

}  // namespace AudioTorture

#endif  // XEMU_PERF_TESTS_AUDIO_VP_SCALING_RESULT_H
