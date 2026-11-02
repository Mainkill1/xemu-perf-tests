#!/usr/bin/env python3
import math
import struct
import unittest

from analyze_capture import analyze


def pcm(swap=False, silent=False, clipped=False):
    data = bytearray()
    for i in range(48000 * 3):
        left = 8192 if i % 100 < 50 else -8192
        right = 8192 if i % 50 < 25 else -8192
        if swap:
            left, right = right, left
        if silent:
            left = right = 0
        if clipped:
            left = 32767
        data.extend(struct.pack('<hh', left, right))
    return bytes(data)


class AnalysisTests(unittest.TestCase):
    def test_valid_stereo_fixture_and_channel_isolation(self):
        result = analyze(pcm())
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['consecutive_seconds'], 3)
        self.assertGreater(result['windows'][-1]['left_480'], 10000)
        self.assertGreater(result['windows'][-1]['right_960'], 10000)

    def test_silence_swapped_and_clipped_are_rejected(self):
        for payload in (pcm(silent=True), pcm(swap=True), pcm(clipped=True)):
            self.assertEqual(analyze(payload)['status'], 'FAIL')

    def test_partial_audio_is_incomplete(self):
        self.assertEqual(analyze(b'\0' * 7)['status'], 'INCOMPLETE')
        self.assertEqual(analyze(b'')['status'], 'INCOMPLETE')


if __name__ == '__main__':
    unittest.main()
