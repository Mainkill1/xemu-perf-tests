#include "test_suite.h"

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wignored-attributes"
#include <hal/debug.h>
#pragma clang diagnostic pop

#include <cstdio>
#include <sstream>

#include "debug_output.h"
#include "nxdk_ext.h"
#include "pushbuffer.h"
#include "result_statistics.h"
#include "test_host.h"
#include "texture_format.h"
#include "xbox_math_matrix.h"
#include "xbox_math_types.h"

using namespace PBKitPlusPlus;
using namespace XboxMath;

#define SET_MASK(mask, val) (((val) << (__builtin_ffs(mask) - 1)) & (mask))

TestSuite::TestSuite(TestHost& host, std::string output_dir, std::string suite_name, const Config& config)
    : host_(host), output_dir_(std::move(output_dir)), suite_name_(std::move(suite_name)) {
  output_dir_ += "\\";
  output_dir_ += suite_name_;
  std::replace(output_dir_.begin(), output_dir_.end(), ' ', '_');
}

std::vector<std::string> TestSuite::TestNames() const {
  std::vector<std::string> ret;
  ret.reserve(tests_.size());

  for (auto& kv : tests_) {
    ret.push_back(kv.first);
  }
  return std::move(ret);
}

void TestSuite::DisableTests(const std::set<std::string>& tests_to_skip) {
  for (auto& name : tests_to_skip) {
    tests_.erase(name);
  }
}

void TestSuite::Run(const std::string& test_name, uint32_t frame_count) {
  auto it = tests_.find(test_name);
  if (it == tests_.end()) {
    ASSERT(!"Invalid test name");
  }

  if (!frame_count) {
    host_.PreTest();
  }

  // Draw progress before the test configures NV2A. ShowResultProgress uses the
  // normal render path once a prior result exists, so calling it from Profile
  // would replace workload state between setup and measured execution.
  host_.ShowResultProgress("Test: " + suite_name_ + "::" + test_name);
  BeginXemuPerfTest();
  SetupTest();
  it->second();
  TearDownTest();
  FinishXemuPerfTestFailureScreen();
  host_.RecordSoftTestOutcome(suite_name_, test_name, XemuPerfTestFailed());
}

void TestSuite::RunAll() {
  auto names = TestNames();
  for (const auto& test_name : names) {
    Run(test_name, true);
  }
}

void TestSuite::SetDefaultTextureFormat() const {
  const TextureFormatInfo& texture_format = GetTextureFormatInfo(NV097_SET_TEXTURE_FORMAT_COLOR_SZ_X8R8G8B8);
  host_.SetTextureFormat(texture_format, 0);
  host_.SetDefaultTextureParams(0);
  host_.SetTextureFormat(texture_format, 1);
  host_.SetDefaultTextureParams(1);
  host_.SetTextureFormat(texture_format, 2);
  host_.SetDefaultTextureParams(2);
  host_.SetTextureFormat(texture_format, 3);
  host_.SetDefaultTextureParams(3);
}

void TestSuite::Initialize() {
  const uint32_t kFramebufferPitch = host_.GetFramebufferWidth() * 4;
  host_.SetSurfaceFormat(TestHost::SCF_A8R8G8B8, TestHost::SZF_Z16, host_.GetFramebufferWidth(),
                         host_.GetFramebufferHeight());

  {
    Pushbuffer::Begin();
    Pushbuffer::PushF(NV097_SET_EYE_POSITION, 0.0f, 0.0f, 0.0f, 1.0f);
    Pushbuffer::Push(NV097_SET_ZMIN_MAX_CONTROL, NV097_SET_ZMIN_MAX_CONTROL_CULL_NEAR_FAR_EN_TRUE |
                                                     NV097_SET_ZMIN_MAX_CONTROL_ZCLAMP_EN_CULL |
                                                     NV097_SET_ZMIN_MAX_CONTROL_CULL_IGNORE_W_FALSE);
    Pushbuffer::Push(NV097_SET_SURFACE_PITCH, SET_MASK(NV097_SET_SURFACE_PITCH_COLOR, kFramebufferPitch) |
                                                  SET_MASK(NV097_SET_SURFACE_PITCH_ZETA, kFramebufferPitch));
    Pushbuffer::Push(NV097_SET_SURFACE_CLIP_HORIZONTAL, host_.GetFramebufferWidth() << 16);
    Pushbuffer::Push(NV097_SET_SURFACE_CLIP_VERTICAL, host_.GetFramebufferHeight() << 16);

    Pushbuffer::Push(NV097_SET_LIGHTING_ENABLE, false);
    Pushbuffer::Push(NV097_SET_SPECULAR_ENABLE, false);
    Pushbuffer::Push(NV097_SET_LIGHT_CONTROL, NV097_SET_LIGHT_CONTROL_V_ALPHA_FROM_MATERIAL_SPECULAR |
                                                  NV097_SET_LIGHT_CONTROL_V_SEPARATE_SPECULAR);
    Pushbuffer::Push(NV097_SET_LIGHT_ENABLE_MASK, NV097_SET_LIGHT_ENABLE_MASK_LIGHT0_OFF);
    Pushbuffer::Push(NV097_SET_COLOR_MATERIAL, NV097_SET_COLOR_MATERIAL_ALL_FROM_MATERIAL);
    Pushbuffer::Push(NV097_SET_SCENE_AMBIENT_COLOR, 0x0, 0x0, 0x0);
    Pushbuffer::Push(NV097_SET_MATERIAL_EMISSION, 0x0, 0x0, 0x0);
    Pushbuffer::PushF(NV097_SET_MATERIAL_ALPHA, 1.0f);
    Pushbuffer::PushF(NV097_SET_BACK_MATERIAL_ALPHA, 1.f);

    Pushbuffer::Push(NV097_SET_LIGHT_TWO_SIDE_ENABLE, false);
    Pushbuffer::Push(NV097_SET_FRONT_POLYGON_MODE, NV097_SET_FRONT_POLYGON_MODE_V_FILL);
    Pushbuffer::Push(NV097_SET_BACK_POLYGON_MODE, NV097_SET_FRONT_POLYGON_MODE_V_FILL);

    Pushbuffer::Push(NV097_SET_POINT_PARAMS_ENABLE, false);
    Pushbuffer::Push(NV097_SET_POINT_SMOOTH_ENABLE, false);
    Pushbuffer::Push(NV097_SET_POINT_SIZE, 8);

    Pushbuffer::Push(NV097_SET_DOT_RGBMAPPING, 0);

    Pushbuffer::Push(NV097_SET_SHADE_MODEL, NV097_SET_SHADE_MODEL_SMOOTH);
    Pushbuffer::Push(NV097_SET_FLAT_SHADE_OP, NV097_SET_FLAT_SHADE_OP_VERTEX_LAST);
    Pushbuffer::End();
  }

  host_.SetWindowClipExclusive(false);
  // Note, setting the first clip region will cause the hardware to also set all subsequent regions.
  host_.SetWindowClip(host_.GetFramebufferWidth(), host_.GetFramebufferHeight());

  host_.SetBlend();

  host_.ClearInputColorCombiners();
  host_.ClearInputAlphaCombiners();
  host_.ClearOutputColorCombiners();
  host_.ClearOutputAlphaCombiners();

  host_.SetCombinerControl(1);
  host_.SetInputColorCombiner(0, TestHost::SRC_DIFFUSE, false, TestHost::MAP_UNSIGNED_IDENTITY, TestHost::SRC_ZERO,
                              false, TestHost::MAP_UNSIGNED_INVERT);
  host_.SetInputAlphaCombiner(0, TestHost::SRC_DIFFUSE, true, TestHost::MAP_UNSIGNED_IDENTITY, TestHost::SRC_ZERO,
                              false, TestHost::MAP_UNSIGNED_INVERT);

  host_.SetOutputColorCombiner(0, TestHost::DST_DISCARD, TestHost::DST_DISCARD, TestHost::DST_R0);
  host_.SetOutputAlphaCombiner(0, TestHost::DST_DISCARD, TestHost::DST_DISCARD, TestHost::DST_R0);

  host_.SetFinalCombiner0(TestHost::SRC_ZERO, false, false, TestHost::SRC_ZERO, false, false, TestHost::SRC_ZERO, false,
                          false, TestHost::SRC_R0);
  host_.SetFinalCombiner1(TestHost::SRC_ZERO, false, false, TestHost::SRC_ZERO, false, false, TestHost::SRC_R0, true,
                          false, /*specular_add_invert_r0*/ false, /* specular_add_invert_v1*/ false,
                          /* specular_clamp */ true);

  while (pb_busy()) {
    /* Wait for completion... */
  }

  matrix4_t identity_matrix;
  MatrixSetIdentity(identity_matrix);
  for (auto i = 0; i < 4; ++i) {
    auto& stage = host_.GetTextureStage(i);
    stage.SetUWrap(TextureStage::WRAP_CLAMP_TO_EDGE, false);
    stage.SetVWrap(TextureStage::WRAP_CLAMP_TO_EDGE, false);
    stage.SetPWrap(TextureStage::WRAP_CLAMP_TO_EDGE, false);
    stage.SetQWrap(false);

    stage.SetEnabled(false);
    stage.SetCubemapEnable(false);
    stage.SetFilter();
    stage.SetAlphaKillEnable(false);
    stage.SetColorKeyMode(TextureStage::CKM_DISABLE);
    stage.SetLODClamp(0, 4095);

    stage.SetTextureMatrixEnable(false);
    stage.SetTextureMatrix(identity_matrix);

    stage.SetTexgenS(TextureStage::TG_DISABLE);
    stage.SetTexgenT(TextureStage::TG_DISABLE);
    stage.SetTexgenR(TextureStage::TG_DISABLE);
    stage.SetTexgenQ(TextureStage::TG_DISABLE);
  }

  // TODO: Set up with TextureStage instances in host_.
  {
    Pushbuffer::Begin();
    uint32_t address = NV097_SET_TEXTURE_ADDRESS;
    uint32_t control = NV097_SET_TEXTURE_CONTROL0;
    uint32_t filter = NV097_SET_TEXTURE_FILTER;
    Pushbuffer::Push(address, 0x10101);
    Pushbuffer::Push(control, 0x3ffc0);
    Pushbuffer::Push(filter, 0x1012000);

    address += 0x40;
    control += 0x40;
    filter += 0x40;
    Pushbuffer::Push(address, 0x10101);
    Pushbuffer::Push(control, 0x3ffc0);
    Pushbuffer::Push(filter, 0x1012000);

    address += 0x40;
    control += 0x40;
    filter += 0x40;
    Pushbuffer::Push(address, 0x10101);
    Pushbuffer::Push(control, 0x3ffc0);
    Pushbuffer::Push(filter, 0x1012000);

    address += 0x40;
    control += 0x40;
    filter += 0x40;
    Pushbuffer::Push(address, 0x10101);
    Pushbuffer::Push(control, 0x3ffc0);
    Pushbuffer::Push(filter, 0x1012000);

    Pushbuffer::Push(NV097_SET_FOG_ENABLE, false);
    Pushbuffer::PushF(NV097_SET_FOG_PLANE, 0.f, 0.f, 1.f, 0.f);
    Pushbuffer::Push(NV097_SET_FOG_GEN_MODE, NV097_SET_FOG_GEN_MODE_V_PLANAR);
    Pushbuffer::Push(NV097_SET_FOG_MODE, NV097_SET_FOG_MODE_V_LINEAR);
    Pushbuffer::Push(NV097_SET_FOG_COLOR, 0xFFFFFFFF);

    Pushbuffer::Push(NV097_SET_TEXTURE_MATRIX_ENABLE, 0, 0, 0, 0);

    Pushbuffer::Push(NV097_SET_FRONT_FACE, NV097_SET_FRONT_FACE_V_CW);
    Pushbuffer::Push(NV097_SET_CULL_FACE, NV097_SET_CULL_FACE_V_BACK);
    Pushbuffer::Push(NV097_SET_CULL_FACE_ENABLE, true);

    Pushbuffer::Push(NV097_SET_COLOR_MASK,
                     NV097_SET_COLOR_MASK_BLUE_WRITE_ENABLE | NV097_SET_COLOR_MASK_GREEN_WRITE_ENABLE |
                         NV097_SET_COLOR_MASK_RED_WRITE_ENABLE | NV097_SET_COLOR_MASK_ALPHA_WRITE_ENABLE);

    Pushbuffer::Push(NV097_SET_DEPTH_TEST_ENABLE, false);
    Pushbuffer::Push(NV097_SET_DEPTH_MASK, true);
    Pushbuffer::Push(NV097_SET_DEPTH_FUNC, NV097_SET_DEPTH_FUNC_V_LESS);
    Pushbuffer::Push(NV097_SET_STENCIL_TEST_ENABLE, false);
    Pushbuffer::Push(NV097_SET_STENCIL_MASK, 0xFF);
    // If the stencil comparison fails, leave the value in the stencil buffer alone.
    Pushbuffer::Push(NV097_SET_STENCIL_OP_FAIL, NV097_SET_STENCIL_OP_V_KEEP);
    // If the stencil comparison passes but the depth comparison fails, leave the stencil buffer alone.
    Pushbuffer::Push(NV097_SET_STENCIL_OP_ZFAIL, NV097_SET_STENCIL_OP_V_KEEP);
    // If the stencil comparison passes and the depth comparison passes, leave the stencil buffer alone.
    Pushbuffer::Push(NV097_SET_STENCIL_OP_ZPASS, NV097_SET_STENCIL_OP_V_KEEP);
    Pushbuffer::Push(NV097_SET_STENCIL_FUNC_REF, 0x7F);

    Pushbuffer::Push(NV097_SET_NORMALIZATION_ENABLE, false);

    Pushbuffer::PushF(NV097_SET_WEIGHT4F, 0.f, 0.f, 0.f, 0.f);
    Pushbuffer::PushF(NV097_SET_NORMAL3F, 0.f, 0.f, 0.f);
    Pushbuffer::Push(NV097_SET_DIFFUSE_COLOR4I, 0x00000000);
    Pushbuffer::Push(NV097_SET_SPECULAR_COLOR4I, 0x00000000);
    Pushbuffer::PushF(NV097_SET_TEXCOORD0_4F, 0.f, 0.f, 0.f, 0.f);
    Pushbuffer::PushF(NV097_SET_TEXCOORD1_4F, 0.f, 0.f, 0.f, 0.f);
    Pushbuffer::PushF(NV097_SET_TEXCOORD2_4F, 0.f, 0.f, 0.f, 0.f);
    Pushbuffer::PushF(NV097_SET_TEXCOORD3_4F, 0.f, 0.f, 0.f, 0.f);
    Pushbuffer::Push(NV097_SET_VERTEX_DATA4UB + (4 * NV2A_VERTEX_ATTR_BACK_DIFFUSE), 0xFFFFFFFF);
    Pushbuffer::Push(NV097_SET_VERTEX_DATA4UB + (4 * NV2A_VERTEX_ATTR_BACK_SPECULAR), 0);

    // Pow 16
    const float specular_params[]{-0.803673, -2.7813, 2.97762, -0.64766, -2.36199, 2.71433};
    for (uint32_t i = 0, offset = 0; i < 6; ++i, offset += 4) {
      Pushbuffer::PushF(NV097_SET_SPECULAR_PARAMS + offset, specular_params[i]);
      Pushbuffer::PushF(NV097_SET_SPECULAR_PARAMS_BACK + offset, 0);
    }
    Pushbuffer::End();
  }

  host_.SetDefaultViewportAndFixedFunctionMatrices();
  host_.SetDepthBufferFloatMode(false);

  host_.SetVertexShaderProgram(nullptr);
  SetDefaultTextureFormat();
  host_.SetTextureStageEnabled(0, false);
  host_.SetTextureStageEnabled(1, false);
  host_.SetTextureStageEnabled(2, false);
  host_.SetTextureStageEnabled(3, false);
  host_.SetShaderStageProgram(TestHost::STAGE_NONE);
  host_.SetShaderStageInput(0, 0);

  host_.ClearAllVertexAttributeStrideOverrides();
}

TestHost::ProfileResults TestSuite::Profile(const std::string& test_name, uint32_t num_iterations,
                                            const std::function<void(void)>& body) const {
  uint32_t measurement_iterations_multiplier = 1;
  if (host_.GetSaveResults()) {
    measurement_iterations_multiplier = host_.GetMeasurementIterationsMultiplier();
    ASSERT(measurement_iterations_multiplier > 0);
    ASSERT(num_iterations <= UINT32_MAX / measurement_iterations_multiplier);
  } else {
    num_iterations = 1;
  }
  const uint32_t sample_count = num_iterations;
  const uint32_t total_work_iterations = sample_count * measurement_iterations_multiplier;

  TestHost::ProfileResults ret{
      .iterations = total_work_iterations,
      .sample_count = sample_count,
      .measurement_iterations_multiplier = measurement_iterations_multiplier,
      .warmup_iterations = 0,
      .total_time_microseconds = 0xFFFFFFFF,
      .average_time_microseconds = 0xFFFFFFFF,
      .maximum_time_microseconds = 0,
      .minimum_time_microseconds = 0xFFFFFFFF,
      .completion_wait_microseconds = 0,
  };

  auto run_times = std::make_unique<uint32_t[]>(sample_count);

  const auto warmup_iterations = host_.GetSaveResults() ? host_.GetWarmupIterations() : 0;
  PrintMsg("TEST_BEGIN %s::%s\n", suite_name_.c_str(), test_name.c_str());
  if (warmup_iterations) {
    PrintMsg("WARMUP_BEGIN %s::%s iterations=%lu\n", suite_name_.c_str(), test_name.c_str(), warmup_iterations);
    for (uint32_t i = 0; i < warmup_iterations; ++i) {
      body();
      host_.WaitForGpu();
      EmitXemuPerfMarker(kXemuPerfMarkerGpuComplete);
    }
    PrintMsg("WARMUP_END %s::%s\n", suite_name_.c_str(), test_name.c_str());
  }

  // Never let warmup work leak into the first measured sample.
  host_.WaitForGpu();
  EmitXemuPerfMarker(kXemuPerfMarkerGpuComplete);
  EmitXemuPerfMarker(kXemuPerfMarkerMeasureBegin);
  PrintMsg("MEASURE_BEGIN %s::%s iterations=%lu samples=%lu multiplier=%lu mode=%s\n", suite_name_.c_str(),
           test_name.c_str(), total_work_iterations, sample_count, measurement_iterations_multiplier,
           host_.GetGpuCompletionModeName());

  LARGE_INTEGER profile_start;
  LARGE_INTEGER iteration_start;

  QueryPerformanceCounter(&profile_start);

  for (uint32_t sample = 0; sample < sample_count; ++sample) {
    QueryPerformanceCounter(&iteration_start);
    for (uint32_t repetition = 0; repetition < measurement_iterations_multiplier; ++repetition) {
      body();
      if (host_.GetGpuCompletionMode() == TestHost::GpuCompletionMode::PER_ITERATION) {
        LARGE_INTEGER wait_start;
        QueryPerformanceCounter(&wait_start);
        host_.WaitForGpu();
        EmitXemuPerfMarker(kXemuPerfMarkerGpuComplete);
        ret.completion_wait_microseconds += host_.GetMicrosecondsSince(wait_start);
      }
    }
    run_times[sample] = host_.GetMicrosecondsSince(iteration_start);
  }

  if (host_.GetGpuCompletionMode() == TestHost::GpuCompletionMode::BATCH_COMPLETE) {
    LARGE_INTEGER wait_start;
    QueryPerformanceCounter(&wait_start);
    host_.WaitForGpu();
    EmitXemuPerfMarker(kXemuPerfMarkerGpuComplete);
    ret.completion_wait_microseconds = host_.GetMicrosecondsSince(wait_start);
  }

  auto duration = host_.GetMicrosecondsSince(profile_start);
  EmitXemuPerfMarker(kXemuPerfMarkerMeasureEnd);
  pb_show_front_screen();

  PrintMsg("MEASURE_END %s::%s duration_us=%lu completion_wait_us=%lu\n", suite_name_.c_str(), test_name.c_str(),
           duration, ret.completion_wait_microseconds);

  if (!host_.GetSaveResults()) {
    return ret;
  }

  ret.warmup_iterations = warmup_iterations;
  ret.total_time_microseconds = 0;
  for (uint32_t sample = 0; sample < sample_count; ++sample) {
    const uint32_t aggregate_time = run_times[sample];
    const uint32_t normalized_time = aggregate_time / measurement_iterations_multiplier;
    ret.raw_results.emplace_back(normalized_time);
    ret.total_time_microseconds += aggregate_time;
    if (normalized_time < ret.minimum_time_microseconds) {
      ret.minimum_time_microseconds = normalized_time;
    }
    if (normalized_time > ret.maximum_time_microseconds) {
      ret.maximum_time_microseconds = normalized_time;
    }
  }
  ret.average_time_microseconds = ret.total_time_microseconds / total_work_iterations;
  const auto statistics = CalculateResultStatistics(ret.raw_results);
  ret.median_time_microseconds = statistics.median_us;
  ret.p95_time_microseconds = statistics.p95_us;
  ret.mad_time_microseconds = statistics.mad_us;

  return ret;
}
