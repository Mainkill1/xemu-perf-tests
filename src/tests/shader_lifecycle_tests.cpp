#include "shader_lifecycle_tests.h"

#include <pbkit/nv_regs.h>

#include <array>
#include <cstddef>

#include "debug_output.h"
#include "pushbuffer.h"
#include "test_host.h"

using namespace PBKitPlusPlus;

namespace {

static constexpr char kPipelineTrain[] = "pipeline.train";
static constexpr char kPipelineCapacityCMinusOne[] =
    "pipeline.capacity-c-minus-one";
static constexpr char kPipelineCapacityC[] = "pipeline.capacity-c";
static constexpr char kPipelineCapacityCPlusOne[] =
    "pipeline.capacity-c-plus-one";
static constexpr char kPipelineIdenticalReplay[] =
    "pipeline.identical-replay";
static constexpr char kPipelineUniformOnly[] = "pipeline.uniform-only";
static constexpr char kReadinessTrainVisible[] = "readiness.train-visible";
static constexpr char kReadinessReplayVisible[] = "readiness.replay-visible";
static constexpr char kReadinessIdenticalReplay[] =
    "readiness.identical-replay";
static constexpr char kReadinessUniformOnly[] = "readiness.uniform-only";
static constexpr char kReadinessEarlyDemand[] = "readiness.early-demand";

// Audited from the xemu renderer revision named by PR #43. Runtime traces must
// still report the effective capacity; a mismatch invalidates C-1/C/C+1 labels.
static constexpr uint32_t kPipelineJobCapacity = 16;
static constexpr uint32_t kPipelineVariantCount = kPipelineJobCapacity + 1;
static constexpr uint32_t kReadinessFamilyCount = 3;
static constexpr uint32_t kReadinessCombinerVariantCount = 2;
static constexpr uint32_t kBackgroundColor = 0xFF102030;
static constexpr uint32_t kSourceColor = 0x8040C080;
static constexpr uint32_t kSentinelColor = 0xFF40C080;
static constexpr uint32_t kSentinelX = 16;
static constexpr uint32_t kSentinelY = 16;
static constexpr uint32_t kSentinelSize = 32;
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

struct PipelineVariant {
  uint32_t source_factor;
  uint32_t destination_factor;
  uint32_t blend_equation;
};

// Color-write masks are dynamic Vulkan state in xemu, so they do not create
// distinct fixed-pipeline recipes. These entries instead exercise all legal
// NV2A source factors and two additional equations while shader, texture,
// geometry, render target, color mask, and vertex format state remain fixed.
static constexpr std::array<PipelineVariant, kPipelineVariantCount>
    kPipelineVariants{{
        {NV097_SET_BLEND_FUNC_SFACTOR_V_ZERO,
         NV097_SET_BLEND_FUNC_DFACTOR_V_ZERO,
         NV097_SET_BLEND_EQUATION_V_FUNC_ADD},
        {NV097_SET_BLEND_FUNC_SFACTOR_V_ONE,
         NV097_SET_BLEND_FUNC_DFACTOR_V_ZERO,
         NV097_SET_BLEND_EQUATION_V_FUNC_ADD},
        {NV097_SET_BLEND_FUNC_SFACTOR_V_SRC_COLOR,
         NV097_SET_BLEND_FUNC_DFACTOR_V_ZERO,
         NV097_SET_BLEND_EQUATION_V_FUNC_ADD},
        {NV097_SET_BLEND_FUNC_SFACTOR_V_ONE_MINUS_SRC_COLOR,
         NV097_SET_BLEND_FUNC_DFACTOR_V_ZERO,
         NV097_SET_BLEND_EQUATION_V_FUNC_ADD},
        {NV097_SET_BLEND_FUNC_SFACTOR_V_SRC_ALPHA,
         NV097_SET_BLEND_FUNC_DFACTOR_V_ZERO,
         NV097_SET_BLEND_EQUATION_V_FUNC_ADD},
        {NV097_SET_BLEND_FUNC_SFACTOR_V_ONE_MINUS_SRC_ALPHA,
         NV097_SET_BLEND_FUNC_DFACTOR_V_ZERO,
         NV097_SET_BLEND_EQUATION_V_FUNC_ADD},
        {NV097_SET_BLEND_FUNC_SFACTOR_V_DST_ALPHA,
         NV097_SET_BLEND_FUNC_DFACTOR_V_ZERO,
         NV097_SET_BLEND_EQUATION_V_FUNC_ADD},
        {NV097_SET_BLEND_FUNC_SFACTOR_V_ONE_MINUS_DST_ALPHA,
         NV097_SET_BLEND_FUNC_DFACTOR_V_ZERO,
         NV097_SET_BLEND_EQUATION_V_FUNC_ADD},
        {NV097_SET_BLEND_FUNC_SFACTOR_V_DST_COLOR,
         NV097_SET_BLEND_FUNC_DFACTOR_V_ZERO,
         NV097_SET_BLEND_EQUATION_V_FUNC_ADD},
        {NV097_SET_BLEND_FUNC_SFACTOR_V_ONE_MINUS_DST_COLOR,
         NV097_SET_BLEND_FUNC_DFACTOR_V_ZERO,
         NV097_SET_BLEND_EQUATION_V_FUNC_ADD},
        {NV097_SET_BLEND_FUNC_SFACTOR_V_SRC_ALPHA_SATURATE,
         NV097_SET_BLEND_FUNC_DFACTOR_V_ZERO,
         NV097_SET_BLEND_EQUATION_V_FUNC_ADD},
        {NV097_SET_BLEND_FUNC_SFACTOR_V_CONSTANT_COLOR,
         NV097_SET_BLEND_FUNC_DFACTOR_V_ZERO,
         NV097_SET_BLEND_EQUATION_V_FUNC_ADD},
        {NV097_SET_BLEND_FUNC_SFACTOR_V_ONE_MINUS_CONSTANT_COLOR,
         NV097_SET_BLEND_FUNC_DFACTOR_V_ZERO,
         NV097_SET_BLEND_EQUATION_V_FUNC_ADD},
        {NV097_SET_BLEND_FUNC_SFACTOR_V_CONSTANT_ALPHA,
         NV097_SET_BLEND_FUNC_DFACTOR_V_ZERO,
         NV097_SET_BLEND_EQUATION_V_FUNC_ADD},
        {NV097_SET_BLEND_FUNC_SFACTOR_V_ONE_MINUS_CONSTANT_ALPHA,
         NV097_SET_BLEND_FUNC_DFACTOR_V_ZERO,
         NV097_SET_BLEND_EQUATION_V_FUNC_ADD},
        {NV097_SET_BLEND_FUNC_SFACTOR_V_ONE,
         NV097_SET_BLEND_FUNC_DFACTOR_V_ZERO,
         NV097_SET_BLEND_EQUATION_V_FUNC_SUBTRACT},
        {NV097_SET_BLEND_FUNC_SFACTOR_V_ONE,
         NV097_SET_BLEND_FUNC_DFACTOR_V_ZERO,
         NV097_SET_BLEND_EQUATION_V_FUNC_REVERSE_SUBTRACT},
    }};
static_assert(kPipelineVariants.size() == kPipelineVariantCount);

static constexpr bool AllPipelineVariantsHaveUniqueBlendIdentity() {
  for (size_t lhs = 0; lhs < kPipelineVariants.size(); ++lhs) {
    for (size_t rhs = lhs + 1; rhs < kPipelineVariants.size(); ++rhs) {
      const PipelineVariant &a = kPipelineVariants[lhs];
      const PipelineVariant &b = kPipelineVariants[rhs];
      if (a.source_factor == b.source_factor &&
          a.destination_factor == b.destination_factor &&
          a.blend_equation == b.blend_equation) {
        return false;
      }
    }
  }
  return true;
}
static_assert(AllPipelineVariantsHaveUniqueBlendIdentity());

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
  tests_[kPipelineTrain] = [this]() {
    RunPipelineScenario(kPipelineTrain, kPipelineVariantCount, 1, false,
                        false);
  };
  tests_[kPipelineCapacityCMinusOne] = [this]() {
    RunPipelineScenario(kPipelineCapacityCMinusOne,
                        kPipelineJobCapacity - 1, 1, false, true);
  };
  tests_[kPipelineCapacityC] = [this]() {
    RunPipelineScenario(kPipelineCapacityC, kPipelineJobCapacity, 1, false,
                        true);
  };
  tests_[kPipelineCapacityCPlusOne] = [this]() {
    RunPipelineScenario(kPipelineCapacityCPlusOne,
                        kPipelineJobCapacity + 1, 2, false, true);
  };
  tests_[kPipelineIdenticalReplay] = [this]() {
    RunPipelineScenario(kPipelineIdenticalReplay,
                        kPipelineVariantCount, 2, false, false);
  };
  tests_[kPipelineUniformOnly] = [this]() {
    RunPipelineScenario(kPipelineUniformOnly,
                        kPipelineVariantCount, 1, true, false);
  };
  tests_[kReadinessTrainVisible] = [this]() {
    RunReadinessScenario(kReadinessTrainVisible, 1, false);
  };
  tests_[kReadinessReplayVisible] = [this]() {
    RunReadinessScenario(kReadinessReplayVisible, 1, false);
  };
  tests_[kReadinessIdenticalReplay] = [this]() {
    RunReadinessScenario(kReadinessIdenticalReplay, 2, false);
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

void ShaderLifecycleTests::DrawPipelineVariants(uint32_t variant_count,
                                                uint32_t passes,
                                                bool uniform_only,
                                                bool safe_omission) const {
  host_.PrepareDraw(kBackgroundColor);
  host_.SetFinalCombiner0Just(TestHost::SRC_DIFFUSE);
  host_.SetFinalCombiner1Just(TestHost::SRC_ZERO, true, true);

  Pushbuffer::Begin();
  Pushbuffer::Push(NV097_SET_ALPHA_TEST_ENABLE, false);
  Pushbuffer::Push(NV097_SET_DEPTH_TEST_ENABLE, false);
  Pushbuffer::Push(NV097_SET_DEPTH_MASK, false);
  Pushbuffer::Push(NV097_SET_STENCIL_TEST_ENABLE, false);
  Pushbuffer::Push(NV097_SET_CULL_FACE_ENABLE, false);
  Pushbuffer::End();

  static constexpr float kLeft = 48.f;
  static constexpr float kTop = 96.f;
  static constexpr float kTileWidth = 64.f;
  static constexpr float kTileHeight = 56.f;
  static constexpr uint32_t kColumns = 8;

  for (uint32_t pass = 0; pass < passes; ++pass) {
    for (uint32_t index = 0; index < variant_count; ++index) {
      const PipelineVariant &variant = uniform_only
          ? kPipelineVariants[1]
          : kPipelineVariants[index];
      host_.SetBlend(true);
      Pushbuffer::Begin();
      Pushbuffer::Push(NV097_SET_COLOR_MASK,
                       safe_omission ? 0 : kAllChannels);
      Pushbuffer::Push(NV097_SET_BLEND_FUNC_SFACTOR,
                       variant.source_factor);
      Pushbuffer::Push(NV097_SET_BLEND_FUNC_DFACTOR,
                       variant.destination_factor);
      Pushbuffer::Push(NV097_SET_BLEND_EQUATION, variant.blend_equation);
      Pushbuffer::End();

      host_.SetDiffuse(uniform_only ? UniformColor(index) : kSourceColor);
      const float left = kLeft + (index % kColumns) * kTileWidth;
      const float top = kTop + (index / kColumns) * kTileHeight;
      host_.Begin(TestHost::PRIMITIVE_QUADS);
      host_.SetVertex(left, top, 1.f);
      host_.SetVertex(left + kTileWidth - 4.f, top, 1.f);
      host_.SetVertex(left + kTileWidth - 4.f, top + kTileHeight - 4.f, 1.f);
      host_.SetVertex(left, top + kTileHeight - 4.f, 1.f);
      host_.End();
    }
  }

  host_.SetBlend(false);
  Pushbuffer::Begin();
  Pushbuffer::Push(NV097_SET_COLOR_MASK, kAllChannels);
  Pushbuffer::End();
  if (safe_omission) {
    DrawVisibleSentinel();
  }
}

void ShaderLifecycleTests::DrawVisibleSentinel() const {
  host_.SetBlend(false);
  host_.SetDiffuse(kSentinelColor);
  host_.Begin(TestHost::PRIMITIVE_QUADS);
  host_.SetVertex(kSentinelX, kSentinelY, 1.f);
  host_.SetVertex(kSentinelX + kSentinelSize, kSentinelY, 1.f);
  host_.SetVertex(kSentinelX + kSentinelSize, kSentinelY + kSentinelSize,
                  1.f);
  host_.SetVertex(kSentinelX, kSentinelY + kSentinelSize, 1.f);
  host_.End();
}

uint32_t ShaderLifecycleTests::ValidatePipelineVariants(
    uint32_t variant_count, bool safe_omission) const {
  static constexpr uint32_t kColumns = 8;
  static constexpr uint32_t kLeft = 48;
  static constexpr uint32_t kTop = 96;
  static constexpr uint32_t kTileWidth = 64;
  static constexpr uint32_t kTileHeight = 56;
  uint32_t checksum = kFnvOffsetBasis;
  for (uint32_t index = 0; index < variant_count; ++index) {
    const uint32_t x = kLeft + (index % kColumns) * kTileWidth + 8;
    const uint32_t y = kTop + (index / kColumns) * kTileHeight + 8;
    const uint32_t pixel = ReadPixel(x, y);
    if (safe_omission) {
      ASSERT(pixel == kBackgroundColor);
    } else {
      ASSERT(pixel != kBackgroundColor);
    }
    checksum = Fnv1aWord(checksum, pixel);
  }
  if (safe_omission) {
    const uint32_t sentinel = ReadPixel(kSentinelX, kSentinelY);
    ASSERT(ReadPixel(kSentinelX, kSentinelY) != kBackgroundColor);
    checksum = Fnv1aWord(checksum, sentinel);
  }
  return checksum;
}

void ShaderLifecycleTests::RunPipelineScenario(const char *test_name,
                                               uint32_t variant_count,
                                               uint32_t passes,
                                               bool uniform_only,
                                               bool safe_omission) {
  ASSERT(variant_count > 0 && variant_count <= kPipelineVariantCount);
  ConfigureFixedShader();
  auto results = Profile(test_name, 1, [this, variant_count, passes,
                                        uniform_only, safe_omission]() {
    DrawPipelineVariants(variant_count, passes, uniform_only, safe_omission);
  });
  host_.WaitForGpu();
  EmitXemuPerfMarker(kXemuPerfMarkerGpuComplete);
  const uint32_t result_kat =
      ValidatePipelineVariants(variant_count, safe_omission);
  PrintMsg("SHADER_LIFECYCLE_PIPELINE variants=%lu passes=%lu uniform_only=%lu safe_omission=%lu result_kat=%08lx\n",
           static_cast<unsigned long>(variant_count),
           static_cast<unsigned long>(passes),
           static_cast<unsigned long>(uniform_only),
           static_cast<unsigned long>(safe_omission),
           static_cast<unsigned long>(result_kat));
  host_.FinishDraw(suite_name_, test_name, results);
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

void ShaderLifecycleTests::DrawReadinessFamilies(uint32_t passes,
                                                 bool uniform_only) const {
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

void ShaderLifecycleTests::RunReadinessScenario(const char *test_name,
                                                uint32_t passes,
                                                bool uniform_only) {
  ConfigureFixedShader();
  auto results = Profile(test_name, 1, [this, passes, uniform_only]() {
    DrawReadinessFamilies(passes, uniform_only);
  });
  host_.WaitForGpu();
  EmitXemuPerfMarker(kXemuPerfMarkerGpuComplete);
  const uint32_t result_kat = ValidateReadinessFamilies(uniform_only);
  PrintMsg("SHADER_LIFECYCLE_READINESS families=%lu combiner_variants=%lu "
           "passes=%lu uniform_only=%lu no_omission=1 result_kat=%08lx\n",
           static_cast<unsigned long>(kReadinessFamilyCount),
           static_cast<unsigned long>(kReadinessCombinerVariantCount),
           static_cast<unsigned long>(passes),
           static_cast<unsigned long>(uniform_only),
           static_cast<unsigned long>(result_kat));
  host_.FinishDraw(suite_name_, test_name, results);
}
