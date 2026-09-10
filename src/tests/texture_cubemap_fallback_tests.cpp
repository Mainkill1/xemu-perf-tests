#include "texture_cubemap_fallback_tests.h"

#include <array>
#include <cstdint>
#include <cstring>
#include <sstream>
#include <utility>

#include <pbkit/pbkit.h>

#include "debug_output.h"
#include "test_host.h"
#include "texture_format.h"

using namespace PBKitPlusPlus;

namespace {

constexpr char kSubblockDxt1Test[] = "UnborderedSubblockDxt1";
constexpr char kOracleKind[] = "unbordered_subblock_cubemap_stride";
constexpr uint32_t kLogicalSizes[] = {1, 2};
constexpr uint32_t kLogicalSizeCount =
    sizeof(kLogicalSizes) / sizeof(kLogicalSizes[0]);
constexpr uint32_t kFaceCount = 6;
constexpr uint32_t kCellCount = kLogicalSizeCount * kFaceCount;
constexpr uint32_t kFaceStride = 128;
constexpr uint32_t kSamples = 8;
constexpr uint32_t kFnvOffset = 2166136261U;
constexpr uint32_t kFnvPrime = 16777619U;
constexpr uint32_t kExpectedSourceKat = 0xF13E387F;
constexpr uint32_t kTileLeft = 28;
constexpr uint32_t kTileTop = 68;
constexpr uint32_t kTileWidth = 84;
constexpr uint32_t kTileHeight = 76;

constexpr uint16_t kFaceColors[] = {
    0xF800, 0x07E0, 0x001F, 0xFFE0, 0xF81F, 0x07FF,
};

constexpr float kFaceDirections[kFaceCount][3] = {
    {1.0f, 0.0f, 0.0f},  {-1.0f, 0.0f, 0.0f},
    {0.0f, 1.0f, 0.0f},  {0.0f, -1.0f, 0.0f},
    {0.0f, 0.0f, 1.0f},  {0.0f, 0.0f, -1.0f},
};

uint32_t Fnv1a(const uint8_t *data, size_t size) {
  uint32_t hash = kFnvOffset;
  for (size_t i = 0; i < size; ++i) {
    hash = (hash ^ data[i]) * kFnvPrime;
  }
  return hash;
}

void WriteColorBlock(uint8_t *out, uint16_t color) {
  out[0] = static_cast<uint8_t>(color);
  out[1] = static_cast<uint8_t>(color >> 8);
  out[2] = 0;
  out[3] = 0;
  out[4] = 0;
  out[5] = 0;
  out[6] = 0;
  out[7] = 0;
}

uint32_t ReadRgb565(uint32_t x, uint32_t y, uint8_t *alpha) {
  const auto *base = reinterpret_cast<volatile const uint8_t *>(pb_back_buffer());
  const auto *pixel = base + y * pb_back_buffer_pitch() + x * sizeof(uint32_t);
  const uint32_t blue = pixel[0];
  const uint32_t green = pixel[1];
  const uint32_t red = pixel[2];
  *alpha = pixel[3];
  return ((red >> 3) << 11) | ((green >> 2) << 5) | (blue >> 3);
}

}  // namespace

TextureCubemapFallbackTests::TextureCubemapFallbackTests(
    TestHost &host, std::string output_dir, const Config &config)
    : TestSuite(host, std::move(output_dir), "TextureCubemapFallback", config) {
  tests_[kSubblockDxt1Test] = [this]() { RunSubblockDxt1(); };
}

void TextureCubemapFallbackTests::Initialize() {
  TestSuite::Initialize();
  host_.SetupFixedFunctionPassthrough();
  host_.SetBlend(false);
  host_.SetTextureStageEnabled(0, false);
  host_.SetTextureStageEnabled(1, false);
  host_.SetTextureStageEnabled(2, false);
  host_.SetTextureStageEnabled(3, false);
  host_.SetShaderStageProgram(TestHost::STAGE_NONE);
  host_.SetFinalCombiner0Just(TestHost::SRC_TEX0);
  host_.SetFinalCombiner1Just(TestHost::SRC_TEX0, true);
}

void TextureCubemapFallbackTests::Deinitialize() {
  host_.SetTextureStageEnabled(0, false);
  host_.SetShaderStageProgram(TestHost::STAGE_NONE);
  host_.SetupTextureStages();
}

void TextureCubemapFallbackTests::RunSubblockDxt1() {
  host_.SetupFixedFunctionPassthrough();
  host_.SetBlend(false);
  host_.SetFinalCombiner0Just(TestHost::SRC_TEX0);
  host_.SetFinalCombiner1Just(TestHost::SRC_TEX0, true);

  std::array<uint8_t, kFaceStride * kFaceCount> source{};
  for (uint32_t face = 0; face < kFaceCount; ++face) {
    WriteColorBlock(source.data() + face * kFaceStride, kFaceColors[face]);
  }
  const uint32_t source_kat = Fnv1a(source.data(), source.size());
  auto *texture = host_.GetTextureMemoryForStage(0);
  memcpy(texture, source.data(), source.size());

  auto &stage = host_.GetTextureStage(0);
  stage.SetFormat(GetTextureFormatInfo(
      NV097_SET_TEXTURE_FORMAT_COLOR_L_DXT1_A1R5G5B5));
  stage.SetMipMapLevels(1);
  stage.SetCubemapEnable(true);
  stage.SetBorderFromColor(true);
  stage.SetUWrap(TextureStage::WRAP_CLAMP_TO_EDGE, false);
  stage.SetVWrap(TextureStage::WRAP_CLAMP_TO_EDGE, false);
  stage.SetPWrap(TextureStage::WRAP_CLAMP_TO_EDGE, false);
  stage.SetLODClamp(0, 0);
  stage.SetFilter(0, TextureStage::K_QUINCUNX,
                  TextureStage::MIN_BOX_NEARESTLOD,
                  TextureStage::MAG_BOX_LOD0);
  host_.SetTextureStageEnabled(0, true);
  host_.SetShaderStageProgram(TestHost::STAGE_CUBE_MAP);

  auto draw = [this, &stage]() {
    host_.PrepareDraw(0xFF101010);
    for (uint32_t size_index = 0; size_index < kLogicalSizeCount;
         ++size_index) {
      stage.SetTextureDimensions(kLogicalSizes[size_index],
                                 kLogicalSizes[size_index]);
      host_.SetupTextureStages();
      for (uint32_t face = 0; face < kFaceCount; ++face) {
        const float left =
            static_cast<float>(kTileLeft + face * kTileWidth);
        const float top =
            static_cast<float>(kTileTop + size_index * kTileHeight);
        const float right = left + static_cast<float>(kTileWidth - 8);
        const float bottom = top + static_cast<float>(kTileHeight - 8);
        const float *direction = kFaceDirections[face];
        host_.Begin(TestHost::PRIMITIVE_QUADS);
        for (uint32_t vertex = 0; vertex < 4; ++vertex) {
          host_.SetTexCoord0(direction[0], direction[1], direction[2], 1.0f);
          host_.SetVertex(vertex == 0 || vertex == 3 ? left : right,
                          vertex < 2 ? top : bottom, 0.1f, 1.0f);
        }
        host_.End();
      }
    }
  };

  SetXemuPerfEventContext(0x1604U, source_kat);
  const auto results = Profile(kSubblockDxt1Test, kSamples, draw);
  host_.WaitForGpu();

  uint32_t failure_count = source_kat == kExpectedSourceKat ? 0U : 1U;
  uint32_t failure_mask = failure_count ? 1U << 31 : 0U;
  std::array<uint16_t, kCellCount> observed_cells{};
  std::array<uint8_t, kCellCount> observed_alpha{};
  for (uint32_t size_index = 0; size_index < kLogicalSizeCount;
       ++size_index) {
    for (uint32_t face = 0; face < kFaceCount; ++face) {
      const uint32_t cell = size_index * kFaceCount + face;
      const uint32_t x =
          kTileLeft + face * kTileWidth + (kTileWidth - 8) / 2;
      const uint32_t y =
          kTileTop + size_index * kTileHeight + (kTileHeight - 8) / 2;
      uint8_t alpha = 0;
      const uint32_t observed_rgb565 = ReadRgb565(x, y, &alpha);
      observed_cells[cell] = static_cast<uint16_t>(observed_rgb565);
      observed_alpha[cell] = alpha;
      if (observed_rgb565 != kFaceColors[face] || alpha != 0xFF) {
        ++failure_count;
        failure_mask |= 1U << cell;
      }
      PrintMsg("CUBEMAP_SUBBLOCK_ORACLE size=%lu face=%lu "
               "expected565=%04lx observed565=%04lx alpha=%02x\n",
               kLogicalSizes[size_index], face, kFaceColors[face],
               observed_rgb565, alpha);
    }
  }

  std::ostringstream metadata;
  metadata << "{\"schema_version\":1,";
  metadata << "\"kind\":\"" << kOracleKind << "\",";
  metadata << "\"oracle_status\":\""
           << (failure_count ? "FAIL" : "PASS") << "\",";
  metadata << "\"source_kat\":" << source_kat << ",";
  metadata << "\"failure_count\":" << failure_count << ",";
  metadata << "\"failure_mask\":" << failure_mask << ",";
  metadata << R"("faces":6,"logical_extents":[1,2],)";
  metadata << "\"face_stride\":" << kFaceStride << ",";
  metadata << "\"observed_rgb565\":[";
  for (uint32_t cell = 0; cell < kCellCount; ++cell) {
    if (cell) {
      metadata << ",";
    }
    metadata << observed_cells[cell];
  }
  metadata << "],\"observed_alpha\":[";
  for (uint32_t cell = 0; cell < kCellCount; ++cell) {
    if (cell) {
      metadata << ",";
    }
    metadata << static_cast<uint32_t>(observed_alpha[cell]);
  }
  metadata << "]}";

  if (failure_count) {
    EmitXemuPerfEvent(XemuPerfEventType::FAIL,
                      static_cast<uint16_t>(XemuPerfAssertion::GENERIC_ASSERT),
                      0, failure_mask);
  } else {
    EmitXemuPerfEvent(XemuPerfEventType::PASS, 0, source_kat, source_kat);
  }
  host_.FinishDraw(suite_name_, kSubblockDxt1Test, results, metadata.str());
  ClearXemuPerfEventContext();

  host_.SetTextureStageEnabled(0, false);
  host_.SetShaderStageProgram(TestHost::STAGE_NONE);
  host_.SetupTextureStages();
}
