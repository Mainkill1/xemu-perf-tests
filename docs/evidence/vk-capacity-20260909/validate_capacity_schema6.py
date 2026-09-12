#!/usr/bin/env python3
"""Validate and summarize exact schema-6 Vulkan capacity telemetry."""
import argparse
import hashlib
import json
from pathlib import Path

SOURCE = "3db2bbfecd5153bb6841599d66bb24de731e12b7"
TREE = "e76e9879fedb81973b0eb0b93b99b9d8331669c7"
BINARY = "a18ae99f2e1274cefff5c1e73d9068e606445b0a171e3c498ad4d7a8d26f99b6"
CAPACITY = 8192
FINISH_REASONS = ['vertex_buffer_dirty', 'surface_create', 'surface_down', 'need_buffer_space', 'framebuffer_dirty', 'presenting', 'flip_stall', 'flush', 'stalled', 'texture_dirty']
SINGLE_TIME_CALLERS = ['pvideo_upload', 'display_render', 'surface_download', 'surface_create', 'surface_upload', 'texture_upload', 'dummy_texture_create']
CATEGORIES = {
    "descriptor_only": "need_descriptor_write_reset && !need_ubo_staging_buffer_reset",
    "ubo_staging_only": "!need_descriptor_write_reset && need_ubo_staging_buffer_reset",
    "both": "need_descriptor_write_reset && need_ubo_staging_buffer_reset",
}


class ValidationError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def nonnegative_integer(value, name):
    require(type(value) is int and value >= 0, f"{name} must be a nonnegative integer")
    return value


def load_records(path):
    raw = Path(path).read_bytes()
    require(raw.endswith(b"\n"), "input must end with a complete newline")
    try:
        records = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError(f"invalid JSONL: {error}") from error
    require(records, "input is empty")
    return raw, records


def validate(records):
    require(records[0].get("type") == "schema", "first record must be schema")
    schema = records[0]
    require(schema.get("schema_version") == 6, "schema5 or another schema is rejected")
    require(schema.get("duration_sampling", {}).get("mode") == "all", "full timing mode is required")
    deferred = schema.get("deferred_capture")
    require(isinstance(deferred, dict), "deferred capture metadata is required")
    capacity = nonnegative_integer(deferred.get("capacity"), "deferred capacity")
    require(capacity == CAPACITY, "wrong capacity for pinned source")
    require(deferred.get("allocation_failed") is False, "explicit allocation success is required")
    require(schema.get("need_buffer_space_capacity_triggers") ==
            {"schema_version": 1, **CATEGORIES}, "altered capacity mapping")
    names = schema.get("finish_reasons")
    require(names == FINISH_REASONS, "altered finish-reason mapping")
    require(schema.get("single_time_callers") == SINGLE_TIME_CALLERS,
            "altered single-time caller mapping")
    need_index = names.index("need_buffer_space")
    frames = records[1:-1]
    terminal = records[-1]
    require(terminal.get("type") == "deferred_capture" and terminal.get("schema_version") == 6,
            "last record must be one schema6 terminal")
    require(all(record.get("type") == "frame" and record.get("schema_version") == 6
                for record in frames), "only contiguous schema6 frames may precede terminal")
    require(len([r for r in records if r.get("type") == "schema"]) == 1, "exactly one schema")
    require(len([r for r in records if r.get("type") == "deferred_capture"]) == 1,
            "exactly one terminal")
    for field in ("capacity", "stored_frames", "dropped_frames"):
        nonnegative_integer(terminal.get(field), f"terminal {field}")
    require(terminal.get("capacity") == capacity and terminal.get("stored_frames") == len(frames),
            "terminal capacity or stored frame count mismatch")
    require(terminal.get("dropped_frames") == 0 and terminal.get("overflow") is False and
            terminal.get("incomplete") is False, "terminal reports dropped, overflow, or incomplete data")
    require(terminal.get("stored_frames") <= capacity, "stored frames exceed capacity")
    require(len(frames) >= 2 and frames[0].get("guest_frame") == 1,
            "at least two frames starting at guest frame 1 are required")
    previous_frame = previous_time = None
    for frame in frames:
        guest_frame = nonnegative_integer(frame.get("guest_frame"), "guest_frame")
        timestamp = nonnegative_integer(frame.get("timestamp_us"), "timestamp_us")
        if previous_frame is not None:
            require(guest_frame == previous_frame + 1 and timestamp > previous_time,
                    "frames must be contiguous and timestamp-monotonic")
        previous_frame, previous_time = guest_frame, timestamp
        arrays = []
        for key in ("finish_count_per_guest_frame", "finish_submit_count_per_guest_frame",
                    "finish_timed_submit_count_per_guest_frame", "fence_wait_count_per_guest_frame",
                    "finish_sampled_wait_us_per_guest_frame"):
            values = frame.get(key)
            require(isinstance(values, list) and len(values) == len(names), f"invalid {key}")
            arrays.append(values)
        for index, name in enumerate(names):
            actual, submitted, timed, waits, wait_us = (values[index] for values in arrays)
            for label, value in (("actual", actual), ("submitted", submitted),
                                 ("timed", timed), ("waits", waits), ("wait_us", wait_us)):
                nonnegative_integer(value, f"{name} {label}")
            require(actual >= submitted and submitted == timed == waits,
                    f"{name} calls/submits/timed/wait mismatch")
        actual = arrays[0][need_index]
        categories = frame.get("need_buffer_space_capacity_triggers_per_guest_frame")
        require(isinstance(categories, dict) and set(categories) == set(CATEGORIES),
                "missing capacity category fields")
        category_sum = sum(nonnegative_integer(categories[name], name) for name in CATEGORIES)
        require(category_sum <= actual, "category sum exceeds all-producer need_buffer_space count")
        single_names = schema.get("single_time_callers")
        require(isinstance(single_names, list), "single-time names are required")
        single_arrays = [frame.get(key) for key in (
            "single_time_submit_count_per_guest_frame",
            "single_time_timed_submit_count_per_guest_frame",
            "queue_wait_idle_count_per_guest_frame",
            "single_time_sampled_wait_us_per_guest_frame")]
        require(all(isinstance(values, list) and len(values) == len(single_names)
                    for values in single_arrays), "invalid single-time arrays")
        for index, name in enumerate(single_names):
            submitted, timed, waits, wait_us = (values[index] for values in single_arrays)
            for label, value in (("submitted", submitted), ("timed", timed),
                                 ("waits", waits), ("wait_us", wait_us)):
                nonnegative_integer(value, f"{name} {label}")
            require(submitted == timed == waits, f"{name} single-time mismatch")
    return frames, need_index


def summarize(raw, records, frames, need_index, source, tree, binary):
    selected = frames[1:]
    def count(frame):
        return frame["finish_count_per_guest_frame"][need_index]
    def wait(frame):
        return frame["finish_sampled_wait_us_per_guest_frame"][need_index]
    categories = {name: sum(frame["need_buffer_space_capacity_triggers_per_guest_frame"][name]
                             for frame in selected) for name in CATEGORIES}
    all_producer = sum(count(frame) for frame in selected)
    if selected:
        span = selected[-1]["timestamp_us"] - frames[0]["timestamp_us"]
    else:
        span = 0
    return {
        "summary_schema_version": 1,
        "analysis": "schema6 capacity counters over observed QPC intervals",
        "raw_input_sha256": hashlib.sha256(raw).hexdigest(),
        "source": source, "tree": tree, "binary": binary,
        "selected_records": len(selected),
        "excluded_first_unknown_prefix_record": bool(frames),
        "observed_qpc_span_us": span,
        "capacity_category_counts": categories,
        "all_producer_need_buffer_space_calls": all_producer,
        "all_producer_need_buffer_space_wait_us": sum(wait(frame) for frame in selected),
        "finish_wait_count": sum(sum(frame["fence_wait_count_per_guest_frame"]) for frame in selected),
        "finish_wait_us": sum(sum(frame["finish_sampled_wait_us_per_guest_frame"]) for frame in selected),
        "single_time_wait_count": sum(sum(frame["queue_wait_idle_count_per_guest_frame"]) for frame in selected),
        "single_time_wait_us": sum(sum(frame["single_time_sampled_wait_us_per_guest_frame"]) for frame in selected),
        "unresolved_unrelated_producers_difference": all_producer - sum(categories.values()),
        "limitations": [
            "Category counts are not removable-wait estimates.",
            "No category-specific wait duration is recorded; wait time is not subtracted.",
            "The first counter block has an unknown prefix and is excluded from interval sums.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--tree", required=True)
    parser.add_argument("--binary", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    require(args.source == SOURCE and args.tree == TREE and args.binary == BINARY,
            "source, tree, or binary identity mismatch")
    raw, records = load_records(args.input)
    frames, need_index = validate(records)
    Path(args.output).write_text(json.dumps(
        summarize(raw, records, frames, need_index, args.source, args.tree, args.binary), indent=2) + "\n")


if __name__ == "__main__":
    try:
        main()
    except ValidationError as error:
        raise SystemExit(f"validation failed: {error}")
