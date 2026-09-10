#!/usr/bin/env python3
"""Production-function controls for direction-normalized runner reporting."""

import ast
import hashlib
import math
import os
import random
import shutil
import statistics
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ENV = "XEMU_PGRAPH_RUNNER_ROOT"
PAIR_SHA256 = "e358b55d940e361bf57ef64a7a5cde83fc267d885191c813e7616764a88ee58a"
OUTPUT_ONLY_PAIR_SHA256 = (
    "7e1a7ccc3fefc259775bffb5ba3198f05b3549b511ca4f342195b07716850e0e"
)
OUTPUT_ONLY_PATCH = ROOT / "utils/host-runner/run-pair-output-only-forwarding.patch"
IMPROVEMENT_PATCH = ROOT / "utils/host-runner/run-pair-improvement-semantics.patch"


class PairRunError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_functions(path: Path, names: tuple[str, ...], namespace: dict) -> dict:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    missing = set(names) - set(found)
    if missing:
        raise AssertionError(f"missing production functions: {sorted(missing)}")
    for name in names:
        module = ast.Module(body=[found[name]], type_ignores=[])
        exec(compile(module, str(path), "exec"), namespace)
    return namespace


class ImprovementSemanticsTests(unittest.TestCase):
    def patched_pair(self):
        fixture_name = os.environ.get(FIXTURE_ENV)
        if fixture_name is None:
            self.skipTest(f"set {FIXTURE_ENV} to run the external runner fixture")
        source = Path(fixture_name) / "run-pair.py"
        self.assertEqual(sha256(source), PAIR_SHA256)
        self.assertTrue(IMPROVEMENT_PATCH.is_file(), "improvement patch is missing")
        with tempfile.TemporaryDirectory() as temporary:
            pair = Path(temporary) / "run-pair.py"
            shutil.copyfile(source, pair)
            for patch in (OUTPUT_ONLY_PATCH, IMPROVEMENT_PATCH):
                result = subprocess.run(
                    ["patch", "--batch", "--forward", "-p0", "-i", str(patch)],
                    cwd=temporary,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                if patch == OUTPUT_ONLY_PATCH:
                    self.assertEqual(sha256(pair), OUTPUT_ONLY_PAIR_SHA256)
            yield pair

    def production_functions(self, pair: Path) -> dict:
        return extract_functions(
            pair,
            (
                "percentile",
                "metric_seed",
                "bootstrap_median_ci",
                "classify_ratio",
                "calculate_improvement_percent",
                "improvement_interval_from_ratio",
                "format_improvement",
                "summarize_metric",
                "summarize_nonnegative_metric",
                "render_markdown",
            ),
            {
                "Any": Any,
                "BOOTSTRAP_SAMPLES": 100,
                "PairRunError": PairRunError,
                "hashlib": hashlib,
                "math": math,
                "random": random,
                "statistics": statistics,
            },
        )

    def test_direction_normalizes_favorable_and_unfavorable_changes(self):
        for pair in self.patched_pair():
            function = self.production_functions(pair)["calculate_improvement_percent"]
            cases = (
                (100, 110, "+good", 10.0),
                (100, 90, "+good", -10.0),
                (100, 90, "+bad", 10.0),
                (100, 110, "+bad", -10.0),
                (100, 100, "+good", 0.0),
                (100, 100, "+bad", 0.0),
            )
            for baseline, candidate, direction, expected in cases:
                with self.subTest(direction=direction, candidate=candidate):
                    self.assertAlmostEqual(
                        function(baseline, candidate, direction), expected
                    )
            self.assertIsNone(function(0, 1, "+good"))
            self.assertIsNone(function(100, 90, "N/A"))
            with self.assertRaisesRegex(ValueError, "raw-positive marker"):
                function(100, 90, "unknown")

    def test_confidence_interval_direction_and_bound_order(self):
        for pair in self.patched_pair():
            function = self.production_functions(pair)["improvement_interval_from_ratio"]
            lower_is_better = function(0.80, 0.95, "+bad")
            self.assertAlmostEqual(lower_is_better["lower"], 5.0)
            self.assertAlmostEqual(lower_is_better["upper"], 20.0)
            higher_is_better = function(1.05, 1.20, "+good")
            self.assertAlmostEqual(higher_is_better["lower"], 5.0)
            self.assertAlmostEqual(higher_is_better["upper"], 20.0)
            self.assertIsNone(function(0.80, 0.95, "N/A"))

    def test_formatter_uses_signed_nonzero_and_neutral_zero(self):
        for pair in self.patched_pair():
            function = self.production_functions(pair)["format_improvement"]
            self.assertEqual(function(10.0), "+10.00%")
            self.assertEqual(function(-10.0), "-10.00%")
            self.assertEqual(function(-0.00001), "0.00%")
            self.assertEqual(function(None), "N/A")

    def test_timing_summary_adds_improvement_without_removing_raw_ratio(self):
        for pair in self.patched_pair():
            function = self.production_functions(pair)["summarize_metric"]
            result = function([100.0] * 15, [90.0] * 15, 7, "timing", "us")
            self.assertEqual(result["raw_positive_is"], "+bad")
            self.assertEqual(result["metric_direction"], "lower_is_better")
            self.assertAlmostEqual(result["median_change_percent"], -10.0)
            self.assertAlmostEqual(result["median_improvement_percent"], 10.0)
            self.assertAlmostEqual(
                result["median_candidate_over_baseline_ratio"], 0.9
            )
            self.assertAlmostEqual(result["improvement_95_ci"]["lower"], 10.0)
            self.assertAlmostEqual(result["improvement_95_ci"]["upper"], 10.0)
            self.assertEqual(result["classification"], "FASTER")

    def test_contextual_metrics_do_not_invent_improvement(self):
        for pair in self.patched_pair():
            function = self.production_functions(pair)["summarize_nonnegative_metric"]
            contextual = function([100.0], [90.0], "events", "N/A")
            self.assertIsNone(contextual["median_improvement_percent"])
            self.assertEqual(contextual["improvement_unavailable_reason"], "contextual metric")
            lower_is_better = function([100.0], [90.0], "bytes", "+bad")
            self.assertAlmostEqual(
                lower_is_better["median_improvement_percent"], 10.0
            )
            zero_reference = function([0.0], [1.0], "events", "+bad")
            self.assertIsNone(zero_reference["median_improvement_percent"])
            self.assertEqual(
                zero_reference["improvement_unavailable_reason"], "zero baseline"
            )

    def test_markdown_uses_improvement_columns_and_keeps_raw_values(self):
        for pair in self.patched_pair():
            namespace = self.production_functions(pair)
            timing = namespace["summarize_metric"](
                [100.0] * 15, [90.0] * 15, 7, "timing", "guest_us"
            )
            timing.update(
                {
                    "correctness_status": "VERIFIED",
                    "correctness_verified": True,
                }
            )
            payload = {
                "status": "PASSED",
                "error": None,
                "configuration": {
                    "profile": "test-profile",
                    "workload_label": "test-profile",
                    "backend": "vulkan",
                    "scale": 1,
                    "vsync": False,
                    "memory_megabytes": 64,
                    "warmup_pairs": 3,
                    "measured_pairs": 15,
                    "seed": 7,
                    "warmup_iterations": 2,
                    "measurement_iterations_multiplier": 4,
                    "target_measurement_seconds": 60,
                    "minimum_measurement_seconds": 15,
                    "minimum_warmup_seconds": 5,
                    "allow_short_smoke": False,
                    "completion_mode": "per_iteration",
                    "baseline_host_telemetry": "off",
                    "candidate_host_telemetry": "off",
                    "baseline_xemu_environment": {},
                    "candidate_xemu_environment": {},
                    "experiment_manifest": {},
                    "baseline_effective_experiment": {"features": {}},
                    "candidate_effective_experiment": {"features": {}},
                    "baseline_xemu": "baseline.exe",
                    "candidate_xemu": "candidate.exe",
                },
                "results": {"tests": {"Timing": timing}},
                "run_order": [],
                "claim_eligibility": {},
            }
            markdown = namespace["render_markdown"](payload)
            self.assertIn("Improvement % (+ good / - bad)", markdown)
            self.assertIn("+10.00%", markdown)
            self.assertIn("100.000", markdown)
            self.assertIn("90.000", markdown)
            self.assertNotIn("Median C/B", markdown)
            self.assertIn('"comparison_semantics": {', pair.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
