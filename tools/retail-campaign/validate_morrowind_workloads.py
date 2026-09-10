#!/usr/bin/env python3
"""Validate or inspect the no-launch Morrowind qualification contract."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SHA256 = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_METRICS = [
    "cadence_per_second",
    "average_interval_ms",
    "p95_ms",
    "p99_ms",
    "max_ms",
    "stall_count",
    "worst_intervals_ms",
]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _validate_identity(identity: Any, label: str) -> None:
    _require(isinstance(identity, dict), f"{label} must be an object")
    _require(bool(identity.get("path")), f"{label}.path must be non-empty")
    _require(
        bool(SHA256.fullmatch(str(identity.get("sha256", "")))),
        f"{label}.sha256 must be a lowercase SHA-256",
    )


def _validate_profile(name: str, profile: Any) -> None:
    _require(isinstance(profile, dict), f"{name} must be an object")
    expected_mode = "FreshBoot" if name == "MORROWIND-FRESH" else "Snapshot"
    _require(profile.get("launch_mode") == expected_mode, f"{name} launch_mode mismatch")
    if name == "MORROWIND-FRESH":
        _require(
            profile.get("snapshot") is None,
            "MORROWIND-FRESH must not restore a snapshot",
        )
    else:
        _require(bool(profile.get("snapshot")), "MORROWIND-SNAPSHOT requires a snapshot")

    inputs = profile.get("inputs", {})
    _validate_identity(inputs.get("seed"), "seed")
    _validate_identity(inputs.get("disc"), "disc")
    _validate_identity(inputs.get("eeprom"), "eeprom")
    configs = inputs.get("configs", {})
    for renderer in ("VULKAN", "OPENGL"):
        _validate_identity(configs.get(renderer), f"configs.{renderer}")

    steps = profile.get("input_steps")
    _require(isinstance(steps, list) and steps, f"{name} input_steps must be non-empty")
    for index, step in enumerate(steps):
        label = f"{name} input_steps[{index}]"
        _require(isinstance(step, dict), f"{label} must be an object")
        _require(bool(step.get("button")), f"{label}.button must be non-empty")
        _require(
            bool(re.fullmatch(r"[A-Za-z0-9._-]+", str(step.get("capture_label", "")))),
            f"{label}.capture_label contains unsupported characters",
        )
        _require(
            isinstance(step.get("virtual_key"), int)
            and 1 <= step["virtual_key"] <= 254,
            f"{label}.virtual_key must be between 1 and 254",
        )
        _require(
            isinstance(step.get("delay_seconds"), int)
            and step["delay_seconds"] >= 0,
            f"{label}.delay_seconds must be a nonnegative integer",
        )
    _require(
        isinstance(profile.get("post_input_delay_seconds"), int)
        and profile["post_input_delay_seconds"] >= 0,
        f"{name} post_input_delay_seconds must be a nonnegative integer",
    )

    admission = profile.get("admission", {})
    _require(bool(admission.get("route")), f"{name} admission.route is required")
    for key in (
        "require_all_captures_accepted",
        "require_image_transition",
        "require_display_progression",
    ):
        _require(admission.get(key) is True, f"{name} admission.{key} must be true")

    measurement = profile.get("measurement", {})
    _require(
        measurement.get("metrics") == EXPECTED_METRICS,
        f"{name} must retain the cadence/tail metric set",
    )
    _require(
        isinstance(measurement.get("duration_seconds"), int)
        and measurement["duration_seconds"] >= 10,
        f"{name} measurement.duration_seconds must be at least 10",
    )
    _require(
        measurement.get("stall_threshold_ms") == 75,
        f"{name} stall threshold must remain 75 ms",
    )
    _require(
        measurement.get("worst_interval_count") == 10,
        f"{name} must retain ten worst intervals",
    )


def validate_manifest(manifest: Any) -> dict[str, Any]:
    _require(isinstance(manifest, dict), "manifest must be an object")
    _require(manifest.get("schema_version") == 1, "schema_version must be 1")
    _require(isinstance(manifest.get("example_only"), bool), "example_only must be a boolean")
    workloads = manifest.get("workloads")
    _require(isinstance(workloads, dict), "workloads must be an object")
    _require(
        set(workloads) == {"MORROWIND-FRESH", "MORROWIND-SNAPSHOT"},
        "workloads must define MORROWIND-FRESH and MORROWIND-SNAPSHOT",
    )
    for name in ("MORROWIND-FRESH", "MORROWIND-SNAPSHOT"):
        _validate_profile(name, workloads[name])
    fresh = workloads["MORROWIND-FRESH"]
    snapshot = workloads["MORROWIND-SNAPSHOT"]
    _require(fresh["inputs"] == snapshot["inputs"], "Morrowind gates must share inputs")
    _require(
        fresh["measurement"] == snapshot["measurement"],
        "Morrowind gates must share the measurement contract",
    )
    _require(
        fresh["admission"]["route"] != snapshot["admission"]["route"],
        "Morrowind gates must use distinct admission routes",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--print-plan", choices=("MORROWIND-FRESH", "MORROWIND-SNAPSHOT")
    )
    args = parser.parse_args()
    try:
        manifest = validate_manifest(
            json.loads(args.manifest.read_text(encoding="utf-8-sig"))
        )
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2
    if args.print_plan:
        print(json.dumps({"workload": args.print_plan, **manifest["workloads"][args.print_plan]}, indent=2))
    else:
        print(json.dumps({
            "status": "PASS",
            "host_launch_performed": False,
            "example_only": manifest.get("example_only", False),
        }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
