#!/usr/bin/env python3
"""Portable boundary, rounding and rejection checks for the native prototype."""
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location('compare_native', ROOT / 'compare_native.py')
compare_native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compare_native)
guest_spec = importlib.util.spec_from_file_location('run_guest', ROOT / 'run_guest.py')
run_guest = importlib.util.module_from_spec(guest_spec)
guest_spec.loader.exec_module(run_guest)


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

    def test_cli_shadow_controls_override_inherited_experiment_settings(self):
        inherited = {'KEEP': 'unchanged', 'XEMU_DSP_GAIN_SHADOW': '1',
                     'XEMU_DSP_GAIN_SHADOW_ROUTES': '0', 'XEMU_DSP_GAIN_SHADOW_FAULT': '65'}
        off = run_guest.shadow_environment(inherited, False, 7, None)
        self.assertEqual(off, {'KEEP': 'unchanged'})
        on = run_guest.shadow_environment(inherited, True, 5, None)
        self.assertEqual(on, {'KEEP': 'unchanged', 'XEMU_DSP_GAIN_SHADOW': '1',
                              'XEMU_DSP_GAIN_SHADOW_ROUTES': '5'})
        fault = run_guest.shadow_environment(inherited, True, 7, 0)
        self.assertEqual(fault['XEMU_DSP_GAIN_SHADOW_FAULT'], '0')
        self.assertEqual(inherited['XEMU_DSP_GAIN_SHADOW_FAULT'], '65')

    def test_shadow_stats_cannot_hide_zero_coverage_or_inconsistent_counts(self):
        import copy
        report = {'status': 'BASELINE_MATCH', 'authoritative': 'dsp', 'live_native_commits': 0,
                  'route_mask': 7, 'fault_index': -1, 'admitted_jobs': 1, 'routes': []}
        for name in ('gain_half', 'invert_half', 'gain_quarter'):
            report['routes'].append({'name': name, 'native_calls': 1, 'fallback_calls': 0,
                                     'compared_words': 64, 'matching_words': 64, 'differing_words': 0,
                                     'matched_calls': 1, 'mismatched_calls': 0, 'native_wall_ns': 100,
                                     'first_difference': None})
        run_guest.validate_shadow(report, 7, None)
        ignored_fault = copy.deepcopy(report)
        ignored_fault['fault_index'] = 65
        with self.assertRaises(ValueError):
            run_guest.validate_shadow(ignored_fault, 7, 65)
        empty = copy.deepcopy(report)
        empty.update(status='NO_COMPARISONS', admitted_jobs=0)
        for route in empty['routes']:
            for key in ('native_calls', 'compared_words', 'matching_words', 'matched_calls'):
                route[key] = 0
        snapshots = run_guest.parse_shadow_records([json.dumps(empty), json.dumps(report)], 7, None)
        self.assertEqual(snapshots[-1], report)
        for records in ([], [json.dumps(report), json.dumps(empty)], ['{}', json.dumps(report)],
                        [json.dumps(report), 'invalid-json']):
            with self.subTest(records=records), self.assertRaises(ValueError):
                run_guest.parse_shadow_records(records, 7, None)
        for change in ('no_coverage', 'lost_word', 'wrong_mask', 'live_commit'):
            modified = copy.deepcopy(report)
            if change == 'no_coverage':
                modified['admitted_jobs'] = 0
                for route in modified['routes']:
                    for key in ('native_calls', 'compared_words', 'matching_words', 'matched_calls'):
                        route[key] = 0
            elif change == 'lost_word':
                modified['routes'][0]['matching_words'] = 63
            elif change == 'wrong_mask':
                modified['route_mask'] = 5
            else:
                modified['live_native_commits'] = 1
            with self.subTest(change=change), self.assertRaises(ValueError):
                run_guest.validate_shadow(modified, 7, None)


if __name__ == '__main__':
    unittest.main()
