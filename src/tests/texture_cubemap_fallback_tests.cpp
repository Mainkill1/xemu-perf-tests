#include "texture_cubemap_fallback_tests.h"

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstring>
#include <sstream>
#include <utility>
#include <vector>

#include <pbkit/pbkit.h>

#include "debug_output.h"
#include "test_host.h"
#include "texture_format.h"

using namespace PBKitPlusPlus;

namespace {

constexpr char kSubblockDxt1Test[] = "UnborderedSubblockDxt1";
constexpr char kBorderedRgba8Names[][24] = {
    "BorderedRgba8Size1", "BorderedRgba8Size2",
    "BorderedRgba8Size4", "BorderedRgba8Size8",
};
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
constexpr uint32_t kBorderedSourceKats[] = {
    0xAE745524, 0xCCA3A610, 0x32FF9E3C, 0xE80E51B4,
};
constexpr uint32_t kPaletteSourceKats[] = {
    0x5C491B36, 0x7A17D2A4, 0xC00D98F0, 0xDFF1316B
};
constexpr uint32_t kR6G5B5SourceKats[] = {
    0x7CB76AD2, 0x7D92DBC5, 0xA3451B31, 0x6B1248B9
};
constexpr uint32_t kTileLeft = 28;
constexpr uint32_t kTileTop = 68;
constexpr uint32_t kTileWidth = 84;
constexpr uint32_t kTileHeight = 76;
// left/top, right/top, left/bottom, right/bottom, and center.
constexpr uint32_t kBorderedSampleCoords[][2] = {
    {0, 0}, {1, 0}, {0, 1}, {1, 1}, {2, 2},
};
constexpr uint32_t kBorderedSamplesPerCell =
    sizeof(kBorderedSampleCoords) / sizeof(kBorderedSampleCoords[0]);

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

uint32_t Morton2D(uint32_t x, uint32_t y) {
  uint32_t index = 0;
  for (uint32_t bit = 0; bit < 4; ++bit) {
    index |= ((x >> bit) & 1U) << (2 * bit);
    index |= ((y >> bit) & 1U) << (2 * bit + 1);
  }
  return index;
}

uint16_t BorderedCellColor(uint32_t face, uint32_t level,
                           uint32_t x, uint32_t y) {
  const uint32_t red = 3 + face * 4;
  const uint32_t green = 5 + level * 14 + y;
  const uint32_t blue = 2 + x;
  return static_cast<uint16_t>((red << 11) | (green << 5) | blue);
}

uint32_t SampleTexel(uint32_t logical, uint32_t position) {
  return position == 0 ? 0 : position == 1 ? logical - 1 : logical / 2;
}

void CubeDirection(uint32_t face, float s, float t, float *out) {
  switch (face) {
    case 0: out[0] = 1;  out[1] = -t; out[2] = -s; break;
    case 1: out[0] = -1; out[1] = -t; out[2] = s;  break;
    case 2: out[0] = s;  out[1] = 1;  out[2] = t;  break;
    case 3: out[0] = s;  out[1] = -1; out[2] = -t; break;
    case 4: out[0] = s;  out[1] = -t; out[2] = 1;  break;
    default:out[0] = -s; out[1] = -t; out[2] = -1; break;
  }
}

uint32_t ExpandRgb565(uint16_t value) {
  const uint32_t red = (value >> 11) & 31;
  const uint32_t green = (value >> 5) & 63;
  const uint32_t blue = value & 31;
  return 0xFF000000U | ((red << 3 | red >> 2) << 16) |
         ((green << 2 | green >> 4) << 8) | (blue << 3 | blue >> 2);
}

// Positive signed known-answer pairs avoid the -128/-127 endpoint ambiguity.
// This xemu regression oracle does not establish original Xbox SNORM semantics.
constexpr uint16_t kSignedWords[] = {0x0000, 0xFC00, 0x01E0, 0x000F, 0x7CEB};
constexpr uint8_t kSignedRgb[][3] = {
    {0, 3, 3}, {127, 3, 3}, {0, 127, 3}, {0, 3, 127}, {62, 61, 94},
};

uint32_t ConvertedPattern(uint32_t face, uint32_t level,
                          uint32_t x, uint32_t y) {
  return (face * 37 + level * 19 + x * 7 + y * 11) % 251 + 1;
}

uint16_t PaletteColor(uint32_t index) {
  return static_cast<uint16_t>(((index % 29 + 1) << 11) |
                              ((index % 59 + 1) << 5) | (index % 29 + 1));
}

uint16_t ConvertedColor(uint32_t format, uint32_t face, uint32_t level,
                        uint32_t x, uint32_t y) {
  const uint32_t pattern = ConvertedPattern(face, level, x, y);
  if (format == NV097_SET_TEXTURE_FORMAT_COLOR_SZ_I8_A8R8G8B8) {
    return PaletteColor(pattern);
  }
  const auto &rgb = kSignedRgb[pattern % 5];
  const uint32_t red = (rgb[0] * 255 + 63) / 127;
  const uint32_t green = (rgb[1] * 255 + 63) / 127;
  const uint32_t blue = (rgb[2] * 255 + 63) / 127;
  return static_cast<uint16_t>(((red >> 3) << 11) |
                              ((green >> 2) << 5) | (blue >> 3));
}

bool SignedColorMatches(uint16_t observed, uint16_t expected) {
  for (const auto shift : {0U, 5U, 11U}) {
    const uint32_t mask = shift == 5 ? 63 : 31;
    const int a = (observed >> shift) & mask;
    const int b = (expected >> shift) & mask;
    if (std::abs(a - b) > 1) return false;
  }
  return true;
}

void FillConvertedSource(std::vector<uint8_t> *source, uint32_t size,
                         uint32_t levels, size_t stride, uint32_t format) {
  const uint32_t bytes =
      format == NV097_SET_TEXTURE_FORMAT_COLOR_SZ_I8_A8R8G8B8 ? 1 : 2;
  for (uint32_t face = 0; face < kFaceCount; ++face) {
    size_t offset = face * stride;
    for (uint32_t level = 0; level < levels; ++level) {
      const uint32_t stored = 16U >> level;
      const uint32_t logical = std::max(1U, size >> level);
      const uint32_t inset = level < 3 ? 4U >> level : 0;
      for (uint32_t y = 0; y < stored; ++y) {
        for (uint32_t x = 0; x < stored; ++x) {
          const bool inside = x >= inset && y >= inset &&
                              x < inset + logical && y < inset + logical;
          const uint32_t pattern = inside ?
              ConvertedPattern(face, level, x - inset, y - inset) : 0;
          auto *pixel = source->data() + offset + Morton2D(x, y) * bytes;
          if (bytes == 1) {
            *pixel = static_cast<uint8_t>(pattern);
          } else {
            const uint16_t word = inside ? kSignedWords[pattern % 5] : 0;
            std::memcpy(pixel, &word, 2);
          }
        }
      }
      offset += stored * stored * bytes;
    }
  }
}

size_t BorderedFaceStride(uint32_t levels, uint32_t pixel_bytes = 4) {
  uint32_t stored = 16;
  size_t bytes = 0;
  for (uint32_t level = 0; level < levels; ++level) {
    bytes += stored * stored * pixel_bytes;
    stored >>= 1;
  }
  return (bytes + 127) & ~size_t(127);
}

void FillBorderedRgba8Source(std::vector<uint8_t> *source,
                            uint32_t logical_size, uint32_t levels,
                            size_t face_stride) {
  for (uint32_t face = 0; face < kFaceCount; ++face) {
    size_t level_offset = face * face_stride;
    uint32_t stored = 16;
    for (uint32_t level = 0; level < levels; ++level) {
      const uint32_t logical = std::max(1U, logical_size >> level);
      const uint32_t border = level < 3 ? 4U >> level : 0;
      const uint32_t skip = std::min(border, stored - logical);
      for (uint32_t y = 0; y < stored; ++y) {
        for (uint32_t x = 0; x < stored; ++x) {
          const bool inside = x >= skip && y >= skip &&
                              x < skip + logical && y < skip + logical;
          const uint32_t argb = inside ?
              ExpandRgb565(BorderedCellColor(face, level,
                                             x - skip, y - skip)) : 0xFF000000U;
          const size_t offset = level_offset + Morton2D(x, y) * 4;
          std::memcpy(source->data() + offset, &argb, sizeof(argb));
        }
      }
      level_offset += stored * stored * 4;
      stored >>= 1;
    }
  }
}

}  // namespace

TextureCubemapFallbackTests::TextureCubemapFallbackTests(
    TestHost &host, std::string output_dir, const Config &config)
    : TestSuite(host, std::move(output_dir), "TextureCubemapFallback", config) {
  tests_[kSubblockDxt1Test] = [this]() { RunSubblockDxt1(); };
  for (uint32_t index = 0; index < 4; ++index) {
    const uint32_t size = 1U << index;
    const char *name = kBorderedRgba8Names[index];
    tests_[name] = [this, size, name]() {
      RunBorderedTexture(size, name, NV097_SET_TEXTURE_FORMAT_COLOR_SZ_A8R8G8B8);
    };
    const std::string palette = "BorderedPaletteSize" + std::to_string(size);
    tests_[palette] = [this, size, palette]() {
      RunBorderedTexture(size, palette.c_str(),
                         NV097_SET_TEXTURE_FORMAT_COLOR_SZ_I8_A8R8G8B8);
    };
    const std::string signed_rgb = "BorderedR6G5B5Size" + std::to_string(size);
    tests_[signed_rgb] = [this, size, signed_rgb]() {
      RunBorderedTexture(size, signed_rgb.c_str(),
                         NV097_SET_TEXTURE_FORMAT_COLOR_SZ_R6G5B5);
    };
  }
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

void TextureCubemapFallbackTests::RunBorderedTexture(
    uint32_t logical_size, const char *test_name, uint32_t format) {
  // FinishDraw's overlay changes the viewport and matrices. Restore this
  // workload's pixel-space transform for every case, not only suite init.
  host_.SetupFixedFunctionPassthrough();
  const uint32_t levels = 1 + (logical_size >= 2) +
                          (logical_size >= 4) + (logical_size >= 8);
  const bool rgba = format == NV097_SET_TEXTURE_FORMAT_COLOR_SZ_A8R8G8B8;
  const bool palette_format = format == NV097_SET_TEXTURE_FORMAT_COLOR_SZ_I8_A8R8G8B8;
  const size_t face_stride = BorderedFaceStride(levels, rgba ? 4 : palette_format ? 1 : 2);
  std::vector<uint8_t> source(face_stride * kFaceCount);
  if (rgba) {
    FillBorderedRgba8Source(&source, logical_size, levels, face_stride);
  } else {
    FillConvertedSource(&source, logical_size, levels, face_stride, format);
  }
  if (palette_format) {
    std::array<uint32_t, 256> palette{};
    palette[0] = 0xFF000000;
    for (uint32_t i = 1; i < palette.size(); ++i) {
      palette[i] = ExpandRgb565(PaletteColor(i));
    }
    host_.SetPalette(palette.data(), TestHost::PALETTE_256);
  }
  const uint32_t source_kat = Fnv1a(source.data(), source.size());
  std::memcpy(host_.GetTextureMemoryForStage(0), source.data(), source.size());

  auto &stage = host_.GetTextureStage(0);
  stage.SetFormat(GetTextureFormatInfo(format));
  stage.SetTextureDimensions(logical_size, logical_size);
  stage.SetMipMapLevels(levels);
  stage.SetCubemapEnable(true);
  stage.SetBorderFromColor(false);
  stage.SetUWrap(TextureStage::WRAP_CLAMP_TO_EDGE, false);
  stage.SetVWrap(TextureStage::WRAP_CLAMP_TO_EDGE, false);
  stage.SetPWrap(TextureStage::WRAP_CLAMP_TO_EDGE, false);
  stage.SetFilter(0, TextureStage::K_QUINCUNX,
                  TextureStage::MIN_BOX_NEARESTLOD,
                  TextureStage::MAG_BOX_LOD0);
  host_.SetTextureStageEnabled(0, true);
  host_.SetShaderStageProgram(TestHost::STAGE_CUBE_MAP);
  host_.SetFinalCombiner0Just(TestHost::SRC_TEX0);
  host_.SetFinalCombiner1Just(TestHost::SRC_TEX0, true);
  host_.SetBlend(false);

  auto draw = [this, &stage, levels]() {
    host_.PrepareDraw(0xFF101010);
    for (uint32_t level = 0; level < levels; ++level) {
      // xemu currently maps the raw clamp fields to integer GL base levels.
      // Select each uploaded level explicitly for this xemu-only oracle.
      stage.SetLODClamp(level, level);
      host_.SetupTextureStages();
      for (uint32_t face = 0; face < kFaceCount; ++face) {
        const float left = static_cast<float>(kTileLeft + face * kTileWidth);
        const float top = static_cast<float>(kTileTop + level * kTileHeight);
        const float right = left + static_cast<float>(kTileWidth - 8);
        const float bottom = top + static_cast<float>(kTileHeight - 8);
        host_.Begin(TestHost::PRIMITIVE_QUADS);
        for (uint32_t vertex = 0; vertex < 4; ++vertex) {
          float direction[3];
          CubeDirection(face, vertex == 0 || vertex == 3 ? -1.0f : 1.0f,
                        vertex < 2 ? -1.0f : 1.0f, direction);
          host_.SetTexCoord0(direction[0], direction[1], direction[2], 1.0f);
          host_.SetVertex(vertex == 0 || vertex == 3 ? left : right,
                          vertex < 2 ? top : bottom, 0.1f, 1.0f);
        }
        host_.End();
      }
    }
  };

  SetXemuPerfEventContext(0x1605U, source_kat);
  const auto results = Profile(test_name, kSamples, draw);
  host_.WaitForGpu();

  const uint32_t size_index = levels - 1;
  const uint32_t expected_kat = rgba ? kBorderedSourceKats[size_index] :
      palette_format ? kPaletteSourceKats[size_index] : kR6G5B5SourceKats[size_index];
  uint32_t failure_count = source_kat == expected_kat ? 0U : 1U;
  uint32_t failure_mask = failure_count ? 1U << 31 : 0U;
  std::vector<uint16_t> observed_cells(levels * kFaceCount *
                                      kBorderedSamplesPerCell);
  for (uint32_t level = 0; level < levels; ++level) {
    for (uint32_t face = 0; face < kFaceCount; ++face) {
      const uint32_t cell = level * kFaceCount + face;
      const uint32_t logical = std::max(1U, logical_size >> level);
      for (uint32_t sample = 0; sample < kBorderedSamplesPerCell; ++sample) {
        const uint32_t sample_x =
            SampleTexel(logical, kBorderedSampleCoords[sample][0]);
        const uint32_t sample_y =
            SampleTexel(logical, kBorderedSampleCoords[sample][1]);
        const uint32_t x = kTileLeft + face * kTileWidth +
            ((2 * sample_x + 1) * (kTileWidth - 8)) / (2 * logical);
        const uint32_t y = kTileTop + level * kTileHeight +
            ((2 * sample_y + 1) * (kTileHeight - 8)) / (2 * logical);
        uint8_t alpha = 0;
        const uint16_t observed =
            static_cast<uint16_t>(ReadRgb565(x, y, &alpha));
        const uint16_t expected = rgba ?
            BorderedCellColor(face, level, sample_x, sample_y) :
            ConvertedColor(format, face, level, sample_x, sample_y);
        observed_cells[cell * kBorderedSamplesPerCell + sample] = observed;
        const bool color_matches = !rgba && !palette_format ?
            SignedColorMatches(observed, expected) : observed == expected;
        if (!color_matches || alpha != 0xFF) {
          ++failure_count;
          failure_mask |= 1U << cell;
        }
        PrintMsg("CUBEMAP_BORDERED_ORACLE size=%lu level=%lu face=%lu "
                 "sample=%lu texel=(%lu,%lu) expected565=%04lx "
                 "observed565=%04lx alpha=%02x\n",
                 logical_size, level, face, sample, sample_x, sample_y,
                 expected, observed, alpha);
      }
    }
  }

  std::ostringstream metadata;
  metadata << "{\"schema_version\":1,";
  metadata << "\"kind\":\"bordered_uncompressed_cubemap_mips\",";
  metadata << "\"oracle_status\":\""
           << (failure_count ? "FAIL" : "PASS") << "\",";
  metadata << "\"source_kat\":" << source_kat << ",";
  metadata << "\"guest_format\":" << format << ",";
  metadata << "\"logical_size\":" << logical_size << ",";
  metadata << "\"levels\":" << levels << ",";
  metadata << "\"faces\":6,\"face_stride\":" << face_stride << ",";
  metadata << "\"samples_per_cell\":" << kBorderedSamplesPerCell << ",";
  metadata << "\"failure_count\":" << failure_count << ",";
  metadata << "\"failure_mask\":" << failure_mask << ",";
  metadata << "\"observed_rgb565\":[";
  for (size_t cell = 0; cell < observed_cells.size(); ++cell) {
    if (cell) {
      metadata << ",";
    }
    metadata << observed_cells[cell];
  }
  metadata << "]}";

  if (failure_count) {
    EmitXemuPerfEvent(XemuPerfEventType::FAIL,
                      static_cast<uint16_t>(XemuPerfAssertion::GENERIC_ASSERT),
                      0, failure_mask);
  } else {
    EmitXemuPerfEvent(XemuPerfEventType::PASS, 0, source_kat, source_kat);
  }
  host_.FinishDraw(suite_name_, test_name, results, metadata.str());
  ClearXemuPerfEventContext();

  stage.SetBorderFromColor(true);
  stage.SetLODClamp(0, 4095);
  host_.SetTextureStageEnabled(0, false);
  host_.SetShaderStageProgram(TestHost::STAGE_NONE);
  host_.SetupTextureStages();
}
