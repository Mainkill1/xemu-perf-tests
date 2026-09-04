#ifndef XEMU_PERF_TESTS_REPORT_QUERY_TESTS_H
#define XEMU_PERF_TESTS_REPORT_QUERY_TESTS_H

#include <array>

#include <pbkit/pbkit_dma.h>

#include "test_suite.h"

enum class XemuPerfAssertion : uint16_t;

/**
 * Exercises ordered ZPASS report publication and DMA-target ownership.
 */
class ReportQueryTests : public TestSuite {
 public:
  ReportQueryTests(TestHost &host, std::string output_dir, const Config &config);

  void Initialize() override;
  void Deinitialize() override;

 private:
  enum class Scenario {
    ZERO_QUERY,
    SINGLE_BOUNDARY,
    CLEAR_BOUNDARY,
    MULTIPLE_BOUNDARIES,
    DMA_TARGET_SWITCH,
    FIFO_PRODUCER_ORDERING,
    DMA_DESCRIPTOR_REWRITE,
    DMA_RANGE_GUARD,
  };

  struct ReportRecord {
    uint64_t timestamp;
    uint32_t value;
    uint32_t done;
  };
  static_assert(sizeof(ReportRecord) == 16,
                "NV097 report records must remain exactly 16 bytes");

  using DmaDescriptorWords = std::array<uint32_t, 4>;

  void Test(const char *test_name, Scenario scenario, uint32_t final_color);
  void RunScenario(Scenario scenario);
  void BindReportContext(const s_CtxDma &context) const;
  void BindReportContext(uint32_t channel_id) const;
  void ClearReportValue() const;
  void SetZpassEnabled(bool enabled) const;
  void QueueReport(uint32_t byte_offset) const;
  void QueueTerminalSemaphore() const;
  void BusyWaitMicroseconds(uint32_t delay_us) const;
  bool WaitForDmaDataShadow(uint32_t expected) const;
  void DrawCountedQuad() const;
  void QueueProducerWork() const;
  void ResetRecord(volatile ReportRecord &record) const;
  bool WaitForTerminalSemaphore() const;
  bool CompleteGpuWork(const char *failure_message) const;
  bool WaitForPublishedRecord(volatile ReportRecord &record) const;
  bool WaitForEitherPublishedRecord(volatile ReportRecord &first,
                                    volatile ReportRecord &second) const;
  bool ValidatePublishedRecord(volatile ReportRecord &record,
                               XemuPerfAssertion assertion,
                               const char *failure_prefix) const;
  void FillRangeCanaries() const;
  bool RangeCanariesIntact() const;
  DmaDescriptorWords ReadDmaDescriptor(const s_CtxDma &context) const;
  void WriteDmaDescriptor(const s_CtxDma &context,
                          const DmaDescriptorWords &words) const;
  bool IsCorrectnessOnly(Scenario scenario) const;
  ReportRecord SnapshotRecord(volatile ReportRecord &record) const;
  std::string BuildObservationMetadata(Scenario scenario) const;
  volatile ReportRecord &Record(uint8_t *base, uint32_t index) const;

  uint8_t *report_memory_a_{nullptr};
  uint8_t *report_memory_b_{nullptr};
  volatile uint32_t *completion_memory_{nullptr};
  s_CtxDma report_context_a_{};
  s_CtxDma report_context_b_{};
  s_CtxDma report_context_limited_{};
  DmaDescriptorWords original_report_descriptor_a_{};
  mutable ReportRecord observed_a0_{};
  mutable ReportRecord observed_a1_{};
  mutable ReportRecord observed_b0_{};
  mutable ReportRecord observed_b1_{};
  mutable bool terminal_completed_{false};
  mutable bool rewrite_observed_pending_{false};
  mutable bool rewrite_completed_before_{false};
  mutable uint32_t rewrite_attempt_count_{0};
  mutable uint32_t rewrite_selected_delay_us_{0};
  mutable uint32_t rewrite_early_attempts_{0};
  mutable uint32_t rewrite_completed_before_attempts_{0};
  mutable bool range_canaries_intact_{true};
};

#endif  // XEMU_PERF_TESTS_REPORT_QUERY_TESTS_H
