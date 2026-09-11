#!/usr/bin/env python3
"""Contracts for the restored historical 4,097-draw query-pressure control."""

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class QueryPressureRestorationContractTests(unittest.TestCase):
    def test_catalog_exposes_historical_query_control(self):
        catalog = json.loads((ROOT / "resources/catalog.json").read_text())
        by_id = {item["id"]: item for item in catalog["tests"]}

        control = by_id["query_pressure.repeated_page_4097"]
        self.assertEqual(control["legacy_ids"], ["QueryPressure::query.repeated-page-4097"])
        self.assertEqual(control["execution"], {
            "legacy_suite": "QueryPressure",
            "legacy_test": "query.repeated-page-4097",
        })
        self.assertEqual(control["measurement_class"], "correctness")
        self.assertEqual(control["default_measurement"]["measured_samples"], 1)
        self.assertEqual(control["supported_targets"], ["xemu", "xbox"])
        self.assertEqual(control["tags"], ["gpu", "correctness", "hardware-safe"])
        self.assertIn(
            {"name": "recipe.input", "kind": "hash", "algorithm": "fnv1a32", "scope_version": 1},
            control["observations"],
        )
        self.assertIn(
            {"name": "zpass.accumulated", "kind": "known_answer", "expected": 655424},
            control["observations"],
        )
        self.assertIn(
            {"name": "framebuffer.tile_mismatches", "kind": "known_answer", "expected": 0},
            control["observations"],
        )

    def test_guest_fixture_keeps_the_archived_pressure_boundary(self):
        source = (ROOT / "src/tests/query_pressure_tests.cpp").read_text()
        header = (ROOT / "src/tests/query_pressure_tests.h").read_text()
        main = (ROOT / "src/main.cpp").read_text()
        cmake = (ROOT / "src/CMakeLists.txt").read_text()

        self.assertIn("#include \"tests/query_pressure_tests.h\"", main)
        self.assertIn("REG_TEST(QueryPressureTests)", main)
        self.assertIn("tests/query_pressure_tests.cpp", cmake)
        self.assertIn("tests/query_pressure_tests.h", cmake)
        self.assertIn("class QueryPressureTests : public TestSuite", header)
        for token in (
            "kDraws = 4097",
            "kTiles = 512",
            "kExpectedInputHash = 0xC4DDD0FB",
            "static_assert(kExpectedSamples == 655424)",
            "DMA_CLASS_3",
            "kReportContext = 23",
            "DrainGuestFifo(host_)",
            "Method(NV097_GET_REPORT",
            "report->value == kExpectedSamples",
            "tile_mismatches",
            "\\\"expected_zpass\\\"",
            "\\\"oracle_status\\\"",
        ):
            self.assertIn(token, source)
        pressure_loop = source.split("for (uint32_t draw = 0; draw < kDraws; ++draw) {")[2]
        self.assertLess(pressure_loop.index("DrainGuestFifo(host_)"),
                        pressure_loop.index("host_.DrawArrays"))
        self.assertLess(pressure_loop.index("host_.DrawArrays"),
                        pressure_loop.index("Method(NV097_GET_REPORT"))


if __name__ == "__main__":
    unittest.main()
