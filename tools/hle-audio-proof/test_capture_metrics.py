#!/usr/bin/env python3
import os
import unittest

from run_capture import process_sample


class MetricsTests(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
