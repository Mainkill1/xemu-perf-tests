import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SUMMARIZER = REPO_ROOT / "utils" / "summarize_vk_texture_span.py"


class VkTextureSpanSummaryTests(unittest.TestCase):
    def run_summary(self, records, incomplete_tail=""):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source = temp / "telemetry.jsonl"
            output = temp / "summary.json"
            source.write_text(
                "".join(json.dumps(record) + "\n" for record in records)
                + incomplete_tail,
                encoding="utf-8",
            )
            completed = subprocess.run(
                [sys.executable, str(SUMMARIZER), str(source), "--output", str(output)],
                text=True,
                capture_output=True,
                check=False,
            )
            result = json.loads(output.read_text(encoding="utf-8")) if output.exists() else None
            return completed, result

    def test_aggregates_focused_cost_and_preserves_peak_frame(self):
        fields = {
            "clamped_cubemap_prepares_per_guest_frame": 0,
            "clamped_cubemap_sampled_levels_per_guest_frame": 0,
            "clamped_cubemap_storage_levels_per_guest_frame": 0,
            "clamped_cubemap_storage_span_bytes_per_guest_frame": 0,
            "clamped_cubemap_sampled_span_bytes_per_guest_frame": 0,
            "clamped_cubemap_extra_span_bytes_per_guest_frame": 0,
            "clamped_cubemap_surface_range_checks_per_guest_frame": 0,
            "clamped_cubemap_surface_range_check_cpu_us_per_guest_frame": 0,
            "clamped_cubemap_prepare_dirty_checks_per_guest_frame": 0,
            "clamped_cubemap_prepare_dirty_hits_per_guest_frame": 0,
            "clamped_cubemap_prepare_dirty_check_cpu_us_per_guest_frame": 0,
            "clamped_cubemap_bound_dirty_checks_per_guest_frame": 0,
            "clamped_cubemap_bound_dirty_hits_per_guest_frame": 0,
            "clamped_cubemap_bound_dirty_storage_span_bytes_per_guest_frame": 0,
            "clamped_cubemap_bound_dirty_sampled_span_bytes_per_guest_frame": 0,
            "clamped_cubemap_bound_dirty_extra_span_bytes_per_guest_frame": 0,
            "clamped_cubemap_bound_dirty_check_cpu_us_per_guest_frame": 0,
            "clamped_cubemap_content_hashes_per_guest_frame": 0,
            "clamped_cubemap_content_hash_texture_bytes_per_guest_frame": 0,
            "clamped_cubemap_content_hash_extra_texture_bytes_per_guest_frame": 0,
            "clamped_cubemap_content_hash_cpu_us_per_guest_frame": 0,
            "clamped_cubemap_uploads_per_guest_frame": 0,
            "clamped_cubemap_upload_cpu_us_per_guest_frame": 0,
        }
        first = dict(fields, type="frame", schema_version=6, guest_frame=671)
        first.update({
            "clamped_cubemap_prepares_per_guest_frame": 2,
            "clamped_cubemap_storage_span_bytes_per_guest_frame": 1200,
            "clamped_cubemap_sampled_span_bytes_per_guest_frame": 600,
            "clamped_cubemap_extra_span_bytes_per_guest_frame": 600,
            "clamped_cubemap_surface_range_check_cpu_us_per_guest_frame": 100,
            "clamped_cubemap_prepare_dirty_check_cpu_us_per_guest_frame": 200,
            "clamped_cubemap_bound_dirty_check_cpu_us_per_guest_frame": 300,
            "clamped_cubemap_content_hash_cpu_us_per_guest_frame": 400,
            "clamped_cubemap_upload_cpu_us_per_guest_frame": 500,
        })
        second = dict(fields, type="frame", schema_version=6, guest_frame=672)
        second.update({
            "clamped_cubemap_prepares_per_guest_frame": 1,
            "clamped_cubemap_extra_span_bytes_per_guest_frame": 100,
            "clamped_cubemap_content_hash_cpu_us_per_guest_frame": 50,
        })
        completed, result = self.run_summary([
            {"type": "schema", "schema_version": 6}, first, second
        ])

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(result["frame_count"], 2)
        self.assertEqual(result["totals"]["clamped_cubemap_prepares"], 3)
        self.assertEqual(result["totals"]["clamped_cubemap_extra_span_bytes"], 700)
        self.assertEqual(result["peak_focused_cpu_frame"]["guest_frame"], 671)
        self.assertEqual(result["peak_focused_cpu_frame"]["focused_cpu_us"], 1500)
        self.assertEqual(result["classification"], "possible_contributor_1_to_5ms")

    def test_rejects_telemetry_without_texture_span_fields(self):
        completed, result = self.run_summary([
            {"type": "schema", "schema_version": 5},
            {"type": "frame", "schema_version": 5, "guest_frame": 1},
        ])

        self.assertNotEqual(completed.returncode, 0)
        self.assertIsNone(result)
        self.assertIn("unsupported Vulkan telemetry schema", completed.stderr)

    def test_ignores_an_incomplete_final_write(self):
        fields = {
            f"clamped_cubemap_{name}_per_guest_frame": 0
            for name in (
                "prepares", "sampled_levels", "storage_levels",
                "storage_span_bytes", "sampled_span_bytes", "extra_span_bytes",
                "surface_range_checks", "surface_range_check_cpu_us",
                "prepare_dirty_checks", "prepare_dirty_hits",
                "prepare_dirty_check_cpu_us", "bound_dirty_checks",
                "bound_dirty_hits", "bound_dirty_storage_span_bytes",
                "bound_dirty_sampled_span_bytes", "bound_dirty_extra_span_bytes",
                "bound_dirty_check_cpu_us", "content_hashes",
                "content_hash_texture_bytes", "content_hash_extra_texture_bytes",
                "content_hash_cpu_us", "uploads", "upload_cpu_us",
            )
        }
        completed, result = self.run_summary([
            {"type": "schema", "schema_version": 6},
            dict(fields, type="frame", schema_version=6, guest_frame=1),
        ], incomplete_tail='{"type":"frame","guest_frame":2')

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(result["frame_count"], 1)


if __name__ == "__main__":
    unittest.main()
