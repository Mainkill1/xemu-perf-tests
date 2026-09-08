from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "utils"))
import oracle_validation as oracle


class FunctionalEligibilityTests(unittest.TestCase):
    def record(self, framebuffer: str, tile: str, *, eligible: bool = False) -> dict:
        metadata = {
            "work_checksum": "65c0b7e5",
            "result_checksum": "1a4ff923",
            "source_kat": "0ea3ddc5",
            "tile_center_kat": tile,
            "oracle_status": "PASS",
        }
        if not eligible:
            metadata.update(
                {
                    "oracle_applicable": False,
                    "framebuffer_comparison_eligible": False,
                    "framebuffer_comparison_reason": (
                        "unsynchronized writes have no defined source generation"
                    ),
                }
            )
        return {
            "name": "Suite::Queued",
            "iterations": 8,
            "sample_count": 8,
            "measurement_iterations_multiplier": 1,
            "warmup_iterations": 0,
            "gpu_completion_mode": "per_iteration",
            "framebuffer_fnv1a64": framebuffer,
            "metadata": metadata,
        }

    def report(self, record: dict, observation: str) -> dict:
        return oracle.build_report(
            [record],
            guest_image_sha256="1" * 64,
            job_config={"fixed": True},
            source_backend="vulkan",
            source_type="XEMU",
            observation_id=observation,
            surface_scale=1,
        )

    def test_ineligible_framebuffer_and_rendered_kat_do_not_change_functional_id(self):
        first = self.report(self.record("1" * 16, "2" * 8), "first")
        second = self.report(self.record("3" * 16, "4" * 8), "second")
        self.assertEqual(first["functional_id"], second["functional_id"])
        normalized = first["records"][0]
        self.assertEqual(
            normalized["hashes"],
            {
                "work_checksum": "65c0b7e5",
                "result_checksum": "1a4ff923",
                "kats": {"source_kat": "0ea3ddc5"},
            },
        )
        self.assertEqual(
            normalized["comparison_policy"]["excluded_observations"],
            ["framebuffer_fnv1a64", "kats.tile_center_kat"],
        )

    def test_ledger_records_scoped_exclusion_but_still_checks_work(self):
        first = self.report(self.record("1" * 16, "2" * 8), "first")
        second_record = self.record("3" * 16, "4" * 8)
        second = self.report(second_record, "second")
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "ledger.json"
            oracle.update_determinism_ledger(ledger, first)
            result = oracle.update_determinism_ledger(ledger, second)
            self.assertEqual(len(result["excluded_ineligible_observations"]), 1)
            second_record["metadata"]["work_checksum"] = "deadbeef"
            changed_work = self.report(second_record, "changed-work")
            with self.assertRaises(oracle.SameBackendNondeterminism):
                oracle.update_determinism_ledger(ledger, changed_work)

    def test_eligible_framebuffer_difference_remains_a_hard_failure(self):
        first = self.report(self.record("1" * 16, "2" * 8, eligible=True), "first")
        second = self.report(self.record("3" * 16, "2" * 8, eligible=True), "second")
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "ledger.json"
            oracle.update_determinism_ledger(ledger, first)
            with self.assertRaises(oracle.SameBackendNondeterminism):
                oracle.update_determinism_ledger(ledger, second)


class DiagnosticCountTests(FunctionalEligibilityTests):
    def record(self, framebuffer="1" * 16, tile="2" * 8, *, eligible=False):
        record = super().record(framebuffer, tile, eligible=eligible)
        record["name"] = "GameLoadComposite::10-S3tcSyncFactor-02-Dxt1SameAddressQueued"
        record["metadata"]["oracle_provenance"] = "regression_only"
        record["metadata"]["oracle_failure_count"] = 14
        if not eligible:
            record["metadata"]["framebuffer_comparison_reason"] = (
                "unsynchronized same-address writes have no defined per-draw source generation"
            )
        return record

    def pair(self, *, eligible=False, field="oracle_failure_count", value=13):
        first = self.record(eligible=eligible)
        second = self.record(eligible=eligible)
        second["metadata"][field] = value
        return self.report(first, "one"), self.report(second, "two")

    def test_inapplicable_count_consensus_and_candidate_preserve_raw_evidence(self):
        import copy
        first, second = self.pair()
        original = copy.deepcopy([first, second])
        consensus = oracle.build_consensus([first, second])
        self.assertEqual(oracle.validate_against_oracle(second, consensus)["status"], "PASSED")
        self.assertEqual([first, second], original)
        self.assertEqual(first["records"][0]["internal_oracle"]["failure_count"], 14)

    def test_eligible_count_remains_compared_with_precise_reason(self):
        first, second = self.pair(eligible=True)
        with self.assertRaisesRegex(oracle.SameBackendNondeterminism, "internal_oracle.failure_count"):
            oracle.build_consensus([first, second])

    def test_deterministic_checksum_still_fails(self):
        first, second = self.pair(field="work_checksum", value="deadbeef")
        with self.assertRaisesRegex(oracle.SameBackendNondeterminism, "hashes.work_checksum"):
            oracle.build_consensus([first, second])

    def test_explicit_failure_cannot_become_passing_consensus(self):
        first, second = self.pair(field="oracle_status", value="FAIL")
        with self.assertRaises(oracle.OracleValidationError):
            oracle.build_consensus([second, self.report(self.record(), "three")])

    def test_unrelated_test_diagnostic_is_not_excluded(self):
        a, b = self.record(), self.record()
        a["name"] = b["name"] = "Other::Queued"
        b["metadata"]["oracle_failure_count"] = 13
        with self.assertRaises(oracle.SameBackendNondeterminism):
            oracle.build_consensus([self.report(a, "a"), self.report(b, "b")])

    def test_tampered_sealed_report_is_rejected_before_projection(self):
        first, second = self.pair()
        second["records"][0]["internal_oracle"]["failure_count"] = 99
        with self.assertRaisesRegex(oracle.OracleValidationError, "functional_id"):
            oracle.build_consensus([first, second])


    def test_rgba8_queued_count_also_uses_the_inspected_contract(self):
        a, b = self.record(), self.record()
        a["name"] = b["name"] = "GameLoadComposite::10-S3tcSyncFactor-06-Rgba8SameAddressQueued"
        b["metadata"]["oracle_failure_count"] = 15
        oracle.build_consensus([self.report(a, "a"), self.report(b, "b")])

    def test_source_kat_difference_remains_a_failure(self):
        first, second = self.pair(field="source_kat", value="deadbeef")
        with self.assertRaisesRegex(oracle.SameBackendNondeterminism, "source_kat"):
            oracle.build_consensus([first, second])

    def test_all_failed_reports_cannot_create_consensus(self):
        a, b = self.record(), self.record()
        a["metadata"]["oracle_status"] = b["metadata"]["oracle_status"] = "FAIL"
        with self.assertRaisesRegex(oracle.OracleValidationError, "status is FAIL"):
            oracle.build_consensus([self.report(a, "a"), self.report(b, "b")])

    def test_eligible_pixels_fail_consensus_and_candidate_validation(self):
        a = self.report(self.record(eligible=True), "a")
        b = self.report(self.record(eligible=True), "b")
        changed = self.report(self.record("3" * 16, eligible=True), "changed")
        consensus = oracle.build_consensus([a, b])
        with self.assertRaisesRegex(oracle.OracleValidationError, "framebuffer_fnv1a64"):
            oracle.validate_against_oracle(changed, consensus)
        with self.assertRaises(oracle.SameBackendNondeterminism):
            oracle.build_consensus([a, changed])

    def test_missing_or_changed_exclusion_contract_is_not_ignored(self):
        for key, value in (("oracle_provenance", "other"),
                           ("framebuffer_comparison_reason", "other"),
                           ("oracle_applicable", True)):
            with self.subTest(key=key):
                a, b = self.record(), self.record()
                a["metadata"][key] = b["metadata"][key] = value
                b["metadata"]["oracle_failure_count"] = 13
                with self.assertRaises(oracle.SameBackendNondeterminism):
                    oracle.build_consensus([self.report(a, "a"), self.report(b, "b")])

    def test_cli_writes_new_evidence_and_refuses_overwrite(self):
        import subprocess
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = self.pair()
            a, b = root / "a.json", root / "b.json"
            oracle.write_json(a, first)
            oracle.write_json(b, second)
            before = (a.read_bytes(), b.read_bytes())
            cmd = [sys.executable, str(Path(oracle.__file__).with_name("revalidate_oracles.py")),
                   "--baseline", str(a), str(b), "--candidate", str(b),
                   "--output", str(root / "out")]
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("output already exists", result.stderr)
            self.assertEqual((a.read_bytes(), b.read_bytes()), before)


if __name__ == "__main__":
    unittest.main()
