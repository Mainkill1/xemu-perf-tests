#include "report_query_tests.h"

#include <pbkit/nv_regs.h>
#include <pbkit/pbkit.h>
#include <pbkit/pbkit_pushbuffer.h>

#include "debug_output.h"
#include "test_host.h"

static constexpr char kZeroQueryTestName[] = "report.zero-query";
static constexpr char kSingleBoundaryTestName[] = "report.single-boundary";
static constexpr char kClearBoundaryTestName[] = "report.clear-boundary";
static constexpr char kMultipleBoundariesTestName[] = "report.multiple-boundaries";
static constexpr char kDmaTargetSwitchTestName[] = "report.dma-target-switch";
static constexpr char kFifoProducerOrderingTestName[] = "report.fifo-producer-ordering";

static constexpr uint32_t kReportBufferBytes = 256;
static constexpr uint32_t kReportContextA = 20;
static constexpr uint32_t kReportContextB = 21;
static constexpr uint32_t kProfileSamples = 4;
static constexpr uint32_t kReportTimeoutUs = 2000000;
static constexpr uint64_t kTimestampSentinel = UINT64_C(0xF00DFACECAFE0123);
static constexpr uint32_t kValueSentinel = 0xDEADBEEF;
static constexpr uint32_t kDoneSentinel = 0xA5A55A5A;

static void PushMethod(uint32_t method, uint32_t parameter) {
  PBKitPlusPlus::Pushbuffer::Begin();
  PBKitPlusPlus::Pushbuffer::Push(method, parameter);
  PBKitPlusPlus::Pushbuffer::End();
}

ReportQueryTests::ReportQueryTests(TestHost &host, std::string output_dir, const Config &config)
    : TestSuite(host, std::move(output_dir), "ReportQuery", config) {
  tests_[kZeroQueryTestName] =
      [this]() { Test(kZeroQueryTestName, Scenario::ZERO_QUERY, 0xFF102030); };
  tests_[kSingleBoundaryTestName] =
      [this]() { Test(kSingleBoundaryTestName, Scenario::SINGLE_BOUNDARY, 0xFF204060); };
  tests_[kClearBoundaryTestName] =
      [this]() { Test(kClearBoundaryTestName, Scenario::CLEAR_BOUNDARY, 0xFF306090); };
  tests_[kMultipleBoundariesTestName] = [this]() {
    Test(kMultipleBoundariesTestName, Scenario::MULTIPLE_BOUNDARIES, 0xFF4080C0);
  };
  tests_[kDmaTargetSwitchTestName] = [this]() {
    Test(kDmaTargetSwitchTestName, Scenario::DMA_TARGET_SWITCH, 0xFF50A070);
  };
  tests_[kFifoProducerOrderingTestName] = [this]() {
    Test(kFifoProducerOrderingTestName, Scenario::FIFO_PRODUCER_ORDERING, 0xFF60C090);
  };
}

void ReportQueryTests::Initialize() {
  TestSuite::Initialize();

  report_memory_a_ = static_cast<uint8_t *>(MmAllocateContiguousMemoryEx(
      kReportBufferBytes, 0, MAXRAM, 0, PAGE_NOCACHE | PAGE_READWRITE));
  report_memory_b_ = static_cast<uint8_t *>(MmAllocateContiguousMemoryEx(
      kReportBufferBytes, 0, MAXRAM, 0, PAGE_NOCACHE | PAGE_READWRITE));
  ASSERT(report_memory_a_ != nullptr);
  ASSERT(report_memory_b_ != nullptr);
  if (!report_memory_a_ || !report_memory_b_) {
    return;
  }

  pb_create_dma_ctx(kReportContextA, DMA_CLASS_3,
                    reinterpret_cast<DWORD>(report_memory_a_),
                    kReportBufferBytes - 1, &report_context_a_);
  pb_create_dma_ctx(kReportContextB, DMA_CLASS_3,
                    reinterpret_cast<DWORD>(report_memory_b_),
                    kReportBufferBytes - 1, &report_context_b_);
  pb_bind_channel(&report_context_a_);
  pb_bind_channel(&report_context_b_);
}

void ReportQueryTests::Deinitialize() {
  host_.WaitForGpu();
  if (report_memory_a_) {
    MmFreeContiguousMemory(report_memory_a_);
    report_memory_a_ = nullptr;
  }
  if (report_memory_b_) {
    MmFreeContiguousMemory(report_memory_b_);
    report_memory_b_ = nullptr;
  }
  TestSuite::Deinitialize();
}

void ReportQueryTests::BindReportContext(const s_CtxDma &context) const {
  PushMethod(NV097_SET_CONTEXT_DMA_REPORT, context.ChannelID);
}

void ReportQueryTests::ClearReportValue() const {
  PushMethod(NV097_CLEAR_REPORT_VALUE,
             NV097_CLEAR_REPORT_VALUE_TYPE_ZPASS_PIXEL_CNT);
}

void ReportQueryTests::SetZpassEnabled(bool enabled) const {
  PushMethod(NV097_SET_ZPASS_PIXEL_COUNT_ENABLE, enabled ? 1 : 0);
}

void ReportQueryTests::QueueReport(uint32_t byte_offset) const {
  ASSERT((byte_offset & 0xF) == 0);
  ASSERT(byte_offset + sizeof(ReportRecord) <= kReportBufferBytes);
  PushMethod(NV097_GET_REPORT,
             (NV097_GET_REPORT_TYPE_ZPASS_PIXEL_CNT << 24) | byte_offset);
}

void ReportQueryTests::DrawCountedQuad() const {
  static constexpr float kLeft = 96.0f;
  static constexpr float kTop = 96.0f;
  static constexpr float kRight = 224.0f;
  static constexpr float kBottom = 224.0f;
  static constexpr float kZ = 0.5f;
  static constexpr float kW = 1.0f;

  host_.SetDiffuse(0.75f, 0.5f, 0.25f);
  host_.Begin(TestHost::PRIMITIVE_QUADS);
  host_.SetVertex(kLeft, kTop, kZ, kW);
  host_.SetVertex(kRight, kTop, kZ, kW);
  host_.SetVertex(kRight, kBottom, kZ, kW);
  host_.SetVertex(kLeft, kBottom, kZ, kW);
  host_.End();
}

void ReportQueryTests::QueueProducerWork() const {
  PBKitPlusPlus::Pushbuffer::Begin();
  for (uint32_t i = 0; i < 512; ++i) {
    PBKitPlusPlus::Pushbuffer::Push(NV097_SET_ALPHA_REF, i & 0xFF);
    PBKitPlusPlus::Pushbuffer::Push(NV097_SET_COLOR_MATERIAL,
                                    NV097_SET_COLOR_MATERIAL_ALL_FROM_MATERIAL);
  }
  PBKitPlusPlus::Pushbuffer::End();
}

void ReportQueryTests::ResetRecord(volatile ReportRecord &record) const {
  record.timestamp = kTimestampSentinel;
  record.value = kValueSentinel;
  record.done = kDoneSentinel;
}

bool ReportQueryTests::WaitForReport(volatile ReportRecord &record) const {
  LARGE_INTEGER start;
  QueryPerformanceCounter(&start);
  while (record.value == kValueSentinel) {
    if (host_.GetMicrosecondsSince(start) >= kReportTimeoutUs) {
      return false;
    }
    Sleep(0);
  }
  return record.timestamp != kTimestampSentinel;
}

volatile ReportQueryTests::ReportRecord &ReportQueryTests::Record(
    uint8_t *base, uint32_t index) const {
  ASSERT(base != nullptr);
  ASSERT((index + 1) * sizeof(ReportRecord) <= kReportBufferBytes);
  return reinterpret_cast<volatile ReportRecord *>(base)[index];
}

void ReportQueryTests::RunScenario(Scenario scenario) {
  auto &a0 = Record(report_memory_a_, 0);
  auto &a1 = Record(report_memory_a_, 1);
  auto &b0 = Record(report_memory_b_, 0);
  ResetRecord(a0);
  ResetRecord(a1);
  ResetRecord(b0);

  BindReportContext(report_context_a_);
  ClearReportValue();

  if (scenario == Scenario::ZERO_QUERY) {
    // Keep ZPASS counting disabled, but record real renderer work so the
    // report boundary is exercised inside a command buffer on every backend.
    DrawCountedQuad();
    QueueReport(0);
    if (!WaitForReport(a0)) {
      AssertXemuPerfEqual(1, 0, XemuPerfAssertion::REPORT_TIMEOUT_A,
                          "zero-query report is published", __FILE__, __LINE__);
      return;
    }
    AssertXemuPerfEqual(0, a0.value, XemuPerfAssertion::REPORT_ZERO_VALUE,
                        "disabled ZPASS report remains zero", __FILE__, __LINE__);
    return;
  }

  SetZpassEnabled(true);
  DrawCountedQuad();
  QueueReport(0);

  if (scenario == Scenario::SINGLE_BOUNDARY) {
    SetZpassEnabled(false);
    // Start one non-counted draw so backends that close an active query at the
    // next draw boundary publish the preceding report before the CPU polls it.
    DrawCountedQuad();
    if (!WaitForReport(a0)) {
      AssertXemuPerfEqual(1, 0, XemuPerfAssertion::REPORT_TIMEOUT_A,
                          "single-boundary report is published", __FILE__, __LINE__);
      return;
    }
    AssertXemuPerfEqual(1, a0.value != 0 && a0.value != kValueSentinel,
                        XemuPerfAssertion::REPORT_NONZERO_VALUE,
                        "counted ZPASS report is nonzero", __FILE__, __LINE__);
    return;
  }

  if (scenario == Scenario::DMA_TARGET_SWITCH) {
    BindReportContext(report_context_b_);
    ClearReportValue();
    DrawCountedQuad();
    QueueReport(0);
    SetZpassEnabled(false);
    DrawCountedQuad();
    if (!WaitForReport(a0)) {
      AssertXemuPerfEqual(1, 0, XemuPerfAssertion::REPORT_TIMEOUT_A,
                          "first DMA-target report is published", __FILE__, __LINE__);
      return;
    }
    if (!WaitForReport(b0)) {
      AssertXemuPerfEqual(1, 0, XemuPerfAssertion::REPORT_TIMEOUT_B,
                          "second DMA-target report is published", __FILE__, __LINE__);
      return;
    }
    AssertXemuPerfEqual(1, a0.value != 0 && a0.value == b0.value,
                        XemuPerfAssertion::REPORT_DMA_TARGET_VALUE,
                        "DMA-target reports are nonzero and equal", __FILE__, __LINE__);
    return;
  }

  if (scenario == Scenario::CLEAR_BOUNDARY) {
    ClearReportValue();
  } else if (scenario == Scenario::FIFO_PRODUCER_ORDERING) {
    QueueProducerWork();
  }

  DrawCountedQuad();
  QueueReport(sizeof(ReportRecord));
  SetZpassEnabled(false);
  if (!WaitForReport(a0)) {
    AssertXemuPerfEqual(1, 0, XemuPerfAssertion::REPORT_TIMEOUT_A,
                        "first ordered report is published", __FILE__, __LINE__);
    return;
  }
  if (!WaitForReport(a1)) {
    AssertXemuPerfEqual(1, 0, XemuPerfAssertion::REPORT_TIMEOUT_B,
                        "second ordered report is published", __FILE__, __LINE__);
    return;
  }
  AssertXemuPerfEqual(1, a0.value != 0 && a0.value != kValueSentinel,
                      XemuPerfAssertion::REPORT_NONZERO_VALUE,
                      "first ordered report is nonzero", __FILE__, __LINE__);
  if (scenario == Scenario::CLEAR_BOUNDARY) {
    AssertXemuPerfEqual(a0.value, a1.value,
                        XemuPerfAssertion::REPORT_CLEAR_VALUE,
                        "clear-separated reports have equal counts", __FILE__, __LINE__);
  } else {
    AssertXemuPerfEqual(a0.value * 2, a1.value,
                        XemuPerfAssertion::REPORT_CUMULATIVE_VALUE,
                        "ordered reports accumulate equal draws", __FILE__, __LINE__);
  }
}

void ReportQueryTests::Test(const char *test_name, Scenario scenario,
                            uint32_t final_color) {
  ASSERT(report_memory_a_ != nullptr);
  ASSERT(report_memory_b_ != nullptr);
  if (!report_memory_a_ || !report_memory_b_) {
    return;
  }

  host_.SetVertexShaderProgram(nullptr);
  host_.SetupFixedFunctionPassthrough();
  PushMethod(NV097_SET_CULL_FACE_ENABLE, 0);
  PushMethod(NV097_SET_DEPTH_TEST_ENABLE, 0);
  host_.PrepareDraw(0xFF101010);

  auto results = Profile(test_name, kProfileSamples,
                         [this, scenario]() { RunScenario(scenario); });

  BindReportContext(report_context_a_);
  SetZpassEnabled(false);
  host_.PrepareDraw(final_color);
  host_.FinishDraw(suite_name_, test_name, results);
}
