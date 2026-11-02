#!/usr/bin/env python3
"""Portable boundary, rounding and rejection checks for the native prototype."""
import importlib.util
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location('compare_native', ROOT / 'compare_native.py')
compare_native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compare_native)


class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.worker = Path(cls.directory.name) / 'native'
        subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                        str(ROOT / 'native_gain.c'), '-o', str(cls.worker)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def execute(self, data):
        return subprocess.run([str(self.worker)], input=data, capture_output=True, timeout=5)

    def test_signed_extremes_and_negative_rounding(self):
        values = [0, 1, -1, 0x7fffff, -0x800000, 3, -3, 5] * 8
        result = self.execute(struct.pack('<64I', *(value & 0xffffff for value in values)))
        self.assertEqual(result.returncode, 0)
        output = struct.unpack('<192I', result.stdout)
        expected = [(value * gain // divisor) & 0xffffff
                    for gain, divisor in ((1, 2), (-1, 2), (1, 4)) for value in values]
        self.assertEqual(list(output), expected)
        self.assertEqual((output[2], output[66], output[130]), (0xffffff, 0, 0xffffff))

    def test_rejects_short_trailing_and_high_bits_without_output(self):
        for data in (b'', bytes(255), bytes(257), struct.pack('<64I', *([0x1000000] * 64))):
            with self.subTest(length=len(data)):
                result = self.execute(data)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b'')

    def test_comparator_detects_injected_difference_and_missing_admission(self):
        report = {'status': 'PASS', 'program_matches': True, 'input_words': [0] * 64,
                  'output_words': [0] * 192, 'program_sha256': 'a' * 64, 'iso_sha256': 'b' * 64}
        self.assertEqual(compare_native.compare(report, self.worker)['status'], 'BASELINE_MATCH')
        failed = compare_native.compare(report, self.worker, True)
        self.assertEqual(failed['status'], 'MISMATCH')
        self.assertEqual(failed['first_difference'], {'route': 0, 'sample': 0, 'expected': 0, 'actual': 1})
        report['program_matches'] = False
        self.assertEqual(compare_native.compare(report, self.worker)['status'], 'INCOMPLETE')


if __name__ == '__main__':
    unittest.main()
