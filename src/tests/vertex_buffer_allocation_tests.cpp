#include "vertex_buffer_allocation_tests.h"

#include <sstream>

#include "debug_output.h"
#include "pushbuffer.h"
#include "shaders/passthrough_vertex_shader.h"
#include "test_host.h"
#include "vertex_buffer.h"

using namespace PBKitPlusPlus;

static constexpr char kTinyAllocationTest[] = "TinyAlloc";
static constexpr char kMixedVertexCountTest[] = "MixedVtxAlloc";
static constexpr char kDisjointSamePageTest[] =
    "XemuVertexRamDisjointSamePage";
static constexpr uint32_t kGeometrySeed = 0x5642414CU;
static constexpr uint32_t kOracleBackground = 0xFF182028U;
static constexpr uint32_t kOracleTileCount = 16;
static constexpr uint32_t kOracleTileColumns = 4;
static constexpr uint32_t kOracleTileWidth = 48;
static constexpr uint32_t kOracleTileHeight = 48;
static constexpr uint32_t kOracleTileGap = 16;
static constexpr uint32_t kOracleTileMarginX = 64;
static constexpr uint32_t kOracleTileMarginY = 48;

// Binary channel values make the guest-visible oracle exact on NV2A and host
// renderers without accepting rounding tolerances. The reverse-order second
// half makes stale/reordered tiles visible while primary colors catch channel
// swaps.
static constexpr uint32_t kOracleColors[kOracleTileCount] = {
    0xFF000000U, 0xFFFF0000U, 0xFF00FF00U, 0xFF0000FFU,
    0xFFFFFF00U, 0xFFFF00FFU, 0xFF00FFFFU, 0xFFFFFFFFU,
    0xFFFFFFFFU, 0xFF00FFFFU, 0xFFFF00FFU, 0xFFFFFF00U,
    0xFF0000FFU, 0xFF00FF00U, 0xFFFF0000U, 0xFF000000U,
};

static constexpr uint32_t HashUint32(uint32_t hash, uint32_t value) {
  for (uint32_t byte = 0; byte < 4; ++byte) {
    hash ^= (value >> (byte * 8)) & 0xFF;
    hash *= 16777619U;
  }
  return hash;
}

static constexpr uint32_t VertexAllocationOracleSourceKat() {
  uint32_t hash = 2166136261U;
  for (uint32_t tile = 0; tile < kOracleTileCount; ++tile) {
    hash = HashUint32(hash, tile);
    hash = HashUint32(hash, kOracleColors[tile]);
  }
  return hash;
}

static constexpr uint32_t kVertexAllocationOracleSourceKat =
    VertexAllocationOracleSourceKat();

class SpecifiedGenerator {
 public:
  explicit SpecifiedGenerator(uint32_t seed) : state_(seed) {}

  uint32_t Next() {
    state_ = state_ * 1664525U + 1013904223U;
    return state_;
  }

 private:
  uint32_t state_;
};

static constexpr uint32_t kMixedVertexBufferSizeMultiframeArrays[] = {
    0x2a12, 0x17cdc, 0xb43,  0x1f5,  0x1522, 0x1a0,  0x1292, 0x123,
    0x3c,   0x1bde,  0x1b31, 0x1a2e, 0x1d00, 0x1FFE, 0x12a7, 0x9ef,
};

static constexpr uint32_t kMixedVertexBufferSizeMultiframeInlineArrays[] = {
    0x212, 0x1dc, 0xb43, 0x1f5, 0x122, 0x1a0, 0x122, 0x123, 0x3c, 0x1be, 0xb31, 0xa2e, 0xd00, 0x1FE, 0x127, 0x9ef,
};

static constexpr uint32_t kMixedVertexBufferSizeMultiframeInlineBuffers[] = {
    0x212, 0x1dc, 0x443, 0x1f5, 0x122, 0x1a0, 0x122, 0x123, 0x3c, 0x1be, 0x231, 0x62e, 0x500, 0xFE, 0x127, 0x4ef,
};

static constexpr uint32_t kMixedVertexBufferSizeMultiframeInlineElements[] = {
    0x2a12, 0x17cdc, 0xb43,  0x1f5,  0x1522, 0x1a0,  0x1292, 0x123,
    0x3c,   0x1bde,  0x1b31, 0x1a2e, 0x1d00, 0x1FFE, 0x12a7, 0x9ef,
};

static constexpr const uint32_t *GetMixedVertexBufferSizesMultiframe(VertexBufferAllocationTests::DrawMode mode) {
  switch (mode) {
    case VertexBufferAllocationTests::DrawMode::DRAW_ARRAYS:
      return kMixedVertexBufferSizeMultiframeArrays;
    case VertexBufferAllocationTests::DrawMode::DRAW_INLINE_BUFFERS:
      return kMixedVertexBufferSizeMultiframeInlineBuffers;
    case VertexBufferAllocationTests::DrawMode::DRAW_INLINE_ARRAYS:
      return kMixedVertexBufferSizeMultiframeInlineArrays;
    case VertexBufferAllocationTests::DrawMode::DRAW_INLINE_ELEMENTS:
      return kMixedVertexBufferSizeMultiframeInlineElements;
  }
  return nullptr;
}

static constexpr uint32_t kMixedVertexBufferSizesSingleFrame[] = {
    0x2a12, 0x17cdc, 0xcb43,  0x91f5,  0x15225, 0x14a0f, 0x12921, 0x12327,
    0x3c,   0x1bde6, 0x1b31e, 0x1a2e3, 0x1d001, 0x1FFE0, 0x12a7a, 0x9ef7,
};

static uint32_t kVertexAttributes =
    TestHost::POSITION | TestHost::DIFFUSE | TestHost::SPECULAR | TestHost::WEIGHT | TestHost::TEXCOORD0;

// Keep in sync with the size required for kVertexAttributes
// 4 position, 1 weight, 4 diffuse, 4 specular, 2 texcoord0
static constexpr uint32_t kArrayEntriesPerVertex = 15;

static constexpr uint32_t kSmallestVertexBufferSize = kArrayEntriesPerVertex * 4;

static std::string MakeTestName(const std::string &prefix, VertexBufferAllocationTests::DrawMode draw_mode) {
  std::string ret = prefix;

  switch (draw_mode) {
    case VertexBufferAllocationTests::DrawMode::DRAW_ARRAYS:
      ret += "-arrays";
      break;
    case VertexBufferAllocationTests::DrawMode::DRAW_INLINE_BUFFERS:
      ret += "-inlinebuffers";
      break;
    case VertexBufferAllocationTests::DrawMode::DRAW_INLINE_ARRAYS:
      ret += "-inlinearrays";
      break;
    case VertexBufferAllocationTests::DrawMode::DRAW_INLINE_ELEMENTS:
      ret += "-inlineelements";
      break;
  }

  return ret;
}

/**
 * Initializes the test suite and creates test cases.
 *
 * @tc MixedVtxAlloc-arrays
 *  Tests NV097_DRAW_ARRAYS with multiple successive draws using a variety of different vertex counts.
 *
 * @tc MixedVtxAlloc-inlinebuffers
 *  Tests immediate mode (e.g., NV097_SET_VERTEX3F) with multiple successive draws using a variety of different vertex
 *  counts.
 *
 * @tc MixedVtxAlloc-inlinearrays
 *  Tests NV097_INLINE_ARRAY with multiple successive draws using a variety of different vertex counts.
 *
 * @tc MixedVtxAlloc-inlineelements
 *  Tests NV097_ARRAY_ELEMENT16 / NV097_ARRAY_ELEMENT32 with multiple successive draws using a variety of different
 *  vertex counts.
 *
 * @tc TinyAlloc-arrays
 *  Tests NV097_DRAW_ARRAYS with a large number of single quad draws.
 *
 * @tc TinyAlloc-inlinebuffers
 *  Tests immediate mode (e.g., NV097_SET_VERTEX3F) with a large number of single quad draws.
 *
 * @tc TinyAlloc-inlinearrays
 *  Tests NV097_INLINE_ARRAY with a large number of single quad draws.
 *
 * @tc TinyAlloc-inlineelements
 *  Tests NV097_ARRAY_ELEMENT16 / NV097_ARRAY_ELEMENT32 with a large number of single quad draws.
 */
VertexBufferAllocationTests::VertexBufferAllocationTests(TestHost &host, std::string output_dir, const Config &config)
    : TestSuite(host, std::move(output_dir), "Vertex buffer allocation", config) {
  for (auto draw_mode : {DrawMode::DRAW_ARRAYS, DrawMode::DRAW_INLINE_BUFFERS, DrawMode::DRAW_INLINE_ARRAYS,
                         DrawMode::DRAW_INLINE_ELEMENTS}) {
    auto name = MakeTestName(kMixedVertexCountTest, draw_mode);
    tests_[name] = [this, name, draw_mode]() { TestMixedSizes(name, draw_mode); };

    name = MakeTestName(kTinyAllocationTest, draw_mode);
    tests_[name] = [this, name, draw_mode]() { TestTinyAllocations(name, draw_mode); };
  }
  tests_[kDisjointSamePageTest] =
      [this]() { TestDisjointSamePageVertexUpdates(); };
}

static uint32_t PackField(uint32_t mask, uint32_t value) {
  return (value << (__builtin_ffs(mask) - 1)) & mask;
}

static constexpr bool DrawModeRequiresRetainedVertexRam(
    VertexBufferAllocationTests::DrawMode mode) {
  return mode == VertexBufferAllocationTests::DrawMode::DRAW_ARRAYS ||
         mode == VertexBufferAllocationTests::DrawMode::DRAW_INLINE_ELEMENTS;
}

static constexpr const char *DrawModeName(
    VertexBufferAllocationTests::DrawMode mode) {
  switch (mode) {
    case VertexBufferAllocationTests::DrawMode::DRAW_ARRAYS:
      return "arrays";
    case VertexBufferAllocationTests::DrawMode::DRAW_INLINE_BUFFERS:
      return "inlinebuffers";
    case VertexBufferAllocationTests::DrawMode::DRAW_INLINE_ARRAYS:
      return "inlinearrays";
    case VertexBufferAllocationTests::DrawMode::DRAW_INLINE_ELEMENTS:
      return "inlineelements";
  }
  return "unknown";
}

void VertexBufferAllocationTests::TestDisjointSamePageVertexUpdates() {
  static constexpr uint32_t kIterations = 10;
  static constexpr uint32_t kDraws = 1024;
  static constexpr uint32_t kVerticesPerDraw = 3;
  static constexpr uint32_t kAttributes = TestHost::POSITION | TestHost::DIFFUSE;

  auto shader = std::make_shared<PassthroughVertexShader>();
  host_.SetVertexShaderProgram(shader);
  host_.PrepareDraw(0xFF101010);

  auto vertex_buffer = host_.AllocateVertexBuffer(kDraws * kVerticesPerDraw);
  vertex_buffer->SetPositionIncludesW(true);

  auto results = Profile(kDisjointSamePageTest, kIterations,
                         [this, vertex_buffer] {
    for (uint32_t draw = 0; draw < kDraws; ++draw) {
      uint32_t first_vertex = draw * kVerticesPerDraw;
      auto vertex = vertex_buffer->Lock() + first_vertex;

      float left = static_cast<float>((draw % 32) * 20);
      float top = static_cast<float>((draw / 32) * 15);
      float red = static_cast<float>((draw * 37) & 0xFF) / 255.0f;
      float green = static_cast<float>((draw * 73) & 0xFF) / 255.0f;
      float blue = static_cast<float>((draw * 109) & 0xFF) / 255.0f;

      vertex->SetPosition(left, top, 1.0f);
      vertex->SetDiffuse(red, green, blue, 1.0f);
      ++vertex;
      vertex->SetPosition(left + 12.0f, top, 1.0f);
      vertex->SetDiffuse(red, green, blue, 1.0f);
      ++vertex;
      vertex->SetPosition(left + 6.0f, top + 10.0f, 1.0f);
      vertex->SetDiffuse(red, green, blue, 1.0f);
      vertex_buffer->Unlock();

      host_.SetVertexBufferAttributes(kAttributes);
      Pushbuffer::Begin();
      Pushbuffer::Push(NV097_SET_BEGIN_END,
                       NV097_SET_BEGIN_END_OP_TRIANGLES);
      Pushbuffer::Push(
          NV097_DRAW_ARRAYS,
          PackField(NV097_DRAW_ARRAYS_COUNT, kVerticesPerDraw - 1) |
              PackField(NV097_DRAW_ARRAYS_START_INDEX, first_vertex));
      Pushbuffer::Push(NV097_SET_BEGIN_END, NV097_SET_BEGIN_END_OP_END);
      Pushbuffer::End();
    }
  });

  host_.FinishDraw(suite_name_, kDisjointSamePageTest, results);
}

static std::shared_ptr<VertexBuffer> CreateGeometry(
    TestHost &host, std::vector<uint32_t> &index_buffer,
    uint32_t target_array_entries, uint32_t seed) {
  index_buffer.clear();

  static constexpr float kQuadSize = 16.f;
  static constexpr float kQuadZ = 0.f;

  const uint32_t target_quads = target_array_entries / (4 * kArrayEntriesPerVertex);
  ASSERT(target_quads > 0);

  float red = 0.f;
  float green = 0.5f;
  float blue = 0.75f;

  static constexpr float kRedInc = 0.03f;
  static constexpr float kGreenInc = 0.05f;
  static constexpr float kBlueInc = 0.01f;

  auto increment_colors = [&red, &green, &blue]() {
    red += kRedInc;
    green += kGreenInc;
    blue += kBlueInc;

    if (red > 1.f) {
      red -= 1.f;
    }
    if (green > 1.f) {
      green -= 1.f;
    }
    if (blue > 1.f) {
      blue -= 1.f;
    }
  };

  auto vertex_buffer = host.AllocateVertexBuffer(target_quads * 4);
  vertex_buffer->SetPositionIncludesW(true);
  auto vertex = vertex_buffer->Lock();
  auto add_quad = [&vertex, &red, &green, &blue, &increment_colors](float left, float top, float alpha) {
    vertex->SetPosition(left, top, kQuadZ);
    vertex->SetDiffuse(red, green, blue, alpha);
    increment_colors();
    vertex->SetSpecular(red, green, blue, alpha);
    increment_colors();
    vertex->SetWeight(0.f);
    vertex->SetTexCoord0(0.f, 0.f);
    ++vertex;

    vertex->SetPosition(left + kQuadSize, top, kQuadZ);
    vertex->SetDiffuse(red, green, blue, alpha);
    increment_colors();
    vertex->SetSpecular(red, green, blue, alpha);
    increment_colors();
    vertex->SetWeight(1.f);
    vertex->SetTexCoord0(1.f, 0.f);
    ++vertex;

    vertex->SetPosition(left + kQuadSize, top + kQuadSize, kQuadZ);
    vertex->SetDiffuse(red, green, blue, alpha);
    increment_colors();
    vertex->SetSpecular(red, green, blue, alpha);
    increment_colors();
    vertex->SetWeight(2.f);
    vertex->SetTexCoord0(1.f, 1.f);
    ++vertex;

    vertex->SetPosition(left, top + kQuadSize, kQuadZ);
    vertex->SetDiffuse(red, green, blue, alpha);
    increment_colors();
    vertex->SetSpecular(red, green, blue, alpha);
    increment_colors();
    vertex->SetWeight(3.f);
    vertex->SetTexCoord0(0.f, 1.f);
    ++vertex;
  };

  uint32_t vertex_index = 0;
  const auto x_range = static_cast<uint32_t>(host.GetFramebufferWidth() - kQuadSize);
  const auto y_range = static_cast<uint32_t>(host.GetFramebufferHeight() - kQuadSize);
  SpecifiedGenerator generator(seed);
  float alpha = 1.f;
  for (auto quad_count = 0; quad_count < target_quads; ++quad_count) {
    auto left = static_cast<float>(generator.Next() % x_range);
    auto top = static_cast<float>(generator.Next() % y_range);
    add_quad(left, top, alpha);
    index_buffer.emplace_back(vertex_index++);
    index_buffer.emplace_back(vertex_index++);
    index_buffer.emplace_back(vertex_index++);
    index_buffer.emplace_back(vertex_index++);
  }

  vertex_buffer->Unlock();
  return vertex_buffer;
}

void VertexBufferAllocationTests::Initialize() {
  TestSuite::Initialize();
}

void VertexBufferAllocationTests::Deinitialize() {
  host_.ClearVertexBuffer();
  TestSuite::Deinitialize();
}

void VertexBufferAllocationTests::TestMixedSizes(const std::string &name, DrawMode draw_mode) {
  TestSuite::Initialize();
  auto shader = std::make_shared<PassthroughVertexShader>();
  host_.SetVertexShaderProgram(shader);

  static constexpr uint32_t kNumProfilingRuns = 10;

  static constexpr uint32_t kBackgroundColor = 0xFF444444;
  host_.PrepareDraw(kBackgroundColor);

  static constexpr auto kPrimitive = TestHost::PRIMITIVE_QUADS;

  TestHost::ProfileResults results{};
  const auto vertex_counts =
      host_.GetSaveResults() ? kMixedVertexBufferSizesSingleFrame : GetMixedVertexBufferSizesMultiframe(draw_mode);

  uint64_t embedded_completion_wait_us = 0;
  uint32_t embedded_completion_wait_calls = 0;
  results = Profile(name, kNumProfilingRuns,
                    [this, vertex_counts, draw_mode,
                     &embedded_completion_wait_us,
                     &embedded_completion_wait_calls] {
    std::vector<std::shared_ptr<VertexBuffer>> retained_buffers;
    retained_buffers.reserve(std::size(kMixedVertexBufferSizesSingleFrame));
    for (uint32_t idx = 0;
         idx < std::size(kMixedVertexBufferSizesSingleFrame); ++idx) {
      const uint32_t vertex_count = vertex_counts[idx];
      std::vector<uint32_t> index_buffer;
      auto vertex_buffer = CreateGeometry(
          host_, index_buffer, vertex_count,
          kGeometrySeed ^ (static_cast<uint32_t>(draw_mode) << 24) ^ idx);
      if (DrawModeRequiresRetainedVertexRam(draw_mode)) {
        retained_buffers.emplace_back(vertex_buffer);
      }
      switch (draw_mode) {
        case DrawMode::DRAW_ARRAYS:
          host_.DrawArrays(kVertexAttributes, kPrimitive);
          break;
        case DrawMode::DRAW_INLINE_BUFFERS:
          host_.DrawInlineBuffer(kVertexAttributes, kPrimitive);
          break;
        case DrawMode::DRAW_INLINE_ARRAYS:
          host_.DrawInlineArray(kVertexAttributes, kPrimitive);
          break;
        case DrawMode::DRAW_INLINE_ELEMENTS:
          host_.DrawInlineElements16(index_buffer, kVertexAttributes,
                                     kPrimitive);
          break;
      }
    }

    LARGE_INTEGER wait_start;
    QueryPerformanceCounter(&wait_start);
    host_.WaitForGpu();
    embedded_completion_wait_us += host_.GetMicrosecondsSince(wait_start);
    ++embedded_completion_wait_calls;
    retained_buffers.clear();
    host_.ClearVertexBuffer();
  });

  uint32_t work_checksum = HashUint32(
      2166136261U, static_cast<uint32_t>(draw_mode));
  work_checksum = HashUint32(work_checksum, kGeometrySeed);
  work_checksum = HashUint32(work_checksum, results.iterations);
  work_checksum = HashUint32(
      work_checksum, std::size(kMixedVertexBufferSizesSingleFrame));
  for (uint32_t idx = 0;
       idx < std::size(kMixedVertexBufferSizesSingleFrame); ++idx) {
    work_checksum = HashUint32(work_checksum, vertex_counts[idx]);
  }
  FinishProfileWithOracle(name, draw_mode, results, work_checksum,
                          embedded_completion_wait_us,
                          embedded_completion_wait_calls);
}

static constexpr uint32_t GetTinyAllocDrawsMultiframe(VertexBufferAllocationTests::DrawMode mode) {
  switch (mode) {
    case VertexBufferAllocationTests::DrawMode::DRAW_ARRAYS:
    case VertexBufferAllocationTests::DrawMode::DRAW_INLINE_ELEMENTS:
      return 80;
    case VertexBufferAllocationTests::DrawMode::DRAW_INLINE_BUFFERS:
    case VertexBufferAllocationTests::DrawMode::DRAW_INLINE_ARRAYS:
      return 70;
  }
  return 0;
}

void VertexBufferAllocationTests::TestTinyAllocations(const std::string &name, DrawMode draw_mode) {
  TestSuite::Initialize();
  auto shader = std::make_shared<PassthroughVertexShader>();
  host_.SetVertexShaderProgram(shader);

  static constexpr uint32_t kNumProfilingRuns = 10;
  static constexpr uint32_t kNumDrawsSingleFrame = 500;
  static constexpr uint32_t kBackgroundColor = 0xFF333333;
  host_.PrepareDraw(kBackgroundColor);

  static constexpr auto kPrimitive = TestHost::PRIMITIVE_QUADS;

  TestHost::ProfileResults results{};
  const uint32_t num_draws = host_.GetSaveResults() ? kNumDrawsSingleFrame : GetTinyAllocDrawsMultiframe(draw_mode);
  uint64_t embedded_completion_wait_us = 0;
  uint32_t embedded_completion_wait_calls = 0;
  results = Profile(name, kNumProfilingRuns,
                    [this, num_draws, draw_mode,
                     &embedded_completion_wait_us,
                     &embedded_completion_wait_calls] {
    std::vector<std::shared_ptr<VertexBuffer>> retained_buffers;
    if (DrawModeRequiresRetainedVertexRam(draw_mode)) {
      retained_buffers.reserve(num_draws);
    }
    for (uint32_t draw = 0; draw < num_draws; ++draw) {
      std::vector<uint32_t> index_buffer;
      auto vertex_buffer = CreateGeometry(
          host_, index_buffer, kSmallestVertexBufferSize,
          kGeometrySeed ^ (static_cast<uint32_t>(draw_mode) << 24) ^ draw);
      if (DrawModeRequiresRetainedVertexRam(draw_mode)) {
        retained_buffers.emplace_back(vertex_buffer);
      }
      switch (draw_mode) {
        case DrawMode::DRAW_ARRAYS:
          host_.DrawArrays(kVertexAttributes, kPrimitive);
          break;
        case DrawMode::DRAW_INLINE_BUFFERS:
          host_.DrawInlineBuffer(kVertexAttributes, kPrimitive);
          break;
        case DrawMode::DRAW_INLINE_ARRAYS:
          host_.DrawInlineArray(kVertexAttributes, kPrimitive);
          break;
        case DrawMode::DRAW_INLINE_ELEMENTS:
          host_.DrawInlineElements16(index_buffer, kVertexAttributes,
                                     kPrimitive);
          break;
      }
    }

    LARGE_INTEGER wait_start;
    QueryPerformanceCounter(&wait_start);
    host_.WaitForGpu();
    embedded_completion_wait_us += host_.GetMicrosecondsSince(wait_start);
    ++embedded_completion_wait_calls;
    retained_buffers.clear();
    host_.ClearVertexBuffer();
  });

  uint32_t work_checksum = HashUint32(
      2166136261U, static_cast<uint32_t>(draw_mode));
  work_checksum = HashUint32(work_checksum, kGeometrySeed);
  work_checksum = HashUint32(work_checksum, results.iterations);
  work_checksum = HashUint32(work_checksum, num_draws);
  work_checksum = HashUint32(work_checksum, kSmallestVertexBufferSize);
  FinishProfileWithOracle(name, draw_mode, results, work_checksum,
                          embedded_completion_wait_us,
                          embedded_completion_wait_calls);
}

static std::shared_ptr<VertexBuffer> CreateVertexAllocationOracleGeometry(
    TestHost &host, std::vector<uint32_t> &index_buffer) {
  index_buffer.clear();
  auto vertex_buffer = host.AllocateVertexBuffer(kOracleTileCount * 4);
  vertex_buffer->SetPositionIncludesW(true);
  auto vertex = vertex_buffer->Lock();

  for (uint32_t tile = 0; tile < kOracleTileCount; ++tile) {
    const uint32_t column = tile % kOracleTileColumns;
    const uint32_t row = tile / kOracleTileColumns;
    const float left = static_cast<float>(
        kOracleTileMarginX + column * (kOracleTileWidth + kOracleTileGap));
    const float top = static_cast<float>(
        kOracleTileMarginY + row * (kOracleTileHeight + kOracleTileGap));
    const float right = left + static_cast<float>(kOracleTileWidth);
    const float bottom = top + static_cast<float>(kOracleTileHeight);
    const uint32_t color = kOracleColors[tile];
    const float red = static_cast<float>((color >> 16) & 0xFF) / 255.0f;
    const float green = static_cast<float>((color >> 8) & 0xFF) / 255.0f;
    const float blue = static_cast<float>(color & 0xFF) / 255.0f;

    const float positions[4][2] = {
        {left, top}, {right, top}, {right, bottom}, {left, bottom}};
    for (uint32_t corner = 0; corner < 4; ++corner) {
      vertex->SetPosition(positions[corner][0], positions[corner][1], 0.0f);
      vertex->SetDiffuse(red, green, blue, 1.0f);
      vertex->SetSpecular(0.0f, 0.0f, 0.0f, 0.0f);
      vertex->SetWeight(0.0f);
      vertex->SetTexCoord0(0.0f, 0.0f);
      index_buffer.emplace_back(tile * 4 + corner);
      ++vertex;
    }
  }
  vertex_buffer->Unlock();
  return vertex_buffer;
}

static void DrawVertexAllocationOracle(
    TestHost &host, VertexBufferAllocationTests::DrawMode draw_mode,
    const std::vector<uint32_t> &index_buffer) {
  switch (draw_mode) {
    case VertexBufferAllocationTests::DrawMode::DRAW_ARRAYS:
      host.DrawArrays(kVertexAttributes, TestHost::PRIMITIVE_QUADS);
      break;
    case VertexBufferAllocationTests::DrawMode::DRAW_INLINE_BUFFERS:
      host.DrawInlineBuffer(kVertexAttributes, TestHost::PRIMITIVE_QUADS);
      break;
    case VertexBufferAllocationTests::DrawMode::DRAW_INLINE_ARRAYS:
      host.DrawInlineArray(kVertexAttributes, TestHost::PRIMITIVE_QUADS);
      break;
    case VertexBufferAllocationTests::DrawMode::DRAW_INLINE_ELEMENTS:
      host.DrawInlineElements16(index_buffer, kVertexAttributes,
                                TestHost::PRIMITIVE_QUADS);
      break;
  }
}

static uint32_t ValidateVertexAllocationOracle(TestHost &host,
                                               uint32_t assertion_base) {
  const auto *const base =
      reinterpret_cast<volatile const uint8_t *>(pb_back_buffer());
  const uint32_t pitch = pb_back_buffer_pitch();
  uint32_t observed_kat = 2166136261U;
  for (uint32_t tile = 0; tile < kOracleTileCount; ++tile) {
    const uint32_t column = tile % kOracleTileColumns;
    const uint32_t row = tile / kOracleTileColumns;
    const uint32_t x = kOracleTileMarginX +
                       column * (kOracleTileWidth + kOracleTileGap) +
                       kOracleTileWidth / 2;
    const uint32_t y = kOracleTileMarginY +
                       row * (kOracleTileHeight + kOracleTileGap) +
                       kOracleTileHeight / 2;
    const auto *const pixel = base + y * pitch + x * sizeof(uint32_t);
    const uint32_t observed_argb = (static_cast<uint32_t>(pixel[3]) << 24) |
                                   (static_cast<uint32_t>(pixel[2]) << 16) |
                                   (static_cast<uint32_t>(pixel[1]) << 8) |
                                   static_cast<uint32_t>(pixel[0]);
    PrintMsg("VERTEX_ALLOCATION_TILE tile=%lu x=%lu y=%lu expected=%08lx "
             "observed=%08lx\n",
             tile, x, y, kOracleColors[tile], observed_argb);
    AssertXemuPerfEqual(
        kOracleColors[tile], observed_argb,
        static_cast<XemuPerfAssertion>(assertion_base + tile),
        "vertex allocation oracle tile center matches exact ARGB", __FILE__,
        __LINE__);
    observed_kat = HashUint32(observed_kat, tile);
    observed_kat = HashUint32(observed_kat, observed_argb);
  }
  AssertXemuPerfEqual(
      kVertexAllocationOracleSourceKat, observed_kat,
      static_cast<XemuPerfAssertion>(assertion_base + kOracleTileCount),
      "vertex allocation ordered tile KAT matches source", __FILE__,
      __LINE__);
  return observed_kat;
}

void VertexBufferAllocationTests::FinishProfileWithOracle(
    const std::string &name, DrawMode draw_mode,
    const TestHost::ProfileResults &results, uint32_t work_checksum,
    uint64_t embedded_completion_wait_us,
    uint32_t embedded_completion_wait_calls) {
  const uint32_t expected_wait_calls =
      results.iterations + results.warmup_iterations;
  ASSERT(embedded_completion_wait_calls == expected_wait_calls);

  // All measured work is complete before the correctness scene owns state and
  // framebuffer contents. The embedded per-body completion is inside raw
  // timing; this second wait is an untimed correctness barrier only.
  host_.WaitForGpu();
  TestSuite::Initialize();
  host_.ClearVertexBuffer();
  host_.SetupFixedFunctionPassthrough();
  auto shader = std::make_shared<PassthroughVertexShader>();
  host_.SetVertexShaderProgram(shader);
  host_.SetBlend(false);
  host_.SetFinalCombiner0Just(TestHost::SRC_DIFFUSE);
  host_.SetFinalCombiner1Just(TestHost::SRC_ZERO, true, true);
  host_.PrepareDraw(kOracleBackground);

  std::vector<uint32_t> index_buffer;
  auto oracle_vertex_buffer =
      CreateVertexAllocationOracleGeometry(host_, index_buffer);
  DrawVertexAllocationOracle(host_, draw_mode, index_buffer);
  host_.WaitForGpu();
  const uint32_t assertion_base =
      0x200U + static_cast<uint32_t>(draw_mode) * 0x20U;
  SetXemuPerfEventContext(0xB000U + static_cast<uint32_t>(draw_mode),
                          kVertexAllocationOracleSourceKat);
  const uint32_t tile_center_kat =
      ValidateVertexAllocationOracle(host_, assertion_base);
  EmitXemuPerfEvent(XemuPerfEventType::PASS, 0,
                    kVertexAllocationOracleSourceKat, tile_center_kat);
  oracle_vertex_buffer.reset();
  host_.ClearVertexBuffer();

  char work_checksum_string[9] = {};
  char result_checksum_string[9] = {};
  char tile_center_kat_string[9] = {};
  snprintf(work_checksum_string, sizeof(work_checksum_string), "%08lx",
           work_checksum);
  snprintf(result_checksum_string, sizeof(result_checksum_string), "%08lx",
           kVertexAllocationOracleSourceKat);
  snprintf(tile_center_kat_string, sizeof(tile_center_kat_string), "%08lx",
           tile_center_kat);

  std::ostringstream metadata;
  metadata << "{";
  metadata << "\"schema_version\":1,";
  metadata << "\"kind\":\"vertex_allocation_validity\",";
  metadata << "\"draw_mode\":\"" << DrawModeName(draw_mode) << "\",";
  metadata << "\"embedded_completion\":{";
  metadata << "\"scope\":\"per_body\",";
  metadata << "\"included_in_raw_timing\":true,";
  metadata << "\"wait_calls_total\":" << embedded_completion_wait_calls
           << ",";
  metadata << "\"wait_calls_measured\":" << results.iterations << ",";
  metadata << "\"wait_calls_warmup\":" << results.warmup_iterations << ",";
  metadata << "\"wait_us_total\":" << embedded_completion_wait_us;
  metadata << "},";
  metadata << "\"retained_vertex_ram\":"
           << (DrawModeRequiresRetainedVertexRam(draw_mode) ? "true" : "false")
           << ",";
  metadata << "\"work_checksum\":\"" << work_checksum_string << "\",";
  metadata << "\"result_checksum\":\"" << result_checksum_string << "\",";
  metadata << "\"tile_center_kat\":\"" << tile_center_kat_string << "\"";
  metadata << "}";
  host_.FinishDraw(suite_name_, name, results, metadata.str());
  ClearXemuPerfEventContext();
}
