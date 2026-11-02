#!/usr/bin/env python3
import importlib.util
import copy
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('bench_gain', Path(__file__).with_name('bench_gain.py'))
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


class BenchmarkTests(unittest.TestCase):
    def test_balanced_order_and_normalized_metrics(self):
        self.assertEqual(bench.balanced_order(2), ['dsp', 'native', 'native', 'dsp',
                                                 'native', 'dsp', 'dsp', 'native'])
        rows = [{'mode': mode, 'blocks': 10, 'wall_ns': wall, 'cpu_ns': cpu,
                 'peak_rss_kib': 100, 'output_words_checked': 1920,
                 'dma_words_checked': 1920, 'status': 'MATCH',
                 'semantic_gain_results': 1920, 'exports': 10, 'exported_bytes': 7680,
                 'dsp_instructions_per_block': 588 if mode == 'dsp' else 0,
                 'dsp_route_instructions': [193] * 3 if mode == 'dsp' else [0] * 3}
                for mode, wall, cpu in [('dsp', 1000, 800), ('native', 500, 400)]]
        result = bench.summarize(rows)
        self.assertEqual(result['dsp']['median_cpu_ns_per_block'], 80)
        self.assertEqual(result['native']['median_cpu_ns_per_block'], 40)
        self.assertEqual(result['cpu_improvement_percent'], 50)
        self.assertEqual(result['wall_improvement_percent'], 50)
        self.assertEqual(result['dsp']['median_one_core_cpu_percent'], 80)
        for field, value in (('exports', 0), ('semantic_gain_results', 0),
                             ('dsp_instructions_per_block', 0), ('wall_ns', 0)):
            bad = copy.deepcopy(rows)
            bad[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                bench.summarize(bad)

    def test_rejects_failed_missing_or_unequal_work(self):
        for rows in ([], [{'mode': 'dsp', 'status': 'MISMATCH'}],
                     [{'mode': 'dsp', 'status': 'MATCH', 'blocks': 0}]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                bench.summarize(rows)

    @unittest.skipUnless(os.environ.get('DSP_GAIN_BENCH'), 'linked DSP benchmark not supplied')
    def test_linked_worker_rejects_corruption_and_counts_real_work(self):
        report = json.loads(Path(os.environ['DSP_GAIN_GUEST_REPORT']).read_text())
        with tempfile.TemporaryDirectory() as directory:
            files = bench.prepare(report, Path(__file__).with_name('program.h'), Path(directory))
            for mode in ('dsp', 'native'):
                command = [os.environ['DSP_GAIN_BENCH'], mode, *(str(file) for file in files), '3', '2']
                completed = subprocess.run(command, capture_output=True, text=True, timeout=30)
                row = json.loads(completed.stdout)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual(row['status'], 'MATCH')
                self.assertEqual(row['exports'], 3)
                self.assertEqual(row['output_words_checked'], 576)
                self.assertEqual(row['dsp_route_instructions'], [193] * 3 if mode == 'dsp' else [0] * 3)
                expected = files[2].read_bytes()
                files[2].write_bytes(bytes([expected[0] ^ 1]) + expected[1:])
                rejected = subprocess.run(command, capture_output=True, text=True, timeout=30)
                self.assertEqual(rejected.returncode, 1)
                self.assertEqual(json.loads(rejected.stdout)['status'], 'MISMATCH')
                files[2].write_bytes(expected)
            original = files[1].read_bytes()
            files[1].write_bytes(original[:-1])
            rejected = subprocess.run(command, capture_output=True, text=True, timeout=30)
            self.assertEqual(rejected.returncode, 2)
            self.assertEqual(json.loads(rejected.stdout)['status'], 'INVALID')


if __name__ == '__main__':
    unittest.main()
