#include "pfifo_packet_boundary_tests.h"

#include <pbkit/nv_regs.h>
#include <pbkit/pbkit.h>

#include <algorithm>
#include <array>
#include <sstream>

#include "debug_output.h"
#include "pushbuffer.h"
#include "test_host.h"

using namespace PBKitPlusPlus;

namespace {

static constexpr char kArray16Name[] = "pfifo.boundary-array-element16";
static constexpr char kArray32Name[] = "pfifo.boundary-array-element32";
static constexpr char kInlineArrayName[] = "pfifo.boundary-inline-array";
static constexpr char kIncrementingName[] = "pfifo.incrementing-inline-fallback";

// Mirrors xemu's guarded destination capacity. These tests are xemu-only and
// must not be run on physical hardware.
static constexpr uint32_t kXemuMaxBatchLength = 0x07FFFF;
static constexpr uint32_t kPacketChunkWords = 64;

void SynchronizeCorrectness(TestHost &host) {
  host.WaitForGpu();
  EmitXemuPerfMarker(kXemuPerfMarkerGpuComplete);
  host.WaitForGpu();
}

}  // namespace

PfifoPacketBoundaryTests::PfifoPacketBoundaryTests(
    TestHost &host, std::string output_dir, const Config &config)
    : TestSuite(host, std::move(output_dir), "PFIFOPacketBoundary", config) {
  static constexpr BoundaryRecipe kArray16Recipe{
      kArray16Name, NV097_ARRAY_ELEMENT16,
      (kXemuMaxBatchLength - 1) / 2, 1, NV097_ARRAY_ELEMENT32,
      0xFF341610, 0x4D1756526F052325ULL};
  static constexpr BoundaryRecipe kArray32Recipe{
      kArray32Name, NV097_ARRAY_ELEMENT32, kXemuMaxBatchLength - 1, 2,
      NV097_ARRAY_ELEMENT32, 0xFF343210, 0x6EB7071BE692A325ULL};
  static constexpr BoundaryRecipe kInlineArrayRecipe{
      kInlineArrayName, NV097_INLINE_ARRAY, kXemuMaxBatchLength - 1, 2,
      NV097_INLINE_ARRAY, 0xFF341810, 0x847DA1930526A325ULL};

  tests_[kArray16Name] = [this]() { RunBoundary(kArray16Recipe); };
  tests_[kArray32Name] = [this]() { RunBoundary(kArray32Recipe); };
  tests_[kInlineArrayName] = [this]() { RunBoundary(kInlineArrayRecipe); };
  tests_[kIncrementingName] = [this]() { RunIncrementingFallback(); };
}

void PfifoPacketBoundaryTests::PushPacket(uint32_t method, uint32_t words,
                                          uint32_t seed,
                                          bool non_incrementing) {
  ASSERT(words <= kPacketChunkWords);
  std::array<DWORD, kPacketChunkWords> payload{};
  for (uint32_t i = 0; i < words; ++i) {
    payload[i] = seed + i;
  }

  Pushbuffer::Begin();
  Pushbuffer::PushN(non_incrementing ? NV2A_SUPPRESS_COMMAND_INCREMENT(method)
                                     : method,
                    words, payload.data());
  Pushbuffer::End();
}

void PfifoPacketBoundaryTests::PushRepeated(uint32_t method, uint32_t words,
                                            uint32_t seed) {
  while (words) {
    const uint32_t count = std::min(words, kPacketChunkWords);
    PushPacket(method, count, seed, true);
    seed += count;
    words -= count;
  }
}

void PfifoPacketBoundaryTests::ResetInvalidPrimitiveState() {
  Pushbuffer::Begin();
  Pushbuffer::Push(NV097_SET_BEGIN_END, NV097_SET_BEGIN_END_OP_END);
  Pushbuffer::End(true);
}

uint64_t PfifoPacketBoundaryTests::HashBackBuffer() {
  static constexpr uint64_t kOffset = 14695981039346656037ULL;
  static constexpr uint64_t kPrime = 1099511628211ULL;
  const auto *base = reinterpret_cast<volatile const uint8_t *>(pb_back_buffer());
  const uint32_t pitch = pb_back_buffer_pitch();
  const uint32_t row_bytes = pb_back_buffer_width() * sizeof(uint32_t);
  const uint32_t height = pb_back_buffer_height();
  uint64_t hash = kOffset;
  for (uint32_t y = 0; y < height; ++y) {
    const auto *row = base + static_cast<size_t>(y) * pitch;
    for (uint32_t x = 0; x < row_bytes; ++x) {
      hash = (hash ^ row[x]) * kPrime;
    }
  }
  return hash;
}

void PfifoPacketBoundaryTests::RunBoundary(const BoundaryRecipe &recipe) {
  host_.PrepareDraw(0xFF101010);
  auto results = Profile(recipe.name, 1, [&]() {
    PushRepeated(recipe.method, recipe.fill_words, 0x01000000);

    // This batch crosses the capacity and must be rejected atomically.
    PushPacket(recipe.method, recipe.crossing_words, 0xA1000000);

    // If the crossing batch did not mutate state, this word reaches the exact
    // capacity. One further word must be rejected without terminating xemu.
    PushPacket(recipe.exact_tail_method, 1, 0xB2000000);
    PushPacket(recipe.exact_tail_method, 1, 0xC3000000);
    ResetInvalidPrimitiveState();
  });

  host_.PrepareDraw(recipe.final_color);
  SynchronizeCorrectness(host_);
  const uint64_t actual_hash = HashBackBuffer();
  AssertXemuPerfEqual(static_cast<uint32_t>(recipe.final_hash >> 32),
                      static_cast<uint32_t>(actual_hash >> 32),
                      XemuPerfAssertion::PFIFO_BOUNDARY_FRAMEBUFFER,
                      "pfifo_boundary_framebuffer_hash_hi == expected",
                      __FILE__, __LINE__);
  AssertXemuPerfEqual(static_cast<uint32_t>(recipe.final_hash),
                      static_cast<uint32_t>(actual_hash),
                      XemuPerfAssertion::PFIFO_BOUNDARY_FRAMEBUFFER,
                      "pfifo_boundary_framebuffer_hash_lo == expected",
                      __FILE__, __LINE__);

  std::ostringstream metadata;
  metadata << "{\"schema_version\":1,\"kind\":\"pfifo_boundary\",";
  metadata << "\"method\":" << recipe.method << ",";
  metadata << "\"capacity\":" << kXemuMaxBatchLength << ",";
  metadata << "\"fill_words\":" << recipe.fill_words << ",";
  metadata << "\"crossing_words\":" << recipe.crossing_words << ",";
  metadata << "\"exact_tail_words\":1,\"beyond_capacity_words\":1,";
  metadata << "\"expected_framebuffer_fnv1a64\":\"" << std::hex
           << recipe.final_hash << "\"}";

  host_.FinishDraw(suite_name_, recipe.name, results, metadata.str());
}

void PfifoPacketBoundaryTests::RunIncrementingFallback() {
  host_.PrepareDraw(0xFF101010);
  auto results = Profile(kIncrementingName, 1, []() {
    // INLINE_ARRAY is followed by SET_EYE_VECTOR in the incrementing method
    // range. xemu must consume only the first word through the scalar inline
    // fallback, then dispatch the second word at its incremented method.
    PushPacket(NV097_INLINE_ARRAY, 2, 0x3F800000, false);
    ResetInvalidPrimitiveState();
  });

  static constexpr uint32_t kFinalColor = 0xFF341C10;
  static constexpr uint64_t kFinalHash = 0x640439EE8ECD2325ULL;
  host_.PrepareDraw(kFinalColor);
  SynchronizeCorrectness(host_);
  const uint64_t actual_hash = HashBackBuffer();
  AssertXemuPerfEqual(static_cast<uint32_t>(kFinalHash >> 32),
                      static_cast<uint32_t>(actual_hash >> 32),
                      XemuPerfAssertion::PFIFO_BOUNDARY_FRAMEBUFFER,
                      "pfifo_incrementing_framebuffer_hash_hi == expected",
                      __FILE__, __LINE__);
  AssertXemuPerfEqual(static_cast<uint32_t>(kFinalHash),
                      static_cast<uint32_t>(actual_hash),
                      XemuPerfAssertion::PFIFO_BOUNDARY_FRAMEBUFFER,
                      "pfifo_incrementing_framebuffer_hash_lo == expected",
                      __FILE__, __LINE__);

  host_.FinishDraw(
      suite_name_, kIncrementingName, results,
      "{\"schema_version\":1,\"kind\":\"pfifo_incrementing_fallback\","
      "\"start_method\":6168,\"packet_words\":2,"
      "\"expected_first_method_consumed_words\":1,"
      "\"expected_framebuffer_fnv1a64\":\"640439ee8ecd2325\"}");
}
