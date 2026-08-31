#!/usr/bin/env python3
"""Static and independent KAT contracts for texture identity benchmarks."""

import json
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/tests/pipeline_texture_switch_tests.cpp").read_text()
MAIN = (ROOT / "src/main.cpp").read_text()
CMAKE = (ROOT / "src/CMakeLists.txt").read_text()
DOC = (ROOT / "docs/pipeline-texture-switch-workload.md").read_text()
CATALOG = json.loads((ROOT / "resources/catalog.json").read_text())
SEED = 0x50545357
FNV32_OFFSET = 2166136261
FNV32_PRIME = 16777619
FNV64_OFFSET = 14695981039346656037
FNV64_PRIME = 1099511628211
MIP_COLORS = (0xFFFF0000, 0xFFFFFF00, 0xFF00FF00, 0xFF00FFFF, 0xFF0000FF)


def word_kat(values):
    checksum = FNV32_OFFSET
    for value in values:
        for byte in struct.pack("<I", value & 0xFFFFFFFF):
            checksum = ((checksum ^ byte) * FNV32_PRIME) & 0xFFFFFFFF
    return checksum


def frame_kat(color):
    checksum = FNV64_OFFSET
    for _ in range(640 * 480):
        for byte in struct.pack("<I", color):
            checksum = ((checksum ^ byte) * FNV64_PRIME) & 0xFFFFFFFFFFFFFFFF
    return checksum


class PipelineTextureSwitchContractTests(unittest.TestCase):
    def test_suite_registration_and_stable_catalog_ids(self):
        self.assertIn("REG_TEST(PipelineTextureSwitchTests)", MAIN)
        self.assertIn("tests/pipeline_texture_switch_tests.cpp", CMAKE)
        by_id = {item["id"]: item for item in CATALOG["tests"]}
        expected = {
            "pipeline_texture_switch.texture_switch": "pipeline.texture-switch",
            "pipeline_texture_switch.shader_negative_control": "pipeline.shader-negative-control",
            "pipeline_texture_switch.clear_texture_normal": "pipeline.clear-texture-normal",
            "pipeline_texture_switch.sampler_only_identity": "pipeline.sampler-only-identity",
        }
        for stable, legacy in expected.items():
            self.assertEqual(by_id[stable]["execution"]["legacy_test"], legacy)
            self.assertIn(legacy, SOURCE)

    def test_all_manifests_are_catalog_bound_resolved_plans(self):
        families = {
            "pipeline-texture-switch": {
                "pipeline_texture_switch.texture_switch",
                "pipeline_texture_switch.shader_negative_control",
                "pipeline_texture_switch.sampler_only_identity",
            },
            "pipeline-clear-texture-normal": {"pipeline_texture_switch.clear_texture_normal"},
            "pipeline-sampler-only-identity": {"pipeline_texture_switch.sampler_only_identity"},
        }
        for family, expected in families.items():
            for profile in ("fast-smoke", "quick", "sustained"):
                config = json.loads((ROOT / "resources" / f"{family}-{profile}.json").read_text())
                self.assertNotIn("test_suites", config)
                plan = config["resolved_plan"]
                self.assertEqual(plan["catalog_id"], CATALOG["catalog_id"])
                self.assertTrue(plan["plan_id"].startswith("sha256:"))
                ids = {test["id"] for test in plan["tests"]}
                self.assertEqual(ids, expected)
                self.assertEqual(plan["selected_leaf_count"], len(expected))

    def test_sampler_identity_input_oracles_are_independent(self):
        mip_words = []
        dimension = 64
        for color in MIP_COLORS:
            mip_words.extend([color] * (dimension * dimension))
            dimension //= 2
        backing = word_kat(mip_words)
        recipe = word_kat((SEED, 64, 64, 5, *MIP_COLORS, backing, 512, 4, 0, 24))
        pixels = word_kat((MIP_COLORS[0], MIP_COLORS[4]) * 2)
        self.assertEqual(len(mip_words), 5456)
        self.assertEqual(backing, 0xCDD5D7A5)
        self.assertEqual(recipe, 0x281BCD52)
        self.assertEqual(pixels, 0xBB0EC8ED)
        for value in (backing, recipe, pixels):
            self.assertIn(f"{value:08X}", SOURCE.upper())
            self.assertIn(f"{value:08X}", DOC.upper())

    def test_sampler_path_changes_only_sampler_identity(self):
        iteration = SOURCE[SOURCE.index("void PipelineTextureSwitchTests::RunIteration"):]
        start = iteration.index("if (recipe.sampler_only_identity) {")
        end = iteration.index("} else if (recipe.shader_negative_control)", start)
        sampler_path = iteration[start:end]
        for required in ("SetLODClamp", "SetUWrap", "SetVWrap", "SetPWrap",
                         "SetBorderColor", "MIN_TENT_NEARESTLOD",
                         "MIN_BOX_NEARESTLOD", "host_.SetupTextureStages()"):
            self.assertIn(required, sampler_path)
        for forbidden in ("SET_TEXTURE_OFFSET", "SetFormat", "SetTextureDimensions",
                         "SetImageDimensions", "SetMipMapLevels"):
            self.assertNotIn(forbidden, sampler_path)
        self.assertIn("kSamplerQuadHalfExtent", iteration)
        for contract in ("image_identity_changes", "sampler_identity_count",
                         "image_cache_misses", "sampler_cache_misses"):
            self.assertIn(contract, SOURCE)

    def test_exact_framebuffer_oracles(self):
        expected = {
            0xFF18405A: 0x8AE05D31FB00C325,
            0xFF4A2038: 0xF110C8BD6338C325,
            0xFF305060: 0x22BA4F1405CDA325,
            0xFF405020: 0x0B8438C8404DA325,
        }
        for color, digest in expected.items():
            self.assertEqual(frame_kat(color), digest)
            self.assertIn(f"{color:08X}", SOURCE.upper())
            self.assertIn(f"{digest:016X}", SOURCE.upper())


if __name__ == "__main__":
    unittest.main()
