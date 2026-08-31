#ifndef XEMU_PERF_TESTS_RESULT_STATISTICS_H
#define XEMU_PERF_TESTS_RESULT_STATISTICS_H

#include <cstdint>
#include <vector>

struct ResultStatistics {
  uint32_t median_us{0};
  uint32_t p95_us{0};
  uint32_t mad_us{0};
};

// Exact integer statistics for microsecond samples. Median and MAD use the
// midpoint of the two center values. P95 uses the nearest-rank definition.
ResultStatistics CalculateResultStatistics(
    const std::vector<uint32_t> &samples);

#endif  // XEMU_PERF_TESTS_RESULT_STATISTICS_H
