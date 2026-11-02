#!/usr/bin/env python3
"""Check the DSP/DMA fixture's externally selectable audio engine."""
from pathlib import Path
import importlib.util
import subprocess
import sys
import unittest


class AudioEngineCliTest(unittest.TestCase):
    def test_hle_engine_is_advertised(self):
        runner = Path(__file__).with_name('run_guest.py')
        output = subprocess.check_output([sys.executable, str(runner), '--help'], text=True)
        self.assertIn('--audio-engine', output)
        self.assertIn('hle', output)

    def test_guest_failure_finishes_without_a_dsp_completion_marker(self):
        runner = Path(__file__).with_name('run_guest.py')
        spec = importlib.util.spec_from_file_location('dsp_io_guest', runner)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertFalse(module.mailbox_terminal([0, 0xbad, 0, 0], False))
        self.assertTrue(module.mailbox_terminal([0, 0xbad, 0, 0], True))
        self.assertFalse(module.mailbox_terminal([0, 0x600d, 0, 0], True))
        self.assertTrue(module.mailbox_terminal([0x51d00d, 0x600d, 0, 0], True))
        self.assertTrue(module.mailbox_terminal([0x51d00d, 0xbad, 0, 0], False))


if __name__ == '__main__':
    unittest.main()
