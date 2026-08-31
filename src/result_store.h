#ifndef XEMU_PERF_TESTS_RESULT_STORE_H
#define XEMU_PERF_TESTS_RESULT_STORE_H

#include <cstdint>
#include <cstddef>
#include <string>
#include <vector>

struct StoredResultRecord {
  std::string id;
  std::string name;
  std::string kind;
  std::string outcome;
  uint32_t average_us{0};
  uint32_t minimum_us{0};
  uint32_t maximum_us{0};
  uint32_t median_us{0};
  uint32_t p95_us{0};
  uint32_t mad_us{0};
  uint32_t sample_count{0};
  bool has_measurement{false};
  bool has_distribution{false};
  bool oracle_recorded{false};
  bool oracle_failed{false};
  std::string unit{"us"};
  std::string direction{"lower_is_better"};
  std::string failure_reason;
  std::string expected_value;
  std::string actual_value;
};

struct StoredResultFile {
  std::string path;
  std::string label;
  std::string error;
  uint64_t size_bytes{0};
  bool complete{false};
  std::vector<StoredResultRecord> records;
};

struct StoredResultSamples {
  std::vector<uint32_t> values;
  uint32_t total_count{0};
  uint32_t stride{1};
  bool found{false};
  bool approximate{false};
  std::string error;
};

// Viewer scratch is a deliberate Xbox-RAM budget, not a sample-count limit.
// The loader downsamples deterministically if the selected record exceeds it.
constexpr size_t kResultViewerSampleScratchBytes = 512U * 1024U;

// Read-only, completed regression reference shipped in the XISO resource root.
const char *BundledReferenceResultsPath();
bool HasBundledReferenceResults();

// Moves the prior results file into the history directory. History is not
// pruned automatically: deleting benchmark evidence requires an explicit host
// or console-storage decision, not an arbitrary retention magic number.
bool ArchiveCurrentResults(const std::string &output_directory, std::string &error);

// Returns current results first, followed by archived runs newest-name first.
std::vector<std::string> DiscoverStoredResults(const std::string &output_directory);

// Streams one result file. Memory use scales with record count, not file size.
StoredResultFile ReadStoredResults(const std::string &path);

// Rescans one file and loads only the selected record's raw samples. This keeps
// menu memory proportional to one record instead of the complete run.
StoredResultSamples ReadStoredResultSamples(
    const std::string &path, const std::string &stable_id,
    size_t scratch_budget_bytes = kResultViewerSampleScratchBytes);

#endif  // XEMU_PERF_TESTS_RESULT_STORE_H
