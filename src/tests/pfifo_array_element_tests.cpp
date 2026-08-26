#include "pfifo_array_element_tests.h"

#include <pbkit/nv_regs.h>
#include <pbkit/pbkit.h>

#include <array>
#include <cstddef>
#include <sstream>

#include "debug_output.h"
#include "pushbuffer.h"
#include "shaders/passthrough_vertex_shader.h"
#include "test_host.h"
#include "vertex_buffer.h"

using namespace PBKitPlusPlus;

namespace {

static constexpr char kArrayElement16Name[] = "pfifo.array-element16";
static constexpr char kArrayElement32Name[] = "pfifo.array-element32";
static constexpr char kArrayElementPgr2Name[] = "pfifo.array-element-pgr2";

static constexpr uint32_t kSeed = 0x50464946;  // "PFIF"
static constexpr uint32_t kFnvOffsetBasis = 2166136261U;
static constexpr uint32_t kFnvPrime = 16777619U;
static constexpr uint32_t kProfileSamples = 8;
static constexpr uint32_t kPacketsPerIteration = 256;
static constexpr uint32_t kMorrowindPacketWords = 38;
static constexpr uint32_t kPgr2PacketWords = 29;
static constexpr uint32_t kMorrowindIndexCount = kMorrowindPacketWords * 2;
static constexpr uint32_t kPgr2IndexCount = kPgr2PacketWords * 2;
static constexpr uint32_t kTileCount = kMorrowindIndexCount / 4;
static constexpr uint32_t kVertexAttributes = TestHost::POSITION | TestHost::DIFFUSE;
static constexpr uint32_t kBackgroundColor = 0xFF111820;

// These are independently reproduced in tests/test_pfifo_array_element_contract.py.
static constexpr uint32_t kVertexInputKat = 0x576F9C60;
static constexpr uint32_t kMorrowindIndexKat = 0x214ABD05;
static constexpr uint32_t kPgr2IndexKat = 0x33E7DBF4;
static constexpr uint32_t kMorrowind16PayloadKat = 0x38503435;
static constexpr uint32_t kMorrowind32PayloadKat = 0x214ABD05;
static constexpr uint32_t kPgr2PayloadKat = 0x555DCC3C;
static constexpr uint32_t kMorrowindPixelKat = 0x8F69B3C6;
static constexpr uint32_t kPgr2PixelKat = 0x18D08B94;

static constexpr uint32_t kMorrowind16FinalColor = 0xFF163826;
static constexpr uint32_t kMorrowind32FinalColor = 0xFF32764C;
static constexpr uint32_t kPgr2FinalColor = 0xFF291D52;
static constexpr uint64_t kMorrowind16FinalFrameHash = 0x9C884DE2A5D32325ULL;
static constexpr uint64_t kMorrowind32FinalFrameHash = 0xE079F0CF1A994325ULL;
static constexpr uint64_t kPgr2FinalFrameHash = 0xBBC8B0702FFD0325ULL;

uint32_t XorShift32(uint32_t &state) {
  state ^= state << 13;
  state ^= state >> 17;
  state ^= state << 5;
  return state;
}

uint32_t Fnv1aAddWord(uint32_t hash, uint32_t value) {
  for (uint32_t byte = 0; byte < 4; ++byte) {
    hash = (hash ^ static_cast<uint8_t>(value >> (byte * 8))) * kFnvPrime;
  }
  return hash;
}

uint32_t FoldKnownOutput(uint32_t state, uint32_t value) {
  return (state ^ value) * kFnvPrime;
}

uint32_t TileColor(uint32_t tile) {
  uint32_t state = kSeed;
  for (uint32_t i = 0; i <= tile; ++i) {
    XorShift32(state);
  }
  uint32_t bits = (state >> 3) & 7;
  if (!bits) {
    bits = 1;
  }
  return 0xFF000000U | ((bits & 1) ? 0x00FF0000U : 0) |
         ((bits & 2) ? 0x0000FF00U : 0) |
         ((bits & 4) ? 0x000000FFU : 0);
}

uint32_t ExpectedFinalState(uint32_t phase, uint32_t payload_kat,
                            uint32_t packet_words,
                            uint32_t measured_iterations) {
  uint32_t state = kSeed ^ phase;
  for (uint32_t iteration = 0; iteration < measured_iterations; ++iteration) {
    state = FoldKnownOutput(state, payload_kat);
    state = FoldKnownOutput(state, packet_words);
    state = FoldKnownOutput(state, kPacketsPerIteration);
  }
  return state;
}

uint64_t HashBackBuffer() {
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

void SynchronizeCorrectness(TestHost &host) {
  host.WaitForGpu();
  EmitXemuPerfMarker(kXemuPerfMarkerGpuComplete);
  host.WaitForGpu();
}

}  // namespace

PfifoArrayElementTests::PfifoArrayElementTests(TestHost &host,
                                               std::string output_dir,
                                               const Config &config)
    : TestSuite(host, std::move(output_dir), "PFIFOArrayElements", config) {
  static constexpr Recipe kMorrowind16{
      kArrayElement16Name, ElementWidth::BITS_16, kMorrowindPacketWords,
      kMorrowindIndexCount, kMorrowindIndexKat, kMorrowind16PayloadKat,
      kMorrowindPixelKat, 0xA116, kMorrowind16FinalColor,
      kMorrowind16FinalFrameHash};
  static constexpr Recipe kMorrowind32{
      kArrayElement32Name, ElementWidth::BITS_32, kMorrowindIndexCount,
      kMorrowindIndexCount, kMorrowindIndexKat, kMorrowind32PayloadKat,
      kMorrowindPixelKat, 0xA132, kMorrowind32FinalColor,
      kMorrowind32FinalFrameHash};
  static constexpr Recipe kPgr2{
      kArrayElementPgr2Name, ElementWidth::BITS_16, kPgr2PacketWords,
      kPgr2IndexCount, kPgr2IndexKat, kPgr2PayloadKat, kPgr2PixelKat,
      0xA229, kPgr2FinalColor, kPgr2FinalFrameHash};

  tests_[kArrayElement16Name] = [this]() { Run(kMorrowind16); };
  tests_[kArrayElement32Name] = [this]() { Run(kMorrowind32); };
  tests_[kArrayElementPgr2Name] = [this]() { Run(kPgr2); };
}

void PfifoArrayElementTests::Initialize() {
  TestSuite::Initialize();

  vertex_buffer_ = host_.AllocateVertexBuffer(kMorrowindIndexCount);
  vertex_buffer_->SetPositionIncludesW(true);
  auto *vertex = vertex_buffer_->Lock();

  vertex_input_kat_ = kFnvOffsetBasis;
  vertex_input_kat_ = Fnv1aAddWord(vertex_input_kat_, kSeed);
  indices_.reserve(kMorrowindIndexCount);
  for (uint32_t tile = 0; tile < kTileCount; ++tile) {
    const uint32_t left = 32 + (tile % 5) * 112;
    const uint32_t top = 48 + (tile / 5) * 96;
    const uint32_t right = left + 80;
    const uint32_t bottom = top + 64;
    const uint32_t color = TileColor(tile);
    vertex_input_kat_ = Fnv1aAddWord(vertex_input_kat_, tile);
    vertex_input_kat_ = Fnv1aAddWord(vertex_input_kat_, left);
    vertex_input_kat_ = Fnv1aAddWord(vertex_input_kat_, top);
    vertex_input_kat_ = Fnv1aAddWord(vertex_input_kat_, right);
    vertex_input_kat_ = Fnv1aAddWord(vertex_input_kat_, bottom);
    vertex_input_kat_ = Fnv1aAddWord(vertex_input_kat_, color);

    const float red = (color & 0x00FF0000U) ? 1.f : 0.f;
    const float green = (color & 0x0000FF00U) ? 1.f : 0.f;
    const float blue = (color & 0x000000FFU) ? 1.f : 0.f;
    const std::array<std::array<float, 2>, 4> positions{{
        {{static_cast<float>(left), static_cast<float>(top)}},
        {{static_cast<float>(right), static_cast<float>(top)}},
        {{static_cast<float>(right), static_cast<float>(bottom)}},
        {{static_cast<float>(left), static_cast<float>(bottom)}},
    }};
    for (const auto &position : positions) {
      vertex->SetPosition(position[0], position[1], 1.f, 1.f);
      vertex->SetDiffuse(red, green, blue, 1.f);
      ++vertex;
      indices_.push_back(static_cast<uint32_t>(indices_.size()));
    }
  }
  vertex_buffer_->Unlock();
  AssertXemuPerfEqual(kVertexInputKat, vertex_input_kat_,
                      XemuPerfAssertion::PFIFO_ARRAY_VERTEX_INPUT,
                      "pfifo_array_vertex_kat == kVertexInputKat", __FILE__,
                      __LINE__);

  payload16_morrowind_.reserve(kMorrowindPacketWords);
  for (uint32_t i = 0; i < kMorrowindIndexCount; i += 2) {
    payload16_morrowind_.push_back(indices_[i] | (indices_[i + 1] << 16));
  }
  payload16_pgr2_.assign(payload16_morrowind_.begin(),
                         payload16_morrowind_.begin() + kPgr2PacketWords);
}

void PfifoArrayElementTests::Deinitialize() {
  host_.ClearVertexBuffer();
  vertex_buffer_.reset();
  indices_.clear();
  payload16_morrowind_.clear();
  payload16_pgr2_.clear();
  vertex_input_kat_ = 0;
  TestSuite::Deinitialize();
}

void PfifoArrayElementTests::Run(const Recipe &recipe) {
  const uint32_t measured_iterations =
      host_.GetSaveResults()
          ? kProfileSamples * host_.GetMeasurementIterationsMultiplier()
          : 1;
  const uint32_t expected_final =
      ExpectedFinalState(recipe.phase, recipe.payload_kat, recipe.packet_words,
                         measured_iterations);
  uint32_t actual_final = kSeed ^ recipe.phase;
  uint32_t invocation = 0;
  const uint32_t warmup_iterations =
      host_.GetSaveResults() ? host_.GetWarmupIterations() : 0;

  uint32_t actual_index_kat = kFnvOffsetBasis;
  for (uint32_t i = 0; i < recipe.index_count; ++i) {
    actual_index_kat = Fnv1aAddWord(actual_index_kat, indices_[i]);
  }
  uint32_t actual_payload_kat = kFnvOffsetBasis;
  if (recipe.element_width == ElementWidth::BITS_32) {
    for (uint32_t i = 0; i < recipe.packet_words; ++i) {
      actual_payload_kat = Fnv1aAddWord(actual_payload_kat, indices_[i]);
    }
  } else {
    const auto &payload = recipe.packet_words == kPgr2PacketWords
                              ? payload16_pgr2_
                              : payload16_morrowind_;
    for (uint32_t word : payload) {
      actual_payload_kat = Fnv1aAddWord(actual_payload_kat, word);
    }
  }
  AssertXemuPerfEqual(kVertexInputKat, vertex_input_kat_,
                      XemuPerfAssertion::PFIFO_ARRAY_VERTEX_INPUT,
                      "pfifo_array_vertex_input == expected", __FILE__,
                      __LINE__);
  AssertXemuPerfEqual(recipe.index_kat, actual_index_kat,
                      XemuPerfAssertion::PFIFO_ARRAY_VERTEX_INPUT,
                      "pfifo_array_index_input == expected", __FILE__,
                      __LINE__);
  AssertXemuPerfEqual(recipe.payload_kat, actual_payload_kat,
                      XemuPerfAssertion::PFIFO_ARRAY_VERTEX_INPUT,
                      "pfifo_array_payload_input == expected", __FILE__,
                      __LINE__);

  SetXemuPerfEventContext(recipe.phase, expected_final);
  EmitXemuPerfEvent(XemuPerfEventType::CONTEXT, 0,
                    host_.GetMeasurementIterationsMultiplier(),
                    warmup_iterations);

  host_.SetDefaultViewportAndFixedFunctionMatrices();
  host_.SetVertexShaderProgram(std::make_shared<PassthroughVertexShader>());
  host_.SetVertexBuffer(vertex_buffer_);
  host_.SetVertexBufferAttributes(kVertexAttributes);
  host_.SetBlend(false);
  host_.SetFinalCombiner0Just(TestHost::SRC_DIFFUSE);
  host_.SetFinalCombiner1Just(TestHost::SRC_DIFFUSE, true);
  {
    Pushbuffer::Begin();
    Pushbuffer::Push(NV097_SET_CULL_FACE_ENABLE, false);
    Pushbuffer::Push(NV097_SET_DEPTH_TEST_ENABLE, false);
    Pushbuffer::End();
  }
  host_.PrepareDraw(kBackgroundColor);

  auto results = Profile(recipe.test_name, kProfileSamples, [&]() {
    SubmitPackets(recipe);
    if (invocation >= warmup_iterations) {
      actual_final = FoldKnownOutput(actual_final, recipe.payload_kat);
      actual_final = FoldKnownOutput(actual_final, recipe.packet_words);
      actual_final = FoldKnownOutput(actual_final, kPacketsPerIteration);
    }
    ++invocation;
  });

  // Profile emitted F1. Correctness/fence work begins only here.
  SynchronizeCorrectness(host_);
  const uint32_t pixel_kat = ValidateRenderedTiles(recipe);
  AssertXemuPerfEqual(recipe.pixel_kat, pixel_kat,
                      XemuPerfAssertion::PFIFO_ARRAY_SURFACE,
                      "pfifo_array_pixel_kat == expected", __FILE__, __LINE__);
  AssertXemuPerfEqual(expected_final, actual_final,
                      XemuPerfAssertion::PFIFO_ARRAY_FINAL,
                      "pfifo_array_final_state == expected", __FILE__, __LINE__);

  // A fixed solid result frame gives each capsule an exact standard
  // framebuffer_fnv1a64 independent of the selected multiplier.
  host_.SetVertexShaderProgram(nullptr);
  host_.SetupFixedFunctionPassthrough();
  host_.SetBlend(false);
  host_.PrepareDraw(recipe.final_frame_color);
  SynchronizeCorrectness(host_);
  const uint64_t actual_frame_hash = HashBackBuffer();
  AssertXemuPerfEqual(static_cast<uint32_t>(recipe.final_frame_hash >> 32),
                      static_cast<uint32_t>(actual_frame_hash >> 32),
                      XemuPerfAssertion::PFIFO_ARRAY_FRAMEBUFFER,
                      "pfifo_array_framebuffer_hash_hi == expected", __FILE__,
                      __LINE__);
  AssertXemuPerfEqual(static_cast<uint32_t>(recipe.final_frame_hash),
                      static_cast<uint32_t>(actual_frame_hash),
                      XemuPerfAssertion::PFIFO_ARRAY_FRAMEBUFFER,
                      "pfifo_array_framebuffer_hash_lo == expected", __FILE__,
                      __LINE__);

  const uint64_t total_packets =
      static_cast<uint64_t>(kPacketsPerIteration) * results.iterations;
  const uint64_t total_payload_words = total_packets * recipe.packet_words;
  PrintMsg(
      "PFIFO_ARRAY_WORK PFIFOArrayElements::%s seed=%08lx iterations=%lu "
      "packet_words=%lu packets=%llu payload_words=%llu input=%08lx "
      "index=%08lx payload=%08lx pixels=%08lx final=%08lx frame=%016llx\n",
      recipe.test_name, kSeed, results.iterations, recipe.packet_words,
      static_cast<unsigned long long>(total_packets),
      static_cast<unsigned long long>(total_payload_words), vertex_input_kat_,
      actual_index_kat, actual_payload_kat, pixel_kat, actual_final,
      static_cast<unsigned long long>(actual_frame_hash));

  std::ostringstream metadata;
  metadata << "{\"schema_version\":1,\"kind\":\"pfifo_array_element_capsule\",";
  metadata << "\"test_id\":\"" << recipe.test_name << "\",";
  metadata << "\"oracle_provenance\":\"REGRESSION_ONLY\",";
  metadata << "\"seed\":\"50464946\",";
  metadata << "\"method\":\""
           << (recipe.element_width == ElementWidth::BITS_16
                   ? "NV097_ARRAY_ELEMENT16"
                   : "NV097_ARRAY_ELEMENT32")
           << "\",";
  metadata << "\"non_incrementing\":true,";
  metadata << "\"packet_words\":" << recipe.packet_words << ",";
  metadata << "\"indices_per_packet\":" << recipe.index_count << ",";
  metadata << "\"packets_per_iteration\":" << kPacketsPerIteration << ",";
  metadata << "\"total_packets\":" << total_packets << ",";
  metadata << "\"total_payload_words\":" << total_payload_words << ",";
  metadata << "\"input_kat\":{\"vertex_expected\":" << kVertexInputKat
           << ",\"vertex_actual\":" << vertex_input_kat_
           << ",\"index_expected\":" << recipe.index_kat
           << ",\"index_actual\":" << actual_index_kat
           << ",\"payload_expected\":" << recipe.payload_kat
           << ",\"payload_actual\":" << actual_payload_kat << "},";
  metadata << "\"rendered_pixel_kat\":{\"expected\":" << recipe.pixel_kat
           << ",\"actual\":" << pixel_kat << "},";
  metadata << "\"expected_final_state\":" << expected_final << ",";
  metadata << "\"actual_final_state\":" << actual_final << ",";
  metadata << "\"terminal_fence\":\"F2 after F1\",";
  char hash_string[17]{};
  snprintf(hash_string, sizeof(hash_string), "%016llx",
           static_cast<unsigned long long>(recipe.final_frame_hash));
  metadata << "\"expected_framebuffer_fnv1a64\":\"" << hash_string << "\",";
  metadata << "\"framebuffer_contract\":\"FinishDraw framebuffer_fnv1a64\"}";

  EmitXemuPerfEvent(XemuPerfEventType::PASS, 0, expected_final, actual_final);
  host_.FinishDraw(suite_name_, recipe.test_name, results, metadata.str());
  ClearXemuPerfEventContext();
}

void PfifoArrayElementTests::SubmitPackets(const Recipe &recipe) const {
  const std::vector<uint32_t> *payload = nullptr;
  if (recipe.element_width == ElementWidth::BITS_32) {
    payload = &indices_;
  } else if (recipe.packet_words == kPgr2PacketWords) {
    payload = &payload16_pgr2_;
  } else {
    payload = &payload16_morrowind_;
  }
  ASSERT(payload->size() >= recipe.packet_words);

  const uint32_t method =
      recipe.element_width == ElementWidth::BITS_16 ? NV097_ARRAY_ELEMENT16
                                                    : NV097_ARRAY_ELEMENT32;
  Pushbuffer::Begin();
  Pushbuffer::Push(NV097_SET_BEGIN_END, NV097_SET_BEGIN_END_OP_QUADS);
  for (uint32_t packet = 0; packet < kPacketsPerIteration; ++packet) {
    Pushbuffer::PushN(NV2A_SUPPRESS_COMMAND_INCREMENT(method),
                      recipe.packet_words,
                      reinterpret_cast<const DWORD *>(payload->data()));
  }
  Pushbuffer::Push(NV097_SET_BEGIN_END, NV097_SET_BEGIN_END_OP_END);
  Pushbuffer::End();
}

uint32_t PfifoArrayElementTests::ValidateRenderedTiles(
    const Recipe &recipe) const {
  const auto *base = reinterpret_cast<volatile const uint8_t *>(pb_back_buffer());
  const uint32_t pitch = pb_back_buffer_pitch();
  const uint32_t complete_tiles = recipe.index_count / 4;
  uint32_t pixel_kat = kFnvOffsetBasis;
  for (uint32_t tile = 0; tile < complete_tiles; ++tile) {
    const uint32_t x = 32 + (tile % 5) * 112 + 40;
    const uint32_t y = 48 + (tile / 5) * 96 + 32;
    const auto *row = reinterpret_cast<volatile const uint32_t *>(base + y * pitch);
    const uint32_t actual = row[x];
    const uint32_t expected = TileColor(tile);
    AssertXemuPerfEqual(expected, actual,
                        XemuPerfAssertion::PFIFO_ARRAY_SURFACE,
                        "pfifo_array_tile_pixel == expected", __FILE__,
                        __LINE__);
    pixel_kat = Fnv1aAddWord(pixel_kat, actual);
  }
  return pixel_kat;
}
