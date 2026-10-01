#ifndef XEMU_PERF_TESTS_PVIDEO_TESTS_H
#define XEMU_PERF_TESTS_PVIDEO_TESTS_H

#include "test_suite.h"

class PvideoTests : public TestSuite {
 public:
  PvideoTests(TestHost &host, std::string output_dir, const Config &config);
  void Initialize() override;
  void Deinitialize() override;

 private:
  void RunOverlay(bool resize);
  uint8_t *source_{nullptr};
  uint32_t physical_{0};
};

#endif
