#!/usr/bin/env python3
"""Create compact, host-context-minimized CSVs from validated WPA exports."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path) -> tuple[list[str], list[list[str]]]:
    data = path.read_bytes()
    if not data.endswith(b"\r\n"):
        raise RuntimeError(f"source CSV is not terminal-CRLF complete: {path}")
    with path.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.reader(stream))
    if not rows or any(len(row) != len(rows[0]) for row in rows[1:]):
        raise RuntimeError(f"malformed source CSV: {path}")
    return rows[0], rows[1:]


def column(header: list[str], name: str, occurrence: int = 0) -> int:
    matches = [index for index, value in enumerate(header) if value == name]
    if len(matches) <= occurrence:
        raise RuntimeError(f"missing column {name!r} occurrence {occurrence}")
    return matches[occurrence]


def write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sampled", required=True, type=Path)
    parser.add_argument("--precise", required=True, type=Path)
    parser.add_argument("--gpu", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--pid", required=True, type=int)
    parser.add_argument("--tid", required=True, type=int)
    parser.add_argument("--image-base", required=True, type=lambda value: int(value, 0))
    parser.add_argument("--image-end", required=True, type=lambda value: int(value, 0))
    args = parser.parse_args()
    if args.image_end <= args.image_base:
        raise RuntimeError("invalid image interval")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    process = f"xemu.exe ({args.pid})"

    sh, sampled = read_rows(args.sampled)
    s_process = column(sh, "Process")
    s_tid = column(sh, "Thread ID")
    s_time = column(sh, "TimeStamp (s)")
    s_weight = column(sh, "Weight (ms)")
    s_count = column(sh, "Count")
    s_address = column(sh, "Address")
    s_stack_tags = column(sh, "Stack (Frame Tags)")
    if any(row[s_process] != process or row[s_tid] != str(args.tid) for row in sampled):
        raise RuntimeError("sampled CPU filter gate failed")
    sampled_out = []
    for row in sampled:
        address = int(row[s_address], 16)
        in_image = args.image_base <= address < args.image_end
        stack_tags = row[s_stack_tags]
        if in_image:
            leaf_class = "xemu_image"
            leaf_module = "xemu.exe"
        elif stack_tags == "n/a" or stack_tags.endswith("/?!?"):
            leaf_class = "unknown_external"
            leaf_module = ""
        else:
            leaf = stack_tags.rsplit("/", 1)[-1]
            leaf_module = leaf.split("!", 1)[0]
            leaf_class = "external_module" if leaf_module else "unknown_external"
        sampled_out.append([
            str(args.pid), str(args.tid), row[s_time], row[s_weight], row[s_count],
            leaf_class, leaf_module,
            f"0x{address - args.image_base:08x}" if in_image else "",
        ])

    ph, precise = read_rows(args.precise)
    p_process = column(ph, "New Process")
    p_tid = column(ph, "New Thread Id")
    p_readier_process = column(ph, "Readying Process")
    p_readier_tid = column(ph, "Readying Thread Id")
    if any(row[p_process] != process or row[p_tid] != str(args.tid) for row in precise):
        raise RuntimeError("precise CPU filter gate failed")
    p_indices = [
        column(ph, "Last Switch-Out Time (s)", 0),
        column(ph, "Ready Time (s)"),
        column(ph, "Switch-In Time (s)", 0),
        column(ph, "Next Switch-Out Time (s)"),
        column(ph, "Waits (µs)", 0),
        column(ph, "Ready (µs)", 0),
        column(ph, "CPU Usage (in view) (ms)"),
        column(ph, "Count"),
        column(ph, "CPU"),
    ]
    precise_out = []
    for row in precise:
        readier = row[p_readier_process]
        if readier == process:
            scope = "same_process"
        elif readier == "Idle (0)":
            scope = "idle"
        elif readier == "Unknown":
            scope = "unknown"
        else:
            scope = "external"
        precise_out.append([
            str(args.pid), str(args.tid), *(row[index] for index in p_indices),
            scope, row[p_readier_tid],
        ])

    gh, gpu = read_rows(args.gpu)
    g_process = column(gh, "Process")
    if any(row[g_process] != process for row in gpu):
        raise RuntimeError("GPU process filter gate failed")
    g_indices = [
        column(gh, "ThreadId"), column(gh, "Type"), column(gh, "Count"),
        column(gh, "GPU Time (µs)", 0), column(gh, "Initialized (s)"),
        column(gh, "Submitted To HW (s)"), column(gh, "Start Execution (s)"),
        column(gh, "Finished (s)"), column(gh, "A/N/E"),
    ]
    gpu_out = [
        [str(args.pid), *(row[index] for index in g_indices)] for row in gpu
    ]

    outputs = {
        "sampled-pfifo.csv": (
            ["target_pid", "target_tid", "timestamp_s", "weight_ms", "count",
             "leaf_class", "leaf_module", "xemu_rva"], sampled_out
        ),
        "precise-pfifo.csv": (
            ["target_pid", "target_tid", "last_switch_out_s", "ready_s",
             "switch_in_s", "next_switch_out_s", "waits_us", "ready_us",
             "cpu_usage_ms", "count", "cpu", "readying_scope", "readying_tid"],
            precise_out,
        ),
        "gpu-process.csv": (
            ["target_pid", "submitting_tid", "type", "count", "gpu_time_us",
             "initialized_s", "submitted_s", "start_execution_s", "finished_s",
             "ane"], gpu_out
        ),
    }
    for name, (header, rows) in outputs.items():
        write_csv(args.output_dir / name, header, rows)
    manifest = {
        "source_hashes": {
            "sampled": sha256(args.sampled),
            "precise": sha256(args.precise),
            "gpu": sha256(args.gpu),
        },
        "target": {"pid": args.pid, "tid": args.tid},
        "image_interval": {
            "base": f"0x{args.image_base:016x}",
            "end_exclusive": f"0x{args.image_end:016x}",
        },
        "rows": {name: len(rows) for name, (_, rows) in outputs.items()},
        "output_hashes": {name: sha256(args.output_dir / name) for name in outputs},
        "redactions": [
            "full stack strings", "absolute non-xemu instruction addresses",
            "thread start fields", "old-process scheduler fields",
            "readier process names",
        ],
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
