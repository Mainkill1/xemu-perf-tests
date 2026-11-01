"""Recipe-derived oracles for completed and pending surface readback."""
import importlib.util
import json
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("completion_catalog", ROOT / "utils/test_catalog.py")
catalog = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = catalog
spec.loader.exec_module(catalog)


class SurfaceCompletionReadbackTests(unittest.TestCase):
    def test_independent_routes_keep_the_completed_and_pending_cases_separate(self):
        tests = {test["id"]: test for test in catalog.catalog(catalog.entries())["tests"]}
        for suffix, legacy in [("completed", "XemuCpuReadCompletedSurface"),
                               ("pending", "XemuCpuReadPendingSurface")]:
            self.assertIn(f"surface.cpu_read_{suffix}_surface", tests)
            test = tests[f"surface.cpu_read_{suffix}_surface"]
            self.assertEqual(test["execution"], {"legacy_suite": "SurfaceRendering",
                                                "legacy_test": legacy})
            self.assertEqual(test["revision"], 1)
            self.assertEqual(test["supported_targets"], ["xemu", "xbox"])

    def test_reference_checks_every_word_and_iteration_instead_of_a_captured_image(self):
        self.assertTrue((ROOT / "resources/surface-completion-reference.json").is_file())
        reference = {row["id"]: row for row in json.loads(
            (ROOT / "resources/surface-completion-reference.json").read_text())}
        for suffix, first_color in [("completed", 0xFF102030),
                                    ("pending", 0xFF204080)]:
            checksum = 2166136261
            for iteration in range(22):
                # Actual CPU observation order: completion trigger B, subject A, successor C.
                for color in (0xFF506070, first_color, 0xFF90A0B0):
                    value = color + iteration * 0x010101
                    for _ in range(32 * 32):
                        for byte in struct.pack("<I", value):
                            checksum = ((checksum ^ byte) * 16777619) & 0xFFFFFFFF
            row = reference[f"surface.cpu_read_{suffix}_surface"]
            self.assertEqual(row["sample_count"], 20)
            self.assertEqual(row["warmup_iterations"], 2)
            self.assertEqual(row["metadata"], {
                "kind": "surface_completion_readback", "case": suffix,
                "oracle_status": "PASS", "failure_count": 0,
                "checked_words": 67584, "observed_kat": checksum})
            self.assertNotIn("framebuffer_hash", row)


if __name__ == "__main__":
    unittest.main()
