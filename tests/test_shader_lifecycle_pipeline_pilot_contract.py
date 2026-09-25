#!/usr/bin/env python3
"""Static contracts for the visible learned-fallback readiness synthetic."""

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "src/tests/shader_lifecycle_tests.cpp"
HEADER_PATH = ROOT / "src/tests/shader_lifecycle_tests.h"


class ShaderLifecycleReadinessContractTests(unittest.TestCase):
    def test_suite_is_native_and_registered(self) -> None:
        source = SOURCE_PATH.read_text(encoding="utf-8")
        header = HEADER_PATH.read_text(encoding="utf-8")
        main = (ROOT / "src/main.cpp").read_text(encoding="utf-8")
        cmake = (ROOT / "src/CMakeLists.txt").read_text(encoding="utf-8")

        self.assertIn("class ShaderLifecycleTests", header)
        self.assertIn("REG_TEST(ShaderLifecycleTests)", main)
        self.assertIn("tests/shader_lifecycle_tests.cpp", cmake)
        self.assertIn("kReadinessFamilyCount = 3", source)
        self.assertIn("kReadinessCombinerVariantCount = 2", source)

    def test_reduced_scope_excludes_unqualified_capacity_workload(self) -> None:
        source = SOURCE_PATH.read_text(encoding="utf-8")
        header = HEADER_PATH.read_text(encoding="utf-8")
        catalog = json.loads(
            (ROOT / "resources/catalog.json").read_text(encoding="utf-8")
        )

        self.assertNotIn("kPipelineJobCapacity", source)
        self.assertNotIn("RunPipelineScenario", source)
        self.assertNotIn("RunPipelineScenario", header)
        self.assertFalse(
            any(
                entry["id"].startswith("shader_lifecycle.pipeline_")
                for entry in catalog["tests"]
            )
        )
        self.assertFalse(
            list((ROOT / "resources").glob("shader-lifecycle-pipeline-*.json"))
        )

    def test_visible_readiness_profile_is_small_and_never_omittable(self) -> None:
        source = SOURCE_PATH.read_text(encoding="utf-8")

        self.assertIn("kReadinessFamilyCount = 3", source)
        self.assertIn("kReadinessCombinerVariantCount = 2", source)
        self.assertIn("PRIMITIVE_TRIANGLES", source)
        self.assertIn("PRIMITIVE_TRIANGLE_STRIP", source)
        self.assertIn("PRIMITIVE_QUADS", source)
        self.assertIn("DrawReadinessFamilies", source)
        self.assertIn("ConfigureReadinessCombiner", source)

        readiness_start = source.index(
            "void ShaderLifecycleTests::DrawReadinessFamilies"
        )
        readiness_end = source.index("\n}", readiness_start)
        readiness = source[readiness_start:readiness_end]
        self.assertIn("NV097_SET_COLOR_MASK, kAllChannels", readiness)
        self.assertNotIn("safe_omission", readiness)

        validation_start = source.index(
            "uint32_t ShaderLifecycleTests::ValidateReadinessFamilies"
        )
        validation_end = source.index("\n}", validation_start)
        validation = source[validation_start:validation_end]
        self.assertIn("ASSERT(first_pixel != kBackgroundColor)", validation)
        self.assertIn("ASSERT(second_pixel != kBackgroundColor)", validation)
        self.assertIn("ASSERT(first_pixel == second_pixel)", validation)

    def test_visible_readiness_profiles_have_separate_launch_plans(self) -> None:
        expected = {
            "shader_lifecycle.readiness_train_visible":
                "shader-lifecycle-readiness-train-visible.json",
            "shader_lifecycle.readiness_replay_visible":
                "shader-lifecycle-readiness-replay-visible.json",
            "shader_lifecycle.readiness_identical_replay":
                "shader-lifecycle-readiness-identical-replay.json",
            "shader_lifecycle.readiness_uniform_only":
                "shader-lifecycle-readiness-uniform-only.json",
            "shader_lifecycle.readiness_early_demand":
                "shader-lifecycle-readiness-early-demand.json",
        }
        catalog = json.loads(
            (ROOT / "resources/catalog.json").read_text(encoding="utf-8")
        )
        descriptors = {entry["id"]: entry for entry in catalog["tests"]}

        for test_id, filename in expected.items():
            self.assertIn(test_id, descriptors)
            descriptor = descriptors[test_id]
            self.assertEqual(descriptor["supported_targets"], ["xemu"])
            self.assertIn("shader-readiness", descriptor["tags"])

            plan = json.loads(
                (ROOT / "resources" / filename).read_text(encoding="utf-8")
            )
            self.assertEqual(plan["settings"]["warmup_iterations"], 0)
            self.assertEqual(plan["resolved_plan"]["tests"], [{"id": test_id}])

    def test_visible_readiness_acceptance_is_publication_and_use(self) -> None:
        source = SOURCE_PATH.read_text(encoding="utf-8")
        doc = (ROOT / "docs/shader-lifecycle-pipeline-pilot.md").read_text(
            encoding="utf-8"
        )
        normalized_doc = " ".join(doc.split())

        self.assertIn("kReadinessSpecializationLeadMs = 2000", source)
        self.assertIn("kReadinessVisibleResultHoldMs = 10000", source)
        self.assertRegex(
            source,
            r"kReadinessIdenticalReplay,\s*3,\s*false,\s*"
            r"kReadinessSpecializationLeadMs",
        )
        self.assertIn("Sleep(interpass_delay_ms)", source)
        self.assertIn("Sleep(kReadinessVisibleResultHoldMs)", source)
        self.assertIn("visible, non-omittable readiness profile", normalized_doc)
        self.assertIn(
            "fallback pipeline publication before first demand", normalized_doc
        )
        self.assertIn("actual submitted use", normalized_doc)
        self.assertIn("missing vertex", normalized_doc)
        self.assertIn("missing geometry", normalized_doc)
        self.assertIn("missing fallback fragment", normalized_doc)
        self.assertIn("early-demand", normalized_doc)
        self.assertIn("does not require a promotion event", normalized_doc)


if __name__ == "__main__":
    unittest.main()
