#include "test_host.h"

#include <SDL.h>
#include <cstddef>
#include <cstdio>
#include <strings.h>

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wignored-attributes"
#include <hal/debug.h>
#pragma clang diagnostic pop

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wmacro-redefined"
#include <windows.h>
#pragma clang diagnostic pop

#include <texture_generator.h>
#include <pbkit/pbkit.h>
#include <xboxkrnl/xboxkrnl.h>

#include "debug_output.h"
#include "logger.h"
#include "test_catalog.h"
#include "shaders/vertex_shader_program.h"
#include "xbox_math_matrix.h"
#include "xbox_math_types.h"

using namespace XboxMath;

static constexpr uint32_t kResultsOverlayColor = 0x88000000;
static constexpr uint32_t kTextBackingColor = 0xDD000000;

static bool MetadataReportsOracleFailure(const std::string &metadata_json) {
  return metadata_json.find("\"oracle_status\":\"FAIL\"") != std::string::npos;
}

static const char *ResultOutcome(const std::string &metadata_json) {
  return XemuPerfTestFailed() || MetadataReportsOracleFailure(metadata_json)
             ? "FAIL"
             : "PASS";
}

#define MAX_FILE_PATH_SIZE 248
#define MAX_FILENAME_SIZE 42

TestHost::TestHost(uint32_t framebuffer_width, uint32_t framebuffer_height, uint32_t max_texture_width,
                   uint32_t max_texture_height, uint32_t max_texture_depth)
    : NV2AState(framebuffer_width, framebuffer_height, max_texture_width, max_texture_height, max_texture_depth) {
  LARGE_INTEGER frequency;
  QueryPerformanceFrequency(&frequency);
  perf_counter_frequency_ = static_cast<double>(frequency.QuadPart);
  QueryPerformanceCounter(&last_frame_time_);
}

void TestHost::DrawResultsOverlay() {
  SetVertexShaderProgram(nullptr);
  SetXDKDefaultViewportAndFixedFunctionMatrices();

  SetBlend();
  SetFinalCombiner0Just(SRC_DIFFUSE);
  SetFinalCombiner1Just(SRC_DIFFUSE, true);

  Begin(TestHost::PRIMITIVE_QUADS);
  SetDiffuse(kResultsOverlayColor);
  SetScreenVertex(0.f, 0.f);
  SetScreenVertex(GetFramebufferWidthF(), 0.f);
  SetScreenVertex(GetFramebufferWidthF(), GetFramebufferHeightF());
  SetScreenVertex(0.f, GetFramebufferHeightF());
  End();
}

void TestHost::DrawTextBacking(uint32_t row_count) {
  // pbkit text starts at (20, 25), advances 25 pixels per row, and is at
  // most 60 columns wide. A small padded backing keeps white text readable
  // over bright test output without clearing or flashing the whole frame.
  constexpr float kLeft = 16.f;
  constexpr float kTop = 20.f;
  constexpr float kWidth = 608.f;
  constexpr float kRowHeight = 25.f;

  SetVertexShaderProgram(nullptr);
  SetXDKDefaultViewportAndFixedFunctionMatrices();
  SetBlend();
  SetFinalCombiner0Just(SRC_DIFFUSE);
  SetFinalCombiner1Just(SRC_DIFFUSE, true);

  const float bottom = kTop + kRowHeight * static_cast<float>(row_count);
  Begin(TestHost::PRIMITIVE_QUADS);
  SetDiffuse(kTextBackingColor);
  SetScreenVertex(kLeft, kTop);
  SetScreenVertex(kLeft + kWidth, kTop);
  SetScreenVertex(kLeft + kWidth, bottom);
  SetScreenVertex(kLeft, bottom);
  End();
}

void TestHost::PrintLastResult() {
  if (result_display_kind_ == ResultDisplayKind::NONE) {
    return;
  }

  pb_print("%s::%s\n", result_display_suite_.c_str(),
           result_display_test_.c_str());
  if (result_display_kind_ == ResultDisplayKind::GROUP) {
    pb_print("  PASS (%lu child results; no group timing)\n",
             result_display_child_count_);
    return;
  }

  auto micro_to_milliseconds = [](uint32_t microseconds) -> double {
    return static_cast<double>(microseconds) / 1000.0;
  };
  if (save_results_) {
    pb_print("  %lu iterations\n", result_display_profile_.iterations);
    pb_print_with_floats(
        "  Total: %f ms\n",
        micro_to_milliseconds(result_display_profile_.total_time_microseconds));
    pb_print_with_floats(
        "  Avg: %f ms\n",
        micro_to_milliseconds(result_display_profile_.average_time_microseconds));
    pb_print_with_floats(
        "  Min: %f ms\n",
        micro_to_milliseconds(result_display_profile_.minimum_time_microseconds));
    pb_print_with_floats(
        "  Max: %f ms\n",
        micro_to_milliseconds(result_display_profile_.maximum_time_microseconds));
  } else {
    pb_print("Continuous mode: saving disabled\n");
    pb_print_with_floats("Average FPS: %f\n", average_frame_rate_);
    pb_print_with_floats("Average MSPF: %f\n", average_mspf_);
  }
}

void TestHost::ShowResultProgress(const std::string &activity) {
  if (result_display_kind_ == ResultDisplayKind::NONE) {
    debugClearScreen();
    debugPrint("RUNNING\n\n%s\n", activity.c_str());
    pb_show_debug_screen();
    PrintMsg("RUNNING_PROGRESS %s\n", activity.c_str());
    return;
  }

  // Rebuild the text buffer and draw it directly over the existing render
  // buffer. Do not clear or darken the whole frame between tests.
  pb_erase_text_screen();
  PrintLastResult();
  pb_print("\nRUNNING: %s\n", activity.c_str());
  DrawTextBacking(result_display_kind_ == ResultDisplayKind::GROUP ? 4 : 8);
  pb_draw_text_screen();
  NV2AState::FinishDraw();
  PrintMsg("RUNNING_PROGRESS %s\n", activity.c_str());
}

void TestHost::EnsureFolderExists(const std::string &folder_path) {
  if (folder_path.length() > MAX_FILE_PATH_SIZE) {
    ASSERT(!"Folder Path is too long.");
  }

  char buffer[MAX_FILE_PATH_SIZE + 1] = {0};
  const char *path_start = folder_path.c_str();
  const char *slash = strchr(path_start, '\\');
  slash = strchr(slash + 1, '\\');

  while (slash) {
    strncpy(buffer, path_start, slash - path_start);
    if (!CreateDirectory(buffer, nullptr) && GetLastError() != ERROR_ALREADY_EXISTS) {
      ASSERT(!"Failed to create output directory.");
    }

    slash = strchr(slash + 1, '\\');
  }

  // Handle case where there was no trailing slash.
  if (!CreateDirectory(path_start, nullptr) && GetLastError() != ERROR_ALREADY_EXISTS) {
    ASSERT(!"Failed to create output directory.");
  }
}

void TestHost::FinishDraw(const std::string &suite_name, const std::string &test_name,
                          const ProfileResults &results, const std::string &metadata_json) {
  // Validation is deliberately outside the measured region. Waiting here
  // makes the CPU read deterministic even when the selected measurement mode
  // only times enqueue work.
  WaitForGpu();
  const uint64_t framebuffer_hash = HashBackBuffer();
  char framebuffer_hash_string[17] = {};
  snprintf(framebuffer_hash_string, sizeof(framebuffer_hash_string), "%016llx",
           static_cast<unsigned long long>(framebuffer_hash));
  PrintMsg("CORRECTNESS_HASH %s::%s fnv1a64=%s\n", suite_name.c_str(), test_name.c_str(),
           framebuffer_hash_string);

  DrawResultsOverlay();

  result_display_kind_ = ResultDisplayKind::PROFILE;
  result_display_suite_ = suite_name;
  result_display_test_ = test_name;
  result_display_profile_ = results;
  pb_erase_text_screen();
  PrintLastResult();

  DrawTextBacking(7);
  pb_draw_text_screen();

  NV2AState::FinishDraw();

  if (save_results_) {
    const auto *descriptor = RecordDescriptor(suite_name, test_name, false);
    if (MetadataReportsOracleFailure(metadata_json)) {
      ++oracle_failure_count_;
      if (first_oracle_failure_.empty()) {
        first_oracle_failure_ = std::string(descriptor->id);
      }
    }
    auto& log = Logger::Log();
    if (!first_result_) {
      log << "," << std::endl;
    }
    first_result_ = false;
    log << "  {" << std::endl;
    log << "    \"schema_version\": 1," << std::endl;
    log << R"(    "id": ")" << descriptor->id << "\"," << std::endl;
    log << "    \"revision\": " << descriptor->revision << "," << std::endl;
    log << "    \"kind\": \"leaf\"," << std::endl;
    log << R"(    "name": ")" << suite_name << "::" << test_name << "\"," << std::endl;
    log << R"(    "outcome": ")" << ResultOutcome(metadata_json) << "\"," << std::endl;
    log << "    \"iterations\": " << results.iterations << "," << std::endl;
    log << "    \"sample_count\": " << results.sample_count << "," << std::endl;
    log << "    \"measurement_iterations_multiplier\": "
        << results.measurement_iterations_multiplier << "," << std::endl;
    log << "    \"warmup_iterations\": " << results.warmup_iterations << "," << std::endl;
    log << R"(    "gpu_completion_mode": ")" << GetGpuCompletionModeName() << "\"," << std::endl;
    log << "    \"completion_wait_us\": " << results.completion_wait_microseconds << "," << std::endl;
    log << "    \"total_us\": " << results.total_time_microseconds << "," << std::endl;
    log << "    \"average_us\": " << results.average_time_microseconds << "," << std::endl;
    log << "    \"min_us\": " << results.minimum_time_microseconds << "," << std::endl;
    log << "    \"max_us\": " << results.maximum_time_microseconds << "," << std::endl;
    log << "    \"raw_results\": [";
    std::string separator;
    for (auto val : results.raw_results) {
      log << separator << std::endl;
      separator = ",";
      log << "      " << val;
    }
    log << std::endl;
    log << "    ]," << std::endl;
    log << R"(    "framebuffer_fnv1a64": ")" << framebuffer_hash_string << "\"";
    if (!metadata_json.empty()) {
      log << "," << std::endl;
      log << "    \"metadata\": " << metadata_json << std::endl;
    } else {
      log << std::endl;
    }
    log << "  }" << std::endl;
    log.flush();
    ASSERT(log && "Failed to write benchmark result");
  } else {
    LARGE_INTEGER now;
    QueryPerformanceCounter(&now);
    auto delta =
        static_cast<float>(static_cast<double>(now.QuadPart - last_frame_time_.QuadPart) / perf_counter_frequency_);
    last_frame_time_ = now;

    frame_times_[current_frame_index_] = delta;
    current_frame_index_ = (current_frame_index_ + 1) % kFrameTimeWindow;

    if (!current_frame_index_) {
      float sum = 0;
      for (float frame_time : frame_times_) {
        sum += frame_time;
      }

      float avg_delta = sum / kFrameTimeWindow;
      average_mspf_ = avg_delta * 1000.f;
      average_frame_rate_ = 1.0f / avg_delta;
    }
  }

  PrintMsg("TEST_END %s::%s\n", suite_name.c_str(), test_name.c_str());
}

void TestHost::RecordProfileResult(const std::string &suite_name, const std::string &test_name,
                                   const ProfileResults &results, const std::string &metadata_json) {
  if (!save_results_) {
    return;
  }
  WaitForGpu();
  const uint64_t framebuffer_hash = HashBackBuffer();
  char framebuffer_hash_string[17] = {};
  snprintf(framebuffer_hash_string, sizeof(framebuffer_hash_string), "%016llx",
           static_cast<unsigned long long>(framebuffer_hash));
  const auto *descriptor = RecordDescriptor(suite_name, test_name, false);
  if (MetadataReportsOracleFailure(metadata_json)) {
    ++oracle_failure_count_;
    if (first_oracle_failure_.empty()) {
      first_oracle_failure_ = std::string(descriptor->id);
    }
  }
  auto &log = Logger::Log();
  if (!first_result_) {
    log << "," << std::endl;
  }
  first_result_ = false;
  log << "  {" << std::endl;
  log << "    \"schema_version\": 1," << std::endl;
  log << R"(    "id": ")" << descriptor->id << "\"," << std::endl;
  log << "    \"revision\": " << descriptor->revision << "," << std::endl;
  log << "    \"kind\": \"leaf\"," << std::endl;
  log << R"(    "name": ")" << suite_name << "::" << test_name << "\"," << std::endl;
  log << R"(    "outcome": ")" << ResultOutcome(metadata_json) << "\"," << std::endl;
  log << "    \"iterations\": " << results.iterations << "," << std::endl;
  log << "    \"sample_count\": " << results.sample_count << "," << std::endl;
  log << "    \"measurement_iterations_multiplier\": "
      << results.measurement_iterations_multiplier << "," << std::endl;
  log << "    \"warmup_iterations\": " << results.warmup_iterations << "," << std::endl;
  log << R"(    "gpu_completion_mode": ")" << GetGpuCompletionModeName() << "\"," << std::endl;
  log << "    \"completion_wait_us\": " << results.completion_wait_microseconds << "," << std::endl;
  log << "    \"total_us\": " << results.total_time_microseconds << "," << std::endl;
  log << "    \"average_us\": " << results.average_time_microseconds << "," << std::endl;
  log << "    \"min_us\": " << results.minimum_time_microseconds << "," << std::endl;
  log << "    \"max_us\": " << results.maximum_time_microseconds << "," << std::endl;
  log << "    \"raw_results\": [";
  std::string separator;
  for (auto value : results.raw_results) {
    log << separator << std::endl;
    separator = ",";
    log << "      " << value;
  }
  log << std::endl;
  log << "    ]," << std::endl;
  log << R"(    "framebuffer_fnv1a64": ")" << framebuffer_hash_string << "\"";
  if (!metadata_json.empty()) {
    log << "," << std::endl;
    log << "    \"metadata\": " << metadata_json << std::endl;
  } else {
    log << std::endl;
  }
  log << "  }" << std::endl;
  log.flush();
  ASSERT(log && "Failed to write benchmark result");
}

void TestHost::FinishGroup(const std::string &suite_name, const std::string &group_name,
                           uint32_t child_result_count, const std::string &metadata_json) {
  WaitForGpu();
  const uint64_t framebuffer_hash = HashBackBuffer();
  char framebuffer_hash_string[17] = {};
  snprintf(framebuffer_hash_string, sizeof(framebuffer_hash_string), "%016llx",
           static_cast<unsigned long long>(framebuffer_hash));
  PrintMsg("CORRECTNESS_HASH %s::%s fnv1a64=%s kind=group\n",
           suite_name.c_str(), group_name.c_str(), framebuffer_hash_string);
  const TestDescriptor *descriptor = nullptr;
  if (save_results_) {
    descriptor = RecordDescriptor(suite_name, group_name, true);
  }

  DrawResultsOverlay();
  result_display_kind_ = ResultDisplayKind::GROUP;
  result_display_suite_ = suite_name;
  result_display_test_ = group_name;
  result_display_child_count_ = child_result_count;
  pb_erase_text_screen();
  PrintLastResult();
  pb_draw_text_screen();
  NV2AState::FinishDraw();

  if (!save_results_) {
    PrintMsg("TEST_END %s::%s\n", suite_name.c_str(), group_name.c_str());
    return;
  }

  auto &log = Logger::Log();
  if (!first_result_) {
    log << "," << std::endl;
  }
  first_result_ = false;
  log << "  {" << std::endl;
  log << "    \"schema_version\": 1," << std::endl;
  log << R"(    "id": ")" << descriptor->id << "\"," << std::endl;
  log << "    \"revision\": " << descriptor->revision << "," << std::endl;
  log << "    \"kind\": \"group\"," << std::endl;
  log << R"(    "name": ")" << suite_name << "::" << group_name << "\"," << std::endl;
  log << R"(    "outcome": ")" << ResultOutcome(metadata_json) << "\"," << std::endl;
  log << "    \"child_result_count\": " << child_result_count << "," << std::endl;
  log << "    \"measurement\": null," << std::endl;
  // Keep the legacy numeric shape during migration, but explicitly mark it as
  // non-measurement data. Zeroes are never copied from the final child.
  log << "    \"iterations\": 0," << std::endl;
  log << "    \"sample_count\": 0," << std::endl;
  log << "    \"measurement_iterations_multiplier\": "
      << GetMeasurementIterationsMultiplier() << "," << std::endl;
  log << "    \"warmup_iterations\": " << GetWarmupIterations() << "," << std::endl;
  log << R"(    "gpu_completion_mode": ")" << GetGpuCompletionModeName() << "\"," << std::endl;
  log << "    \"completion_wait_us\": 0," << std::endl;
  log << "    \"total_us\": 0," << std::endl;
  log << "    \"average_us\": 0," << std::endl;
  log << "    \"min_us\": 0," << std::endl;
  log << "    \"max_us\": 0," << std::endl;
  log << "    \"raw_results\": []," << std::endl;
  log << R"(    "framebuffer_fnv1a64": ")" << framebuffer_hash_string << "\"";
  if (!metadata_json.empty()) {
    log << "," << std::endl << "    \"metadata\": " << metadata_json << std::endl;
  } else {
    log << std::endl;
  }
  log << "  }" << std::endl;
  log.flush();
  ASSERT(log && "Failed to write group outcome");
  PrintMsg("TEST_END %s::%s\n", suite_name.c_str(), group_name.c_str());
}

void TestHost::RecordSoftTestOutcome(const std::string &suite_name,
                                     const std::string &test_name,
                                     bool failed) {
  if (!failed) {
    return;
  }
  ++soft_failure_count_;
  if (!first_soft_failure_.empty()) {
    return;
  }
  const auto *descriptor =
      FindTestDescriptorByLegacyResult(suite_name, test_name);
  first_soft_failure_ = descriptor
                            ? descriptor->id
                            : suite_name + "::" + test_name;
}

void TestHost::ConfigureResolvedPlan(const std::string &plan_id,
                                     const std::set<std::string> &selected_test_ids) {
  plan_id_ = plan_id;
  selected_test_ids_ = selected_test_ids;
  emitted_test_ids_.clear();
  unexpected_or_duplicate_result_ = false;
}

const TestDescriptor *TestHost::RecordDescriptor(const std::string &suite_name,
                                                 const std::string &test_name,
                                                 bool expect_group) {
  const auto *descriptor = FindTestDescriptorByLegacyResult(suite_name, test_name);
  ASSERT(descriptor && "Result is missing from the generated test catalog");
  ASSERT((descriptor->kind == TestKind::GROUP) == expect_group);
  if (expect_group) {
    ++recorded_group_count_;
  } else {
    ++recorded_leaf_count_;
  }
  if (!expect_group && !plan_id_.empty()) {
    if (!selected_test_ids_.count(descriptor->id) ||
        !emitted_test_ids_.insert(descriptor->id).second) {
      unexpected_or_duplicate_result_ = true;
    }
  }
  return descriptor;
}

bool TestHost::ValidateResolvedPlan(std::string &error) const {
  if (plan_id_.empty()) {
    return true;
  }
  if (unexpected_or_duplicate_result_) {
    error = "resolved plan emitted an unexpected or duplicate leaf result";
    return false;
  }
  if (emitted_test_ids_ != selected_test_ids_) {
    error = "resolved plan leaf completion set does not match selected leaf ids";
    return false;
  }
  return true;
}

const char *TestHost::GetGpuCompletionModeName() const {
  switch (gpu_completion_mode_) {
    case GpuCompletionMode::ENQUEUE:
      return "enqueue";
    case GpuCompletionMode::BATCH_COMPLETE:
      return "batch_complete";
    case GpuCompletionMode::PER_ITERATION:
      return "per_iteration";
  }
  return "unknown";
}

void TestHost::WaitForGpu() const {
  while (pb_busy()) {
  }
  pb_wait_until_gr_not_busy();
}

uint64_t TestHost::HashBackBuffer() const {
  static constexpr uint64_t kFnvOffsetBasis = 14695981039346656037ULL;
  static constexpr uint64_t kFnvPrime = 1099511628211ULL;

  const auto *base = reinterpret_cast<const uint8_t *>(pb_back_buffer());
  const uint32_t pitch = pb_back_buffer_pitch();
  const uint32_t row_bytes = pb_back_buffer_width() * sizeof(uint32_t);
  const uint32_t height = pb_back_buffer_height();
  uint64_t hash = kFnvOffsetBasis;
  for (uint32_t y = 0; y < height; ++y) {
    const auto *row = base + static_cast<size_t>(y) * pitch;
    for (uint32_t x = 0; x < row_bytes; ++x) {
      hash ^= row[x];
      hash *= kFnvPrime;
    }
  }
  return hash;
}

void TestHost::SetupFixedFunctionPassthrough() {
  SetVertexShaderProgram(nullptr);
  SetWindowClip(GetFramebufferWidth(), GetFramebufferHeight());
  SetViewportOffset(0, 0, 0, 0);
  SetViewportScale(1.f, 1.f, 1.f, 1.f);

  matrix4_t matrix;
  MatrixSetIdentity(matrix);
  SetFixedFunctionModelViewMatrix(matrix);
  SetFixedFunctionProjectionMatrix(matrix);
}

void pb_print_with_floats(const char *format, ...) {
  char buffer[512];

  va_list argList;
  va_start(argList, format);
  vsnprintf_(buffer, 512, format, argList);
  va_end(argList);

  char *str = buffer;
  while (*str != 0) {
    pb_print_char(*str++);
  }
}

[[nodiscard]] uint32_t TestHost::GetMicrosecondsSince(const LARGE_INTEGER &previous) const {
  LARGE_INTEGER now;
  QueryPerformanceCounter(&now);

  double delta = (double)(now.QuadPart - previous.QuadPart) / perf_counter_frequency_;
  return static_cast<uint32_t>(delta * 1000000.f);
  ;
}
