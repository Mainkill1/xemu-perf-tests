#ifndef XEMU_PERF_TESTS_CPU_TRANSLATION_BLOCK_TESTS_H
#define XEMU_PERF_TESTS_CPU_TRANSLATION_BLOCK_TESTS_H

#include <cstdint>

#include "test_suite.h"

/**
 * Fixed-work CPU probes that separate a directly chained loop from an
 * indirect call/return workload and generated code with or without writes.
 * These exercise TCG lookup and invalidation without touching an emulated device.
 */
class CpuTranslationBlockTests : public TestSuite {
 public:
  CpuTranslationBlockTests(TestHost &host, std::string output_dir, const Config &config);

 private:
  void TestDirectLoop();
  void TestIndirectDispatch();
  void TestIndirectDispatchStress();
  void TestGeneratedCode(const char *name, bool rewrite, uint32_t expected);
};

#endif  // XEMU_PERF_TESTS_CPU_TRANSLATION_BLOCK_TESTS_H
