#ifndef XEMU_PERF_TESTS_CPU_TRANSLATION_BLOCK_TESTS_H
#define XEMU_PERF_TESTS_CPU_TRANSLATION_BLOCK_TESTS_H

#include "test_suite.h"

/**
 * Fixed-work CPU probes that separate a directly chained loop from an
 * indirect call/return workload. The latter deliberately exercises TCG's
 * indirect translation-block lookup path without touching an emulated device.
 */
class CpuTranslationBlockTests : public TestSuite {
 public:
  CpuTranslationBlockTests(TestHost &host, std::string output_dir, const Config &config);

 private:
  void TestDirectLoop();
  void TestIndirectDispatch();
  void TestIndirectDispatchStress();
};

#endif  // XEMU_PERF_TESTS_CPU_TRANSLATION_BLOCK_TESTS_H
