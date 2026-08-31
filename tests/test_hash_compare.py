import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "utils/hash_compare.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("hash_compare", TOOL)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class HashCompareTests(unittest.TestCase):
    def setUp(self):
        self.module = load_tool()
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, data):
        path = self.root / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_zero_hash_checks_are_unverified_and_fail(self):
        baseline = self.write("baseline.json", {"records": [{"name": "test.a"}]})
        candidate = self.write("candidate.json", [{"name": "test.a"}])

        report = self.module.compare_runs(baseline, [candidate])

        self.assertEqual(report["verdict"], "FAIL")
        self.assertEqual(report["comparisons"][0]["verdict"], "UNVERIFIED")
        self.assertEqual(report["comparisons"][0]["checked_hashes"], 0)
        completed = subprocess.run(
            [sys.executable, str(TOOL), str(baseline), str(candidate)],
            text=True, capture_output=True, check=False)
        self.assertEqual(completed.returncode, 1)
        self.assertIn("VERDICT UNVERIFIED checked=0", completed.stdout)

    def test_compares_top_level_and_metadata_hashes(self):
        baseline = self.write("baseline.json", {"records": [{
            "id": "test.a",
            "framebuffer_fnv1a64": "ABCD",
            "metadata": {"work_checksum": "12", "result_checksum": "34"},
        }]})
        candidate = self.write("candidate.json", [{
            "id": "test.a",
            "framebuffer_fnv1a64": "abcd",
            "metadata": json.dumps({"work_checksum": "12", "result_checksum": "34"}),
        }])

        report = self.module.compare_runs(baseline, [candidate])

        comparison = report["comparisons"][0]
        self.assertEqual(report["verdict"], "PASS")
        self.assertEqual(comparison["checked_hashes"], 3)
        self.assertEqual(comparison["mismatched_hashes"], 0)
        self.assertTrue(all(item["match"] for item in comparison["records"][0]["hashes"].values()))

    def test_mismatch_is_human_readable_and_nonzero(self):
        baseline = self.write("baseline.json", [{
            "name": "test.a", "framebuffer_fnv1a64": "aa",
            "work_checksum": "bb", "result_checksum": "cc",
        }])
        candidate = self.write("candidate.json", {"results": [{
            "name": "test.a", "framebuffer_fnv1a64": "bad",
            "work_checksum": "bb", "result_checksum": "cc",
        }]})

        completed = subprocess.run(
            [sys.executable, str(TOOL), str(baseline), str(candidate)],
            text=True, capture_output=True, check=False)

        self.assertEqual(completed.returncode, 1)
        self.assertIn("test.a framebuffer=0 work=1 result=1", completed.stdout)
        self.assertIn("VERDICT FAIL checked=3 mismatch=1", completed.stdout)

    def test_one_baseline_compares_many_candidates_and_writes_json(self):
        record = {"name": "test.a", "framebuffer_fnv1a64": "aa"}
        baseline = self.write("baseline.json", [record])
        good = self.write("good.json", [record])
        bad = self.write("bad.json", [{"name": "test.a", "framebuffer_fnv1a64": "bb"}])
        output = self.root / "report.json"

        completed = subprocess.run([
            sys.executable, str(TOOL), str(baseline), str(good), str(bad),
            "--json-out", str(output),
        ], text=True, capture_output=True, check=False)

        self.assertEqual(completed.returncode, 1)
        report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual([item["verdict"] for item in report["comparisons"]],
                         ["PASS", "FAIL"])

    def test_directory_prefers_normalized_results(self):
        run = self.root / "run"
        run.mkdir()
        (run / "summary.json").write_text(
            json.dumps({"records": [{"name": "wrong"}]}), encoding="utf-8")
        (run / "normalized-results.json").write_text(
            json.dumps([{"name": "right", "framebuffer_fnv1a64": "aa"}]),
            encoding="utf-8")

        source, records = self.module.load_run(run)

        self.assertEqual(source.name, "normalized-results.json")
        self.assertEqual(set(records), {"right"})

    def test_summary_and_normalized_result_use_shared_record_name(self):
        baseline = self.write("summary.json", {"records": [{
            "name": "Suite::Case", "framebuffer_fnv1a64": "aa",
        }]})
        candidate = self.write("normalized-results.json", [{
            "id": "suite.case", "name": "Suite::Case",
            "framebuffer_fnv1a64": "aa",
        }])

        report = self.module.compare_runs(baseline, [candidate])

        self.assertEqual(report["verdict"], "PASS")
        self.assertEqual(report["comparisons"][0]["checked_hashes"], 1)

    def test_missing_and_extra_records_fail(self):
        baseline = self.write("baseline.json", [
            {"name": "test.a", "framebuffer_fnv1a64": "aa"},
            {"name": "test.b", "framebuffer_fnv1a64": "bb"},
        ])
        candidate = self.write("candidate.json", [
            {"name": "test.a", "framebuffer_fnv1a64": "aa"},
            {"name": "test.c", "framebuffer_fnv1a64": "cc"},
        ])

        comparison = self.module.compare_runs(baseline, [candidate])["comparisons"][0]

        self.assertEqual(comparison["verdict"], "FAIL")
        self.assertEqual(comparison["missing_records"], ["test.b"])
        self.assertEqual(comparison["extra_records"], ["test.c"])


if __name__ == "__main__":
    unittest.main()
