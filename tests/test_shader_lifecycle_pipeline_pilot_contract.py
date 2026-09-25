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

    def test_capacity_cells_are_safe_to_omit_but_keep_a_visible_oracle(self) -> None:
        source = SOURCE_PATH.read_text(encoding="utf-8")

        self.assertIn(
            "kPipelineJobCapacity + 1, 2, false, true", source
        )
        self.assertIn("safe_omission ? 0 : kAllChannels", source)
        self.assertIn("DrawVisibleSentinel", source)
        self.assertIn("ASSERT(pixel == kBackgroundColor)", source)
        self.assertIn("ASSERT(ReadPixel(kSentinelX, kSentinelY) !=", source)

        doc = (ROOT / "docs/shader-lifecycle-pipeline-pilot.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("side-effect-free", doc)
        self.assertIn("visible sentinel", doc)
        self.assertIn("The second pass revisits every capacity", doc)

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
        doc = (ROOT / "docs/shader-lifecycle-pipeline-pilot.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("visible, non-omittable readiness profile", doc)
        self.assertIn("fallback pipeline publication before first demand", doc)
        self.assertIn("actual submitted use", doc)
        self.assertIn("missing vertex", doc)
        self.assertIn("missing geometry", doc)
        self.assertIn("missing fallback fragment", doc)
        self.assertIn("early-demand", doc)
        self.assertIn("does not require a promotion event", doc)


if __name__ == "__main__":
    unittest.main()
