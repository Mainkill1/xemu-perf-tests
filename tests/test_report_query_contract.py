#!/usr/bin/env python3
"""Static contracts for the ZPASS report-query capsule."""

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/tests/report_query_tests.cpp").read_text()
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
            self.assertIn("report", descriptor["tags"])
            self.assertIn(legacy_test, SOURCE)

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
            "WaitForReport",
            "AssertXemuPerfEqual(a0.value, a1.value",
            "AssertXemuPerfEqual(a0.value * 2, a1.value",
            "a0.value == b0.value",
            "XemuPerfAssertion::REPORT_TIMEOUT_A",
            "pb_set_dma_address(&report_context_a_, report_memory_b_",
            "kLimitedReportInclusiveLimit",
            "XemuPerfAssertion::REPORT_DMA_RANGE_GUARD",
        ):
            self.assertIn(token, SOURCE)
        for phrase in (
            "report memory directly",
            "DMA-target ownership",
            "dropped, reordered, or mis-targeted reports",
            "same RAMIN descriptor",
            "complete 16-byte record",
        ):
            self.assertIn(phrase, DOC)


if __name__ == "__main__":
    unittest.main()
