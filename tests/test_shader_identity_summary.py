import csv
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SUMMARIZER = REPO_ROOT / "tools" / "shader-identity-summary.py"


def miss(
    frame,
    stage,
    key,
    source,
    source_class,
    generation_us,
    compile_us,
    module_create_us,
    reflection_us,
):
    return (
        "nv2a/vk: shader-module-miss "
        f"profile_frame={frame} stage={stage} key={key:016x} "
        f"source={source:016x} source_class={source_class} "
        f"generation_us={generation_us} compile_us={compile_us} "
        f"module_create_us={module_create_us} reflection_us={reflection_us}"
    )


def summary(records, saturated=0, unique_sources=0, source_bytes=0):
    return (
        "nv2a/vk: shader-identity-summary "
        f"records={records} records_saturated={saturated} "
        f"unique_sources={unique_sources} source_bytes={source_bytes}"
    )


class ShaderIdentitySummaryTests(unittest.TestCase):
    def run_summary(self, lines, output_format="json"):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source = temp / "xemu-stderr.txt"
            output = temp / f"summary.{output_format}"
            source.write_text("\n".join(lines) + "\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SUMMARIZER),
                    str(source),
                    "--format",
                    output_format,
                    "--output",
                    str(output),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            rendered = output.read_text(encoding="utf-8") if output.exists() else None
            return completed, rendered

    def test_json_aggregates_frames_stages_and_repeat_identity(self):
        lines = [
            "unrelated stderr remains ignored",
            miss(9, 16, 0x30, 0xAA, "first", 3, 30, 7, 5),
            miss(8, 1, 0x10, 0xBB, "first", 1, 10, 2, 3),
            miss(8, 1, 0x10, 0xBB, "repeat", 4, 40, 8, 6),
            miss(8, 1, 0x20, 0xBB, "repeat", 2, 20, 4, 1),
            summary(4, unique_sources=2, source_bytes=256),
        ]

        completed, rendered = self.run_summary(lines)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(rendered)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["incomplete_reasons"], [])
        self.assertEqual(result["record_count"], 4)
        self.assertEqual(
            [(row["profile_frame"], row["stage"]) for row in result["aggregates"]],
            [(8, 1), (9, 16)],
        )
        frame = result["aggregates"][0]
        self.assertEqual(frame["misses"], 3)
        self.assertEqual(frame["source_classes"], {
            "first": 1,
            "repeat": 2,
            "saturated": 0,
        })
        self.assertEqual(frame["unique_key_count"], 2)
        self.assertEqual(frame["unique_source_count"], 1)
        self.assertEqual(frame["repeat_identity"], {
            "same_key_repeat": 1,
            "different_key_same_source": 1,
        })
        self.assertEqual(frame["timing_us"]["generation"], {"sum": 7, "max": 4})
        self.assertEqual(frame["timing_us"]["compile"], {"sum": 70, "max": 40})
        self.assertEqual(frame["timing_us"]["module_create"], {"sum": 14, "max": 8})
        self.assertEqual(frame["timing_us"]["reflection"], {"sum": 10, "max": 6})
        self.assertEqual(result["trace_summary"]["source_bytes"], 256)

    def test_markdown_and_csv_have_stable_clean_table_columns(self):
        lines = [
            miss(7, 8, 1, 2, "first", 10, 20, 30, 40),
            summary(1, unique_sources=1, source_bytes=80),
        ]

        markdown_completed, markdown = self.run_summary(lines, "markdown")
        csv_completed, csv_text = self.run_summary(lines, "csv")

        self.assertEqual(markdown_completed.returncode, 0, markdown_completed.stderr)
        self.assertIn("Status: **complete**", markdown)
        self.assertIn(
            "| Profile frame | Stage | Misses | First | Repeat | Saturated |",
            markdown,
        )
        self.assertEqual(csv_completed.returncode, 0, csv_completed.stderr)
        rows = list(csv.DictReader(io.StringIO(csv_text)))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["profile_frame"], "7")
        self.assertEqual(rows[0]["stage_name"], "geometry")
        self.assertEqual(rows[0]["compile_us_sum"], "20")
        self.assertEqual(rows[0]["reflection_us_max"], "40")

    def test_malformed_shader_record_fails_without_output(self):
        completed, rendered = self.run_summary([
            "nv2a/vk: shader-module-miss profile_frame=1 stage=1 broken",
            summary(1),
        ])

        self.assertNotEqual(completed.returncode, 0)
        self.assertIsNone(rendered)
        self.assertIn("malformed shader-module-miss line 1", completed.stderr)

    def test_saturation_marks_result_incomplete(self):
        lines = [
            miss(1, 1, 1, 1, "saturated", 1, 2, 3, 4),
            summary(1, saturated=1),
        ]
        completed, rendered = self.run_summary(lines)
        csv_completed, csv_text = self.run_summary(lines, "csv")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(rendered)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(
            result["incomplete_reasons"],
            ["record_source_tracking_saturated", "summary_records_saturated"],
        )
        self.assertEqual(csv_completed.returncode, 0, csv_completed.stderr)
        csv_row = next(csv.DictReader(io.StringIO(csv_text)))
        self.assertEqual(csv_row["status"], "incomplete")
        self.assertEqual(
            csv_row["incomplete_reasons"],
            "record_source_tracking_saturated;summary_records_saturated",
        )

    def test_missing_or_mismatched_summary_marks_result_incomplete(self):
        record = miss(1, 1, 1, 1, "first", 1, 2, 3, 4)

        missing_completed, missing_rendered = self.run_summary([record])
        mismatch_completed, mismatch_rendered = self.run_summary([
            record,
            summary(2, unique_sources=1, source_bytes=20),
        ])

        self.assertEqual(missing_completed.returncode, 0, missing_completed.stderr)
        self.assertEqual(json.loads(missing_rendered)["incomplete_reasons"], [
            "missing_summary",
        ])
        self.assertEqual(mismatch_completed.returncode, 0, mismatch_completed.stderr)
        self.assertEqual(json.loads(mismatch_rendered)["incomplete_reasons"], [
            "summary_record_count_mismatch",
        ])

    def test_duplicate_or_malformed_summary_fails(self):
        record = miss(1, 1, 1, 1, "first", 1, 2, 3, 4)
        duplicate, duplicate_rendered = self.run_summary([
            record,
            summary(1, unique_sources=1, source_bytes=20),
            summary(1, unique_sources=1, source_bytes=20),
        ])
        malformed, malformed_rendered = self.run_summary([
            record,
            "nv2a/vk: shader-identity-summary records=1 broken",
        ])

        self.assertNotEqual(duplicate.returncode, 0)
        self.assertIsNone(duplicate_rendered)
        self.assertIn("duplicate shader-identity-summary", duplicate.stderr)
        self.assertNotEqual(malformed.returncode, 0)
        self.assertIsNone(malformed_rendered)
        self.assertIn("malformed shader-identity-summary line 2", malformed.stderr)


if __name__ == "__main__":
    unittest.main()
