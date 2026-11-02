#!/usr/bin/env python3
"""Check loopback gain parity, mismatch detection, and admission rejection."""
import copy
import ctypes.util
import unittest

import openal_loopback_probe as loopback


class LoopbackTests(unittest.TestCase):
    def report(self):
        values = [0, 1, -1, 0x7fffff, -0x800000, 0x400001, -0x400001, 255] * 8
        return {'status': 'PASS', 'program_matches': True,
                'input_words': [value & 0xffffff for value in values],
                'output_words': [(value * gain // divisor) & 0xffffff
                                 for gain, divisor in ((1, 2), (-1, 2), (1, 4))
                                 for value in values],
                'program_sha256': 'fixture-unit-test', 'iso_sha256': 'fixture-unit-test'}

    def test_rejects_unadmitted_and_invalid_words_before_loading_library(self):
        report = self.report()
        report['program_matches'] = False
        self.assertEqual(loopback.probe(report, '/missing/library')['status'], 'INCOMPLETE')
        report['program_matches'] = True
        report['input_words'][0] = 0x1000000
        self.assertEqual(loopback.probe(report, '/missing/library')['status'], 'INVALID')

    def test_real_loopback_and_injected_expected_difference(self):
        library = ctypes.util.find_library('openal')
        if not library:
            self.skipTest('OpenAL library unavailable')
        report = self.report()
        result = loopback.probe(report, library)
        if result['status'] == 'UNSUPPORTED':
            self.skipTest(result['reason'])
        self.assertEqual(result['status'], 'BASELINE_MATCH')
        self.assertEqual([route['compared_words'] for route in result['routes']], [64] * 3)
        self.assertEqual([route['right_channel_nonzero'] for route in result['routes']], [0] * 3)
        changed = copy.deepcopy(report)
        changed['output_words'][65] ^= 1
        result = loopback.probe(changed, library)
        self.assertEqual(result['status'], 'MISMATCH')
        self.assertEqual([route['mismatching_words'] for route in result['routes']], [0, 1, 0])
        self.assertEqual(result['routes'][1]['first_difference']['sample'], 1)


if __name__ == '__main__':
    unittest.main()
