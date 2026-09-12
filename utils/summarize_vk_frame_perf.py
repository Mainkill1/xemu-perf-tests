#!/usr/bin/env python3
"""Summarize opt-in Vulkan counters over a matching guest-flip time window.

The perf stream uses a monotonic clock; the guest-flip log uses UTC. Both
streams emit one row per guest frame, so join by ordinal after checking their
full-run lengths. This fails closed if the two captures lost an event.
"""

import argparse
import json
import statistics
from datetime import datetime
from pathlib import Path


def percentile(values, fraction):
    ordered = sorted(values)
    if not ordered:
        return None
    rank = (len(ordered) - 1) * fraction
    lo = int(rank)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (rank - lo)


def summarize(perf, flips, start, end):
    records = [json.loads(line) for line in Path(perf).read_text().splitlines()]
    schema = next(row for row in records if row.get("type") == "schema")
    frames = [row for row in records if row.get("type") == "frame"]
    times = [datetime.fromisoformat(line.split()[0].replace("Z", "+00:00"))
             for line in Path(flips).read_text().splitlines() if line.strip()]
    if len(frames) != len(times):
        raise ValueError(f"frame/flip count mismatch: {len(frames)} vs {len(times)}")
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("guest-flip timestamps are not strictly increasing")
    indices = [i for i, stamp in enumerate(times) if start <= stamp < end]
    if len(indices) < 2:
        raise ValueError("measurement window has fewer than two guest flips")
    reasons = schema["finish_reasons"]
    regions = schema["cpu_regions"]
    need = reasons.index("need_buffer_space")
    surface_down = reasons.index("surface_down")
    descriptor = regions.index("update_descriptor_sets")
    draw_flush = regions.index("draw_flush")
    rows = [frames[i] for i in indices]
    interval_ms = [(times[b] - times[a]).total_seconds() * 1000
                   for a, b in zip(indices, indices[1:]) if b == a + 1]
    if len(interval_ms) != len(indices) - 1:
        raise ValueError("measurement window has a discontinuous frame sequence")

    def samples(key, slot=None):
        return [row[key] if slot is None else row[key][slot] for row in rows]

    need_counts = samples("finish_submit_count_per_guest_frame", need)
    need_wait = samples("finish_sampled_wait_us_per_guest_frame", need)
    surface_wait = samples("finish_sampled_wait_us_per_guest_frame", surface_down)
    finish_wait = [sum(row["finish_sampled_wait_us_per_guest_frame"])
                   for row in rows]
    descriptor_us = samples("cpu_region_us_per_guest_frame", descriptor)
    flush_us = samples("cpu_region_us_per_guest_frame", draw_flush)
    descriptor_calls = samples("cpu_region_calls_per_guest_frame", descriptor)
    return {
        "status": "complete", "schema_version": schema["schema_version"],
        "full_run_frames": len(frames), "window_frames": len(rows),
        "window_intervals": len(interval_ms),
        "display_writes_per_second": len(rows) / (end - start).total_seconds(),
        "interval_ms": {"p50": percentile(interval_ms, .5),
                        "p95": percentile(interval_ms, .95),
                        "p99": percentile(interval_ms, .99),
                        "max": max(interval_ms)},
        "need_buffer_space": {
            "submit_count_total": sum(need_counts),
            "frames_with_submit": sum(n > 0 for n in need_counts),
            "submit_count_median_per_frame": statistics.median(need_counts),
            "sampled_wait_us_median_per_frame": statistics.median(need_wait),
            "sampled_wait_us_p95_per_frame": percentile(need_wait, .95),
        },
        "surface_down": {
            "submit_count_total": sum(samples("finish_submit_count_per_guest_frame", surface_down)),
            "sampled_wait_us_median_per_frame": statistics.median(surface_wait),
        },
        "all_finish_sampled_wait_us_median_per_frame": statistics.median(finish_wait),
        "descriptor_update": {
            "calls_median_per_frame": statistics.median(descriptor_calls),
            "region_us_median_per_frame": statistics.median(descriptor_us),
            "region_minus_need_wait_us_median_per_frame": statistics.median(
                a - b for a, b in zip(descriptor_us, need_wait)),
        },
        "draw_flush_region_us_median_per_frame": statistics.median(flush_us),
        "vertex_staged_bytes_median_per_frame": statistics.median(
            samples("vertex_staged_bytes_per_guest_frame")),
        "vk_queue_submit_calls_median_per_frame": statistics.median(
            samples("vk_queue_submit_calls_per_guest_frame")),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--perf", required=True)
    parser.add_argument("--flips", required=True)
    parser.add_argument("--start", required=True, help="UTC ISO-8601 time")
    parser.add_argument("--end", required=True, help="UTC ISO-8601 time")
    args = parser.parse_args()
    start = datetime.fromisoformat(args.start.replace("Z", "+00:00"))
    end = datetime.fromisoformat(args.end.replace("Z", "+00:00"))
    if not start.tzinfo or not end.tzinfo or end <= start:
        parser.error("start/end must be ordered timezone-aware timestamps")
    print(json.dumps(summarize(args.perf, args.flips, start, end), indent=2))


if __name__ == "__main__":
    main()
