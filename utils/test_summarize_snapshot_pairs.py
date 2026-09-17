import copy
import math
import unittest

from summarize_snapshot_pairs import compare_pairs


def fixture():
    rows = []
    for pair, reference, candidate in ((1, 100.0, 90.0), (2, 200.0, 240.0)):
        for role, value in (("B", reference), ("AM", candidate)):
            rows.append({
                "run_id": f"run-{pair}-{role}", "phase": "measured",
                "pair": pair, "renderer": "OPENGL", "build": role,
                "status": "VALID", "source_commit": role,
                "exe_sha256": role, "duration_seconds": 60,
                "metrics": {"cadence_hz": value, "mean_ms": value,
                            "p95_ms": value, "p99_ms": value,
                            "maximum_ms": value},
            })
    return rows


class SnapshotPairTests(unittest.TestCase):
    def test_signs_and_median_of_pair_improvements(self):
        result = compare_pairs(fixture(), 2)
        self.assertIn("OPENGL", result)
        summary = result["OPENGL"]["summary"]
        self.assertAlmostEqual(summary["mean_ms"]["median_improvement_percent"], -5)
        self.assertAlmostEqual(summary["cadence_hz"]["median_improvement_percent"], 5)
        # The pooled-value ratio would be -10%, which is a different statistic.
        self.assertNotEqual(summary["p99_ms"]["median_improvement_percent"], -10)

    def test_requires_all_declared_pairs(self):
        with self.assertRaisesRegex(ValueError, "pairs"):
            compare_pairs(fixture()[:2], 2)

    def test_missing_renderer_is_not_a_complete_campaign(self):
        with self.assertRaisesRegex(ValueError, "renderer"):
            compare_pairs(fixture(), 2, ["OPENGL", "VULKAN"])

    def test_rejects_duplicate_role(self):
        rows = fixture()
        rows.append(copy.deepcopy(rows[0]))
        rows[-1]["run_id"] = "other-id-same-role"
        with self.assertRaisesRegex(ValueError, "duplicate"):
            compare_pairs(rows, 2)

    def test_invalid_measured_run_cannot_disappear(self):
        rows = fixture()
        rows[0]["status"] = "INVALID"
        with self.assertRaisesRegex(ValueError, "invalid"):
            compare_pairs(rows, 2)

    def test_pilot_is_explicitly_excluded(self):
        rows = fixture()
        pilot = copy.deepcopy(rows[0])
        pilot.update(run_id="pilot", phase="pilot", pair=0, status="INVALID")
        rows.append(pilot)
        self.assertEqual(compare_pairs(rows, 2), compare_pairs(fixture(), 2))

    def test_rejects_identity_drift_and_nonfinite_metric(self):
        for field in ("exe_sha256", "source_commit", "duration_seconds"):
            rows = fixture()
            rows[2][field] = "changed"
            with self.subTest(field=field), self.assertRaises(ValueError):
                compare_pairs(rows, 2)
        for value in (math.nan, math.inf, -1, 0):
            rows = fixture()
            rows[0]["metrics"]["p99_ms"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                compare_pairs(rows, 2)


if __name__ == "__main__":
    unittest.main()
