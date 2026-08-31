#!/usr/bin/env python3
"""Static contract for bounded, visibly distinct guest test failures."""

import unittest
from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / "src/debug_output.cpp").read_text()
HOST = (Path(__file__).resolve().parents[1] / "src/test_host.cpp").read_text()
SUITE = (Path(__file__).resolve().parents[1] / "src/tests/test_suite.cpp").read_text()
MAIN = (Path(__file__).resolve().parents[1] / "src/main.cpp").read_text()


class SoftFailureScreenContractTests(unittest.TestCase):
    def test_failure_is_bounded_and_user_advanceable(self):
        start = SOURCE.index("void ShowSoftFailureScreen")
        end = SOURCE.index("inline bool XemuPerfMarkerAvailable", start)
        body = SOURCE[start:end]
        self.assertIn("SOFT TEST FAILURE - NOT HALTED", body)
        self.assertIn("FillFailureBackground", body)
        self.assertIn("GetTickCount() - start < 10000", body)
        self.assertIn("SDL_CONTROLLER_BUTTON_A", body)
        self.assertIn("SDL_CONTROLLERBUTTONUP", body)
        self.assertIn("pb_show_front_screen()", body)
        self.assertNotIn("while (true)", body)

    def test_failure_details_reach_xemu_log(self):
        self.assertIn('DbgPrint("SOFT TEST FAILURE:', SOURCE)
        self.assertIn("expected=%08lx actual=%08lx", SOURCE)

    def test_soft_failure_reaches_record_and_final_verdict(self):
        self.assertIn("bool XemuPerfTestFailed()", SOURCE)
        self.assertIn("RecordSoftTestOutcome", SUITE)
        self.assertIn('"outcome":', HOST)
        self.assertIn("SoftFailureCount() == 0", MAIN)
        self.assertIn('debugPrint("Soft failures: %lu', MAIN)


if __name__ == "__main__":
    unittest.main()
