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

    def test_aggregates_schema7_texture_lookup_and_cubemap_fields(self):
        clamped_fields = {
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
        texture_fields = {
            f"{name}_per_guest_frame": 0
            for name in (
                "texture_creates", "texture_key_hashes", "texture_key_hash_cpu_us",
                "texture_cache_lookups", "texture_cache_lookup_cpu_us",
                "texture_cache_saturated_lookups",
                "texture_cache_saturated_misses", "texture_cache_hits",
                "texture_cache_misses", "cubemap_prepares",
                "cubemap_same_level_prepares", "cubemap_texture_length_calls",
                "cubemap_texture_length_cpu_us", "cubemap_layouts",
                "cubemap_layout_cpu_us", "cubemap_uploads",
                "cubemap_upload_cpu_us",
            )
        }
        first = dict(clamped_fields, **texture_fields,
                     type="frame", schema_version=7, guest_frame=40)
        first.update({
            "texture_creates_per_guest_frame": 12,
            "texture_key_hashes_per_guest_frame": 12,
            "texture_key_hash_cpu_us_per_guest_frame": 300,
            "texture_cache_lookups_per_guest_frame": 12,
            "texture_cache_lookup_cpu_us_per_guest_frame": 900,
            "texture_cache_saturated_lookups_per_guest_frame": 10,
            "texture_cache_saturated_misses_per_guest_frame": 3,
            "texture_cache_hits_per_guest_frame": 9,
            "texture_cache_misses_per_guest_frame": 3,
            "cubemap_prepares_per_guest_frame": 2,
            "cubemap_layout_cpu_us_per_guest_frame": 100,
            "cubemap_upload_cpu_us_per_guest_frame": 200,
        })
        second = dict(clamped_fields, **texture_fields,
                      type="frame", schema_version=7, guest_frame=41)
        second.update({
            "texture_creates_per_guest_frame": 4,
            "texture_key_hashes_per_guest_frame": 4,
            "texture_key_hash_cpu_us_per_guest_frame": 50,
            "texture_cache_lookups_per_guest_frame": 4,
            "texture_cache_lookup_cpu_us_per_guest_frame": 100,
            "texture_cache_saturated_lookups_per_guest_frame": 4,
            "texture_cache_saturated_misses_per_guest_frame": 1,
            "texture_cache_hits_per_guest_frame": 3,
            "texture_cache_misses_per_guest_frame": 1,
        })

        completed, result = self.run_summary([
            {"type": "schema", "schema_version": 7}, first, second
        ])

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(result["texture_work"]["totals"]["texture_creates"], 16)
        self.assertEqual(
            result["texture_work"]["totals"]["texture_cache_saturated_misses"], 4
        )
        self.assertEqual(result["texture_work"]["peak_cpu_frame"]["guest_frame"], 40)
        self.assertEqual(result["texture_work"]["peak_cpu_frame"]["cpu_us"], 1500)

    def test_aggregates_schema8_pipeline_stage_fields(self):
        clamped_fields = {
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
        texture_fields = {
            f"{name}_per_guest_frame": 0
            for name in (
                "texture_creates", "texture_key_hashes", "texture_key_hash_cpu_us",
                "texture_cache_lookups", "texture_cache_lookup_cpu_us",
                "texture_cache_saturated_lookups",
                "texture_cache_saturated_misses", "texture_cache_hits",
                "texture_cache_misses", "cubemap_prepares",
                "cubemap_same_level_prepares", "cubemap_texture_length_calls",
                "cubemap_texture_length_cpu_us", "cubemap_layouts",
                "cubemap_layout_cpu_us", "cubemap_uploads",
                "cubemap_upload_cpu_us",
            )
        }
        pipeline_fields = {
            f"{name}_per_guest_frame": 0
            for name in (
                "pipeline_shader_binds", "pipeline_shader_bind_cpu_us",
                "pipeline_key_inits", "pipeline_key_init_cpu_us",
                "pipeline_key_hashes", "pipeline_key_hash_cpu_us",
                "pipeline_cache_lookups", "pipeline_cache_lookup_cpu_us",
                "pipeline_cache_hits", "pipeline_cache_misses",
                "pipeline_layout_creates", "pipeline_layout_create_cpu_us",
                "graphics_pipeline_creates",
                "graphics_pipeline_create_cpu_us",
            )
        }
        first = dict(clamped_fields, **texture_fields, **pipeline_fields,
                     type="frame", schema_version=8, guest_frame=70)
        first.update({
            "pipeline_shader_binds_per_guest_frame": 20,
            "pipeline_shader_bind_cpu_us_per_guest_frame": 4000,
            "pipeline_key_inits_per_guest_frame": 2,
            "pipeline_key_init_cpu_us_per_guest_frame": 100,
            "pipeline_key_hashes_per_guest_frame": 2,
            "pipeline_key_hash_cpu_us_per_guest_frame": 20,
            "pipeline_cache_lookups_per_guest_frame": 2,
            "pipeline_cache_lookup_cpu_us_per_guest_frame": 80,
            "pipeline_cache_hits_per_guest_frame": 1,
            "pipeline_cache_misses_per_guest_frame": 1,
            "pipeline_layout_creates_per_guest_frame": 1,
            "pipeline_layout_create_cpu_us_per_guest_frame": 200,
            "graphics_pipeline_creates_per_guest_frame": 1,
            "graphics_pipeline_create_cpu_us_per_guest_frame": 7000,
        })
        second = dict(clamped_fields, **texture_fields, **pipeline_fields,
                      type="frame", schema_version=8, guest_frame=71)
        second.update({
            "pipeline_shader_binds_per_guest_frame": 10,
            "pipeline_shader_bind_cpu_us_per_guest_frame": 1000,
        })

        completed, result = self.run_summary([
            {"type": "schema", "schema_version": 8}, first, second
        ])

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(result["pipeline_work"]["totals"]["pipeline_cache_misses"], 1)
        self.assertEqual(result["pipeline_work"]["peak_cpu_frame"]["guest_frame"], 70)
        self.assertEqual(result["pipeline_work"]["peak_cpu_frame"]["cpu_us"], 11400)


if __name__ == "__main__":
    unittest.main()
