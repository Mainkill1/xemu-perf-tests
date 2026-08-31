#!/usr/bin/env python3
"""Static contracts for unattended suite lifecycle behavior."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPOSITE = (ROOT / "src/tests/game_load_composite_tests.cpp").read_text()
DRIVER = (ROOT / "src/test_driver.cpp").read_text()


class GameLoadLifecycleContractTests(unittest.TestCase):
    def test_audio_stop_is_idempotent(self):
        start = COMPOSITE.index("void GameLoadCompositeTests::StopAudio()")
        end = COMPOSITE.index("uint32_t GameLoadCompositeTests::ValidateStreamingSurface", start)
        body = COMPOSITE[start:end]
        self.assertIn("if (!audio_voices_)", body)
        self.assertEqual(body.count("XAudioPause();"), 1)
        self.assertIn("audio_voices_ = 0;", body)
        self.assertIn("g_audio_voice_count = 0;", body)

    def test_noninteractive_teardown_replaces_result_screen(self):
        start = DRIVER.index("void TestDriver::RunAllTestsNonInteractive()")
        end = DRIVER.index("void TestDriver::OnControllerAdded", start)
        body = DRIVER[start:end]
        self.assertIn("Suite teardown", body)
        self.assertLess(body.index("Suite teardown"), body.index("suite->Deinitialize()"))


if __name__ == "__main__":
    unittest.main()
