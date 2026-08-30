from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/tests/surface_rendering_tests.cpp").read_text()
HEADER = (ROOT / "src/tests/surface_rendering_tests.h").read_text()
RECIPE = (ROOT / "resources/vulkan-memory-pressure-config.json").read_text()


def function_body(signature: str) -> str:
    match = re.search(re.escape(signature) + r"\s*\{", SOURCE)
    if match is None:
        raise AssertionError(f"missing function: {signature}")
    depth = 1
    index = match.end()
    while depth and index < len(SOURCE):
        depth += (SOURCE[index] == "{") - (SOURCE[index] == "}")
        index += 1
    if depth:
        raise AssertionError(f"unterminated function: {signature}")
    return SOURCE[match.end() : index - 1]


def fnv_u32(hash_value: int, value: int) -> int:
    for byte in range(4):
        hash_value ^= (value >> (byte * 8)) & 0xFF
        hash_value = (hash_value * 16777619) & 0xFFFFFFFF
    return hash_value


class VulkanMemoryPressureContractTests(unittest.TestCase):
    def test_exposes_comparable_fixed_1x_and_4x_variants(self) -> None:
        self.assertIn('"XemuVulkanMemoryPressure1x"', SOURCE)
        self.assertIn('"XemuVulkanMemoryPressure4x"', SOURCE)
        self.assertIn("kVulkanMemoryPressureSeed = 0x564D5052", SOURCE)
        self.assertIn("kVulkanMemoryPressureTargetsPerScale = 16", SOURCE)
        self.assertIn("kVulkanMemoryPressureCyclesPerSample = 4", SOURCE)
        self.assertIn("kVulkanMemoryPressureProfileSamples = 4", SOURCE)
        self.assertIn("TestXemuVulkanMemoryPressure", HEADER)

    def test_checkpoint_sequence_separates_growth_cache_and_leak_signals(self) -> None:
        body = function_body(
            "void SurfaceRenderingTests::TestXemuVulkanMemoryPressure(const char *test_name,\n"
            "                                                          uint32_t scale)"
        )
        for phase in (
            "GROWTH",
            "PLATEAU",
            "ALIAS_RESIZE",
            "REUSE",
            "IDLE_RETENTION",
        ):
            with self.subTest(phase=phase):
                self.assertIn(f"VulkanMemoryPressurePhase::{phase}", body)
        for metadata_field in (
            r'\"kind\":\"vulkan_memory_pressure_checkpoint\"',
            r'\"expected_memory_behavior\"',
            r'\"new_surface_texture_keys\"',
            r'\"alias_offset\"',
            r'\"transitions_per_work_iteration\"',
        ):
            with self.subTest(metadata_field=metadata_field):
                self.assertIn(metadata_field, body)
        self.assertIn("VULKAN_MEMORY_CHECKPOINT", body)
        self.assertIn("SetXemuPerfEventContext(phase_code", body)
        self.assertIn("EmitXemuPerfHeartbeat();", body)

    def test_churn_has_scaled_targets_formats_aliases_resizes_and_reuse(self) -> None:
        body = function_body(
            "void SurfaceRenderingTests::TestXemuVulkanMemoryPressure(const char *test_name,\n"
            "                                                          uint32_t scale)"
        )
        for required in (
            "target * kVulkanMemoryPressureSurfaceStride",
            "kVulkanMemoryPressureAliasOffset",
            "TestHost::SCF_A8R8G8B8",
            "TestHost::SCF_R5G6B5",
            "SetTextureDimensions(shape.width, shape.height)",
            "RenderToSurfaceStart(address, shape.surface_format",
            "BindSurfaceTextureAddress(address)",
        ):
            with self.subTest(required=required):
                self.assertIn(required, body)

    def test_final_oracle_is_fixed_and_nonfatal(self) -> None:
        body = function_body(
            "void SurfaceRenderingTests::TestXemuVulkanMemoryPressure(const char *test_name,\n"
            "                                                          uint32_t scale)"
        )
        self.assertIn("pb_back_buffer()", body)
        self.assertIn("pb_back_buffer_pitch()", body)
        self.assertIn("VULKAN_MEMORY_ORACLE_KAT", body)
        self.assertIn("XemuPerfEventType::FAIL", body)
        self.assertIn(r'\"oracle_nonfatal\":true', body)
        self.assertNotIn("AssertXemuPerfEqual", body)
        self.assertNotIn("ASSERT(", body)

        colors = [0xFF3C78B4, 0xFFB46E3C, 0xFF56A866, 0xFF9A4FB4]
        observed = 2166136261
        for tile, color in enumerate(colors):
            observed = fnv_u32(observed, tile)
            observed = fnv_u32(observed, color)
        self.assertEqual(observed, 0x0D626FA0)
        self.assertIn("kVulkanMemoryPressureOracleKat = 0x0D626FA0", SOURCE)

    def test_checked_in_recipe_selects_sustained_4x_path(self) -> None:
        self.assertIn('"skip_tests_by_default": true', RECIPE)
        self.assertIn('"XemuVulkanMemoryPressure4x"', RECIPE)
        self.assertIn('"warmup_iterations": 0', RECIPE)
        self.assertIn('"gpu_completion_mode": "per_iteration"', RECIPE)


if __name__ == "__main__":
    unittest.main()
