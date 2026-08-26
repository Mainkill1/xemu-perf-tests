#include "pipeline_texture_switch_tests.h"

#include <pbkit/nv_regs.h>
#include <pbkit/pbkit.h>

#include <cstddef>
#include <sstream>

#include "debug_output.h"
#include "pushbuffer.h"
#include "test_host.h"
#include "texture_format.h"

using namespace PBKitPlusPlus;

namespace {

static constexpr char kTextureSwitchName[] = "pipeline.texture-switch";
static constexpr char kShaderNegativeControlName[] =
    "pipeline.shader-negative-control";

static constexpr uint32_t kSeed = 0x50545357;  // "PTSW"
static constexpr uint32_t kFnvOffsetBasis = 2166136261U;
static constexpr uint32_t kFnvPrime = 16777619U;
static constexpr uint32_t kTextureWidth = 64;
static constexpr uint32_t kTextureHeight = 64;
static constexpr uint32_t kTexturePixels = kTextureWidth * kTextureHeight;
static constexpr uint32_t kProfileSamples = 8;
static constexpr uint32_t kOperationsPerIteration = 512;
static constexpr uint32_t kTextureStageCount = 1;
static constexpr uint32_t kHeartbeatInterval = 32;

static constexpr uint32_t kTextureAColor = 0xFFFF0000;
static constexpr uint32_t kTextureBColor = 0xFF0000FF;
static constexpr uint32_t kDiffuseColor = 0xFF00FF00;
static constexpr uint32_t kBackgroundColor = 0xFF101820;

static constexpr uint32_t kRepeatAddress = 0x00010101;
static constexpr uint32_t kClampAddress = 0x00030303;
static constexpr uint32_t kBoxFilter = 0x01012000;
static constexpr uint32_t kTentFilter = 0x02022000;

// Independently reproduced in tests/test_pipeline_texture_switch_contract.py.
static constexpr uint32_t kTextureABackingKat = 0xBDF93DC5;
static constexpr uint32_t kTextureBBackingKat = 0xC40ABDC5;
static constexpr uint32_t kInputKat = 0xA9CA7145;
static constexpr uint32_t kTextureSwitchPixelKat = 0xBB0EC8ED;
static constexpr uint32_t kShaderNegativePixelKat = 0x08C5E8A1;

static constexpr uint32_t kTextureSwitchFinalColor = 0xFF18405A;
static constexpr uint32_t kShaderNegativeFinalColor = 0xFF4A2038;
static constexpr uint64_t kTextureSwitchFinalFrameHash =
    0x8AE05D31FB00C325ULL;
static constexpr uint64_t kShaderNegativeFinalFrameHash =
    0xF110C8BD6338C325ULL;

struct Quad {
  float left;
  float top;
  float right;
  float bottom;
};

static constexpr Quad kQuads[] = {
    {64.f, 64.f, 288.f, 224.f},
    {352.f, 64.f, 576.f, 224.f},
    {64.f, 256.f, 288.f, 416.f},
    {352.f, 256.f, 576.f, 416.f},
};

uint32_t Fnv1aAddWord(uint32_t hash, uint32_t value) {
  for (uint32_t byte = 0; byte < 4; ++byte) {
    hash = (hash ^ static_cast<uint8_t>(value >> (byte * 8))) * kFnvPrime;
  }
  return hash;
}

uint32_t HashWords(volatile const uint32_t *words, uint32_t count) {
  uint32_t hash = kFnvOffsetBasis;
  for (uint32_t i = 0; i < count; ++i) {
    hash = Fnv1aAddWord(hash, words[i]);
  }
  return hash;
}

uint32_t FoldKnownOutput(uint32_t state, uint32_t value) {
  return (state ^ value) * kFnvPrime;
}

uint32_t ExpectedFinalState(uint32_t phase, uint32_t expected_pixel_kat,
                            uint32_t measured_iterations) {
  uint32_t state = kSeed ^ phase;
  for (uint32_t iteration = 0; iteration < measured_iterations; ++iteration) {
    state = FoldKnownOutput(state, kInputKat);
    state = FoldKnownOutput(state, phase);
    state = FoldKnownOutput(state, kOperationsPerIteration);
    state = FoldKnownOutput(state, expected_pixel_kat);
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

PipelineTextureSwitchTests::PipelineTextureSwitchTests(TestHost &host,
                                                       std::string output_dir,
                                                       const Config &config)
    : TestSuite(host, std::move(output_dir), "PipelineTextureSwitch", config) {
  static constexpr Recipe kTextureSwitch{
      kTextureSwitchName, 0x1501, false, kTextureSwitchPixelKat,
      kTextureSwitchFinalColor, kTextureSwitchFinalFrameHash};
  static constexpr Recipe kShaderNegativeControl{
      kShaderNegativeControlName, 0x1502, true, kShaderNegativePixelKat,
      kShaderNegativeFinalColor, kShaderNegativeFinalFrameHash};

  tests_[kTextureSwitchName] = [this]() { Run(kTextureSwitch); };
  tests_[kShaderNegativeControlName] =
      [this]() { Run(kShaderNegativeControl); };
}

void PipelineTextureSwitchTests::Initialize() {
  TestSuite::Initialize();

  auto *texture_a = reinterpret_cast<uint32_t *>(host_.GetTextureMemoryForStage(0));
  auto *texture_b = reinterpret_cast<uint32_t *>(host_.GetTextureMemoryForStage(1));
  for (uint32_t pixel = 0; pixel < kTexturePixels; ++pixel) {
    texture_a[pixel] = kTextureAColor;
    texture_b[pixel] = kTextureBColor;
  }

  backing_a_kat_ = HashWords(texture_a, kTexturePixels);
  backing_b_kat_ = HashWords(texture_b, kTexturePixels);
  input_kat_ = kFnvOffsetBasis;
  const uint32_t input_words[]{
      kSeed,          kTextureWidth,       kTextureHeight,
      kTextureAColor, kTextureBColor,      backing_a_kat_,
      backing_b_kat_, kRepeatAddress,      kClampAddress,
      kBoxFilter,     kTentFilter,         kOperationsPerIteration,
  };
  for (uint32_t value : input_words) {
    input_kat_ = Fnv1aAddWord(input_kat_, value);
  }
  AssertXemuPerfEqual(kTextureABackingKat, backing_a_kat_,
                      XemuPerfAssertion::PIPELINE_TEXTURE_INPUT,
                      "texture_a_backing_kat == expected", __FILE__, __LINE__);
  AssertXemuPerfEqual(kTextureBBackingKat, backing_b_kat_,
                      XemuPerfAssertion::PIPELINE_TEXTURE_INPUT,
                      "texture_b_backing_kat == expected", __FILE__, __LINE__);
  AssertXemuPerfEqual(kInputKat, input_kat_,
                      XemuPerfAssertion::PIPELINE_TEXTURE_INPUT,
                      "pipeline_texture_input_kat == expected", __FILE__,
                      __LINE__);
}

void PipelineTextureSwitchTests::Run(const Recipe &recipe) {
  const uint32_t measured_iterations =
      host_.GetSaveResults()
          ? kProfileSamples * host_.GetMeasurementIterationsMultiplier()
          : 1;
  const uint32_t warmup_iterations =
      host_.GetSaveResults() ? host_.GetWarmupIterations() : 0;
  const uint32_t expected_final =
      ExpectedFinalState(recipe.phase, recipe.expected_pixel_kat,
                         measured_iterations);
  uint32_t actual_final = kSeed ^ recipe.phase;
  uint32_t invocation = 0;

  SetXemuPerfEventContext(recipe.phase, expected_final);
  EmitXemuPerfEvent(XemuPerfEventType::CONTEXT, 0,
                    host_.GetMeasurementIterationsMultiplier(),
                    warmup_iterations);

  AssertXemuPerfEqual(kTextureABackingKat, backing_a_kat_,
                      XemuPerfAssertion::PIPELINE_TEXTURE_INPUT,
                      "pipeline_texture_input_a == expected", __FILE__,
                      __LINE__);
  AssertXemuPerfEqual(kTextureBBackingKat, backing_b_kat_,
                      XemuPerfAssertion::PIPELINE_TEXTURE_INPUT,
                      "pipeline_texture_input_b == expected", __FILE__,
                      __LINE__);
  AssertXemuPerfEqual(kInputKat, input_kat_,
                      XemuPerfAssertion::PIPELINE_TEXTURE_INPUT,
                      "pipeline_texture_input == expected", __FILE__,
                      __LINE__);

  ConfigureTexturePipeline();
  host_.PrepareDraw(kBackgroundColor);

  auto results = Profile(recipe.test_name, kProfileSamples, [&]() {
    RunIteration(recipe);
    if (invocation >= warmup_iterations) {
      actual_final = FoldKnownOutput(actual_final, input_kat_);
      actual_final = FoldKnownOutput(actual_final, recipe.phase);
      actual_final = FoldKnownOutput(actual_final, kOperationsPerIteration);
      actual_final = FoldKnownOutput(actual_final, recipe.expected_pixel_kat);
    }
    if ((invocation % kHeartbeatInterval) == 0) {
      EmitXemuPerfHeartbeat();
    }
    ++invocation;
  });

  // F1 has already been emitted. All reads and correctness work stay outside
  // the measured window and begin after a separate F2 fence.
  SynchronizeCorrectness(host_);

  auto *texture_a = reinterpret_cast<volatile const uint32_t *>(
      host_.GetTextureMemoryForStage(0));
  auto *texture_b = reinterpret_cast<volatile const uint32_t *>(
      host_.GetTextureMemoryForStage(1));
  const uint32_t actual_backing_a = HashWords(texture_a, kTexturePixels);
  const uint32_t actual_backing_b = HashWords(texture_b, kTexturePixels);
  AssertXemuPerfEqual(kTextureABackingKat, actual_backing_a,
                      XemuPerfAssertion::PIPELINE_TEXTURE_BACKING,
                      "texture_a_backing_unchanged", __FILE__, __LINE__);
  AssertXemuPerfEqual(kTextureBBackingKat, actual_backing_b,
                      XemuPerfAssertion::PIPELINE_TEXTURE_BACKING,
                      "texture_b_backing_unchanged", __FILE__, __LINE__);

  const uint32_t actual_pixel_kat = ValidatePixels(recipe);
  AssertXemuPerfEqual(recipe.expected_pixel_kat, actual_pixel_kat,
                      XemuPerfAssertion::PIPELINE_TEXTURE_SURFACE,
                      "pipeline_texture_pixel_kat == expected", __FILE__,
                      __LINE__);
  AssertXemuPerfEqual(expected_final, actual_final,
                      XemuPerfAssertion::PIPELINE_TEXTURE_FINAL,
                      "pipeline_texture_final_state == expected", __FILE__,
                      __LINE__);

  host_.SetTextureStageEnabled(0, false);
  host_.SetShaderStageProgram(TestHost::STAGE_NONE);
  host_.SetupTextureStages();
  host_.SetFinalCombiner0Just(TestHost::SRC_DIFFUSE);
  host_.SetFinalCombiner1Just(TestHost::SRC_DIFFUSE, true);
  host_.SetBlend(false);
  host_.PrepareDraw(recipe.final_frame_color);
  SynchronizeCorrectness(host_);
  const uint64_t actual_frame_hash = HashBackBuffer();
  AssertXemuPerfEqual(static_cast<uint32_t>(recipe.final_frame_hash >> 32),
                      static_cast<uint32_t>(actual_frame_hash >> 32),
                      XemuPerfAssertion::PIPELINE_TEXTURE_FRAMEBUFFER,
                      "pipeline_texture_framebuffer_hash_hi == expected",
                      __FILE__, __LINE__);
  AssertXemuPerfEqual(static_cast<uint32_t>(recipe.final_frame_hash),
                      static_cast<uint32_t>(actual_frame_hash),
                      XemuPerfAssertion::PIPELINE_TEXTURE_FRAMEBUFFER,
                      "pipeline_texture_framebuffer_hash_lo == expected",
                      __FILE__, __LINE__);

  const uint64_t total_operations =
      static_cast<uint64_t>(kOperationsPerIteration) * results.iterations;
  const uint64_t texture_switches =
      recipe.shader_negative_control ? 0 : total_operations;
  const uint64_t shader_state_writes =
      recipe.shader_negative_control ? total_operations : 0;
  PrintMsg(
      "PIPELINE_TEXTURE_WORK PipelineTextureSwitch::%s seed=%08lx "
      "iterations=%lu stages=%lu operations=%llu draws=%llu "
      "texture_switches=%llu sampler_changes=%llu address_changes=%llu "
      "shader_state_writes=%llu input=%08lx backing_a=%08lx "
      "backing_b=%08lx pixels=%08lx final=%08lx frame=%016llx\n",
      recipe.test_name, kSeed, results.iterations, kTextureStageCount,
      static_cast<unsigned long long>(total_operations),
      static_cast<unsigned long long>(total_operations),
      static_cast<unsigned long long>(texture_switches),
      static_cast<unsigned long long>(texture_switches),
      static_cast<unsigned long long>(texture_switches),
      static_cast<unsigned long long>(shader_state_writes), input_kat_,
      actual_backing_a, actual_backing_b, actual_pixel_kat, actual_final,
      static_cast<unsigned long long>(actual_frame_hash));

  std::ostringstream metadata;
  metadata << "{\"schema_version\":1,";
  metadata << "\"kind\":\"pipeline_texture_switch_capsule\",";
  metadata << "\"test_id\":\"" << recipe.test_name << "\",";
  metadata << "\"oracle_provenance\":\"REGRESSION_ONLY\",";
  metadata << "\"seed\":\"50545357\",";
  metadata << "\"phase\":\""
           << (recipe.shader_negative_control ? "shader_negative_control"
                                              : "texture_switch")
           << "\",";
  metadata << "\"phase_count\":2,";
  metadata << "\"texture_stage_count\":" << kTextureStageCount << ",";
  metadata << "\"operations_per_iteration\":"
           << kOperationsPerIteration << ",";
  metadata << "\"total_operations\":" << total_operations << ",";
  metadata << "\"draws\":" << total_operations << ",";
  metadata << "\"texture_switches\":" << texture_switches << ",";
  metadata << "\"sampler_changes\":" << texture_switches << ",";
  metadata << "\"address_changes\":" << texture_switches << ",";
  metadata << "\"shader_state_writes\":" << shader_state_writes << ",";
  metadata << "\"input_kat\":{\"expected\":" << kInputKat
           << ",\"actual\":" << input_kat_ << "},";
  metadata << "\"backing_kat\":{\"a_expected\":"
           << kTextureABackingKat << ",\"a_actual\":" << actual_backing_a
           << ",\"b_expected\":" << kTextureBBackingKat
           << ",\"b_actual\":" << actual_backing_b << "},";
  metadata << "\"rendered_pixel_kat\":{\"expected\":"
           << recipe.expected_pixel_kat << ",\"actual\":"
           << actual_pixel_kat << "},";
  metadata << "\"expected_final_state\":" << expected_final << ",";
  metadata << "\"actual_final_state\":" << actual_final << ",";
  metadata << "\"terminal_fence\":\"F2 after F1\",";
  char hash_string[17]{};
  snprintf(hash_string, sizeof(hash_string), "%016llx",
           static_cast<unsigned long long>(recipe.final_frame_hash));
  metadata << "\"expected_framebuffer_fnv1a64\":\"" << hash_string
           << "\",";
  metadata << "\"framebuffer_contract\":\"FinishDraw framebuffer_fnv1a64\"}";

  EmitXemuPerfEvent(XemuPerfEventType::PASS, 0, expected_final, actual_final);
  host_.FinishDraw(suite_name_, recipe.test_name, results, metadata.str());
  ClearXemuPerfEventContext();
}

void PipelineTextureSwitchTests::ConfigureTexturePipeline() const {
  host_.SetVertexShaderProgram(nullptr);
  host_.SetupFixedFunctionPassthrough();
  auto &texture_stage = host_.GetTextureStage(0);
  texture_stage.SetFormat(GetTextureFormatInfo(
      NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_A8R8G8B8));
  texture_stage.SetTextureDimensions(kTextureWidth, kTextureHeight);
  texture_stage.SetImageDimensions(kTextureWidth, kTextureHeight);
  texture_stage.SetUWrap(TextureStage::WRAP_REPEAT, false);
  texture_stage.SetVWrap(TextureStage::WRAP_REPEAT, false);
  texture_stage.SetPWrap(TextureStage::WRAP_REPEAT, false);
  texture_stage.SetFilter();
  texture_stage.SetEnabled(true);
  host_.SetShaderStageProgram(TestHost::STAGE_2D_PROJECTIVE);
  host_.SetupTextureStages();
  host_.SetBlend(false);
  host_.SetFinalCombiner0Just(TestHost::SRC_TEX0);
  host_.SetFinalCombiner1Just(TestHost::SRC_ZERO, true, true);
  host_.SetDiffuse(0.f, 1.f, 0.f, 1.f);
  Pushbuffer::Begin();
  Pushbuffer::Push(NV097_SET_CULL_FACE_ENABLE, false);
  Pushbuffer::Push(NV097_SET_DEPTH_TEST_ENABLE, false);
  Pushbuffer::End();
}

void PipelineTextureSwitchTests::RunIteration(const Recipe &recipe) const {
  const uint32_t texture_a =
      reinterpret_cast<uint32_t>(host_.GetTextureMemoryForStage(0)) &
      0x03FFFFFF;
  const uint32_t texture_b =
      reinterpret_cast<uint32_t>(host_.GetTextureMemoryForStage(1)) &
      0x03FFFFFF;

  if (recipe.shader_negative_control) {
    Pushbuffer::Begin();
    Pushbuffer::Push(NV097_SET_TEXTURE_OFFSET, texture_a);
    Pushbuffer::Push(NV097_SET_TEXTURE_ADDRESS, kRepeatAddress);
    Pushbuffer::Push(NV097_SET_TEXTURE_FILTER, kBoxFilter);
    Pushbuffer::End();
  }

  for (uint32_t operation = 0; operation < kOperationsPerIteration;
       ++operation) {
    const uint32_t selector = operation & 1;
    if (recipe.shader_negative_control) {
      host_.SetFinalCombiner0Just(selector ? TestHost::SRC_DIFFUSE
                                           : TestHost::SRC_TEX0);
    } else {
      Pushbuffer::Begin();
      Pushbuffer::Push(NV097_SET_TEXTURE_OFFSET,
                       selector ? texture_b : texture_a);
      Pushbuffer::Push(NV097_SET_TEXTURE_ADDRESS,
                       selector ? kClampAddress : kRepeatAddress);
      Pushbuffer::Push(NV097_SET_TEXTURE_FILTER,
                       selector ? kTentFilter : kBoxFilter);
      Pushbuffer::End();
    }

    const Quad &quad = kQuads[operation & 3];
    host_.DrawTexturedScreenQuadEx(
        quad.left, quad.top, quad.right, quad.bottom, 1.f, -16.f, -16.f,
        80.f, -16.f, 80.f, 80.f, -16.f, 80.f);
  }
}

uint32_t PipelineTextureSwitchTests::ValidatePixels(
    const Recipe &recipe) const {
  const auto *base = reinterpret_cast<volatile const uint8_t *>(pb_back_buffer());
  const uint32_t pitch = pb_back_buffer_pitch();
  uint32_t kat = kFnvOffsetBasis;
  for (uint32_t tile = 0; tile < 4; ++tile) {
    const Quad &quad = kQuads[tile];
    const uint32_t x = static_cast<uint32_t>((quad.left + quad.right) * 0.5f);
    const uint32_t y = static_cast<uint32_t>((quad.top + quad.bottom) * 0.5f);
    const auto *row =
        reinterpret_cast<volatile const uint32_t *>(base + y * pitch);
    const uint32_t actual = row[x];
    uint32_t expected;
    if (recipe.shader_negative_control) {
      expected = (tile & 1) ? kDiffuseColor : kTextureAColor;
    } else {
      expected = (tile & 1) ? kTextureBColor : kTextureAColor;
    }
    AssertXemuPerfEqual(expected, actual,
                        XemuPerfAssertion::PIPELINE_TEXTURE_SURFACE,
                        "pipeline_texture_tile_pixel == expected", __FILE__,
                        __LINE__);
    kat = Fnv1aAddWord(kat, actual);
  }
  return kat;
}
