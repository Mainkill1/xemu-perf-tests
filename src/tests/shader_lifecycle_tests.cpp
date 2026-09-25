#include "shader_lifecycle_tests.h"

#include <pbkit/nv_regs.h>

#include <array>
#include <cstddef>

#include "debug_output.h"
#include "pushbuffer.h"
#include "test_host.h"

using namespace PBKitPlusPlus;

namespace {

static constexpr char kReadinessTrainVisible[] = "readiness.train-visible";
static constexpr char kReadinessReplayVisible[] = "readiness.replay-visible";
static constexpr char kReadinessIdenticalReplay[] =
    "readiness.identical-replay";
static constexpr char kReadinessUniformOnly[] = "readiness.uniform-only";
static constexpr char kReadinessEarlyDemand[] = "readiness.early-demand";

static constexpr uint32_t kReadinessFamilyCount = 3;
static constexpr uint32_t kReadinessCombinerVariantCount = 2;
static constexpr uint32_t kReadinessSpecializationLeadMs = 2000;
static constexpr uint32_t kReadinessVisibleResultHoldMs = 10000;
static constexpr uint32_t kBackgroundColor = 0xFF102030;
static constexpr uint32_t kFnvOffsetBasis = 2166136261U;
static constexpr uint32_t kFnvPrime = 16777619U;

static constexpr uint32_t kBlue =
    NV097_SET_COLOR_MASK_BLUE_WRITE_ENABLE;
static constexpr uint32_t kGreen =
    NV097_SET_COLOR_MASK_GREEN_WRITE_ENABLE;
static constexpr uint32_t kRed = NV097_SET_COLOR_MASK_RED_WRITE_ENABLE;
static constexpr uint32_t kAlpha =
    NV097_SET_COLOR_MASK_ALPHA_WRITE_ENABLE;
static constexpr uint32_t kAllChannels = kBlue | kGreen | kRed | kAlpha;

static constexpr std::array<TestHost::DrawPrimitive, kReadinessFamilyCount>
    kReadinessPrimitives{{
        TestHost::PRIMITIVE_TRIANGLES,
        TestHost::PRIMITIVE_TRIANGLE_STRIP,
        TestHost::PRIMITIVE_QUADS,
    }};

static uint32_t UniformColor(uint32_t index) {
  const uint32_t red = 0x30U + (index * 37U) % 0xC0U;
  const uint32_t green = 0x30U + (index * 67U) % 0xC0U;
  const uint32_t blue = 0x30U + (index * 97U) % 0xC0U;
  return 0xFF000000U | (red << 16) | (green << 8) | blue;
}

static uint32_t ReadPixel(uint32_t x, uint32_t y) {
  const auto *base =
      reinterpret_cast<volatile const uint8_t *>(pb_back_buffer());
  const auto *row = reinterpret_cast<volatile const uint32_t *>(
      base + static_cast<size_t>(y) * pb_back_buffer_pitch());
  return row[x];
}

static uint32_t Fnv1aWord(uint32_t hash, uint32_t value) {
  for (uint32_t byte = 0; byte < 4; ++byte) {
    hash = (hash ^ static_cast<uint8_t>(value >> (byte * 8))) * kFnvPrime;
  }
  return hash;
}

}  // namespace

ShaderLifecycleTests::ShaderLifecycleTests(TestHost &host,
                                           std::string output_dir,
                                           const Config &config)
    : TestSuite(host, std::move(output_dir), "ShaderLifecycle", config) {
  tests_[kReadinessTrainVisible] = [this]() {
    RunReadinessScenario(kReadinessTrainVisible, 1, false);
  };
  tests_[kReadinessReplayVisible] = [this]() {
    RunReadinessScenario(kReadinessReplayVisible, 1, false);
  };
  tests_[kReadinessIdenticalReplay] = [this]() {
    RunReadinessScenario(kReadinessIdenticalReplay, 3, false,
                         kReadinessSpecializationLeadMs);
  };
  tests_[kReadinessUniformOnly] = [this]() {
    RunReadinessScenario(kReadinessUniformOnly, 1, true);
  };
  tests_[kReadinessEarlyDemand] = [this]() {
    RunReadinessScenario(kReadinessEarlyDemand, 1, false);
  };
}

void ShaderLifecycleTests::ConfigureFixedShader() const {
  host_.SetVertexShaderProgram(nullptr);
  host_.SetupFixedFunctionPassthrough();
  for (uint32_t stage = 0; stage < 4; ++stage) {
    host_.SetTextureStageEnabled(stage, false);
  }
  host_.SetupTextureStages();
  host_.SetShaderStageProgram(TestHost::STAGE_NONE, TestHost::STAGE_NONE,
                              TestHost::STAGE_NONE, TestHost::STAGE_NONE);
}

void ShaderLifecycleTests::ConfigureReadinessCombiner(
    uint32_t variant) const {
  ASSERT(variant < kReadinessCombinerVariantCount);
  host_.ClearInputColorCombiners();
  host_.ClearInputAlphaCombiners();
  host_.ClearOutputColorCombiners();
  host_.ClearOutputAlphaCombiners();
  host_.SetCombinerControl(1);

  // Multiplication is commutative: both programs emit the same diffuse value,
  // but swapping A/B produces distinct specialized fragment state. xemu's
  // fallback route canonicalizes these combiner fields, so the pair must share
  // the same compatible fallback family for a given primitive topology.
  const auto source_a = variant ? TestHost::SRC_ZERO : TestHost::SRC_DIFFUSE;
  const auto source_b = variant ? TestHost::SRC_DIFFUSE : TestHost::SRC_ZERO;
  const auto map_a = variant ? TestHost::MAP_UNSIGNED_INVERT
                             : TestHost::MAP_UNSIGNED_IDENTITY;
  const auto map_b = variant ? TestHost::MAP_UNSIGNED_IDENTITY
                             : TestHost::MAP_UNSIGNED_INVERT;
  host_.SetInputColorCombiner(0, source_a, false, map_a, source_b, false,
                              map_b);
  host_.SetInputAlphaCombiner(0, source_a, true, map_a, source_b, true,
                              map_b);
  host_.SetOutputColorCombiner(0, TestHost::DST_DISCARD,
                               TestHost::DST_DISCARD, TestHost::DST_R0);
  host_.SetOutputAlphaCombiner(0, TestHost::DST_DISCARD,
                               TestHost::DST_DISCARD, TestHost::DST_R0);
  host_.SetFinalCombiner0(TestHost::SRC_ZERO, false, false,
                          TestHost::SRC_ZERO, false, false,
                          TestHost::SRC_ZERO, false, false,
                          TestHost::SRC_R0);
  host_.SetFinalCombiner1(TestHost::SRC_ZERO, false, false,
                          TestHost::SRC_ZERO, false, false,
                          TestHost::SRC_R0, true, false, false, false, true);
}

void ShaderLifecycleTests::DrawReadinessTile(
    TestHost::DrawPrimitive primitive, float left, float top, float width,
    float height) const {
  host_.Begin(primitive);
  if (primitive == TestHost::PRIMITIVE_TRIANGLES) {
    host_.SetVertex(left, top, 1.f);
    host_.SetVertex(left + width, top, 1.f);
    host_.SetVertex(left + width, top + height, 1.f);
    host_.SetVertex(left, top, 1.f);
    host_.SetVertex(left + width, top + height, 1.f);
    host_.SetVertex(left, top + height, 1.f);
  } else if (primitive == TestHost::PRIMITIVE_TRIANGLE_STRIP) {
    host_.SetVertex(left, top, 1.f);
    host_.SetVertex(left, top + height, 1.f);
    host_.SetVertex(left + width, top, 1.f);
    host_.SetVertex(left + width, top + height, 1.f);
  } else {
    ASSERT(primitive == TestHost::PRIMITIVE_QUADS);
    host_.SetVertex(left, top, 1.f);
    host_.SetVertex(left + width, top, 1.f);
    host_.SetVertex(left + width, top + height, 1.f);
    host_.SetVertex(left, top + height, 1.f);
  }
  host_.End();
}

void ShaderLifecycleTests::DrawReadinessFamilies(
    uint32_t passes, bool uniform_only, uint32_t interpass_delay_ms) const {
  static constexpr float kLeft = 72.f;
  static constexpr float kTop = 72.f;
  static constexpr float kColumnStride = 240.f;
  static constexpr float kRowStride = 120.f;
  static constexpr float kTileWidth = 160.f;
  static constexpr float kTileHeight = 80.f;

  host_.PrepareDraw(kBackgroundColor);
  host_.SetBlend(false);
  Pushbuffer::Begin();
  Pushbuffer::Push(NV097_SET_COLOR_MASK, kAllChannels);
  Pushbuffer::Push(NV097_SET_ALPHA_TEST_ENABLE, false);
  Pushbuffer::Push(NV097_SET_DEPTH_TEST_ENABLE, false);
  Pushbuffer::Push(NV097_SET_DEPTH_MASK, false);
  Pushbuffer::Push(NV097_SET_STENCIL_TEST_ENABLE, false);
  Pushbuffer::Push(NV097_SET_CULL_FACE_ENABLE, false);
  Pushbuffer::End();

  for (uint32_t pass = 0; pass < passes; ++pass) {
    for (uint32_t family = 0; family < kReadinessFamilyCount; ++family) {
      for (uint32_t variant = 0;
           variant < kReadinessCombinerVariantCount; ++variant) {
        ConfigureReadinessCombiner(variant);
        const uint32_t color_index = uniform_only
            ? family * kReadinessCombinerVariantCount + variant + 1
            : family + 1;
        host_.SetDiffuse(UniformColor(color_index));
        DrawReadinessTile(
            kReadinessPrimitives[family],
            kLeft + variant * kColumnStride,
            kTop + family * kRowStride, kTileWidth, kTileHeight);
      }
    }
    if (interpass_delay_ms && pass + 1 < passes) {
      // The first pass exercises the already-published fallback. The second
      // can queue an exact pipeline after a rebuilt stage; the third proves
      // actual specialized takeover after publication.
      host_.WaitForGpu();
      Sleep(interpass_delay_ms);
    }
  }
}

uint32_t ShaderLifecycleTests::ValidateReadinessFamilies(
    bool uniform_only) const {
  static constexpr uint32_t kLeft = 72;
  static constexpr uint32_t kTop = 72;
  static constexpr uint32_t kColumnStride = 240;
  static constexpr uint32_t kRowStride = 120;
  static constexpr uint32_t kSampleOffset = 32;
  uint32_t checksum = kFnvOffsetBasis;

  for (uint32_t family = 0; family < kReadinessFamilyCount; ++family) {
    const uint32_t y = kTop + family * kRowStride + kSampleOffset;
    const uint32_t first_pixel = ReadPixel(kLeft + kSampleOffset, y);
    const uint32_t second_pixel =
        ReadPixel(kLeft + kColumnStride + kSampleOffset, y);
    ASSERT(first_pixel != kBackgroundColor);
    ASSERT(second_pixel != kBackgroundColor);
    if (!uniform_only) {
      ASSERT(first_pixel == second_pixel);
    }
    checksum = Fnv1aWord(checksum, first_pixel);
    checksum = Fnv1aWord(checksum, second_pixel);
  }
  return checksum;
}

void ShaderLifecycleTests::RunReadinessScenario(
    const char *test_name, uint32_t passes, bool uniform_only,
    uint32_t interpass_delay_ms) {
  ConfigureFixedShader();
  auto results = Profile(test_name, 1, [this, passes, uniform_only,
                                        interpass_delay_ms]() {
    DrawReadinessFamilies(passes, uniform_only, interpass_delay_ms);
  });
  host_.WaitForGpu();
  EmitXemuPerfMarker(kXemuPerfMarkerGpuComplete);
  const uint32_t result_kat = ValidateReadinessFamilies(uniform_only);
  PrintMsg("SHADER_LIFECYCLE_READINESS families=%lu combiner_variants=%lu "
           "passes=%lu uniform_only=%lu interpass_delay_ms=%lu "
           "no_omission=1 result_kat=%08lx\n",
           static_cast<unsigned long>(kReadinessFamilyCount),
           static_cast<unsigned long>(kReadinessCombinerVariantCount),
           static_cast<unsigned long>(passes),
           static_cast<unsigned long>(uniform_only),
           static_cast<unsigned long>(interpass_delay_ms),
           static_cast<unsigned long>(result_kat));
  host_.FinishDraw(suite_name_, test_name, results);
  // Keep the validated color-producing tiles and result overlay visible long
  // enough for an unattended host capture. This is outside Profile(), so the
  // evidence window cannot be mistaken for guest-work timing.
  Sleep(kReadinessVisibleResultHoldMs);
}
