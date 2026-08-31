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


if __name__ == "__main__":
    unittest.main()
