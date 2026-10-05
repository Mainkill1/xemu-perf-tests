#ifndef XEMU_PERF_TESTS_AUDIO_VP_SCALING_TESTS_H
#define XEMU_PERF_TESTS_AUDIO_VP_SCALING_TESTS_H

#include "test_suite.h"
#include "audio_case_descriptor.h"

class AudioVpScalingTests : public TestSuite {
 public:
  AudioVpScalingTests(TestHost &host, std::string output_dir, const Config &config);

 private:
  void RunCase(const AudioTorture::AudioCaseDescriptor &descriptor,
               const std::string &legacy_name);
};

#endif  // XEMU_PERF_TESTS_AUDIO_VP_SCALING_TESTS_H
