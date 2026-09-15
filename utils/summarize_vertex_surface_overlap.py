#!/usr/bin/env python3
"""Summarize a selective NV2A vertex/surface trace without publishing raw logs."""

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path


RAW = re.compile(
    r"raw vertex 0x([0-9a-f]+)\+0x([0-9a-f]+) "
    r"page 0x([0-9a-f]+)\+0x([0-9a-f]+)"
)
SURFACE = re.compile(
    r"vertex range 0x([0-9a-f]+)\+0x([0-9a-f]+) "
    r"overlaps surface 0x([0-9a-f]+)\+0x([0-9a-f]+)"
)
DOWNLOAD = re.compile(r"surface @ 0x([0-9a-f]+)")


def intersects(a, a_size, b, b_size):
    return a < b + b_size and b < a + a_size


def digest(path):
    hash_value = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            hash_value.update(block)
    return hash_value.hexdigest()


def summarize(trace_path, result_path, patch_path):
    result = json.loads(Path(result_path).read_text())
    if result.get("status") != "complete" or not result.get("private_hdd_deleted"):
        raise ValueError("diagnostic cell or private-disk cleanup did not complete")
    start = datetime.fromisoformat(result["measurement_started_utc"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(result["measurement_ended_utc"].replace("Z", "+00:00"))
    rows = []
    for line in Path(trace_path).read_text().splitlines():
        stamp = datetime.fromisoformat(line.split()[0].replace("Z", "+00:00"))
        event = line.split()[1]
        rows.append((stamp, event, line))
    event_counts = Counter(event for _, event, _ in rows)
    window = [(stamp, event, line) for stamp, event, line in rows if start <= stamp < end]
    window_counts = Counter(event for _, event, _ in window)
    surface_ranges = set()
    raw_requests = []
    for _, event, line in rows:
        if event == "nv2a_pgraph_surface_range_download":
            match = SURFACE.search(line)
            if not match:
                raise ValueError("malformed surface-range event")
            surface_ranges.add((int(match[3], 16), int(match[4], 16)))
        elif event == "nv2a_pgraph_vertex_sync_request":
            match = RAW.search(line)
            if not match:
                raise ValueError("malformed raw vertex event")
            raw_requests.append(tuple(int(match[i], 16) for i in range(1, 5)))
    if not surface_ranges or not raw_requests:
        raise ValueError("trace lacks overlap or raw-request events")
    actual_any = sum(
        any(intersects(raw_start, raw_size, surf_start, surf_size)
            for surf_start, surf_size in surface_ranges)
        for raw_start, raw_size, _, _ in raw_requests
    )
    by_surface = []
    for surf_start, surf_size in sorted(surface_ranges):
        aligned = [entry for entry in raw_requests
                   if intersects(entry[2], entry[3], surf_start, surf_size)]
        actual = sum(intersects(a, b, surf_start, surf_size)
                     for a, b, _, _ in aligned)
        gaps = [a - (surf_start + surf_size) if a >= surf_start + surf_size
                else surf_start - (a + b) for a, b, _, _ in aligned
                if not intersects(a, b, surf_start, surf_size)]
        page_overlap = sorted({min(c + d, surf_start + surf_size) - max(c, surf_start)
                               for _, _, c, d in aligned})
        downloads = [row for row in rows
                     if row[1] == "nv2a_pgraph_surface_download" and
                     (match := DOWNLOAD.search(row[2])) and
                     int(match[1], 16) == surf_start]
        by_surface.append({
            "surface_start_hex": hex(surf_start), "surface_size_bytes": surf_size,
            "aligned_requests_full_run": len(aligned),
            "actual_raw_overlaps_full_run": actual,
            "minimum_raw_gap_bytes": min(gaps) if gaps else None,
            "page_overlap_bytes": page_overlap,
            "downloads_full_run": len(downloads),
            "downloads_measurement_window": sum(start <= row[0] < end for row in downloads),
        })
    return {
        "status": "complete", "source_commit": result["source_commit"],
        "diagnostic_executable_sha256": result["executable_sha256"],
        "diagnostic_patch_sha256": digest(patch_path),
        "runner_sha256": result["runner_sha256"],
        "trace_sha256": digest(trace_path), "result_sha256": digest(result_path),
        "guest_flips_in_window": result["display_write_events"],
        "final_image_validation": result["final_image_validation"],
        "private_hdd_deleted": result["private_hdd_deleted"],
        "event_counts_full_run": dict(sorted(event_counts.items())),
        "event_counts_measurement_window": dict(sorted(window_counts.items())),
        "raw_requests_full_run": len(raw_requests),
        "raw_requests_intersecting_any_recorded_surface": actual_any,
        "surface_ranges": by_surface,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--patch", required=True)
    args = parser.parse_args()
    print(json.dumps(summarize(args.trace, args.result, args.patch), indent=2))


if __name__ == "__main__":
    main()
