#!/usr/bin/env python3
"""Static contract for bounded, visibly distinct guest test failures."""

import unittest
from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / "src/debug_output.cpp").read_text()


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


if __name__ == "__main__":
    unittest.main()
