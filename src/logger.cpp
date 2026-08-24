#include "logger.h"

#include "debug_output.h"

Logger* Logger::singleton_ = nullptr;

Logger::Logger(const std::string& log_path, bool truncate_log)
    : log_path_(log_path),
      log_file_(log_path, truncate_log ? std::ios_base::trunc : std::ios_base::app) {
  const char* p = log_path.c_str();
  PrintMsg("Opening log file at %s\n", p);
  ASSERT(log_file_ && "Failed to open log file for output");
}

void Logger::Initialize(const std::string& log_path, bool truncate_log) {
  ASSERT(!singleton_ && "Invalid attempt to initialize logger twice.");

  singleton_ = new Logger(log_path, truncate_log);
}

std::ofstream& Logger::Log() {
  ASSERT(singleton_ && "Attempt to use Logger before Initialize");
  ASSERT(singleton_->log_file_ && "Result log is not writable");
  return singleton_->log_file_;
}
