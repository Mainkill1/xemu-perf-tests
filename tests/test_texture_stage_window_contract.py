from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/tests/game_load_composite_tests.cpp").read_text()
HEADER = (ROOT / "src/tests/game_load_composite_tests.h").read_text()
SUITE_HEADER = (ROOT / "src/tests/test_suite.h").read_text()
CONFIG = (ROOT / "src/runtime_config.cpp").read_text()


EXPECTED_KEYS = (
    "dxt1_same_address_wait",
    "dxt1_same_address_queued",
    "dxt1_ring",
    "dxt1_dirty_once",
    "rgba8_same_address_wait",
    "rgba8_same_address_queued",
    "rgba8_ring",
    "rgba8_dirty_once",
    "bc2_native_eligible",
    "bc2_bordered_fallback",
    "bc3_native_eligible",
    "bc3_bordered_fallback",
)


class TextureStageWindowContractTests(unittest.TestCase):
    def test_stage_count_is_exactly_twelve(self) -> None:
        self.assertIn("kGameLoadCompositeS3tcSyncFactorStageCount = 12", SUITE_HEADER)
        self.assertIn(
            "TestSuite::Config::kGameLoadCompositeS3tcSyncFactorStageCount",
            SOURCE,
        )

    def test_stage_keys_are_unique_and_complete(self) -> None:
        keys = re.findall(r'\.stage_key = "([^"]+)"', SOURCE)
        factor_keys = [key for key in keys if key in EXPECTED_KEYS]
        self.assertEqual(factor_keys, list(EXPECTED_KEYS))

    def test_record_names_are_strictly_ordered(self) -> None:
        names = re.findall(r'\.record_name = "10-S3tcSyncFactor-(\d\d)-', SOURCE)
        self.assertEqual(names, [f"{index:02d}" for index in range(1, 13)])

    def test_each_key_maps_to_an_independent_mask_bit(self) -> None:
        for index, key in enumerate(EXPECTED_KEYS):
            self.assertIn(f'if (name == "{key}") return {index};', CONFIG)

    def test_zero_or_out_of_range_masks_are_rejected(self) -> None:
        self.assertIn("!config.game_load_composite_s3tc_sync_factor_stage_mask", CONFIG)
        self.assertIn("must select bits 0 through 11", CONFIG)

    def test_named_stage_selection_cannot_select_zero_records(self) -> None:
        self.assertIn("stage_list_mask |= 1U << index;", CONFIG)
        self.assertIn("s3tc_sync_factor selects no stages", CONFIG)

    def test_mask_is_copied_into_suite_instance(self) -> None:
        self.assertIn("s3tc_sync_factor_stage_mask_", HEADER)
        self.assertIn(
            "config.game_load_composite_s3tc_sync_factor_stage_mask", SOURCE
        )

    def test_unselected_stage_is_skipped_before_context_and_profile(self) -> None:
        skip = SOURCE.index("if (!(s3tc_sync_factor_stage_mask_ & (1U << stage_index)))")
        count = SOURCE.index("++stage_record_count;", skip)
        context = SOURCE.index("SetXemuPerfEventContext(0xA001U + stage_index", count)
        profile = SOURCE.index("auto results = Profile(definition.record_name", context)
        self.assertLess(skip, count)
        self.assertLess(count, context)
        self.assertLess(context, profile)

    def test_each_profile_window_precedes_its_oracle_and_record(self) -> None:
        profile = SOURCE.index("auto results = Profile(definition.record_name")
        oracle = SOURCE.index("ValidateS3tcSyncFactorFramebuffer(", profile)
        record = SOURCE.index("host_.RecordProfileResult", oracle)
        self.assertLess(profile, oracle)
        self.assertLess(oracle, record)

    def test_summary_is_after_all_stage_records(self) -> None:
        record = SOURCE.index("host_.RecordProfileResult", SOURCE.index("RunS3tcSyncFactor()"))
        summary = SOURCE.index("std::ostringstream summary_metadata", record)
        finish = SOURCE.index("host_.FinishDraw(", summary)
        self.assertLess(record, summary)
        self.assertLess(summary, finish)

    def test_summary_reports_exact_selected_count_and_mask(self) -> None:
        self.assertIn(
            'summary_metadata << "\\"stage_mask\\":" << s3tc_sync_factor_stage_mask_',
            SOURCE,
        )
        self.assertIn(
            'summary_metadata << "\\"stage_record_count\\":" << stage_record_count',
            SOURCE,
        )

    def test_records_report_absolute_and_selected_order(self) -> None:
        self.assertIn('metadata << "\\"stage_index\\":" << stage_index', SOURCE)
        self.assertIn(
            'metadata << "\\"selected_record_ordinal\\":" << stage_record_count',
            SOURCE,
        )

    def test_summary_is_excluded_from_stage_window_mapping(self) -> None:
        self.assertIn(
            '"\\"exclude_from_stage_window_mapping\\":true,"', SOURCE
        )


if __name__ == "__main__":
    unittest.main()
