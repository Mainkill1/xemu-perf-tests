#!/usr/bin/env python3
"""Recompute retained scheduler summaries from compact clipped intervals."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import statistics
from collections import defaultdict
from pathlib import Path


def merge_length(intervals: list[tuple[int, int]]) -> tuple[int, int]:
    ordered = sorted(intervals)
    raw = sum(end - start for start, end in ordered)
    merged = []
    for start, end in ordered:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    union = sum(end - start for start, end in merged)
    return union, raw - union


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("summary", type=Path, nargs="?", default=Path("trace-attribution-summary.json"))
    parser.add_argument("intervals", type=Path, nargs="?", default=Path("clipped-scheduler-intervals.csv.gz"))
    args = parser.parse_args()
    summary = json.loads(args.summary.read_text())
    digest = hashlib.sha256(args.intervals.read_bytes()).hexdigest()
    assert digest == summary["extraction"]["clipped_intervals_sha256"]

    state_ns = defaultdict(lambda: defaultdict(int))
    spans = defaultdict(list)
    metadata = {}
    with gzip.open(args.intervals, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == [
            "run_id", "renderer", "pair", "order_position", "build",
            "frame_duration_ns", "thread_label", "thread_id", "state",
            "start_offset_ns", "end_offset_ns",
        ]
        row_count = 0
        for row in reader:
            row_count += 1
            run_id = row["run_id"]
            tid = row["thread_id"]
            state = row["state"]
            assert state in {"running", "ready", "waiting"}
            start = int(row["start_offset_ns"])
            end = int(row["end_offset_ns"])
            duration = int(row["frame_duration_ns"])
            assert 0 <= start < end <= duration
            key = (run_id, tid)
            state_ns[key][state] += end - start
            spans[key].append((start, end))
            current = (
                row["renderer"], int(row["pair"]), row["order_position"],
                row["build"], duration, row["thread_label"],
            )
            assert key not in metadata or metadata[key] == current
            metadata[key] = current
    assert row_count == summary["extraction"]["clipped_interval_rows"]
    assert {key[0] for key in state_ns} == {
        run["run_id"] for run in summary["runs"]
    }
    assert len(summary["runs"]) == 20
    assert len({run["run_id"] for run in summary["runs"]}) == 20

    recomputed_runs = {}
    for expected in summary["runs"]:
        run_id = expected["run_id"]
        threads = []
        keys = sorted(
            (key for key in state_ns if key[0] == run_id),
            key=lambda key: int(key[1]),
        )
        for key in keys:
            _, tid = key
            renderer, pair, position, build, duration, label = metadata[key]
            assert (renderer, pair, position, build, duration) == (
                expected["renderer"], expected["pair"],
                expected["order_position"], expected["build"],
                expected["frame_duration_ns"],
            )
            covered, overlap = merge_length(spans[key])
            threads.append(
                {
                    "thread_label": label,
                    "thread_id": tid,
                    "running_ns": state_ns[key]["running"],
                    "ready_ns": state_ns[key]["ready"],
                    "waiting_ns": state_ns[key]["waiting"],
                    "covered_union_ns": covered,
                    "unresolved_gap_ns": max(0, duration - covered),
                    "row_overlap_ns": overlap,
                }
            )
        assert threads == expected["threads"]
        assert len(threads) == expected["thread_count"]
        cross = {
            state: sum(thread[f"{state}_ns"] for thread in threads)
            for state in ("running", "ready", "waiting")
        }
        assert cross == expected["cross_thread_sums_ns"]
        assert all(thread["unresolved_gap_ns"] == 0 for thread in threads)
        assert all(thread["row_overlap_ns"] == 0 for thread in threads)
        by_label = {thread["thread_label"]: thread for thread in threads}
        assert expected["key_threads"] == {
            role: by_label.get(role)
            for role in ("dominant-unnamed", "cpu0-tcg", "nv2a-pfifo")
        }
        recomputed_runs[run_id] = expected

    for renderer, expected_renderer in summary["order_comparison"].items():
        recomputed_pairs = []
        for pair_number in range(1, 6):
            first = next(
                run for run in summary["runs"]
                if run["renderer"] == renderer and run["pair"] == pair_number
                and run["order_position"] == "first"
            )
            second = next(
                run for run in summary["runs"]
                if run["renderer"] == renderer and run["pair"] == pair_number
                and run["order_position"] == "second"
            )
            roles = {}
            for role in ("dominant-unnamed", "cpu0-tcg", "nv2a-pfifo"):
                roles[role] = {
                    state: (
                        second["key_threads"][role][f"{state}_ns"]
                        - first["key_threads"][role][f"{state}_ns"]
                    )
                    for state in ("running", "ready", "waiting")
                }
            recomputed_pairs.append(
                {
                    "pair": pair_number,
                    "first_run": first["run_id"],
                    "second_run": second["run_id"],
                    "first_build": first["build"],
                    "second_build": second["build"],
                    "frame_second_minus_first_ns": (
                        second["frame_duration_ns"] - first["frame_duration_ns"]
                    ),
                    "key_thread_second_minus_first_ns": roles,
                }
            )
        assert recomputed_pairs == expected_renderer["pairs"]
        for role, states in expected_renderer["key_thread_summary"].items():
            for state, expected_state in states.items():
                values = [
                    pair["key_thread_second_minus_first_ns"][role][state]
                    for pair in recomputed_pairs
                ]
                assert values == expected_state["deltas_ns"]
                assert sum(value > 0 for value in values) == expected_state["second_greater_pairs"]
                assert int(statistics.median(values)) == expected_state["median_second_minus_first_ns"]

    print(
        f"validated {len(summary['runs'])} runs, {row_count} clipped intervals, "
        f"SHA-256 {digest}"
    )


if __name__ == "__main__":
    main()
