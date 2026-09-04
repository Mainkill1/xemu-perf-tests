#!/usr/bin/env python3
"""Static contracts for the ZPASS report-query capsule."""

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/tests/report_query_tests.cpp").read_text()
HEADER = (ROOT / "src/tests/report_query_tests.h").read_text()
MAIN = (ROOT / "src/main.cpp").read_text()
CMAKE = (ROOT / "src/CMakeLists.txt").read_text()
DOC = (ROOT / "docs/report-query-workload.md").read_text()
CATALOG = json.loads((ROOT / "resources/catalog.json").read_text())

EXPECTED = {
    "report_query.zero_query": "report.zero-query",
    "report_query.single_boundary": "report.single-boundary",
    "report_query.clear_boundary": "report.clear-boundary",
    "report_query.multiple_boundaries": "report.multiple-boundaries",
    "report_query.dma_target_switch": "report.dma-target-switch",
    "report_query.fifo_producer_ordering": "report.fifo-producer-ordering",
    "report_query.dma_descriptor_rewrite": "report.dma-descriptor-rewrite",
    "report_query.dma_range_guard": "report.dma-range-guard",
}


class ReportQueryContractTests(unittest.TestCase):
    def test_suite_registration_and_catalog(self):
        self.assertIn("REG_TEST(ReportQueryTests)", MAIN)
        self.assertIn("tests/report_query_tests.cpp", CMAKE)
        by_id = {item["id"]: item for item in CATALOG["tests"]}
        for stable_id, legacy_test in EXPECTED.items():
            descriptor = by_id[stable_id]
            self.assertEqual(descriptor["execution"]["legacy_test"], legacy_test)
            self.assertEqual(descriptor["revision"], 2)
            self.assertIn("report", descriptor["tags"])
            self.assertIn(
                {"name": "report.memory", "kind": "structured", "scope_version": 1},
                descriptor["observations"],
            )
            self.assertIn(legacy_test, SOURCE)
        for stable_id in (
            "report_query.dma_descriptor_rewrite",
            "report_query.dma_range_guard",
        ):
            descriptor = by_id[stable_id]
            self.assertEqual(descriptor["supported_targets"], ["xemu"])
            self.assertEqual(descriptor["measurement_class"], "correctness")
            self.assertNotIn("performance", descriptor["tags"])
            self.assertEqual(descriptor["default_measurement"]["measured_samples"], 1)

    def test_focused_plans_are_catalog_bound(self):
        for profile in ("fast-smoke", "quick", "sustained"):
            config = json.loads(
                (ROOT / "resources" / f"report-query-{profile}.json").read_text()
            )
            plan = config["resolved_plan"]
            self.assertEqual(plan["catalog_id"], CATALOG["catalog_id"])
            self.assertEqual(plan["selected_leaf_count"], len(EXPECTED))
            self.assertEqual({entry["id"] for entry in plan["tests"]}, set(EXPECTED))

    def test_report_ordering_contract_is_explicit(self):
        for token in (
            "NV097_CLEAR_REPORT_VALUE",
            "NV097_SET_ZPASS_PIXEL_COUNT_ENABLE",
            "NV097_GET_REPORT",
            "NV097_SET_CONTEXT_DMA_REPORT",
            "kTimestampSentinel",
            "kValueSentinel",
            "kDoneSentinel",
            "QueueTerminalSemaphore",
            "WaitForTerminalSemaphore",
            "NV097_BACK_END_WRITE_SEMAPHORE_RELEASE",
            "AssertXemuPerfEqual(a0.value, a1.value",
            "AssertXemuPerfEqual(a0.value * 2, a1.value",
            "a0.value == b0.value",
            "XemuPerfAssertion::REPORT_TIMEOUT_A",
            "ReadDmaDescriptor(report_context_b_)",
            "rewrite_observed_pending_",
            "kDescriptorRewriteDelaysUs",
            "BusyWaitMicroseconds(delay_us);",
            "WaitForDmaDataShadow(report_parameter)",
            "kPfifoDmaDataShadowRegister",
            "rewrite_early_attempts_",
            "rewrite_completed_before_attempts_",
            "completed_before_rewrite",
            "kLimitedReportInclusiveLimit",
            "kRangeCanaryBytes",
            "RangeCanariesIntact",
            "XemuPerfAssertion::REPORT_DMA_RANGE_GUARD",
            "performance_eligible",
            "report_query_observations",
        ):
            self.assertIn(token, SOURCE)
        self.assertIn("static_assert(sizeof(ReportRecord) == 16", HEADER)
        self.assertNotIn("kDescriptorRewriteDelayMs", SOURCE)
        self.assertNotIn("WaitForReport", SOURCE)
        for phrase in (
            "report memory directly",
            "DMA-target ownership",
            "dropped, reordered",
            "same RAMIN descriptor",
            "complete 16-byte record",
            "A0/A1/B0/B1",
            "correctness-only, xemu-only",
            "terminal GPU semaphore",
        ):
            self.assertIn(phrase, DOC)

    def test_descriptor_rewrite_has_distinct_controls_and_exact_restore(self):
        body = SOURCE.split(
            "if (scenario == Scenario::DMA_DESCRIPTOR_REWRITE)", 1
        )[1].split("if (scenario == Scenario::DMA_RANGE_GUARD)", 1)[0]
        for token in (
            "QueueReport(0);",
            "ResetRecord(a1);",
            "ResetRecord(b0);",
            "ResetRecord(b1);",
            "QueueReport(sizeof(ReportRecord));",
            "WriteDmaDescriptor(report_context_a_,",
            "ReadDmaDescriptor(report_context_b_));",
            "b1.timestamp == kTimestampSentinel",
            "pending_before_rewrite",
            "shadow_observed",
            "original_report_descriptor_a_",
        ):
            self.assertIn(token, body)
        self.assertLess(body.index("QueueReport(sizeof(ReportRecord));"),
                        body.index("ReadDmaDescriptor(report_context_b_)"))
        self.assertLess(body.index("ReadDmaDescriptor(report_context_b_)"),
                        body.rindex("QueueReport(0);"))

    def test_teardown_quiesces_and_detaches_before_free(self):
        body = SOURCE.split("void ReportQueryTests::Deinitialize()", 1)[1].split(
            "void ReportQueryTests::BindReportContext", 1
        )[0]
        for token in (
            "SetZpassEnabled(false);",
            "BindReportContext(kFullRamDmaContext);",
            "WriteDmaDescriptor(report_context_a_, original_report_descriptor_a_);",
            "QueueTerminalSemaphore();",
            "WaitForTerminalSemaphore();",
            "MmFreeContiguousMemory(report_memory_a_)",
        ):
            self.assertIn(token, body)
        self.assertLess(body.index("WaitForTerminalSemaphore();"),
                        body.index("MmFreeContiguousMemory(report_memory_a_)"))


if __name__ == "__main__":
    unittest.main()
