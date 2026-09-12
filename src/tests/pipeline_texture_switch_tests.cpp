#include "pipeline_texture_switch_tests.h"

#include <pbkit/nv_regs.h>
#include <pbkit/pbkit.h>

#include <array>
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
static constexpr char kClearTextureNormalName[] =
    "pipeline.clear-texture-normal";
static constexpr char kSamplerOnlyIdentityName[] =
    "pipeline.sampler-only-identity";
static constexpr char kPaletteOnlyUpdateName[] = "pipeline.palette-only-update";
static constexpr char kSharedPageOverlapName[] =
    "pipeline.shared-page-overlap";
static constexpr char kTextureDmaRemapName[] = "pipeline.texture-dma-remap";
static constexpr char kPaletteDmaRemapName[] = "pipeline.palette-dma-remap";

static constexpr uint32_t kSeed = 0x50545357;  // "PTSW"
static constexpr uint32_t kFnvOffsetBasis = 2166136261U;
static constexpr uint32_t kFnvPrime = 16777619U;
static constexpr uint32_t kTextureWidth = 64;
static constexpr uint32_t kTextureHeight = 64;
static constexpr uint32_t kTexturePixels = kTextureWidth * kTextureHeight;
static constexpr uint32_t kLinearTextureBytes =
    kTexturePixels * sizeof(uint32_t);
static constexpr uint32_t kPaletteEntries = 256;
static constexpr uint32_t kPaletteIndexWords = kTexturePixels / sizeof(uint32_t);
static constexpr uint32_t kSharedBindingOffset = 256;
static constexpr uint32_t kSharedBindingOffsetWords =
    kSharedBindingOffset / sizeof(uint32_t);
static constexpr uint32_t kSharedRegionWords =
    kTexturePixels + kSharedBindingOffsetWords;
static constexpr uint32_t kSamplerMipLevels = 5;
static constexpr uint32_t kSamplerTextureWords = 5456;
static constexpr uint32_t kProfileSamples = 8;
static constexpr uint32_t kOperationsPerIteration = 512;
static constexpr uint32_t kTextureStageCount = 1;
static constexpr uint32_t kSamplerQuadHalfExtent = 4;
static constexpr uint32_t kSamplerUvMin = 0;
static constexpr uint32_t kSamplerUvMax = 24;
static constexpr uint32_t kHeartbeatInterval = 32;
static constexpr uint32_t kClearBoundariesPerIteration = 128;
static constexpr uint32_t kClearTextureChangesPerBoundary = 2;
static constexpr uint32_t kClearNormalDrawsPerBoundary = 2;
static constexpr uint32_t kClearOperationsPerIteration =
    kClearBoundariesPerIteration *
    (1 + kClearTextureChangesPerBoundary + kClearNormalDrawsPerBoundary);

static constexpr uint32_t kTextureAColor = 0xFFFF0000;
static constexpr uint32_t kTextureBColor = 0xFF0000FF;
static constexpr uint32_t kDiffuseColor = 0xFF00FF00;
static constexpr uint32_t kTextureDmaRed = 23;
static constexpr uint32_t kTextureDmaBlue = 24;
static constexpr uint32_t kTextureDmaGreen = 25;
static constexpr uint32_t kPaletteDmaRed = 26;
static constexpr uint32_t kPaletteDmaBlue = 27;
static constexpr uint32_t kDefaultDmaA = 3;
static constexpr uint32_t kDefaultDmaB = 11;
static constexpr uint32_t kTextureStageStride = 64;
// Keep the DMA sources out of the host texture/render-target pool. They still
// need GPU-addressable backing; ordinary XBE globals do not provide that.
static constexpr uint32_t kDmaTextureStorageBytes =
    3 * kLinearTextureBytes;
// PBKit frame/depth surfaces live toward the top of a 64 MiB Xbox address
// space. Keep this allocation in a separate physical window so a retained
// SurfaceBinding cannot mask the clean-stage DMA remap fast path under test.
static constexpr uint32_t kDmaTextureLowAddress = 0x01000000;
static constexpr uint32_t kDmaTextureHighAddress = 0x02FFFFFF;
static constexpr uint32_t kSamplerMipColors[] = {
    0xFFFF0000, 0xFFFFFF00, 0xFF00FF00, 0xFF00FFFF, 0xFF0000FF};
static constexpr uint32_t kBackgroundColor = 0xFF101820;
static constexpr uint32_t kBoundaryClearColor = 0xFF202830;

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
static constexpr uint32_t kClearTextureNormalInputKat = 0x1A404C43;
static constexpr uint32_t kClearTextureNormalPixelKat = 0x50C0069D;
static constexpr uint32_t kSamplerBackingKat = 0xCDD5D7A5;
static constexpr uint32_t kSamplerInputKat = 0x281BCD52;
// Regression oracle captured identically on upstream d73326b and the candidate.
static constexpr uint32_t kSamplerOnlyPixelKat = 0xBB0EC8ED;
static constexpr uint32_t kPaletteIndexKat = 0x76EFDDC5;
static constexpr uint32_t kPaletteInitialKat = 0xFEBA67C5;
static constexpr uint32_t kPaletteChangedKat = 0xD2A80FED;
static constexpr uint32_t kPaletteOnlyInputKat = 0xE9635B33;
static constexpr uint32_t kSharedInitialKat = 0x2D306945;
static constexpr uint32_t kSharedChangedKat = 0xE941E945;
static constexpr uint32_t kSharedBindingBKat = 0xB721F1C5;
static constexpr uint32_t kSharedPageInputKat = 0x5F016545;
static constexpr uint32_t kMutationPixelKat = 0x0ABCCA3D;

static constexpr uint32_t kTextureSwitchFinalColor = 0xFF18405A;
static constexpr uint32_t kShaderNegativeFinalColor = 0xFF4A2038;
static constexpr uint64_t kTextureSwitchFinalFrameHash =
    0x8AE05D31FB00C325ULL;
static constexpr uint64_t kShaderNegativeFinalFrameHash =
    0xF110C8BD6338C325ULL;
static constexpr uint32_t kClearTextureNormalFinalColor = 0xFF305060;
static constexpr uint64_t kClearTextureNormalFinalFrameHash =
    0x22BA4F1405CDA325ULL;
static constexpr uint32_t kSamplerOnlyFinalColor = 0xFF405020;
static constexpr uint64_t kSamplerOnlyFinalFrameHash =
    0x0B8438C8404DA325ULL;
static constexpr uint32_t kPaletteOnlyFinalColor = 0xFF604020;
static constexpr uint64_t kPaletteOnlyFinalFrameHash =
    0x467AAB2F95CDA325ULL;
static constexpr uint32_t kSharedPageFinalColor = 0xFF206040;
static constexpr uint64_t kSharedPageFinalFrameHash =
    0x83BB59A8648DA325ULL;

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

uint32_t ExpectedFinalState(uint32_t phase, uint32_t input_kat,
                            uint32_t expected_pixel_kat,
                            uint32_t measured_iterations) {
  uint32_t state = kSeed ^ phase;
  for (uint32_t iteration = 0; iteration < measured_iterations; ++iteration) {
    state = FoldKnownOutput(state, input_kat);
    state = FoldKnownOutput(state, phase);
    state = FoldKnownOutput(state, kOperationsPerIteration);
    state = FoldKnownOutput(state, expected_pixel_kat);
  }
  return state;
}

uint32_t ExpectedClearTextureNormalFinalState(uint32_t measured_iterations) {
  static constexpr uint32_t kPhase = 0x1503;
  uint32_t state = kSeed ^ kPhase;
  for (uint32_t iteration = 0; iteration < measured_iterations; ++iteration) {
    state = FoldKnownOutput(state, kClearTextureNormalInputKat);
    state = FoldKnownOutput(state, kPhase);
    state = FoldKnownOutput(state, kClearBoundariesPerIteration);
    state = FoldKnownOutput(state, kClearTextureNormalPixelKat);
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

void PushDmaBinding(uint32_t method, uint32_t handle) {
  Pushbuffer::Begin();
  Pushbuffer::Push(method, handle);
  Pushbuffer::End();
}

void DrawDmaTile(TestHost &host, const Quad &quad, bool stage_one,
                 float texture_extent) {
  host.SetFinalCombiner0Just(stage_one ? TestHost::SRC_TEX1
                                        : TestHost::SRC_TEX0);
  host.Begin(TestHost::PRIMITIVE_QUADS);
  const float xy[][2] = {{quad.left, quad.top}, {quad.right, quad.top},
                         {quad.right, quad.bottom}, {quad.left, quad.bottom}};
  const float uv[][2] = {{0.f, 0.f}, {texture_extent, 0.f},
                         {texture_extent, texture_extent},
                         {0.f, texture_extent}};
  for (uint32_t vertex = 0; vertex < 4; ++vertex) {
    host.SetTexCoord0(uv[vertex][0], uv[vertex][1]);
    host.SetTexCoord1(uv[vertex][0], uv[vertex][1]);
    host.SetVertex(xy[vertex][0], xy[vertex][1], 1.f);
  }
  host.End();
}

uint32_t ReadTileCenter(uint32_t tile) {
  const Quad &quad = kQuads[tile];
  const uint32_t x = static_cast<uint32_t>((quad.left + quad.right) * 0.5f);
  const uint32_t y = static_cast<uint32_t>((quad.top + quad.bottom) * 0.5f);
  const auto *base = reinterpret_cast<volatile const uint8_t *>(pb_back_buffer());
  const auto *row = reinterpret_cast<volatile const uint32_t *>(
      base + static_cast<size_t>(y) * pb_back_buffer_pitch());
  return row[x];
}

}  // namespace

PipelineTextureSwitchTests::PipelineTextureSwitchTests(TestHost &host,
                                                       std::string output_dir,
                                                       const Config &config)
    : TestSuite(host, std::move(output_dir), "PipelineTextureSwitch", config) {
  static constexpr Recipe kTextureSwitch{
      kTextureSwitchName, 0x1501, false, false, kTextureSwitchPixelKat,
      kTextureSwitchFinalColor, kTextureSwitchFinalFrameHash};
  static constexpr Recipe kShaderNegativeControl{
      kShaderNegativeControlName, 0x1502, true, false, kShaderNegativePixelKat,
      kShaderNegativeFinalColor, kShaderNegativeFinalFrameHash};
  static constexpr Recipe kSamplerOnlyIdentity{
      kSamplerOnlyIdentityName, 0x1504, false, true, kSamplerOnlyPixelKat,
      kSamplerOnlyFinalColor, kSamplerOnlyFinalFrameHash};

  tests_[kTextureSwitchName] = [this]() { Run(kTextureSwitch); };
  tests_[kShaderNegativeControlName] =
      [this]() { Run(kShaderNegativeControl); };
  tests_[kClearTextureNormalName] = [this]() { RunClearTextureNormal(); };
  tests_[kSamplerOnlyIdentityName] =
      [this]() { Run(kSamplerOnlyIdentity); };
  tests_[kPaletteOnlyUpdateName] = [this]() { RunPaletteOnlyUpdate(); };
  tests_[kSharedPageOverlapName] = [this]() { RunSharedPageOverlap(); };
  tests_[kTextureDmaRemapName] = [this]() { RunTextureDmaRemap(); };
  tests_[kPaletteDmaRemapName] = [this]() { RunPaletteDmaRemap(); };
}

void PipelineTextureSwitchTests::Initialize() {
  TestSuite::Initialize();

  ResetCanonicalTextureBacking();

  dma_texture_storage_ = static_cast<uint32_t *>(MmAllocateContiguousMemoryEx(
      kDmaTextureStorageBytes, kDmaTextureLowAddress,
      kDmaTextureHighAddress, 0,
      PAGE_WRITECOMBINE | PAGE_READWRITE));
  ASSERT(dma_texture_storage_ != nullptr);
  if (!dma_texture_storage_) {
    return;
  }
  auto *red = dma_texture_storage_;
  auto *blue = red + kTexturePixels;
  auto *green = blue + kTexturePixels;

  pb_create_dma_ctx(kTextureDmaRed, DMA_CLASS_3,
                    reinterpret_cast<DWORD>(red),
                    kLinearTextureBytes - 1, &texture_dma_red_);
  pb_create_dma_ctx(kTextureDmaBlue, DMA_CLASS_3,
                    reinterpret_cast<DWORD>(blue),
                    kLinearTextureBytes - 1, &texture_dma_blue_);
  pb_create_dma_ctx(kTextureDmaGreen, DMA_CLASS_3,
                    reinterpret_cast<DWORD>(green),
                    kLinearTextureBytes - 1, &texture_dma_green_);
  pb_create_dma_ctx(kPaletteDmaRed, DMA_CLASS_3,
                    reinterpret_cast<DWORD>(host_.GetPaletteMemoryForStage(0)),
                    kPaletteEntries * sizeof(uint32_t) - 1, &palette_dma_red_);
  pb_create_dma_ctx(kPaletteDmaBlue, DMA_CLASS_3,
                    reinterpret_cast<DWORD>(host_.GetTextureMemoryForStage(2)),
                    kPaletteEntries * sizeof(uint32_t) - 1, &palette_dma_blue_);
  pb_bind_channel(&texture_dma_red_);
  pb_bind_channel(&texture_dma_blue_);
  pb_bind_channel(&texture_dma_green_);
  pb_bind_channel(&palette_dma_red_);
  pb_bind_channel(&palette_dma_blue_);

  auto *texture_a = reinterpret_cast<uint32_t *>(
      host_.GetTextureMemoryForStage(0));
  auto *texture_b = reinterpret_cast<uint32_t *>(
      host_.GetTextureMemoryForStage(1));

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
  sampler_backing_kat_ = HashWords(texture_a, kSamplerTextureWords);
  sampler_input_kat_ = kFnvOffsetBasis;
  const uint32_t sampler_input_words[]{
      kSeed, kTextureWidth, kTextureHeight, kSamplerMipLevels,
      kSamplerMipColors[0], kSamplerMipColors[1], kSamplerMipColors[2],
      kSamplerMipColors[3], kSamplerMipColors[4], sampler_backing_kat_,
      kOperationsPerIteration, kSamplerQuadHalfExtent, kSamplerUvMin,
      kSamplerUvMax};
  for (uint32_t value : sampler_input_words) {
    sampler_input_kat_ = Fnv1aAddWord(sampler_input_kat_, value);
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
  AssertXemuPerfEqual(kSamplerBackingKat, sampler_backing_kat_,
                      XemuPerfAssertion::PIPELINE_TEXTURE_INPUT,
                      "sampler_identity_backing_kat == expected", __FILE__,
                      __LINE__);
  AssertXemuPerfEqual(kSamplerInputKat, sampler_input_kat_,
                      XemuPerfAssertion::PIPELINE_TEXTURE_INPUT,
                      "sampler_identity_input_kat == expected", __FILE__,
                      __LINE__);
}

void PipelineTextureSwitchTests::Deinitialize() {
  host_.WaitForGpu();
  if (dma_texture_storage_) {
    MmFreeContiguousMemory(dma_texture_storage_);
    dma_texture_storage_ = nullptr;
  }
  TestSuite::Deinitialize();
}

void PipelineTextureSwitchTests::SetupTest() {
  // All leaves share TestHost's texture-stage allocations. Rebuild the
  // canonical source bytes before each leaf so a mutation workload cannot
  // make a later leaf depend on suite execution order.
  ResetCanonicalTextureBacking();
}

void PipelineTextureSwitchTests::ResetCanonicalTextureBacking() const {
  auto *texture_a = reinterpret_cast<uint32_t *>(
      host_.GetTextureMemoryForStage(0));
  auto *texture_b = reinterpret_cast<uint32_t *>(
      host_.GetTextureMemoryForStage(1));
  for (uint32_t pixel = 0; pixel < kTexturePixels; ++pixel) {
    texture_a[pixel] = kTextureAColor;
    texture_b[pixel] = kTextureBColor;
  }

  uint32_t mip_offset = 0;
  uint32_t mip_dimension = kTextureWidth;
  for (uint32_t level = 0; level < kSamplerMipLevels; ++level) {
    const uint32_t level_words = mip_dimension * mip_dimension;
    for (uint32_t word = 0; word < level_words; ++word) {
      texture_a[mip_offset + word] = kSamplerMipColors[level];
    }
    mip_offset += level_words;
    mip_dimension >>= 1;
  }
}

void PipelineTextureSwitchTests::Run(const Recipe &recipe) {
  const uint32_t measured_iterations =
      host_.GetSaveResults()
          ? kProfileSamples * host_.GetMeasurementIterationsMultiplier()
          : 1;
  const uint32_t warmup_iterations =
      host_.GetSaveResults() ? host_.GetWarmupIterations() : 0;
  const uint32_t recipe_input_kat =
      recipe.sampler_only_identity ? sampler_input_kat_ : input_kat_;
  const uint32_t expected_input_kat =
      recipe.sampler_only_identity ? kSamplerInputKat : kInputKat;
  const uint32_t expected_final =
      ExpectedFinalState(recipe.phase, recipe_input_kat, recipe.expected_pixel_kat,
                         measured_iterations);
  uint32_t actual_final = kSeed ^ recipe.phase;
  uint32_t invocation = 0;

  SetXemuPerfEventContext(recipe.phase, expected_final);
  EmitXemuPerfEvent(XemuPerfEventType::CONTEXT, 0,
                    host_.GetMeasurementIterationsMultiplier(),
                    warmup_iterations);

  AssertXemuPerfEqual(recipe.sampler_only_identity ? kSamplerBackingKat
                                                   : kTextureABackingKat,
                      recipe.sampler_only_identity ? sampler_backing_kat_
                                                   : backing_a_kat_,
                      XemuPerfAssertion::PIPELINE_TEXTURE_INPUT,
                      "pipeline_texture_input_a == expected", __FILE__,
                      __LINE__);
  AssertXemuPerfEqual(kTextureBBackingKat, backing_b_kat_,
                      XemuPerfAssertion::PIPELINE_TEXTURE_INPUT,
                      "pipeline_texture_input_b == expected", __FILE__,
                      __LINE__);
  AssertXemuPerfEqual(expected_input_kat, recipe_input_kat,
                      XemuPerfAssertion::PIPELINE_TEXTURE_INPUT,
                      "pipeline_texture_input == expected", __FILE__,
                      __LINE__);

  if (recipe.sampler_only_identity) {
    ConfigureSamplerIdentityPipeline();
  } else {
    ConfigureTexturePipeline();
  }
  host_.PrepareDraw(kBackgroundColor);

  auto results = Profile(recipe.test_name, kProfileSamples, [&]() {
    RunIteration(recipe);
    if (invocation >= warmup_iterations) {
      actual_final = FoldKnownOutput(actual_final, recipe_input_kat);
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
  const uint32_t actual_backing_a = HashWords(
      texture_a, recipe.sampler_only_identity ? kSamplerTextureWords
                                              : kTexturePixels);
  const uint32_t actual_backing_b = HashWords(texture_b, kTexturePixels);
  AssertXemuPerfEqual(recipe.sampler_only_identity ? kSamplerBackingKat
                                                   : kTextureABackingKat,
                      actual_backing_a,
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
      (recipe.shader_negative_control || recipe.sampler_only_identity)
          ? 0
          : total_operations;
  const uint64_t sampler_changes =
      recipe.sampler_only_identity ? total_operations : texture_switches;
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
      static_cast<unsigned long long>(sampler_changes),
      static_cast<unsigned long long>(sampler_changes),
      static_cast<unsigned long long>(shader_state_writes), recipe_input_kat,
      actual_backing_a, actual_backing_b, actual_pixel_kat, actual_final,
      static_cast<unsigned long long>(actual_frame_hash));

  std::ostringstream metadata;
  metadata << "{\"schema_version\":1,";
  metadata << "\"kind\":\"pipeline_texture_switch_capsule\",";
  metadata << "\"test_id\":\"" << recipe.test_name << "\",";
  metadata << "\"oracle_provenance\":\"REGRESSION_ONLY\",";
  metadata << "\"seed\":\"50545357\",";
  metadata << "\"phase\":\""
           << (recipe.shader_negative_control
                   ? "shader_negative_control"
                   : (recipe.sampler_only_identity ? "sampler_only_identity"
                                                   : "texture_switch"))
           << "\",";
  metadata << "\"phase_count\":4,";
  metadata << "\"texture_stage_count\":" << kTextureStageCount << ",";
  metadata << "\"operations_per_iteration\":"
           << kOperationsPerIteration << ",";
  metadata << "\"total_operations\":" << total_operations << ",";
  metadata << "\"draws\":" << total_operations << ",";
  metadata << "\"texture_switches\":" << texture_switches << ",";
  metadata << "\"sampler_changes\":" << sampler_changes << ",";
  metadata << "\"address_changes\":" << sampler_changes << ",";
  metadata << "\"shader_state_writes\":" << shader_state_writes << ",";
  metadata << "\"input_kat\":{\"expected\":" << expected_input_kat
           << ",\"actual\":" << recipe_input_kat << "},";
  metadata << "\"backing_kat\":{\"a_expected\":"
           << (recipe.sampler_only_identity ? kSamplerBackingKat
                                            : kTextureABackingKat)
           << ",\"a_actual\":" << actual_backing_a
           << ",\"b_expected\":" << kTextureBBackingKat
           << ",\"b_actual\":" << actual_backing_b << "},";
  metadata << "\"rendered_pixel_kat\":{\"expected\":"
           << recipe.expected_pixel_kat << ",\"actual\":"
           << actual_pixel_kat << "},";
  metadata << "\"expected_final_state\":" << expected_final << ",";
  metadata << "\"actual_final_state\":" << actual_final << ",";
  metadata << "\"terminal_fence\":\"F2 after F1\",";
  if (recipe.sampler_only_identity) {
    metadata << "\"image_identity_changes\":0,";
    metadata << "\"storage_mip_levels\":" << kSamplerMipLevels << ",";
    metadata << "\"sampler_identity_count\":2,";
    metadata << "\"cold_setup_counter_contract\":{";
    metadata << "\"image_cache_misses\":1,";
    metadata << "\"sampler_cache_misses\":2,";
    metadata << "\"image_uploads\":1,";
    metadata << "\"correlation\":\"TEST_BEGIN through F0\"},";
    metadata << "\"measured_counter_contract\":{";
    metadata << "\"image_cache_misses\":0,";
    metadata << "\"sampler_cache_misses\":0,";
    metadata << "\"sampler_lookups\":" << total_operations << ",";
    metadata << "\"correlation\":\"F0/F1 interval only\"},";
  }
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

void PipelineTextureSwitchTests::RunClearTextureNormal() {
  static constexpr uint32_t kPhase = 0x1503;
  uint32_t clear_texture_normal_input_kat = kFnvOffsetBasis;
  const uint32_t clear_input_words[]{
      kSeed,
      input_kat_,
      kClearBoundariesPerIteration,
      kBoundaryClearColor,
      backing_b_kat_,
      backing_a_kat_,
      kClearNormalDrawsPerBoundary,
  };
  for (uint32_t value : clear_input_words) {
    clear_texture_normal_input_kat =
        Fnv1aAddWord(clear_texture_normal_input_kat, value);
  }
  const uint32_t measured_iterations =
      host_.GetSaveResults()
          ? kProfileSamples * host_.GetMeasurementIterationsMultiplier()
          : 1;
  const uint32_t warmup_iterations =
      host_.GetSaveResults() ? host_.GetWarmupIterations() : 0;
  const uint32_t expected_final =
      ExpectedClearTextureNormalFinalState(measured_iterations);
  uint32_t actual_final = kSeed ^ kPhase;
  uint32_t invocation = 0;

  SetXemuPerfEventContext(kPhase, expected_final);
  EmitXemuPerfEvent(XemuPerfEventType::CONTEXT, 0,
                    host_.GetMeasurementIterationsMultiplier(),
                    warmup_iterations);
  AssertXemuPerfEqual(kTextureABackingKat, backing_a_kat_,
                      XemuPerfAssertion::PIPELINE_TEXTURE_INPUT,
                      "clear_texture_normal_input_a == expected", __FILE__,
                      __LINE__);
  AssertXemuPerfEqual(kTextureBBackingKat, backing_b_kat_,
                      XemuPerfAssertion::PIPELINE_TEXTURE_INPUT,
                      "clear_texture_normal_input_b == expected", __FILE__,
                      __LINE__);
  AssertXemuPerfEqual(kClearTextureNormalInputKat,
                      clear_texture_normal_input_kat,
                      XemuPerfAssertion::PIPELINE_TEXTURE_INPUT,
                      "clear_texture_normal_input == expected", __FILE__,
                      __LINE__);

  ConfigureTexturePipeline();
  host_.PrepareDraw(kBackgroundColor);

  auto results = Profile(kClearTextureNormalName, kProfileSamples, [&]() {
    RunClearTextureNormalIteration();
    if (invocation >= warmup_iterations) {
      actual_final =
          FoldKnownOutput(actual_final, clear_texture_normal_input_kat);
      actual_final = FoldKnownOutput(actual_final, kPhase);
      actual_final =
          FoldKnownOutput(actual_final, kClearBoundariesPerIteration);
      actual_final =
          FoldKnownOutput(actual_final, kClearTextureNormalPixelKat);
    }
    if ((invocation % kHeartbeatInterval) == 0) {
      EmitXemuPerfHeartbeat();
    }
    ++invocation;
  });

  SynchronizeCorrectness(host_);
  auto *texture_a = reinterpret_cast<volatile const uint32_t *>(
      host_.GetTextureMemoryForStage(0));
  auto *texture_b = reinterpret_cast<volatile const uint32_t *>(
      host_.GetTextureMemoryForStage(1));
  const uint32_t actual_backing_a = HashWords(texture_a, kTexturePixels);
  const uint32_t actual_backing_b = HashWords(texture_b, kTexturePixels);
  AssertXemuPerfEqual(kTextureABackingKat, actual_backing_a,
                      XemuPerfAssertion::PIPELINE_TEXTURE_BACKING,
                      "clear_texture_normal_backing_a_unchanged", __FILE__,
                      __LINE__);
  AssertXemuPerfEqual(kTextureBBackingKat, actual_backing_b,
                      XemuPerfAssertion::PIPELINE_TEXTURE_BACKING,
                      "clear_texture_normal_backing_b_unchanged", __FILE__,
                      __LINE__);

  const uint32_t actual_pixel_kat = ValidateClearTextureNormalPixels();
  AssertXemuPerfEqual(kClearTextureNormalPixelKat, actual_pixel_kat,
                      XemuPerfAssertion::PIPELINE_TEXTURE_SURFACE,
                      "clear_texture_normal_pixel_kat == expected", __FILE__,
                      __LINE__);
  AssertXemuPerfEqual(expected_final, actual_final,
                      XemuPerfAssertion::PIPELINE_TEXTURE_FINAL,
                      "clear_texture_normal_final_state == expected", __FILE__,
                      __LINE__);

  host_.SetTextureStageEnabled(0, false);
  host_.SetShaderStageProgram(TestHost::STAGE_NONE);
  host_.SetupTextureStages();
  host_.SetFinalCombiner0Just(TestHost::SRC_DIFFUSE);
  host_.SetFinalCombiner1Just(TestHost::SRC_DIFFUSE, true);
  host_.SetBlend(false);
  host_.PrepareDraw(kClearTextureNormalFinalColor);
  SynchronizeCorrectness(host_);
  const uint64_t actual_frame_hash = HashBackBuffer();
  AssertXemuPerfEqual(
      static_cast<uint32_t>(kClearTextureNormalFinalFrameHash >> 32),
      static_cast<uint32_t>(actual_frame_hash >> 32),
      XemuPerfAssertion::PIPELINE_TEXTURE_FRAMEBUFFER,
      "clear_texture_normal_framebuffer_hash_hi == expected", __FILE__,
      __LINE__);
  AssertXemuPerfEqual(
      static_cast<uint32_t>(kClearTextureNormalFinalFrameHash),
      static_cast<uint32_t>(actual_frame_hash),
      XemuPerfAssertion::PIPELINE_TEXTURE_FRAMEBUFFER,
      "clear_texture_normal_framebuffer_hash_lo == expected", __FILE__,
      __LINE__);

  const uint64_t total_boundaries =
      static_cast<uint64_t>(kClearBoundariesPerIteration) *
      results.iterations;
  const uint64_t total_texture_changes =
      total_boundaries * kClearTextureChangesPerBoundary;
  const uint64_t total_normal_draws =
      total_boundaries * kClearNormalDrawsPerBoundary;
  const uint64_t total_operations =
      static_cast<uint64_t>(kClearOperationsPerIteration) *
      results.iterations;
  PrintMsg(
      "PIPELINE_CLEAR_TEXTURE_WORK PipelineTextureSwitch::%s seed=%08lx "
      "iterations=%lu operations=%llu clear_pipeline_uses=%llu "
      "descriptor_changes=%llu normal_draws=%llu "
      "clear_to_normal=%llu safe_texture_only=%llu vertex_bindings=0 "
      "input=%08lx backing_a=%08lx backing_b=%08lx pixels=%08lx "
      "final=%08lx frame=%016llx\n",
      kClearTextureNormalName, kSeed, results.iterations,
      static_cast<unsigned long long>(total_operations),
      static_cast<unsigned long long>(total_boundaries),
      static_cast<unsigned long long>(total_texture_changes),
      static_cast<unsigned long long>(total_normal_draws),
      static_cast<unsigned long long>(total_boundaries),
      static_cast<unsigned long long>(total_boundaries),
      clear_texture_normal_input_kat, actual_backing_a, actual_backing_b,
      actual_pixel_kat, actual_final,
      static_cast<unsigned long long>(actual_frame_hash));

  std::ostringstream metadata;
  metadata << "{\"schema_version\":1,";
  metadata << "\"kind\":\"pipeline_clear_texture_normal_capsule\",";
  metadata << "\"test_id\":\"" << kClearTextureNormalName << "\",";
  metadata << "\"oracle_provenance\":\"REGRESSION_ONLY\",";
  metadata << "\"seed\":\"50545357\",";
  metadata << "\"phase\":\"clear_texture_normal\",";
  metadata << "\"texture_stage_count\":" << kTextureStageCount << ",";
  metadata << "\"operations_per_iteration\":"
           << kClearOperationsPerIteration << ",";
  metadata << "\"total_operations\":" << total_operations << ",";
  metadata << "\"clear_pipeline_uses\":" << total_boundaries << ",";
  metadata << "\"descriptor_changes\":" << total_texture_changes << ",";
  metadata << "\"normal_draws\":" << total_normal_draws << ",";
  metadata << "\"clear_to_normal_transitions\":" << total_boundaries
           << ",";
  metadata << "\"safe_texture_only_transitions\":" << total_boundaries
           << ",";
  metadata << "\"vertex_binding_mode\":\"inline_immediate\",";
  metadata << "\"expected_vertex_bindings\":0,";
  metadata << "\"expected_pipeline_dirty_clear_binding\":"
           << total_boundaries << ",";
  metadata << "\"expected_pipeline_texture_with_other_dirty\":"
           << total_boundaries << ",";
  metadata << "\"expected_pipeline_texture_only_bypass\":"
           << total_boundaries << ",";
  metadata << "\"counter_contract\":{";
  metadata << "\"PIPELINE_DIRTY_CLEAR_BINDING\":\">0\",";
  metadata << "\"clear_boundary_counts_as_TEXTURE_ONLY_BYPASS\":false,";
  metadata << "\"PIPELINE_TEXTURE_ONLY_BYPASS\":\">0 after normal bind\"},";
  metadata << "\"input_kat\":{\"expected\":"
           << kClearTextureNormalInputKat << ",\"actual\":"
           << clear_texture_normal_input_kat << "},";
  metadata << "\"backing_kat\":{\"a_expected\":"
           << kTextureABackingKat << ",\"a_actual\":" << actual_backing_a
           << ",\"b_expected\":" << kTextureBBackingKat
           << ",\"b_actual\":" << actual_backing_b << "},";
  metadata << "\"rendered_pixel_kat\":{\"expected\":"
           << kClearTextureNormalPixelKat << ",\"actual\":"
           << actual_pixel_kat << "},";
  metadata << "\"expected_final_state\":" << expected_final << ",";
  metadata << "\"actual_final_state\":" << actual_final << ",";
  metadata << "\"terminal_fence\":\"F2 after F1\",";
  char hash_string[17]{};
  snprintf(hash_string, sizeof(hash_string), "%016llx",
           static_cast<unsigned long long>(
               kClearTextureNormalFinalFrameHash));
  metadata << "\"expected_framebuffer_fnv1a64\":\"" << hash_string
           << "\",";
  metadata << "\"framebuffer_contract\":\"FinishDraw framebuffer_fnv1a64\"}";

  EmitXemuPerfEvent(XemuPerfEventType::PASS, 0, expected_final, actual_final);
  host_.FinishDraw(suite_name_, kClearTextureNormalName, results,
                   metadata.str());
  ClearXemuPerfEventContext();
}

void PipelineTextureSwitchTests::RunPaletteOnlyUpdate() {
  static constexpr uint32_t kPhase = 0x1505;
  std::array<uint32_t, kPaletteEntries> initial_palette{};
  initial_palette.fill(kTextureAColor);
  std::array<uint32_t, kPaletteEntries> changed_palette = initial_palette;
  changed_palette[0] = kTextureBColor;

  uint32_t input_kat = kFnvOffsetBasis;
  // The texture is reset to all-zero indices inside every invocation. Use its
  // independently calculated KAT here rather than reading prior suite state.
  const uint32_t canonical_input_words[]{
      kSeed, kTextureWidth, kTextureHeight, kTexturePixels, kPaletteEntries,
      kPaletteIndexKat, kPaletteInitialKat, kPaletteChangedKat,
      kOperationsPerIteration,
  };
  for (uint32_t value : canonical_input_words) {
    input_kat = Fnv1aAddWord(input_kat, value);
  }
  AssertXemuPerfEqual(kPaletteOnlyInputKat, input_kat,
                      XemuPerfAssertion::PIPELINE_TEXTURE_INPUT,
                      "palette_only_input == expected", __FILE__, __LINE__);
  AssertXemuPerfEqual(kPaletteInitialKat,
                      HashWords(initial_palette.data(), initial_palette.size()),
                      XemuPerfAssertion::PIPELINE_TEXTURE_INPUT,
                      "initial_palette_kat == expected", __FILE__, __LINE__);
  AssertXemuPerfEqual(kPaletteChangedKat,
                      HashWords(changed_palette.data(), changed_palette.size()),
                      XemuPerfAssertion::PIPELINE_TEXTURE_INPUT,
                      "changed_palette_kat == expected", __FILE__, __LINE__);

  const uint32_t measured_iterations =
      host_.GetSaveResults() ? host_.GetMeasurementIterationsMultiplier() : 1;
  const uint32_t warmup_iterations =
      host_.GetSaveResults() ? host_.GetWarmupIterations() : 0;
  const uint32_t expected_final =
      ExpectedFinalState(kPhase, input_kat, kMutationPixelKat,
                         measured_iterations);
  uint32_t actual_final = kSeed ^ kPhase;
  uint32_t invocation = 0;

  SetXemuPerfEventContext(kPhase, expected_final);
  EmitXemuPerfEvent(XemuPerfEventType::CONTEXT, 0,
                    host_.GetMeasurementIterationsMultiplier(),
                    warmup_iterations);
  ConfigurePalettePipeline();
  host_.PrepareDraw(kBackgroundColor);

  auto results = Profile(kPaletteOnlyUpdateName, 1, [&]() {
    auto *indices = host_.GetTextureMemoryForStage(0);
    memset(indices, 0, kTexturePixels);
    const int palette_result =
        host_.SetPalette(initial_palette.data(), TestHost::PALETTE_256, 0);
    AssertXemuPerfEqual(0, static_cast<uint32_t>(palette_result),
                        XemuPerfAssertion::PIPELINE_TEXTURE_INPUT,
                        "palette_setup_succeeds", __FILE__, __LINE__);

    for (const auto &quad : kQuads) {
      host_.DrawTexturedScreenQuadEx(
          quad.left, quad.top, quad.right, quad.bottom, 1.f, 0.f, 0.f,
          static_cast<float>(kTextureWidth), 0.f,
          static_cast<float>(kTextureWidth),
          static_cast<float>(kTextureHeight), 0.f,
          static_cast<float>(kTextureHeight));
    }
    SynchronizeCorrectness(host_);

    // Change only palette memory. The index image and every texture method
    // remain untouched, so the next draw must be recovered by palette dirtiness.
    host_.GetPaletteMemoryForStage(0)[0] = kTextureBColor;
    const Quad &first = kQuads[0];
    host_.DrawTexturedScreenQuadEx(
        first.left, first.top, first.right, first.bottom, 1.f, 0.f, 0.f,
        static_cast<float>(kTextureWidth), 0.f,
        static_cast<float>(kTextureWidth),
        static_cast<float>(kTextureHeight), 0.f,
        static_cast<float>(kTextureHeight));
    SynchronizeCorrectness(host_);

    // These draws perform no writes or state changes. Host counters correlated
    // with F0/F1 can verify that validation retired after the palette update.
    for (uint32_t operation = 0; operation < kOperationsPerIteration;
         ++operation) {
      const Quad &quad = kQuads[operation & 3];
      host_.DrawTexturedScreenQuadEx(
          quad.left, quad.top, quad.right, quad.bottom, 1.f, 0.f, 0.f,
          static_cast<float>(kTextureWidth), 0.f,
          static_cast<float>(kTextureWidth),
          static_cast<float>(kTextureHeight), 0.f,
          static_cast<float>(kTextureHeight));
    }

    if (invocation >= warmup_iterations) {
      actual_final = FoldKnownOutput(actual_final, input_kat);
      actual_final = FoldKnownOutput(actual_final, kPhase);
      actual_final = FoldKnownOutput(actual_final, kOperationsPerIteration);
      actual_final = FoldKnownOutput(actual_final, kMutationPixelKat);
    }
    ++invocation;
  });

  SynchronizeCorrectness(host_);
  const uint32_t actual_index_kat = HashWords(
      reinterpret_cast<volatile const uint32_t *>(
          host_.GetTextureMemoryForStage(0)),
      kPaletteIndexWords);
  const uint32_t actual_palette_kat = HashWords(
      host_.GetPaletteMemoryForStage(0), kPaletteEntries);
  AssertXemuPerfEqual(kPaletteIndexKat, actual_index_kat,
                      XemuPerfAssertion::PIPELINE_TEXTURE_BACKING,
                      "palette_only_indices_unchanged", __FILE__, __LINE__);
  AssertXemuPerfEqual(kPaletteChangedKat, actual_palette_kat,
                      XemuPerfAssertion::PIPELINE_TEXTURE_BACKING,
                      "palette_only_palette_changed", __FILE__, __LINE__);
  const uint32_t actual_pixel_kat =
      ValidateSolidTilePixels(kTextureBColor, "palette_only_tile_is_blue");
  AssertXemuPerfEqual(kMutationPixelKat, actual_pixel_kat,
                      XemuPerfAssertion::PIPELINE_TEXTURE_SURFACE,
                      "palette_only_pixel_kat == expected", __FILE__,
                      __LINE__);
  AssertXemuPerfEqual(expected_final, actual_final,
                      XemuPerfAssertion::PIPELINE_TEXTURE_FINAL,
                      "palette_only_final_state == expected", __FILE__,
                      __LINE__);

  host_.SetTextureStageEnabled(0, false);
  host_.SetShaderStageProgram(TestHost::STAGE_NONE);
  host_.SetupTextureStages();
  host_.SetFinalCombiner0Just(TestHost::SRC_DIFFUSE);
  host_.SetFinalCombiner1Just(TestHost::SRC_DIFFUSE, true);
  host_.SetBlend(false);
  host_.PrepareDraw(kPaletteOnlyFinalColor);
  SynchronizeCorrectness(host_);
  const uint64_t actual_frame_hash = HashBackBuffer();
  AssertXemuPerfEqual(
      static_cast<uint32_t>(kPaletteOnlyFinalFrameHash >> 32),
      static_cast<uint32_t>(actual_frame_hash >> 32),
      XemuPerfAssertion::PIPELINE_TEXTURE_FRAMEBUFFER,
      "palette_only_framebuffer_hash_hi == expected", __FILE__, __LINE__);
  AssertXemuPerfEqual(static_cast<uint32_t>(kPaletteOnlyFinalFrameHash),
                      static_cast<uint32_t>(actual_frame_hash),
                      XemuPerfAssertion::PIPELINE_TEXTURE_FRAMEBUFFER,
                      "palette_only_framebuffer_hash_lo == expected", __FILE__,
                      __LINE__);

  std::ostringstream metadata;
  metadata << "{\"schema_version\":1,";
  metadata << "\"kind\":\"palette_only_texture_revalidation\",";
  metadata << "\"test_id\":\"" << kPaletteOnlyUpdateName << "\",";
  metadata << "\"oracle_provenance\":\"SPEC_DERIVED\",";
  metadata << "\"texture_bytes_changed\":0,";
  metadata << "\"palette_entries_changed\":1,";
  metadata << "\"validation_draws\":" << results.iterations << ",";
  metadata << "\"steady_redraws\":"
           << static_cast<uint64_t>(kOperationsPerIteration) * results.iterations
           << ",";
  metadata << "\"index_kat\":{\"expected\":" << kPaletteIndexKat
           << ",\"actual\":" << actual_index_kat << "},";
  metadata << "\"palette_kat\":{\"expected\":" << kPaletteChangedKat
           << ",\"actual\":" << actual_palette_kat << "},";
  metadata << "\"rendered_pixel_kat\":{\"expected\":"
           << kMutationPixelKat << ",\"actual\":" << actual_pixel_kat
           << "},";
  metadata << "\"expected_final_state\":" << expected_final << ",";
  metadata << "\"actual_final_state\":" << actual_final << ",";
  metadata << "\"counter_contract\":{\"palette_uploads_per_iteration\":2,"
              "\"unchanged_redraw_uploads\":0},";
  metadata << "\"terminal_fence\":\"F2 after F1\"}";
  EmitXemuPerfEvent(XemuPerfEventType::PASS, 0, expected_final, actual_final);
  host_.FinishDraw(suite_name_, kPaletteOnlyUpdateName, results,
                   metadata.str());
  ClearXemuPerfEventContext();
}

void PipelineTextureSwitchTests::RunSharedPageOverlap() {
  static constexpr uint32_t kPhase = 0x1506;
  uint32_t input_kat = kFnvOffsetBasis;
  const uint32_t input_words[]{
      kSeed, kTextureWidth, kTextureHeight, kSharedBindingOffset,
      kLinearTextureBytes, kSharedInitialKat, kSharedChangedKat,
      kSharedBindingBKat, kOperationsPerIteration,
  };
  for (uint32_t value : input_words) {
    input_kat = Fnv1aAddWord(input_kat, value);
  }
  AssertXemuPerfEqual(kSharedPageInputKat, input_kat,
                      XemuPerfAssertion::PIPELINE_TEXTURE_INPUT,
                      "shared_page_input == expected", __FILE__, __LINE__);

  const uint32_t measured_iterations =
      host_.GetSaveResults() ? host_.GetMeasurementIterationsMultiplier() : 1;
  const uint32_t warmup_iterations =
      host_.GetSaveResults() ? host_.GetWarmupIterations() : 0;
  const uint32_t expected_final =
      ExpectedFinalState(kPhase, input_kat, kMutationPixelKat,
                         measured_iterations);
  uint32_t actual_final = kSeed ^ kPhase;
  uint32_t invocation = 0;
  const uint32_t binding_a =
      reinterpret_cast<uint32_t>(host_.GetTextureMemoryForStage(2)) &
      0x03FFFFFF;
  const uint32_t binding_b = binding_a + kSharedBindingOffset;

  SetXemuPerfEventContext(kPhase, expected_final);
  EmitXemuPerfEvent(XemuPerfEventType::CONTEXT, 0,
                    host_.GetMeasurementIterationsMultiplier(),
                    warmup_iterations);
  ConfigureTexturePipeline();
  host_.PrepareDraw(kBackgroundColor);

  auto results = Profile(kSharedPageOverlapName, 1, [&]() {
    auto *shared = reinterpret_cast<uint32_t *>(
        host_.GetTextureMemoryForStage(2));
    for (uint32_t word = 0; word < kSharedRegionWords; ++word) {
      shared[word] = kTextureAColor;
    }

    // Populate two distinct cache bindings whose 16 KiB source ranges overlap
    // by all but 256 bytes and therefore share the four pages dirtied below.
    for (uint32_t address : {binding_a, binding_b}) {
      Pushbuffer::Begin();
      Pushbuffer::Push(NV097_SET_TEXTURE_OFFSET, address);
      Pushbuffer::End();
      for (const auto &quad : kQuads) {
        host_.DrawTexturedScreenQuadEx(
            quad.left, quad.top, quad.right, quad.bottom, 1.f, 0.f, 0.f,
            static_cast<float>(kTextureWidth), 0.f,
            static_cast<float>(kTextureWidth),
            static_cast<float>(kTextureHeight), 0.f,
            static_cast<float>(kTextureHeight));
      }
      SynchronizeCorrectness(host_);
    }

    Pushbuffer::Begin();
    Pushbuffer::Push(NV097_SET_TEXTURE_OFFSET, binding_a);
    Pushbuffer::End();
    for (uint32_t word = 0; word < kTexturePixels; ++word) {
      shared[word] = kTextureBColor;
    }

    // Validate binding A and complete it before selecting B. Clearing the page
    // dirty bit here must not retire B's per-binding validation hint.
    const Quad &first = kQuads[0];
    host_.DrawTexturedScreenQuadEx(
        first.left, first.top, first.right, first.bottom, 1.f, 0.f, 0.f,
        static_cast<float>(kTextureWidth), 0.f,
        static_cast<float>(kTextureWidth),
        static_cast<float>(kTextureHeight), 0.f,
        static_cast<float>(kTextureHeight));
    SynchronizeCorrectness(host_);

    Pushbuffer::Begin();
    Pushbuffer::Push(NV097_SET_TEXTURE_OFFSET, binding_b);
    Pushbuffer::End();
    host_.DrawTexturedScreenQuadEx(
        first.left, first.top, first.right, first.bottom, 1.f, 0.f, 0.f,
        static_cast<float>(kTextureWidth), 0.f,
        static_cast<float>(kTextureWidth),
        static_cast<float>(kTextureHeight), 0.f,
        static_cast<float>(kTextureHeight));
    SynchronizeCorrectness(host_);

    for (uint32_t operation = 0; operation < kOperationsPerIteration;
         ++operation) {
      const Quad &quad = kQuads[operation & 3];
      host_.DrawTexturedScreenQuadEx(
          quad.left, quad.top, quad.right, quad.bottom, 1.f, 0.f, 0.f,
          static_cast<float>(kTextureWidth), 0.f,
          static_cast<float>(kTextureWidth),
          static_cast<float>(kTextureHeight), 0.f,
          static_cast<float>(kTextureHeight));
    }

    if (invocation >= warmup_iterations) {
      actual_final = FoldKnownOutput(actual_final, input_kat);
      actual_final = FoldKnownOutput(actual_final, kPhase);
      actual_final = FoldKnownOutput(actual_final, kOperationsPerIteration);
      actual_final = FoldKnownOutput(actual_final, kMutationPixelKat);
    }
    ++invocation;
  });

  SynchronizeCorrectness(host_);
  const auto *shared = reinterpret_cast<volatile const uint32_t *>(
      host_.GetTextureMemoryForStage(2));
  const uint32_t actual_region_kat = HashWords(shared, kSharedRegionWords);
  const uint32_t actual_binding_b_kat =
      HashWords(shared + kSharedBindingOffsetWords, kTexturePixels);
  AssertXemuPerfEqual(kSharedChangedKat, actual_region_kat,
                      XemuPerfAssertion::PIPELINE_TEXTURE_BACKING,
                      "shared_page_region_changed", __FILE__, __LINE__);
  AssertXemuPerfEqual(kSharedBindingBKat, actual_binding_b_kat,
                      XemuPerfAssertion::PIPELINE_TEXTURE_BACKING,
                      "shared_page_binding_b_source", __FILE__, __LINE__);
  const uint32_t actual_pixel_kat = ValidateSolidTilePixels(
      kTextureBColor, "shared_page_binding_b_tile_is_blue");
  AssertXemuPerfEqual(kMutationPixelKat, actual_pixel_kat,
                      XemuPerfAssertion::PIPELINE_TEXTURE_SURFACE,
                      "shared_page_pixel_kat == expected", __FILE__, __LINE__);
  AssertXemuPerfEqual(expected_final, actual_final,
                      XemuPerfAssertion::PIPELINE_TEXTURE_FINAL,
                      "shared_page_final_state == expected", __FILE__,
                      __LINE__);

  host_.SetTextureStageEnabled(0, false);
  host_.SetShaderStageProgram(TestHost::STAGE_NONE);
  host_.SetupTextureStages();
  host_.SetFinalCombiner0Just(TestHost::SRC_DIFFUSE);
  host_.SetFinalCombiner1Just(TestHost::SRC_DIFFUSE, true);
  host_.SetBlend(false);
  host_.PrepareDraw(kSharedPageFinalColor);
  SynchronizeCorrectness(host_);
  const uint64_t actual_frame_hash = HashBackBuffer();
  AssertXemuPerfEqual(static_cast<uint32_t>(kSharedPageFinalFrameHash >> 32),
                      static_cast<uint32_t>(actual_frame_hash >> 32),
                      XemuPerfAssertion::PIPELINE_TEXTURE_FRAMEBUFFER,
                      "shared_page_framebuffer_hash_hi == expected", __FILE__,
                      __LINE__);
  AssertXemuPerfEqual(static_cast<uint32_t>(kSharedPageFinalFrameHash),
                      static_cast<uint32_t>(actual_frame_hash),
                      XemuPerfAssertion::PIPELINE_TEXTURE_FRAMEBUFFER,
                      "shared_page_framebuffer_hash_lo == expected", __FILE__,
                      __LINE__);

  std::ostringstream metadata;
  metadata << "{\"schema_version\":1,";
  metadata << "\"kind\":\"shared_page_texture_revalidation\",";
  metadata << "\"test_id\":\"" << kSharedPageOverlapName << "\",";
  metadata << "\"oracle_provenance\":\"SPEC_DERIVED\",";
  metadata << "\"cached_bindings\":2,";
  metadata << "\"binding_offset_bytes\":" << kSharedBindingOffset << ",";
  metadata << "\"binding_length_bytes\":" << kLinearTextureBytes << ",";
  metadata << "\"shared_dirty_pages\":4,";
  metadata << "\"validated_before_second_binding\":1,";
  metadata << "\"second_binding_validation_draws\":" << results.iterations
           << ",";
  metadata << "\"steady_redraws\":"
           << static_cast<uint64_t>(kOperationsPerIteration) * results.iterations
           << ",";
  metadata << "\"region_kat\":{\"expected\":" << kSharedChangedKat
           << ",\"actual\":" << actual_region_kat << "},";
  metadata << "\"binding_b_kat\":{\"expected\":" << kSharedBindingBKat
           << ",\"actual\":" << actual_binding_b_kat << "},";
  metadata << "\"rendered_pixel_kat\":{\"expected\":"
           << kMutationPixelKat << ",\"actual\":" << actual_pixel_kat
           << "},";
  metadata << "\"expected_final_state\":" << expected_final << ",";
  metadata << "\"actual_final_state\":" << actual_final << ",";
  metadata << "\"counter_contract\":{\"binding_uploads_per_iteration\":4,"
              "\"post_mutation_binding_a_uploads\":1,"
              "\"post_mutation_binding_b_uploads\":1,"
              "\"unchanged_redraw_uploads\":0},";
  metadata << "\"terminal_fence\":\"F2 after F1\"}";
  EmitXemuPerfEvent(XemuPerfEventType::PASS, 0, expected_final, actual_final);
  host_.FinishDraw(suite_name_, kSharedPageOverlapName, results,
                   metadata.str());
  ClearXemuPerfEventContext();
}

void PipelineTextureSwitchTests::RunTextureDmaRemap() {
  static constexpr uint32_t kPhase = 0x1507;
  static constexpr uint32_t kFormatB =
      2U | (2U << 4) |
      (NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_A8R8G8B8 << 8) |
      (1U << 16) | (6U << 20) | (6U << 24);
  static constexpr uint32_t kExpected[] = {
      kTextureAColor, kTextureBColor, kDiffuseColor, kTextureBColor};
  uint32_t expected_kat = kFnvOffsetBasis;
  for (uint32_t expected : kExpected) {
    expected_kat = Fnv1aAddWord(expected_kat, expected);
  }

  ASSERT(dma_texture_storage_ != nullptr);
  if (!dma_texture_storage_) {
    return;
  }
  auto *red = dma_texture_storage_;
  auto *blue = red + kTexturePixels;
  auto *green = blue + kTexturePixels;
  for (uint32_t pixel = 0; pixel < kTexturePixels; ++pixel) {
    red[pixel] = kTextureAColor;
    blue[pixel] = kTextureBColor;
    green[pixel] = kDiffuseColor;
  }
  const uint32_t red_source =
      reinterpret_cast<uint32_t>(red) & 0x03FFFFFF;
  const uint32_t blue_source =
      reinterpret_cast<uint32_t>(blue) & 0x03FFFFFF;
  const uint32_t green_source =
      reinterpret_cast<uint32_t>(green) & 0x03FFFFFF;
  const uint32_t red_source_kat = HashWords(red, kTexturePixels);
  const uint32_t blue_source_kat = HashWords(blue, kTexturePixels);
  const uint32_t green_source_kat = HashWords(green, kTexturePixels);
  AssertXemuPerfEqual(0, (red_source | blue_source | green_source) & 0xFFF,
                      XemuPerfAssertion::PIPELINE_TEXTURE_INPUT,
                      "texture_dma_sources_page_aligned", __FILE__, __LINE__);
  AssertXemuPerfEqual(1, static_cast<uint32_t>(
                          red_source != blue_source &&
                          red_source != green_source &&
                          blue_source != green_source),
                      XemuPerfAssertion::PIPELINE_TEXTURE_INPUT,
                      "texture_dma_sources_distinct", __FILE__, __LINE__);
  PrintMsg("TEXTURE_DMA_REMAP_SOURCES %08lx %08lx %08lx\n",
           static_cast<unsigned long>(red_source),
           static_cast<unsigned long>(blue_source),
           static_cast<unsigned long>(green_source));
  PrintMsg("TEXTURE_DMA_REMAP_SOURCE_KATS %08lx %08lx %08lx\n",
           static_cast<unsigned long>(red_source_kat),
           static_cast<unsigned long>(blue_source_kat),
           static_cast<unsigned long>(green_source_kat));

  host_.SetVertexShaderProgram(nullptr);
  host_.SetupFixedFunctionPassthrough();
  for (uint32_t stage = 0; stage < 2; ++stage) {
    auto &texture = host_.GetTextureStage(stage);
    texture.SetFormat(GetTextureFormatInfo(
        NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_A8R8G8B8));
    texture.SetTextureDimensions(kTextureWidth, kTextureHeight);
    texture.SetImageDimensions(kTextureWidth, kTextureHeight);
    texture.SetMipMapLevels(1);
    texture.SetLODClamp(0, 0);
    texture.SetUWrap(TextureStage::WRAP_CLAMP_TO_EDGE, false);
    texture.SetVWrap(TextureStage::WRAP_CLAMP_TO_EDGE, false);
    texture.SetPWrap(TextureStage::WRAP_CLAMP_TO_EDGE, false);
    texture.SetFilter();
    texture.SetEnabled(true);
  }
  host_.SetShaderStageProgram(TestHost::STAGE_2D_PROJECTIVE,
                              TestHost::STAGE_2D_PROJECTIVE);
  host_.SetupTextureStages();
  host_.SetBlend(false);
  host_.SetFinalCombiner1Just(TestHost::SRC_ZERO, true, true);
  Pushbuffer::Begin();
  Pushbuffer::Push(NV097_SET_CULL_FACE_ENABLE, false);
  Pushbuffer::Push(NV097_SET_DEPTH_TEST_ENABLE, false);
  Pushbuffer::End();

  SetXemuPerfEventContext(kPhase, expected_kat);
  auto results = Profile(kTextureDmaRemapName, 1, [&]() {
    host_.PrepareDraw(kBackgroundColor);
    // PrepareDraw recommits the host's default A-relative texture methods.
    // Establish the initial two-DMA state before the control draws.
    Pushbuffer::Begin();
    Pushbuffer::Push(NV097_SET_CONTEXT_DMA_A, texture_dma_red_.ChannelID);
    Pushbuffer::Push(NV097_SET_CONTEXT_DMA_B, texture_dma_blue_.ChannelID);
    Pushbuffer::Push(NV097_SET_TEXTURE_OFFSET, 0);
    Pushbuffer::Push(NV097_SET_TEXTURE_OFFSET + kTextureStageStride, 0);
    Pushbuffer::Push(NV097_SET_TEXTURE_FORMAT + kTextureStageStride, kFormatB);
    Pushbuffer::End();
    DrawDmaTile(host_, kQuads[0], false, kTextureWidth);
    DrawDmaTile(host_, kQuads[1], true, kTextureWidth);
    SynchronizeCorrectness(host_);

    // Stage 0's source changes without a stage-0 texture-state write. Stage 1
    // receives an unrelated sampler write, admitting the texture slow path.
    // The binder must resolve stage 0's new A target despite its clean flag.
    Pushbuffer::Begin();
    Pushbuffer::Push(NV097_SET_CONTEXT_DMA_A, texture_dma_green_.ChannelID);
    Pushbuffer::Push(NV097_SET_TEXTURE_ADDRESS + kTextureStageStride,
                     kRepeatAddress);
    Pushbuffer::End();
    DrawDmaTile(host_, kQuads[2], false, kTextureWidth);
    DrawDmaTile(host_, kQuads[3], true, kTextureWidth);
  });
  SynchronizeCorrectness(host_);
  uint32_t actual_kat = kFnvOffsetBasis;
  std::array<uint32_t, 4> actual_tiles{};
  for (uint32_t tile = 0; tile < 4; ++tile) {
    const uint32_t actual = ReadTileCenter(tile);
    actual_tiles[tile] = actual;
    AssertXemuPerfEqual(kExpected[tile], actual,
                        XemuPerfAssertion::PIPELINE_TEXTURE_SURFACE,
                        "texture_dma_remap_tile", __FILE__, __LINE__);
    actual_kat = Fnv1aAddWord(actual_kat, actual);
  }
  PrintMsg("TEXTURE_DMA_REMAP_TILES %08lx %08lx %08lx %08lx\n",
           static_cast<unsigned long>(actual_tiles[0]),
           static_cast<unsigned long>(actual_tiles[1]),
           static_cast<unsigned long>(actual_tiles[2]),
           static_cast<unsigned long>(actual_tiles[3]));
  AssertXemuPerfEqual(expected_kat, actual_kat,
                      XemuPerfAssertion::PIPELINE_TEXTURE_FINAL,
                      "texture_dma_remap_pixel_kat", __FILE__, __LINE__);
  PushDmaBinding(NV097_SET_CONTEXT_DMA_A, kDefaultDmaA);
  PushDmaBinding(NV097_SET_CONTEXT_DMA_B, kDefaultDmaB);
  host_.SetTextureStageEnabled(0, false);
  host_.SetTextureStageEnabled(1, false);
  host_.SetShaderStageProgram(TestHost::STAGE_NONE);
  host_.SetupTextureStages();
  host_.PrepareDraw(kBackgroundColor);
  SynchronizeCorrectness(host_);

  std::ostringstream metadata;
  metadata << "{\"schema_version\":1,\"kind\":\"texture_dma_remap\",";
  metadata << "\"test_id\":\"" << kTextureDmaRemapName << "\",";
  metadata << "\"oracle_provenance\":\"SPEC_DERIVED\",";
  metadata << "\"clean_remapped_stage\":0,\"dirty_control_stage\":1,";
  metadata << "\"stage0_texture_state_writes_after_remap\":0,";
  metadata << "\"stage1_sampler_writes_after_remap\":1,";
  metadata << "\"source_physical\":{\"red\":" << red_source
           << ",\"blue\":" << blue_source << ",\"green\":"
           << green_source << "},";
  metadata << "\"source_kat\":{\"red\":" << red_source_kat
           << ",\"blue\":" << blue_source_kat << ",\"green\":"
           << green_source_kat << "},";
  metadata << "\"expected_pixel_kat\":" << expected_kat << ",";
  metadata << "\"actual_pixel_kat\":" << actual_kat << ",";
  metadata << "\"tile_argb\":[" << actual_tiles[0] << ","
           << actual_tiles[1] << "," << actual_tiles[2] << ","
           << actual_tiles[3] << "],";
  metadata << "\"terminal_fence\":\"F2 after F1\"}";
  EmitXemuPerfEvent(XemuPerfEventType::PASS, 0, expected_kat, actual_kat);
  host_.FinishDraw(suite_name_, kTextureDmaRemapName, results, metadata.str());
  ClearXemuPerfEventContext();
}

void PipelineTextureSwitchTests::RunPaletteDmaRemap() {
  static constexpr uint32_t kPhase = 0x1508;
  static constexpr uint32_t kExpected[] = {
      kTextureAColor, kTextureBColor, kTextureBColor, kTextureBColor};
  uint32_t expected_kat = kFnvOffsetBasis;
  for (uint32_t expected : kExpected) {
    expected_kat = Fnv1aAddWord(expected_kat, expected);
  }
  memset(host_.GetTextureMemoryForStage(0), 0, kTexturePixels);
  auto *red = host_.GetPaletteMemoryForStage(0);
  // DMA descriptors store the page frame separately from the 12-bit adjust.
  // pb_create_dma_ctx does not encode an adjust, so sources 1 KiB apart in
  // GetPaletteMemoryForStage(0/1) would resolve to the same 4 KiB page.
  auto *blue = reinterpret_cast<uint32_t *>(
      host_.GetTextureMemoryForStage(2));
  for (uint32_t entry = 0; entry < kPaletteEntries; ++entry) {
    red[entry] = kTextureAColor;
    blue[entry] = kTextureBColor;
  }
  auto *stage_one_image = reinterpret_cast<uint32_t *>(
      host_.GetTextureMemoryForStage(3));
  const uint32_t red_dma_page = reinterpret_cast<uint32_t>(red) & 0x03FFF000;
  const uint32_t blue_dma_page = reinterpret_cast<uint32_t>(blue) & 0x03FFF000;
  AssertXemuPerfEqual(0, reinterpret_cast<uint32_t>(red) & 0xFFF,
                      XemuPerfAssertion::PIPELINE_TEXTURE_INPUT,
                      "palette_red_dma_page_aligned", __FILE__, __LINE__);
  AssertXemuPerfEqual(0, reinterpret_cast<uint32_t>(blue) & 0xFFF,
                      XemuPerfAssertion::PIPELINE_TEXTURE_INPUT,
                      "palette_blue_dma_page_aligned", __FILE__, __LINE__);
  AssertXemuPerfEqual(1, static_cast<uint32_t>(red_dma_page != blue_dma_page),
                      XemuPerfAssertion::PIPELINE_TEXTURE_INPUT,
                      "palette_dma_sources_have_distinct_pages", __FILE__,
                      __LINE__);
  for (uint32_t pixel = 0; pixel < kTexturePixels; ++pixel) {
    stage_one_image[pixel] = kTextureBColor;
  }

  ConfigurePalettePipeline();
  auto &stage_one = host_.GetTextureStage(1);
  stage_one.SetFormat(GetTextureFormatInfo(
      NV097_SET_TEXTURE_FORMAT_COLOR_LU_IMAGE_A8R8G8B8));
  stage_one.SetTextureDimensions(kTextureWidth, kTextureHeight);
  stage_one.SetImageDimensions(kTextureWidth, kTextureHeight);
  stage_one.SetMipMapLevels(1);
  stage_one.SetLODClamp(0, 0);
  stage_one.SetUWrap(TextureStage::WRAP_CLAMP_TO_EDGE, false);
  stage_one.SetVWrap(TextureStage::WRAP_CLAMP_TO_EDGE, false);
  stage_one.SetPWrap(TextureStage::WRAP_CLAMP_TO_EDGE, false);
  stage_one.SetFilter();
  stage_one.SetEnabled(true);
  host_.SetShaderStageProgram(TestHost::STAGE_2D_PROJECTIVE,
                              TestHost::STAGE_2D_PROJECTIVE);
  host_.SetupTextureStages();

  SetXemuPerfEventContext(kPhase, expected_kat);
  auto results = Profile(kPaletteDmaRemapName, 1, [&]() {
    host_.PrepareDraw(kBackgroundColor);
    Pushbuffer::Begin();
    Pushbuffer::Push(NV097_SET_CONTEXT_DMA_B, palette_dma_red_.ChannelID);
    Pushbuffer::Push(NV097_SET_TEXTURE_PALETTE, 1U);
    Pushbuffer::Push(NV097_SET_TEXTURE_OFFSET + kTextureStageStride,
                     reinterpret_cast<uint32_t>(stage_one_image) & 0x03FFFFFF);
    Pushbuffer::End();
    DrawDmaTile(host_, kQuads[0], false, 1.f);
    DrawDmaTile(host_, kQuads[1], true, kTextureWidth);
    SynchronizeCorrectness(host_);

    // Stage 0's indexed image and palette method stay clean. The palette DMA
    // source changes while an unrelated stage-1 sampler write admits a bind.
    Pushbuffer::Begin();
    Pushbuffer::Push(NV097_SET_CONTEXT_DMA_B, palette_dma_blue_.ChannelID);
    Pushbuffer::Push(NV097_SET_TEXTURE_ADDRESS + kTextureStageStride,
                     kRepeatAddress);
    Pushbuffer::End();
    DrawDmaTile(host_, kQuads[2], false, 1.f);
    DrawDmaTile(host_, kQuads[3], true, kTextureWidth);
  });
  SynchronizeCorrectness(host_);
  uint32_t actual_kat = kFnvOffsetBasis;
  std::array<uint32_t, 4> actual_tiles{};
  for (uint32_t tile = 0; tile < 4; ++tile) {
    const uint32_t actual = ReadTileCenter(tile);
    actual_tiles[tile] = actual;
    AssertXemuPerfEqual(kExpected[tile], actual,
                        XemuPerfAssertion::PIPELINE_TEXTURE_SURFACE,
                        "palette_dma_remap_tile", __FILE__, __LINE__);
    actual_kat = Fnv1aAddWord(actual_kat, actual);
  }
  PrintMsg("PALETTE_DMA_REMAP_TILES %08lx %08lx %08lx %08lx\n",
           static_cast<unsigned long>(actual_tiles[0]),
           static_cast<unsigned long>(actual_tiles[1]),
           static_cast<unsigned long>(actual_tiles[2]),
           static_cast<unsigned long>(actual_tiles[3]));
  AssertXemuPerfEqual(expected_kat, actual_kat,
                      XemuPerfAssertion::PIPELINE_TEXTURE_FINAL,
                      "palette_dma_remap_pixel_kat", __FILE__, __LINE__);
  PushDmaBinding(NV097_SET_CONTEXT_DMA_B, kDefaultDmaB);
  host_.SetTextureStageEnabled(0, false);
  host_.SetTextureStageEnabled(1, false);
  host_.SetShaderStageProgram(TestHost::STAGE_NONE);
  host_.SetupTextureStages();
  host_.PrepareDraw(kBackgroundColor);
  SynchronizeCorrectness(host_);

  std::ostringstream metadata;
  metadata << "{\"schema_version\":1,\"kind\":\"palette_dma_remap\",";
  metadata << "\"test_id\":\"" << kPaletteDmaRemapName << "\",";
  metadata << "\"oracle_provenance\":\"SPEC_DERIVED\",";
  metadata << "\"clean_palette_stage\":0,\"dirty_control_stage\":1,";
  metadata << "\"palette_register_writes_after_remap\":0,";
  metadata << "\"stage1_sampler_writes_after_remap\":1,";
  metadata << "\"expected_pixel_kat\":" << expected_kat << ",";
  metadata << "\"actual_pixel_kat\":" << actual_kat << ",";
  metadata << "\"tile_argb\":[" << actual_tiles[0] << ","
           << actual_tiles[1] << "," << actual_tiles[2] << ","
           << actual_tiles[3] << "],";
  metadata << "\"terminal_fence\":\"F2 after F1\"}";
  EmitXemuPerfEvent(XemuPerfEventType::PASS, 0, expected_kat, actual_kat);
  host_.FinishDraw(suite_name_, kPaletteDmaRemapName, results, metadata.str());
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
  texture_stage.SetMipMapLevels(1);
  texture_stage.SetLODClamp(0, 4095);
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

void PipelineTextureSwitchTests::ConfigurePalettePipeline() const {
  host_.SetVertexShaderProgram(nullptr);
  host_.SetupFixedFunctionPassthrough();
  auto &texture_stage = host_.GetTextureStage(0);
  texture_stage.SetFormat(GetTextureFormatInfo(
      NV097_SET_TEXTURE_FORMAT_COLOR_SZ_I8_A8R8G8B8));
  texture_stage.SetTextureDimensions(kTextureWidth, kTextureHeight);
  texture_stage.SetImageDimensions(kTextureWidth, kTextureHeight);
  texture_stage.SetMipMapLevels(1);
  texture_stage.SetLODClamp(0, 0);
  texture_stage.SetUWrap(TextureStage::WRAP_CLAMP_TO_EDGE, false);
  texture_stage.SetVWrap(TextureStage::WRAP_CLAMP_TO_EDGE, false);
  texture_stage.SetPWrap(TextureStage::WRAP_CLAMP_TO_EDGE, false);
  texture_stage.SetFilter();
  texture_stage.SetEnabled(true);
  host_.SetPaletteSize(TestHost::PALETTE_256, 0);
  host_.SetShaderStageProgram(TestHost::STAGE_2D_PROJECTIVE);
  host_.SetupTextureStages();
  host_.SetBlend(false);
  host_.SetFinalCombiner0Just(TestHost::SRC_TEX0);
  host_.SetFinalCombiner1Just(TestHost::SRC_ZERO, true, true);
  Pushbuffer::Begin();
  Pushbuffer::Push(NV097_SET_CULL_FACE_ENABLE, false);
  Pushbuffer::Push(NV097_SET_DEPTH_TEST_ENABLE, false);
  Pushbuffer::End();
}

void PipelineTextureSwitchTests::ConfigureSamplerIdentityPipeline() const {
  host_.SetVertexShaderProgram(nullptr);
  host_.SetupFixedFunctionPassthrough();
  auto &texture_stage = host_.GetTextureStage(0);
  texture_stage.SetFormat(GetTextureFormatInfo(
      NV097_SET_TEXTURE_FORMAT_COLOR_SZ_A8R8G8B8));
  texture_stage.SetTextureDimensions(kTextureWidth, kTextureHeight);
  texture_stage.SetImageDimensions(kTextureWidth, kTextureHeight);
  texture_stage.SetMipMapLevels(kSamplerMipLevels);
  texture_stage.SetUWrap(TextureStage::WRAP_REPEAT, false);
  texture_stage.SetVWrap(TextureStage::WRAP_REPEAT, false);
  texture_stage.SetPWrap(TextureStage::WRAP_REPEAT, false);
  texture_stage.SetBorderFromColor(true);
  texture_stage.SetBorderColor(0xFF112233);
  texture_stage.SetLODClamp(0, 0);
  texture_stage.SetFilter(0, TextureStage::K_QUINCUNX,
                          TextureStage::MIN_BOX_NEARESTLOD,
                          TextureStage::MAG_BOX_LOD0);
  texture_stage.SetEnabled(true);
  host_.SetShaderStageProgram(TestHost::STAGE_2D_PROJECTIVE);
  host_.SetupTextureStages();
  host_.SetBlend(false);
  host_.SetFinalCombiner0Just(TestHost::SRC_TEX0);
  host_.SetFinalCombiner1Just(TestHost::SRC_ZERO, true, true);
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
    if (recipe.sampler_only_identity) {
      auto &texture_stage = host_.GetTextureStage(0);
      const uint32_t lod = selector ? (2U << 8) : 0;
      texture_stage.SetLODClamp(lod, lod);
      // Repeat avoids making the output oracle depend on where a backend
      // applies mip-coordinate scaling. LOD and min/mag filters still form
      // two distinct sampler identities while selecting deterministic texels.
      texture_stage.SetUWrap(TextureStage::WRAP_REPEAT, false);
      texture_stage.SetVWrap(TextureStage::WRAP_REPEAT, false);
      texture_stage.SetPWrap(TextureStage::WRAP_REPEAT, false);
      texture_stage.SetBorderColor(selector ? 0xFF445566 : 0xFF112233);
      texture_stage.SetFilter(
          0, TextureStage::K_QUINCUNX,
          selector ? TextureStage::MIN_TENT_NEARESTLOD
                   : TextureStage::MIN_BOX_NEARESTLOD,
          selector ? TextureStage::MAG_TENT_LOD0
                   : TextureStage::MAG_BOX_LOD0);
      host_.SetupTextureStages();
    } else if (recipe.shader_negative_control) {
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
    if (recipe.sampler_only_identity) {
      // The ordinary tiles magnify a 48-texel span and therefore use the
      // magnification path regardless of the LOD clamp. Keep the same tile
      // centers, but draw an 8-pixel square so the 24-texel span is minified.
      // Its center remains inside the 16x16 level-2 image even with border
      // wrapping. Exact clamps 0 and 2 select the intended red/green levels.
      const float center_x = (quad.left + quad.right) * 0.5f;
      const float center_y = (quad.top + quad.bottom) * 0.5f;
      host_.DrawTexturedScreenQuadEx(
          center_x - kSamplerQuadHalfExtent,
          center_y - kSamplerQuadHalfExtent,
          center_x + kSamplerQuadHalfExtent,
          center_y + kSamplerQuadHalfExtent, 1.f, kSamplerUvMin,
          kSamplerUvMin, kSamplerUvMax, kSamplerUvMin, kSamplerUvMax,
          kSamplerUvMax, kSamplerUvMin, kSamplerUvMax);
    } else {
      host_.DrawTexturedScreenQuadEx(
          quad.left, quad.top, quad.right, quad.bottom, 1.f, -16.f, -16.f,
          80.f, -16.f, 80.f, 80.f, -16.f, 80.f);
    }
  }
}

void PipelineTextureSwitchTests::RunClearTextureNormalIteration() const {
  const uint32_t texture_a =
      reinterpret_cast<uint32_t>(host_.GetTextureMemoryForStage(0)) &
      0x03FFFFFF;
  const uint32_t texture_b =
      reinterpret_cast<uint32_t>(host_.GetTextureMemoryForStage(1)) &
      0x03FFFFFF;

  for (uint32_t boundary = 0; boundary < kClearBoundariesPerIteration;
       ++boundary) {
    const Quad &quad = kQuads[boundary & 3];
    host_.ClearColorRegion(
        kBoundaryClearColor, static_cast<uint32_t>(quad.left),
        static_cast<uint32_t>(quad.top),
        static_cast<uint32_t>(quad.right - quad.left),
        static_cast<uint32_t>(quad.bottom - quad.top));

    // The clear pipeline is now bound. This texture-only descriptor change
    // must force a normal pipeline bind and must not be attributed to the
    // texture-only bypass.
    Pushbuffer::Begin();
    Pushbuffer::Push(NV097_SET_TEXTURE_OFFSET, texture_b);
    Pushbuffer::End();
    host_.DrawTexturedScreenQuadEx(
        quad.left, quad.top, quad.right, quad.bottom, 1.f, -16.f, -16.f,
        80.f, -16.f, 80.f, 80.f, -16.f, 80.f);

    // A normal zero-binding inline/immediate pipeline is now active. The
    // second descriptor-only transition exercises the safe bypass path.
    Pushbuffer::Begin();
    Pushbuffer::Push(NV097_SET_TEXTURE_OFFSET, texture_a);
    Pushbuffer::End();
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
    if (recipe.sampler_only_identity) {
      expected = (tile & 1) ? kSamplerMipColors[4] : kSamplerMipColors[0];
    } else if (recipe.shader_negative_control) {
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

uint32_t PipelineTextureSwitchTests::ValidateClearTextureNormalPixels() const {
  const auto *base =
      reinterpret_cast<volatile const uint8_t *>(pb_back_buffer());
  const uint32_t pitch = pb_back_buffer_pitch();
  uint32_t kat = kFnvOffsetBasis;
  for (uint32_t tile = 0; tile < 4; ++tile) {
    const Quad &quad = kQuads[tile];
    const uint32_t x =
        static_cast<uint32_t>((quad.left + quad.right) * 0.5f);
    const uint32_t y =
        static_cast<uint32_t>((quad.top + quad.bottom) * 0.5f);
    const auto *row =
        reinterpret_cast<volatile const uint32_t *>(base + y * pitch);
    const uint32_t actual = row[x];
    AssertXemuPerfEqual(kTextureAColor, actual,
                        XemuPerfAssertion::PIPELINE_TEXTURE_SURFACE,
                        "clear_texture_normal_tile_pixel == texture_a",
                        __FILE__, __LINE__);
    kat = Fnv1aAddWord(kat, actual);
  }
  return kat;
}

uint32_t PipelineTextureSwitchTests::ValidateSolidTilePixels(
    uint32_t expected, const char *message) const {
  const auto *base =
      reinterpret_cast<volatile const uint8_t *>(pb_back_buffer());
  const uint32_t pitch = pb_back_buffer_pitch();
  uint32_t kat = kFnvOffsetBasis;
  for (const auto &quad : kQuads) {
    const uint32_t x =
        static_cast<uint32_t>((quad.left + quad.right) * 0.5f);
    const uint32_t y =
        static_cast<uint32_t>((quad.top + quad.bottom) * 0.5f);
    const auto *row =
        reinterpret_cast<volatile const uint32_t *>(base + y * pitch);
    const uint32_t actual = row[x];
    AssertXemuPerfEqual(expected, actual,
                        XemuPerfAssertion::PIPELINE_TEXTURE_SURFACE, message,
                        __FILE__, __LINE__);
    kat = Fnv1aAddWord(kat, actual);
  }
  return kat;
}
