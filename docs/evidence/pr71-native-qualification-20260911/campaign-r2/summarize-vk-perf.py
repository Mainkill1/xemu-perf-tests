#!/usr/bin/env python3
"""Aggregate xemu's per-guest-frame Vulkan wait telemetry."""

import argparse
import json
from pathlib import Path


def add_arrays(total: list[int], values: list[int], field: str) -> None:
    if len(total) != len(values):
        raise ValueError(f"{field} length changed within one telemetry stream")
    for index, value in enumerate(values):
        total[index] += int(value)


def ranked_owners(
    names: list[str], calls: list[int], submits: list[int],
    timed_submits: list[int], sampled_submit_us: list[int], waits: list[int],
    sampled_wait_us: list[int], frames: int, owner_type: str
) -> list[dict]:
    owners = []
    for index, name in enumerate(names):
        timed = timed_submits[index]
        scale = submits[index] / timed if timed else 0.0
        submit_us = sampled_submit_us[index] * scale
        wait_us = sampled_wait_us[index] * scale
        owners.append({
            "owner_type": owner_type,
            "owner": name,
            "calls": calls[index],
            "submits": submits[index],
            "timed_samples": timed,
            "sample_coverage": timed / submits[index] if submits[index] else 0.0,
            "duration_estimated": timed < submits[index],
            "sampled_submit_cpu_us": sampled_submit_us[index],
            "submit_cpu_us": submit_us,
            "waits": waits[index],
            "sampled_wait_us": sampled_wait_us[index],
            "wait_us": wait_us,
            "calls_per_guest_frame": calls[index] / frames,
            "submits_per_guest_frame": submits[index] / frames,
            "submit_cpu_us_per_guest_frame": submit_us / frames,
            "wait_us_per_guest_frame": wait_us / frames,
        })
    return sorted(owners, key=lambda owner: owner["wait_us"], reverse=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("telemetry", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    schema = None
    frames = []
    with args.telemetry.open(encoding="utf-8-sig") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise SystemExit(
                    f"invalid JSON on line {line_number}: {error}"
                ) from error
            if record.get("type") == "schema":
                schema = record
            elif record.get("type") == "frame":
                frames.append(record)

    if schema is None or schema.get("schema_version") not in (
        1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14
    ):
        raise SystemExit("missing or unsupported Vulkan telemetry schema")
    if not frames:
        raise SystemExit("no Vulkan guest-frame records")

    finish_names = schema["finish_reasons"]
    single_names = schema["single_time_callers"]
    version = schema["schema_version"]
    finish_fields = {
        "calls": "finish_count_per_guest_frame",
        "submits": "finish_submit_count_per_guest_frame",
        "timed": ("finish_timed_submit_count_per_guest_frame" if version >= 2
                  else "finish_submit_count_per_guest_frame"),
        "submit_us": ("finish_sampled_submit_cpu_us_per_guest_frame"
                      if version >= 2
                      else "finish_submit_cpu_us_per_guest_frame"),
        "waits": "fence_wait_count_per_guest_frame",
        "wait_us": ("finish_sampled_wait_us_per_guest_frame" if version >= 2
                    else "fence_wait_us_per_guest_frame"),
    }
    single_fields = {
        "calls": "single_time_submit_count_per_guest_frame",
        "submits": "single_time_submit_count_per_guest_frame",
        "timed": ("single_time_timed_submit_count_per_guest_frame"
                  if version >= 2
                  else "single_time_submit_count_per_guest_frame"),
        "submit_us": ("single_time_sampled_submit_cpu_us_per_guest_frame"
                      if version >= 2
                      else "single_time_submit_cpu_us_per_guest_frame"),
        "waits": "queue_wait_idle_count_per_guest_frame",
        "wait_us": ("single_time_sampled_wait_us_per_guest_frame"
                    if version >= 2
                    else "queue_wait_idle_us_per_guest_frame"),
    }
    finish = {key: [0] * len(finish_names) for key in finish_fields}
    single = {key: [0] * len(single_names) for key in single_fields}
    gpu_finish_fields = {
        "timed_submits": "finish_gpu_timed_submit_count_per_guest_frame",
        "batch_ns": "finish_gpu_batch_ns_per_guest_frame",
        "aux_ns": "finish_gpu_aux_ns_per_guest_frame",
        "handoff_ns": "finish_gpu_handoff_ns_per_guest_frame",
        "main_ns": "finish_gpu_main_ns_per_guest_frame",
    }
    gpu_finish = {
        key: [0] * len(finish_names) for key in gpu_finish_fields
    }
    pipeline_names = schema.get("pipeline_statistics_names", [])
    pipeline_fields = {
        name: f"finish_{name}_per_guest_frame" for name in pipeline_names
    }
    pipeline_finish = {
        name: [0] * len(finish_names) for name in pipeline_names
    }
    cpu_region_names = schema.get("cpu_regions", [])
    cpu_region_calls = [0] * len(cpu_region_names)
    cpu_region_us = [0] * len(cpu_region_names)
    scalar_fields = (
        "vk_queue_submit_calls_per_guest_frame",
        "vk_submit_infos_per_guest_frame",
        "command_buffers_per_guest_frame",
        "staged_bytes_per_guest_frame",
        "vertex_staged_bytes_per_guest_frame",
        "vertex_staging_copies_per_guest_frame",
        "vertex_staging_capacity_growths_per_guest_frame",
        "vertex_staging_fallback_finishes_per_guest_frame",
        "vertex_dirty_checks_per_guest_frame",
        "vertex_dirty_pages_checked_per_guest_frame",
        "vertex_dirty_hits_per_guest_frame",
        "vertex_dirty_hit_pages_per_guest_frame",
        "vertex_dirty_repeated_ranges_per_guest_frame",
        "vertex_dirty_repeated_range_hits_per_guest_frame",
        "shader_bind_calls_per_guest_frame",
        "shader_state_checks_per_guest_frame",
        "shader_state_dirty_per_guest_frame",
        "shader_binding_changes_per_guest_frame",
        "vsh_uniform_update_requests_per_guest_frame",
        "psh_uniform_update_requests_per_guest_frame",
        "shader_uniform_no_updates_per_guest_frame",
        "vsh_uniform_source_changes_per_guest_frame",
        "vsh_uniform_layout_changes_per_guest_frame",
        "vsh_uniform_inline_values_per_guest_frame",
        "vsh_uniform_dirty_rows_per_guest_frame",
        "psh_uniform_source_changes_per_guest_frame",
        "psh_uniform_layout_changes_per_guest_frame",
        "psh_uniform_texture_binding_changes_per_guest_frame",
        "psh_uniform_effective_input_changes_per_guest_frame",
        "shader_uniform_force_full_updates_per_guest_frame",
        "vsh_uniform_value_changes_per_guest_frame",
        "psh_uniform_value_changes_per_guest_frame",
        "equivalent_texture_scale_skips_per_guest_frame",
        "draw_pipeline_fast_reuses_per_guest_frame",
        "draw_pipeline_key_lookups_per_guest_frame",
        "draw_pipeline_cache_hits_per_guest_frame",
        "draw_pipeline_cache_misses_per_guest_frame",
        "draw_pipeline_binding_changes_per_guest_frame",
        "clear_pipeline_cache_hits_per_guest_frame",
        "clear_pipeline_cache_misses_per_guest_frame",
        "native_bc_uploads_per_guest_frame",
        "native_bc_source_bytes_per_guest_frame",
        "native_bc_staged_bytes_per_guest_frame",
        "native_bc_prepare_cpu_us_per_guest_frame",
        "decoded_bc_uploads_per_guest_frame",
        "decoded_bc_source_bytes_per_guest_frame",
        "decoded_bc_staged_bytes_per_guest_frame",
        "decoded_bc_prepare_cpu_us_per_guest_frame",
        "shader_query_overflows_per_guest_frame",
        "shader_stats_overflows_per_guest_frame",
    )
    scalars = {field: 0 for field in scalar_fields}
    shader_totals = {}

    for frame in frames:
        for key, field in finish_fields.items():
            add_arrays(finish[key], frame[field], field)
        for key, field in single_fields.items():
            add_arrays(single[key], frame[field], field)
        for key, field in gpu_finish_fields.items():
            if field in frame:
                add_arrays(gpu_finish[key], frame[field], field)
        for name, field in pipeline_fields.items():
            if field in frame:
                add_arrays(pipeline_finish[name], frame[field], field)
        if "cpu_region_calls_per_guest_frame" in frame:
            add_arrays(
                cpu_region_calls, frame["cpu_region_calls_per_guest_frame"],
                "cpu_region_calls_per_guest_frame"
            )
        if "cpu_region_us_per_guest_frame" in frame:
            add_arrays(
                cpu_region_us, frame["cpu_region_us_per_guest_frame"],
                "cpu_region_us_per_guest_frame"
            )
        for field in scalar_fields:
            scalars[field] += int(frame.get(field, 0))
        for shader in frame.get(
            "fragment_shader_stats_per_guest_frame", []
        ):
            spirv_hash = str(shader["spirv_hash"])
            total = shader_totals.setdefault(spirv_hash, {
                "draw_count": 0,
                "gpu_timed_draw_count": 0,
                "gpu_time_ns": 0,
                "pipeline_statistics": {
                    name: 0 for name in pipeline_names
                },
                "clip_region0_covers_scissor": {
                    "draw_count": 0,
                    "pipeline_statistics": {
                        name: 0 for name in pipeline_names
                    },
                },
            })
            total["draw_count"] += int(shader["draw_count"])
            total["gpu_timed_draw_count"] += int(shader.get(
                "gpu_timed_draw_count", 0
            ))
            total["gpu_time_ns"] += int(shader.get("gpu_time_ns", 0))
            for name in pipeline_names:
                total["pipeline_statistics"][name] += int(
                    shader.get(name, 0)
                )
            clip = total["clip_region0_covers_scissor"]
            clip["draw_count"] += int(shader.get(
                "clip_region0_covers_scissor_draw_count", 0
            ))
            for name in pipeline_names:
                clip["pipeline_statistics"][name] += int(shader.get(
                    f"clip_region0_covers_scissor_{name}", 0
                ))

    frame_count = len(frames)
    finish_owners = ranked_owners(
        finish_names, finish["calls"], finish["submits"],
        finish["timed"], finish["submit_us"], finish["waits"],
        finish["wait_us"], frame_count, "finish_reason"
    )
    finish_indices = {name: index for index, name in enumerate(finish_names)}
    for owner in finish_owners:
        index = finish_indices[owner["owner"]]
        owner["gpu"] = {
            key: values[index] for key, values in gpu_finish.items()
        }
        owner["gpu"].update({
            f"{key}_per_guest_frame": values[index] / frame_count
            for key, values in gpu_finish.items()
        })
        owner["pipeline_statistics"] = {
            name: {
                "count": values[index],
                "per_guest_frame": values[index] / frame_count,
            }
            for name, values in pipeline_finish.items()
        }
    single_owners = ranked_owners(
        single_names, single["calls"], single["submits"],
        single["timed"], single["submit_us"], single["waits"],
        single["wait_us"], frame_count, "single_time_caller"
    )
    owners = sorted(
        finish_owners + single_owners,
        key=lambda owner: owner["wait_us"], reverse=True
    )
    total_wait_us = sum(owner["wait_us"] for owner in owners)
    total_submit_cpu_us = sum(owner["submit_cpu_us"] for owner in owners)
    interval_us = 0
    if frame_count > 1:
        interval_us = (
            int(frames[-1]["timestamp_us"]) - int(frames[0]["timestamp_us"])
        )
    hot_fragment_shaders = []
    shader_gpu_time_total_ns = sum(
        total["gpu_time_ns"] for total in shader_totals.values()
    )
    for spirv_hash, total in shader_totals.items():
        clip = total["clip_region0_covers_scissor"]
        fragment_count = total["pipeline_statistics"].get(
            "fragment_shader_invocations", 0
        )
        clip_fragment_count = clip["pipeline_statistics"].get(
            "fragment_shader_invocations", 0
        )
        hot_fragment_shaders.append({
            "spirv_hash": spirv_hash,
            "draw_count": total["draw_count"],
            "draws_per_guest_frame": total["draw_count"] / frame_count,
            "gpu_timed_draw_count": total["gpu_timed_draw_count"],
            "gpu_time_ns": total["gpu_time_ns"],
            "gpu_time_ns_per_guest_frame": (
                total["gpu_time_ns"] / frame_count
            ),
            "gpu_time_ns_per_timed_draw": (
                total["gpu_time_ns"] / total["gpu_timed_draw_count"]
                if total["gpu_timed_draw_count"] else 0.0
            ),
            "gpu_time_share": (
                total["gpu_time_ns"] / shader_gpu_time_total_ns
                if shader_gpu_time_total_ns else 0.0
            ),
            "pipeline_statistics": {
                name: {
                    "count": value,
                    "per_guest_frame": value / frame_count,
                }
                for name, value in total["pipeline_statistics"].items()
            },
            "clip_region0_covers_scissor": {
                "draw_count": clip["draw_count"],
                "draws_per_guest_frame": clip["draw_count"] / frame_count,
                "draw_share": (
                    clip["draw_count"] / total["draw_count"]
                    if total["draw_count"] else 0.0
                ),
                "fragment_invocation_share": (
                    clip_fragment_count / fragment_count
                    if fragment_count else 0.0
                ),
                "pipeline_statistics": {
                    name: {
                        "count": value,
                        "per_guest_frame": value / frame_count,
                    }
                    for name, value in clip["pipeline_statistics"].items()
                },
            },
        })
    hot_fragment_shaders.sort(
        key=lambda shader: shader["pipeline_statistics"].get(
            "fragment_shader_invocations", {}
        ).get("count", 0),
        reverse=True,
    )
    hot_fragment_shaders_by_gpu_time = sorted(
        hot_fragment_shaders,
        key=lambda shader: shader["gpu_time_ns"],
        reverse=True,
    )

    result = {
        "schema_version": 1,
        "telemetry_schema_version": version,
        "duration_sampling": schema.get("duration_sampling"),
        "gpu_batch_timestamps": schema.get("gpu_batch_timestamps"),
        "pipeline_statistics_support": schema.get("pipeline_statistics"),
        "shader_state_classification": schema.get(
            "shader_state_classification"
        ),
        "shader_gpu_timestamps": schema.get("shader_gpu_timestamps"),
        "duration_values_are_estimates": any(
            owner["duration_estimated"] for owner in owners
        ),
        "source": str(args.telemetry),
        "guest_frames": frame_count,
        "measured_interval_us": interval_us,
        "total_wait_us": total_wait_us,
        "wait_us_per_guest_frame": total_wait_us / frame_count,
        "total_submit_cpu_us": total_submit_cpu_us,
        "submit_cpu_us_per_guest_frame": total_submit_cpu_us / frame_count,
        "blocked_share_of_measured_interval": (
            total_wait_us / interval_us if interval_us > 0 else None
        ),
        "submits_per_guest_frame": (
            scalars["vk_queue_submit_calls_per_guest_frame"] / frame_count
        ),
        "submit_infos_per_guest_frame": (
            scalars["vk_submit_infos_per_guest_frame"] / frame_count
        ),
        "command_buffers_per_guest_frame": (
            scalars["command_buffers_per_guest_frame"] / frame_count
        ),
        "staged_bytes_per_guest_frame": (
            scalars["staged_bytes_per_guest_frame"] / frame_count
        ),
        "staged_bytes_per_submit": (
            scalars["staged_bytes_per_guest_frame"] /
            scalars["vk_queue_submit_calls_per_guest_frame"]
            if scalars["vk_queue_submit_calls_per_guest_frame"] else 0.0
        ),
        "vertex_staged_bytes_per_guest_frame": (
            scalars["vertex_staged_bytes_per_guest_frame"] / frame_count
        ),
        "vertex_staging_copies_per_guest_frame": (
            scalars["vertex_staging_copies_per_guest_frame"] / frame_count
        ),
        "vertex_staging_capacity_growths": (
            scalars["vertex_staging_capacity_growths_per_guest_frame"]
        ),
        "vertex_staging_fallback_finishes_per_guest_frame": (
            scalars["vertex_staging_fallback_finishes_per_guest_frame"] /
            frame_count
        ),
        "vertex_dirty_checks_per_guest_frame": (
            scalars["vertex_dirty_checks_per_guest_frame"] / frame_count
        ),
        "vertex_dirty_pages_checked_per_guest_frame": (
            scalars["vertex_dirty_pages_checked_per_guest_frame"] /
            frame_count
        ),
        "vertex_dirty_hits_per_guest_frame": (
            scalars["vertex_dirty_hits_per_guest_frame"] / frame_count
        ),
        "vertex_dirty_hit_pages_per_guest_frame": (
            scalars["vertex_dirty_hit_pages_per_guest_frame"] / frame_count
        ),
        "vertex_dirty_repeated_ranges_per_guest_frame": (
            scalars["vertex_dirty_repeated_ranges_per_guest_frame"] /
            frame_count
        ),
        "vertex_dirty_repeated_range_hits_per_guest_frame": (
            scalars["vertex_dirty_repeated_range_hits_per_guest_frame"] /
            frame_count
        ),
        "cpu_regions": [
            {
                "region": name,
                "calls": cpu_region_calls[index],
                "cpu_us": cpu_region_us[index],
                "calls_per_guest_frame": (
                    cpu_region_calls[index] / frame_count
                ),
                "cpu_us_per_guest_frame": cpu_region_us[index] / frame_count,
            }
            for index, name in enumerate(cpu_region_names)
        ],
        "shader_binding_attribution": {
            field.removesuffix("_per_guest_frame"): scalars[field] / frame_count
            for field in (
                "shader_bind_calls_per_guest_frame",
                "shader_state_checks_per_guest_frame",
                "shader_state_dirty_per_guest_frame",
                "shader_binding_changes_per_guest_frame",
                "vsh_uniform_update_requests_per_guest_frame",
                "psh_uniform_update_requests_per_guest_frame",
                "shader_uniform_no_updates_per_guest_frame",
                "vsh_uniform_source_changes_per_guest_frame",
                "vsh_uniform_layout_changes_per_guest_frame",
                "vsh_uniform_inline_values_per_guest_frame",
                "vsh_uniform_dirty_rows_per_guest_frame",
                "psh_uniform_source_changes_per_guest_frame",
                "psh_uniform_layout_changes_per_guest_frame",
                "psh_uniform_texture_binding_changes_per_guest_frame",
                "psh_uniform_effective_input_changes_per_guest_frame",
                "shader_uniform_force_full_updates_per_guest_frame",
                "vsh_uniform_value_changes_per_guest_frame",
                "psh_uniform_value_changes_per_guest_frame",
                "equivalent_texture_scale_skips_per_guest_frame",
            )
        },
        "pipeline_cache_attribution": {
            field.removesuffix("_per_guest_frame"): scalars[field] / frame_count
            for field in (
                "draw_pipeline_fast_reuses_per_guest_frame",
                "draw_pipeline_key_lookups_per_guest_frame",
                "draw_pipeline_cache_hits_per_guest_frame",
                "draw_pipeline_cache_misses_per_guest_frame",
                "draw_pipeline_binding_changes_per_guest_frame",
                "clear_pipeline_cache_hits_per_guest_frame",
                "clear_pipeline_cache_misses_per_guest_frame",
            )
        },
        "ranked_wait_owners": owners,
        "finish_reasons": finish_owners,
        "gpu_totals": {
            key: sum(values) for key, values in gpu_finish.items()
        },
        "pipeline_statistics_totals": {
            name: sum(values) for name, values in pipeline_finish.items()
        },
        "hot_fragment_shaders": hot_fragment_shaders,
        "hot_fragment_shaders_by_gpu_time": (
            hot_fragment_shaders_by_gpu_time
        ),
        "shader_gpu_time_total_ns": shader_gpu_time_total_ns,
        "shader_query_overflows": scalars[
            "shader_query_overflows_per_guest_frame"
        ],
        "shader_stats_overflows": scalars[
            "shader_stats_overflows_per_guest_frame"
        ],
        "single_time_callers": single_owners,
        "latest_submission_state": {
            key: frames[-1][key] for key in (
                "in_flight_submission_count",
                "peak_in_flight_submission_count",
                "oldest_in_flight_serial",
                "newest_submitted_serial",
                "retirement_queue_objects",
                "retirement_queue_bytes",
            )
        },
        "latest_vertex_staging_capacity_bytes": frames[-1].get(
            "vertex_staging_capacity_bytes"
        ),
        "bc_uploads": {
            route: {
                "uploads": scalars[f"{route}_bc_uploads_per_guest_frame"],
                "source_bytes": scalars[
                    f"{route}_bc_source_bytes_per_guest_frame"
                ],
                "staged_bytes": scalars[
                    f"{route}_bc_staged_bytes_per_guest_frame"
                ],
                "prepare_cpu_us": scalars[
                    f"{route}_bc_prepare_cpu_us_per_guest_frame"
                ],
                "uploads_per_guest_frame": (
                    scalars[f"{route}_bc_uploads_per_guest_frame"] /
                    frame_count
                ),
            }
            for route in ("native", "decoded")
        },
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
