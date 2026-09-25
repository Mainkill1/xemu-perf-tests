#ifndef XEMU_PERF_TESTS_SHADER_LIFECYCLE_TESTS_H
#define XEMU_PERF_TESTS_SHADER_LIFECYCLE_TESTS_H

#include "test_suite.h"

/** Deterministic, xemu-focused learned-fallback readiness workloads. */
class ShaderLifecycleTests : public TestSuite {
 public:
  ShaderLifecycleTests(TestHost &host, std::string output_dir,
                       const Config &config);

 private:
  void ConfigureFixedShader() const;
  void RunReadinessScenario(const char *test_name, uint32_t passes,
                            bool uniform_only,
                            uint32_t interpass_delay_ms = 0);
  void ConfigureReadinessCombiner(uint32_t variant) const;
  void DrawReadinessFamilies(uint32_t passes, bool uniform_only,
                             uint32_t interpass_delay_ms) const;
  void DrawReadinessTile(TestHost::DrawPrimitive primitive, float left,
                         float top, float width, float height) const;
  uint32_t ValidateReadinessFamilies(uint32_t passes,
                                     bool uniform_only) const;
};

#endif  // XEMU_PERF_TESTS_SHADER_LIFECYCLE_TESTS_H
