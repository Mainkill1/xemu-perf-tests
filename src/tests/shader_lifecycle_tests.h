#ifndef XEMU_PERF_TESTS_SHADER_LIFECYCLE_TESTS_H
#define XEMU_PERF_TESTS_SHADER_LIFECYCLE_TESTS_H

#include "test_suite.h"

/**
 * Deterministic, xemu-focused workloads for shader and pipeline lifecycle
 * qualification. The first slice varies complete pipeline state while holding
 * shader state fixed.
 */
class ShaderLifecycleTests : public TestSuite {
 public:
  ShaderLifecycleTests(TestHost &host, std::string output_dir,
                       const Config &config);

 private:
  void RunPipelineScenario(const char *test_name, uint32_t variant_count,
                           uint32_t passes, bool uniform_only,
                           bool safe_omission);
  void ConfigureFixedShader() const;
  void DrawPipelineVariants(uint32_t variant_count, uint32_t passes,
                            bool uniform_only, bool safe_omission) const;
  void DrawVisibleSentinel() const;
  uint32_t ValidatePipelineVariants(uint32_t variant_count,
                                    bool safe_omission) const;
  void RunReadinessScenario(const char *test_name, uint32_t passes,
                            bool uniform_only);
  void ConfigureReadinessCombiner(uint32_t variant) const;
  void DrawReadinessFamilies(uint32_t passes, bool uniform_only) const;
  void DrawReadinessTile(TestHost::DrawPrimitive primitive, float left,
                         float top, float width, float height) const;
  uint32_t ValidateReadinessFamilies(bool uniform_only) const;
};

#endif  // XEMU_PERF_TESTS_SHADER_LIFECYCLE_TESTS_H
