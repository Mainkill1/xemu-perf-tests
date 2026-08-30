#include "surface_rendering_tests.h"

#include <array>
#include <cassert>
#include <cstring>
#include <memory>
#include <sstream>

#include <pbkit/pbkit.h>
#include <texture_generator.h>
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wmacro-redefined"
#include <windows.h>
#pragma clang diagnostic pop

#include "debug_output.h"
#include "shaders/passthrough_vertex_shader.h"
#include "test_host.h"
#include "vertex_buffer.h"

static constexpr char kBasicTestName[] = "SurfaceRendering";
static constexpr char kXemuSurfaceDownloadTestName[] = "XemuSurfaceDownloadPath";
static constexpr char kXemuOverlapRepresentativeTestName[] =
    "XemuOverlappingSurfaceChurnRepresentative";
static constexpr char kXemuOverlapStressTestName[] =
    "XemuOverlappingSurfaceChurnStress";
static constexpr char kXemuFullClearElisionGuardTestName[] =
    "XemuFullClearElisionGuard";
static constexpr char kXemuPartialChannelClearGuardTestName[] =
    "XemuPartialChannelClearGuard";
static constexpr char kXemuSurfaceListLookup002TestName[] =
    "XemuSurfaceListLookup002";
static constexpr char kXemuSurfaceListLookup008TestName[] =
    "XemuSurfaceListLookup008";
static constexpr char kXemuSurfaceListLookup032TestName[] =
    "XemuSurfaceListLookup032";
static constexpr char kXemuSurfaceListLookup128TestName[] =
    "XemuSurfaceListLookup128";
static constexpr char kXemuFramebufferWorkingSet002TestName[] =
    "XemuFramebufferWorkingSet002";
static constexpr char kXemuFramebufferWorkingSet008TestName[] =
    "XemuFramebufferWorkingSet008";
static constexpr char kXemuFramebufferWorkingSet032TestName[] =
    "XemuFramebufferWorkingSet032";
static constexpr char kXemuFramebufferWorkingSet064TestName[] =
    "XemuFramebufferWorkingSet064";
static constexpr char kXemuCpuReadCleanSurfaceTestName[] =
    "XemuCpuReadCleanSurface";
static constexpr char kXemuCpuReadAfterGpuWriteTestName[] =
    "XemuCpuReadAfterGpuWrite";
static constexpr char kXemuVulkanMemoryPressureRepresentativeTestName[] =
    "XemuVulkanMemoryPressureRepresentative";
static constexpr char kXemuVulkanMemoryPressureStressTestName[] =
    "XemuVulkanMemoryPressureStress";

static constexpr uint32_t kIterations = 10;
static constexpr uint32_t kNumDrawsSingleFrame = 80;

static constexpr uint32_t kTextureWidth = 128;
static constexpr uint32_t kTextureHeight = 128;

// The workload deliberately uses a fixed, address-indexed recipe.  It is not
// a capacity probe: Representative and Stress differ only by their guest
// pressure multiplier and therefore their identity count. Xemu render scale
// is intentionally external to this guest workload.
static constexpr uint32_t kVulkanMemoryPressureSeed = 0x564D5052;
static constexpr uint32_t kVulkanMemoryPressureTargetsPerPressureMultiplier = 16;
static constexpr uint32_t kVulkanMemoryPressureCyclesPerSample = 4;
static constexpr uint32_t kVulkanMemoryPressureProfileSamples = 4;
static constexpr uint32_t kVulkanMemoryPressureSurfaceStride = 0x50000;
static constexpr uint32_t kVulkanMemoryPressureAliasOffset = 0x1800;
static constexpr uint32_t kVulkanMemoryPressureMaxTargetCount = 64;
static constexpr uint32_t kVulkanMemoryPressureMaxSurfaceBytes = 256 * 256 * sizeof(uint32_t);
static constexpr uint32_t kVulkanMemoryPressureOracleKat = 0x0D626FA0;
static constexpr uint32_t kVulkanMemoryPressureOracleColors[] = {
    0xFF3C78B4, 0xFFB46E3C, 0xFF56A866, 0xFF9A4FB4,
};

enum class VulkanMemoryPressurePhase : uint32_t {
  GROWTH = 0,
  PLATEAU = 1,
  ALIAS_RESIZE = 2,
  REUSE = 3,
  IDLE_RETENTION = 4,
};

static uint32_t HashVulkanMemoryPressureU32(uint32_t hash, uint32_t value) {
  for (uint32_t byte = 0; byte < 4; ++byte) {
    hash ^= (value >> (byte * 8)) & 0xFF;
    hash *= 16777619U;
  }
  return hash;
}

static void BindSurfaceTextureAddress(const uint8_t *address) {
  uint32_t *push = pb_begin();
  push = pb_push1(push, NV097_SET_TEXTURE_OFFSET,
                  reinterpret_cast<uint32_t>(address) & 0x03FFFFFFU);
  pb_end(push);
}

SurfaceRenderingTests::SurfaceRenderingTests(TestHost &host, std::string output_dir, const Config &config)
    : TestSuite(host, std::move(output_dir), "SurfaceRendering", config) {
  tests_[kBasicTestName] = [this]() { Test(); };
  tests_[kXemuSurfaceDownloadTestName] = [this]() { TestXemuForceSurfaceDownloadPath(); };
  tests_[kXemuOverlapRepresentativeTestName] = [this]() {
    TestXemuOverlappingSurfaceChurn(kXemuOverlapRepresentativeTestName, 1, 100);
  };
  tests_[kXemuOverlapStressTestName] = [this]() {
    TestXemuOverlappingSurfaceChurn(kXemuOverlapStressTestName, 20, 10);
  };
  tests_[kXemuFullClearElisionGuardTestName] = [this]() {
    TestXemuFullClearElisionGuard();
  };
  tests_[kXemuPartialChannelClearGuardTestName] = [this]() {
    TestXemuPartialChannelClearGuard();
  };
  tests_[kXemuSurfaceListLookup002TestName] = [this]() {
    TestXemuSurfaceListLookup(kXemuSurfaceListLookup002TestName, 2);
  };
  tests_[kXemuSurfaceListLookup008TestName] = [this]() {
    TestXemuSurfaceListLookup(kXemuSurfaceListLookup008TestName, 8);
  };
  tests_[kXemuSurfaceListLookup032TestName] = [this]() {
    TestXemuSurfaceListLookup(kXemuSurfaceListLookup032TestName, 32);
  };
  tests_[kXemuSurfaceListLookup128TestName] = [this]() {
    TestXemuSurfaceListLookup(kXemuSurfaceListLookup128TestName, 128);
  };
  tests_[kXemuFramebufferWorkingSet002TestName] = [this]() {
    TestXemuFramebufferWorkingSet(kXemuFramebufferWorkingSet002TestName, 2);
  };
  tests_[kXemuFramebufferWorkingSet008TestName] = [this]() {
    TestXemuFramebufferWorkingSet(kXemuFramebufferWorkingSet008TestName, 8);
  };
  tests_[kXemuFramebufferWorkingSet032TestName] = [this]() {
    TestXemuFramebufferWorkingSet(kXemuFramebufferWorkingSet032TestName, 32);
  };
  tests_[kXemuFramebufferWorkingSet064TestName] = [this]() {
    TestXemuFramebufferWorkingSet(kXemuFramebufferWorkingSet064TestName, 64);
  };
  tests_[kXemuCpuReadCleanSurfaceTestName] = [this]() {
    TestXemuCpuReadCleanSurface();
  };
  tests_[kXemuCpuReadAfterGpuWriteTestName] = [this]() {
    TestXemuCpuReadAfterGpuWrite();
  };
  tests_[kXemuVulkanMemoryPressureRepresentativeTestName] = [this]() {
    TestXemuVulkanMemoryPressure(kXemuVulkanMemoryPressureRepresentativeTestName, 1);
  };
  tests_[kXemuVulkanMemoryPressureStressTestName] = [this]() {
    TestXemuVulkanMemoryPressure(kXemuVulkanMemoryPressureStressTestName, 4);
  };
}

/**
 * Initializes the test suite and creates test cases.
 *
 * @tc SurfaceRendering
 *  Renders to various offscreen buffers before blitting to the screen.
 *
 * @tc XemuSurfaceDownloadPath
 *  Renders to an ARGB8 surface, then uses it as an R5G6B5 texture. This forces xemu to perform a download from host GPU
 *  memory, triggering a potentially pathological slowdown as seen in xemu#2790.
 */
void SurfaceRenderingTests::Initialize() {
  TestSuite::Initialize();

  PBKitPlusPlus::GenerateSwizzledRGBRadialGradient(host_.GetTextureMemoryForStage(2), kTextureWidth, kTextureHeight);
  PBKitPlusPlus::GenerateSwizzledRGBMaxContrastNoisePattern(host_.GetTextureMemoryForStage(3), kTextureWidth,
                                                            kTextureHeight);

  host_.SetBlend(false);
  host_.SetVertexShaderProgram(nullptr);

  // Zeta writes are disabled to allow the zeta buffer to be assigned to arbitrary memory in order to avoid a GPU
  // exception when setting the offscreen render target with swizzling enabled.
  PBKitPlusPlus::Pushbuffer::Begin();
  PBKitPlusPlus::Pushbuffer::Push(NV097_SET_DEPTH_MASK, false);
  PBKitPlusPlus::Pushbuffer::Push(NV097_SET_STENCIL_MASK, false);
  PBKitPlusPlus::Pushbuffer::End();

  host_.SetFinalCombiner1Just(PBKitPlusPlus::NV2AState::SRC_ZERO, true, true);
}

static void DrawBiTri(TestHost &host, float left, float top, float span_x, float span_y,
                      PBKitPlusPlus::NV2AState::CombinerSource tex_top,
                      PBKitPlusPlus::NV2AState::CombinerSource tex_bottom) {
  static constexpr float kZ = 1.f;

  host.SetFinalCombiner0Just(tex_top);
  host.Begin(PBKitPlusPlus::NV2AState::PRIMITIVE_TRIANGLES);
  host.SetTexCoord0(0.f, 0.f);
  host.SetTexCoord2(0.f, 0.f);
  host.SetVertex(left, top, kZ);
  host.SetTexCoord0(1.f, 0.f);
  host.SetTexCoord2(1.f, 0.f);
  host.SetVertex(left + span_x, top, kZ);
  host.SetTexCoord0(0.f, 1.f);
  host.SetTexCoord2(0.f, 1.f);
  host.SetVertex(left, top + span_y, kZ);
  host.End();

  host.SetFinalCombiner0Just(tex_bottom);
  host.Begin(PBKitPlusPlus::NV2AState::PRIMITIVE_TRIANGLES);
  host.SetTexCoord1(0.f, 1.f);
  host.SetTexCoord3(0.f, 1.f);
  host.SetVertex(left, top + span_y, kZ);
  host.SetTexCoord1(1.f, 0.f);
  host.SetTexCoord3(1.f, 0.f);
  host.SetVertex(left + span_x, top, kZ);
  host.SetTexCoord1(1.f, 1.f);
  host.SetTexCoord3(1.f, 1.f);
  host.SetVertex(left + span_x, top + span_y, kZ);
  host.End();
}

static void ClearColorRegionMasked(uint32_t argb, uint32_t left,
                                   uint32_t top, uint32_t width,
                                   uint32_t height, uint32_t channel_mask) {
  PBKitPlusPlus::Pushbuffer::Begin();
  PBKitPlusPlus::Pushbuffer::Push(
      NV097_SET_CLEAR_RECT_HORIZONTAL,
      ((left + width - 1) << 16) | (left & 0xFFFF));
  PBKitPlusPlus::Pushbuffer::Push(
      NV097_SET_CLEAR_RECT_VERTICAL,
      ((top + height - 1) << 16) | (top & 0xFFFF));
  PBKitPlusPlus::Pushbuffer::Push(NV097_SET_COLOR_CLEAR_VALUE, argb);
  PBKitPlusPlus::Pushbuffer::Push(NV097_CLEAR_SURFACE, channel_mask);
  PBKitPlusPlus::Pushbuffer::End();
}

void SurfaceRenderingTests::Test() {
  host_.SetupFixedFunctionPassthrough();
  host_.PrepareDraw(0xFF444444);

  TestHost::ProfileResults results{};

  auto fill_surface = [this]() {
    host_.SetTextureStageEnabled(0, false);
    host_.SetTextureStageEnabled(1, false);
    auto format = PBKitPlusPlus::GetTextureFormatInfo(NV097_SET_TEXTURE_FORMAT_COLOR_SZ_A8B8G8R8);
    for (auto i = 2; i < 4; ++i) {
      auto &texture_stage = host_.GetTextureStage(i);
      texture_stage.SetFormat(format);
      texture_stage.SetTextureDimensions(kTextureWidth, kTextureHeight);
      texture_stage.SetEnabled(true);
    }
    host_.SetupTextureStages();
    host_.SetShaderStageProgram(TestHost::STAGE_NONE, TestHost::STAGE_NONE, TestHost::STAGE_2D_PROJECTIVE,
                                TestHost::STAGE_2D_PROJECTIVE);

    DrawBiTri(host_, 0.f, 0.f, kTextureWidth, kTextureHeight, PBKitPlusPlus::NV2AState::SRC_TEX2,
              PBKitPlusPlus::NV2AState::SRC_TEX3);

    host_.SetTextureStageEnabled(2, false);
    host_.SetTextureStageEnabled(3, false);
    host_.SetupTextureStages();
    host_.SetShaderStageProgram(TestHost::STAGE_NONE);
  };

  const float screen_w = host_.GetFramebufferWidthF();
  const float screen_h = host_.GetFramebufferHeightF();
  const float center_x = screen_w * 0.5f;
  const float center_y = screen_h * 0.5f;

  const float span_x = screen_w * 0.25f;
  const float span_y = screen_h * 0.25f;
  const float left = center_x - (span_x * 0.5f);
  const float top = center_y - (span_y * 0.5f);

  static constexpr uint32_t kNumDrawsMultiframe60FPS = 40;
  const uint32_t num_draws = host_.GetSaveResults() ? kNumDrawsSingleFrame : kNumDrawsMultiframe60FPS;
  results = Profile(kBasicTestName, kIterations, [this, num_draws, &fill_surface, left, top, span_x, span_y] {
    for (auto i = 0; i < num_draws; ++i) {
      host_.RenderToSurfaceStart(host_.GetTextureMemoryForStage(0), PBKitPlusPlus::NV2AState::SCF_A8R8G8B8,
                                 host_.GetTextureMemoryForStage(1), PBKitPlusPlus::NV2AState::SZF_Z24S8, kTextureWidth,
                                 kTextureHeight, true);
      fill_surface();
      host_.RenderToSurfaceEnd();

      host_.RenderToSurfaceStart(host_.GetTextureMemoryForStage(1), PBKitPlusPlus::NV2AState::SCF_R5G6B5,
                                 host_.GetTextureMemoryForStage(0), PBKitPlusPlus::NV2AState::SZF_Z16, kTextureWidth,
                                 kTextureHeight, true);
      fill_surface();
      host_.RenderToSurfaceEnd();

      {
        auto &texture_stage = host_.GetTextureStage(0);
        texture_stage.SetFormat(PBKitPlusPlus::GetTextureFormatInfo(NV097_SET_TEXTURE_FORMAT_COLOR_SZ_A8R8G8B8));
        texture_stage.SetTextureDimensions(kTextureWidth, kTextureHeight);
        texture_stage.SetEnabled(true);
      }
      {
        auto &texture_stage = host_.GetTextureStage(1);
        texture_stage.SetFormat(PBKitPlusPlus::GetTextureFormatInfo(NV097_SET_TEXTURE_FORMAT_COLOR_SZ_R5G6B5));
        texture_stage.SetTextureDimensions(kTextureWidth, kTextureHeight);
        texture_stage.SetEnabled(true);
      }
      host_.SetupTextureStages();
      host_.SetShaderStageProgram(TestHost::STAGE_2D_PROJECTIVE, TestHost::STAGE_2D_PROJECTIVE);

      DrawBiTri(host_, left, top, span_x, span_y, PBKitPlusPlus::NV2AState::SRC_TEX0,
                PBKitPlusPlus::NV2AState::SRC_TEX1);

      host_.SetTextureStageEnabled(0, false);
      host_.SetTextureStageEnabled(1, false);
      host_.SetupTextureStages();
      host_.SetShaderStageProgram(TestHost::STAGE_NONE);
    }
  });

  host_.FinishDraw(suite_name_, kBasicTestName, results);
}

void SurfaceRenderingTests::TestXemuForceSurfaceDownloadPath() {
  host_.SetupFixedFunctionPassthrough();
  host_.PrepareDraw(0xFF454545);

  TestHost::ProfileResults results{};

  const float screen_w = host_.GetFramebufferWidthF();
  const float screen_h = host_.GetFramebufferHeightF();
  const float center_x = screen_w * 0.5f;
  const float center_y = screen_h * 0.5f;

  const float span_x = screen_w * 0.25f;
  const float span_y = screen_h * 0.25f;
  const float left = center_x - span_x;
  const float top = center_y - span_y;
  const float right = left + span_x * 2;
  const float bottom = top + span_y * 2;

  static constexpr uint32_t kNumDrawsMultiframe60FPS = 45;
  const uint32_t num_draws = host_.GetSaveResults() ? kNumDrawsSingleFrame : kNumDrawsMultiframe60FPS;
  results = Profile(kXemuSurfaceDownloadTestName, kIterations, [this, num_draws, left, top, right, bottom] {
    for (auto i = 0; i < num_draws; ++i) {
      // Render something to texture memory, treating it as an ARGB8 surface.
      {
        host_.RenderToSurfaceStart(host_.GetTextureMemoryForStage(0), PBKitPlusPlus::NV2AState::SCF_A8R8G8B8,
                                   host_.GetTextureMemoryForStage(1), PBKitPlusPlus::NV2AState::SZF_Z24S8,
                                   kTextureWidth, kTextureHeight, true);

        auto &texture_stage = host_.GetTextureStage(2);
        texture_stage.SetFormat(PBKitPlusPlus::GetTextureFormatInfo(NV097_SET_TEXTURE_FORMAT_COLOR_SZ_A8B8G8R8));
        texture_stage.SetTextureDimensions(kTextureWidth, kTextureHeight);
        texture_stage.SetEnabled(true);
        host_.SetupTextureStages();
        host_.SetShaderStageProgram(TestHost::STAGE_NONE, TestHost::STAGE_NONE, TestHost::STAGE_2D_PROJECTIVE,
                                    TestHost::STAGE_NONE);

        host_.SetFinalCombiner0Just(PBKitPlusPlus::NV2AState::SRC_TEX2);
        host_.DrawSwizzledTexturedScreenQuad(0.f, 0.f, kTextureWidth, kTextureHeight, 1.f);

        host_.SetTextureStageEnabled(2, false);
        host_.SetupTextureStages();
        host_.SetShaderStageProgram(TestHost::STAGE_NONE);

        host_.RenderToSurfaceEnd();
      }

      // Now render to the backbuffer, using the just-rendered texture but configured as an incompatible texture format
      // to force xemu to perform a download via
      // https://github.com/xemu-project/xemu/blob/fd0ae0c0a189d56e87f8e46073b15b287e4a1e1a/hw/xbox/nv2a/pgraph/gl/texture.c#L311
      {
        auto &texture_stage = host_.GetTextureStage(0);
        texture_stage.SetFormat(PBKitPlusPlus::GetTextureFormatInfo(NV097_SET_TEXTURE_FORMAT_COLOR_SZ_R5G6B5));
        texture_stage.SetTextureDimensions(kTextureWidth, kTextureHeight);
        texture_stage.SetEnabled(true);
        host_.SetupTextureStages();
        host_.SetShaderStageProgram(TestHost::STAGE_2D_PROJECTIVE);

        host_.SetFinalCombiner0Just(PBKitPlusPlus::NV2AState::SRC_TEX0);
        host_.DrawSwizzledTexturedScreenQuad(left, top, right, bottom, 1.f);

        host_.SetTextureStageEnabled(0, false);
        host_.SetTextureStageEnabled(1, false);
        host_.SetupTextureStages();
        host_.SetShaderStageProgram(TestHost::STAGE_NONE);
        host_.SetFinalCombiner0Just(PBKitPlusPlus::NV2AState::SRC_DIFFUSE);
      }
    }
  });

  host_.FinishDraw(suite_name_, kXemuSurfaceDownloadTestName, results);
}

void SurfaceRenderingTests::TestXemuOverlappingSurfaceChurn(
    const char *test_name, uint32_t cycles_per_iteration,
    uint32_t iterations) {
  host_.SetupFixedFunctionPassthrough();
  host_.PrepareDraw(0xFF202020);

  struct Target {
    uint32_t offset;
    uint32_t width;
    uint32_t height;
    uint32_t color;
  };

  // This generated layout is reduced from the repeating surface geometry in
  // Jesse's Halo 2 trace. The 160x120 targets partially overlap the two
  // adjacent 128x128 targets, forcing xemu's overlap-eviction policy without
  // using any title data.
  static constexpr Target kTargets[] = {
      {0x00000, 128, 128, 0xFFB04040},
      {0x10000, 128, 128, 0xFF40B040},
      {0x16800, 160, 120, 0xFF4040B0},
      {0x00000, 160, 120, 0xFFB09040},
  };

  uint8_t *const surface_memory = host_.GetTextureMemoryForStage(0);
  auto results = Profile(test_name, iterations,
                         [this, surface_memory, cycles_per_iteration] {
    for (uint32_t cycle = 0; cycle < cycles_per_iteration; ++cycle) {
      for (const auto &target : kTargets) {
        host_.RenderToSurfaceStart(
            surface_memory + target.offset,
            PBKitPlusPlus::NV2AState::SCF_A8R8G8B8, target.width,
            target.height, false);
        host_.ClearColorRegion(target.color, 0, 0, target.width,
                               target.height);
        host_.RenderToSurfaceEnd();
      }
    }
  });

  // Correctness work is outside Profile's measured markers. The final target
  // always occupies the stage-0 base as a 160x120 linear A8R8G8B8 image.
  auto &texture_stage = host_.GetTextureStage(0);
  texture_stage.SetFormat(PBKitPlusPlus::GetTextureFormatInfo(
      NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_A8R8G8B8));
  texture_stage.SetTextureDimensions(160, 120);
  texture_stage.SetEnabled(true);
  host_.SetupTextureStages();
  host_.SetShaderStageProgram(TestHost::STAGE_2D_PROJECTIVE);
  host_.SetFinalCombiner0Just(PBKitPlusPlus::NV2AState::SRC_TEX0);
  host_.DrawTexturedScreenQuad(160.f, 120.f, 480.f, 360.f, 1.f, 160, 120);
  host_.SetTextureStageEnabled(0, false);
  host_.SetupTextureStages();
  host_.SetShaderStageProgram(TestHost::STAGE_NONE);
  host_.SetFinalCombiner0Just(PBKitPlusPlus::NV2AState::SRC_DIFFUSE);

  host_.FinishDraw(suite_name_, test_name, results);
}

void SurfaceRenderingTests::TestXemuFullClearElisionGuard() {
  host_.SetupFixedFunctionPassthrough();
  host_.PrepareDraw(0xFF202020);

  static constexpr uint32_t kSmallWidth = 128;
  static constexpr uint32_t kSmallHeight = 128;
  static constexpr uint32_t kLargeWidth = 160;
  static constexpr uint32_t kLargeHeight = 120;
  static constexpr uint32_t kIterations = 100;

  uint8_t *const surface_memory = host_.GetTextureMemoryForStage(0);
  std::memset(surface_memory, 0x39, kLargeWidth * kLargeHeight * 4);

  auto results = Profile(kXemuFullClearElisionGuardTestName, kIterations,
                         [this, surface_memory] {
    host_.RenderToSurfaceStart(
        surface_memory, PBKitPlusPlus::NV2AState::SCF_A8R8G8B8,
        kSmallWidth, kSmallHeight, false);
    host_.ClearColorRegion(0xFFB04040, 0, 0, kSmallWidth, kSmallHeight);
    host_.RenderToSurfaceEnd();

    // Reinterpret the same base with a larger shape, but clear only the center.
    // The untouched border must come from uploaded VRAM, so this rejects a
    // candidate that treats every clear as a complete overwrite.
    host_.RenderToSurfaceStart(
        surface_memory, PBKitPlusPlus::NV2AState::SCF_A8R8G8B8,
        kLargeWidth, kLargeHeight, false);
    host_.ClearColorRegion(0xFF4060B0, 16, 16,
                           kLargeWidth - 32, kLargeHeight - 32);
    host_.RenderToSurfaceEnd();
  });

  auto &texture_stage = host_.GetTextureStage(0);
  texture_stage.SetFormat(PBKitPlusPlus::GetTextureFormatInfo(
      NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_A8R8G8B8));
  texture_stage.SetTextureDimensions(kLargeWidth, kLargeHeight);
  texture_stage.SetEnabled(true);
  host_.SetupTextureStages();
  host_.SetShaderStageProgram(TestHost::STAGE_2D_PROJECTIVE);
  host_.SetFinalCombiner0Just(PBKitPlusPlus::NV2AState::SRC_TEX0);
  host_.DrawTexturedScreenQuad(160.f, 120.f, 480.f, 360.f, 1.f,
                               kLargeWidth, kLargeHeight);
  host_.SetTextureStageEnabled(0, false);
  host_.SetupTextureStages();
  host_.SetShaderStageProgram(TestHost::STAGE_NONE);
  host_.SetFinalCombiner0Just(PBKitPlusPlus::NV2AState::SRC_DIFFUSE);

  host_.FinishDraw(suite_name_, kXemuFullClearElisionGuardTestName, results);
}

void SurfaceRenderingTests::TestXemuPartialChannelClearGuard() {
  host_.SetupFixedFunctionPassthrough();
  host_.PrepareDraw(0xFF202020);

  static constexpr uint32_t kSmallWidth = 128;
  static constexpr uint32_t kSmallHeight = 128;
  static constexpr uint32_t kLargeWidth = 160;
  static constexpr uint32_t kLargeHeight = 120;
  static constexpr uint32_t kIterations = 100;

  uint8_t *const surface_memory = host_.GetTextureMemoryForStage(0);
  std::memset(surface_memory, 0x39, kLargeWidth * kLargeHeight * 4);

  auto results = Profile(kXemuPartialChannelClearGuardTestName, kIterations,
                         [this, surface_memory] {
    host_.RenderToSurfaceStart(
        surface_memory, PBKitPlusPlus::NV2AState::SCF_A8R8G8B8,
        kSmallWidth, kSmallHeight, false);
    host_.ClearColorRegion(0xFFB04040, 0, 0, kSmallWidth, kSmallHeight);
    host_.RenderToSurfaceEnd();

    // Cover the full larger target but clear only alpha. RGB must be uploaded
    // from VRAM, including the preceding small surface's downloaded contents.
    // This rejects candidates that treat full geometry as a full-byte write.
    host_.RenderToSurfaceStart(
        surface_memory, PBKitPlusPlus::NV2AState::SCF_A8R8G8B8,
        kLargeWidth, kLargeHeight, false);
    ClearColorRegionMasked(0x7F000000, 0, 0, kLargeWidth, kLargeHeight,
                           NV097_CLEAR_SURFACE_A);
    host_.RenderToSurfaceEnd();
  });

  auto &texture_stage = host_.GetTextureStage(0);
  texture_stage.SetFormat(PBKitPlusPlus::GetTextureFormatInfo(
      NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_A8R8G8B8));
  texture_stage.SetTextureDimensions(kLargeWidth, kLargeHeight);
  texture_stage.SetEnabled(true);
  host_.SetupTextureStages();
  host_.SetShaderStageProgram(TestHost::STAGE_2D_PROJECTIVE);
  host_.SetFinalCombiner0Just(PBKitPlusPlus::NV2AState::SRC_TEX0);
  host_.DrawTexturedScreenQuad(160.f, 120.f, 480.f, 360.f, 1.f,
                               kLargeWidth, kLargeHeight);
  host_.SetTextureStageEnabled(0, false);
  host_.SetupTextureStages();
  host_.SetShaderStageProgram(TestHost::STAGE_NONE);
  host_.SetFinalCombiner0Just(PBKitPlusPlus::NV2AState::SRC_DIFFUSE);

  host_.FinishDraw(suite_name_, kXemuPartialChannelClearGuardTestName, results);
}

void SurfaceRenderingTests::TestXemuSurfaceListLookup(
    const char *test_name, uint32_t surface_count) {
  host_.SetupFixedFunctionPassthrough();
  host_.PrepareDraw(0xFF202020);

  static constexpr uint32_t kSurfaceWidth = 16;
  static constexpr uint32_t kSurfaceHeight = 16;
  static constexpr uint32_t kSurfaceBytes =
      kSurfaceWidth * kSurfaceHeight * sizeof(uint32_t);
  static constexpr uint32_t kSwitchPairsPerIteration = 32;
  static constexpr uint32_t kProfileIterations = 20;

  assert(surface_count >= 2 && surface_count <= 128);
  uint8_t *const surface_memory = host_.GetTextureMemoryForStage(0);

  // Populate non-overlapping surfaces before the measured marker. xemu keeps
  // them in insertion order. Alternating the oldest and newest address then
  // gives a stable long-scan/short-scan pair without measuring construction.
  for (uint32_t i = 0; i < surface_count; ++i) {
    host_.RenderToSurfaceStart(
        surface_memory + i * kSurfaceBytes,
        PBKitPlusPlus::NV2AState::SCF_A8R8G8B8, kSurfaceWidth,
        kSurfaceHeight, false);
    host_.ClearColorRegion(0xFF000000 | (i * 0x00010101), 0, 0,
                           kSurfaceWidth, kSurfaceHeight);
    host_.RenderToSurfaceEnd();
  }
  host_.WaitForGpu();

  auto results = Profile(test_name, kProfileIterations,
                         [this, surface_memory, surface_count] {
    for (uint32_t pair = 0; pair < kSwitchPairsPerIteration; ++pair) {
      const uint32_t indices[] = {surface_count - 1, 0};
      for (uint32_t index : indices) {
        host_.RenderToSurfaceStart(
            surface_memory + index * kSurfaceBytes,
            PBKitPlusPlus::NV2AState::SCF_A8R8G8B8, kSurfaceWidth,
            kSurfaceHeight, false);
        host_.ClearColorRegion(0xFF203040 | index, 0, 0, kSurfaceWidth,
                               kSurfaceHeight);
        host_.RenderToSurfaceEnd();
      }
    }
  });

  // Display the oldest target at the stage-0 base so every list-size variant
  // has a deterministic correctness guard independent of scan timing.
  auto &texture_stage = host_.GetTextureStage(0);
  texture_stage.SetFormat(PBKitPlusPlus::GetTextureFormatInfo(
      NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_A8R8G8B8));
  texture_stage.SetTextureDimensions(kSurfaceWidth, kSurfaceHeight);
  texture_stage.SetEnabled(true);
  host_.SetupTextureStages();
  host_.SetShaderStageProgram(TestHost::STAGE_2D_PROJECTIVE);
  host_.SetFinalCombiner0Just(PBKitPlusPlus::NV2AState::SRC_TEX0);
  host_.DrawTexturedScreenQuad(160.f, 120.f, 480.f, 360.f, 1.f,
                               kSurfaceWidth, kSurfaceHeight);
  host_.SetTextureStageEnabled(0, false);
  host_.SetupTextureStages();
  host_.SetShaderStageProgram(TestHost::STAGE_NONE);
  host_.SetFinalCombiner0Just(PBKitPlusPlus::NV2AState::SRC_DIFFUSE);

  host_.FinishDraw(suite_name_, test_name, results);
}

void SurfaceRenderingTests::TestXemuFramebufferWorkingSet(
    const char *test_name, uint32_t active_surface_count) {
  host_.SetupFixedFunctionPassthrough();
  host_.PrepareDraw(0xFF202020);

  static constexpr uint32_t kSurfaceWidth = 16;
  static constexpr uint32_t kSurfaceHeight = 16;
  static constexpr uint32_t kSurfaceBytes =
      kSurfaceWidth * kSurfaceHeight * sizeof(uint32_t);
  static constexpr uint32_t kRequestsPerIteration = 64;
  static constexpr uint32_t kProfileIterations = 20;

  assert(active_surface_count >= 2 && active_surface_count <= 64);
  assert(kRequestsPerIteration % active_surface_count == 0);
  uint8_t *const surface_memory = host_.GetTextureMemoryForStage(0);

  // Populate all active surfaces before measurement, then complete that GPU
  // work. The measured phase has the same 1,280 requests in every variant and
  // differs only in reuse distance. This separates framebuffer working-set
  // capacity from surface construction and total guest method count.
  for (uint32_t i = 0; i < active_surface_count; ++i) {
    host_.RenderToSurfaceStart(
        surface_memory + i * kSurfaceBytes,
        PBKitPlusPlus::NV2AState::SCF_A8R8G8B8, kSurfaceWidth,
        kSurfaceHeight, false);
    host_.ClearColorRegion(0xFF000000 | (i * 0x00010101), 0, 0,
                           kSurfaceWidth, kSurfaceHeight);
    host_.RenderToSurfaceEnd();
  }
  host_.WaitForGpu();

  auto results = Profile(test_name, kProfileIterations,
                         [this, surface_memory, active_surface_count] {
    for (uint32_t request = 0; request < kRequestsPerIteration; ++request) {
      const uint32_t index = request % active_surface_count;
      host_.RenderToSurfaceStart(
          surface_memory + index * kSurfaceBytes,
          PBKitPlusPlus::NV2AState::SCF_A8R8G8B8, kSurfaceWidth,
          kSurfaceHeight, false);
      host_.ClearColorRegion(0xFF203040 | index, 0, 0, kSurfaceWidth,
                             kSurfaceHeight);
      host_.RenderToSurfaceEnd();
    }
  });

  // Surface zero receives a fixed clear in every variant. Displaying it after
  // the measured markers gives the runner a deterministic output guard without
  // contaminating the timed phase with correctness readback work.
  auto &texture_stage = host_.GetTextureStage(0);
  texture_stage.SetFormat(PBKitPlusPlus::GetTextureFormatInfo(
      NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_A8R8G8B8));
  texture_stage.SetTextureDimensions(kSurfaceWidth, kSurfaceHeight);
  texture_stage.SetEnabled(true);
  host_.SetupTextureStages();
  host_.SetShaderStageProgram(TestHost::STAGE_2D_PROJECTIVE);
  host_.SetFinalCombiner0Just(PBKitPlusPlus::NV2AState::SRC_TEX0);
  host_.DrawTexturedScreenQuad(160.f, 120.f, 480.f, 360.f, 1.f,
                               kSurfaceWidth, kSurfaceHeight);
  host_.SetTextureStageEnabled(0, false);
  host_.SetupTextureStages();
  host_.SetShaderStageProgram(TestHost::STAGE_NONE);
  host_.SetFinalCombiner0Just(PBKitPlusPlus::NV2AState::SRC_DIFFUSE);

  host_.FinishDraw(suite_name_, test_name, results);
}

void SurfaceRenderingTests::TestXemuCpuReadCleanSurface() {
  host_.SetupFixedFunctionPassthrough();
  host_.PrepareDraw(0xFF202020);

  static constexpr uint32_t kWidth = 64;
  static constexpr uint32_t kHeight = 64;
  static constexpr uint32_t kWordCount = kWidth * kHeight;
  static constexpr uint32_t kProfileIterations = 100;

  uint8_t *const surface_memory = host_.GetTextureMemoryForStage(0);
  auto *const mutable_words = reinterpret_cast<uint32_t *>(surface_memory);
  auto *const words = reinterpret_cast<volatile uint32_t *>(surface_memory);
  for (uint32_t i = 0; i < kWordCount; ++i) {
    mutable_words[i] = 0x10203040u ^ i;
  }

  // Bind a valid surface without drawing to it. Its CPU memory remains newer
  // than the host image, so every read below is a coherency no-op even though
  // xemu must still recognize that the address belongs to a surface.
  host_.RenderToSurfaceStart(
      surface_memory, PBKitPlusPlus::NV2AState::SCF_A8R8G8B8,
      kWidth, kHeight, false);
  host_.RenderToSurfaceEnd();
  host_.WaitForGpu();

  uint64_t checksum = 14695981039346656037ULL;
  auto results = Profile(kXemuCpuReadCleanSurfaceTestName,
                         kProfileIterations, [&checksum, words] {
    for (uint32_t i = 0; i < kWordCount; ++i) {
      checksum ^= words[i];
      checksum *= 1099511628211ULL;
    }
  });

  host_.ClearColorRegion(0xFF000000 | static_cast<uint32_t>(checksum),
                         0, 0,
                         static_cast<uint32_t>(host_.GetFramebufferWidthF()),
                         static_cast<uint32_t>(host_.GetFramebufferHeightF()));
  host_.FinishDraw(suite_name_, kXemuCpuReadCleanSurfaceTestName, results);
}

void SurfaceRenderingTests::TestXemuCpuReadAfterGpuWrite() {
  host_.SetupFixedFunctionPassthrough();
  host_.PrepareDraw(0xFF202020);

  static constexpr uint32_t kWidth = 32;
  static constexpr uint32_t kHeight = 32;
  static constexpr uint32_t kWordCount = kWidth * kHeight;
  static constexpr uint32_t kProfileIterations = 20;

  uint8_t *const surface_memory = host_.GetTextureMemoryForStage(0);
  auto *const words = reinterpret_cast<volatile uint32_t *>(surface_memory);
  uint32_t iteration = 0;
  uint64_t checksum = 14695981039346656037ULL;

  auto results = Profile(kXemuCpuReadAfterGpuWriteTestName,
                         kProfileIterations,
                         [this, surface_memory, words, &iteration, &checksum] {
    const uint32_t color = 0xFF102030u + iteration++;
    host_.RenderToSurfaceStart(
        surface_memory, PBKitPlusPlus::NV2AState::SCF_A8R8G8B8,
        kWidth, kHeight, false);
    host_.ClearColorRegion(color, 0, 0, kWidth, kHeight);
    host_.RenderToSurfaceEnd();
    host_.WaitForGpu();

    // The first read must download newer GPU contents. The rest deliberately
    // exercise clean reads from the now-synchronized surface.
    for (uint32_t i = 0; i < kWordCount; ++i) {
      checksum ^= words[i];
      checksum *= 1099511628211ULL;
    }
  });

  host_.ClearColorRegion(0xFF000000 | static_cast<uint32_t>(checksum),
                         0, 0,
                         static_cast<uint32_t>(host_.GetFramebufferWidthF()),
                         static_cast<uint32_t>(host_.GetFramebufferHeightF()));
  host_.FinishDraw(suite_name_, kXemuCpuReadAfterGpuWriteTestName, results);
}

void SurfaceRenderingTests::TestXemuVulkanMemoryPressure(const char *test_name,
                                                          uint32_t guest_pressure_multiplier) {
  struct TargetShape {
    uint32_t width;
    uint32_t height;
    TestHost::SurfaceColorFormat surface_format;
    uint32_t texture_format;
  };
  static constexpr TargetShape kTargetShapes[] = {
      {256, 256, TestHost::SCF_A8R8G8B8,
       NV097_SET_TEXTURE_FORMAT_COLOR_SZ_A8R8G8B8},
      {224, 192, TestHost::SCF_R5G6B5,
       NV097_SET_TEXTURE_FORMAT_COLOR_SZ_R5G6B5},
      {192, 224, TestHost::SCF_A8R8G8B8,
       NV097_SET_TEXTURE_FORMAT_COLOR_SZ_A8R8G8B8},
      {160, 128, TestHost::SCF_R5G6B5,
       NV097_SET_TEXTURE_FORMAT_COLOR_SZ_R5G6B5},
  };
  static constexpr const char *kPhaseNames[] = {
      "growth", "plateau", "alias_resize", "reuse", "idle_retention",
  };
  static constexpr const char *kMemoryExpectations[] = {
      "growth_from_unique_surface_texture_keys",
      "plateau_no_new_surface_texture_keys",
      "cache_retention_allowed_for_overlapping_alias_resize_keys",
      "plateau_reuse_of_original_surface_texture_keys",
      "cache_retention_observable_without_new_work_keys",
  };
  static_assert(sizeof(kTargetShapes) / sizeof(kTargetShapes[0]) == 4);
  static_assert(sizeof(kPhaseNames) / sizeof(kPhaseNames[0]) == 5);

  assert(guest_pressure_multiplier == 1 || guest_pressure_multiplier == 4);
  const uint32_t target_count =
      kVulkanMemoryPressureTargetsPerPressureMultiplier * guest_pressure_multiplier;
  assert(target_count <= kVulkanMemoryPressureMaxTargetCount);
  const uint32_t transitions_per_work_iteration =
      target_count * kVulkanMemoryPressureCyclesPerSample;
  // PBKit++ allocates only four 256x256x4 stage backing regions (4 MiB in
  // total). Stress addresses 64 distinct render targets, so it must not use
  // stage-zero memory plus a large offset: that escaped the allocation and
  // eventually overwrote the PFIFO command area. This explicitly sized DMA
  // allocation contains the highest aliased 256x256 ARGB target.
  const uint32_t surface_memory_bytes =
      (target_count - 1U) * kVulkanMemoryPressureSurfaceStride +
      kVulkanMemoryPressureAliasOffset + kVulkanMemoryPressureMaxSurfaceBytes;
  auto *surface_memory = static_cast<uint8_t *>(MmAllocateContiguousMemoryEx(
      surface_memory_bytes, 0, MAXRAM, 0, PAGE_WRITECOMBINE | PAGE_READWRITE));
  ASSERT(surface_memory != nullptr);

  // Every phase receives a distinct event context and Profile marker window.
  // The checkpoints deliberately leave GPU completion outside the measurement:
  // a host RSS/VRAM sampler can classify growth, steady cache retention, and a
  // leak by looking at memory between completed windows instead of timing it.
  auto profile_phase = [this, test_name, guest_pressure_multiplier, target_count,
                        transitions_per_work_iteration,
                        surface_memory](VulkanMemoryPressurePhase phase) {
    const uint32_t phase_index = static_cast<uint32_t>(phase);
    const uint32_t phase_code =
        0x4400U + guest_pressure_multiplier * 0x10U + phase_index;
    const bool use_alias = phase == VulkanMemoryPressurePhase::ALIAS_RESIZE;
    const bool idle = phase == VulkanMemoryPressurePhase::IDLE_RETENTION;
    uint32_t invocation = 0;

    // DrawTexturedScreenQuad uses inline arrays. Before a later surface switch
    // can begin, restore the same no-texture, diffuse-combiner state used by
    // the other surface tests. In particular, do not carry an enabled stage
    // or pending inline-array state from one target identity into the next.
    auto reset_textured_draw_state = [this] {
      host_.SetTextureStageEnabled(0, false);
      host_.SetupTextureStages();
      host_.SetShaderStageProgram(TestHost::STAGE_NONE);
      host_.SetFinalCombiner0Just(TestHost::SRC_DIFFUSE);
    };

    SetXemuPerfEventContext(phase_code, kVulkanMemoryPressureOracleKat);
    EmitXemuPerfEvent(XemuPerfEventType::CONTEXT, 0, kVulkanMemoryPressureSeed,
                      target_count);
    PrintMsg("VULKAN_MEMORY_CHECKPOINT name=%s guest_pressure_multiplier=%lu "
             "xemu_render_scale=external phase=%s "
             "expected_memory=%s guest_identity_count=%lu new_surface_keys=%lu "
             "transitions_per_work_iteration=%lu\n",
             test_name, guest_pressure_multiplier, kPhaseNames[phase_index],
             kMemoryExpectations[phase_index], target_count,
             (phase == VulkanMemoryPressurePhase::GROWTH || use_alias) ? target_count : 0,
             transitions_per_work_iteration);

    const auto results = Profile(
        std::string(test_name) + "-" + kPhaseNames[phase_index],
        kVulkanMemoryPressureProfileSamples,
        [this, surface_memory, target_count, phase_index, use_alias, idle,
         &invocation, &reset_textured_draw_state] {
          auto &texture_stage = host_.GetTextureStage(0);
          const uint32_t seed = kVulkanMemoryPressureSeed +
                                invocation++ * 0x9E3779B9U + phase_index * 0x10001U;
          const uint32_t shape_count = sizeof(kTargetShapes) / sizeof(kTargetShapes[0]);

          if (idle) {
            // This is intentionally a completed display-only window. It
            // performs no RenderToSurfaceStart and binds only a key created by
            // growth, making retained cache memory visible to host telemetry.
            const auto &shape = kTargetShapes[0];
            texture_stage.SetFormat(PBKitPlusPlus::GetTextureFormatInfo(shape.texture_format));
            texture_stage.SetTextureDimensions(shape.width, shape.height);
            texture_stage.SetEnabled(true);
            host_.SetupTextureStages();
            host_.SetShaderStageProgram(TestHost::STAGE_2D_PROJECTIVE);
            host_.SetFinalCombiner0Just(TestHost::SRC_TEX0);
            host_.SetBlend(false);
            BindSurfaceTextureAddress(surface_memory);
            for (uint32_t draw = 0; draw < 16; ++draw) {
              const float left = 96.f + static_cast<float>((draw & 3U) * 112U);
              const float top = 120.f + static_cast<float>((draw >> 2U) * 72U);
              host_.DrawTexturedScreenQuad(left, top, left + 96.f, top + 64.f,
                                           1.f, shape.width, shape.height);
            }
            reset_textured_draw_state();
            return;
          }

          for (uint32_t cycle = 0; cycle < kVulkanMemoryPressureCyclesPerSample;
               ++cycle) {
            for (uint32_t ordinal = 0; ordinal < target_count; ++ordinal) {
              // The odd multiplier makes address visitation deterministic but
              // non-linear. It prevents simple adjacent-address special cases
              // from hiding allocation-key or eviction behavior.
              const uint32_t target =
                  (ordinal * 13U + cycle * 7U + (seed >> 3U)) % target_count;
              // Keep one shape per base address across every repeated
              // sample. Alias/resize rotates that shape exactly once, so the
              // metadata's new-key count remains a fixed target_count.
              const uint32_t shape_index =
                  (target + (use_alias ? 1U : 0U)) % shape_count;
              const auto &shape = kTargetShapes[shape_index];
              const uint32_t alias_offset = use_alias ? kVulkanMemoryPressureAliasOffset : 0;
              uint8_t *const address =
                  surface_memory + target * kVulkanMemoryPressureSurfaceStride + alias_offset;
              const uint32_t clear_color =
                  0xFF000000U | ((seed + target * 0x010203U + cycle * 0x10101U) & 0x00FFFFFFU);

              host_.RenderToSurfaceStart(address, shape.surface_format,
                                         shape.width, shape.height, false);
              host_.ClearColorRegion(clear_color, 0, 0, shape.width, shape.height);
              host_.RenderToSurfaceEnd();

              texture_stage.SetFormat(PBKitPlusPlus::GetTextureFormatInfo(shape.texture_format));
              texture_stage.SetTextureDimensions(shape.width, shape.height);
              texture_stage.SetEnabled(true);
              host_.SetupTextureStages();
              host_.SetShaderStageProgram(TestHost::STAGE_2D_PROJECTIVE);
              host_.SetFinalCombiner0Just(TestHost::SRC_TEX0);
              host_.SetBlend(false);
              BindSurfaceTextureAddress(address);
              const float left = 32.f + static_cast<float>((target & 7U) * 72U);
              const float top = 48.f + static_cast<float>(((target >> 3U) & 3U) * 92U);
              host_.DrawTexturedScreenQuad(left, top, left + 64.f, top + 56.f,
                                           1.f, shape.width, shape.height);
              reset_textured_draw_state();
            }
          }
        });

    std::ostringstream metadata;
    metadata << "{\"schema_version\":1,";
    metadata << "\"kind\":\"vulkan_memory_pressure_checkpoint\",";
    metadata << "\"checkpoint\":\"" << kPhaseNames[phase_index] << "\",";
    metadata << "\"expected_memory_behavior\":\""
             << kMemoryExpectations[phase_index] << "\",";
    metadata << "\"seed\":\"564d5052\",";
    metadata << "\"guest_pressure_multiplier\":" << guest_pressure_multiplier << ",";
    metadata << "\"guest_identity_count\":" << target_count << ",";
    metadata << "\"xemu_render_scale\":\"external\",";
    metadata << "\"new_surface_texture_keys\":"
             << ((phase == VulkanMemoryPressurePhase::GROWTH || use_alias) ? target_count : 0)
             << ",";
    metadata << "\"alias_offset\":" << (use_alias ? kVulkanMemoryPressureAliasOffset : 0) << ",";
    metadata << "\"transitions_per_work_iteration\":"
             << (idle ? 16U : transitions_per_work_iteration) << ",";
    metadata << "\"fixed_profile_samples\":" << kVulkanMemoryPressureProfileSamples;
    metadata << "}";
    host_.RecordProfileResult(suite_name_, std::string(test_name) + "-" + kPhaseNames[phase_index],
                              results, metadata.str());
    EmitXemuPerfHeartbeat();
    return results;
  };

  TestSuite::Initialize();
  host_.SetupFixedFunctionPassthrough();
  host_.PrepareDraw(0xFF141820);
  auto growth_results = profile_phase(VulkanMemoryPressurePhase::GROWTH);
  profile_phase(VulkanMemoryPressurePhase::PLATEAU);
  profile_phase(VulkanMemoryPressurePhase::ALIAS_RESIZE);
  profile_phase(VulkanMemoryPressurePhase::REUSE);
  auto idle_results = profile_phase(VulkanMemoryPressurePhase::IDLE_RETENTION);

  // The post-work oracle owns the framebuffer state. It deliberately uses the
  // established vertex-buffer/pass-through/readback sequence, rather than
  // reinterpreting churned linear surfaces as COLOR_SZ textures or relying on
  // immediate-mode attributes. Those are workload inputs, not a portable
  // correctness representation. Validation remains outside every checkpoint
  // window, so it cannot distort memory progression.
  host_.WaitForGpu();
  MmFreeContiguousMemory(surface_memory);
  TestSuite::Initialize();
  host_.SetupFixedFunctionPassthrough();
  host_.ClearVertexBuffer();
  auto oracle_shader = std::make_shared<PBKitPlusPlus::PassthroughVertexShader>();
  host_.SetVertexShaderProgram(oracle_shader);
  host_.SetBlend(false);
  host_.SetFinalCombiner0Just(TestHost::SRC_DIFFUSE);
  host_.SetFinalCombiner1Just(TestHost::SRC_ZERO, true, true);
  host_.PrepareDraw(0xFF101820);

  static constexpr uint32_t kOracleVertexAttributes =
      TestHost::POSITION | TestHost::DIFFUSE | TestHost::SPECULAR |
      TestHost::WEIGHT | TestHost::TEXCOORD0;
  auto oracle_vertex_buffer = host_.AllocateVertexBuffer(
      sizeof(kVulkanMemoryPressureOracleColors) /
      sizeof(kVulkanMemoryPressureOracleColors[0]) * 4);
  oracle_vertex_buffer->SetPositionIncludesW(true);
  auto vertex = oracle_vertex_buffer->Lock();

  for (uint32_t tile = 0;
       tile < sizeof(kVulkanMemoryPressureOracleColors) / sizeof(kVulkanMemoryPressureOracleColors[0]);
       ++tile) {
    const float left = 112.f + static_cast<float>((tile & 1U) * 216U);
    const float top = 112.f + static_cast<float>((tile >> 1U) * 136U);
    const uint32_t color = kVulkanMemoryPressureOracleColors[tile];
    const float red = static_cast<float>((color >> 16) & 0xFF) / 255.0f;
    const float green = static_cast<float>((color >> 8) & 0xFF) / 255.0f;
    const float blue = static_cast<float>(color & 0xFF) / 255.0f;
    const float positions[4][2] = {
        {left, top}, {left + 200.f, top},
        {left + 200.f, top + 120.f}, {left, top + 120.f},
    };
    for (uint32_t corner = 0; corner < 4; ++corner, ++vertex) {
      vertex->SetPosition(positions[corner][0], positions[corner][1], 0.0f);
      vertex->SetDiffuse(red, green, blue, 1.0f);
      vertex->SetSpecular(0.0f, 0.0f, 0.0f, 0.0f);
      vertex->SetWeight(0.0f);
      vertex->SetTexCoord0(0.0f, 0.0f);
    }
  }
  oracle_vertex_buffer->Unlock();
  host_.SetVertexBuffer(oracle_vertex_buffer);
  host_.DrawArrays(kOracleVertexAttributes, TestHost::PRIMITIVE_QUADS);

  host_.WaitForGpu();
  const auto *const framebuffer =
      reinterpret_cast<volatile const uint8_t *>(pb_back_buffer());
  const uint32_t framebuffer_pitch = pb_back_buffer_pitch();
  uint32_t observed_kat = 2166136261U;
  uint32_t oracle_failure_count = 0;
  uint64_t oracle_failure_mask = 0;
  std::array<uint32_t, sizeof(kVulkanMemoryPressureOracleColors) /
                           sizeof(kVulkanMemoryPressureOracleColors[0])>
      observed_tile_argb{};
  SetXemuPerfEventContext(0x4480U + guest_pressure_multiplier,
                          kVulkanMemoryPressureOracleKat);
  for (uint32_t tile = 0;
       tile < sizeof(kVulkanMemoryPressureOracleColors) / sizeof(kVulkanMemoryPressureOracleColors[0]);
       ++tile) {
    const uint32_t x = 112U + (tile & 1U) * 216U + 100U;
    const uint32_t y = 112U + (tile >> 1U) * 136U + 60U;
    const auto *const pixel = framebuffer + y * framebuffer_pitch + x * sizeof(uint32_t);
    const uint32_t observed_argb = (static_cast<uint32_t>(pixel[3]) << 24) |
                                   (static_cast<uint32_t>(pixel[2]) << 16) |
                                   (static_cast<uint32_t>(pixel[1]) << 8) |
                                   static_cast<uint32_t>(pixel[0]);
    const uint32_t expected_argb = kVulkanMemoryPressureOracleColors[tile];
    observed_tile_argb[tile] = observed_argb;
    observed_kat = HashVulkanMemoryPressureU32(observed_kat, tile);
    observed_kat = HashVulkanMemoryPressureU32(observed_kat, observed_argb);
    PrintMsg("VULKAN_MEMORY_ORACLE tile=%lu x=%lu y=%lu expected=%08lx observed=%08lx\n",
             tile, x, y, expected_argb, observed_argb);
    if (observed_argb != expected_argb) {
      ++oracle_failure_count;
      oracle_failure_mask |= UINT64_C(1) << tile;
      EmitXemuPerfEvent(XemuPerfEventType::FAIL, static_cast<uint16_t>(0x140U + tile),
                        expected_argb, observed_argb);
    }
  }
  if (observed_kat != kVulkanMemoryPressureOracleKat) {
    ++oracle_failure_count;
    oracle_failure_mask |= UINT64_C(1) << 32U;
    EmitXemuPerfEvent(XemuPerfEventType::FAIL, 0x144U,
                      kVulkanMemoryPressureOracleKat, observed_kat);
  }
  if (!oracle_failure_count) {
    EmitXemuPerfEvent(XemuPerfEventType::PASS, 0,
                      kVulkanMemoryPressureOracleKat, observed_kat);
  }
  PrintMsg("VULKAN_MEMORY_ORACLE_KAT expected=%08lx observed=%08lx status=%s "
           "failure_count=%lu failure_mask=%016llx nonfatal=true\n",
           kVulkanMemoryPressureOracleKat, observed_kat,
           oracle_failure_count ? "FAIL" : "PASS", oracle_failure_count,
           static_cast<unsigned long long>(oracle_failure_mask));

  char observed_kat_string[9] = {};
  char oracle_failure_mask_string[17] = {};
  snprintf(observed_kat_string, sizeof(observed_kat_string), "%08lx", observed_kat);
  snprintf(oracle_failure_mask_string, sizeof(oracle_failure_mask_string), "%016llx",
           static_cast<unsigned long long>(oracle_failure_mask));
  std::ostringstream metadata;
  metadata << "{\"schema_version\":1,";
  metadata << "\"kind\":\"vulkan_memory_pressure_summary\",";
  metadata << "\"seed\":\"564d5052\",";
  metadata << "\"guest_pressure_multiplier\":" << guest_pressure_multiplier << ",";
  metadata << "\"guest_identity_count\":" << target_count << ",";
  metadata << "\"xemu_render_scale\":\"external\",";
  metadata << "\"transitions_per_work_iteration\":" << transitions_per_work_iteration << ",";
  metadata << "\"fixed_profile_samples\":" << kVulkanMemoryPressureProfileSamples << ",";
  metadata << "\"checkpoint_count\":5,";
  metadata << "\"oracle_status\":\"" << (oracle_failure_count ? "FAIL" : "PASS") << "\",";
  metadata << "\"oracle_nonfatal\":true,";
  metadata << "\"oracle_failure_count\":" << oracle_failure_count << ",";
  metadata << "\"oracle_failure_mask\":\"" << oracle_failure_mask_string << "\",";
  metadata << "\"oracle_expected_kat\":\"0d626fa0\",";
  metadata << "\"oracle_observed_kat\":\"" << observed_kat_string << "\",";
  metadata << "\"oracle_observed_tiles\":[";
  for (uint32_t tile = 0; tile < observed_tile_argb.size(); ++tile) {
    char observed_tile_string[9] = {};
    snprintf(observed_tile_string, sizeof(observed_tile_string), "%08lx",
             observed_tile_argb[tile]);
    metadata << (tile ? "," : "") << "\"" << observed_tile_string << "\"";
  }
  metadata << "],";
  metadata << "\"oracle_compatibility_key\":\"vulkan-memory-pressure-bgra-v1\",";
  metadata << "\"growth_profile_iterations\":" << growth_results.iterations << ",";
  metadata << "\"idle_profile_iterations\":" << idle_results.iterations;
  metadata << "}";
  host_.FinishDraw(suite_name_, test_name, idle_results, metadata.str());
  ClearXemuPerfEventContext();
}
