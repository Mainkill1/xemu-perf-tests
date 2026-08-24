#include "surface_rendering_tests.h"

#include <cstring>

#include <texture_generator.h>

#include "test_host.h"

static constexpr char kBasicTestName[] = "SurfaceRendering";
static constexpr char kXemuSurfaceDownloadTestName[] = "XemuSurfaceDownloadPath";
static constexpr char kXemuOverlapRepresentativeTestName[] =
    "XemuOverlappingSurfaceChurnRepresentative";
static constexpr char kXemuOverlapStressTestName[] =
    "XemuOverlappingSurfaceChurnStress";
static constexpr char kXemuFullClearElisionGuardTestName[] =
    "XemuFullClearElisionGuard";

static constexpr uint32_t kIterations = 10;
static constexpr uint32_t kNumDrawsSingleFrame = 80;

static constexpr uint32_t kTextureWidth = 128;
static constexpr uint32_t kTextureHeight = 128;

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
