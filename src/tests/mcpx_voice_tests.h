// SPDX-License-Identifier: Unlicense
#ifndef XEMU_PERF_TESTS_MCPX_VOICE_TESTS_H
#define XEMU_PERF_TESTS_MCPX_VOICE_TESTS_H
#include "test_suite.h"

class McpxVoiceTests : public TestSuite {
 public:
  McpxVoiceTests(TestHost &host, std::string output_dir, const Config &config);

 private:
  void TestVoice(const char *name, bool stereo, bool page_crossing, bool pcm);
};
#endif
