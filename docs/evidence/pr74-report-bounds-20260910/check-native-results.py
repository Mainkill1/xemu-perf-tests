#!/usr/bin/env python3
"""Verify the sanitized issue60 focused native result and its guest oracles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


EXPECTED_TESTS = [
    "report_query.zero_query",
    "report_query.single_boundary",
    "report_query.multiple_boundaries",
    "report_query.clear_boundary",
    "report_query.dma_target_switch",
    "report_query.dma_range_guard",
]


def complete(record: dict, sentinel_timestamp: int) -> bool:
    return record["timestamp"] != sentinel_timestamp and record["done"] == 0


def check_cell(cell: dict) -> None:
    assert cell["status"] == "passed"
    assert cell["outcome"] == "PASS"
    metadata = cell["metadata"]
    scenario = cell["scenario"]
    assert metadata["kind"] == "report_query_observations"
    assert metadata["scenario"] == scenario
    assert metadata["completion"]["completed"] is True
    records = metadata["records"]
    sentinel = records["b1"]["timestamp"]
    if scenario == "zero_query":
        assert complete(records["a0"], sentinel)
        assert records["a0"]["value"] == 0
    elif scenario == "single_boundary":
        assert complete(records["a0"], sentinel)
        assert records["a0"]["value"] != 0
    elif scenario == "multiple_boundaries":
        assert complete(records["a0"], sentinel)
        assert complete(records["a1"], sentinel)
        assert records["a0"]["value"] != 0
        assert records["a1"]["value"] == 2 * records["a0"]["value"]
    elif scenario == "clear_boundary":
        assert complete(records["a0"], sentinel)
        assert complete(records["a1"], sentinel)
        assert records["a0"]["value"] != 0
        assert records["a1"]["value"] == records["a0"]["value"]
    elif scenario == "dma_target_switch":
        assert complete(records["a0"], sentinel)
        assert complete(records["b0"], sentinel)
        assert records["a0"]["value"] != 0
        assert records["b0"]["value"] == records["a0"]["value"]
    elif scenario == "dma_range_guard":
        assert complete(records["a0"], sentinel)
        assert complete(records["b0"], sentinel)
        assert records["a0"]["value"] != 0
        assert records["a1"] == {
            "timestamp": 0xC7C7C7C7C7C7C7C7,
            "value": 0xC7C7C7C7,
            "done": 0xC7C7C7C7,
        }
        assert records["b0"]["value"] == 0
        assert metadata["range_canaries_intact"] is True
    else:
        raise AssertionError(f"unexpected scenario: {scenario}")
    if cell["backend"] == "vulkan":
        assert cell["validation_active"] is True
        assert cell["unique_vuid_count"] == 0
    configuration = cell["configuration"]
    assert configuration["backend"] == cell["backend"]
    assert configuration["surface_scale"] == 1
    assert configuration["vsync"] is False
    assert configuration["xbox_memory_megabytes"] == 64
    assert configuration["warmup_iterations"] == 0
    assert configuration["measurement_iterations_multiplier"] == 1
    assert configuration["completion_mode"] == "per_iteration"
    assert configuration["host_telemetry"] == "off"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path, nargs="?", default=Path("native-results.json"))
    args = parser.parse_args()
    data = json.loads(args.results.read_text())
    assert data["status"] == "PASSED"
    assert data["performance_acceptance"] is False
    assert data["candidate"]["source_commit"] == "05c149635b839e09bbe1c457f26f55ca4ad5be8b"
    assert data["candidate"]["source_tree"] == "f1479bd7e58371f8b03233b73bf239b93dd5a024"
    assert data["test_image"]["source_commit"] == "61012b4e702fbb46a02d813e71f2159a109a1c29"
    assert data["test_image"]["xiso_sha256"] == "6b2161f1b4abab94648f3fa0ca8da893092bab1b63d7e139a2358eb0319d05ac"
    assert data["test_image"]["catalog_sha256"] == "8298d8baa59144caa4fd8715c4709b86e40e47fb5f830539b853fefa2a9f1a29"
    assert data["host_identity"]["cpu"] == "AMD Ryzen 9 6900HX with Radeon Graphics"
    assert data["host_identity"]["gpu"] == "NVIDIA GeForce RTX 3070 Ti Laptop GPU"
    assert data["host_identity"]["gpu_driver"] == "581.95"
    cells = data["matrix"]["cells"]
    assert data["matrix"]["expected_cells"] == 12
    assert data["matrix"]["observed_cells"] == 12
    assert data["matrix"]["passed_cells"] == 12
    assert data["matrix"]["failed_cells"] == 0
    assert data["matrix"]["missing_cells"] == []
    assert [(cell["backend"], cell["test_id"]) for cell in cells] == [
        (backend, test_id)
        for backend in ("opengl", "vulkan")
        for test_id in EXPECTED_TESTS
    ]
    for cell in cells:
        check_cell(cell)
    assert data["missing_no_draw_control"]["status"] == "MISSING"
    assert data["gdb_diagnostic"]["status"] == "UNSUPPORTED_BY_EXISTING_RUNNER_SEAM"
    assert data["historical_baseline_only"]["rerun"] is False
    assert data["native_unit"]["result"]["target"] == "test-xbox-pgraph-reports"
    assert data["native_unit"]["result"]["status"] == "passed"
    assert data["native_unit"]["result"]["exit_code"] == 0
    assert data["native_unit"]["result"]["execution_count"] == 1
    assert data["native_unit"]["result"]["executable_sha256"] == data["candidate"]["native_unit_sha256"]
    assert data["final_cleanup"]["private_hdd_absent"] is True
    assert data["final_cleanup"]["remaining_owned_process_count"] == 0
    assert data["final_cleanup"]["error"] is None
    print("validated 12 focused candidate cells, renderer oracles, explicit gaps, and cleanup")


if __name__ == "__main__":
    main()
