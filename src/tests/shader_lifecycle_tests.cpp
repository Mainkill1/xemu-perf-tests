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
static constexpr uint32_t kReadinessLeft = 72;
static constexpr uint32_t kReadinessTop = 72;
static constexpr uint32_t kReadinessColumnStride = 88;
static constexpr uint32_t kReadinessRowStride = 120;
static constexpr uint32_t kReadinessTileWidth = 64;
static constexpr uint32_t kReadinessTileHeight = 80;
static constexpr uint32_t kReadinessSampleOffset = 24;

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

// Literal packed framebuffer expectations are deliberately independent of
// the shader route. Equal-but-wrong fallback/specialized output must fail.
static constexpr std::array<uint32_t, kReadinessFamilyCount>
    kReadinessDiffuseInputColors{{
        0xFF557391,
        0xFF7AB632,
        0xFF9F3993,
    }};
static constexpr std::array<
    uint32_t, kReadinessFamilyCount * kReadinessCombinerVariantCount>
    kReadinessUniformDiffuseInputColors{{
        0xFF557391,
        0xFF7AB632,
        0xFF9F3993,
        0xFFC47C34,
        0xFFE9BF95,
        0xFF4E4236,
    }};

// NV097_SET_DIFFUSE_COLOR4I and the linear framebuffer use opposite red/blue
// byte orderings. Keep the readback literals separate from the draw inputs so
// the oracle remains independent of the route that produced the pixels.
static constexpr std::array<uint32_t, kReadinessFamilyCount>
    kReadinessFramebufferExpectedColors{{
        0xFF917355,
        0xFF32B67A,
        0xFF93399F,
    }};
static constexpr std::array<
    uint32_t, kReadinessFamilyCount * kReadinessCombinerVariantCount>
    kReadinessUniformFramebufferExpectedColors{{
        0xFF917355,
        0xFF32B67A,
        0xFF93399F,
        0xFF347CC4,
        0xFF95BFE9,
        0xFF36424E,
    }};

static uint32_t ReadinessDiffuseInputColor(bool uniform_only, uint32_t family,
                                           uint32_t variant) {
  if (!uniform_only) {
    return kReadinessDiffuseInputColors[family];
  }
  return kReadinessUniformDiffuseInputColors[
      family * kReadinessCombinerVariantCount + variant];
}

static uint32_t ExpectedReadinessFramebufferColor(
    bool uniform_only, uint32_t family, uint32_t variant) {
  if (!uniform_only) {
    return kReadinessFramebufferExpectedColors[family];
  }
  return kReadinessUniformFramebufferExpectedColors[
      family * kReadinessCombinerVariantCount + variant];
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
  ASSERT(passes > 0 && passes <= 3);

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
        host_.SetDiffuse(
            ReadinessDiffuseInputColor(uniform_only, family, variant));
        const uint32_t column =
            pass * kReadinessCombinerVariantCount + variant;
        DrawReadinessTile(
            kReadinessPrimitives[family],
            kReadinessLeft + column * kReadinessColumnStride,
            kReadinessTop + family * kReadinessRowStride,
            kReadinessTileWidth, kReadinessTileHeight);
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
    uint32_t passes, bool uniform_only) const {
  uint32_t checksum = kFnvOffsetBasis;

  for (uint32_t pass = 0; pass < passes; ++pass) {
    for (uint32_t family = 0; family < kReadinessFamilyCount; ++family) {
      const uint32_t y = kReadinessTop +
          family * kReadinessRowStride + kReadinessSampleOffset;
      for (uint32_t variant = 0;
           variant < kReadinessCombinerVariantCount; ++variant) {
        const uint32_t column =
            pass * kReadinessCombinerVariantCount + variant;
        const uint32_t pixel = ReadPixel(
            kReadinessLeft + column * kReadinessColumnStride +
                kReadinessSampleOffset,
            y);
        const uint32_t expected = ExpectedReadinessFramebufferColor(
            uniform_only, family, variant);
        if (pixel != expected) {
          PrintMsg("SHADER_LIFECYCLE_READINESS_MISMATCH pass=%lu "
                   "family=%lu variant=%lu x=%lu y=%lu "
                   "actual=%08lx expected=%08lx\n",
                   static_cast<unsigned long>(pass),
                   static_cast<unsigned long>(family),
                   static_cast<unsigned long>(variant),
                   static_cast<unsigned long>(
                       kReadinessLeft + column * kReadinessColumnStride +
                           kReadinessSampleOffset),
                   static_cast<unsigned long>(y),
                   static_cast<unsigned long>(pixel),
                   static_cast<unsigned long>(expected));
        }
        ASSERT(pixel == expected);
        checksum = Fnv1aWord(checksum, pixel);
      }
    }
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
  const uint32_t result_kat =
      ValidateReadinessFamilies(passes, uniform_only);
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
