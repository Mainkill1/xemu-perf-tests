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
    def test_exposes_guest_pressure_variants_without_claiming_render_scale(self) -> None:
        self.assertIn('"XemuVulkanMemoryPressureRepresentative"', SOURCE)
        self.assertIn('"XemuVulkanMemoryPressureStress"', SOURCE)
        self.assertNotIn('"XemuVulkanMemoryPressure1x"', SOURCE)
        self.assertNotIn('"XemuVulkanMemoryPressure4x"', SOURCE)
        self.assertIn("kVulkanMemoryPressureSeed = 0x564D5052", SOURCE)
        self.assertIn(
            "kVulkanMemoryPressureTargetsPerPressureMultiplier = 16", SOURCE
        )
        self.assertIn("kVulkanMemoryPressureCyclesPerSample = 4", SOURCE)
        self.assertIn("kVulkanMemoryPressureProfileSamples = 4", SOURCE)
        self.assertIn("TestXemuVulkanMemoryPressure", HEADER)

    def test_checkpoint_sequence_separates_growth_cache_and_leak_signals(self) -> None:
        body = function_body(
            "void SurfaceRenderingTests::TestXemuVulkanMemoryPressure(const char *test_name,\n"
            "                                                          uint32_t guest_pressure_multiplier)"
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
            r'\"guest_pressure_multiplier\"',
            r'\"guest_identity_count\"',
            r'\"xemu_render_scale\":\"external\"',
            r'\"new_surface_texture_keys\"',
            r'\"alias_offset\"',
            r'\"transitions_per_work_iteration\"',
        ):
            with self.subTest(metadata_field=metadata_field):
                self.assertIn(metadata_field, body)
        self.assertIn("VULKAN_MEMORY_CHECKPOINT", body)
        self.assertIn("SetXemuPerfEventContext(phase_code", body)
        self.assertIn("EmitXemuPerfHeartbeat();", body)

    def test_churn_has_guest_pressure_targets_formats_aliases_resizes_and_reuse(self) -> None:
        body = function_body(
            "void SurfaceRenderingTests::TestXemuVulkanMemoryPressure(const char *test_name,\n"
            "                                                          uint32_t guest_pressure_multiplier)"
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
            "                                                          uint32_t guest_pressure_multiplier)"
        )
        self.assertIn("pb_back_buffer()", body)
        self.assertIn("pb_back_buffer_pitch()", body)
        self.assertIn("VULKAN_MEMORY_ORACLE_KAT", body)
        self.assertIn("XemuPerfEventType::FAIL", body)
        self.assertIn(r'\"oracle_nonfatal\":true', body)
        self.assertNotIn("AssertXemuPerfEqual", body)
        self.assertNotIn("ASSERT(", body)

        oracle_start = body.index("// The post-work oracle owns the framebuffer state.")
        oracle_end = body.index("const auto *const framebuffer =", oracle_start)
        oracle = body[oracle_start:oracle_end]
        # The workload deliberately stresses render-target-to-texture reuse,
        # but the final correctness scene must not depend on that churned
        # representation. Match the established vertex-buffer/pass-through
        # oracle path so immediate-mode state cannot mask a valid run.
        for required in (
            "host_.PrepareDraw(0xFF101820);",
            "host_.ClearVertexBuffer();",
            "std::make_shared<PBKitPlusPlus::PassthroughVertexShader>()",
            "host_.SetVertexShaderProgram(oracle_shader);",
            "host_.SetFinalCombiner0Just(TestHost::SRC_DIFFUSE);",
            "host_.SetFinalCombiner1Just(TestHost::SRC_ZERO, true, true);",
            "host_.AllocateVertexBuffer(",
            "oracle_vertex_buffer->SetPositionIncludesW(true);",
            "vertex->SetDiffuse(red, green, blue, 1.0f);",
            "host_.DrawArrays(kOracleVertexAttributes, TestHost::PRIMITIVE_QUADS);",
        ):
            with self.subTest(required=required):
                self.assertIn(required, oracle)
        self.assertNotIn("oracle_texture_stage", oracle)
        self.assertNotIn("DrawTexturedScreenQuad", oracle)
        self.assertLess(
            oracle.index("host_.SetVertexShaderProgram(oracle_shader);"),
            oracle.index("host_.PrepareDraw(0xFF101820);"),
        )
        self.assertIn(r'\"oracle_observed_tiles\"', body)

        colors = [0xFF3C78B4, 0xFFB46E3C, 0xFF56A866, 0xFF9A4FB4]
        observed = 2166136261
        for tile, color in enumerate(colors):
            observed = fnv_u32(observed, tile)
            observed = fnv_u32(observed, color)
        self.assertEqual(observed, 0x0D626FA0)
        self.assertIn("kVulkanMemoryPressureOracleKat = 0x0D626FA0", SOURCE)

    def test_checked_in_recipe_selects_sustained_stress_path(self) -> None:
        self.assertIn('"skip_tests_by_default": true', RECIPE)
        self.assertIn('"XemuVulkanMemoryPressureStress"', RECIPE)
        self.assertIn('"warmup_iterations": 0', RECIPE)
        self.assertIn('"gpu_completion_mode": "per_iteration"', RECIPE)


if __name__ == "__main__":
    unittest.main()
