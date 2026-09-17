#!/usr/bin/env python3
"""Aggregate deferred Vulkan shader-identity stderr records."""

import argparse
import csv
import io
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


MISS_PREFIX = "nv2a/vk: shader-module-miss"
SUMMARY_PREFIX = "nv2a/vk: shader-identity-summary"
MISS_RE = re.compile(
    r"^nv2a/vk: shader-module-miss "
    r"profile_frame=(?P<profile_frame>\d+) "
    r"stage=(?P<stage>\d+) "
    r"key=(?P<key>[0-9a-fA-F]{16}) "
    r"source=(?P<source>[0-9a-fA-F]{16}) "
    r"source_class=(?P<source_class>first|repeat|saturated) "
    r"generation_us=(?P<generation_us>\d+) "
    r"compile_us=(?P<compile_us>\d+) "
    r"module_create_us=(?P<module_create_us>\d+) "
    r"reflection_us=(?P<reflection_us>\d+)$"
)
SUMMARY_RE = re.compile(
    r"^nv2a/vk: shader-identity-summary "
    r"records=(?P<records>\d+) "
    r"records_saturated=(?P<records_saturated>[01]) "
    r"unique_sources=(?P<unique_sources>\d+) "
    r"source_bytes=(?P<source_bytes>\d+)$"
)
TIMING_NAMES = ("generation", "compile", "module_create", "reflection")
STAGE_NAMES = {
    1: "vertex",
    2: "tessellation-control",
    4: "tessellation-evaluation",
    8: "geometry",
    16: "fragment",
    32: "compute",
}


class ParseError(ValueError):
    """The input contains a malformed shader-identity record."""


def stage_name(stage: int) -> str:
    return STAGE_NAMES.get(stage, f"unknown-{stage}")


def parse_input(path: Path) -> tuple[list[dict], dict | None]:
    records = []
    trace_summary = None
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(), 1
    ):
        line = raw_line.strip()
        if line.startswith(MISS_PREFIX):
            match = MISS_RE.fullmatch(line)
            if not match:
                raise ParseError(f"malformed shader-module-miss line {line_number}")
            values = match.groupdict()
            records.append({
                "profile_frame": int(values["profile_frame"]),
                "stage": int(values["stage"]),
                "key": values["key"].lower(),
                "source": values["source"].lower(),
                "source_class": values["source_class"],
                "generation_us": int(values["generation_us"]),
                "compile_us": int(values["compile_us"]),
                "module_create_us": int(values["module_create_us"]),
                "reflection_us": int(values["reflection_us"]),
            })
        elif line.startswith(SUMMARY_PREFIX):
            match = SUMMARY_RE.fullmatch(line)
            if not match:
                raise ParseError(f"malformed shader-identity-summary line {line_number}")
            if trace_summary is not None:
                raise ParseError("duplicate shader-identity-summary")
            values = match.groupdict()
            trace_summary = {name: int(value) for name, value in values.items()}

    if not records and trace_summary is None:
        raise ParseError("no shader identity records or summary")
    return records, trace_summary


def empty_group(profile_frame: int, stage: int) -> dict:
    return {
        "profile_frame": profile_frame,
        "stage": stage,
        "stage_name": stage_name(stage),
        "misses": 0,
        "source_classes": {"first": 0, "repeat": 0, "saturated": 0},
        "unique_keys": set(),
        "unique_sources": set(),
        "same_key_repeat": 0,
        "different_key_same_source": 0,
        "timing_values": {name: [] for name in TIMING_NAMES},
    }


def finalize_group(group: dict) -> dict:
    return {
        "profile_frame": group["profile_frame"],
        "stage": group["stage"],
        "stage_name": group["stage_name"],
        "misses": group["misses"],
        "source_classes": group["source_classes"],
        "unique_key_count": len(group["unique_keys"]),
        "unique_source_count": len(group["unique_sources"]),
        "repeat_identity": {
            "same_key_repeat": group["same_key_repeat"],
            "different_key_same_source": group["different_key_same_source"],
        },
        "timing_us": {
            name: {
                "sum": sum(group["timing_values"][name]),
                "max": max(group["timing_values"][name], default=0),
            }
            for name in TIMING_NAMES
        },
    }


def summarize(records: list[dict], trace_summary: dict | None) -> dict:
    groups = {}
    identity_keys = defaultdict(set)
    record_source_tracking_saturated = False

    for record in records:
        identity = (record["stage"], record["source"])
        if record["source_class"] == "repeat":
            repeat_kind = (
                "same_key_repeat"
                if record["key"] in identity_keys[identity]
                else "different_key_same_source"
            )
        else:
            repeat_kind = None
        identity_keys[identity].add(record["key"])

        group_key = (record["profile_frame"], record["stage"])
        group = groups.setdefault(group_key, empty_group(*group_key))
        group["misses"] += 1
        group["source_classes"][record["source_class"]] += 1
        group["unique_keys"].add(record["key"])
        group["unique_sources"].add(record["source"])
        if repeat_kind:
            group[repeat_kind] += 1
        for name in TIMING_NAMES:
            group["timing_values"][name].append(record[f"{name}_us"])
        if record["source_class"] == "saturated":
            record_source_tracking_saturated = True

    incomplete_reasons = []
    if record_source_tracking_saturated:
        incomplete_reasons.append("record_source_tracking_saturated")
    if trace_summary and trace_summary["records_saturated"]:
        incomplete_reasons.append("summary_records_saturated")
    if trace_summary is None:
        incomplete_reasons.append("missing_summary")
    elif trace_summary["records"] != len(records):
        incomplete_reasons.append("summary_record_count_mismatch")

    return {
        "schema_version": 1,
        "status": "incomplete" if incomplete_reasons else "complete",
        "incomplete_reasons": incomplete_reasons,
        "record_count": len(records),
        "trace_summary": trace_summary,
        "aggregates": [
            finalize_group(groups[key]) for key in sorted(groups)
        ],
    }


def flat_rows(result: dict) -> list[dict]:
    rows = []
    for aggregate in result["aggregates"]:
        row = {
            "status": result["status"],
            "incomplete_reasons": ";".join(result["incomplete_reasons"]),
            "profile_frame": aggregate["profile_frame"],
            "stage": aggregate["stage"],
            "stage_name": aggregate["stage_name"],
            "misses": aggregate["misses"],
            **aggregate["source_classes"],
            "unique_key_count": aggregate["unique_key_count"],
            "unique_source_count": aggregate["unique_source_count"],
            **aggregate["repeat_identity"],
        }
        for name in TIMING_NAMES:
            row[f"{name}_us_sum"] = aggregate["timing_us"][name]["sum"]
            row[f"{name}_us_max"] = aggregate["timing_us"][name]["max"]
        rows.append(row)
    return rows


def render_csv(result: dict) -> str:
    fieldnames = [
        "status", "incomplete_reasons", "profile_frame", "stage",
        "stage_name", "misses", "first", "repeat", "saturated",
        "unique_key_count", "unique_source_count", "same_key_repeat",
        "different_key_same_source",
    ]
    for name in TIMING_NAMES:
        fieldnames.extend((f"{name}_us_sum", f"{name}_us_max"))
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(flat_rows(result))
    return output.getvalue()


def render_markdown(result: dict) -> str:
    lines = [
        "# Vulkan shader identity summary",
        "",
        f"Status: **{result['status']}**",
        "",
    ]
    if result["incomplete_reasons"]:
        lines.extend((
            "Incomplete reasons: " + ", ".join(result["incomplete_reasons"]),
            "",
        ))
    lines.extend((
        "## Miss and identity counts",
        "",
        "| Profile frame | Stage | Misses | First | Repeat | Saturated | "
        "Unique keys | Unique sources | Same-key repeat | Different-key same-source |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ))
    for row in flat_rows(result):
        lines.append(
            f"| {row['profile_frame']} | {row['stage_name']} ({row['stage']}) | "
            f"{row['misses']} | {row['first']} | {row['repeat']} | "
            f"{row['saturated']} | {row['unique_key_count']} | "
            f"{row['unique_source_count']} | {row['same_key_repeat']} | "
            f"{row['different_key_same_source']} |"
        )
    lines.extend((
        "",
        "## Timing totals",
        "",
        "| Profile frame | Stage | Generation sum/max (us) | Compile sum/max (us) | "
        "Module create sum/max (us) | Reflection sum/max (us) |",
        "| ---: | --- | ---: | ---: | ---: | ---: |",
    ))
    for row in flat_rows(result):
        lines.append(
            f"| {row['profile_frame']} | {row['stage_name']} ({row['stage']}) | "
            f"{row['generation_us_sum']}/{row['generation_us_max']} | "
            f"{row['compile_us_sum']}/{row['compile_us_max']} | "
            f"{row['module_create_us_sum']}/{row['module_create_us_max']} | "
            f"{row['reflection_us_sum']}/{row['reflection_us_max']} |"
        )
    return "\n".join(lines) + "\n"


def render(result: dict, output_format: str) -> str:
    if output_format == "json":
        return json.dumps(result, indent=2, sort_keys=True) + "\n"
    if output_format == "markdown":
        return render_markdown(result)
    return render_csv(result)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stderr", type=Path, help="xemu stderr capture")
    parser.add_argument(
        "--format", choices=("json", "markdown", "csv"), default="json"
    )
    parser.add_argument(
        "--output", type=Path, help="output path; omit to write to stdout"
    )
    args = parser.parse_args()

    try:
        records, trace_summary = parse_input(args.stderr)
        rendered = render(summarize(records, trace_summary), args.format)
    except (OSError, ParseError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
