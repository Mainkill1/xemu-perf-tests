#!/usr/bin/env python3
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from run_capture import copy_private_images, process_sample, expected_sentinels


class MetricsTests(unittest.TestCase):
    def test_sentinel_expectations_distinguish_old_and_hybrid_hle(self):
        self.assertEqual(expected_sentinels(2, False, False), (0, 0))
        self.assertEqual(expected_sentinels(2, False, True), (0x123456, 0x123456))
        self.assertEqual(expected_sentinels(2, True, True), (0x123456, 0))
        self.assertEqual(expected_sentinels(1, False, False), (0x123456, 0x123456))

    def test_samples_running_process_cpu_and_memory(self):
        before = process_sample(os.getpid())
        for _ in range(200000):
            sum(range(10))
        after = process_sample(os.getpid())
        self.assertGreaterEqual(after['cpu_ticks'], before['cpu_ticks'])
        self.assertGreater(after['rss_kib'], 0)
        self.assertGreaterEqual(after['peak_rss_kib'], after['rss_kib'])

    def test_missing_process_is_not_a_valid_measurement(self):
        with self.assertRaises(FileNotFoundError):
            process_sample(99999999)

    def test_failed_owned_hdd_copy_is_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            source.write_bytes(b'fixture')
            private = root / 'private'
            private.mkdir()
            files = {'bootrom_path': source, 'flashrom_path': source,
                     'eeprom_path': source, 'hdd_path': root / 'missing'}
            with self.assertRaises(subprocess.CalledProcessError):
                copy_private_images(files, private)
            self.assertFalse((private / 'hdd_path').exists())
            self.assertEqual(source.read_bytes(), b'fixture')


if __name__ == '__main__':
    unittest.main()
