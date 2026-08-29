from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/tests/game_load_composite_tests.cpp").read_text()
HEADER = (ROOT / "src/tests/game_load_composite_tests.h").read_text()
SUITE_SOURCE = (ROOT / "src/tests/test_suite.cpp").read_text()
SUITE_HEADER = (ROOT / "src/tests/test_suite.h").read_text()


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


class CompositeOracleDeterminismContractTests(unittest.TestCase):
    def test_correctness_draw_owns_prior_result_and_workload_state(self) -> None:
        body = function_body(
            "void GameLoadCompositeTests::PrepareCorrectnessRenderState()"
        )
        required = (
            "SetDefaultViewportAndFixedFunctionMatrices()",
            "SetVertexShaderProgram(nullptr)",
            "ClearVertexBuffer()",
            "SetTextureStageEnabled(0, false)",
            "SetTextureStageEnabled(1, false)",
            "SetTextureStageEnabled(2, false)",
            "SetTextureStageEnabled(3, false)",
            "SetupTextureStages()",
            "SetShaderStageProgram(TestHost::STAGE_NONE, TestHost::STAGE_NONE,",
            "SetBlend(false)",
            "SetFinalCombiner0Just(TestHost::SRC_DIFFUSE)",
            "SetFinalCombiner1Just(TestHost::SRC_DIFFUSE, true)",
        )
        for statement in required:
            with self.subTest(statement=statement):
                self.assertIn(statement, body)

    def test_final_hash_scene_resets_before_textured_and_immediate_draws(self) -> None:
        body = function_body(
            "void GameLoadCompositeTests::DrawCorrectnessResult(uint32_t checksum,\n"
            "                                                   const Preset &preset,\n"
            "                                                   Phase phase)"
        )
        self.assertEqual(body.count("PrepareCorrectnessRenderState();"), 2)
        first_reset = body.index("PrepareCorrectnessRenderState();")
        textured_draw = body.index("host_.DrawArrays")
        second_reset = body.rindex("PrepareCorrectnessRenderState();")
        immediate_draw = body.index("host_.Begin(TestHost::PRIMITIVE_QUADS)")
        self.assertLess(first_reset, textured_draw)
        self.assertLess(textured_draw, second_reset)
        self.assertLess(second_reset, immediate_draw)

    def test_final_hash_scene_uses_a_fixed_completed_texture_oracle(self) -> None:
        body = function_body(
            "void GameLoadCompositeTests::DrawCorrectnessResult(uint32_t checksum,\n"
            "                                                   const Preset &preset,\n"
            "                                                   Phase phase)"
        )
        self.assertEqual(body.count("host_.WaitForGpu();"), 3)
        self.assertEqual(
            body.count("EmitXemuPerfMarker(kXemuPerfMarkerGpuComplete);"), 1
        )
        required = (
            "kOracleTextureSourceKat",
            "streaming_buffer_checksums_[0]",
            "memcpy(oracle_texture, streaming_buffers_[0].data(),",
            "NV097_SET_TEXTURE_FORMAT_COLOR_SZ_A8B8G8R8",
            "SetTextureDimensions(kTextureWidth, kTextureHeight)",
            "BindTextureStage0Address(oracle_texture)",
        )
        for statement in required:
            with self.subTest(statement=statement):
                self.assertIn(statement, body)
        pre_wait = body.index("host_.WaitForGpu();")
        texture_write = body.index("memcpy(oracle_texture")
        draw = body.index("host_.DrawArrays")
        final_fence = body.index("EmitXemuPerfMarker(kXemuPerfMarkerGpuComplete);")
        self.assertLess(pre_wait, texture_write)
        self.assertLess(texture_write, draw)
        self.assertLess(draw, final_fence)

    def test_reset_is_guest_workload_scoped(self) -> None:
        self.assertIn("void PrepareCorrectnessRenderState();", HEADER)
        self.assertIn("void PrepareCrossTitleWorkState();", HEADER)
        run_test = function_body(
            "void GameLoadCompositeTests::RunTest(const Preset &preset, Phase phase)"
        )
        self.assertIn("DrawCorrectnessResult(aggregate_checksum_, preset, phase);", run_test)

    def test_each_cross_title_stage_records_a_fixed_oracle(self) -> None:
        body = function_body("void GameLoadCompositeTests::RunCrossTitleHotpath()")
        oracle = (
            "DrawCorrectnessResult(aggregate_checksum_, preset, "
            "definition.result_phase);"
        )
        record = "host_.RecordProfileResult(suite_name_, definition.record_name"
        restore = "PrepareCrossTitleWorkState();"
        self.assertIn(oracle, body)
        self.assertLess(body.index(oracle), body.index(record))
        self.assertLess(body.index(record), body.rindex(restore))

    def test_cross_title_restore_owns_next_stage_state(self) -> None:
        body = function_body(
            "void GameLoadCompositeTests::PrepareCrossTitleWorkState()"
        )
        required = (
            "SetDefaultViewportAndFixedFunctionMatrices()",
            "memcpy(texture_memory, streaming_buffers_[current_streaming_buffer_]",
            "NV097_SET_TEXTURE_FORMAT_COLOR_SZ_A8B8G8R8",
            "SetTextureDimensions(kTextureWidth, kTextureHeight)",
            "texture_stage.SetEnabled(true)",
            "SetTextureStageEnabled(1, false)",
            "SetTextureStageEnabled(2, false)",
            "SetTextureStageEnabled(3, false)",
            "SetupTextureStages()",
            "BindTextureStage0Address(texture_memory)",
            "SetShaderStageProgram(TestHost::STAGE_2D_PROJECTIVE,",
            "SetVertexShaderProgram(nullptr)",
            "SetVertexBuffer(alpha_vertex_buffer_)",
            "SetBlend(true)",
            "SetFinalCombiner0Just(TestHost::SRC_DIFFUSE)",
            "SetFinalCombiner1Just(TestHost::SRC_DIFFUSE, true)",
        )
        for statement in required:
            with self.subTest(statement=statement):
                self.assertIn(statement, body)

    def test_s3tc_factor_owns_state_after_cross_title(self) -> None:
        body = function_body(
            "uint32_t GameLoadCompositeTests::RunS3tcSyncFactorWork(bool compressed,\n"
            "                                                       bool per_draw_wait,\n"
            "                                                       uint32_t seed)"
        )
        required = (
            "NV097_SET_ALPHA_TEST_ENABLE, false",
            "NV097_SET_DEPTH_TEST_ENABLE, false",
            "NV097_SET_DEPTH_MASK, true",
            "NV097_SET_STENCIL_TEST_ENABLE, false",
            "NV097_SET_FRONT_FACE, NV097_SET_FRONT_FACE_V_CW",
            "NV097_SET_CULL_FACE, NV097_SET_CULL_FACE_V_BACK",
            "NV097_SET_CULL_FACE_ENABLE, true",
            "NV097_SET_COLOR_MASK",
            "SetVertexShaderProgram(nullptr)",
            "ClearVertexBuffer()",
            "SetTextureStageEnabled(0, true)",
            "SetTextureStageEnabled(1, false)",
            "SetTextureStageEnabled(2, false)",
            "SetTextureStageEnabled(3, false)",
            "SetShaderStageProgram(TestHost::STAGE_2D_PROJECTIVE,",
            "SetVertexBuffer(factor_vertex_buffer_)",
            "SetFinalCombiner0Just(TestHost::SRC_TEX0)",
            "SetFinalCombiner1Just(TestHost::SRC_DIFFUSE, true)",
            "SetBlend(false)",
            "BindTextureStage0Address(destination)",
        )
        for statement in required:
            with self.subTest(statement=statement):
                self.assertIn(statement, body)
        self.assertLess(
            body.index("SetVertexBuffer(factor_vertex_buffer_)"),
            body.index("host_.PrepareDraw"),
        )

    def test_full_suite_runs_cross_title_directly_before_s3tc(self) -> None:
        self.assertIn(
            'kCrossTitleHotpathName = "09-CrossTitleHotpath"', HEADER
        )
        self.assertIn('kS3tcSyncFactorName = "10-S3tcSyncFactor"', HEADER)
        self.assertLess(
            HEADER.index('kCrossTitleHotpathName = "09-CrossTitleHotpath"'),
            HEADER.index('kS3tcSyncFactorName = "10-S3tcSyncFactor"'),
        )
        self.assertIn(
            "std::map<std::string, std::function<void(void)>> tests_", SUITE_HEADER
        )
        run_all = re.search(
            r"void TestSuite::RunAll\(\)\s*\{(?P<body>.*?)\n\}",
            SUITE_SOURCE,
            re.DOTALL,
        )
        self.assertIsNotNone(run_all)
        self.assertIn("auto names = TestNames();", run_all.group("body"))
        self.assertIn("Run(test_name, true);", run_all.group("body"))

        s3tc = function_body("void GameLoadCompositeTests::RunS3tcSyncFactor()")
        self.assertIn("TestSuite::Initialize();", s3tc)
        self.assertIn("host_.SetupFixedFunctionPassthrough();", s3tc)
        self.assertLess(
            s3tc.index("TestSuite::Initialize();"),
            s3tc.index("host_.SetupFixedFunctionPassthrough();"),
        )
        self.assertLess(
            s3tc.index("host_.SetupFixedFunctionPassthrough();"),
            s3tc.index("SetXemuPerfEventContext"),
        )
        self.assertLess(
            s3tc.index("host_.SetupFixedFunctionPassthrough();"),
            s3tc.index("auto results = Profile"),
        )

    def test_s3tc_uses_exact_interior_tile_center_oracle(self) -> None:
        body = function_body(
            "uint32_t GameLoadCompositeTests::ValidateS3tcSyncFactorFramebuffer(\n"
            "    bool compressed) const"
        )
        required = (
            "host_.WaitForGpu()",
            "pb_back_buffer()",
            "pb_back_buffer_pitch()",
            "kFactorTileWidth / 2",
            "kFactorTileHeight / 2",
            "volatile const uint8_t",
            "const uint32_t blue = pixel[0]",
            "const uint32_t green = pixel[1]",
            "const uint32_t red = pixel[2]",
            "const uint32_t alpha = pixel[3]",
            "ExpandFactorRgb565(kFactorColors[tile])",
            "0x130U + tile",
            "0x150U + tile",
            "0x170U + tile",
            "kFactorTileSourceKat",
        )
        for statement in required:
            with self.subTest(statement=statement):
                self.assertIn(statement, body)
        run = function_body("void GameLoadCompositeTests::RunS3tcSyncFactor()")
        self.assertIn(
            "ValidateS3tcSyncFactorFramebuffer(definition.compressed);", run
        )
        self.assertLess(
            run.index("ValidateS3tcSyncFactorFramebuffer(definition.compressed);"),
            run.index("host_.RecordProfileResult"),
        )


if __name__ == "__main__":
    unittest.main()
