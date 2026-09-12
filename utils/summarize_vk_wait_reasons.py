#!/usr/bin/env python3
"""Attribute Vulkan finish waits to reasons in a matched guest-flip window."""

import argparse
import hashlib
import json
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def percentile(values, fraction):
    values = sorted(values)
    if not values:
        return None
    rank = (len(values) - 1) * fraction
    lower = int(rank)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (rank - lower)


def summarize(perf_path, flips_path, result_path):
    perf_bytes = perf_path.read_bytes()
    flips_bytes = flips_path.read_bytes()
    records = [json.loads(line) for line in perf_bytes.splitlines()]
    schemas = [record for record in records if record.get("type") == "schema"]
    if len(schemas) != 1:
        raise ValueError("expected exactly one Vulkan counter schema")
    schema = schemas[0]
    frames = [record for record in records if record.get("type") == "frame"]
    flip_lines = flips_bytes.decode("utf-8").splitlines()
    if any(" nv2a_pgraph_flip_increment_write " not in line for line in flip_lines):
        raise ValueError("flip input contains other event types")
    times = [datetime.fromisoformat(line.split()[0].replace("Z", "+00:00"))
             for line in flip_lines]
    if len(frames) != len(times):
        raise ValueError(f"frame/flip count mismatch: {len(frames)} vs {len(times)}")
    if any(next_time <= time for time, next_time in zip(times, times[1:])):
        raise ValueError("flip timestamps are not strictly increasing")

    result = json.loads(result_path.read_text())
    if result.get("status") != "complete" or not result.get("private_hdd_deleted"):
        raise ValueError("workload or private-HDD cleanup was incomplete")
    start = datetime.fromisoformat(result["measurement_started_utc"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(result["measurement_ended_utc"].replace("Z", "+00:00"))
    if start.tzinfo is None or end.tzinfo is None or end <= start:
        raise ValueError("invalid measurement window")
    selected = [frames[index] for index, time in enumerate(times)
                if start <= time < end]
    if len(selected) != result["display_write_events"]:
        raise ValueError("counter window does not match runner event count")

    reasons = {}
    for index, name in enumerate(schema["finish_reasons"]):
        waits = [row["finish_sampled_wait_us_per_guest_frame"][index]
                 for row in selected]
        submits = [row["finish_submit_count_per_guest_frame"][index]
                   for row in selected]
        reasons[name] = {
            "submits": sum(submits),
            "frames_with_submit": sum(count > 0 for count in submits),
            "median_wait_us_per_frame": statistics.median(waits),
            "p95_wait_us_per_frame": percentile(waits, .95),
            "sum_sampled_wait_us": sum(waits),
        }
        gpu_fields = {
            "gpu_batch_ns": "finish_gpu_batch_ns_per_guest_frame",
            "gpu_aux_ns": "finish_gpu_aux_ns_per_guest_frame",
            "gpu_handoff_ns": "finish_gpu_handoff_ns_per_guest_frame",
            "gpu_main_ns": "finish_gpu_main_ns_per_guest_frame",
        }
        if all("finish_gpu_timed_submit_count_per_guest_frame" in row
               for row in selected):
            gpu_counts = [row["finish_gpu_timed_submit_count_per_guest_frame"][index]
                          for row in selected]
            reasons[name]["gpu_timed_submits"] = sum(gpu_counts)
            for label, key in gpu_fields.items():
                if not all(key in row for row in selected):
                    continue
                values = [row[key][index] for row in selected]
                timed_values = [value for value, count in zip(values, gpu_counts)
                                if count > 0]
                reasons[name][f"sum_{label}"] = sum(values)
                reasons[name][f"median_{label}_per_timed_frame"] = (
                    statistics.median(timed_values) if timed_values else None)
                reasons[name][f"p95_{label}_per_timed_frame"] = (
                    percentile(timed_values, .95) if timed_values else None)

    cpu_regions = {}
    for index, name in enumerate(schema["cpu_regions"]):
        values = [row["cpu_region_us_per_guest_frame"][index]
                  for row in selected]
        cpu_regions[name] = {
            "median_us_per_frame": statistics.median(values),
            "p95_us_per_frame": percentile(values, .95),
        }

    total_wait = [sum(row["finish_sampled_wait_us_per_guest_frame"])
                  for row in selected]
    summary = {
        "schema_version": 1,
        "source_commit": result["source_commit"],
        "executable_sha256": result["executable_sha256"],
        "renderer": result["renderer"],
        "snapshot": result["snapshot"],
        "full_run_frames": len(frames),
        "window_frames": len(selected),
        "perf_input_sha256": hashlib.sha256(perf_bytes).hexdigest(),
        "flips_input_sha256": hashlib.sha256(flips_bytes).hexdigest(),
        "median_total_sampled_finish_wait_us_per_frame": statistics.median(total_wait),
        "p95_total_sampled_finish_wait_us_per_frame": percentile(total_wait, .95),
        "queue_submits_median_per_frame": statistics.median(
            row["vk_queue_submit_calls_per_guest_frame"] for row in selected),
        "reasons": reasons,
        "cpu_regions": cpu_regions,
    }
    command_fields = (
        "draw_begin_count", "draw_clear_count", "draw_command_count",
        "pipeline_bind_count", "descriptor_bind_count",
        "descriptor_same_recorded_bind_count", "descriptor_write_count",
    )
    if all(all(key in frame for key in command_fields) for frame in selected):
        summary["command_recording"] = {
            key: {
                "total": sum(frame[key] for frame in selected),
                "median_per_guest_frame": statistics.median(
                    frame[key] for frame in selected),
            }
            for key in command_fields
        }
    cause_fields = (
        "descriptor_reason_texture_count", "descriptor_reason_first_count",
        "descriptor_reason_vsh_count", "descriptor_reason_psh_count",
        "descriptor_reason_ubo_reset_count", "texture_slow_bind_count",
        "texture_slow_bind_same_images_count",
    )
    if all(all(key in frame for key in cause_fields) for frame in selected):
        summary["descriptor_write_causes"] = {
            key: {
                "total": sum(frame[key] for frame in selected),
                "median_per_guest_frame": statistics.median(
                    frame[key] for frame in selected),
            }
            for key in cause_fields
        }
    pipeline_fields = (
        "pipeline_dirty_count", "pipeline_dirty_same_key_count",
        "pipeline_uniform_only_key_count",
        "pipeline_uniform_only_alpha_count",
        "pipeline_uniform_only_zoffset_count", "pipeline_create_count",
    )
    if all(all(key in frame for key in pipeline_fields) for frame in selected):
        summary["pipeline_key_churn"] = {
            key: {
                "total": sum(frame[key] for frame in selected),
                "median_per_guest_frame": statistics.median(
                    frame[key] for frame in selected),
            }
            for key in pipeline_fields
        }
    if schema.get("draw_queries", {}).get("supported"):
        stat_names = schema["draw_stats"]
        by_shader = defaultdict(lambda: defaultdict(int))
        draw_counts = []
        for frame in selected:
            if frame["draw_query_overflows"] or frame["draw_shader_overflows"]:
                raise ValueError("draw-query profiling capacity was exceeded")
            draw_counts.append(sum(shader["draw_count"] for shader in
                                   frame["fragment_shader_stats"]))
            for shader in frame["fragment_shader_stats"]:
                aggregate = by_shader[shader["spirv_hash"]]
                for key in ("draw_count", "gpu_time_ns", *stat_names):
                    aggregate[key] += shader[key]
        shaders = [dict(spirv_hash=shader_hash, **counts)
                   for shader_hash, counts in by_shader.items()]
        shaders.sort(key=lambda row: row["draw_count"], reverse=True)
        total_draws = sum(draw_counts)
        total_draw_gpu_ns = sum(shader["gpu_time_ns"] for shader in shaders)
        for shader in shaders:
            shader["draw_share_percent"] = (
                100 * shader["draw_count"] / total_draws if total_draws else 0)
            shader["draw_gpu_time_share_percent"] = (
                100 * shader["gpu_time_ns"] / total_draw_gpu_ns
                if total_draw_gpu_ns else 0)
        summary["draw_queries"] = {
            "capacity_per_submission": schema["draw_queries"]["capacity"],
            "overflow_count": 0,
            "unique_fragment_spirv_hashes": len(shaders),
            "total_profiled_draw_groups": total_draws,
            "median_profiled_draw_groups_per_guest_frame":
                statistics.median(draw_counts),
            "sum_draw_gpu_time_ns": total_draw_gpu_ns,
            "pipeline_stat_totals": {
                name: sum(shader[name] for shader in shaders)
                for name in stat_names
            },
            "fragment_shaders": shaders,
        }
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--perf", type=Path, required=True)
    parser.add_argument("--flips", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(summarize(args.perf, args.flips, args.result), indent=2))


if __name__ == "__main__":
    main()
