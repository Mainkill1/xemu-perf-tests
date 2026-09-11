#ifndef XEMU_PERF_TESTS_QUERY_PRESSURE_TESTS_H
#define XEMU_PERF_TESTS_QUERY_PRESSURE_TESTS_H

#include "test_suite.h"

/**
 * Preserves the historical same-page vertex rewrite query-pressure control.
 */
class QueryPressureTests : public TestSuite {
 public:
  QueryPressureTests(TestHost &host, std::string output_dir, const Config &config);

 private:
  void Test();
};

#endif  // XEMU_PERF_TESTS_QUERY_PRESSURE_TESTS_H
