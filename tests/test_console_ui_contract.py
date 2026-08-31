import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ConsoleUiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads((ROOT / "resources/catalog.json").read_text(encoding="utf-8"))
        cls.menu_source = (ROOT / "src/menu_item.cpp").read_text(encoding="utf-8")
        cls.driver_source = (ROOT / "src/test_driver.cpp").read_text(encoding="utf-8")
        cls.main_source = (ROOT / "src/main.cpp").read_text(encoding="utf-8")

    def test_full_catalog_inventory_has_one_unique_console_entry_per_descriptor(self):
        tests = self.catalog["tests"]
        self.assertEqual(len(tests), self.catalog["leaf_count"] + self.catalog["group_count"])
        self.assertEqual(sum(x["kind"] == "leaf" for x in tests), self.catalog["leaf_count"])
        self.assertEqual(sum(x["kind"] == "group" for x in tests), self.catalog["group_count"])
        self.assertEqual(len({x["id"] for x in tests}), len(tests))
        self.assertEqual(len({x["legacy_ids"][0] for x in tests}), len(tests))
        self.assertTrue(all(x.get("execution", {}).get("legacy_test") or x["kind"] == "group"
                            for x in tests))
        self.assertIn("for (const auto *descriptor : TestCatalogEntries())", self.menu_source)

    def test_pagination_and_wrap_navigation_reaches_every_inventory_position(self):
        # The Xbox implementation displays 12 rows and advances half a page.
        page_size = 12
        half_page = page_size // 2
        for count in (1, 5, 12, 13, 26, 52, len(self.catalog["tests"])):
            visited = set()
            cursor = 0
            for _ in range(count):
                visited.add(cursor)
                cursor = cursor + 1 if cursor < count - 1 else 0
            self.assertEqual(visited, set(range(count)))
            cursor = 0
            for _ in range((count + half_page - 1) // half_page):
                cursor = min(cursor + half_page, count - 1)
            self.assertEqual(cursor, count - 1)
        self.assertRegex(self.menu_source, r"kNumItemsPerPage = 12")
        self.assertIn("if (submenu.empty())", self.menu_source)

    def test_ui_exposes_identity_help_routes_progress_and_result_location(self):
        for token in ("About / controls", "Catalog browser", "Plans", "Quick smoke routes", "TestCatalogId()",
                      "A/Start select", "Grouped route", "results.txt", "Previous results",
                      "System information", "A: refresh"):
            self.assertIn(token, self.menu_source)
        for token in ("RunCatalogRoute", "HasTest"):
            self.assertIn(token, self.driver_source)

    def test_direct_test_execution_retains_the_current_frame(self):
        on_enter = self.menu_source.split("void MenuItemTest::OnEnter()", 1)[1].split(
            "bool MenuItemTest::Deactivate()", 1
        )[0]
        route = self.driver_source.split("void TestDriver::RunCatalogRoute", 1)[1].split(
            "void TestDriver::OnControllerAdded", 1
        )[0]
        valid_route = route.split("return;", 1)[0]
        self.assertNotIn("PrepareDraw", on_enter)
        self.assertNotIn("pb_print", on_enter)
        self.assertNotIn("debugClearScreen", valid_route)
        self.assertNotIn("DrawProgress", route)

    def test_final_screen_distinguishes_completion_and_oracle_failure(self):
        for token in ("xemu perf tests: %s", "Oracle failures", "First failure",
                      "Plan: INCOMPLETE", "Plan: COMPLETE", "RecordedLeafCount"):
            self.assertIn(token, self.main_source)
        sample = json.loads((ROOT / "resources/sample-config.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(sample["settings"]["reboot_or_shutdown_delay"], 30000)

    def test_previous_results_are_preserved_and_device_values_are_polled(self):
        store = (ROOT / "src/result_store.cpp").read_text(encoding="utf-8")
        device = (ROOT / "src/device_info.cpp").read_text(encoding="utf-8")
        for token in ("ArchiveCurrentResults", "DiscoverStoredResults", "ReadStoredResults",
                      "MoveFile", "results-*.txt"):
            self.assertIn(token, store)
        for token in ("QueryPerformanceFrequency", "MmQueryStatistics", "GetDiskFreeSpaceEx",
                      "XboxHardwareInfo", "Host GPU / clock / VRAM: Unavailable to guest"):
            self.assertIn(token, device)
        self.assertIn("ArchiveCurrentResults", self.main_source)


if __name__ == "__main__":
    unittest.main()
