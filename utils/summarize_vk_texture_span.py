#!/usr/bin/env python3
"""Summarize opt-in Vulkan clamped-cubemap attribution records."""

import argparse
import json
from pathlib import Path


PREFIX = "clamped_cubemap_"
SUFFIX = "_per_guest_frame"
FIELD_NAMES = (
    "prepares",
    "sampled_levels",
    "storage_levels",
    "storage_span_bytes",
    "sampled_span_bytes",
    "extra_span_bytes",
    "surface_range_checks",
    "surface_range_check_cpu_us",
    "prepare_dirty_checks",
    "prepare_dirty_hits",
    "prepare_dirty_check_cpu_us",
    "bound_dirty_checks",
    "bound_dirty_hits",
    "bound_dirty_storage_span_bytes",
    "bound_dirty_sampled_span_bytes",
    "bound_dirty_extra_span_bytes",
    "bound_dirty_check_cpu_us",
    "content_hashes",
    "content_hash_texture_bytes",
    "content_hash_extra_texture_bytes",
    "content_hash_cpu_us",
    "uploads",
    "upload_cpu_us",
)
FIELDS = tuple(f"{PREFIX}{name}{SUFFIX}" for name in FIELD_NAMES)
CPU_FIELDS = (
    "surface_range_check_cpu_us",
    "prepare_dirty_check_cpu_us",
    "bound_dirty_check_cpu_us",
    "content_hash_cpu_us",
    "upload_cpu_us",
)
TEXTURE_FIELD_NAMES = (
    "texture_creates",
    "texture_key_hashes",
    "texture_key_hash_cpu_us",
    "texture_cache_lookups",
    "texture_cache_lookup_cpu_us",
    "texture_cache_saturated_lookups",
    "texture_cache_saturated_misses",
    "texture_cache_hits",
    "texture_cache_misses",
    "cubemap_prepares",
    "cubemap_same_level_prepares",
    "cubemap_texture_length_calls",
    "cubemap_texture_length_cpu_us",
    "cubemap_layouts",
    "cubemap_layout_cpu_us",
    "cubemap_uploads",
    "cubemap_upload_cpu_us",
)
TEXTURE_FIELDS = tuple(f"{name}{SUFFIX}" for name in TEXTURE_FIELD_NAMES)
TEXTURE_CPU_FIELDS = (
    "texture_key_hash_cpu_us",
    "texture_cache_lookup_cpu_us",
    "cubemap_texture_length_cpu_us",
    "cubemap_layout_cpu_us",
    "cubemap_upload_cpu_us",
)
PIPELINE_FIELD_NAMES = (
    "pipeline_shader_binds",
    "pipeline_shader_bind_cpu_us",
    "pipeline_key_inits",
    "pipeline_key_init_cpu_us",
    "pipeline_key_hashes",
    "pipeline_key_hash_cpu_us",
    "pipeline_cache_lookups",
    "pipeline_cache_lookup_cpu_us",
    "pipeline_cache_hits",
    "pipeline_cache_misses",
    "pipeline_layout_creates",
    "pipeline_layout_create_cpu_us",
    "graphics_pipeline_creates",
    "graphics_pipeline_create_cpu_us",
)
PIPELINE_FIELDS = tuple(f"{name}{SUFFIX}" for name in PIPELINE_FIELD_NAMES)
PIPELINE_CPU_FIELDS = (
    "pipeline_shader_bind_cpu_us",
    "pipeline_key_init_cpu_us",
    "pipeline_key_hash_cpu_us",
    "pipeline_cache_lookup_cpu_us",
    "pipeline_layout_create_cpu_us",
    "graphics_pipeline_create_cpu_us",
)


def read_records(path: Path) -> tuple[dict, list[dict]]:
    schema = None
    frames = []
    lines = path.read_text(encoding="utf-8-sig").splitlines(keepends=True)
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            incomplete_final_write = (
                line_number == len(lines) and not line.endswith(("\n", "\r"))
            )
            if incomplete_final_write:
                break
            raise SystemExit(
                f"invalid JSON on line {line_number}: {error}"
            ) from error
        if record.get("type") == "schema":
            schema = record
        elif record.get("type") == "frame":
            frames.append(record)

    if schema is None or int(schema.get("schema_version", 0)) < 6:
        raise SystemExit("missing or unsupported Vulkan telemetry schema")
    if not frames:
        raise SystemExit("no Vulkan guest-frame records")
    return schema, frames


def classify(prepares: int, peak_cpu_us: int) -> str:
    if prepares == 0:
        return "path_absent"
    if peak_cpu_us < 1000:
        return "below_1ms_reject"
    if peak_cpu_us < 5000:
        return "possible_contributor_1_to_5ms"
    return "at_least_5ms_behavioral_ab_warranted"


def summarize(schema: dict, frames: list[dict]) -> dict:
    totals = {name: 0 for name in FIELD_NAMES}
    output_frames = []
    for frame_index, frame in enumerate(frames):
        missing = [field for field in FIELDS if field not in frame]
        if missing:
            raise SystemExit(
                f"frame {frame_index} lacks texture-span field {missing[0]}"
            )
        values = {
            name: int(frame[f"{PREFIX}{name}{SUFFIX}"])
            for name in FIELD_NAMES
        }
        for name, value in values.items():
            totals[name] += value
        focused_cpu_us = sum(values[name] for name in CPU_FIELDS)
        output_frames.append({
            "frame_index": frame_index,
            "guest_frame": int(frame["guest_frame"]),
            "focused_cpu_us": focused_cpu_us,
            **values,
        })

    peak = max(output_frames, key=lambda frame: frame["focused_cpu_us"])
    active_frames = [
        frame for frame in output_frames if frame["prepares"] > 0
    ]
    result = {
        "schema_version": 1,
        "telemetry_schema_version": int(schema["schema_version"]),
        "source_field_contract": {
            "prefix": PREFIX,
            "suffix": SUFFIX,
            "required_fields": list(FIELD_NAMES),
        },
        "frame_count": len(output_frames),
        "active_frame_count": len(active_frames),
        "totals": {f"{PREFIX}{name}": value for name, value in totals.items()},
        "peak_focused_cpu_frame": peak,
        "classification": classify(totals["prepares"], peak["focused_cpu_us"]),
        "thresholds": {
            "below_1ms": "reject as the tail cause",
            "1_to_below_5ms": "possible contributor only",
            "at_least_5ms": "permits a one-change behavioral A/B",
        },
        "frames": output_frames,
    }
    if int(schema["schema_version"]) >= 7:
        texture_totals = {name: 0 for name in TEXTURE_FIELD_NAMES}
        texture_frames = []
        for frame_index, frame in enumerate(frames):
            missing = [field for field in TEXTURE_FIELDS if field not in frame]
            if missing:
                raise SystemExit(
                    f"frame {frame_index} lacks texture-work field {missing[0]}"
                )
            values = {
                name: int(frame[f"{name}{SUFFIX}"])
                for name in TEXTURE_FIELD_NAMES
            }
            for name, value in values.items():
                texture_totals[name] += value
            cpu_us = sum(values[name] for name in TEXTURE_CPU_FIELDS)
            texture_frames.append({
                "frame_index": frame_index,
                "guest_frame": int(frame["guest_frame"]),
                "cpu_us": cpu_us,
                **values,
            })
        result["texture_work"] = {
            "source_field_contract": {
                "suffix": SUFFIX,
                "required_fields": list(TEXTURE_FIELD_NAMES),
            },
            "totals": texture_totals,
            "peak_cpu_frame": max(
                texture_frames, key=lambda frame: frame["cpu_us"]
            ),
            "frames": texture_frames,
        }
    if int(schema["schema_version"]) >= 8:
        pipeline_totals = {name: 0 for name in PIPELINE_FIELD_NAMES}
        pipeline_frames = []
        for frame_index, frame in enumerate(frames):
            missing = [field for field in PIPELINE_FIELDS if field not in frame]
            if missing:
                raise SystemExit(
                    f"frame {frame_index} lacks pipeline-work field {missing[0]}"
                )
            values = {
                name: int(frame[f"{name}{SUFFIX}"])
                for name in PIPELINE_FIELD_NAMES
            }
            for name, value in values.items():
                pipeline_totals[name] += value
            cpu_us = sum(values[name] for name in PIPELINE_CPU_FIELDS)
            pipeline_frames.append({
                "frame_index": frame_index,
                "guest_frame": int(frame["guest_frame"]),
                "cpu_us": cpu_us,
                **values,
            })
        result["pipeline_work"] = {
            "source_field_contract": {
                "suffix": SUFFIX,
                "required_fields": list(PIPELINE_FIELD_NAMES),
            },
            "totals": pipeline_totals,
            "peak_cpu_frame": max(
                pipeline_frames, key=lambda frame: frame["cpu_us"]
            ),
            "frames": pipeline_frames,
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("telemetry", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    schema, frames = read_records(args.telemetry)
    result = summarize(schema, frames)
    args.output.write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
