#ifndef XEMU_PERF_TESTS_TEST_SUITE_H
#define XEMU_PERF_TESTS_TEST_SUITE_H

#include <chrono>
#include <array>
#include <limits>
#include <functional>
#include <map>
#include <set>
#include <string>
#include <vector>

#include "test_host.h"

/**
 * Base class for all test suites.
 */
class TestSuite {
 public:
  //! Runtime configuration for TestSuites.
  struct Config {
    static constexpr uint32_t kGameLoadCompositeStageCount = 6;
    static constexpr uint32_t kAllGameLoadCompositeStages =
        (1U << kGameLoadCompositeStageCount) - 1;
    static constexpr uint32_t kGameLoadCompositeCrossTitleStageCount = 11;
    static constexpr uint32_t kAllGameLoadCompositeCrossTitleStages =
        (1U << kGameLoadCompositeCrossTitleStageCount) - 1;
    static constexpr uint32_t kGameLoadCompositeS3tcSyncFactorStageCount = 12;
    static constexpr uint32_t kAllGameLoadCompositeS3tcSyncFactorStages =
        (1U << kGameLoadCompositeS3tcSyncFactorStageCount) - 1;

    // Zero multiplier inherits the global setting. UINT32_MAX warmup inherits
    // the global setting, allowing an explicit per-stage zero warmup.
    uint32_t game_load_composite_stage_mask{kAllGameLoadCompositeStages};
    std::array<uint32_t, kGameLoadCompositeStageCount>
        game_load_composite_stage_multipliers{};
    std::array<uint32_t, kGameLoadCompositeStageCount>
        game_load_composite_stage_warmups{
            std::numeric_limits<uint32_t>::max(), std::numeric_limits<uint32_t>::max(),
            std::numeric_limits<uint32_t>::max(), std::numeric_limits<uint32_t>::max(),
            std::numeric_limits<uint32_t>::max(), std::numeric_limits<uint32_t>::max()};
    uint32_t game_load_composite_gpu_precondition_alpha_draws{8192};
    uint32_t game_load_composite_cross_title_stage_mask{
        kAllGameLoadCompositeCrossTitleStages};
    uint32_t game_load_composite_s3tc_sync_factor_stage_mask{
        kAllGameLoadCompositeS3tcSyncFactorStages};
    bool game_load_composite_cross_title_fast_smoke{false};
  };

 public:
  TestSuite() = delete;
  TestSuite(TestHost &host, std::string output_dir, std::string suite_name, const Config &config);
  virtual ~TestSuite() = default;

  [[nodiscard]] const std::string &Name() const { return suite_name_; };

  //! Called to initialize the test suite.
  virtual void Initialize();

  //! Called to tear down the test suite.
  virtual void Deinitialize() {}

  //! Called before running an individual test within this suite.
  //! In multiframe mode, this will be called each frame.
  virtual void SetupTest() {}

  //! Called after running an individual test within this suite.
  //! In multiframe mode, this will be called each frame.
  virtual void TearDownTest() {}

  void DisableTests(const std::set<std::string> &tests_to_skip);

  [[nodiscard]] std::vector<std::string> TestNames() const;
  [[nodiscard]] bool HasTest(const std::string &test_name) const {
    return tests_.find(test_name) != tests_.end();
  }
  [[nodiscard]] bool HasEnabledTests() const { return !tests_.empty(); };

  void Run(const std::string &test_name, uint32_t frame_count);

  void RunAll();

  //! General purpose +1/-1 callback allowing user interaction via the left/right DPAD.
  virtual void UpdateUserContext(int direction) {};

 protected:
  //! Runs the given body function a number of times and calculates profiling information.
  TestHost::ProfileResults Profile(const std::string &test_name, uint32_t num_iterations,
                                   const std::function<void(void)> &body) const;
  void SetDefaultTextureFormat() const;

 protected:
  TestHost &host_;
  std::string output_dir_;
  std::string suite_name_;

  // Map of `test_name` to `void test()`
  std::map<std::string, std::function<void(void)>> tests_{};
};

#endif  // XEMU_PERF_TESTS_TEST_SUITE_H
