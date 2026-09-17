"""Recompute this dataset's frame metrics and paired comparisons, without xemu."""

import csv
import gzip
import hashlib
import importlib.util
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


root = Path(__file__).resolve().parent
runs = json.loads((root / "runs.json").read_text())
manifest = json.loads((root / "manifest.json").read_text())
assert [row["run_id"] for row in runs] == [row["run_id"] for row in manifest["cases"]]
assert len(runs) == 24 and sum(row["phase"] == "measured" for row in runs) == 20
frames = defaultdict(list)
with gzip.open(root / "frame-intervals.csv.gz", "rt", newline="") as stream:
    for row in csv.DictReader(stream):
        frames[row["run_id"]].append(tuple(int(row[key]) for key in
                                        ("end_us_since_measurement_start", "frame", "delta_us")))
assert set(frames) == {row["run_id"] for row in runs}
for run in runs:
    samples = frames[run["run_id"]]
    assert len(samples) == run["frame_interval_count"]
    previous_end = previous_frame = -1
    for end, frame, interval in samples:
        assert interval > 0 and end > previous_end and frame > previous_frame
        assert end - interval >= 0 and end <= run["measured_window_us"]
        previous_end, previous_frame = end, frame
    values = sorted(sample[2] / 1000 for sample in samples)
    expected = {
        "mean_ms": statistics.fmean(values),
        "p95_ms": values[math.ceil(len(values) * .95) - 1],
        "p99_ms": values[math.ceil(len(values) * .99) - 1],
        "maximum_ms": max(values),
        "cadence_hz": 1e6 * run["cadence_flip_count"] / run["cadence_elapsed_us"],
    }
    for key, value in expected.items():
        assert math.isclose(value, run["metrics"][key], rel_tol=1e-11), (run["run_id"], key)
    assert sum(sample[2] for sample in samples) == run["frame_interval_sum_us"]
    assert run["status"] == "VALID" and run["cleanup_verified"]
    assert run["source_commit"] == manifest["builds"][run["build"]]["source"]
    assert run["exe_sha256"] == manifest["builds"][run["build"]]["sha256"]
    assert run["seed_sha256"] == manifest["seed_sha256"]
    assert run["start_scene_review"]["status"] == "PASS_START_SCENE"
    assert all(run["gates"][key] == 0 for key in
               ("focus_loss_samples", "etw_lost_events", "etw_lost_buffers"))

spec = importlib.util.spec_from_file_location(
    "summarize_snapshot_pairs", root.parents[2] / "utils/summarize_snapshot_pairs.py")
calculator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calculator)
assert calculator.compare_pairs(runs, 5, ["OPENGL", "VULKAN"]) == json.loads(
    (root / "paired-results.json").read_text())
unit = json.loads((root / "timebase-unit-results.json").read_text())
assert unit["status"] == "WINE_AND_NATIVE_PASS" and len(unit["tests"]) == 70
assert unit["native"]["exit_code"] == 0 and unit["native"]["cleanup_complete"]
assert unit["native"]["exe_sha256"] == unit["sha256"]["test-xbox-nv2a-ptimer.exe"]
for case in unit["tests"]:
    assert case["wine"] == case["native_windows"] == "PASS"
checksums = root / "SHA256SUMS"
if checksums.exists():
    for line in checksums.read_text().splitlines():
        expected, name = line.split("  ", 1)
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name
print(json.dumps({"runs_checked": len(runs), "measured_runs": 20, "pairs": 10,
                  "frame_intervals_recalculated": sum(map(len, frames.values())),
                  "native_and_wine_cases": 70, "qualification": "HOLD"}))
