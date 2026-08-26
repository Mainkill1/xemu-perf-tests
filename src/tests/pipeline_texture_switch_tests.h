#ifndef XEMU_PERF_TESTS_PIPELINE_TEXTURE_SWITCH_TESTS_H
#define XEMU_PERF_TESTS_PIPELINE_TEXTURE_SWITCH_TESTS_H

#include <cstdint>

#include "test_suite.h"

/**
 * Deterministic texture/sampler/address switching capsule plus a shader-state
 * negative control. All texture bytes are generated locally.
 */
class PipelineTextureSwitchTests : public TestSuite {
 public:
  PipelineTextureSwitchTests(TestHost &host, std::string output_dir,
                             const Config &config);

  void Initialize() override;

 private:
  struct Recipe {
    const char *test_name;
    uint32_t phase;
    bool shader_negative_control;
    uint32_t expected_pixel_kat;
    uint32_t final_frame_color;
    uint64_t final_frame_hash;
  };

  void Run(const Recipe &recipe);
  void ConfigureTexturePipeline() const;
  void RunIteration(const Recipe &recipe) const;
  uint32_t ValidatePixels(const Recipe &recipe) const;

  uint32_t backing_a_kat_{0};
  uint32_t backing_b_kat_{0};
  uint32_t input_kat_{0};
};

#endif  // XEMU_PERF_TESTS_PIPELINE_TEXTURE_SWITCH_TESTS_H
