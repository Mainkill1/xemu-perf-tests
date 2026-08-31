#ifndef XEMU_PERF_TESTS_RESULT_STORE_H
#define XEMU_PERF_TESTS_RESULT_STORE_H

#include <cstdint>
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
  bool has_measurement{false};
  bool oracle_failed{false};
};

struct StoredResultFile {
  std::string path;
  std::string label;
  std::string error;
  uint64_t size_bytes{0};
  bool complete{false};
  std::vector<StoredResultRecord> records;
};

// Moves the prior results file into the history directory. History is not
// pruned automatically: deleting benchmark evidence requires an explicit host
// or console-storage decision, not an arbitrary retention magic number.
bool ArchiveCurrentResults(const std::string &output_directory, std::string &error);

// Returns current results first, followed by archived runs newest-name first.
std::vector<std::string> DiscoverStoredResults(const std::string &output_directory);

// Streams one result file. Memory use scales with record count, not file size.
StoredResultFile ReadStoredResults(const std::string &path);

#endif  // XEMU_PERF_TESTS_RESULT_STORE_H
