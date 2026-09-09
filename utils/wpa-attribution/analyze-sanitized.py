#!/usr/bin/env python3
"""Validate compact WPA derivatives and reproduce bounded attribution totals."""
from __future__ import annotations

import argparse
import bisect
import csv
import gzip
import hashlib
import json
import re
import subprocess
from collections import defaultdict
from decimal import Decimal
from pathlib import Path


D = Decimal


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def number(value: str) -> Decimal:
    return D(value.replace(",", ""))


def read_csv(path: Path) -> list[dict[str, str]]:
    data = path.read_bytes()
    if not data.endswith(b"\n"):
        raise RuntimeError(f"CSV has no complete final record: {path}")
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise RuntimeError(f"CSV has no header: {path}")
        rows = list(reader)
        if any(None in row or None in row.values() for row in rows):
            raise RuntimeError(f"CSV has a malformed row: {path}")
    return rows


def clip_duration(begin: Decimal, end: Decimal,
                  view_begin: Decimal, view_end: Decimal) -> Decimal:
    return max(D(0), min(end, view_end) - max(begin, view_begin))


def merge_intervals(intervals: list[tuple[Decimal, Decimal]]) -> list[tuple[Decimal, Decimal]]:
    merged: list[list[Decimal]] = []
    for begin, end in sorted(intervals):
        if end <= begin:
            continue
        if not merged or begin > merged[-1][1]:
            merged.append([begin, end])
        elif end > merged[-1][1]:
            merged[-1][1] = end
    return [(begin, end) for begin, end in merged]


def interval_sum(intervals: list[tuple[Decimal, Decimal]]) -> Decimal:
    return sum((end - begin for begin, end in intervals), D(0))


def intersection_sum(left: list[tuple[Decimal, Decimal]],
                     right: list[tuple[Decimal, Decimal]]) -> Decimal:
    left = merge_intervals(left)
    right = merge_intervals(right)
    i = j = 0
    total = D(0)
    while i < len(left) and j < len(right):
        begin = max(left[i][0], right[j][0])
        end = min(left[i][1], right[j][1])
        if end > begin:
            total += end - begin
        if left[i][1] <= right[j][1]:
            i += 1
        else:
            j += 1
    return total


def exact_function_map(pe: Path, symbols: Path, objdump: str,
                       expected_pe_sha: str | None,
                       expected_symbol_sha: str | None):
    if expected_pe_sha and sha256(pe) != expected_pe_sha.lower():
        raise RuntimeError("exact PE hash gate failed")
    if expected_symbol_sha and sha256(symbols) != expected_symbol_sha.lower():
        raise RuntimeError("exact symbol-map hash gate failed")
    dump = subprocess.check_output(
        [objdump, "-p", str(pe)], text=True, errors="replace"
    )
    image_base_match = re.search(r"^ImageBase\s+([0-9A-Fa-f]+)$", dump, re.MULTILINE)
    if not image_base_match:
        raise RuntimeError("objdump output has no PE ImageBase")
    image_base = int(image_base_match.group(1), 16)
    ranges = []
    for line in dump.splitlines():
        match = re.search(
            r":\s+([0-9A-Fa-f]{16})\s+([0-9A-Fa-f]{16})\s+([0-9A-Fa-f]{16})$",
            line,
        )
        if match:
            begin, end, _ = (int(value, 16) for value in match.groups())
            if begin and end > begin:
                ranges.append((begin, end))
    ranges.sort()
    starts = [begin for begin, _ in ranges]
    labels: dict[int, list[str]] = defaultdict(list)
    opener = gzip.open if symbols.suffix == ".gz" else open
    with opener(symbols, "rt", encoding="utf-8") as stream:
        for line in stream:
            if line.startswith("#"):
                continue
            va, _, label = line.rstrip("\n").split("\t", 2)
            labels[int(va, 16)].append(label)

    def choose_label(values: list[str]) -> str | None:
        for value in values:
            if value != ".text" and not value.startswith((".l", ".L")):
                return value
        return None

    def resolve(rva: int) -> tuple[str, int, int]:
        va = image_base + rva
        index = bisect.bisect_right(starts, va) - 1
        if index < 0 or va >= ranges[index][1]:
            return "xemu text without .pdata extent", 0, 0
        begin, end = ranges[index]
        label = choose_label(labels.get(begin, []))
        if label is None:
            return "unnamed xemu .pdata extent", begin - image_base, end - image_base
        return label, begin - image_base, end - image_base

    return resolve


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sampled", required=True, type=Path)
    parser.add_argument("--precise", required=True, type=Path)
    parser.add_argument("--gpu", required=True, type=Path)
    parser.add_argument("--output-summary", required=True, type=Path)
    parser.add_argument("--output-leaves", required=True, type=Path)
    parser.add_argument("--pid", required=True, type=int)
    parser.add_argument("--tid", required=True, type=int)
    parser.add_argument("--start-s", required=True, type=D)
    parser.add_argument("--end-s", required=True, type=D)
    parser.add_argument("--pe", type=Path)
    parser.add_argument("--symbol-map", type=Path)
    parser.add_argument("--objdump", default="x86_64-w64-mingw32-objdump")
    parser.add_argument("--expected-pe-sha256")
    parser.add_argument("--expected-symbol-map-sha256")
    args = parser.parse_args()
    if args.end_s <= args.start_s:
        raise RuntimeError("invalid analysis range")
    if (args.pe is None) != (args.symbol_map is None):
        raise RuntimeError("--pe and --symbol-map must be supplied together")

    target_pid = str(args.pid)
    target_tid = str(args.tid)
    sampled = read_csv(args.sampled)
    precise = read_csv(args.precise)
    gpu = read_csv(args.gpu)
    if any(row["target_pid"] != target_pid or row["target_tid"] != target_tid
           for row in sampled + precise):
        raise RuntimeError("CPU target filter gate failed")
    if any(row["target_pid"] != target_pid for row in gpu):
        raise RuntimeError("GPU process filter gate failed")

    sample_weight = sum((number(row["weight_ms"]) for row in sampled), D(0))
    sample_count = sum((int(row["count"]) for row in sampled), 0)
    if any(not (args.start_s <= number(row["timestamp_s"]) <= args.end_s)
           for row in sampled):
        raise RuntimeError("sample timestamp outside requested range")
    resolver = None
    if args.pe is not None and args.symbol_map is not None:
        resolver = exact_function_map(
            args.pe, args.symbol_map, args.objdump,
            args.expected_pe_sha256, args.expected_symbol_map_sha256,
        )
    leaf_groups: dict[tuple[str, str, int, int], list[Decimal | int]] = defaultdict(
        lambda: [0, D(0)]
    )
    for row in sampled:
        leaf_class = row["leaf_class"]
        if leaf_class == "xemu_image":
            if resolver:
                label, begin, end = resolver(int(row["xemu_rva"], 16))
                key = ("xemu_exact" if begin else "xemu_unbounded", label, begin, end)
            else:
                key = ("xemu_unresolved", "xemu image", 0, 0)
        elif leaf_class == "external_module":
            key = ("external_module", row["leaf_module"], 0, 0)
        else:
            key = ("unknown_external", "unknown leaf", 0, 0)
        leaf_groups[key][0] += int(row["count"])
        leaf_groups[key][1] += number(row["weight_ms"])

    leaf_rows = []
    for (leaf_class, label, begin, end), (count, weight) in sorted(
        leaf_groups.items(), key=lambda item: (-item[1][1], item[0])
    ):
        leaf_rows.append({
            "leaf_class": leaf_class,
            "leaf": label,
            "begin_rva": f"0x{begin:08x}" if begin else "",
            "end_rva_exclusive": f"0x{end:08x}" if end else "",
            "samples": str(count),
            "weight_ms": format(weight, "f"),
            "sample_weight_percent": format(weight * 100 / sample_weight, ".6f"),
        })
    args.output_leaves.parent.mkdir(parents=True, exist_ok=True)
    with args.output_leaves.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(leaf_rows[0]))
        writer.writeheader()
        writer.writerows(leaf_rows)

    running = D(0)
    off_cpu = D(0)
    wait = D(0)
    ready = D(0)
    raw_wait = D(0)
    raw_ready = D(0)
    wait_intervals = []
    clamp_count = 0
    clamp_total = D(0)
    clamp_max = D(0)
    for row in precise:
        last_out = number(row["last_switch_out_s"])
        ready_time = number(row["ready_s"])
        switch_in = number(row["switch_in_s"])
        next_out = number(row["next_switch_out_s"])
        waits = number(row["waits_us"]) / D(1000000)
        readies = number(row["ready_us"]) / D(1000000)
        if switch_in < ready_time or next_out < switch_in:
            raise RuntimeError("invalid precise-table timestamp order")
        if switch_in - ready_time != readies:
            raise RuntimeError("Ready Time and Ready duration disagree")
        if ready_time < last_out:
            delta = last_out - ready_time
            if waits != 0:
                raise RuntimeError("negative rounded wait boundary with nonzero Waits")
            clamp_count += 1
            clamp_total += delta
            clamp_max = max(clamp_max, delta)
        elif ready_time - last_out != waits:
            raise RuntimeError("Ready Time and Waits duration disagree")
        phase_boundary = max(last_out, ready_time)
        running += number(row["cpu_usage_ms"]) / D(1000)
        raw_wait += waits
        raw_ready += readies
        off_cpu += clip_duration(last_out, switch_in, args.start_s, args.end_s)
        wait += clip_duration(last_out, phase_boundary, args.start_s, args.end_s)
        ready += clip_duration(phase_boundary, switch_in, args.start_s, args.end_s)
        wait_begin = max(last_out, args.start_s)
        wait_end = min(phase_boundary, args.end_s)
        if wait_end > wait_begin:
            wait_intervals.append((wait_begin, wait_end))
    view = args.end_s - args.start_s
    if abs((running + wait + ready) - view) > D("0.0000001"):
        raise RuntimeError("running/wait/ready partition does not close the view")

    gpu_intervals = []
    gpu_time = D(0)
    gpu_type: dict[str, list[Decimal | int]] = defaultdict(lambda: [0, D(0)])
    gpu_tid: dict[str, list[Decimal | int]] = defaultdict(lambda: [0, D(0)])
    for row in gpu:
        initialized = number(row["initialized_s"])
        submitted = number(row["submitted_s"])
        started = number(row["start_execution_s"])
        finished = number(row["finished_s"])
        duration = number(row["gpu_time_us"]) / D(1000000)
        if not (initialized <= submitted <= started <= finished):
            raise RuntimeError("invalid GPU timestamp order")
        if finished - started != duration:
            raise RuntimeError("GPU Time and execution timestamps disagree")
        if started < args.start_s or finished > args.end_s:
            raise RuntimeError("GPU execution interval outside requested range")
        gpu_time += duration
        gpu_intervals.append((started, finished))
        gpu_type[row["type"]][0] += int(row["count"])
        gpu_type[row["type"]][1] += duration
        gpu_tid[row["submitting_tid"]][0] += int(row["count"])
        gpu_tid[row["submitting_tid"]][1] += duration
    gpu_union = merge_intervals(gpu_intervals)

    def grouped(values: dict[str, list[Decimal | int]]) -> dict[str, dict[str, object]]:
        return {
            key: {"rows": int(value[0]), "time_s": format(value[1], "f")}
            for key, value in sorted(values.items())
        }

    summary = {
        "range_s": [format(args.start_s, "f"), format(args.end_s, "f")],
        "view_duration_s": format(view, "f"),
        "target": {"pid": args.pid, "tid": args.tid},
        "input_hashes": {
            "sampled": sha256(args.sampled),
            "precise": sha256(args.precise),
            "gpu": sha256(args.gpu),
        },
        "sampled_cpu": {
            "rows": len(sampled), "count": sample_count,
            "weight_ms": format(sample_weight, "f"),
            "first_timestamp_s": min(row["timestamp_s"] for row in sampled),
            "last_timestamp_s": max(row["timestamp_s"] for row in sampled),
            "leaf_summary_sha256": sha256(args.output_leaves),
            "top_leaf_groups": leaf_rows[:20],
            "limit": "sample weight only; unresolved caller frames prevent causal attribution",
        },
        "precise_cpu": {
            "rows": len(precise),
            "running_s": format(running, "f"),
            "running_percent": format(running * 100 / view, ".6f"),
            "off_cpu_s": format(off_cpu, "f"),
            "wait_s": format(wait, "f"),
            "ready_s": format(ready, "f"),
            "raw_waits_column_s": format(raw_wait, "f"),
            "raw_ready_column_s": format(raw_ready, "f"),
            "ready_boundary": (
                "exported WPA Ready Time (s), used as the absolute wait-to-ready "
                "boundary; this packet does not distinguish an observed ReadyThread "
                "event from a WPA-synthesized boundary"
            ),
            "ready_before_last_out_rounding_rows": clamp_count,
            "ready_before_last_out_rounding_total_us": format(clamp_total * D(1000000), "f"),
            "ready_before_last_out_rounding_max_us": format(clamp_max * D(1000000), "f"),
        },
        "process_gpu": {
            "rows": len(gpu),
            "summed_gpu_time_s": format(gpu_time, "f"),
            "execution_union_s": format(interval_sum(gpu_union), "f"),
            "by_type": grouped(gpu_type),
            "by_submitting_tid": grouped(gpu_tid),
            "gpu_union_intersection_with_pfifo_wait_s": format(
                intersection_sum(gpu_union, wait_intervals), "f"
            ),
            "limit": "temporal overlap only; no fence, utilization, copy, wait-cause, or FPS claim",
        },
    }
    args.output_summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
