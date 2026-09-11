#!/usr/bin/env python3
"""Regression tests for the PR74 native-result checker."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/evidence/pr74-report-bounds-20260910"
CHECKER = EVIDENCE / "check-native-results.py"
RESULTS = EVIDENCE / "native-results.json"

TIMESTAMP_SENTINEL = 0xF00DFACECAFE0123
VALUE_SENTINEL = 0xDEADBEEF
DONE_SENTINEL = 0xA5A55A5A


def load_results():
    return json.loads(RESULTS.read_text())


def cell(data, backend, test_id):
    return next(
        item for item in data["matrix"]["cells"]
        if item["backend"] == backend and item["test_id"] == test_id
    )


def checker_exit_code(data):
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "synthetic-native-results.json"
        path.write_text(json.dumps(data))
        return subprocess.run(
            [sys.executable, str(CHECKER), str(path)],
            cwd=EVIDENCE,
            capture_output=True,
            text=True,
            check=False,
        ).returncode


class Pr74NativeResultsCheckerTests(unittest.TestCase):
    def test_constants_are_pinned_to_guest_source(self):
        source = (ROOT / "src/tests/report_query_tests.cpp").read_text()

        self.assertIn("kTimestampSentinel = UINT64_C(0xF00DFACECAFE0123)", source)
        self.assertIn("kValueSentinel = 0xDEADBEEF", source)
        self.assertIn("kDoneSentinel = 0xA5A55A5A", source)
        self.assertIn("kExpectedDone = 0", source)

    def test_published_records_are_accepted(self):
        self.assertEqual(checker_exit_code(load_results()), 0)

    def test_rejects_published_value_sentinel(self):
        data = load_results()
        cell(data, "opengl", "report_query.single_boundary")["metadata"][
            "records"
        ]["a0"]["value"] = VALUE_SENTINEL

        self.assertNotEqual(checker_exit_code(data), 0)

    def test_rejects_changed_b1_record(self):
        data = load_results()
        cell(data, "opengl", "report_query.single_boundary")["metadata"][
            "records"
        ]["b1"]["done"] = 0

        self.assertNotEqual(checker_exit_code(data), 0)

    def test_rejects_stale_timestamp_when_b1_is_also_changed(self):
        data = load_results()
        records = cell(data, "opengl", "report_query.single_boundary")[
            "metadata"
        ]["records"]
        records["a0"]["timestamp"] = TIMESTAMP_SENTINEL
        records["b1"]["timestamp"] = TIMESTAMP_SENTINEL - 1
        records["b1"]["value"] = VALUE_SENTINEL
        records["b1"]["done"] = DONE_SENTINEL

        self.assertNotEqual(checker_exit_code(data), 0)

    def test_rejects_stale_timestamp(self):
        data = load_results()
        cell(data, "opengl", "report_query.single_boundary")["metadata"][
            "records"
        ]["a0"]["timestamp"] = TIMESTAMP_SENTINEL

        self.assertNotEqual(checker_exit_code(data), 0)

    def test_rejects_test_id_scenario_mismatch(self):
        data = load_results()
        target = cell(data, "opengl", "report_query.single_boundary")
        target["scenario"] = "zero_query"
        target["metadata"]["scenario"] = "zero_query"
        target["metadata"]["records"]["a0"]["value"] = 0

        self.assertNotEqual(checker_exit_code(data), 0)


if __name__ == "__main__":
    unittest.main()
