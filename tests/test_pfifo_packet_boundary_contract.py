#!/usr/bin/env python3
"""Contracts for xemu-only PFIFO packet boundary coverage."""

import json
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/tests/pfifo_packet_boundary_tests.cpp").read_text()
MAIN = (ROOT / "src/main.cpp").read_text()
RUNTIME_CONFIG = (ROOT / "src/runtime_config.cpp").read_text()
CMAKE = (ROOT / "src/CMakeLists.txt").read_text()
DOC = (ROOT / "docs/pfifo-packet-boundary.md").read_text()
README = (ROOT / "README.md").read_text()

LEGACY_IDS = (
    "pfifo.boundary-array-element16",
    "pfifo.boundary-array-element32",
    "pfifo.boundary-inline-array",
    "pfifo.incrementing-inline-fallback",
)
STABLE_IDS = (
    "pfifo_packet_boundary.array_element16_overflow",
    "pfifo_packet_boundary.array_element32_overflow",
    "pfifo_packet_boundary.inline_array_overflow",
    "pfifo_packet_boundary.incrementing_inline_fallback",
)


def solid_hash(color: int) -> int:
    value = 14695981039346656037
    for _ in range(640 * 480):
        for byte in struct.pack("<I", color):
            value = ((value ^ byte) * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return value


class PfifoPacketBoundaryContractTests(unittest.TestCase):
    def test_suite_is_registered_once(self):
        self.assertEqual(MAIN.count("REG_TEST(PfifoPacketBoundaryTests)"), 1)
        self.assertIn("tests/pfifo_packet_boundary_tests.cpp", CMAKE)
        self.assertIn("tests/pfifo_packet_boundary_tests.h", CMAKE)

    def test_boundary_arithmetic_and_recovery_sequence(self):
        capacity = 0x07FFFF
        self.assertEqual(((capacity - 1) // 2) * 2, capacity - 1)
        self.assertEqual((capacity - 1) + 2, capacity + 1)
        for literal in (
            "kXemuMaxBatchLength = 0x07FFFF",
            "(kXemuMaxBatchLength - 1) / 2",
            "kXemuMaxBatchLength - 1",
            "recipe.crossing_words",
            "recipe.exact_tail_method",
            "NV2A_SUPPRESS_COMMAND_INCREMENT(method)",
        ):
            self.assertIn(literal, SOURCE)
        self.assertIn("PushPacket(recipe.exact_tail_method, 1", SOURCE)
        self.assertGreaterEqual(SOURCE.count("PushPacket(recipe.exact_tail_method, 1"), 2)

    def test_incrementing_fallback_is_a_real_incrementing_packet(self):
        start = SOURCE.index("void PfifoPacketBoundaryTests::RunIncrementingFallback")
        body = SOURCE[start:]
        self.assertIn("PushPacket(NV097_INLINE_ARRAY, 2", body)
        self.assertIn("false", body)
        self.assertIn("expected_first_method_consumed_words", body)

    def test_literal_frame_hashes(self):
        expected = {
            0xFF341610: 0x4D1756526F052325,
            0xFF343210: 0x6EB7071BE692A325,
            0xFF341810: 0x847DA1930526A325,
            0xFF341C10: 0x640439EE8ECD2325,
        }
        for color, frame_hash in expected.items():
            self.assertEqual(solid_hash(color), frame_hash)
            self.assertIn(f"{color:08X}", SOURCE.upper())
            self.assertIn(f"{frame_hash:016X}", SOURCE.upper())

    def test_catalog_and_recipe_are_xemu_only(self):
        catalog = json.loads((ROOT / "resources/catalog.json").read_text())
        descriptors = {entry["id"]: entry for entry in catalog["tests"]}
        for stable, legacy in zip(STABLE_IDS, LEGACY_IDS):
            descriptor = descriptors[stable]
            self.assertEqual(descriptor["supported_targets"], ["xemu"])
            self.assertGreaterEqual(descriptor["timeout_ms"], 180000)
            self.assertEqual(descriptor["legacy_ids"],
                             [f"PFIFOPacketBoundary::{legacy}"])
        recipe = json.loads(
            (ROOT / "resources/pfifo-packet-boundary.json").read_text())
        self.assertEqual(recipe["resolved_plan"]["selected_leaf_count"], 4)
        self.assertEqual({entry["id"] for entry in recipe["resolved_plan"]["tests"]},
                         set(STABLE_IDS))
        self.assertEqual(recipe["settings"]["warmup_iterations"], 0)
        self.assertEqual(recipe["settings"]["measurement_iterations_multiplier"], 1)
        self.assertEqual(recipe["settings"]["gpu_completion_mode"], "per_iteration")

    def test_xemu_only_suite_requires_explicit_runtime_opt_in(self):
        self.assertIn("enable_xemu_only_tests", RUNTIME_CONFIG)
        self.assertIn("runtime_config.enable_xemu_only_tests()", MAIN)
        self.assertIn("xemu-only resolved plan requires enable_xemu_only_tests", RUNTIME_CONFIG)
        recipe = json.loads(
            (ROOT / "resources/pfifo-packet-boundary.json").read_text())
        self.assertTrue(recipe["settings"]["enable_xemu_only_tests"])

    def test_boundary_scope_is_liveness_not_unobservable_state(self):
        self.assertIn('\\"verification_scope\\":\\"liveness_and_recovery\\"', SOURCE)
        self.assertIn("The guest does not read xemu's", DOC)
        self.assertIn("private destination state", DOC)
        self.assertIn("liveness and recovery", README)
        self.assertNotIn("hardening leaves for atomic rejection", README)

    def test_documentation_forbids_hardware_and_performance_claims(self):
        for phrase in (
            "xemu-only",
            "must not be run on physical Xbox hardware",
            "not a performance benchmark",
            "old-head negative control",
            "scalar trace fallback",
        ):
            self.assertIn(phrase, DOC)


if __name__ == "__main__":
    unittest.main()
