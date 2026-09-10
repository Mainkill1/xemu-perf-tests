#!/usr/bin/env python3
"""Contracts for the PR14 compressed cubemap face-stride oracle."""

import json
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "src/tests/texture_cubemap_fallback_tests.cpp"
HEADER_PATH = ROOT / "src/tests/texture_cubemap_fallback_tests.h"
MAIN = (ROOT / "src/main.cpp").read_text()
CMAKE = (ROOT / "src/CMakeLists.txt").read_text()
CATALOG = json.loads((ROOT / "resources/catalog.json").read_text())

COLORS_RGB565 = (0xF800, 0x07E0, 0x001F, 0xFFE0, 0xF81F, 0x07FF)
FACE_STRIDE = 128
FNV32_OFFSET = 2166136261
FNV32_PRIME = 16777619


def source_text() -> str:
    return SOURCE_PATH.read_text() if SOURCE_PATH.exists() else ""


def cubemap_source() -> bytes:
    source = bytearray(FACE_STRIDE * len(COLORS_RGB565))
    for face, color in enumerate(COLORS_RGB565):
        offset = face * FACE_STRIDE
        source[offset : offset + 2] = struct.pack("<H", color)
        # Preserve the historical oracle's second endpoint and selector data.
        # Every selector is zero, so each texel resolves to the first endpoint.
    return bytes(source)


def fnv1a(data: bytes) -> int:
    value = FNV32_OFFSET
    for byte in data:
        value = ((value ^ byte) * FNV32_PRIME) & 0xFFFFFFFF
    return value


class CubemapSubblockContractTests(unittest.TestCase):
    def test_stable_catalog_route_is_registered(self) -> None:
        by_id = {item["id"]: item for item in CATALOG["tests"]}
        item = by_id.get("texture_cubemap_fallback.unbordered_subblock_dxt1")
        self.assertIsNotNone(item, "PR14 cubemap regression route is missing")
        self.assertEqual(item["supported_targets"], ["xemu"])
        self.assertEqual(item["execution"]["legacy_suite"], "TextureCubemapFallback")
        self.assertEqual(item["execution"]["legacy_test"], "UnborderedSubblockDxt1")

    def test_xemu_only_suite_is_built_and_registered(self) -> None:
        self.assertTrue(SOURCE_PATH.exists())
        self.assertTrue(HEADER_PATH.exists())
        self.assertIn("tests/texture_cubemap_fallback_tests.cpp", CMAKE)
        self.assertIn('#include "tests/texture_cubemap_fallback_tests.h"', MAIN)
        xemu_only = MAIN[MAIN.index("if (runtime_config.enable_xemu_only_tests())") :]
        self.assertIn("REG_TEST(TextureCubemapFallbackTests)", xemu_only)

    def test_oracle_keeps_distinct_aligned_faces_and_subblock_sizes(self) -> None:
        source = source_text()
        self.assertIn("constexpr uint32_t kLogicalSizes[] = {1, 2};", source)
        self.assertIn("constexpr uint32_t kFaceStride = 128;", source)
        self.assertIn("constexpr uint16_t kFaceColors[]", source)
        for color in COLORS_RGB565:
            self.assertIn(f"0x{color:04X}", source)
        self.assertIn("face * kFaceStride", source)
        self.assertIn("stage.SetCubemapEnable(true);", source)
        self.assertIn("TestHost::STAGE_CUBE_MAP", source)

    def test_oracle_checks_all_twelve_rendered_cells(self) -> None:
        source = source_text()
        self.assertIn("kCellCount = kLogicalSizeCount * kFaceCount", source)
        self.assertIn("for (uint32_t size_index = 0;", source)
        self.assertIn("for (uint32_t face = 0; face < kFaceCount; ++face)", source)
        self.assertIn("observed_rgb565 != kFaceColors[face]", source)
        self.assertIn('"unbordered_subblock_cubemap_stride"', source)
        self.assertIn('"logical_extents":[1,2]', source)
        self.assertIn('"faces":6', source)

    def test_independent_source_model_has_fixed_kat(self) -> None:
        self.assertEqual(len(cubemap_source()), 768)
        self.assertEqual(fnv1a(cubemap_source()), 0xF13E387F)
        self.assertIn("0XF13E387F", source_text().upper())


if __name__ == "__main__":
    unittest.main()
