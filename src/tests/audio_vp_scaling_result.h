#ifndef XEMU_PERF_TESTS_AUDIO_VP_SCALING_RESULT_H
#define XEMU_PERF_TESTS_AUDIO_VP_SCALING_RESULT_H

#include <sstream>
#include <string>

#include "audio_torture_backend.h"

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

inline std::string BuildS16LeafMetadata(bool ran, const WorkloadResult &result,
                                        const std::string &error) {
  const bool passed = ran && result.observed_engine_frames >= 8 &&
                      result.output_oracle_passed && result.cleanup_passed;
  const char *phase = "none";
  if (!passed) {
    phase = result.submitted_sample_frames == 0 ? "setup" :
            !result.cleanup_passed ? "teardown" : "observation";
  }
  std::ostringstream out;
  out << "{\"oracle_status\":\"" << (passed ? "PASS" : "FAIL")
      << "\",\"failure_phase\":\"" << phase
      << "\",\"error\":\"" << EscapeAudioResultString(error)
      << "\",\"source_checksum\":" << result.source_checksum
      << ",\"submitted_sample_frames\":" << result.submitted_sample_frames
      << ",\"completed_sample_frames\":" << result.completed_sample_frames
      << ",\"observed_engine_frames\":" << result.observed_engine_frames
      << ",\"observed_voice_terminal\":" << (result.observed_voice_terminal ? "true" : "false")
      << ",\"output_oracle_passed\":" << (result.output_oracle_passed ? "true" : "false")
      << ",\"cleanup_passed\":" << (result.cleanup_passed ? "true" : "false")
      << ",\"observed_mix_words\":[";
  for (size_t index = 0; index < result.observed_mix_words.size(); ++index) {
    if (index) out << ',';
    out << result.observed_mix_words[index];
  }
  out << "],\"timing_comparable\":false}";
  return out.str();
}

}  // namespace AudioTorture

#endif  // XEMU_PERF_TESTS_AUDIO_VP_SCALING_RESULT_H
