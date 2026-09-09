#!/usr/bin/env python3
"""Summarize cumulative XEMU_CAUSE records within one measurement window.

Input is JSONL containing only counter objects. Counts are diagnostic evidence,
not a benchmark verdict. Reject partial accounting, resets, and clock reversal.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path


IDENTITY = {"tid", "utc_us", "mono_us"}
ORIGINS = ("main", "helper", "other")
OUTCOMES = ("hit", "empty", "pc", "cs", "flags", "cflags")
REQUIRED = {f"{origin}_{key}" for origin in ORIGINS
            for key in (*OUTCOMES, "call", "qht_hit", "qht_miss")}
REQUIRED |= {"dirty_reset", "dirty_zero_arm", "dirty_entries", "dirty_armed"}


def percentage(numerator, denominator):
    return 100 * numerator / denominator if denominator else None


def analyze(rows, start_utc_us, end_utc_us):
    if start_utc_us >= end_utc_us:
        raise ValueError("measurement window must advance")
    grouped = defaultdict(list)
    for row in rows:
        if not IDENTITY <= row.keys():
            raise ValueError("missing timestamp/thread identity")
        if not all(type(value) is int and value >= 0 for value in row.values()):
            raise ValueError("counter values and identities must be nonnegative integers")
        if start_utc_us <= row["utc_us"] <= end_utc_us:
            grouped[row["tid"]].append(row)
    if not grouped:
        raise ValueError("no counter records in measurement window")

    threads = []
    for tid, samples in sorted(grouped.items()):
        if len(samples) < 2:
            raise ValueError(f"thread {tid}: fewer than two in-window samples")
        counters = samples[0].keys() - IDENTITY
        if not REQUIRED <= counters:
            raise ValueError(f"thread {tid}: incomplete counter schema")
        previous = None
        for sample in samples:
            if sample.keys() - IDENTITY != counters:
                raise ValueError(f"thread {tid}: counter schema changed")
            if previous is not None:
                if (sample["mono_us"] <= previous["mono_us"] or
                        sample["utc_us"] < previous["utc_us"]):
                    raise ValueError(f"thread {tid}: clock did not advance")
                if any(sample[key] < previous[key] for key in counters):
                    raise ValueError(f"thread {tid}: cumulative counter decreased")
            for origin in ORIGINS:
                calls = sample[f"{origin}_call"]
                outcomes = sum(sample[f"{origin}_{key}"] for key in OUTCOMES)
                misses = calls - sample[f"{origin}_hit"]
                probes = sample[f"{origin}_qht_hit"] + sample[f"{origin}_qht_miss"]
                if calls != outcomes or misses != probes:
                    raise ValueError(f"thread {tid}: incomplete {origin} lookup accounting")
            previous = sample

        first, last = samples[0], samples[-1]
        seconds = (last["mono_us"] - first["mono_us"]) / 1_000_000
        delta = {key: last[key] - first[key] for key in sorted(counters)}
        derived = {
            f"{origin}_cache_hit_percent": percentage(
                delta[f"{origin}_hit"], delta[f"{origin}_call"])
            for origin in ORIGINS
        }
        derived.update({
            "helper_collision_share_of_misses_percent": percentage(
                delta["helper_pc"], delta["helper_call"] - delta["helper_hit"]),
            "zero_arm_scan_percent": percentage(delta["dirty_zero_arm"], delta["dirty_reset"]),
            "entries_per_scan": (delta["dirty_entries"] / delta["dirty_reset"]
                                 if delta["dirty_reset"] else None),
            "new_arms_per_scan": (delta["dirty_armed"] / delta["dirty_reset"]
                                  if delta["dirty_reset"] else None),
        })
        threads.append({
            "tid": tid, "rows": len(samples), "seconds": seconds,
            "first_sample_utc_us": first["utc_us"],
            "last_sample_utc_us": last["utc_us"],
            "delta": delta,
            "rates_per_second": {key: value / seconds for key, value in delta.items()},
            "derived": derived,
        })
    return {"schema_version": 1, "purpose": "causal counts, not benchmark acceptance",
            "performance_acceptance": False, "lookup_partition_check": "PASS",
            "start_utc_us": start_utc_us, "end_utc_us": end_utc_us,
            "threads": threads}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("records", type=Path)
    parser.add_argument("--start-utc-us", required=True, type=int)
    parser.add_argument("--end-utc-us", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        with args.records.open(encoding="utf-8") as stream:
            rows = [json.loads(line) for line in stream if line.strip()]
        report = analyze(rows, args.start_utc_us, args.end_utc_us)
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(1, f"counter analysis failed: {error}\n")
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
