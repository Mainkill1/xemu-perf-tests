#ifndef XEMU_PERF_TESTS_TEXTURE_CUBEMAP_FALLBACK_TESTS_H
#define XEMU_PERF_TESTS_TEXTURE_CUBEMAP_FALLBACK_TESTS_H

#include "test_suite.h"

class TextureCubemapFallbackTests : public TestSuite {
 public:
  TextureCubemapFallbackTests(TestHost &host, std::string output_dir,
                              const Config &config);

  void Initialize() override;
  void Deinitialize() override;

 private:
  void RunSubblockDxt1();
};

#endif  // XEMU_PERF_TESTS_TEXTURE_CUBEMAP_FALLBACK_TESTS_H
