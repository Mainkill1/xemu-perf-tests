import importlib.util
import unittest
from pathlib import Path


PATH = Path(__file__).resolve().parents[1] / "utils/analyze_cause_counters.py"
SPEC = importlib.util.spec_from_file_location("cause_counters", PATH)
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)


def row(tid, time, count):
    result = {"tid": tid, "utc_us": time, "mono_us": time}
    for origin in ("main", "helper", "other"):
        for key in ("call", "hit", "empty", "pc", "cs", "flags", "cflags",
                    "qht_hit", "qht_miss"):
            result[f"{origin}_{key}"] = 0
    result.update(helper_call=count, helper_hit=count // 2,
                  helper_pc=count // 2, helper_qht_hit=count // 2,
                  dirty_reset=count, dirty_zero_arm=count // 2,
                  dirty_entries=count * 100, dirty_armed=count // 2)
    return result


class CauseCounterTests(unittest.TestCase):
    def test_window_excludes_warmup_and_keeps_thread_deltas_separate(self):
        rows = [row(1, 0, 0), row(1, 1_000_000, 10),
                row(2, 1_000_000, 100), row(1, 3_000_000, 30),
                row(2, 3_000_000, 140), row(1, 4_000_000, 200)]
        result = TOOL.analyze(rows, 1_000_000, 3_000_000)
        self.assertFalse(result["performance_acceptance"])
        first, second = result["threads"]
        self.assertEqual(first["delta"]["helper_call"], 20)
        self.assertEqual(second["delta"]["helper_call"], 40)
        self.assertEqual(first["rates_per_second"]["helper_call"], 10)
        self.assertEqual(first["derived"]["helper_cache_hit_percent"], 50)
        self.assertEqual(first["derived"]["zero_arm_scan_percent"], 50)

    def test_partial_lookup_cannot_produce_a_complete_verdict(self):
        rows = [row(1, 1, 10), row(1, 2, 20)]
        rows[1]["helper_qht_hit"] -= 1
        with self.assertRaisesRegex(ValueError, "lookup accounting"):
            TOOL.analyze(rows, 1, 2)

    def test_counter_reset_is_rejected_even_if_endpoints_increase(self):
        rows = [row(1, 1, 10), row(1, 2, 2), row(1, 3, 20)]
        with self.assertRaisesRegex(ValueError, "counter decreased"):
            TOOL.analyze(rows, 1, 3)

    def test_missing_or_insufficient_samples_are_not_zero_work(self):
        for rows in ([], [row(1, 1, 10)]):
            with self.subTest(rows=len(rows)), self.assertRaises(ValueError):
                TOOL.analyze(rows, 1, 2)

    def test_monotonic_clock_defines_rate_and_must_advance(self):
        rows = [row(1, 1_000_000, 10), row(1, 3_000_000, 30)]
        rows[1]["mono_us"] = 5_000_000
        self.assertEqual(TOOL.analyze(rows, 1_000_000, 3_000_000)
                         ["threads"][0]["rates_per_second"]["helper_call"], 5)
        rows[1]["mono_us"] = rows[0]["mono_us"]
        with self.assertRaisesRegex(ValueError, "clock"):
            TOOL.analyze(rows, 1_000_000, 3_000_000)

    def test_changed_counter_schema_is_rejected(self):
        rows = [row(1, 1, 10), row(1, 2, 20)]
        del rows[1]["dirty_armed"]
        with self.assertRaisesRegex(ValueError, "schema"):
            TOOL.analyze(rows, 1, 2)


if __name__ == "__main__":
    unittest.main()
