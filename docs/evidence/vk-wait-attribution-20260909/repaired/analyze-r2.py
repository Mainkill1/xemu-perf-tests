#!/usr/bin/env python3
"""Summarize a complete deferred Vulkan log over its own bounded QPC span."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
from typing import Any, Iterable


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def nearest_rank(values: Iterable[int], fraction: float) -> int:
    ordered = sorted(values)
    require(bool(ordered), "percentile requires at least one value")
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]


def distribution(values: list[int]) -> dict[str, Any]:
    require(bool(values), "distribution requires at least one value")
    total = sum(values)
    return {
        "count": len(values),
        "sum": total,
        "mean": total / len(values),
        "min": min(values),
        "p50_nearest_rank": nearest_rank(values, 0.50),
        "p95_nearest_rank": nearest_rank(values, 0.95),
        "p99_nearest_rank": nearest_rank(values, 0.99),
        "max": max(values),
    }


def sum_array(frames: list[dict[str, Any]], key: str, length: int) -> list[int]:
    for frame in frames:
        require(len(frame[key]) == length, f"wrong array length for {key}")
    return [sum(int(frame[key][i]) for frame in frames) for i in range(length)]


def named_rows(names: list[str], columns: dict[str, list[int]]) -> list[dict[str, Any]]:
    require(all(len(values) == len(names) for values in columns.values()),
            "named column length mismatch")
    return [
        {"name": name, **{key: values[i] for key, values in columns.items()}}
        for i, name in enumerate(names)
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    raw = args.input.read_bytes()
    require(bool(raw), "input is empty")
    require(raw.endswith(b"\n"), "input lacks final newline")
    records = [json.loads(line) for line in raw.splitlines() if line.strip()]
    schemas = [record for record in records if record.get("type") == "schema"]
    frames = [record for record in records if record.get("type") == "frame"]
    terminals = [record for record in records
                 if record.get("type") == "deferred_capture"]
    require(len(schemas) == 1, "expected exactly one schema")
    require(len(terminals) == 1, "expected exactly one terminal")
    require(len(frames) > 1, "need at least two frame records")
    require(len(records) == 1 + len(frames) + 1,
            "unexpected record type")
    schema = schemas[0]
    terminal = terminals[0]
    require(schema["schema_version"] == 5, "wrong schema version")
    require(schema["duration_sampling"]["mode"] == "all",
            "finish durations are not full-timing")
    require(not schema["deferred_capture"]["allocation_failed"],
            "deferred allocation failed")
    require(terminal["capacity"] == schema["deferred_capture"]["capacity"],
            "terminal/schema capacity mismatch")
    require(terminal["stored_frames"] == len(frames),
            "stored-frame count mismatch")
    require(terminal["dropped_frames"] == 0, "frames were dropped")
    require(not terminal["overflow"], "capture overflowed")
    require(not terminal["incomplete"], "capture is incomplete")
    require(frames[0]["guest_frame"] == 1, "first guest frame is not 1")

    for index, frame in enumerate(frames):
        require(frame["finish_submit_count_per_guest_frame"] ==
                frame["finish_timed_submit_count_per_guest_frame"],
                f"finish submit/timed mismatch at record {index + 1}")
        require(frame["finish_submit_count_per_guest_frame"] ==
                frame["fence_wait_count_per_guest_frame"],
                f"finish submit/wait mismatch at record {index + 1}")
        require(frame["single_time_submit_count_per_guest_frame"] ==
                frame["single_time_timed_submit_count_per_guest_frame"],
                f"single-time submit/timed mismatch at record {index + 1}")
        require(frame["single_time_submit_count_per_guest_frame"] ==
                frame["queue_wait_idle_count_per_guest_frame"],
                f"single-time submit/wait mismatch at record {index + 1}")
    for previous, current in zip(frames, frames[1:]):
        require(current["guest_frame"] == previous["guest_frame"] + 1,
                "guest frames are not contiguous")
        require(current["timestamp_us"] > previous["timestamp_us"],
                "timestamps are not strictly increasing")

    # A frame record snapshots counters accumulated since the preceding reset,
    # then reset_perf_frame clears them. Record 1 starts at telemetry init and
    # has an unknown prefix. Records 2..N align with the N-1 timestamp intervals.
    selected = frames[1:]
    finish_names = list(schema["finish_reasons"])
    single_names = list(schema["single_time_callers"])
    cpu_names = list(schema["cpu_regions"])

    finish_columns = {
        "finish_calls": sum_array(selected, "finish_count_per_guest_frame",
                                  len(finish_names)),
        "vk_queue_submit_calls": sum_array(
            selected, "finish_submit_count_per_guest_frame", len(finish_names)),
        "timed_submit_calls": sum_array(
            selected, "finish_timed_submit_count_per_guest_frame",
            len(finish_names)),
        "submit_cpu_us": sum_array(
            selected, "finish_sampled_submit_cpu_us_per_guest_frame",
            len(finish_names)),
        "vk_wait_for_fences_calls": sum_array(
            selected, "fence_wait_count_per_guest_frame", len(finish_names)),
        "vk_wait_for_fences_us": sum_array(
            selected, "finish_sampled_wait_us_per_guest_frame",
            len(finish_names)),
    }
    single_columns = {
        "vk_queue_submit_calls": sum_array(
            selected, "single_time_submit_count_per_guest_frame",
            len(single_names)),
        "timed_submit_calls": sum_array(
            selected, "single_time_timed_submit_count_per_guest_frame",
            len(single_names)),
        "submit_cpu_us": sum_array(
            selected, "single_time_sampled_submit_cpu_us_per_guest_frame",
            len(single_names)),
        "vk_queue_wait_idle_calls": sum_array(
            selected, "queue_wait_idle_count_per_guest_frame", len(single_names)),
        "vk_queue_wait_idle_us": sum_array(
            selected, "single_time_sampled_wait_us_per_guest_frame",
            len(single_names)),
    }
    require(finish_columns["vk_queue_submit_calls"] ==
            finish_columns["timed_submit_calls"],
            "finish submit/timed counts differ")
    require(finish_columns["vk_queue_submit_calls"] ==
            finish_columns["vk_wait_for_fences_calls"],
            "finish submit/wait counts differ")
    require(single_columns["vk_queue_submit_calls"] ==
            single_columns["timed_submit_calls"],
            "single-time submit/timed counts differ")
    require(single_columns["vk_queue_submit_calls"] ==
            single_columns["vk_queue_wait_idle_calls"],
            "single-time submit/wait counts differ")

    finish_rows = named_rows(finish_names, finish_columns)
    single_rows = named_rows(single_names, single_columns)
    finish_wait_total = sum(finish_columns["vk_wait_for_fences_us"])
    single_wait_total = sum(single_columns["vk_queue_wait_idle_us"])
    queue_submit_total = sum(finish_columns["vk_queue_submit_calls"]) + sum(
        single_columns["vk_queue_submit_calls"])

    api = {
        "vk_queue_submit_calls": sum(
            int(frame["vk_queue_submit_calls_per_guest_frame"])
            for frame in selected),
        "vk_queue_submit_cpu_us": (
            sum(finish_columns["submit_cpu_us"]) +
            sum(single_columns["submit_cpu_us"])
        ),
        "vk_submit_infos": sum(
            int(frame["vk_submit_infos_per_guest_frame"]) for frame in selected),
        "command_buffers": sum(
            int(frame["command_buffers_per_guest_frame"]) for frame in selected),
        "vk_wait_for_fences_calls": sum(
            finish_columns["vk_wait_for_fences_calls"]),
        "vk_wait_for_fences_us": finish_wait_total,
        "vk_queue_wait_idle_calls": sum(
            single_columns["vk_queue_wait_idle_calls"]),
        "vk_queue_wait_idle_us": single_wait_total,
        "tracked_wait_us": finish_wait_total + single_wait_total,
    }
    require(api["vk_queue_submit_calls"] == queue_submit_total,
            "queue-submit total does not match per-reason total")

    cpu_calls = sum_array(selected, "cpu_region_calls_per_guest_frame",
                          len(cpu_names))
    cpu_us = sum_array(selected, "cpu_region_us_per_guest_frame", len(cpu_names))
    cpu_rows = []
    for i, name in enumerate(cpu_names):
        values = [int(frame["cpu_region_us_per_guest_frame"][i])
                  for frame in selected]
        cpu_rows.append({
            "name": name,
            "calls": cpu_calls[i],
            "cpu_us": cpu_us[i],
            "mean_us_per_call": cpu_us[i] / cpu_calls[i]
            if cpu_calls[i] else None,
            "per_frame_cpu_us": distribution(values),
        })

    intervals = [int(current["timestamp_us"]) - int(previous["timestamp_us"])
                 for previous, current in zip(frames, frames[1:])]
    tracked_wait_per_frame = [
        sum(map(int, frame["finish_sampled_wait_us_per_guest_frame"])) +
        sum(map(int, frame["single_time_sampled_wait_us_per_guest_frame"]))
        for frame in selected
    ]
    need_index = finish_names.index("need_buffer_space")
    descriptor_index = cpu_names.index("update_descriptor_sets")
    need_wait_per_frame = [
        int(frame["finish_sampled_wait_us_per_guest_frame"][need_index])
        for frame in selected
    ]
    need_submit_per_frame = [
        int(frame["finish_submit_count_per_guest_frame"][need_index])
        for frame in selected
    ]
    descriptor_region_per_frame = [
        int(frame["cpu_region_us_per_guest_frame"][descriptor_index])
        for frame in selected
    ]
    descriptor_minus_need_wait = [
        descriptor - wait
        for descriptor, wait in zip(descriptor_region_per_frame,
                                    need_wait_per_frame)
    ]
    need_mean = statistics.mean(need_wait_per_frame)
    descriptor_mean = statistics.mean(descriptor_region_per_frame)
    covariance = sum(
        (wait - need_mean) * (descriptor - descriptor_mean)
        for wait, descriptor in zip(need_wait_per_frame,
                                    descriptor_region_per_frame)
    )
    correlation_denominator = math.sqrt(
        sum((wait - need_mean) ** 2 for wait in need_wait_per_frame) *
        sum((descriptor - descriptor_mean) ** 2
            for descriptor in descriptor_region_per_frame)
    )
    need_submit_frequency = {
        str(value): need_submit_per_frame.count(value)
        for value in sorted(set(need_submit_per_frame))
    }

    copies = {
        key.removesuffix("_per_guest_frame"): sum(
            int(frame[key]) for frame in selected)
        for key in (
            "staged_bytes_per_guest_frame",
            "vertex_staged_bytes_per_guest_frame",
            "vertex_staging_copies_per_guest_frame",
            "vertex_staging_capacity_growths_per_guest_frame",
            "vertex_staging_fallback_finishes_per_guest_frame",
            "native_bc_uploads_per_guest_frame",
            "native_bc_source_bytes_per_guest_frame",
            "native_bc_staged_bytes_per_guest_frame",
            "native_bc_prepare_cpu_us_per_guest_frame",
            "decoded_bc_uploads_per_guest_frame",
            "decoded_bc_source_bytes_per_guest_frame",
            "decoded_bc_staged_bytes_per_guest_frame",
            "decoded_bc_prepare_cpu_us_per_guest_frame",
        )
    }
    copies["mean_vertex_staged_bytes_per_copy"] = (
        copies["vertex_staged_bytes"] / copies["vertex_staging_copies"]
        if copies["vertex_staging_copies"] else None
    )

    summary = {
        "schema_version": 1,
        "analysis": "bounded deferred Vulkan telemetry over its own QPC span",
        "input_basename": args.input.name,
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "source_commit": "f16292b472e6bf5aa9d4448cbbf352bc13131b06",
        "source_tree": "f5cac543ac34e50f4b48f6f4b9799dfbd3bd5e8f",
        "validation": {
            "final_newline": True,
            "schema_records": len(schemas),
            "frame_records": len(frames),
            "terminal_records": len(terminals),
            "full_timing": True,
            "dropped_frames": terminal["dropped_frames"],
            "overflow": terminal["overflow"],
            "incomplete": terminal["incomplete"],
            "strict_contiguous_frames_and_monotonic_timestamps": True,
        },
        "boundary": {
            "excluded_frame_record": frames[0]["guest_frame"],
            "excluded_reason": "unknown prefix from telemetry initialization to first frame capture",
            "included_frame_records_first": selected[0]["guest_frame"],
            "included_frame_records_last": selected[-1]["guest_frame"],
            "included_frame_records": len(selected),
            "qpc_start_timestamp_us": frames[0]["timestamp_us"],
            "qpc_end_timestamp_us": frames[-1]["timestamp_us"],
            "qpc_span_us": frames[-1]["timestamp_us"] - frames[0]["timestamp_us"],
            "aligned_intervals": len(intervals),
            "setup_inclusive": True,
            "utc_qpc_anchors_available": False,
            "runner_measurement_window_alignment": "unavailable",
        },
        "frame_interval_us": distribution(intervals),
        "tracked_wait_per_frame_us": distribution(tracked_wait_per_frame),
        "finish_reasons": finish_rows,
        "single_time_callers": single_rows,
        "api_totals": api,
        "copy_and_upload_totals": copies,
        "cpu_regions_nonexclusive": cpu_rows,
        "need_buffer_localization": {
            "status": "strongly localized to the update_descriptor_sets region; exact descriptor-set versus UBO-capacity trigger remains unresolved",
            "records": len(selected),
            "need_buffer_submit_count_frequency": need_submit_frequency,
            "need_buffer_wait_us": sum(need_wait_per_frame),
            "update_descriptor_sets_region_us": sum(
                descriptor_region_per_frame),
            "need_wait_fraction_of_descriptor_region": (
                sum(need_wait_per_frame) /
                sum(descriptor_region_per_frame)
            ),
            "all_descriptor_region_us_ge_need_wait_us_per_record": all(
                residual >= 0 for residual in descriptor_minus_need_wait),
            "descriptor_region_minus_need_wait_us": distribution(
                descriptor_minus_need_wait),
            "pearson_correlation_per_record": (
                covariance / correlation_denominator
                if correlation_denominator else None
            ),
        },
        "limitations": [
            "The interval is setup-inclusive and is not the runner's 20-second window.",
            "Missing UTC/QPC anchors prohibit alignment with the runner or ETL.",
            "No OpenGL or baseline comparison is made.",
            "CPU regions are individually measured and nested; their durations must not be summed as exclusive CPU time.",
            "Counts and durations are observed totals only; no extrapolation is performed.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp = args.output.with_suffix(args.output.suffix + ".tmp")
    temp.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    temp.replace(args.output)


if __name__ == "__main__":
    main()
