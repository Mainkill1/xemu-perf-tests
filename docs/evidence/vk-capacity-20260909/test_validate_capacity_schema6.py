#!/usr/bin/env python3
import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent
TOOL = ROOT / "validate_capacity_schema6.py"
SOURCE = "3db2bbfecd5153bb6841599d66bb24de731e12b7"
TREE = "e76e9879fedb81973b0eb0b93b99b9d8331669c7"
BINARY = "a18ae99f2e1274cefff5c1e73d9068e606445b0a171e3c498ad4d7a8d26f99b6"
MAP = {
    "schema_version": 1,
    "descriptor_only": "need_descriptor_write_reset && !need_ubo_staging_buffer_reset",
    "ubo_staging_only": "!need_descriptor_write_reset && need_ubo_staging_buffer_reset",
    "both": "need_descriptor_write_reset && need_ubo_staging_buffer_reset",
}


def frame(number, timestamp, categories):
    actual = sum(categories.values()) + 2
    return {
        "type": "frame", "schema_version": 6, "guest_frame": number,
        "timestamp_us": timestamp,
        "finish_count_per_guest_frame": [1, 1, 1, actual] + [0] * 6,
        "finish_submit_count_per_guest_frame": [0, 0, 0, actual] + [0] * 6,
        "finish_timed_submit_count_per_guest_frame": [0, 0, 0, actual] + [0] * 6,
        "fence_wait_count_per_guest_frame": [0, 0, 0, actual] + [0] * 6,
        "finish_sampled_wait_us_per_guest_frame": [0, 0, 0, actual * 10] + [0] * 6,
        "single_time_submit_count_per_guest_frame": [1] + [0] * 6,
        "single_time_timed_submit_count_per_guest_frame": [1] + [0] * 6,
        "queue_wait_idle_count_per_guest_frame": [1] + [0] * 6,
        "single_time_sampled_wait_us_per_guest_frame": [2] + [0] * 6,
        "need_buffer_space_capacity_triggers_per_guest_frame": categories,
    }


def records():
    schema = {
        "type": "schema", "schema_version": 6,
        "duration_sampling": {"mode": "all"},
        "deferred_capture": {"capacity": 8192, "allocation_failed": False},
        "finish_reasons": ['vertex_buffer_dirty', 'surface_create', 'surface_down', 'need_buffer_space', 'framebuffer_dirty', 'presenting', 'flip_stall', 'flush', 'stalled', 'texture_dirty'],
        "single_time_callers": ['pvideo_upload', 'display_render', 'surface_download', 'surface_create', 'surface_upload', 'texture_upload', 'dummy_texture_create'],
        "need_buffer_space_capacity_triggers": MAP,
    }
    categories = {"descriptor_only": 2, "ubo_staging_only": 1, "both": 1}
    return [schema, frame(1, 100, categories), frame(2, 130, categories),
            {"type": "deferred_capture", "schema_version": 6, "capacity": 8192,
             "stored_frames": 2, "dropped_frames": 0, "overflow": False, "incomplete": False}]


def run(data, newline=True):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        input_path, output_path = root / "input.jsonl", root / "summary.json"
        input_path.write_text("\n".join(json.dumps(record) for record in data) + ("\n" if newline else ""))
        result = subprocess.run([sys.executable, str(TOOL), "--input", str(input_path),
                                 "--source", SOURCE, "--tree", TREE, "--binary", BINARY,
                                 "--output", str(output_path)], text=True, capture_output=True)
        return result, json.loads(output_path.read_text()) if output_path.exists() else None


def reject(mutator, label):
    data = records()
    mutator(data)
    result, _ = run(data)
    assert result.returncode != 0, label


def main():
    result, summary = run(records())
    assert result.returncode == 0, result.stderr
    assert summary["selected_records"] == 1
    assert summary["observed_qpc_span_us"] == 30
    assert summary["unresolved_unrelated_producers_difference"] == 2
    assert (summary["finish_wait_count"], summary["finish_wait_us"]) == (6, 60)
    assert (summary["single_time_wait_count"], summary["single_time_wait_us"]) == (1, 2)
    reject(lambda data: data.__setitem__(0, {**data[0], "schema_version": 5}), "schema5")
    reject(lambda data: data[0].__setitem__("need_buffer_space_capacity_triggers", {}), "mapping")
    reject(lambda data: data[2].__setitem__("guest_frame", 4), "nonmonotonic frame")
    reject(lambda data: data[1]["finish_timed_submit_count_per_guest_frame"].__setitem__(3, 0), "sampled counts")
    reject(lambda data: data[1]["finish_timed_submit_count_per_guest_frame"].__setitem__(0, 1), "sampled non-need count")
    reject(lambda data: data[1]["single_time_timed_submit_count_per_guest_frame"].__setitem__(0, 0), "single-time sampled count")
    reject(lambda data: data[1]["need_buffer_space_capacity_triggers_per_guest_frame"].__setitem__("both", -1), "negative category")
    reject(lambda data: data[1]["need_buffer_space_capacity_triggers_per_guest_frame"].__setitem__("both", 1.5), "fraction category")
    reject(lambda data: data[1]["need_buffer_space_capacity_triggers_per_guest_frame"].__setitem__("both", True), "bool category")
    reject(lambda data: data[1]["need_buffer_space_capacity_triggers_per_guest_frame"].__setitem__("both", 99), "category sum")
    reject(lambda data: (data[0]["deferred_capture"].__setitem__("capacity", 8), data[-1].__setitem__("capacity", 8)), "wrong fixed capacity")
    reject(lambda data: data[0]["deferred_capture"].pop("allocation_failed"), "missing allocation result")
    reject(lambda data: data[0]["deferred_capture"].__setitem__("allocation_failed", 0), "nonboolean allocation result")
    reject(lambda data: data[-1].__setitem__("dropped_frames", False), "boolean dropped count")
    reject(lambda data: data[-1].__setitem__("stored_frames", 2.0), "fractional stored count")
    reject(lambda data: data[-1].__setitem__("capacity", 8192.0), "fractional capacity")
    reject(lambda data: data[0]["finish_reasons"].__setitem__(0, "unknown"), "altered finish mapping")
    reject(lambda data: data[0]["single_time_callers"].__setitem__(0, "unknown"), "altered caller mapping")
    reject(lambda data: data.pop(), "missing terminal")
    result, _ = run(records(), newline=False)
    assert result.returncode != 0, "truncated terminal newline"
    print("capacity schema6 synthetic controls passed")


if __name__ == "__main__":
    main()
