#include "query_pressure_tests.h"

#include <sstream>
#include <vector>

#include <pbkit/nv_regs.h>
#include <pbkit/pbkit.h>
#include <pbkit/pbkit_pushbuffer.h>

#include "debug_output.h"
#include "shaders/passthrough_vertex_shader.h"
#include "test_host.h"
#include "vertex_buffer.h"

using namespace PBKitPlusPlus;

// Restored from Mainkill1's historical dda08125e0e74fe8400614da096a6a3b2c3fa7ac
// query-pressure fixture. The recipe and known answers are preserved verbatim.
static constexpr char kName[] = "query.repeated-page-4097";
static constexpr uint32_t kDraws = 4097;
static constexpr uint32_t kTiles = 512;
static constexpr uint32_t kExpectedSamples = (kDraws / 2) * (64 + 256) + 64;
static constexpr uint32_t kSentinel = 0xDEADBEEF;
static constexpr uint32_t kTimeoutUs = 5000000;
static constexpr uint32_t kReportContext = 23;
static constexpr uint32_t kColors[] = {0xFFFF0000, 0xFF00FF00, 0xFF0000FF};

// Hash the little-endian recipe words before submitting any draw.
static constexpr uint32_t kExpectedInputHash = 0xC4DDD0FB;

struct DrawInput {
  uint32_t left;
  uint32_t top;
  uint32_t extent;
  uint32_t color;
};

struct alignas(16) ReportRecord {
  volatile uint64_t timestamp;
  volatile uint32_t value;
  volatile uint32_t done;
};

static_assert(sizeof(ReportRecord) == 16);
static_assert(kExpectedSamples == 655424);

static uint32_t HashWord(uint32_t hash, uint32_t word) {
  for (uint32_t shift = 0; shift < 32; shift += 8) {
    hash = (hash ^ ((word >> shift) & 255)) * 16777619U;
  }
  return hash;
}

static void Method(uint32_t method, uint32_t parameter) {
  Pushbuffer::Begin();
  Pushbuffer::Push(method, parameter);
  Pushbuffer::End();
}

static bool DrainGuestFifo(TestHost &host) {
  LARGE_INTEGER start;
  QueryPerformanceCounter(&start);
  while (pb_busy()) {
    if (host.GetMicrosecondsSince(start) >= kTimeoutUs) {
      return false;
    }
    Sleep(0);
  }
  return true;
}

static void Check(uint32_t expected, uint32_t observed, uint32_t assertion,
                  const char *description) {
  AssertXemuPerfEqual(expected, observed,
                      static_cast<XemuPerfAssertion>(0xB400 + assertion),
                      description, __FILE__, __LINE__);
}

QueryPressureTests::QueryPressureTests(TestHost &host, std::string output_dir,
                                       const Config &config)
    : TestSuite(host, std::move(output_dir), "QueryPressure", config) {
  tests_[kName] = [this]() { Test(); };
}

void QueryPressureTests::Test() {
  TestSuite::Initialize();
  host_.SetupFixedFunctionPassthrough();
  host_.SetVertexShaderProgram(std::make_shared<PassthroughVertexShader>());
  host_.SetBlend(false);
  host_.SetFinalCombiner0Just(TestHost::SRC_DIFFUSE);
  host_.SetFinalCombiner1Just(TestHost::SRC_ZERO, true, true);
  host_.PrepareDraw(0xFF102030);
  Method(NV097_SET_CULL_FACE_ENABLE, 0);
  Method(NV097_SET_DEPTH_TEST_ENABLE, 0);
  Method(NV097_SET_ALPHA_TEST_ENABLE, 0);

  auto vertices = host_.AllocateVertexBuffer(4);
  vertices->SetPositionIncludesW(true);
  auto *base = vertices->Lock();
  const uintptr_t first = reinterpret_cast<uintptr_t>(base);
  const bool one_page =
      (first >> 12) == ((first + 4 * sizeof(Vertex) - 1) >> 12);
  Check(1, one_page, 0, "all changing vertex attributes occupy one 4 KiB page");
  vertices->Unlock();

  auto *report = static_cast<ReportRecord *>(MmAllocateContiguousMemoryEx(
      4096, 0, MAXRAM, 4096, PAGE_NOCACHE | PAGE_READWRITE));
  ASSERT(report != nullptr);
  if (!report || !one_page) {
    if (report) {
      MmFreeContiguousMemory(report);
    }
    return;
  }

  s_CtxDma context;
  // Current suites reserve 20-22 for ReportQuery; 23 preserves isolation.
  pb_create_dma_ctx(kReportContext, DMA_CLASS_3,
                    reinterpret_cast<DWORD>(report), 4095, &context);
  pb_bind_channel(&context);
  Method(NV097_SET_CONTEXT_DMA_REPORT, context.ChannelID);

  std::vector<DrawInput> inputs;
  inputs.reserve(kDraws);
  uint32_t input_hash = 2166136261U;
  for (uint32_t draw = 0; draw < kDraws; ++draw) {
    const uint32_t tile = draw % kTiles;
    DrawInput input{32 + (tile % 32) * 18, 64 + (tile / 32) * 20,
                    (draw & 1) ? 16U : 8U, kColors[(draw / kTiles) % 3]};
    for (uint32_t word : {input.left, input.top, input.extent, input.color}) {
      input_hash = HashWord(input_hash, word);
    }
    inputs.push_back(input);
  }
  Check(kExpectedInputHash, input_hash, 5,
        "generated draw recipe matches its input KAT");

  bool completed = true;
  bool all_reports_correct = true;
  const auto results = Profile(kName, 1, [this, vertices, report, &completed,
                                          &all_reports_correct, &inputs]() {
    report->timestamp = UINT64_MAX;
    report->value = kSentinel;
    report->done = kSentinel;
    Method(NV097_CLEAR_REPORT_VALUE,
           NV097_CLEAR_REPORT_VALUE_TYPE_ZPASS_PIXEL_CNT);
    Method(NV097_SET_ZPASS_PIXEL_COUNT_ENABLE, 1);

    for (uint32_t draw = 0; draw < kDraws; ++draw) {
      // Waiting for FIFO consumption makes rewriting these four vertices legal
      // on Xbox. xemu's DMA_GET/PGRAPH_STATUS reads do not submit Vulkan work.
      // There is no report/readback/present boundary inside this pressure loop.
      if (!DrainGuestFifo(host_)) {
        completed = false;
        break;
      }
      const auto &input = inputs[draw];
      const float left = input.left;
      const float top = input.top;
      const float extent = input.extent;
      const uint32_t color = input.color;
      const float red = ((color >> 16) & 255) / 255.f;
      const float green = ((color >> 8) & 255) / 255.f;
      const float blue = (color & 255) / 255.f;
      auto *v = vertices->Lock();
      v[0].SetPosition(left, top, 0.5f, 1.f);
      v[1].SetPosition(left + extent, top, 0.5f, 1.f);
      v[2].SetPosition(left + extent, top + extent, 0.5f, 1.f);
      v[3].SetPosition(left, top + extent, 0.5f, 1.f);
      for (uint32_t i = 0; i < 4; ++i) {
        v[i].SetDiffuse(red, green, blue, 1.f);
      }
      vertices->Unlock();
      host_.DrawArrays(TestHost::POSITION | TestHost::DIFFUSE,
                       TestHost::PRIMITIVE_QUADS);
    }
    Method(NV097_GET_REPORT, NV097_GET_REPORT_TYPE_ZPASS_PIXEL_CNT << 24);
    Method(NV097_SET_ZPASS_PIXEL_COUNT_ENABLE, 0);
    LARGE_INTEGER start;
    QueryPerformanceCounter(&start);
    while (report->done == kSentinel) {
      if (host_.GetMicrosecondsSince(start) >= kTimeoutUs) {
        completed = false;
        break;
      }
      Sleep(0);
    }
    // Keep failure sticky across warmups/repetitions; publish assertions after
    // the timed body. A later successful report cannot erase an earlier failure.
    all_reports_correct &= completed && report->value == kExpectedSamples &&
                           report->done == 0;
  });

  Check(1, completed, 1, "query pressure completes without a timeout");
  Check(1, all_reports_correct, 2,
        "every query report has the expected count and completion");
  // Readback is deliberately after the pressure loop and final report. Exact
  // binary RGB centers also catch stale or reordered same-address uploads.
  host_.WaitForGpu();
  const auto *pixels =
      reinterpret_cast<volatile const uint32_t *>(pb_back_buffer());
  const uint32_t stride = pb_back_buffer_pitch() / 4;
  uint32_t mismatches = 0;
  for (uint32_t tile = 0; tile < kTiles; ++tile) {
    const uint32_t last = tile + ((kDraws - 1 - tile) / kTiles) * kTiles;
    const uint32_t expected = kColors[(last / kTiles) % 3];
    const uint32_t x = 32 + (tile % 32) * 18 + 4;
    const uint32_t y = 64 + (tile / 32) * 20 + 4;
    mismatches += pixels[y * stride + x] != expected;
  }
  Check(0, mismatches, 4,
        "all 512 tile centers retain their final vertex version");

  std::ostringstream metadata;
  metadata << "{\"kind\":\"query_pressure_regression\",\"draws\":"
           << kDraws << ",\"input_fnv1a32\":" << input_hash
           << ",\"vertex_page_bytes\":4096,\"expected_zpass\":"
           << kExpectedSamples << ",\"observed_zpass\":" << report->value
           << ",\"tile_mismatches\":" << mismatches
           << ",\"oracle_status\":\""
           << (all_reports_correct && mismatches == 0 ? "PASS" : "FAIL")
           << "\"}";
  PrintMsg("QUERY_PRESSURE expected=%lu observed=%lu tile_mismatches=%lu\n",
           kExpectedSamples, report->value, mismatches);
  host_.FinishDraw(suite_name_, kName, results, metadata.str());
  host_.ClearVertexBuffer();
  MmFreeContiguousMemory(report);
}
