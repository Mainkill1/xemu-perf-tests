import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class TransientBufferGrowthContractTests(unittest.TestCase):
    def test_workload_is_registered_and_emits_required_boundaries(self) -> None:
        source = (
            ROOT / "src/tests/vertex_buffer_allocation_tests.cpp"
        ).read_text(encoding="utf-8")
        header = (
            ROOT / "src/tests/vertex_buffer_allocation_tests.h"
        ).read_text(encoding="utf-8")

        self.assertIn('kRisingTransientGrowthTest[] =', source)
        self.assertIn('"XemuRisingTransientBufferGrowth"', source)
        self.assertIn("TestRisingTransientBufferGrowth();", source)
        self.assertIn("void TestRisingTransientBufferGrowth();", header)
        self.assertIn("kTransientInitialCapacityBytes", source)
        self.assertIn("kGrowthSmallDrawBytes", source)
        self.assertIn("static_assert(kGrowthExactFillBytes ==", source)
        self.assertIn("SubmitTransientGrowthPhase", source)
        self.assertIn("large_jump", source)

    def test_catalog_marks_workload_as_xemu_only_correctness(self) -> None:
        catalog = json.loads(
            (ROOT / "resources/catalog.json").read_text(encoding="utf-8")
        )
        [entry] = [
            item
            for item in catalog["tests"]
            if item["id"] == "vertex_buffer_allocation.rising_transient_growth"
        ]
        self.assertEqual(
            entry["legacy_ids"],
            ["Vertex buffer allocation::XemuRisingTransientBufferGrowth"],
        )
        self.assertEqual(entry["supported_targets"], ["xemu"])
        self.assertEqual(entry["measurement_class"], "correctness")

        plan = json.loads(
            (ROOT / "resources/transient-buffer-growth.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(plan["settings"]["warmup_iterations"], 0)
        self.assertEqual(
            plan["settings"]["measurement_iterations_multiplier"], 1
        )
        self.assertEqual(
            plan["resolved_plan"]["tests"],
            [{"id": "vertex_buffer_allocation.rising_transient_growth"}],
        )


if __name__ == "__main__":
    unittest.main()
