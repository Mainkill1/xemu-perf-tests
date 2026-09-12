#!/usr/bin/env python3
"""Compare two sanitized PGR2 Vulkan telemetry summaries.

This is a diagnostic correlation report. It preserves the signed On-minus-Off
delta and makes no performance acceptance decision.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"summary is not an object: {path}")
    return value


def region(summary: dict, name: str) -> dict:
    for item in summary.get("cpu_regions", []):
        if item.get("region") == name:
            return item
    raise ValueError(f"telemetry summary has no CPU region {name!r}")


def wait_owner(summary: dict, name: str) -> dict:
    for item in summary.get("finish_reasons", []):
        if item.get("owner") == name:
            return item
    return {"owner": name, "wait_us": 0.0, "wait_us_per_guest_frame": 0.0}


def metric(summary: dict, name: str) -> float:
    if name == "pipeline_prepare_cpu_us_per_guest_frame":
        return float(region(summary, "pipeline_prepare").get("cpu_us_per_guest_frame", 0.0))
    if name == "flip_stall_wait_us_per_guest_frame":
        return float(wait_owner(summary, "flip_stall").get("wait_us_per_guest_frame", 0.0))
    if name == "stalled_wait_us_per_guest_frame":
        return float(wait_owner(summary, "stalled").get("wait_us_per_guest_frame", 0.0))
    if name == "total_wait_us_per_guest_frame":
        return float(summary.get("wait_us_per_guest_frame", 0.0))
    if name == "submit_cpu_us_per_guest_frame":
        return float(summary.get("submit_cpu_us_per_guest_frame", 0.0))
    if name == "guest_frames":
        return float(summary.get("guest_frames", 0.0))
    raise ValueError(f"unknown metric {name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--off-summary", required=True, type=Path)
    parser.add_argument("--on-summary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    off = load(args.off_summary)
    on = load(args.on_summary)
    metrics = (
        "pipeline_prepare_cpu_us_per_guest_frame",
        "flip_stall_wait_us_per_guest_frame",
        "stalled_wait_us_per_guest_frame",
        "total_wait_us_per_guest_frame",
        "submit_cpu_us_per_guest_frame",
        "guest_frames",
    )
    rows = []
    for name in metrics:
        off_value = metric(off, name)
        on_value = metric(on, name)
        rows.append({
            "metric": name,
            "hybrid_off": off_value,
            "hybrid_on": on_value,
            "on_minus_off": on_value - off_value,
            "relative_change_percent": (
                (on_value - off_value) / abs(off_value) * 100.0
                if off_value else None
            ),
        })
    result = {
        "schema_version": 1,
        "kind": "pgr2-vulkan-hybrid-telemetry-diagnostic",
        "qualification": "diagnostic-only; no performance acceptance claim",
        "workload": "pgr2_snapshot",
        "renderer": "vulkan",
        "telemetry": "XEMU_VK_PERF_LOG",
        "hybrid_off": {"summary_file": args.off_summary.name, "shader_cache": "Enabled"},
        "hybrid_on": {"summary_file": args.on_summary.name, "shader_cache": "Enabled"},
        "correlation": {
            "question": "Does Hybrid On change pipeline_prepare CPU time alongside frame stalls?",
            "interpretation": "Compare signed On-minus-Off rows; positive duration deltas are adverse.",
        },
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    table = args.output.with_suffix(".md")
    lines = [
        "# PGR2 Vulkan Hybrid telemetry diagnostic",
        "",
        "Diagnostic only; positive duration deltas mean Hybrid On took longer.",
        "",
        "| Metric | Hybrid Off | Hybrid On | On - Off | Relative change |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        relative = "n/a" if row["relative_change_percent"] is None else f"{row['relative_change_percent']:+.3f}%"
        lines.append(
            f"| {row['metric']} | {row['hybrid_off']:.3f} | {row['hybrid_on']:.3f} | "
            f"{row['on_minus_off']:+.3f} | {relative} |"
        )
    table.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
