import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / "resources/catalog.json").read_text())
DOC = (ROOT / "docs/vulkan-submission-lifetime-plan.md").read_text()
EXPECTED_IDS = {
    "game_load.cross_title_hotpath.queued_vertex_cpu_writes",
    "game_load.cross_title_hotpath.pgr2_small_draws",
    "game_load.cross_title_hotpath.surface_reuse",
    "game_load.cross_title_hotpath.pipeline_state_churn",
    "game_load.cross_title_hotpath.texture_binding_reuse",
    "game_load.cross_title_hotpath.s3tc_streaming_fenced_draws",
    "game_load.cross_title_hotpath.gpu_wait_control",
    "surface.cpu_read_after_gpu_write",
    "surface.surface_download_path",
    "vertex_buffer_allocation.disjoint_same_page",
    "vertex_buffer_allocation.ordered_same_page_overwrite",
    "vertex_buffer_allocation.three_generation_overwrite",
    "tiny_draw.inline_buffers.vertex_shader",
}


class VulkanSubmissionLifetimePlanContractTests(unittest.TestCase):
    def test_plans_select_only_catalog_leaves(self):
        by_id = {test["id"]: test for test in CATALOG["tests"]}
        for profile in ("fast-smoke", "quick", "sustained"):
            path = ROOT / "resources" / f"vulkan-submission-lifetimes-{profile}.json"
            config = json.loads(path.read_text())
            self.assertNotIn("test_suites", config)
            plan = config["resolved_plan"]
            ids = {test["id"] for test in plan["tests"]}
            self.assertEqual(ids, EXPECTED_IDS)
            self.assertEqual(plan["selected_leaf_count"], len(EXPECTED_IDS))
            self.assertEqual(plan["catalog_id"], CATALOG["catalog_id"])
            self.assertTrue(plan["plan_id"].startswith("sha256:"))
            self.assertTrue(all(by_id[test_id]["kind"] == "leaf" for test_id in ids))

    def test_plan_has_required_lifetime_and_timing_gates(self):
        for phrase in ("zero live pins", "zero in-flight slots", "serial order",
                       "complete emitted fetch span", "p95", "5%"):
            self.assertIn(phrase, DOC)


if __name__ == "__main__":
    unittest.main()
