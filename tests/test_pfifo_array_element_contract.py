#!/usr/bin/env python3
"""Static contracts for deterministic PFIFO array-element capsules."""

import hashlib
import json
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/tests/pfifo_array_element_tests.cpp").read_text()
HEADER = (ROOT / "src/debug_output.h").read_text()
MAIN = (ROOT / "src/main.cpp").read_text()
CMAKE = (ROOT / "src/CMakeLists.txt").read_text()
README = (ROOT / "README.md").read_text()
DOC = (ROOT / "docs/pfifo-array-element-workloads.md").read_text()

SEED = 0x50464946
FNV32_OFFSET = 2166136261
FNV32_PRIME = 16777619
FNV64_OFFSET = 14695981039346656037
FNV64_PRIME = 1099511628211
TEST_IDS = (
    "pfifo.array-element16",
    "pfifo.array-element32",
    "pfifo.array-element-pgr2",
)
STABLE_IDS = (
    "pfifo_array_elements.array_element16",
    "pfifo_array_elements.array_element32",
    "pfifo_array_elements.array_element_pgr2",
)


def xorshift32(state: int) -> int:
    state ^= (state << 13) & 0xFFFFFFFF
    state ^= state >> 17
    state ^= (state << 5) & 0xFFFFFFFF
    return state & 0xFFFFFFFF


def fnv32_word(checksum: int, value: int) -> int:
    for byte in struct.pack("<I", value & 0xFFFFFFFF):
        checksum = ((checksum ^ byte) * FNV32_PRIME) & 0xFFFFFFFF
    return checksum


def fnv64_solid_frame(color: int) -> int:
    checksum = FNV64_OFFSET
    for _ in range(640 * 480):
        for byte in struct.pack("<I", color):
            checksum = ((checksum ^ byte) * FNV64_PRIME) & 0xFFFFFFFFFFFFFFFF
    return checksum


def generated_recipe():
    state = SEED
    colors = []
    indices = []
    vertex_kat = fnv32_word(FNV32_OFFSET, SEED)
    for tile in range(19):
        state = xorshift32(state)
        bits = (state >> 3) & 7 or 1
        color = (
            0xFF000000
            | (0x00FF0000 if bits & 1 else 0)
            | (0x0000FF00 if bits & 2 else 0)
            | (0x000000FF if bits & 4 else 0)
        )
        colors.append(color)
        left = 32 + (tile % 5) * 112
        top = 48 + (tile // 5) * 96
        for value in (tile, left, top, left + 80, top + 64, color):
            vertex_kat = fnv32_word(vertex_kat, value)
        indices.extend(range(tile * 4, tile * 4 + 4))
    return vertex_kat, colors, indices


def word_kat(values) -> int:
    checksum = FNV32_OFFSET
    for value in values:
        checksum = fnv32_word(checksum, value)
    return checksum


class PfifoArrayElementContractTests(unittest.TestCase):
    def load(self, name: str) -> dict:
        return json.loads((ROOT / "resources" / name).read_text())

    def test_single_xiso_suite_and_exact_routes(self):
        self.assertIn("REG_TEST(PfifoArrayElementTests)", MAIN)
        self.assertIn("tests/pfifo_array_element_tests.cpp", CMAKE)
        for resource in (
            "pfifo-array-elements-fast-smoke.json",
            "pfifo-array-elements-quick.json",
            "pfifo-array-elements-sustained.json",
        ):
            config = self.load(resource)
            plan = config["resolved_plan"]
            catalog = self.load("catalog.json")
            self.assertEqual(plan["catalog_id"], catalog["catalog_id"])
            self.assertEqual(plan["selected_leaf_count"], len(STABLE_IDS))
            self.assertEqual({entry["id"] for entry in plan["tests"]},
                             set(STABLE_IDS))
            contract = {"catalog_id": plan["catalog_id"],
                        "tests": plan["tests"]}
            expected_plan_id = "sha256:" + hashlib.sha256(
                json.dumps(contract, sort_keys=True,
                           separators=(",", ":")).encode()).hexdigest()
            self.assertEqual(plan["plan_id"], expected_plan_id)
            self.assertNotIn("test_suites", config)
        self.assertEqual(
            self.load("pfifo-array-elements-fast-smoke.json")["settings"]["gpu_completion_mode"],
            "enqueue",
        )
        for resource in (
            "pfifo-array-elements-quick.json",
            "pfifo-array-elements-sustained.json",
        ):
            self.assertEqual(
                self.load(resource)["settings"]["gpu_completion_mode"],
                "batch_complete",
            )
        for test_id in TEST_IDS:
            self.assertIn(test_id, SOURCE)
            self.assertIn(test_id, README)
            self.assertIn(test_id, DOC)
        catalog = self.load("catalog.json")
        descriptors = {entry["id"]: entry for entry in catalog["tests"]}
        for stable_id, legacy_id in zip(STABLE_IDS, TEST_IDS):
            self.assertEqual(descriptors[stable_id]["legacy_ids"],
                             [f"PFIFOArrayElements::{legacy_id}"])
            self.assertEqual(descriptors[stable_id]["execution"], {
                "legacy_suite": "PFIFOArrayElements", "legacy_test": legacy_id})

    def test_fixed_packet_shapes_are_non_incrementing(self):
        for literal in (
            "kMorrowindPacketWords = 38",
            "kPgr2PacketWords = 29",
            "kPacketsPerIteration = 256",
            "NV2A_SUPPRESS_COMMAND_INCREMENT(method)",
            "NV097_ARRAY_ELEMENT16",
            "NV097_ARRAY_ELEMENT32",
        ):
            self.assertIn(literal, SOURCE)
        self.assertIn("kMorrowindIndexCount,\n      kMorrowindIndexCount", SOURCE)

    def test_literal_input_payload_and_pixel_kats(self):
        vertex_kat, colors, indices = generated_recipe()
        index76 = word_kat(indices)
        index58 = word_kat(indices[:58])
        payload16_38 = [indices[i] | (indices[i + 1] << 16) for i in range(0, 76, 2)]
        payload16_29 = payload16_38[:29]
        values = {
            vertex_kat,
            index76,
            index58,
            word_kat(payload16_38),
            word_kat(indices),
            word_kat(payload16_29),
            word_kat(colors),
            word_kat(colors[:14]),
        }
        self.assertEqual(
            values,
            {
                0x576F9C60,
                0x214ABD05,
                0x33E7DBF4,
                0x38503435,
                0x555DCC3C,
                0x8F69B3C6,
                0x18D08B94,
            },
        )
        for value in values:
            literal = f"{value:08X}"
            self.assertIn(literal, SOURCE.upper())
            self.assertIn(literal, DOC.upper())

    def test_exact_framebuffer_hashes(self):
        expected = {
            0xFF163826: 0x9C884DE2A5D32325,
            0xFF32764C: 0xE079F0CF1A994325,
            0xFF291D52: 0xBBC8B0702FFD0325,
        }
        for color, frame_hash in expected.items():
            self.assertEqual(fnv64_solid_frame(color), frame_hash)
            self.assertIn(f"{color:08X}", SOURCE.upper())
            self.assertIn(f"{frame_hash:016X}", SOURCE.upper())
            self.assertIn(f"{frame_hash:016X}", DOC.upper())
        self.assertIn("expected_framebuffer_fnv1a64", SOURCE)
        self.assertIn("HashBackBuffer()", SOURCE)

    def test_f1_precedes_f2_and_correctness(self):
        run = SOURCE[SOURCE.index("void PfifoArrayElementTests::Run(") :]
        profile = run.index("Profile(recipe.test_name")
        sync = run.index("SynchronizeCorrectness(host_);", profile)
        validate = run.index("ValidateRenderedTiles(recipe)", sync)
        self.assertLess(profile, sync)
        self.assertLess(sync, validate)
        self.assertIn("Profile emitted F1", run[profile:sync])
        self.assertIn("EmitXemuPerfMarker(kXemuPerfMarkerGpuComplete)", SOURCE)
        for assertion in (
            "PFIFO_ARRAY_VERTEX_INPUT = 0x140",
            "PFIFO_ARRAY_SURFACE = 0x141",
            "PFIFO_ARRAY_FINAL = 0x142",
            "PFIFO_ARRAY_FRAMEBUFFER = 0x143",
        ):
            self.assertIn(assertion, HEADER)

    def test_duration_profiles_are_long_run_starting_points(self):
        smoke = self.load("pfifo-array-elements-fast-smoke.json")["settings"]
        quick = self.load("pfifo-array-elements-quick.json")["settings"]
        sustained = self.load("pfifo-array-elements-sustained.json")["settings"]
        self.assertEqual((smoke["warmup_iterations"], smoke["measurement_iterations_multiplier"]), (1, 1))
        self.assertEqual((quick["warmup_iterations"], quick["measurement_iterations_multiplier"]), (300, 150))
        self.assertEqual((sustained["warmup_iterations"], sustained["measurement_iterations_multiplier"]), (750, 375))
        for phrase in (
            "2-second warmup / 8-second measurement",
            "5-second / 20-second",
            "Never calibrate the candidate",
            "Short smoke output",
            "fixed batch-completion drain",
            "separate post-F1 F2",
        ):
            self.assertIn(phrase, DOC)

    def test_oracles_are_explicitly_regression_only(self):
        self.assertIn('\\"oracle_provenance\\":\\"REGRESSION_ONLY\\"', SOURCE)
        self.assertIn("retail Xbox", DOC)
        self.assertIn("not physical-NV2A proof", DOC)


if __name__ == "__main__":
    unittest.main()
