#include "result_statistics.h"

#include <algorithm>
#include <cstddef>

namespace {

uint32_t MedianOfSorted(const std::vector<uint32_t> &values) {
  if (values.empty()) {
    return 0;
  }
  const size_t middle = values.size() / 2;
  if (values.size() & 1U) {
    return values[middle];
  }
  return static_cast<uint32_t>(
      (static_cast<uint64_t>(values[middle - 1]) + values[middle]) / 2U);
}

}  // namespace

ResultStatistics CalculateResultStatistics(
    const std::vector<uint32_t> &samples) {
  if (samples.empty()) {
    return {};
  }

  std::vector<uint32_t> sorted(samples);
  std::sort(sorted.begin(), sorted.end());

  ResultStatistics result;
  result.median_us = MedianOfSorted(sorted);
  // nearest-rank p95: ceil(0.95 * N), converted to a zero-based index.
  const size_t p95_rank = (95U * sorted.size() + 99U) / 100U;
  result.p95_us = sorted[p95_rank - 1U];

  std::vector<uint32_t> deviations;
  deviations.reserve(sorted.size());
  for (const uint32_t value : sorted) {
    deviations.push_back(value > result.median_us
                             ? value - result.median_us
                             : result.median_us - value);
  }
  std::sort(deviations.begin(), deviations.end());
  result.mad_us = MedianOfSorted(deviations);
  return result;
}
