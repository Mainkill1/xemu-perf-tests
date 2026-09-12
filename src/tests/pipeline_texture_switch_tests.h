#ifndef XEMU_PERF_TESTS_PIPELINE_TEXTURE_SWITCH_TESTS_H
#define XEMU_PERF_TESTS_PIPELINE_TEXTURE_SWITCH_TESTS_H

#include <cstdint>
#include <pbkit/pbkit.h>

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
  void SetupTest() override;

 private:
  struct Recipe {
    const char *test_name;
    uint32_t phase;
    bool shader_negative_control;
    bool sampler_only_identity;
    uint32_t expected_pixel_kat;
    uint32_t final_frame_color;
    uint64_t final_frame_hash;
  };

  void Run(const Recipe &recipe);
  void RunClearTextureNormal();
  void RunPaletteOnlyUpdate();
  void RunSharedPageOverlap();
  void RunTextureDmaRemap();
  void RunPaletteDmaRemap();
  void ResetCanonicalTextureBacking() const;
  void ConfigureTexturePipeline() const;
  void ConfigurePalettePipeline() const;
  void ConfigureSamplerIdentityPipeline() const;
  void RunIteration(const Recipe &recipe) const;
  void RunClearTextureNormalIteration() const;
  uint32_t ValidatePixels(const Recipe &recipe) const;
  uint32_t ValidateClearTextureNormalPixels() const;
  uint32_t ValidateSolidTilePixels(uint32_t expected,
                                   const char *message) const;

  uint32_t backing_a_kat_{0};
  uint32_t backing_b_kat_{0};
  uint32_t input_kat_{0};
  uint32_t sampler_backing_kat_{0};
  uint32_t sampler_input_kat_{0};
  s_CtxDma texture_dma_red_{};
  s_CtxDma texture_dma_blue_{};
  s_CtxDma texture_dma_green_{};
  s_CtxDma palette_dma_red_{};
  s_CtxDma palette_dma_blue_{};
};

#endif  // XEMU_PERF_TESTS_PIPELINE_TEXTURE_SWITCH_TESTS_H
