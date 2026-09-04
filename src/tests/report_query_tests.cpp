#include "report_query_tests.h"

#include <sstream>

#include <pbkit/nv_regs.h>
#include <pbkit/outer.h>
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
static constexpr char kDmaDescriptorRewriteTestName[] = "report.dma-descriptor-rewrite";
static constexpr char kDmaRangeGuardTestName[] = "report.dma-range-guard";

static constexpr uint32_t kReportBufferBytes = 256;
static constexpr uint32_t kReportContextA = 20;
static constexpr uint32_t kReportContextB = 21;
static constexpr uint32_t kReportContextLimited = 22;
static constexpr uint32_t kFullRamDmaContext = 3;
static constexpr uint32_t kLimitedReportInclusiveLimit = 17;
static constexpr uint32_t kDescriptorRewriteDraws = 4096;
static constexpr uint32_t kProfileSamples = 4;
static constexpr uint32_t kReportTimeoutUs = 2000000;
static constexpr uint32_t kTerminalSemaphoreValue = 0x52E00142;
static constexpr uint32_t kTerminalSemaphoreSentinel = 0xD15EA5ED;
static constexpr uint64_t kTimestampSentinel = UINT64_C(0xF00DFACECAFE0123);
static constexpr uint32_t kValueSentinel = 0xDEADBEEF;
static constexpr uint32_t kDoneSentinel = 0xA5A55A5A;
static constexpr uint32_t kExpectedDone = 0;
static constexpr uint32_t kRangeCanaryOffset = 8;
static constexpr uint32_t kRangeCanaryBytes = 32;
static constexpr uint8_t kRangeCanaryByte = 0xC7;
static_assert(kRangeCanaryOffset + kRangeCanaryBytes <= kReportBufferBytes,
              "range canaries must remain within test-owned report memory");

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
  tests_[kDmaDescriptorRewriteTestName] = [this]() {
    Test(kDmaDescriptorRewriteTestName, Scenario::DMA_DESCRIPTOR_REWRITE, 0xFF70D0A0);
  };
  tests_[kDmaRangeGuardTestName] = [this]() {
    Test(kDmaRangeGuardTestName, Scenario::DMA_RANGE_GUARD, 0xFF80E0B0);
  };
}

void ReportQueryTests::Initialize() {
  TestSuite::Initialize();

  report_memory_a_ = static_cast<uint8_t *>(MmAllocateContiguousMemoryEx(
      kReportBufferBytes, 0, MAXRAM, 0, PAGE_NOCACHE | PAGE_READWRITE));
  report_memory_b_ = static_cast<uint8_t *>(MmAllocateContiguousMemoryEx(
      kReportBufferBytes, 0, MAXRAM, 0, PAGE_NOCACHE | PAGE_READWRITE));
  completion_memory_ = static_cast<volatile uint32_t *>(
      MmAllocateContiguousMemoryEx(sizeof(uint32_t), 0, MAXRAM, 0,
                                   PAGE_NOCACHE | PAGE_READWRITE));
  ASSERT(report_memory_a_ != nullptr);
  ASSERT(report_memory_b_ != nullptr);
  ASSERT(completion_memory_ != nullptr);
  if (!report_memory_a_ || !report_memory_b_ || !completion_memory_) {
    return;
  }

  pb_create_dma_ctx(kReportContextA, DMA_CLASS_3,
                    reinterpret_cast<DWORD>(report_memory_a_),
                    kReportBufferBytes - 1, &report_context_a_);
  pb_create_dma_ctx(kReportContextB, DMA_CLASS_3,
                    reinterpret_cast<DWORD>(report_memory_b_),
                    kReportBufferBytes - 1, &report_context_b_);
  // The limit is inclusive. Offset 16 is a legal starting byte but cannot
  // contain the complete 16-byte report record.
  pb_create_dma_ctx(kReportContextLimited, DMA_CLASS_3,
                    reinterpret_cast<DWORD>(report_memory_a_),
                    kLimitedReportInclusiveLimit, &report_context_limited_);
  pb_bind_channel(&report_context_a_);
  pb_bind_channel(&report_context_b_);
  pb_bind_channel(&report_context_limited_);
  original_report_descriptor_a_ = ReadDmaDescriptor(report_context_a_);
}

void ReportQueryTests::Deinitialize() {
  if (completion_memory_) {
    SetZpassEnabled(false);
    BindReportContext(kFullRamDmaContext);
    WriteDmaDescriptor(report_context_a_, original_report_descriptor_a_);
    QueueTerminalSemaphore();
    WaitForTerminalSemaphore();
  }
  host_.WaitForGpu();
  if (report_memory_a_) {
    MmFreeContiguousMemory(report_memory_a_);
    report_memory_a_ = nullptr;
  }
  if (report_memory_b_) {
    MmFreeContiguousMemory(report_memory_b_);
    report_memory_b_ = nullptr;
  }
  if (completion_memory_) {
    MmFreeContiguousMemory(
        const_cast<uint32_t *>(completion_memory_));
    completion_memory_ = nullptr;
  }
  TestSuite::Deinitialize();
}

void ReportQueryTests::BindReportContext(const s_CtxDma &context) const {
  BindReportContext(context.ChannelID);
}

void ReportQueryTests::BindReportContext(uint32_t channel_id) const {
  PushMethod(NV097_SET_CONTEXT_DMA_REPORT, channel_id);
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

void ReportQueryTests::QueueTerminalSemaphore() const {
  ASSERT(completion_memory_ != nullptr);
  *completion_memory_ = kTerminalSemaphoreSentinel;
  const uint32_t semaphore_offset =
      reinterpret_cast<uint32_t>(completion_memory_) & 0x03FFFFFF;
  PushMethod(NV097_SET_CONTEXT_DMA_SEMAPHORE, kFullRamDmaContext);
  PushMethod(NV097_SET_SEMAPHORE_OFFSET, semaphore_offset);
  PushMethod(NV097_BACK_END_WRITE_SEMAPHORE_RELEASE,
             kTerminalSemaphoreValue);
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

void ReportQueryTests::QueueDelayedCountedWork() const {
  // Build a GPU backlog before GET_REPORT. The guest CPU then has a stable
  // interval in which to rewrite the report's RAMIN descriptor while the
  // renderer is completing the already-queued query prefix.
  for (uint32_t i = 0; i < kDescriptorRewriteDraws; ++i) {
    DrawCountedQuad();
  }
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

bool ReportQueryTests::WaitForTerminalSemaphore() const {
  ASSERT(completion_memory_ != nullptr);
  LARGE_INTEGER start;
  QueryPerformanceCounter(&start);
  while (*completion_memory_ != kTerminalSemaphoreValue) {
    if (host_.GetMicrosecondsSince(start) >= kReportTimeoutUs) {
      return false;
    }
    Sleep(0);
  }
  return true;
}

bool ReportQueryTests::CompleteGpuWork(const char *failure_message) const {
  QueueTerminalSemaphore();
  terminal_completed_ = WaitForTerminalSemaphore();
  AssertXemuPerfEqual(1, terminal_completed_,
                      XemuPerfAssertion::REPORT_TIMEOUT_A, failure_message,
                      __FILE__, __LINE__);
  return terminal_completed_;
}

bool ReportQueryTests::ValidatePublishedRecord(
    volatile ReportRecord &record, XemuPerfAssertion assertion,
    const char *failure_prefix) const {
  if (record.timestamp == kTimestampSentinel) {
    AssertXemuPerfEqual(1, 0, assertion, failure_prefix, __FILE__, __LINE__);
    return false;
  }
  if (record.value == kValueSentinel) {
    AssertXemuPerfEqual(1, 0, assertion, failure_prefix, __FILE__, __LINE__);
    return false;
  }
  AssertXemuPerfEqual(kExpectedDone, record.done, assertion, failure_prefix,
                      __FILE__, __LINE__);
  return record.done == kExpectedDone;
}

void ReportQueryTests::FillRangeCanaries() const {
  volatile uint8_t *canary = report_memory_a_ + kRangeCanaryOffset;
  for (uint32_t i = 0; i < kRangeCanaryBytes; ++i) {
    canary[i] = kRangeCanaryByte;
  }
}

bool ReportQueryTests::RangeCanariesIntact() const {
  const volatile uint8_t *canary = report_memory_a_ + kRangeCanaryOffset;
  for (uint32_t i = 0; i < kRangeCanaryBytes; ++i) {
    if (canary[i] != kRangeCanaryByte) {
      return false;
    }
  }
  return true;
}

ReportQueryTests::DmaDescriptorWords ReportQueryTests::ReadDmaDescriptor(
    const s_CtxDma &context) const {
  DmaDescriptorWords words{};
  const uint32_t base = NV_PRAMIN + (context.Inst << 4);
  for (uint32_t i = 0; i < words.size(); ++i) {
    words[i] = VIDEOREG(base + i * sizeof(uint32_t));
  }
  return words;
}

void ReportQueryTests::WriteDmaDescriptor(
    const s_CtxDma &context, const DmaDescriptorWords &words) const {
  const uint32_t base = NV_PRAMIN + (context.Inst << 4);
  for (uint32_t i = 0; i < words.size(); ++i) {
    VIDEOREG(base + i * sizeof(uint32_t)) = words[i];
  }
}

bool ReportQueryTests::IsCorrectnessOnly(Scenario scenario) const {
  return scenario == Scenario::DMA_DESCRIPTOR_REWRITE ||
         scenario == Scenario::DMA_RANGE_GUARD;
}

ReportQueryTests::ReportRecord ReportQueryTests::SnapshotRecord(
    volatile ReportRecord &record) const {
  ReportRecord snapshot{};
  snapshot.timestamp = record.timestamp;
  snapshot.value = record.value;
  snapshot.done = record.done;
  return snapshot;
}

std::string ReportQueryTests::BuildObservationMetadata(Scenario scenario) const {
  const char *scenario_name = "unknown";
  switch (scenario) {
    case Scenario::ZERO_QUERY:
      scenario_name = "zero_query";
      break;
    case Scenario::SINGLE_BOUNDARY:
      scenario_name = "single_boundary";
      break;
    case Scenario::CLEAR_BOUNDARY:
      scenario_name = "clear_boundary";
      break;
    case Scenario::MULTIPLE_BOUNDARIES:
      scenario_name = "multiple_boundaries";
      break;
    case Scenario::DMA_TARGET_SWITCH:
      scenario_name = "dma_target_switch";
      break;
    case Scenario::FIFO_PRODUCER_ORDERING:
      scenario_name = "fifo_producer_ordering";
      break;
    case Scenario::DMA_DESCRIPTOR_REWRITE:
      scenario_name = "dma_descriptor_rewrite";
      break;
    case Scenario::DMA_RANGE_GUARD:
      scenario_name = "dma_range_guard";
      break;
  }

  auto append_record = [](std::ostringstream &metadata, const char *name,
                          const ReportRecord &record) {
    metadata << "\"" << name << "\":{";
    metadata << "\"timestamp\":" << record.timestamp << ",";
    metadata << "\"value\":" << record.value << ",";
    metadata << "\"done\":" << record.done << "}";
  };

  std::ostringstream metadata;
  metadata << "{\"schema_version\":1,";
  metadata << "\"kind\":\"report_query_observations\",";
  metadata << "\"scenario\":\"" << scenario_name << "\",";
  metadata << "\"performance_eligible\":"
           << (IsCorrectnessOnly(scenario) ? "false" : "true") << ",";
  metadata << "\"completion\":{\"kind\":\"terminal_semaphore\",";
  metadata << "\"completed\":" << (terminal_completed_ ? "true" : "false")
           << "},";
  metadata << "\"records\":{";
  append_record(metadata, "a0", observed_a0_);
  metadata << ",";
  append_record(metadata, "a1", observed_a1_);
  metadata << ",";
  append_record(metadata, "b0", observed_b0_);
  metadata << ",";
  append_record(metadata, "b1", observed_b1_);
  metadata << "},";
  metadata << "\"range_canaries_intact\":"
           << (range_canaries_intact_ ? "true" : "false") << "}";
  return metadata.str();
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
  auto &b1 = Record(report_memory_b_, 1);
  ResetRecord(a0);
  ResetRecord(a1);
  ResetRecord(b0);
  ResetRecord(b1);
  observed_a0_ = SnapshotRecord(a0);
  observed_a1_ = SnapshotRecord(a1);
  observed_b0_ = SnapshotRecord(b0);
  observed_b1_ = SnapshotRecord(b1);
  terminal_completed_ = false;
  range_canaries_intact_ = true;

  BindReportContext(report_context_a_);
  SetZpassEnabled(false);
  ClearReportValue();

  if (scenario == Scenario::ZERO_QUERY) {
    // Establish the zero-query state explicitly in this leaf. Record real
    // renderer work so the report boundary is exercised on every backend.
    DrawCountedQuad();
    QueueReport(0);
    if (!CompleteGpuWork(
            "zero-query terminal semaphore did not complete after GET_REPORT")) {
      return;
    }
    if (!ValidatePublishedRecord(
            a0, XemuPerfAssertion::REPORT_ZERO_VALUE,
            "zero-query report must publish timestamp, value, and done=0")) {
      return;
    }
    AssertXemuPerfEqual(0, a0.value, XemuPerfAssertion::REPORT_ZERO_VALUE,
                        "disabled ZPASS report remains zero", __FILE__, __LINE__);
    return;
  }

  if (scenario == Scenario::DMA_DESCRIPTOR_REWRITE) {
    // Positive control: prove that the original A descriptor and A0 record
    // are writable before testing ownership of a pending report.
    SetZpassEnabled(true);
    DrawCountedQuad();
    QueueReport(0);
    SetZpassEnabled(false);
    if (!CompleteGpuWork(
            "descriptor positive-control semaphore did not complete")) {
      return;
    }
    if (!ValidatePublishedRecord(
            a0, XemuPerfAssertion::REPORT_DMA_DESCRIPTOR_SNAPSHOT,
            "descriptor positive control did not publish complete A0 record")) {
      return;
    }
    AssertXemuPerfEqual(
        1, a0.value != 0, XemuPerfAssertion::REPORT_DMA_DESCRIPTOR_SNAPSHOT,
        "descriptor positive control A0 must contain a nonzero ZPASS count",
        __FILE__, __LINE__);

    ResetRecord(a1);
    ResetRecord(b0);
    ResetRecord(b1);
    BindReportContext(report_context_a_);
    ClearReportValue();
    SetZpassEnabled(true);
    QueueDelayedCountedWork();
    QueueReport(sizeof(ReportRecord));

    // Mutate the RAMIN descriptor immediately from the guest CPU. This is not
    // a FIFO method: the pending GET_REPORT must own the descriptor it saw
    // when consumed, while the following report must observe the new B target.
    WriteDmaDescriptor(report_context_a_, ReadDmaDescriptor(report_context_b_));
    ClearReportValue();
    DrawCountedQuad();
    QueueReport(0);
    SetZpassEnabled(false);

    const bool completed = CompleteGpuWork(
        "descriptor rewrite terminal semaphore did not complete");
    if (completed) {
      ValidatePublishedRecord(
          a1, XemuPerfAssertion::REPORT_DMA_DESCRIPTOR_SNAPSHOT,
          "pending pre-rewrite report must publish complete A1 record");
      const bool b1_unchanged =
          b1.timestamp == kTimestampSentinel && b1.value == kValueSentinel &&
          b1.done == kDoneSentinel;
      AssertXemuPerfEqual(
          1, b1_unchanged,
          XemuPerfAssertion::REPORT_DMA_DESCRIPTOR_SNAPSHOT,
          "pending pre-rewrite report must not be redirected to B1", __FILE__,
          __LINE__);
      ValidatePublishedRecord(
          b0, XemuPerfAssertion::REPORT_DMA_DESCRIPTOR_SNAPSHOT,
          "post-rewrite control report must publish complete B0 record");
    }

    // Restore all four original descriptor dwords only after the terminal
    // semaphore proves both reports have retired.
    WriteDmaDescriptor(report_context_a_, original_report_descriptor_a_);
    BindReportContext(report_context_a_);
    return;
  }

  if (scenario == Scenario::DMA_RANGE_GUARD) {
    // Positive control: offset zero fits the intentionally short inclusive
    // limit and must publish a complete report record.
    BindReportContext(report_context_limited_);
    ClearReportValue();
    SetZpassEnabled(true);
    DrawCountedQuad();
    QueueReport(0);
    SetZpassEnabled(false);
    if (!CompleteGpuWork(
            "range-guard valid-offset terminal semaphore did not complete")) {
      BindReportContext(report_context_a_);
      return;
    }
    if (!ValidatePublishedRecord(
            a0, XemuPerfAssertion::REPORT_DMA_RANGE_GUARD,
            "range-guard valid offset 0 must publish a complete record")) {
      BindReportContext(report_context_a_);
      return;
    }
    observed_a0_ = SnapshotRecord(a0);

    // Offset 16 begins within the descriptor's inclusive limit of 17 but its
    // complete 16-byte record does not fit. Guard the whole target record plus
    // eight bytes on either side so partial writes also fail the oracle.
    FillRangeCanaries();
    SetZpassEnabled(false);
    ClearReportValue();
    QueueReport(sizeof(ReportRecord));
    const bool completed = CompleteGpuWork(
        "range-guard invalid-offset terminal semaphore did not complete");
    if (completed) {
      range_canaries_intact_ = RangeCanariesIntact();
      AssertXemuPerfEqual(
          1, range_canaries_intact_,
          XemuPerfAssertion::REPORT_DMA_RANGE_GUARD,
          "invalid offset 16 must preserve the full record and surrounding canaries",
          __FILE__, __LINE__);
    }
    BindReportContext(report_context_a_);
    return;
  }

  SetZpassEnabled(true);
  DrawCountedQuad();
  QueueReport(0);

  if (scenario == Scenario::SINGLE_BOUNDARY) {
    SetZpassEnabled(false);
    // Start one non-counted draw so backends that close an active query at the
    // next draw boundary publish the preceding report before completion.
    DrawCountedQuad();
    if (!CompleteGpuWork(
            "single-boundary terminal semaphore did not complete")) {
      return;
    }
    if (!ValidatePublishedRecord(
            a0, XemuPerfAssertion::REPORT_NONZERO_VALUE,
            "single-boundary report must publish timestamp, value, and done=0")) {
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
    if (!CompleteGpuWork(
            "DMA-target terminal semaphore did not complete")) {
      return;
    }
    if (!ValidatePublishedRecord(
            a0, XemuPerfAssertion::REPORT_TIMEOUT_A,
            "first DMA-target report must publish complete A0 record")) {
      return;
    }
    if (!ValidatePublishedRecord(
            b0, XemuPerfAssertion::REPORT_TIMEOUT_B,
            "second DMA-target report must publish complete B0 record")) {
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
  if (!CompleteGpuWork("ordered-report terminal semaphore did not complete")) {
    return;
  }
  if (!ValidatePublishedRecord(
          a0, XemuPerfAssertion::REPORT_TIMEOUT_A,
          "first ordered report must publish timestamp, value, and done=0")) {
    return;
  }
  if (!ValidatePublishedRecord(
          a1, XemuPerfAssertion::REPORT_TIMEOUT_B,
          "second ordered report must publish timestamp, value, and done=0")) {
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
  ASSERT(completion_memory_ != nullptr);
  if (!report_memory_a_ || !report_memory_b_ || !completion_memory_) {
    return;
  }

  host_.SetVertexShaderProgram(nullptr);
  host_.SetupFixedFunctionPassthrough();
  PushMethod(NV097_SET_CULL_FACE_ENABLE, 0);
  PushMethod(NV097_SET_DEPTH_TEST_ENABLE, 0);
  host_.PrepareDraw(0xFF101010);

  TestHost::ProfileResults results{};
  if (IsCorrectnessOnly(scenario)) {
    // These are semantic fault oracles, not microbenchmarks. Force exactly one
    // execution regardless of the selected profile and stop after that result.
    const uint32_t saved_warmups = host_.GetWarmupIterations();
    const uint32_t saved_multiplier = host_.GetMeasurementIterationsMultiplier();
    host_.SetWarmupIterations(0);
    host_.SetMeasurementIterationsMultiplier(1);
    results = Profile(test_name, 1,
                      [this, scenario]() { RunScenario(scenario); });
    host_.SetMeasurementIterationsMultiplier(saved_multiplier);
    host_.SetWarmupIterations(saved_warmups);
  } else {
    results = Profile(test_name, kProfileSamples,
                      [this, scenario]() { RunScenario(scenario); });
  }

  auto &a0 = Record(report_memory_a_, 0);
  auto &a1 = Record(report_memory_a_, 1);
  auto &b0 = Record(report_memory_b_, 0);
  auto &b1 = Record(report_memory_b_, 1);
  if (scenario != Scenario::DMA_RANGE_GUARD) {
    observed_a0_ = SnapshotRecord(a0);
  }
  observed_a1_ = SnapshotRecord(a1);
  observed_b0_ = SnapshotRecord(b0);
  observed_b1_ = SnapshotRecord(b1);

  BindReportContext(report_context_a_);
  SetZpassEnabled(false);
  host_.PrepareDraw(final_color);
  host_.FinishDraw(suite_name_, test_name, results,
                   BuildObservationMetadata(scenario));
}
