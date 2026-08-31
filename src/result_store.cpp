#include "result_store.h"

#include <algorithm>
#include <cstdio>
#include <fstream>
#include <functional>

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wmacro-redefined"
#include <windows.h>
#pragma clang diagnostic pop

namespace {

constexpr const char *kResultsFileName = "results.txt";
constexpr const char *kHistoryDirectoryName = "history";

std::string JoinPath(const std::string &directory, const std::string &name) {
  if (!directory.empty() && directory.back() == '\\') {
    return directory + name;
  }
  return directory + "\\" + name;
}

bool FileExists(const std::string &path) {
  const DWORD attributes = GetFileAttributes(path.c_str());
  return attributes != INVALID_FILE_ATTRIBUTES &&
         !(attributes & FILE_ATTRIBUTE_DIRECTORY);
}

std::string FileName(const std::string &path) {
  const auto slash = path.find_last_of("\\/");
  return slash == std::string::npos ? path : path.substr(slash + 1);
}

bool ExtractJsonString(const std::string &line, const char *key,
                       std::string &value) {
  const std::string prefix = std::string("    \"") + key + "\": \"";
  if (line.compare(0, prefix.size(), prefix) != 0) {
    return false;
  }
  const auto end = line.find('"', prefix.size());
  if (end == std::string::npos) {
    return false;
  }
  value = line.substr(prefix.size(), end - prefix.size());
  return true;
}

bool ExtractJsonUInt(const std::string &line, const char *key,
                     uint32_t &value) {
  const std::string prefix = std::string("    \"") + key + "\": ";
  if (line.compare(0, prefix.size(), prefix) != 0) {
    return false;
  }
  unsigned long parsed = 0;
  if (sscanf(line.c_str() + prefix.size(), "%lu", &parsed) != 1) {
    return false;
  }
  value = static_cast<uint32_t>(parsed);
  return true;
}

bool IsRecordStart(const std::string &line) {
  return line == "  {";
}

bool IsRecordEnd(const std::string &line) {
  return line == "  }" || line == "  },";
}

}  // namespace

bool ArchiveCurrentResults(const std::string &output_directory,
                           std::string &error) {
  const std::string current = JoinPath(output_directory, kResultsFileName);
  if (!FileExists(current)) {
    return true;
  }

  const std::string history =
      JoinPath(output_directory, kHistoryDirectoryName);
  if (!CreateDirectory(history.c_str(), nullptr) &&
      GetLastError() != ERROR_ALREADY_EXISTS) {
    error = "Could not create result history directory";
    return false;
  }

  SYSTEMTIME now{};
  GetLocalTime(&now);
  char base_name[64] = {};
  snprintf(base_name, sizeof(base_name),
           "results-%04u%02u%02u-%02u%02u%02u", now.wYear, now.wMonth,
           now.wDay, now.wHour, now.wMinute, now.wSecond);

  std::string destination = JoinPath(history, std::string(base_name) + ".txt");
  // Multiple runs may finish within one clock second. Search monotonically for
  // a free suffix instead of imposing an unexplained retry limit.
  uint32_t suffix = 1;
  while (FileExists(destination)) {
    char suffixed_name[80] = {};
    snprintf(suffixed_name, sizeof(suffixed_name), "%s-%lu.txt", base_name,
             static_cast<unsigned long>(suffix++));
    destination = JoinPath(history, suffixed_name);
  }

  if (!MoveFile(current.c_str(), destination.c_str())) {
    error = "Could not preserve previous results";
    return false;
  }
  return true;
}

std::vector<std::string> DiscoverStoredResults(
    const std::string &output_directory) {
  std::vector<std::string> paths;
  const std::string current = JoinPath(output_directory, kResultsFileName);
  if (FileExists(current)) {
    paths.push_back(current);
  }

  const std::string history =
      JoinPath(output_directory, kHistoryDirectoryName);
  const std::string pattern = JoinPath(history, "results-*.txt");
  WIN32_FIND_DATA find_data{};
  HANDLE find = FindFirstFile(pattern.c_str(), &find_data);
  if (find == INVALID_HANDLE_VALUE) {
    return paths;
  }

  std::vector<std::string> archived;
  do {
    if (!(find_data.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) {
      archived.push_back(JoinPath(history, find_data.cFileName));
    }
  } while (FindNextFile(find, &find_data));
  FindClose(find);

  std::sort(archived.begin(), archived.end(), std::greater<std::string>());
  paths.insert(paths.end(), archived.begin(), archived.end());
  return paths;
}

StoredResultFile ReadStoredResults(const std::string &path) {
  StoredResultFile result;
  result.path = path;
  result.label = FileName(path);

  std::ifstream input(path);
  if (!input) {
    result.error = "File unavailable";
    return result;
  }
  input.seekg(0, std::ios::end);
  const auto file_size = input.tellg();
  if (file_size >= 0) {
    result.size_bytes = static_cast<uint64_t>(file_size);
  }
  input.seekg(0, std::ios::beg);

  std::string line;
  std::string last_nonempty;
  bool in_record = false;
  StoredResultRecord record;
  while (std::getline(input, line)) {
    if (!line.empty() && line.back() == '\r') {
      line.pop_back();
    }
    if (line.find_first_not_of(" \t") != std::string::npos) {
      last_nonempty = line;
    }
    if (IsRecordStart(line)) {
      in_record = true;
      record = {};
      continue;
    }
    if (!in_record) {
      continue;
    }

    ExtractJsonString(line, "id", record.id);
    ExtractJsonString(line, "name", record.name);
    ExtractJsonString(line, "kind", record.kind);
    ExtractJsonString(line, "outcome", record.outcome);
    if (ExtractJsonUInt(line, "average_us", record.average_us)) {
      record.has_measurement = true;
    }
    ExtractJsonUInt(line, "min_us", record.minimum_us);
    ExtractJsonUInt(line, "max_us", record.maximum_us);
    if (line.find("\"oracle_status\":\"FAIL\"") != std::string::npos) {
      record.oracle_failed = true;
    }

    if (IsRecordEnd(line)) {
      if (record.outcome.empty()) {
        record.outcome = record.oracle_failed ? "FAIL" : "PASS";
      }
      result.records.push_back(record);
      in_record = false;
    }
  }
  result.complete = last_nonempty == "]";
  if (!input.eof()) {
    result.error = "Read error";
  }
  return result;
}
