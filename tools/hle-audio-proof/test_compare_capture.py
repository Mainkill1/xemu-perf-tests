#!/usr/bin/env python3
import struct
import unittest

from compare_capture import compare
from test_analyze_capture import pcm


class CompareTests(unittest.TestCase):
    def test_phase_aligned_capture_matches(self):
        reference = pcm(right_gain=.5)
        shifted = reference[28 * 4:] + reference[:28 * 4]
        result = compare(reference, shifted, .5)
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['max_absolute_difference'], [0, 0])

    def test_changed_sample_is_detected(self):
        reference = pcm(right_gain=.5)
        changed = bytearray(reference)
        offset = 2 * 48000 * 4 + 100 * 4
        value = struct.unpack_from('<h', changed, offset)[0]
        struct.pack_into('<h', changed, offset, value + 20)
        self.assertEqual(compare(reference, bytes(changed), .5)['status'], 'MISMATCH')

    def test_silence_and_short_capture_are_not_admitted(self):
        self.assertEqual(compare(b'', b'', .5)['status'], 'INCOMPLETE')
        self.assertEqual(compare(pcm(silent=True), pcm(silent=True), .5)['status'], 'INCOMPLETE')


if __name__ == '__main__':
    unittest.main()
