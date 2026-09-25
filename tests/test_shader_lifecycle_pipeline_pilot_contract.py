#!/usr/bin/env python3
"""Static contracts for the first native shader-lifecycle synthetic."""

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "src/tests/shader_lifecycle_tests.cpp"
HEADER_PATH = ROOT / "src/tests/shader_lifecycle_tests.h"


class ShaderLifecyclePipelinePilotContractTests(unittest.TestCase):
    def test_suite_is_native_and_registered(self) -> None:
        source = SOURCE_PATH.read_text(encoding="utf-8")
        header = HEADER_PATH.read_text(encoding="utf-8")
        main = (ROOT / "src/main.cpp").read_text(encoding="utf-8")
        cmake = (ROOT / "src/CMakeLists.txt").read_text(encoding="utf-8")

        self.assertIn("class ShaderLifecycleTests", header)
        self.assertIn("REG_TEST(ShaderLifecycleTests)", main)
        self.assertIn("tests/shader_lifecycle_tests.cpp", cmake)
        self.assertIn("kPipelineJobCapacity = 16", source)
        self.assertIn("kPipelineVariantCount = kPipelineJobCapacity + 1", source)
        self.assertIn("static_assert(kPipelineVariants.size() == kPipelineVariantCount)", source)

    def test_pipeline_identity_changes_without_shader_changes(self) -> None:
        source = SOURCE_PATH.read_text(encoding="utf-8")
        draw_start = source.index("void ShaderLifecycleTests::DrawPipelineVariants")
        draw_end = source.index("\n}", draw_start)
        draw = source[draw_start:draw_end]

        # Color write masks are dynamic state in xemu and therefore cannot
        # provide the distinct fixed-pipeline identities this workload needs.
        self.assertNotIn("variant.color_mask", draw)
        self.assertIn("kAllChannels", draw)
        self.assertIn("variant.source_factor", draw)
        self.assertIn("variant.destination_factor", draw)
        self.assertIn("NV097_SET_BLEND_FUNC_SFACTOR", draw)
        self.assertIn("NV097_SET_BLEND_FUNC_DFACTOR", draw)
        self.assertIn("NV097_SET_BLEND_EQUATION", draw)
        self.assertIn("host_.SetFinalCombiner0Just(TestHost::SRC_DIFFUSE)", draw)
        self.assertNotIn("SetVertexShaderProgram", draw)
        self.assertNotIn("SetShaderStageProgram", draw)

        self.assertIn("AllPipelineVariantsHaveUniqueBlendIdentity()", source)
        self.assertIn(
            "static_assert(AllPipelineVariantsHaveUniqueBlendIdentity())",
            source,
        )

    def test_capacity_and_control_routes_have_separate_launch_plans(self) -> None:
        expected = {
            "shader_lifecycle.pipeline_train": "shader-lifecycle-pipeline-train.json",
            "shader_lifecycle.pipeline_capacity_c_minus_one": "shader-lifecycle-pipeline-c-minus-one.json",
            "shader_lifecycle.pipeline_capacity_c": "shader-lifecycle-pipeline-c.json",
            "shader_lifecycle.pipeline_capacity_c_plus_one": "shader-lifecycle-pipeline-c-plus-one.json",
            "shader_lifecycle.pipeline_identical_replay": "shader-lifecycle-pipeline-identical-replay.json",
            "shader_lifecycle.pipeline_uniform_only": "shader-lifecycle-pipeline-uniform-only.json",
        }
        catalog = json.loads((ROOT / "resources/catalog.json").read_text(encoding="utf-8"))
        descriptors = {entry["id"]: entry for entry in catalog["tests"]}
        for test_id, filename in expected.items():
            self.assertIn(test_id, descriptors)
            descriptor = descriptors[test_id]
            self.assertEqual(descriptor["supported_targets"], ["xemu"])
            self.assertIn("shader-lifecycle", descriptor["tags"])

            plan = json.loads((ROOT / "resources" / filename).read_text(encoding="utf-8"))
            self.assertTrue(plan["settings"]["enable_autorun_immediately"])
            self.assertEqual(plan["settings"]["warmup_iterations"], 0)
            self.assertEqual(plan["settings"]["measurement_iterations_multiplier"], 1)
            self.assertEqual(plan["resolved_plan"]["tests"], [{"id": test_id}])

    def test_documented_acceptance_requires_real_promotion(self) -> None:
        doc = (ROOT / "docs/shader-lifecycle-pipeline-pilot.md").read_text(encoding="utf-8")
        self.assertIn("pipeline-promotion > 0", doc)
        self.assertIn("Windows", doc)
        self.assertIn("Steam Deck/Linux", doc)
        self.assertIn("never pooled", doc)
        self.assertIn("does not prove promotion", doc)


if __name__ == "__main__":
    unittest.main()
