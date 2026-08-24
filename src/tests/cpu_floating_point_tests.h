#ifndef XEMU_PERF_TESTS_CPU_FLOATING_POINT_TESTS_H
#define XEMU_PERF_TESTS_CPU_FLOATING_POINT_TESTS_H

#include "test_suite.h"

/**
 * Compares deterministic x87 and scalar SSE arithmetic paths. The workloads
 * remain entirely in normal finite values so timing is not dominated by
 * exceptional-value handling.
 */
class CpuFloatingPointTests : public TestSuite {
 public:
  CpuFloatingPointTests(TestHost &host, std::string output_dir, const Config &config);

 private:
  void TestX87Scalar();
  void TestSseScalar();
};

#endif  // XEMU_PERF_TESTS_CPU_FLOATING_POINT_TESTS_H
