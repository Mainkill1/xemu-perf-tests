#ifndef XEMU_PERF_TESTS_TEST_HOST_H
#define XEMU_PERF_TESTS_TEST_HOST_H

#include <cstdint>
#include <string>

#include "nv2astate.h"

/**
 * Provides utility methods for use by TestSuite subclasses.
 */
class TestHost : public PBKitPlusPlus::NV2AState {
 public:
  enum class GpuCompletionMode {
    ENQUEUE,
    BATCH_COMPLETE,
    PER_ITERATION,
  };

  struct ProfileResults {
    uint32_t iterations;
    uint32_t warmup_iterations;
    uint32_t total_time_microseconds;
    uint32_t average_time_microseconds;
    uint32_t maximum_time_microseconds;
    uint32_t minimum_time_microseconds;
    uint32_t completion_wait_microseconds;
    std::vector<uint32_t> raw_results;
  };

 public:
  TestHost(uint32_t framebuffer_width, uint32_t framebuffer_height, uint32_t max_texture_width = 256,
           uint32_t max_texture_height = 256, uint32_t max_texture_depth = 4);

  //! Creates the given directory if it does not already exist.
  static void EnsureFolderExists(const std::string &folder_path);

  //! Renders test results and swaps back buffer.
  void FinishDraw(const std::string &suite_name, const std::string &test_name, const ProfileResults &results);

  //! Sets up the projection matrix for passthrough operation / direct addressing of pixels.
  void SetupFixedFunctionPassthrough();

  [[nodiscard]] bool GetSaveResults() const { return save_results_; }
  void SetSaveResults(bool enable = true) { save_results_ = enable; }

  [[nodiscard]] GpuCompletionMode GetGpuCompletionMode() const { return gpu_completion_mode_; }
  void SetGpuCompletionMode(GpuCompletionMode mode) { gpu_completion_mode_ = mode; }
  [[nodiscard]] const char *GetGpuCompletionModeName() const;

  [[nodiscard]] uint32_t GetWarmupIterations() const { return warmup_iterations_; }
  void SetWarmupIterations(uint32_t iterations) { warmup_iterations_ = iterations; }

  [[nodiscard]] uint32_t GetMeasurementIterationsMultiplier() const {
    return measurement_iterations_multiplier_;
  }
  void SetMeasurementIterationsMultiplier(uint32_t multiplier) {
    measurement_iterations_multiplier_ = multiplier;
  }

  void WaitForGpu() const;
  void ResetResultLogState() { first_result_ = true; }

  [[nodiscard]] const double &GetPerformanceCounterFrequency() const { return perf_counter_frequency_; }
  [[nodiscard]] uint32_t GetMicrosecondsSince(const LARGE_INTEGER &previous) const;

  void PreTest() {
    current_frame_index_ = 0;
    last_frame_time_.QuadPart = 0;
    average_frame_rate_ = 0.f;
    average_mspf_ = 0.f;
  }

 private:
  [[nodiscard]] uint64_t HashBackBuffer() const;

  bool save_results_{true};
  bool first_result_{true};
  GpuCompletionMode gpu_completion_mode_{GpuCompletionMode::ENQUEUE};
  uint32_t warmup_iterations_{0};
  uint32_t measurement_iterations_multiplier_{1};

  static constexpr auto kFrameTimeWindow = 10;
  double perf_counter_frequency_;
  LARGE_INTEGER last_frame_time_;
  uint32_t current_frame_index_ = 0;
  float frame_times_[kFrameTimeWindow] = {0.f};
  float average_frame_rate_ = 0.f;
  float average_mspf_ = 0.f;
};

void pb_print_with_floats(const char *format, ...);

#endif  // XEMU_PERF_TESTS_TEST_HOST_H
