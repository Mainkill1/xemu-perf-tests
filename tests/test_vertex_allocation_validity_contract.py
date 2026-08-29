from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/tests/vertex_buffer_allocation_tests.cpp").read_text()
HEADER = (ROOT / "src/tests/vertex_buffer_allocation_tests.h").read_text()
SUITE_SOURCE = (ROOT / "src/tests/test_suite.cpp").read_text()


def function_body(source: str, signature: str) -> str:
    match = re.search(re.escape(signature) + r"\s*\{", source)
    if match is None:
        raise AssertionError(f"missing function: {signature}")
    depth = 1
    index = match.end()
    while depth and index < len(source):
        depth += (source[index] == "{") - (source[index] == "}")
        index += 1
    if depth:
        raise AssertionError(f"unterminated function: {signature}")
    return source[match.end() : index - 1]


def fnv_u32(hash_value: int, value: int) -> int:
    for byte in range(4):
        hash_value ^= (value >> (byte * 8)) & 0xFF
        hash_value = (hash_value * 16777619) & 0xFFFFFFFF
    return hash_value


def oracle_kat(colors: list[int]) -> int:
    hash_value = 2166136261
    for tile, color in enumerate(colors):
        hash_value = fnv_u32(hash_value, tile)
        hash_value = fnv_u32(hash_value, color)
    return hash_value


def assert_retention_contract(source: str) -> None:
    body = function_body(
        source,
        "void VertexBufferAllocationTests::TestMixedSizes("
        "const std::string &name, DrawMode draw_mode)",
    )
    required = (
        "std::vector<std::shared_ptr<VertexBuffer>> retained_buffers;",
        "retained_buffers.reserve(std::size(kMixedVertexBufferSizesSingleFrame));",
        "DrawModeRequiresRetainedVertexRam(draw_mode)",
        "retained_buffers.emplace_back(vertex_buffer);",
        "host_.WaitForGpu();",
        "retained_buffers.clear();",
        "host_.ClearVertexBuffer();",
    )
    for statement in required:
        if statement not in body:
            raise AssertionError(f"missing retention statement: {statement}")
    if body.index("retained_buffers.emplace_back(vertex_buffer);") > body.index(
        "host_.WaitForGpu();"
    ):
        raise AssertionError("vertex RAM must be retained before completion")
    if body.index("host_.WaitForGpu();") > body.index("retained_buffers.clear();"):
        raise AssertionError("completion must precede retained-buffer release")
    if body.index("host_.WaitForGpu();") > body.index("host_.ClearVertexBuffer();"):
        raise AssertionError("completion must precede host vertex-buffer clear")


class VertexAllocationValidityContractTests(unittest.TestCase):
    def test_geometry_returns_ownership_and_uses_specified_generator(self) -> None:
        signature = (
            "static std::shared_ptr<VertexBuffer> CreateGeometry(\n"
            "    TestHost &host, std::vector<uint32_t> &index_buffer,\n"
            "    uint32_t target_array_entries, uint32_t seed)"
        )
        body = function_body(SOURCE, signature)
        self.assertIn("SpecifiedGenerator generator(seed);", body)
        self.assertIn("return vertex_buffer;", body)
        self.assertNotIn("rand()", SOURCE)
        self.assertNotIn("srand(", SOURCE)

    def test_arrays_and_inline_elements_retain_one_body_until_completion(self) -> None:
        assert_retention_contract(SOURCE)
        predicate = function_body(
            SOURCE,
            "static constexpr bool DrawModeRequiresRetainedVertexRam(\n"
            "    VertexBufferAllocationTests::DrawMode mode)",
        )
        self.assertIn("DrawMode::DRAW_ARRAYS", predicate)
        self.assertIn("DrawMode::DRAW_INLINE_ELEMENTS", predicate)
        self.assertNotIn("DRAW_INLINE_BUFFERS ||", predicate)
        self.assertNotIn("DRAW_INLINE_ARRAYS ||", predicate)

        tiny = function_body(
            SOURCE,
            "void VertexBufferAllocationTests::TestTinyAllocations("
            "const std::string &name, DrawMode draw_mode)",
        )
        for statement in (
            "std::vector<std::shared_ptr<VertexBuffer>> retained_buffers;",
            "retained_buffers.reserve(num_draws);",
            "retained_buffers.emplace_back(vertex_buffer);",
            "host_.WaitForGpu();",
            "retained_buffers.clear();",
            "host_.ClearVertexBuffer();",
        ):
            with self.subTest(tiny_statement=statement):
                self.assertIn(statement, tiny)
        self.assertLess(
            tiny.index("retained_buffers.emplace_back(vertex_buffer);"),
            tiny.index("host_.WaitForGpu();"),
        )
        self.assertLess(
            tiny.index("host_.WaitForGpu();"),
            tiny.index("retained_buffers.clear();"),
        )
        self.assertLess(
            tiny.index("host_.WaitForGpu();"),
            tiny.index("host_.ClearVertexBuffer();"),
        )

    def test_contract_rejects_missing_wait_or_retention(self) -> None:
        for old in (
            "retained_buffers.emplace_back(vertex_buffer);",
            "host_.WaitForGpu();",
        ):
            with self.subTest(removed=old):
                mutated = SOURCE.replace(old, "/* removed */", 1)
                with self.assertRaises(AssertionError):
                    assert_retention_contract(mutated)

    def test_embedded_completion_is_measured_and_reported(self) -> None:
        mixed = function_body(
            SOURCE,
            "void VertexBufferAllocationTests::TestMixedSizes("
            "const std::string &name, DrawMode draw_mode)",
        )
        self.assertIn("QueryPerformanceCounter(&wait_start);", mixed)
        self.assertIn("embedded_completion_wait_us +=", mixed)
        self.assertIn("++embedded_completion_wait_calls;", mixed)
        finish = function_body(
            SOURCE,
            "void VertexBufferAllocationTests::FinishProfileWithOracle(\n"
            "    const std::string &name, DrawMode draw_mode,\n"
            "    const TestHost::ProfileResults &results, uint32_t work_checksum,\n"
            "    uint64_t embedded_completion_wait_us,\n"
            "    uint32_t embedded_completion_wait_calls)",
        )
        for field in (
            r'\"embedded_completion\"',
            r'\"scope\":\"per_body\"',
            r'\"included_in_raw_timing\":true',
            r'\"wait_calls_total\"',
            r'\"wait_calls_measured\"',
            r'\"wait_calls_warmup\"',
            r'\"wait_us_total\"',
        ):
            with self.subTest(field=field):
                self.assertIn(field, finish)
        self.assertIn(
            "results.iterations + results.warmup_iterations", finish
        )
        self.assertIn(
            "total_work_iterations = sample_count * measurement_iterations_multiplier",
            SUITE_SOURCE,
        )
        self.assertIn(".iterations = total_work_iterations", SUITE_SOURCE)

    def test_post_profile_oracle_resets_and_owns_state(self) -> None:
        body = function_body(
            SOURCE,
            "void VertexBufferAllocationTests::FinishProfileWithOracle(\n"
            "    const std::string &name, DrawMode draw_mode,\n"
            "    const TestHost::ProfileResults &results, uint32_t work_checksum,\n"
            "    uint64_t embedded_completion_wait_us,\n"
            "    uint32_t embedded_completion_wait_calls)",
        )
        required = (
            "host_.WaitForGpu();",
            "TestSuite::Initialize();",
            "host_.ClearVertexBuffer();",
            "host_.SetupFixedFunctionPassthrough();",
            "host_.SetVertexShaderProgram(shader);",
            "host_.SetBlend(false);",
            "host_.SetFinalCombiner0Just(TestHost::SRC_DIFFUSE);",
            "host_.SetFinalCombiner1Just(TestHost::SRC_ZERO, true, true);",
            "host_.PrepareDraw(kOracleBackground);",
            "CreateVertexAllocationOracleGeometry(host_, index_buffer);",
            "DrawVertexAllocationOracle(host_, draw_mode, index_buffer);",
            "ValidateVertexAllocationOracle(host_, assertion_base);",
        )
        for statement in required:
            with self.subTest(statement=statement):
                self.assertIn(statement, body)
        self.assertLess(body.index("host_.WaitForGpu();"), body.index("TestSuite::Initialize();"))
        self.assertLess(body.index("TestSuite::Initialize();"), body.index("host_.PrepareDraw"))
        self.assertLess(body.index("host_.PrepareDraw"), body.index("DrawVertexAllocationOracle"))
        self.assertLess(body.index("DrawVertexAllocationOracle"), body.rindex("host_.WaitForGpu();"))
        self.assertLess(body.rindex("host_.WaitForGpu();"), body.index("oracle_vertex_buffer.reset();"))
        setup = body.index("host_.SetupFixedFunctionPassthrough();")
        shader = body.index("host_.SetVertexShaderProgram(shader);")
        self.assertLess(setup, shader)
        self.assertNotIn("SetViewport", body[setup:])

    def test_oracle_uses_same_draw_mode(self) -> None:
        body = function_body(
            SOURCE,
            "static void DrawVertexAllocationOracle(\n"
            "    TestHost &host, VertexBufferAllocationTests::DrawMode draw_mode,\n"
            "    const std::vector<uint32_t> &index_buffer)",
        )
        for draw in (
            "host.DrawArrays",
            "host.DrawInlineBuffer",
            "host.DrawInlineArray",
            "host.DrawInlineElements16",
        ):
            with self.subTest(draw=draw):
                self.assertEqual(body.count(draw), 1)

    def test_oracle_is_fixed_nonoverlapping_flat_color_geometry(self) -> None:
        body = function_body(
            SOURCE,
            "static std::shared_ptr<VertexBuffer> "
            "CreateVertexAllocationOracleGeometry(\n"
            "    TestHost &host, std::vector<uint32_t> &index_buffer)",
        )
        self.assertIn("kOracleTileCount * 4", body)
        self.assertIn("kOracleTileWidth + kOracleTileGap", body)
        self.assertIn("kOracleTileHeight + kOracleTileGap", body)
        self.assertIn("kOracleColors[tile]", body)
        self.assertEqual(body.count("vertex->SetDiffuse(red, green, blue, 1.0f);"), 1)
        self.assertNotIn("SpecifiedGenerator", body)

    def test_pitch_aware_bgra_centers_have_exact_assertions(self) -> None:
        body = function_body(
            SOURCE,
            "static uint32_t ValidateVertexAllocationOracle(TestHost &host,\n"
            "                                               uint32_t assertion_base)",
        )
        required = (
            "volatile const uint8_t",
            "pb_back_buffer()",
            "pb_back_buffer_pitch()",
            "kOracleTileWidth / 2",
            "kOracleTileHeight / 2",
            "pixel[3]",
            "pixel[2]",
            "pixel[1]",
            "pixel[0]",
            "kOracleColors[tile], observed_argb",
            "kVertexAllocationOracleSourceKat, observed_kat",
        )
        for statement in required:
            with self.subTest(statement=statement):
                self.assertIn(statement, body)

    def test_source_kat_and_metadata_are_stable(self) -> None:
        colors_match = re.search(
            r"kOracleColors\[kOracleTileCount\] = \{(?P<body>.*?)\};",
            SOURCE,
            re.DOTALL,
        )
        self.assertIsNotNone(colors_match)
        colors = [int(value, 16) for value in re.findall(r"0x([0-9A-F]+)U", colors_match.group("body"))]
        self.assertEqual(len(colors), 16)
        self.assertEqual(oracle_kat(colors), 0xF36E0EC5)
        for field in (
            r'\"work_checksum\"',
            r'\"result_checksum\"',
            r'\"tile_center_kat\"',
            r'\"retained_vertex_ram\"',
        ):
            self.assertIn(field, SOURCE)
        mixed = function_body(
            SOURCE,
            "void VertexBufferAllocationTests::TestMixedSizes("
            "const std::string &name, DrawMode draw_mode)",
        )
        for work_input in (
            "static_cast<uint32_t>(draw_mode)",
            "kGeometrySeed",
            "results.iterations",
            "std::size(kMixedVertexBufferSizesSingleFrame)",
            "vertex_counts[idx]",
        ):
            with self.subTest(work_input=work_input):
                self.assertIn(work_input, mixed)
        generator = function_body(SOURCE, "uint32_t Next()")
        self.assertIn("state_ * 1664525U + 1013904223U", generator)

    def test_model_rejects_blank_reordered_and_channel_swapped_tiles(self) -> None:
        expected = [
            0xFF000000, 0xFFFF0000, 0xFF00FF00, 0xFF0000FF,
            0xFFFFFF00, 0xFFFF00FF, 0xFF00FFFF, 0xFFFFFFFF,
            0xFFFFFFFF, 0xFF00FFFF, 0xFFFF00FF, 0xFFFFFF00,
            0xFF0000FF, 0xFF00FF00, 0xFFFF0000, 0xFF000000,
        ]

        def validate(observed: list[int]) -> None:
            if observed != expected:
                raise AssertionError("exact tile oracle mismatch")
            if oracle_kat(observed) != 0xF36E0EC5:
                raise AssertionError("ordered KAT mismatch")

        validate(expected)
        invalid = (
            [0xFF182028] * 16,
            expected[1:] + expected[:1],
            [
                (color & 0xFF00FF00)
                | ((color & 0x00FF0000) >> 16)
                | ((color & 0x000000FF) << 16)
                for color in expected
            ],
        )
        for observed in invalid:
            with self.subTest(observed=observed[:2]):
                with self.assertRaises(AssertionError):
                    validate(observed)

    def test_header_exposes_oracle_finisher_only_inside_suite(self) -> None:
        self.assertIn("void FinishProfileWithOracle", HEADER)
        private = HEADER.split("private:", 1)[1]
        self.assertIn("void FinishProfileWithOracle", private)


if __name__ == "__main__":
    unittest.main()
