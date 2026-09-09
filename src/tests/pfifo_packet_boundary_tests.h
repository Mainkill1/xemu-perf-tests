#ifndef XEMU_PERF_TESTS_PFIFO_PACKET_BOUNDARY_TESTS_H
#define XEMU_PERF_TESTS_PFIFO_PACKET_BOUNDARY_TESTS_H

#include "test_suite.h"

class PfifoPacketBoundaryTests : public TestSuite {
 public:
  PfifoPacketBoundaryTests(TestHost &host, std::string output_dir,
                           const Config &config);

 private:
  struct BoundaryRecipe {
    const char *name;
    uint32_t method;
    uint32_t fill_words;
    uint32_t crossing_words;
    uint32_t exact_tail_method;
    uint32_t final_color;
    uint64_t final_hash;
  };

  void RunBoundary(const BoundaryRecipe &recipe);
  void RunIncrementingFallback();
  static void PushRepeated(uint32_t method, uint32_t words,
                           uint32_t seed);
  static void PushPacket(uint32_t method, uint32_t words, uint32_t seed,
                         bool non_incrementing = true);
  static void ResetInvalidPrimitiveState();
  static uint64_t HashBackBuffer();
};

#endif  // XEMU_PERF_TESTS_PFIFO_PACKET_BOUNDARY_TESTS_H
