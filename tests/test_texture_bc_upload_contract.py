from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/tests/game_load_composite_tests.cpp").read_text()
HEADER = (ROOT / "src/tests/game_load_composite_tests.h").read_text()


COLORS = (
    0x0000, 0xFFFF, 0xF800, 0x07E0, 0x001F, 0xFFE0, 0xF81F, 0x07FF,
    0x7800, 0x03E0, 0x000F, 0x7BEF, 0xFC10, 0x83E0, 0x8010, 0x0410,
)


def corpus_kat(bc3: bool, bytes_per_texture: int) -> int:
    value = 2166136261
    for color in COLORS:
        alpha = bytes((0xFF, 0xFF)) + bytes(6) if bc3 else bytes((0xFF,)) * 8
        block = alpha + bytes((color & 0xFF, color >> 8)) * 2 + bytes(4)
        for byte in block * (bytes_per_texture // len(block)):
            value = ((value ^ byte) * 16777619) & 0xFFFFFFFF
    return value


class TextureBcUploadContractTests(unittest.TestCase):
    def test_bc2_uses_xbox_dxt23_format(self) -> None:
        self.assertEqual(
            SOURCE.count(
                ".format = NV097_SET_TEXTURE_FORMAT_COLOR_L_DXT23_A8R8G8B8"
            ),
            2,
        )

    def test_bc3_uses_xbox_dxt45_format(self) -> None:
        self.assertEqual(
            SOURCE.count(
                ".format = NV097_SET_TEXTURE_FORMAT_COLOR_L_DXT45_A8R8G8B8"
            ),
            2,
        )

    def test_bc2_has_native_and_fallback_records(self) -> None:
        self.assertIn('.stage_key = "bc2_native_eligible"', SOURCE)
        self.assertIn('.stage_key = "bc2_bordered_fallback"', SOURCE)

    def test_bc3_has_native_and_fallback_records(self) -> None:
        self.assertIn('.stage_key = "bc3_native_eligible"', SOURCE)
        self.assertIn('.stage_key = "bc3_bordered_fallback"', SOURCE)

    def test_native_cases_are_borderless_2d(self) -> None:
        self.assertEqual(SOURCE.count('.upload_expectation = "native_bc_eligible"'), 6)
        self.assertGreaterEqual(SOURCE.count('.texture_shape = "borderless_2d"'), 10)

    def test_fallback_cases_are_explicit_bordered_2d(self) -> None:
        self.assertEqual(
            SOURCE.count('.upload_expectation = "decoded_fallback_required"'), 2
        )
        self.assertEqual(SOURCE.count('.texture_shape = "bordered_2d"'), 2)
        self.assertEqual(SOURCE.count(".bordered = true"), 2)

    def test_bordered_layout_doubles_each_axis(self) -> None:
        self.assertIn(
            "(kTextureWidth * 2) * (kTextureHeight * 2)", SOURCE
        )
        self.assertIn("kBcBorderedFallbackWork.texture_bytes == 4 * 1024 * 1024", SOURCE)

    def test_bc2_and_bc3_solid_blocks_are_distinct(self) -> None:
        self.assertIn("memset(destination.data() + offset, 0xFF, 8);", SOURCE)
        self.assertIn("destination[offset + 0] = 0xFF;", SOURCE)
        self.assertIn("memset(destination.data() + offset + 2, 0, 6);", SOURCE)

    def test_bc_source_corpora_have_fixed_kats(self) -> None:
        self.assertIn("kS3tcSyncFactorBc2NativeSourceKat = 0x0330DDC5", SOURCE)
        self.assertIn("kS3tcSyncFactorBc3NativeSourceKat = 0x10E7DDC5", SOURCE)
        self.assertIn("kS3tcSyncFactorBc2BorderedSourceKat = 0x896D9DC5", SOURCE)
        self.assertIn("kS3tcSyncFactorBc3BorderedSourceKat = 0xC0499DC5", SOURCE)
        self.assertIn("factor_bc2_source_checksum_", HEADER)
        self.assertIn("factor_bc3_source_checksum_", HEADER)

    def test_each_record_emits_the_kat_for_its_exact_shape(self) -> None:
        self.assertIn("S3tcSyncFactorSourceKat(definition)", SOURCE)
        self.assertIn('metadata << "\\"source_kat\\":\\""', SOURCE)

    def test_known_input_model_reproduces_all_bc_shape_kats(self) -> None:
        self.assertEqual(corpus_kat(False, 256 * 256), 0x0330DDC5)
        self.assertEqual(corpus_kat(True, 256 * 256), 0x10E7DDC5)
        self.assertEqual(corpus_kat(False, 512 * 512), 0x896D9DC5)
        self.assertEqual(corpus_kat(True, 512 * 512), 0xC0499DC5)

    def test_bc_routes_use_common_visible_tile_oracle(self) -> None:
        self.assertIn("FactorTileResultChecksum(seed, dirty_once)", SOURCE)
        self.assertIn("work.visible_tiles", SOURCE)
        self.assertIn("work.unique_colors", SOURCE)


if __name__ == "__main__":
    unittest.main()
