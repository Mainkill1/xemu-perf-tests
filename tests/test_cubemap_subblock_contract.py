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


def bordered_source(size: int) -> bytes:
    levels = size.bit_length()
    level_widths = [16 >> level for level in range(levels)]
    face_bytes = sum(width * width * 4 for width in level_widths)
    face_stride = (face_bytes + 127) & ~127
    source = bytearray(face_stride * 6)

    for face in range(6):
        level_offset = face * face_stride
        for level, width in enumerate(level_widths):
            logical = max(1, size >> level)
            border = (4 >> level) if level < 3 else 0
            skip = min(border, width - logical)
            red = 3 + face * 4
            for y in range(width):
                for x in range(width):
                    if skip <= x < skip + logical and skip <= y < skip + logical:
                        green = 5 + level * 14 + y - skip
                        blue = 2 + x - skip
                        # Xbox A8R8G8B8 payload uses bit replication from RGB565.
                        value = (0xFF000000 | ((red * 8 + red // 4) << 16) |
                                 ((green * 4 + green // 16) << 8) |
                                 (blue * 8 + blue // 4))
                    else:
                        value = 0xFF000000
                    morton = sum(((x >> bit) & 1) << (2 * bit) |
                                 ((y >> bit) & 1) << (2 * bit + 1)
                                 for bit in range(4))
                    offset = level_offset + 4 * morton
                    source[offset:offset + 4] = struct.pack("<I", value)
            level_offset += width * width * 4
    return bytes(source)


class CubemapSubblockContractTests(unittest.TestCase):
    def test_bordered_source_fixed_kats(self) -> None:
        expected = (0xAE745524, 0xCCA3A610, 0x32FF9E3C, 0xE80E51B4)
        for index, size in enumerate((1, 2, 4, 8)):
            self.assertEqual(fnv1a(bordered_source(size)), expected[index])
            self.assertIn(f"0x{expected[index]:08X}", source_text())

    def test_bordered_oracle_samples_position_coded_edges(self) -> None:
        source = "".join(source_text().split())
        self.assertIn("BorderedCellColor(face,level,x-skip,y-skip)", source)
        self.assertIn("kBorderedSampleCoords", source)
        self.assertIn("CubeDirection(face,", source)
        self.assertIn("BorderedCellColor(face,level,sample_x,sample_y)", source)

    def test_bordered_rgba8_routes_cover_terminal_mips(self) -> None:
        by_id = {item["id"]: item for item in CATALOG["tests"]}
        for size in (1, 2, 4, 8):
            stable_id = f"texture_cubemap_fallback.bordered_rgba8_size{size}"
            item = by_id.get(stable_id)
            self.assertIsNotNone(item, stable_id)
            self.assertEqual(item["supported_targets"], ["xemu"])
            self.assertEqual(item["execution"]["legacy_suite"],
                             "TextureCubemapFallback")
            self.assertEqual(item["execution"]["legacy_test"],
                             f"BorderedRgba8Size{size}")

    def test_converted_cubemap_routes_cover_all_logical_sizes(self) -> None:
        by_id = {item["id"]: item for item in CATALOG["tests"]}
        for format_id, label in (("palette", "Palette"), ("r6g5b5", "R6G5B5")):
            for size in (1, 2, 4, 8):
                stable_id = f"texture_cubemap_fallback.bordered_{format_id}_size{size}"
                item = by_id.get(stable_id)
                self.assertIsNotNone(item, stable_id)
                self.assertEqual(item["supported_targets"], ["xemu"])
                self.assertEqual(item["execution"]["legacy_suite"], "TextureCubemapFallback")
                self.assertEqual(item["execution"]["legacy_test"], f"Bordered{label}Size{size}")

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
