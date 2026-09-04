#ifndef XEMU_PERF_TESTS_REPORT_QUERY_TESTS_H
#define XEMU_PERF_TESTS_REPORT_QUERY_TESTS_H

#include <pbkit/pbkit_dma.h>

#include "test_suite.h"

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

  void Test(const char *test_name, Scenario scenario, uint32_t final_color);
  void RunScenario(Scenario scenario);
  void BindReportContext(const s_CtxDma &context) const;
  void ClearReportValue() const;
  void SetZpassEnabled(bool enabled) const;
  void QueueReport(uint32_t byte_offset) const;
  void DrawCountedQuad() const;
  void QueueDelayedCountedWork() const;
  void QueueProducerWork() const;
  void ResetRecord(volatile ReportRecord &record) const;
  bool WaitForReport(volatile ReportRecord &record) const;
  volatile ReportRecord &Record(uint8_t *base, uint32_t index) const;

  uint8_t *report_memory_a_{nullptr};
  uint8_t *report_memory_b_{nullptr};
  s_CtxDma report_context_a_{};
  s_CtxDma report_context_b_{};
  s_CtxDma report_context_limited_{};
};

#endif  // XEMU_PERF_TESTS_REPORT_QUERY_TESTS_H
