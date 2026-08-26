#!/usr/bin/env python3
"""Static contracts for the generated pipeline texture-switch capsule."""

import json
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/tests/pipeline_texture_switch_tests.cpp").read_text()
HEADER = (ROOT / "src/debug_output.h").read_text()
MAIN = (ROOT / "src/main.cpp").read_text()
CMAKE = (ROOT / "src/CMakeLists.txt").read_text()
README = (ROOT / "README.md").read_text()
DOC = (ROOT / "docs/pipeline-texture-switch-workload.md").read_text()

SEED = 0x50545357
WIDTH = 64
HEIGHT = 64
OPERATIONS = 512
TEXTURE_A = 0xFFFF0000
TEXTURE_B = 0xFF0000FF
DIFFUSE = 0xFF00FF00
REPEAT = 0x00010101
CLAMP = 0x00030303
BOX = 0x01012000
TENT = 0x02022000
FNV32_OFFSET = 2166136261
FNV32_PRIME = 16777619
FNV64_OFFSET = 14695981039346656037
FNV64_PRIME = 1099511628211
BOUNDARY_CLEAR = 0xFF202830
CLEAR_BOUNDARIES = 128
CLEAR_TEXTURE_CHANGES = 2
CLEAR_NORMAL_DRAWS = 2
CLEAR_OPERATIONS = 640
CLEAR_TEST_ID = "pipeline.clear-texture-normal"
TEST_IDS = (
    "pipeline.texture-switch",
    "pipeline.shader-negative-control",
)


def fnv32_word(checksum: int, value: int) -> int:
    for byte in struct.pack("<I", value & 0xFFFFFFFF):
        checksum = ((checksum ^ byte) * FNV32_PRIME) & 0xFFFFFFFF
    return checksum


def word_kat(values) -> int:
    checksum = FNV32_OFFSET
    for value in values:
        checksum = fnv32_word(checksum, value)
    return checksum


def texture_kat(color: int) -> int:
    return word_kat([color] * (WIDTH * HEIGHT))


def solid_frame_kat(color: int) -> int:
    checksum = FNV64_OFFSET
    for _ in range(640 * 480):
        for byte in struct.pack("<I", color):
            checksum = ((checksum ^ byte) * FNV64_PRIME) & 0xFFFFFFFFFFFFFFFF
    return checksum


def folded_state(multiplier: int) -> int:
    checksum = SEED ^ 0x1503
    for _ in range(8 * multiplier):
        for value in (0x1A404C43, 0x1503, CLEAR_BOUNDARIES, 0x50C0069D):
            checksum = ((checksum ^ value) * FNV32_PRIME) & 0xFFFFFFFF
    return checksum


class PipelineTextureSwitchContractTests(unittest.TestCase):
    def load(self, name: str) -> dict:
        return json.loads((ROOT / "resources" / name).read_text())

    def test_single_xiso_routes_both_exact_phases(self):
        self.assertIn("REG_TEST(PipelineTextureSwitchTests)", MAIN)
        self.assertIn("tests/pipeline_texture_switch_tests.cpp", CMAKE)
        for resource in (
            "pipeline-texture-switch-fast-smoke.json",
            "pipeline-texture-switch-quick.json",
            "pipeline-texture-switch-sustained.json",
        ):
            config = self.load(resource)
            self.assertTrue(config["settings"]["skip_tests_by_default"])
            self.assertEqual(
                set(config["test_suites"]["PipelineTextureSwitch"]),
                set(TEST_IDS),
            )
        for test_id in TEST_IDS:
            self.assertIn(test_id, SOURCE)
            self.assertIn(test_id, README)
            self.assertIn(test_id, DOC)

    def test_third_phase_has_dedicated_exact_job_selection(self):
        plans = {
            "pipeline-clear-texture-normal-fast-smoke.json": (1, 1, "enqueue"),
            "pipeline-clear-texture-normal-quick.json": (64, 32, "batch_complete"),
            "pipeline-clear-texture-normal-sustained.json": (160, 80, "batch_complete"),
        }
        for resource, expected in plans.items():
            config = self.load(resource)
            self.assertTrue(config["settings"]["skip_tests_by_default"])
            self.assertEqual(
                (
                    config["settings"]["warmup_iterations"],
                    config["settings"]["measurement_iterations_multiplier"],
                    config["settings"]["gpu_completion_mode"],
                ),
                expected,
            )
            self.assertEqual(
                config["test_suites"],
                {
                    "PipelineTextureSwitch": {
                        CLEAR_TEST_ID: {"skipped": False}
                    }
                },
            )
        self.assertIn(CLEAR_TEST_ID, SOURCE)
        self.assertIn(CLEAR_TEST_ID, README)
        self.assertIn(CLEAR_TEST_ID, DOC)

    def test_exact_generated_input_and_backing_kats(self):
        backing_a = texture_kat(TEXTURE_A)
        backing_b = texture_kat(TEXTURE_B)
        input_kat = word_kat(
            (
                SEED,
                WIDTH,
                HEIGHT,
                TEXTURE_A,
                TEXTURE_B,
                backing_a,
                backing_b,
                REPEAT,
                CLAMP,
                BOX,
                TENT,
                OPERATIONS,
            )
        )
        self.assertEqual(backing_a, 0xBDF93DC5)
        self.assertEqual(backing_b, 0xC40ABDC5)
        self.assertEqual(input_kat, 0xA9CA7145)
        for value in (backing_a, backing_b, input_kat):
            literal = f"{value:08X}"
            self.assertIn(literal, SOURCE.upper())
            self.assertIn(literal, DOC.upper())
        self.assertIn("texture_a[pixel] = kTextureAColor", SOURCE)
        self.assertIn("texture_b[pixel] = kTextureBColor", SOURCE)
        self.assertIn("HashWords(texture_a, kTexturePixels)", SOURCE)
        self.assertIn("HashWords(texture_b, kTexturePixels)", SOURCE)

    def test_switch_and_negative_control_paths_are_distinct(self):
        iteration = SOURCE[
            SOURCE.index("void PipelineTextureSwitchTests::RunIteration") :
            SOURCE.index("uint32_t PipelineTextureSwitchTests::ValidatePixels")
        ]
        for required in (
            "NV097_SET_TEXTURE_OFFSET",
            "NV097_SET_TEXTURE_ADDRESS",
            "NV097_SET_TEXTURE_FILTER",
            "selector ? texture_b : texture_a",
            "selector ? kClampAddress : kRepeatAddress",
            "selector ? kTentFilter : kBoxFilter",
            "selector ? TestHost::SRC_DIFFUSE",
            "TestHost::SRC_TEX0",
            "DrawTexturedScreenQuadEx",
        ):
            self.assertIn(required, iteration)
        self.assertIn("kOperationsPerIteration = 512", SOURCE)
        self.assertIn("kTextureStageCount = 1", SOURCE)
        self.assertIn("shader_negative_control ? 0 : total_operations", SOURCE)
        self.assertIn("shader_negative_control ? total_operations : 0", SOURCE)

    def test_exact_pixel_and_framebuffer_oracles(self):
        texture_pixels = word_kat((TEXTURE_A, TEXTURE_B, TEXTURE_A, TEXTURE_B))
        shader_pixels = word_kat((TEXTURE_A, DIFFUSE, TEXTURE_A, DIFFUSE))
        self.assertEqual(texture_pixels, 0xBB0EC8ED)
        self.assertEqual(shader_pixels, 0x08C5E8A1)
        expected_frames = {
            0xFF18405A: 0x8AE05D31FB00C325,
            0xFF4A2038: 0xF110C8BD6338C325,
        }
        for value in (texture_pixels, shader_pixels):
            literal = f"{value:08X}"
            self.assertIn(literal, SOURCE.upper())
            self.assertIn(literal, DOC.upper())
        for color, expected in expected_frames.items():
            self.assertEqual(solid_frame_kat(color), expected)
            self.assertIn(f"{color:08X}", SOURCE.upper())
            self.assertIn(f"{expected:016X}", SOURCE.upper())
            self.assertIn(f"{expected:016X}", DOC.upper())
        self.assertIn("expected_framebuffer_fnv1a64", SOURCE)
        self.assertIn("HashBackBuffer()", SOURCE)

    def test_clear_texture_normal_exact_oracles(self):
        backing_a = texture_kat(TEXTURE_A)
        backing_b = texture_kat(TEXTURE_B)
        input_kat = word_kat(
            (
                SEED,
                0xA9CA7145,
                CLEAR_BOUNDARIES,
                BOUNDARY_CLEAR,
                backing_b,
                backing_a,
                CLEAR_NORMAL_DRAWS,
            )
        )
        pixel_kat = word_kat((TEXTURE_A,) * 4)
        frame_kat = solid_frame_kat(0xFF305060)
        self.assertEqual(input_kat, 0x1A404C43)
        self.assertEqual(pixel_kat, 0x50C0069D)
        self.assertEqual(frame_kat, 0x22BA4F1405CDA325)
        self.assertEqual(folded_state(1), 0x418E6684)
        self.assertEqual(folded_state(32), 0xBF18BC54)
        self.assertEqual(folded_state(80), 0x96C62554)
        for value, width in (
            (input_kat, 8),
            (pixel_kat, 8),
            (frame_kat, 16),
        ):
            literal = f"{value:0{width}X}"
            self.assertIn(literal, SOURCE.upper())
            self.assertIn(literal, DOC.upper())
        self.assertIn("ExpectedClearTextureNormalFinalState", SOURCE)
        self.assertIn("expected_final_state", SOURCE)
        self.assertIn("actual_final_state", SOURCE)

    def test_clear_boundary_order_and_counter_contract(self):
        iteration = SOURCE[
            SOURCE.index(
                "void PipelineTextureSwitchTests::RunClearTextureNormalIteration"
            ) : SOURCE.index(
                "uint32_t PipelineTextureSwitchTests::ValidatePixels"
            )
        ]
        clear = iteration.index("host_.ClearColorRegion(")
        texture_b = iteration.index("NV097_SET_TEXTURE_OFFSET, texture_b")
        first_draw = iteration.index("host_.DrawTexturedScreenQuadEx", texture_b)
        texture_a = iteration.index("NV097_SET_TEXTURE_OFFSET, texture_a", first_draw)
        second_draw = iteration.index("host_.DrawTexturedScreenQuadEx", texture_a)
        self.assertLess(clear, texture_b)
        self.assertLess(texture_b, first_draw)
        self.assertLess(first_draw, texture_a)
        self.assertLess(texture_a, second_draw)
        for literal in (
            "kClearBoundariesPerIteration = 128",
            "kClearTextureChangesPerBoundary = 2",
            "kClearNormalDrawsPerBoundary = 2",
            '\\"expected_vertex_bindings\\":0',
            '\\"expected_pipeline_dirty_clear_binding\\"',
            '\\"expected_pipeline_texture_with_other_dirty\\"',
            '\\"expected_pipeline_texture_only_bypass\\"',
            '\\"PIPELINE_DIRTY_CLEAR_BINDING\\":\\">0\\"',
            '\\"clear_boundary_counts_as_TEXTURE_ONLY_BYPASS\\":false',
            '\\"PIPELINE_TEXTURE_ONLY_BYPASS\\":\\">0 after normal bind\\"',
        ):
            self.assertIn(literal, SOURCE)
        self.assertEqual(
            CLEAR_OPERATIONS,
            CLEAR_BOUNDARIES
            * (1 + CLEAR_TEXTURE_CHANGES + CLEAR_NORMAL_DRAWS),
        )
        self.assertIn("inline_immediate", SOURCE)
        self.assertIn('"texture_stage_count', SOURCE)
        self.assertIn("PIPELINE_DIRTY_CLEAR_BINDING", DOC)
        self.assertIn("each\nequal the emitted boundary count", DOC)
        self.assertIn("counter miss", DOC)

    def test_existing_phase_initialization_semantics_are_unchanged(self):
        initialize = SOURCE[
            SOURCE.index("void PipelineTextureSwitchTests::Initialize()") :
            SOURCE.index("void PipelineTextureSwitchTests::Run(")
        ]
        self.assertNotIn("kClearTextureNormal", initialize)
        self.assertNotIn("kBoundaryClearColor", initialize)

    def test_f1_precedes_f2_and_all_correctness_reads(self):
        run = SOURCE[SOURCE.index("void PipelineTextureSwitchTests::Run(") :]
        profile = run.index("Profile(recipe.test_name")
        sync = run.index("SynchronizeCorrectness(host_);", profile)
        backing = run.index("HashWords(texture_a, kTexturePixels)", sync)
        pixels = run.index("ValidatePixels(recipe)", backing)
        self.assertLess(profile, sync)
        self.assertLess(sync, backing)
        self.assertLess(backing, pixels)
        self.assertIn("F1 has already been emitted", run[profile:sync])
        self.assertIn("EmitXemuPerfHeartbeat()", SOURCE)
        self.assertIn("kHeartbeatInterval = 32", SOURCE)
        for assertion in (
            "PIPELINE_TEXTURE_INPUT = 0x150",
            "PIPELINE_TEXTURE_BACKING = 0x151",
            "PIPELINE_TEXTURE_SURFACE = 0x152",
            "PIPELINE_TEXTURE_FINAL = 0x153",
            "PIPELINE_TEXTURE_FRAMEBUFFER = 0x154",
        ):
            self.assertIn(assertion, HEADER)

    def test_duration_contract_uses_seconds_and_fixed_control_work(self):
        smoke = self.load("pipeline-texture-switch-fast-smoke.json")["settings"]
        quick = self.load("pipeline-texture-switch-quick.json")["settings"]
        formal = self.load("pipeline-texture-switch-sustained.json")["settings"]
        self.assertEqual(
            (smoke["warmup_iterations"], smoke["measurement_iterations_multiplier"]),
            (1, 1),
        )
        self.assertEqual(
            (quick["warmup_iterations"], quick["measurement_iterations_multiplier"]),
            (128, 64),
        )
        self.assertEqual(
            (formal["warmup_iterations"], formal["measurement_iterations_multiplier"]),
            (320, 160),
        )
        self.assertEqual(smoke["gpu_completion_mode"], "enqueue")
        self.assertEqual(quick["gpu_completion_mode"], "batch_complete")
        self.assertEqual(formal["gpu_completion_mode"], "batch_complete")
        for phrase in (
            "2 seconds of warmup plus 8 seconds",
            "at least 5 seconds plus 20 seconds",
            "Never calibrate the candidate",
            "short smoke",
        ):
            self.assertIn(phrase, DOC)

    def test_oracle_provenance_and_metadata_are_explicit(self):
        self.assertIn('\\"oracle_provenance\\":\\"REGRESSION_ONLY\\"', SOURCE)
        for field in (
            "texture_stage_count",
            "phase_count",
            "total_operations",
            "texture_switches",
            "sampler_changes",
            "address_changes",
            "shader_state_writes",
            "backing_kat",
            "rendered_pixel_kat",
            "expected_final_state",
            "actual_final_state",
        ):
            self.assertIn(field, SOURCE)
        self.assertIn("retail Xbox", DOC)


if __name__ == "__main__":
    unittest.main()
