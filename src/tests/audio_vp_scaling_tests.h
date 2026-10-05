#ifndef XEMU_PERF_TESTS_AUDIO_VP_SCALING_TESTS_H
#define XEMU_PERF_TESTS_AUDIO_VP_SCALING_TESTS_H

#include "test_suite.h"

class AudioVpScalingTests : public TestSuite {
 public:
  AudioVpScalingTests(TestHost &host, std::string output_dir, const Config &config);

 private:
  void S16MonoV001();
};

#endif  // XEMU_PERF_TESTS_AUDIO_VP_SCALING_TESTS_H
