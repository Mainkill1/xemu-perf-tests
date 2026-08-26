#ifndef XEMU_PERF_TESTS_PFIFO_ARRAY_ELEMENT_TESTS_H
#define XEMU_PERF_TESTS_PFIFO_ARRAY_ELEMENT_TESTS_H

#include <memory>
#include <vector>

#include "test_suite.h"

namespace PBKitPlusPlus {
class VertexBuffer;
}

/**
 * Deterministic non-incrementing ARRAY_ELEMENT packet workloads reduced from
 * Morrowind/PGR2 trace shapes. These are regression capsules, not hardware
 * conformance tests, until their output is captured on a retail Xbox.
 */
class PfifoArrayElementTests : public TestSuite {
 public:
  PfifoArrayElementTests(TestHost &host, std::string output_dir,
                         const Config &config);

  void Initialize() override;
  void Deinitialize() override;

 private:
  enum class ElementWidth {
    BITS_16,
    BITS_32,
  };

  struct Recipe {
    const char *test_name;
    ElementWidth element_width;
    uint32_t packet_words;
    uint32_t index_count;
    uint32_t index_kat;
    uint32_t payload_kat;
    uint32_t pixel_kat;
    uint32_t phase;
    uint32_t final_frame_color;
    uint64_t final_frame_hash;
  };

  void Run(const Recipe &recipe);
  void SubmitPackets(const Recipe &recipe) const;
  uint32_t ValidateRenderedTiles(const Recipe &recipe) const;

  std::shared_ptr<PBKitPlusPlus::VertexBuffer> vertex_buffer_;
  std::vector<uint32_t> indices_;
  std::vector<uint32_t> payload16_morrowind_;
  std::vector<uint32_t> payload16_pgr2_;
  uint32_t vertex_input_kat_{0};
};

#endif  // XEMU_PERF_TESTS_PFIFO_ARRAY_ELEMENT_TESTS_H
