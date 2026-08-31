from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/tests/game_load_composite_tests.cpp").read_text()


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


WORK = function_body(
    "uint32_t GameLoadCompositeTests::RunS3tcSyncFactorWork(\n"
    "    uint32_t format, bool per_draw_wait, bool dirty_once,\n"
    "    bool queued_same_address, bool bordered, uint32_t seed)"
)


class TextureQueuedUpdateContractTests(unittest.TestCase):
    def test_dxt1_queued_route_is_named(self) -> None:
        self.assertIn('.stage_key = "dxt1_same_address_queued"', SOURCE)

    def test_rgba8_queued_route_is_named(self) -> None:
        self.assertIn('.stage_key = "rgba8_same_address_queued"', SOURCE)

    def test_both_routes_declare_changing_payloads(self) -> None:
        self.assertEqual(
            SOURCE.count(
                '.revalidation_route = "same_address_changing_payload_queued"'
            ),
            2,
        )

    def test_both_routes_declare_no_per_draw_wait(self) -> None:
        self.assertEqual(
            SOURCE.count(
                '.synchronization = "same_address_no_per_draw_wait_final_wait"'
            ),
            2,
        )

    def test_queued_routes_reuse_slot_zero(self) -> None:
        self.assertIn("(per_draw_wait || queued_same_address) ? 0U : draw", WORK)

    def test_every_generation_is_written_before_its_draw(self) -> None:
        write = WORK.index("memcpy(destination, source.data(), texture_bytes);")
        bind = WORK.index("BindTextureStage0Address(destination);", write)
        draw = WORK.index("DrawFactorTile(host_, attributes, draw);", bind)
        self.assertLess(write, bind)
        self.assertLess(bind, draw)

    def test_wait_is_conditional_inside_draw_loop(self) -> None:
        draw = WORK.index("DrawFactorTile(host_, attributes, draw);")
        conditional = WORK.index("if (per_draw_wait)", draw)
        final_wait = WORK.index("host_.WaitForGpu();", conditional + 1)
        self.assertLess(conditional, final_wait)

    def test_final_completion_is_unconditional(self) -> None:
        tail = WORK[WORK.rindex("// Both synchronization cells") :]
        self.assertIn("host_.WaitForGpu();", tail)

    def test_dxt1_queued_counts_are_exact(self) -> None:
        for contract in (
            "kDxt1QueuedSameAddressWork.texture_writes == 16",
            "kDxt1QueuedSameAddressWork.payload_generations == 16",
            "kDxt1QueuedSameAddressWork.distinct_addresses == 1",
            "kDxt1QueuedSameAddressWork.per_draw_waits == 0",
            "kDxt1QueuedSameAddressWork.gpu_waits == 1",
        ):
            self.assertIn(contract, SOURCE)

    def test_rgba8_queued_byte_count_is_exact(self) -> None:
        self.assertIn(
            "kRgba8QueuedSameAddressWork.texture_bytes == 4 * 1024 * 1024",
            SOURCE,
        )


if __name__ == "__main__":
    unittest.main()
