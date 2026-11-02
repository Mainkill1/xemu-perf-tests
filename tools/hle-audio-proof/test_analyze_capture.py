#!/usr/bin/env python3
import math
import struct
import unittest

from analyze_capture import analyze


def pcm(swap=False, silent=False, clipped=False, right_gain=1):
    data = bytearray()
    for i in range(48000 * 3):
        left = 8192 if i % 100 < 50 else -8192
        right = 8192 if i % 50 < 25 else -8192
        right = int(right * right_gain)
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

    def test_asymmetric_right_gain_is_preserved(self):
        self.assertEqual(analyze(pcm(right_gain=.5), .5)['status'], 'PASS')
        self.assertEqual(analyze(pcm(right_gain=1), .5)['status'], 'FAIL')

    def test_constant_adpcm_predictors_and_channel_polarity(self):
        payload = struct.pack('<hh', 4096, -4096) * (48000 * 3)
        swapped = struct.pack('<hh', -4096, 4096) * (48000 * 3)
        self.assertEqual(analyze(payload, signal='adpcm-dc')['status'], 'PASS')
        self.assertEqual(analyze(swapped, signal='adpcm-dc')['status'], 'FAIL')
        self.assertEqual(analyze(bytes(len(payload)), signal='adpcm-dc')['status'], 'FAIL')

    def test_partial_audio_is_incomplete(self):
        self.assertEqual(analyze(b'\0' * 7)['status'], 'INCOMPLETE')
        self.assertEqual(analyze(b'')['status'], 'INCOMPLETE')


if __name__ == '__main__':
    unittest.main()
