import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ResultViewerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.menu = (ROOT / "src/menu_item.cpp").read_text(encoding="utf-8")
        cls.store = (ROOT / "src/result_store.cpp").read_text(encoding="utf-8")
        cls.store_header = (ROOT / "src/result_store.h").read_text(encoding="utf-8")
        cls.host = (ROOT / "src/test_host.cpp").read_text(encoding="utf-8")
        cls.statistics = (ROOT / "src/result_statistics.cpp").read_text(encoding="utf-8")

    def test_new_records_store_distribution_and_comparison_contract(self):
        for field in ("median_us", "p95_us", "mad_us", "unit", "direction"):
            self.assertIn(f'"    \\"{field}\\":', self.host)
        self.assertIn("nearest-rank p95", self.statistics)
        self.assertIn("MedianOfSorted", self.statistics)

    def test_selected_record_samples_are_bounded_and_loaded_on_demand(self):
        self.assertIn("kResultViewerSampleScratchBytes", self.store_header)
        self.assertIn("ReadStoredResultSamples", self.store)
        self.assertIn("result.values.size() >= max_samples", self.store)
        self.assertIn("result.stride *= 2U", self.store)
        self.assertIn("ReadStoredResultSamples(path_, record_->id)", self.menu)

    def test_graph_density_derives_from_visible_plot_width(self):
        self.assertIn("std::min<size_t>(kPlotWidth, samples_.size())", self.menu)
        self.assertIn("kPlotWidth / kMinimumHistogramBarWidth", self.menu)
        self.assertIn("DrawTrace", self.menu)
        self.assertIn("DrawHistogram", self.menu)
        self.assertIn("kViewerWarning", self.menu)

    def test_graph_layout_has_axes_and_selected_point_details(self):
        for token in (
            "constexpr int kPlotLeft = 90",
            "constexpr int kPlotTop = 205",
            "constexpr int kPlotWidth = 510",
            "DrawDurationAxes",
            "L/R S%lu-%lu min/avg/max",
            "L/R bin",
            "count %lu",
            "pb_printat(15, 0",
        ):
            self.assertIn(token, self.menu)
        graph_draw = self.menu.split("void MenuItemStoredRecord::Draw()", 1)[1].split(
            "bool MenuItemStoredRecord::HandleX", 1
        )[0]
        self.assertNotIn('pb_print("', graph_draw)

    def test_results_have_failure_filter_partial_state_and_stable_id_compare(self):
        for token in (
            "PARTIAL - final totals unavailable",
            "Recovered records:",
            "failures_only_",
            "A/B comparison by stable record ID",
            "record.unit != found->second.unit",
            "record.direction != found->second.direction",
        ):
            self.assertIn(token, self.menu)

    def test_results_expose_graphs_and_a_b_trace_overlay(self):
        for token in (
            'std::make_shared<MenuItem>("Graphs"',
            "MenuItemResultComparisonRecord",
            "baseline cyan | candidate green",
            "Sample procedures differ; trace overlay disabled",
        ):
            self.assertIn(token, self.menu)

    def test_bundled_reference_is_complete_unique_and_measured(self):
        records = json.loads(
            (ROOT / "resources/reference-results.txt").read_text(encoding="utf-8")
        )
        self.assertEqual(len(records), 141)
        self.assertEqual(len({record["id"] for record in records}), 141)
        measured = [record for record in records if record.get("raw_results")]
        self.assertGreaterEqual(len(measured), 130)
        self.assertTrue(all(record.get("sample_count") == len(record["raw_results"])
                            for record in measured))
        provenance = (ROOT / "resources/reference-results-provenance.txt").read_text(
            encoding="utf-8"
        )
        for token in ("completed regression-only benchmark", "OpenGL", "1x",
                      "d73326b62199", "141 of 141"):
            self.assertIn(token, provenance)


if __name__ == "__main__":
    unittest.main()
