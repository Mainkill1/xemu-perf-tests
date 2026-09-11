#!/usr/bin/env python3
"""Run deterministic Xbox guest tests through the installed xemu-test lifecycle."""

from __future__ import annotations

import argparse
import collections
import ctypes
import csv
import hashlib
import json
import logging
import os
import re
import shutil
import statistics
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from ctypes import wintypes

from xemutest import Environment, TestStatus, XemuTestBase
import xemutest.xemu_manager as xemu_manager_module
from xemutest.tests.test_xbe import TestXBE

from perf_lab_config import (
    load_experiment_config,
    merge_cli_environment,
    resolve_experiment_role,
)
from game_load_composite import (
    CROSS_TITLE_ALL_MASK,
    CROSS_TITLE_STAGE_ORDER,
    PRESETS as GAME_LOAD_LEGACY_PRESETS,
    install_profiles as install_game_load_profiles,
    interaction_analysis as analyze_game_load_interactions,
    validate_work as validate_game_load_work,
    validate_host_telemetry as validate_game_load_host_telemetry,
    work_from_records as game_load_work_from_records,
)
from xemu_exclusive_lock import XemuExclusiveLock, default_xemu_lock_path
from oracle_validation import (
    OracleValidationError,
    REGRESSION_ONLY,
    SameBackendNondeterminism,
    build_report as build_functional_hash_report,
    load_oracle,
    update_determinism_ledger,
    validate_against_oracle,
    write_json as write_oracle_json,
)
from window_focus import focus_process_window
from record_contract import (
    RecordContractError,
    derive_record_contract,
    discover_catalog,
    file_sha256 as catalog_file_sha256,
    load_catalog,
    validate_record_contract,
)


SUITE_ROOT = Path(__file__).resolve().parent
LAB_ROOT = SUITE_ROOT.parent
PYTHON_ROOT = SUITE_ROOT / "python313"
PRIVATE_ROOT = SUITE_ROOT / "private"
WORK_ROOT = SUITE_ROOT / "work"
XEMU_LOCK_PATH = default_xemu_lock_path()
RUNS_ROOT = LAB_ROOT / "runs" / "suite"
WINDOW_CAPTURE = SUITE_ROOT / "capture-xemu-window.ps1"
DEFAULT_ORACLE_LEDGER = RUNS_ROOT / "functional-hash-ledger.json"
XEMUTEST_DATA = PYTHON_ROOT / "Lib" / "site-packages" / "xemutest" / "data"
PERF_ISO = SUITE_ROOT / "assets" / "xemu-perf-tests" / "xemu-perf-tests_xiso.iso"
DEFAULT_XEMU = (
    LAB_ROOT
    / "builds"
    / "fc13b78060ff-clean-clean-speed-20260824T115334Z"
    / "xemu.exe"
)
DEFAULT_VULKAN_SDK_BIN = Path(r"C:\VulkanSDK\1.4.357.0\Bin")
DEFAULT_HOST_GDB = LAB_ROOT / "tools" / "msys64" / "ucrt64" / "bin" / "gdb.exe"
GUEST_EVIDENCE_LIVE = "live-markers"
GUEST_EVIDENCE_OUTPUT_ONLY = "output-only"
GUEST_EVIDENCE_CAPABILITIES = {
    GUEST_EVIDENCE_LIVE: "live-markers-fail-fast-v1",
    GUEST_EVIDENCE_OUTPUT_ONLY: "post-run-output-oracles-v1",
}
VULKAN_LAB_PERFLOG_ENV = "XEMU_LAB_PERFLOG"
VULKAN_LAB_PERFLOG_NAME = "vulkan-lab-perf.log"
VULKAN_LAB_TIMING_WARNING = (
    "Vulkan lab counters are diagnostic-only; every timing from this run is "
    "ineligible for a performance claim."
)
DIRTY_BUILD_TIMING_WARNING = (
    "SOURCE_STATE is not clean. This run is diagnostic-only and ineligible "
    "for performance claims."
)

PERF_RELEASE = {
    "repository": "https://github.com/abaire/xemu-perf-tests",
    "tag": "v2026-05-27_17-05-29-737267812",
    "commit": "4115d262c5e80d6b71234f8df65fa78c8ef15e12",
    "iso_sha256": "8418315a621d327f448b879db84085c07734f8ebf0993bc75155027b0abafe0e",
}

BOOSTED_VERTEX_STACK_PROFILE = "boosted-vertex-stack"
BOOSTED_VERTEX_STACK_RECORDS = (
    "GameLoadComposite::12-RepeatedDisplay-Boosted",
    "Vertex buffer allocation::XemuVertexRamDisjointSamePage",
)
BOOSTED_VERTEX_STACK_ARTIFACTS = {
    "baseline": {
        "SOURCE_SHA": "960a5d81e7ed5c3af9efa7c211f15ee2b9624b8b",
        "XEMU_SHA256": "b608c5a27993859c353f5d218b3228de380a87a26557c5b0ed436a65c9810b00",
    },
    "candidate": {
        "SOURCE_SHA": "4cd0981d78d9a4e03bca352b2061e848cafcc227",
        "XEMU_SHA256": "cebfeeee6b247d4538aca9ed5037d15172faae5048d73c954a74b576430a1842",
    },
}
BOOSTED_VERTEX_STACK_GUEST_COMMIT = "bde8e5fbebba"
BOOSTED_VERTEX_STACK_GUEST_SHA256 = (
    "a8ce3a595fa4cb688e1041398fb2f6fea255856928da84e325aa180d1da5a07a"
)
BOOSTED_VERTEX_STACK_TEST12_ITERATIONS = 8
BOOSTED_VERTEX_STACK_VERTEX_ITERATIONS = 10

PROFILES = {
    "busy-pfifo": {
        "BusyPfifo": {
            "PFIFOSaturation": {"skipped": False},
        },
    },
    "pfifo-packet-boundary": {
        "PFIFOPacketBoundary": {
            "pfifo.boundary-array-element16": {"skipped": False},
            "pfifo.boundary-array-element32": {"skipped": False},
            "pfifo.boundary-inline-array": {"skipped": False},
            "pfifo.incrementing-inline-fallback": {"skipped": False},
        },
    },
    "pfifo-array-elements": {
        "PFIFOArrayElements": {
            "pfifo.array-element16": {"skipped": False},
            "pfifo.array-element32": {"skipped": False},
            "pfifo.array-element-pgr2": {"skipped": False},
        },
    },
    "pfifo-array-elements-long": {
        "PFIFOArrayElements": {
            "pfifo.array-element16": {"skipped": False},
            "pfifo.array-element32": {"skipped": False},
        },
    },
    "pgraph-pattern-poll": {
        "BusyPfifo": {
            "PgraphPatternPolling": {"skipped": False},
        },
    },
    "cpu-fp-x87": {
        "CpuFloatingPoint": {
            "X87Scalar": {"skipped": False},
        },
    },
    "cpu-fp-sse": {
        "CpuFloatingPoint": {
            "SSEScalar": {"skipped": False},
        },
    },
    "cpu-tb": {
        "CpuTranslationBlocks": {"skipped": False},
    },
    "cpu-tb-direct": {
        "CpuTranslationBlocks": {
            "DirectLoop": {"skipped": False},
        },
    },
    "cpu-tb-indirect": {
        "CpuTranslationBlocks": {
            "IndirectDispatch": {"skipped": False},
        },
    },
    "cpu-tb-indirect-stress": {
        "CpuTranslationBlocks": {
            "IndirectDispatchStress": {"skipped": False},
        },
    },
    "fill-rate": {
        "FillRate": {"skipped": False},
    },
    "high-vertex": {
        "High vertex count": {"skipped": False},
    },
    "high-vertex-arrays": {
        "High vertex count": {
            "HighVtxCount-arrays": {"skipped": False},
        },
    },
    "high-vertex-inlinebuffers": {
        "High vertex count": {
            "HighVtxCount-inlinebuffers": {"skipped": False},
        },
    },
    "primitive-type": {
        "PrimitiveType": {"skipped": False},
    },
    "surface-to-texture": {
        "SurfaceRendering": {
            "SurfaceRendering": {"skipped": False},
        },
    },
    "surface-download": {
        "SurfaceRendering": {
            "XemuSurfaceDownloadPath": {"skipped": False},
        },
    },
    "surface-cpu-read-clean": {
        "SurfaceRendering": {
            "XemuCpuReadCleanSurface": {"skipped": False},
        },
    },
    "surface-cpu-read-after-gpu-write": {
        "SurfaceRendering": {
            "XemuCpuReadAfterGpuWrite": {"skipped": False},
        },
    },
    "surface-overlap-representative": {
        "SurfaceRendering": {
            "XemuOverlappingSurfaceChurnRepresentative": {"skipped": False},
        },
    },
    "surface-overlap-stress": {
        "SurfaceRendering": {
            "XemuOverlappingSurfaceChurnStress": {"skipped": False},
        },
    },
    "surface-full-clear-guard": {
        "SurfaceRendering": {
            "XemuFullClearElisionGuard": {"skipped": False},
        },
    },
    "surface-partial-channel-guard": {
        "SurfaceRendering": {
            "XemuPartialChannelClearGuard": {"skipped": False},
        },
    },
    "surface-list-002": {
        "SurfaceRendering": {
            "XemuSurfaceListLookup002": {"skipped": False},
        },
    },
    "surface-list-008": {
        "SurfaceRendering": {
            "XemuSurfaceListLookup008": {"skipped": False},
        },
    },
    "surface-list-032": {
        "SurfaceRendering": {
            "XemuSurfaceListLookup032": {"skipped": False},
        },
    },
    "surface-list-128": {
        "SurfaceRendering": {
            "XemuSurfaceListLookup128": {"skipped": False},
        },
    },
    "framebuffer-working-set-002": {
        "SurfaceRendering": {
            "XemuFramebufferWorkingSet002": {"skipped": False},
        },
    },
    "framebuffer-working-set-008": {
        "SurfaceRendering": {
            "XemuFramebufferWorkingSet008": {"skipped": False},
        },
    },
    "framebuffer-working-set-032": {
        "SurfaceRendering": {
            "XemuFramebufferWorkingSet032": {"skipped": False},
        },
    },
    "framebuffer-working-set-064": {
        "SurfaceRendering": {
            "XemuFramebufferWorkingSet064": {"skipped": False},
        },
    },
    "uniform-thrash": {
        "UniformThrash": {
            "UniformThrash": {"skipped": False},
        },
    },
    "tiny-draw": {
        "TinyDraw": {"skipped": False},
    },
    "tiny-draw-arrays-vsh": {
        "TinyDraw": {
            "TinyDraw-arrays-vsh": {"skipped": False},
        },
    },
    "tiny-draw-inlinearrays-vsh": {
        "TinyDraw": {
            "TinyDraw-inlinearrays-vsh": {"skipped": False},
        },
    },
    "vertex-buffer-allocation": {
        "Vertex buffer allocation": {"skipped": False},
    },
    "vertex-ram-reuse": {
        "Vertex buffer allocation": {
            "XemuVertexRamDisjointSamePage": {"skipped": False},
        },
    },
    "pgr2-vertex-two-ranges-one-page": {
        "Vertex buffer allocation": {
            "XemuPgr2VertexTwoRangesOneDirtyPage": {"skipped": False},
        },
    },
    "pgr2-rapid-scanout-transition": {
        "GameLoadComposite": {
            "13-Pgr2RapidScanoutTransition": {"skipped": False},
        },
    },
    "pgr2-rapid-scanout-transition-4x": {
        "GameLoadComposite": {
            "13-Pgr2RapidScanoutTransition": {"skipped": False},
        },
    },
    "morrowind-pvideo-cutscene": {
        "GameLoadComposite": {
            "14-MorrowindMovingPvideoCutscene": {"skipped": False},
        },
    },
    "morrowind-pvideo-cutscene-4x": {
        "GameLoadComposite": {
            "14-MorrowindMovingPvideoCutscene": {"skipped": False},
        },
    },
    "morrowind-textured-cutscene": {
        "GameLoadComposite": {
            "15-MorrowindMovingTexturedCutscene": {"skipped": False},
        },
    },
    "morrowind-textured-cutscene-4x": {
        "GameLoadComposite": {
            "15-MorrowindMovingTexturedCutscene": {"skipped": False},
        },
    },
    BOOSTED_VERTEX_STACK_PROFILE: {
        "GameLoadComposite": {
            "12-RepeatedDisplay-Boosted": {"skipped": False},
        },
        "Vertex buffer allocation": {
            "XemuVertexRamDisjointSamePage": {"skipped": False},
        },
    },
    "vertex-ram-after-inlinearrays": {
        "Vertex buffer allocation": {
            "MixedVtxAlloc-inlinearrays": {"skipped": False},
            "XemuVertexRamDisjointSamePage": {"skipped": False},
        },
    },
    "p0": {
        "BusyPfifo": {
            "PFIFOSaturation": {"skipped": False},
        },
        "SurfaceRendering": {
            "XemuSurfaceDownloadPath": {"skipped": False},
        },
        "TinyDraw": {"skipped": False},
        "UniformThrash": {
            "UniformThrash": {"skipped": False},
        },
    },
    "baseline": {
        "BusyPfifo": {"skipped": False},
        "CpuFloatingPoint": {"skipped": False},
        "CpuTranslationBlocks": {"skipped": False},
        "FillRate": {"skipped": False},
        "GameLoadComposite": {"skipped": False},
        "High vertex count": {"skipped": False},
        "PrimitiveType": {"skipped": False},
        "SurfaceRendering": {"skipped": False},
        "TinyDraw": {"skipped": False},
        "UniformThrash": {"skipped": False},
        "Vertex buffer allocation": {"skipped": False},
    },
}

install_game_load_profiles(PROFILES)

HOST_TELEMETRY_ASSERTIONS = {
    "surface-cpu-read-clean": {
        "counter_totals": {
            "SURF_CPU_ACCESS_CALLBACK": 409_600,
            "SURF_CPU_ACCESS_READ": 409_600,
            "SURF_CPU_ACCESS_WRITE": 0,
            "SURF_CPU_ACCESS_SURFACE_CHECK": 409_600,
            "SURF_CPU_ACCESS_SURFACE_MATCH": 409_600,
            "SURF_CPU_ACCESS_DIRTY": 0,
        },
    },
    "surface-cpu-read-after-gpu-write": {
        "counter_totals": {
            "SURF_DOWNLOAD": 20,
            "SURF_CPU_ACCESS_CALLBACK": 20_480,
            "SURF_CPU_ACCESS_READ": 20_480,
            "SURF_CPU_ACCESS_WRITE": 0,
            "SURF_CPU_ACCESS_SURFACE_CHECK": 20_480,
            "SURF_CPU_ACCESS_SURFACE_MATCH": 20_480,
            "SURF_CPU_ACCESS_DIRTY": 20,
        },
        "byte_totals": {
            "SURF_DOWNLOAD": {
                "logical": 81_920,
                "transferred": 81_920,
            },
        },
    },
    "surface-download": {
        "counter_totals": {
            "SURF_DOWNLOAD": 800,
        },
        "byte_totals": {
            "SURF_DOWNLOAD": {
                "logical": 52_428_800,
                "transferred": 52_428_800,
            },
        },
    },
    "surface-overlap-representative": {
        "counter_totals": {
            "CLEAR": 400,
            "SURF_DOWNLOAD_INCOMPATIBLE_REPLACEMENT": 200,
            "SURF_DOWNLOAD_OVERLAP_EVICTION": 200,
            "SURF_EVICT_FULL_CLEAR": 100,
            "SURF_UPLOAD_FULL_CLEAR": 400,
        },
    },
    "surface-overlap-stress": {
        "counter_totals": {
            "CLEAR": 800,
            "SURF_DOWNLOAD_INCOMPATIBLE_REPLACEMENT": 400,
            "SURF_DOWNLOAD_OVERLAP_EVICTION": 400,
            "SURF_EVICT_FULL_CLEAR": 200,
            "SURF_UPLOAD_FULL_CLEAR": 800,
        },
    },
    "surface-full-clear-guard": {
        "counter_totals": {
            "CLEAR": 200,
            "SURF_DOWNLOAD": 200,
            "SURF_DOWNLOAD_INCOMPATIBLE_REPLACEMENT": 200,
            "SURF_EVICT_COVERED": 100,
            "SURF_EVICT_FULL_CLEAR": 0,
            "SURF_EVICT_PARTIAL": 100,
            "SURF_UPLOAD_FULL_CLEAR": 100,
        },
    },
    "surface-partial-channel-guard": {
        "counter_totals": {
            "CLEAR": 200,
            "SURF_DOWNLOAD": 200,
            "SURF_DOWNLOAD_INCOMPATIBLE_REPLACEMENT": 200,
            "SURF_EVICT_COVERED": 100,
            "SURF_EVICT_FULL_CLEAR": 0,
            "SURF_EVICT_PARTIAL": 100,
            "SURF_UPLOAD_FULL_CLEAR": 100,
        },
    },
    "surface-list-002": {
        "counter_totals": {
            "CLEAR": 1_280,
            "SURF_LOOKUP_EXACT": 1_280,
            "SURF_LOOKUP_EXACT_ENTRIES": 1_920,
            "PIPELINE_BIND": 1_280,
            "PIPELINE_RENDERPASSES": 1_280,
            "FRAMEBUFFER_REQUEST": 1_280,
        },
    },
    "surface-list-008": {
        "counter_totals": {
            "CLEAR": 1_280,
            "SURF_LOOKUP_EXACT": 1_280,
            "SURF_LOOKUP_EXACT_ENTRIES": 5_760,
            "PIPELINE_BIND": 1_280,
            "PIPELINE_RENDERPASSES": 1_280,
            "FRAMEBUFFER_REQUEST": 1_280,
        },
    },
    "surface-list-032": {
        "counter_totals": {
            "CLEAR": 1_280,
            "SURF_LOOKUP_EXACT": 1_280,
            "SURF_LOOKUP_EXACT_ENTRIES": 21_120,
            "PIPELINE_BIND": 1_280,
            "PIPELINE_RENDERPASSES": 1_280,
            "FRAMEBUFFER_REQUEST": 1_280,
        },
    },
    "surface-list-128": {
        "counter_totals": {
            "CLEAR": 1_280,
            "SURF_LOOKUP_EXACT": 1_280,
            "SURF_LOOKUP_EXACT_ENTRIES": 82_560,
            "PIPELINE_BIND": 1_280,
            "PIPELINE_RENDERPASSES": 1_280,
            "FRAMEBUFFER_REQUEST": 1_280,
        },
    },
    "framebuffer-working-set-002": {
        "counter_totals": {
            "CLEAR": 1_280,
            "PIPELINE_BIND": 1_280,
            "PIPELINE_RENDERPASSES": 1_280,
            "FRAMEBUFFER_REQUEST": 1_280,
        },
    },
    "framebuffer-working-set-008": {
        "counter_totals": {
            "CLEAR": 1_280,
            "PIPELINE_BIND": 1_280,
            "PIPELINE_RENDERPASSES": 1_280,
            "FRAMEBUFFER_REQUEST": 1_280,
        },
    },
    "framebuffer-working-set-032": {
        "counter_totals": {
            "CLEAR": 1_280,
            "PIPELINE_BIND": 1_280,
            "PIPELINE_RENDERPASSES": 1_280,
            "FRAMEBUFFER_REQUEST": 1_280,
        },
    },
    "framebuffer-working-set-064": {
        "counter_totals": {
            "CLEAR": 1_280,
            "PIPELINE_BIND": 1_280,
            "PIPELINE_RENDERPASSES": 1_280,
            "FRAMEBUFFER_REQUEST": 1_280,
        },
    },
    "vertex-ram-reuse": {
        "counter_totals": {
            "DRAW_ARRAYS": 10_240,
            "VERTEX_RAM_SYNC_REQUEST": 20_480,
            "FINISH_NEED_BUFFER_SPACE": 0,
            "FINISH_FLUSH": 10,
        },
    },
}

PROFILE_CORRECTNESS_HASHES = {
    "pgraph-pattern-poll": {
        "BusyPfifo::PgraphPatternPolling": "386d0f085e98c325",
    },
    "cpu-fp-x87": {
        "CpuFloatingPoint::X87Scalar": "6962077c244da325",
    },
    "cpu-fp-sse": {
        "CpuFloatingPoint::SSEScalar": "6962077c244da325",
    },
    "cpu-tb": {
        "CpuTranslationBlocks::DirectLoop": "bd1fc9bf0c318325",
        "CpuTranslationBlocks::IndirectDispatch": "c0426cf669a02325",
    },
    "cpu-tb-direct": {
        "CpuTranslationBlocks::DirectLoop": "bd1fc9bf0c318325",
    },
    "cpu-tb-indirect": {
        "CpuTranslationBlocks::IndirectDispatch": "c0426cf669a02325",
    },
    "cpu-tb-indirect-stress": {
        "CpuTranslationBlocks::IndirectDispatchStress": "fbd507cb0c622325",
    },
    "busy-pfifo": {
        "BusyPfifo::PFIFOSaturation": "1508607624bb8506",
    },
    "high-vertex-inlinebuffers": {
        "High vertex count::HighVtxCount-inlinebuffers": "a27c67890c2d9083",
    },
    "surface-to-texture": {
        "SurfaceRendering::SurfaceRendering": "42459952797c47fa",
    },
    "surface-download": {
        "SurfaceRendering::XemuSurfaceDownloadPath": "64a30332bf7ebd84",
    },
    "uniform-thrash": {
        "UniformThrash::UniformThrash": "09eb5907ef624c25",
    },
    "tiny-draw-arrays-vsh": {
        "TinyDraw::TinyDraw-arrays-vsh": "acf025546cf667b5",
    },
    "tiny-draw-inlinearrays-vsh": {
        "TinyDraw::TinyDraw-inlinearrays-vsh": "acf025546cf667b5",
    },
    "surface-cpu-read-clean": {
        "SurfaceRendering::XemuCpuReadCleanSurface": "fb905938a70d2325",
    },
    "surface-cpu-read-after-gpu-write": {
        "SurfaceRendering::XemuCpuReadAfterGpuWrite": "7f41f02dc2a96325",
    },
    "surface-overlap-representative": {
        "SurfaceRendering::XemuOverlappingSurfaceChurnRepresentative":
            "6f4b1c962fd7a325",
    },
    "surface-overlap-stress": {
        "SurfaceRendering::XemuOverlappingSurfaceChurnStress":
            "6f4b1c962fd7a325",
    },
    "surface-full-clear-guard": {
        "SurfaceRendering::XemuFullClearElisionGuard": "0fb44e8c33a6e325",
    },
    "surface-partial-channel-guard": {
        "SurfaceRendering::XemuPartialChannelClearGuard": "40666238279fc325",
    },
    "surface-list-002": {
        "SurfaceRendering::XemuSurfaceListLookup002": "fa475bc695046525",
    },
    "surface-list-008": {
        "SurfaceRendering::XemuSurfaceListLookup008": "477aabc5cec335a5",
    },
    "surface-list-032": {
        "SurfaceRendering::XemuSurfaceListLookup032": "fad9c32ebfd34125",
    },
    "surface-list-128": {
        "SurfaceRendering::XemuSurfaceListLookup128": "fad9c32ebfd34125",
    },
    "framebuffer-working-set-002": {
        "SurfaceRendering::XemuFramebufferWorkingSet002": "fa475bc695046525",
    },
    "framebuffer-working-set-008": {
        "SurfaceRendering::XemuFramebufferWorkingSet008": "784f1cfba4b12d25",
    },
    "framebuffer-working-set-032": {
        "SurfaceRendering::XemuFramebufferWorkingSet032": "a47268657a2de925",
    },
    "framebuffer-working-set-064": {
        "SurfaceRendering::XemuFramebufferWorkingSet064": "a47268657a2de925",
    },
    "vertex-ram-reuse": {
        "Vertex buffer allocation::XemuVertexRamDisjointSamePage":
            "fdcd25a37910bb25",
    },
    "pgr2-vertex-two-ranges-one-page": {
        "Vertex buffer allocation::XemuPgr2VertexTwoRangesOneDirtyPage":
            "542cb51ab5730485",
    },
    "pgr2-rapid-scanout-transition": {
        "GameLoadComposite::13-Pgr2RapidScanoutTransition":
            "77d4e0482a1aa325",
    },
    "pgr2-rapid-scanout-transition-4x": {
        "GameLoadComposite::13-Pgr2RapidScanoutTransition":
            "853df802e501a325",
    },
    "morrowind-pvideo-cutscene": {
        "GameLoadComposite::14-MorrowindMovingPvideoCutscene":
            "a05a4cbd63350325",
    },
    "morrowind-pvideo-cutscene-4x": {
        "GameLoadComposite::14-MorrowindMovingPvideoCutscene":
            "a05a4cbd63350325",
    },
    "morrowind-textured-cutscene": {
        "GameLoadComposite::15-MorrowindMovingTexturedCutscene":
            "058fdf8e96a905e9",
    },
}
PROFILE_BACKEND_CORRECTNESS_HASHES = {
    ("morrowind-textured-cutscene-4x", "vulkan"): {
        "GameLoadComposite::15-MorrowindMovingTexturedCutscene":
            "bda631c633302166",
    },
    ("morrowind-textured-cutscene-4x", "opengl"): {
        "GameLoadComposite::15-MorrowindMovingTexturedCutscene":
            "895f94315ce5bdd4",
    },
}
# Populate only from the canonical pre-overlay hold. Older captures included
# variable timing text and are evidence, not valid display-image goldens.
PROFILE_HELD_FRAME_SHA256S = {}
PROFILE_CORRECTNESS_HASH_PROVENANCE = REGRESSION_ONLY
HELD_FRAME_SUPPORTED_SELECTIONS = frozenset(
    {
        "GameLoadComposite::09-CrossTitleHotpath",
        "GameLoadComposite::13-Pgr2RapidScanoutTransition",
        "GameLoadComposite::14-MorrowindMovingPvideoCutscene",
        "GameLoadComposite::15-MorrowindMovingTexturedCutscene",
        "pgr2-rapid-scanout-transition",
        "pgr2-rapid-scanout-transition-4x",
        "morrowind-pvideo-cutscene",
        "morrowind-pvideo-cutscene-4x",
        "morrowind-textured-cutscene",
        "morrowind-textured-cutscene-4x",
    }
)

PROFILE_RECORD_CONTRACTS = {
    "pgraph-pattern-poll": {
        "name": "BusyPfifo::PgraphPatternPolling",
        "iterations": 1,
        "raw_result_count": 1,
        "minimum_total_us": 15_000_000,
    },
    "cpu-fp-x87": {
        "name": "CpuFloatingPoint::X87Scalar",
        "iterations": 10,
        "raw_result_count": 10,
        "minimum_total_us": 15_000_000,
    },
    "cpu-fp-sse": {
        "name": "CpuFloatingPoint::SSEScalar",
        "iterations": 10,
        "raw_result_count": 10,
        "minimum_total_us": 15_000_000,
    },
    "cpu-tb-direct": {
        "name": "CpuTranslationBlocks::DirectLoop",
        "iterations": 10,
        "raw_result_count": 10,
    },
    "cpu-tb-indirect": {
        "name": "CpuTranslationBlocks::IndirectDispatch",
        "iterations": 10,
        "raw_result_count": 10,
    },
    "cpu-tb-indirect-stress": {
        "name": "CpuTranslationBlocks::IndirectDispatchStress",
        "iterations": 10,
        "raw_result_count": 10,
        "minimum_total_us": 15_000_000,
    },
    "uniform-thrash": {
        "name": "UniformThrash::UniformThrash",
        "iterations": 10,
        "raw_result_count": 10,
    },
    "tiny-draw-arrays-vsh": {
        "name": "TinyDraw::TinyDraw-arrays-vsh",
        "iterations": 10,
        "raw_result_count": 10,
    },
    "tiny-draw-inlinearrays-vsh": {
        "name": "TinyDraw::TinyDraw-inlinearrays-vsh",
        "iterations": 10,
        "raw_result_count": 10,
    },
    "vertex-ram-reuse": {
        "name": "Vertex buffer allocation::XemuVertexRamDisjointSamePage",
        "iterations": 10,
        "raw_result_count": 10,
    },
    "pgr2-vertex-two-ranges-one-page": {
        "name": "Vertex buffer allocation::XemuPgr2VertexTwoRangesOneDirtyPage",
        "iterations": 120,
        "raw_result_count": 120,
        "minimum_total_us": 1_000_000,
    },
    "pgr2-rapid-scanout-transition": {
        "name": "GameLoadComposite::13-Pgr2RapidScanoutTransition",
        "iterations": 120,
        "raw_result_count": 120,
        "minimum_total_us": 3_000_000,
    },
    "pgr2-rapid-scanout-transition-4x": {
        "name": "GameLoadComposite::13-Pgr2RapidScanoutTransition",
        "iterations": 120,
        "raw_result_count": 120,
        "minimum_total_us": 3_000_000,
    },
    "morrowind-pvideo-cutscene": {
        "name": "GameLoadComposite::14-MorrowindMovingPvideoCutscene",
        "iterations": 120,
        "raw_result_count": 120,
        "minimum_total_us": 1_000_000,
    },
    "morrowind-pvideo-cutscene-4x": {
        "name": "GameLoadComposite::14-MorrowindMovingPvideoCutscene",
        "iterations": 120,
        "raw_result_count": 120,
        "minimum_total_us": 1_000_000,
    },
    "morrowind-textured-cutscene": {
        "name": "GameLoadComposite::15-MorrowindMovingTexturedCutscene",
        "iterations": 120,
        "raw_result_count": 120,
        "minimum_total_us": 1_000_000,
    },
    "morrowind-textured-cutscene-4x": {
        "name": "GameLoadComposite::15-MorrowindMovingTexturedCutscene",
        "iterations": 120,
        "raw_result_count": 120,
        "minimum_total_us": 1_000_000,
    },
}

PROFILE_REQUIRED_SCALES = {
    "pgr2-rapid-scanout-transition": 1,
    "pgr2-rapid-scanout-transition-4x": 4,
    "morrowind-pvideo-cutscene": 1,
    "morrowind-pvideo-cutscene-4x": 4,
    "morrowind-textured-cutscene": 1,
    "morrowind-textured-cutscene-4x": 4,
}

PROFILE_MULTI_RECORD_CONTRACTS = {
    "vertex-ram-after-inlinearrays": (
        {
            "name": "Vertex buffer allocation::MixedVtxAlloc-inlinearrays",
            "iterations": 10,
            "raw_result_count": 10,
            # This is deliberately scoped to this exact two-test profile and
            # order. MixedVtxAlloc remains non-universal in broad selections.
            "framebuffer_fnv1a64": "c4675a9e2c6a72f5",
        },
        {
            "name": "Vertex buffer allocation::XemuVertexRamDisjointSamePage",
            "iterations": 10,
            "raw_result_count": 10,
            "framebuffer_fnv1a64": "fdcd25a37910bb25",
        },
    ),
    BOOSTED_VERTEX_STACK_PROFILE: (
        {
            "name": BOOSTED_VERTEX_STACK_RECORDS[0],
            "iterations": BOOSTED_VERTEX_STACK_TEST12_ITERATIONS,
            "raw_result_count": BOOSTED_VERTEX_STACK_TEST12_ITERATIONS,
        },
        {
            "name": BOOSTED_VERTEX_STACK_RECORDS[1],
            "iterations": BOOSTED_VERTEX_STACK_VERTEX_ITERATIONS,
            "raw_result_count": BOOSTED_VERTEX_STACK_VERTEX_ITERATIONS,
            "framebuffer_fnv1a64": "fdcd25a37910bb25",
        },
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _xemu_process_running() -> bool:
    if os.name == "nt":
        result = subprocess.run(
            ["tasklist.exe", "/FI", "IMAGENAME eq xemu.exe", "/NH"],
            capture_output=True,
            text=True,
            check=False,
        )
        return "xemu.exe" in result.stdout.lower()

    result = subprocess.run(
        ["ps", "-eo", "comm="],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False
    return any(
        line.strip() in ("qemu-system-i386", "xemu")
        for line in result.stdout.splitlines()
    )


def ensure_no_running_xemu(
    timeout_seconds: float = 0.0, poll_interval_seconds: float = 0.25
) -> None:
    """Wait briefly for the previous xemu shutdown instead of racing it."""

    deadline = time.monotonic() + timeout_seconds
    while True:
        if not _xemu_process_running():
            return
        if time.monotonic() >= deadline:
            raise RuntimeError(
                "xemu is still running; wait for prior shutdown before starting the suite"
            )
        time.sleep(poll_interval_seconds)


class _FileTime(ctypes.Structure):
    _fields_ = (("low", wintypes.DWORD), ("high", wintypes.DWORD))

    def ticks(self) -> int:
        return (self.high << 32) | self.low


class HostGDBSampler:
    """Capture diagnostic host stacks only while the guest measurement runs."""

    def __init__(
        self,
        gdb_path: Path,
        xemu_path: Path,
        marker_path: Path,
        output_dir: Path,
        sample_count: int,
    ):
        self.gdb_path = gdb_path
        self.xemu_path = xemu_path
        self.marker_path = marker_path
        self.output_dir = output_dir
        self.sample_count = sample_count
        self.thread: threading.Thread | None = None
        self.error: str | None = None
        self.completed_samples = 0

    def start(self, process: subprocess.Popen) -> None:
        self.thread = threading.Thread(
            target=self._run,
            args=(process,),
            name="xemu-host-gdb-sampler",
            daemon=True,
        )
        self.thread.start()

    def _marker_text(self) -> str:
        try:
            return self.marker_path.read_text(
                encoding="ascii", errors="replace"
            )
        except FileNotFoundError:
            return ""

    def _run(self, process: subprocess.Popen) -> None:
        try:
            self.output_dir.mkdir(parents=True, exist_ok=False)
            deadline = time.monotonic() + 120
            while process.poll() is None and time.monotonic() < deadline:
                if "F0" in self._marker_text().splitlines():
                    break
                time.sleep(0.01)
            else:
                raise RuntimeError(
                    "guest MEASURE_BEGIN marker was not observed within 120 seconds"
                )

            # Let the guest leave the marker I/O helper before taking the
            # first sample. Without this delay the first backtrace mostly
            # describes marker delivery rather than the measured workload.
            time.sleep(0.05)

            xemu_gdb_path = str(self.xemu_path).replace("\\", "/")
            for index in range(1, self.sample_count + 1):
                if process.poll() is not None:
                    break
                if "F1" in self._marker_text().splitlines():
                    break
                command = [
                    str(self.gdb_path),
                    "-q",
                    "-nx",
                    "-batch",
                    "-ex",
                    "set pagination off",
                    "-ex",
                    "set print thread-events off",
                    "-ex",
                    f"file {xemu_gdb_path}",
                    "-ex",
                    f"attach {process.pid}",
                    "-ex",
                    "info threads",
                    "-ex",
                    "thread apply all bt 32",
                    "-ex",
                    "detach",
                    "-ex",
                    "quit",
                ]
                result = subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    errors="replace",
                    timeout=30,
                    check=False,
                )
                sample_path = self.output_dir / f"sample-{index:03d}.txt"
                sample_path.write_text(result.stdout, encoding="utf-8")
                if result.returncode != 0:
                    raise RuntimeError(
                        f"host GDB sample {index} exited with {result.returncode}; "
                        f"see {sample_path}"
                    )
                self.completed_samples += 1
                time.sleep(0.01)

            if not self.completed_samples:
                raise RuntimeError("host GDB captured no measurement-phase stacks")
        except Exception as exc:
            self.error = str(exc)

    def finish(self) -> dict:
        if self.thread is None:
            raise RuntimeError("host GDB sampler was not started")
        self.thread.join(timeout=45)
        if self.thread.is_alive():
            raise RuntimeError("host GDB sampler did not stop")
        summary = {
            "requested_samples": self.sample_count,
            "completed_samples": self.completed_samples,
            "marker_path": str(self.marker_path),
            "gdb_path": str(self.gdb_path),
            "error": self.error,
        }
        (self.output_dir / "summary.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )
        if self.error:
            raise RuntimeError(self.error)
        return summary


class GuestValidationFailed(RuntimeError):
    """A guest assertion or event-protocol failure observed while xemu runs."""


class LiveMarkerEvidenceError(RuntimeError):
    """The perf child did not prove the live marker device was active."""


class GuestEventWatcher:
    """Tail xemu's append-only guest event stream and stop failed guests early.

    The marker receiver deliberately shares this file with the legacy F0/F1/F2
    text markers. Complete F0/F1 lines become boundary evidence and F2 is
    retained if supplied. Only complete JSONL objects are interpreted as
    events; partial writes remain buffered without losing later events. Every
    JSON event is copied to a durable JSONL evidence file.
    """

    FAILURE_EVENTS = frozenset(("FAIL", "PROTOCOL_ERROR"))
    TERMINAL_EVENTS = frozenset(("PASS", "FAIL"))
    WORKLOAD_PROTOCOL_EVENTS = frozenset(("CONTEXT", "HEARTBEAT", "PASS", "FAIL"))

    def __init__(
        self,
        marker_path: Path,
        event_log_path: Path,
        failure_path: Path,
        terminate_process_tree,
        poll_interval_seconds: float = 0.02,
        marker_evidence_path: Path | None = None,
    ):
        self.marker_path = marker_path
        self.event_log_path = event_log_path
        self.failure_path = failure_path
        self.terminate_process_tree = terminate_process_tree
        self.poll_interval_seconds = poll_interval_seconds
        self.marker_evidence_path = marker_evidence_path
        self.thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.terminal_event = threading.Event()
        self.terminal_event_type: str | None = None
        self._failure_lock = threading.Lock()
        self._offset = 0
        self._partial = b""
        self._file_identity: tuple[int, int] | None = None
        self.event_count = 0
        self.event_types: list[str] = []
        self.event_records: list[dict] = []
        self.marker_file_observed = False
        self.boundary_sequence: list[str] = []
        self.other_markers: list[str] = []
        self.failure: dict | None = None

    def start(self) -> None:
        if self.thread is not None:
            return
        self.thread = threading.Thread(
            target=self._run,
            name="xemu-guest-event-watcher",
            daemon=True,
        )
        self.thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            self.poll_once()
            self._stop.wait(self.poll_interval_seconds)
        self.poll_once()

    def poll_once(self) -> None:
        """Consume complete lines currently available; safe before file creation."""

        try:
            with self.marker_path.open("rb") as source:
                stat = os.fstat(source.fileno())
                identity = (stat.st_dev, stat.st_ino)
                size = source.seek(0, os.SEEK_END)
                # A new xemu run can recreate/truncate the file after the
                # watcher starts. Do not retain a stale partial line in that
                # case, and restart at its beginning.
                if self._file_identity not in (None, identity) or size < self._offset:
                    self._offset = 0
                    self._partial = b""
                self._file_identity = identity
                self.marker_file_observed = True
                source.seek(self._offset)
                chunk = source.read()
                self._offset = source.tell()
        except OSError:
            # The receiver creates this artifact asynchronously. Retrying on
            # transient sharing/deletion races is safer than treating an
            # incomplete stream as a guest protocol failure.
            return

        if not chunk:
            return
        lines = (self._partial + chunk).split(b"\n")
        self._partial = lines.pop()
        for raw_line in lines:
            if raw_line.endswith(b"\r"):
                raw_line = raw_line[:-1]
            if not raw_line:
                continue
            if raw_line in (b"F0", b"F1"):
                self.boundary_sequence.append(raw_line.decode("ascii"))
                continue
            if raw_line == b"F2":
                self.other_markers.append("F2")
                continue
            try:
                event = json.loads(raw_line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                # Legacy F0/F1/F2 marker lines and malformed non-event text
                # are preserved in marker_path but are not JSON protocol
                # events. A host-generated PROTOCOL_ERROR is authoritative.
                continue
            if isinstance(event, dict):
                self._record_event(event)

    def _record_event(self, event: dict) -> None:
        self.event_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.event_log_path.open("a", encoding="utf-8") as destination:
            destination.write(json.dumps(event, sort_keys=True) + "\n")
            destination.flush()
            os.fsync(destination.fileno())
        self.event_count += 1
        event_type = event.get("event")
        if isinstance(event_type, str):
            self.event_types.append(event_type)
        self.event_records.append(
            {
                "event": event_type,
                "sequence": event.get("sequence"),
            }
        )
        if isinstance(event_type, str) and event_type in self.TERMINAL_EVENTS:
            self.terminal_event_type = event_type
            self.terminal_event.set()
        if isinstance(event_type, str) and event_type in self.FAILURE_EVENTS:
            self._fail(event)

    @staticmethod
    def _failure_message(event: dict) -> str:
        return (
            "guest validation failed immediately: "
            f"event={event.get('event')!r} phase={event.get('phase')!r} "
            f"assertion={event.get('assertion')!r} "
            f"expected={event.get('expected')!r} actual={event.get('actual')!r} "
            f"final_state={event.get('final_state')!r}"
        )

    def _fail(self, event: dict) -> None:
        with self._failure_lock:
            if self.failure is not None:
                return
            failure = {
                "schema_version": 1,
                "status": "GUEST_VALIDATION_FAILED",
                "message": self._failure_message(event),
                "observed_monotonic_ns": time.monotonic_ns(),
                "marker_path": str(self.marker_path),
                "event": event,
            }
            self.failure = failure
            self.failure_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.failure_path.with_name(
                f".{self.failure_path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
            )
            with temporary.open("w", encoding="utf-8") as destination:
                destination.write(json.dumps(failure, indent=2, sort_keys=True) + "\n")
                destination.flush()
                os.fsync(destination.fileno())
            os.replace(temporary, self.failure_path)
            print(failure["message"], flush=True)
            # The guest assertion path intentionally waits forever. Kill its
            # complete xemu process tree after durable evidence is on disk.
            self.terminate_process_tree()

    def finish(self) -> dict:
        self._stop.set()
        if self.thread is not None:
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                raise RuntimeError("guest event watcher did not stop")
        else:
            self.poll_once()
        evidence = {
            "schema_version": 1,
            "marker_path": str(self.marker_path),
            "event_log_path": str(self.event_log_path),
            "marker_file_observed": self.marker_file_observed,
            "boundary_sequence": self.boundary_sequence,
            "completed_boundary_count": self.boundary_sequence.count("F1"),
            "other_markers": self.other_markers,
            "event_count": self.event_count,
            "event_types": self.event_types,
            "event_records": self.event_records,
            "failure_path": str(self.failure_path) if self.failure is not None else None,
            "failure": self.failure,
        }
        if self.marker_evidence_path is not None:
            self.marker_evidence_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.marker_evidence_path.with_name(
                f".{self.marker_evidence_path.name}.{os.getpid()}.tmp"
            )
            with temporary.open("w", encoding="utf-8") as destination:
                destination.write(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
                destination.flush()
                os.fsync(destination.fileno())
            os.replace(temporary, self.marker_evidence_path)
            evidence["marker_evidence_path"] = str(self.marker_evidence_path)
        return evidence


def validate_live_marker_evidence(evidence: dict | None) -> dict:
    """Require one or more complete live F0/F1 marker boundaries for perf."""

    if not isinstance(evidence, dict):
        raise LiveMarkerEvidenceError("perf run produced no live marker evidence")
    if evidence.get("marker_file_observed") is not True:
        raise LiveMarkerEvidenceError(
            "xemu did not create the requested live marker path; marker capability is unavailable"
        )
    sequence = evidence.get("boundary_sequence")
    if not isinstance(sequence, list) or not sequence:
        raise LiveMarkerEvidenceError(
            "live marker path contained no F0/F1 boundaries; marker capability is unavailable"
        )
    expected = "F0"
    completed = 0
    for index, marker in enumerate(sequence):
        if marker != expected:
            raise LiveMarkerEvidenceError(
                "live marker boundary order is invalid at index "
                f"{index}: expected {expected}, got {marker!r}"
            )
        if marker == "F1":
            completed += 1
        expected = "F1" if expected == "F0" else "F0"
    if expected != "F0" or completed == 0:
        raise LiveMarkerEvidenceError(
            "live marker stream ended without a completed F0/F1 boundary"
        )
    event_count = evidence.get("event_count")
    if not isinstance(event_count, int) or isinstance(event_count, bool) or event_count < 0:
        raise LiveMarkerEvidenceError("live marker evidence has an invalid guest event count")
    event_records = evidence.get("event_records")
    if not isinstance(event_records, list) or len(event_records) != event_count:
        raise LiveMarkerEvidenceError("live marker evidence has invalid guest event records")
    previous_sequence: int | None = None
    workload_protocol_events: list[str] = []
    for index, record in enumerate(event_records):
        if not isinstance(record, dict):
            raise LiveMarkerEvidenceError(
                f"live marker evidence has malformed guest event at index {index}"
            )
        event_type = record.get("event")
        if (
            isinstance(event_type, str)
            and event_type in GuestEventWatcher.WORKLOAD_PROTOCOL_EVENTS
        ):
            workload_protocol_events.append(event_type)
        sequence = record.get("sequence")
        if sequence is None:
            continue
        if not isinstance(sequence, int) or isinstance(sequence, bool):
            raise LiveMarkerEvidenceError(
                f"guest event sequence is invalid at index {index}: {sequence!r}"
            )
        if previous_sequence is not None and sequence <= previous_sequence:
            raise LiveMarkerEvidenceError(
                "guest event sequence is not strictly monotonic at index "
                f"{index}: {previous_sequence} then {sequence}"
            )
        previous_sequence = sequence
    if (
        workload_protocol_events
        and workload_protocol_events[-1] not in GuestEventWatcher.TERMINAL_EVENTS
    ):
        raise LiveMarkerEvidenceError(
            "guest workload event stream has no terminal PASS/FAIL event"
        )
    return evidence


def assess_live_marker_evidence(
    evidence: dict | None, *, allow_missing_live_markers: bool
) -> dict:
    """Validate markers or explicitly waive only their timing evidence."""

    try:
        validate_live_marker_evidence(evidence)
    except LiveMarkerEvidenceError as exc:
        if not allow_missing_live_markers:
            raise
        return {
            "compatibility_mode_requested": True,
            "marker_waiver_applied": True,
            "live_marker_evidence_validated": False,
            "validation_error": str(exc),
            "timing_limitation": (
                "Live markers are unavailable; timing is not PR-grade performance evidence."
            ),
            "correctness_limitation": (
                "Record count, guest results, functional hashes, and renderer validation "
                "remain mandatory."
            ),
        }
    return {
        "compatibility_mode_requested": allow_missing_live_markers,
        "marker_waiver_applied": False,
        "live_marker_evidence_validated": True,
        "validation_error": None,
        "timing_limitation": None,
        "correctness_limitation": None,
    }


def validate_missing_live_marker_compatibility_request(
    allow_missing_live_markers: bool,
    mode: str,
    host_telemetry: str,
    host_gdb_samples: int,
) -> None:
    """Keep the compatibility mode away from marker-dependent diagnostics."""

    if not allow_missing_live_markers:
        return
    if mode != "perf":
        raise ValueError("--allow-missing-live-markers requires --mode perf")
    if host_telemetry != "off":
        raise ValueError(
            "--allow-missing-live-markers requires --host-telemetry off"
        )
    if host_gdb_samples:
        raise ValueError(
            "--allow-missing-live-markers cannot be used with --host-gdb-samples"
        )


class XemuProcessObserver:
    """Capture xemu's retained process handle without changing xemu-test."""

    def __init__(self, xemu_path: Path, on_start=None, extra_args=()):
        self.xemu_path = xemu_path
        self.on_start = on_start
        self.extra_args = tuple(extra_args)
        self.process: subprocess.Popen | None = None
        self.launch_evidence: dict | None = None
        self._subprocess_module = xemu_manager_module.subprocess
        self.proxy = SimpleNamespace(
            Popen=self._popen,
            STDOUT=self._subprocess_module.STDOUT,
        )

    def _popen(self, args, *popen_args, **popen_kwargs):
        is_xemu = bool(args and Path(args[0]).resolve() == self.xemu_path)
        launch_args = list(args)
        if is_xemu:
            launch_args.extend(self.extra_args)
        process = self._subprocess_module.Popen(
            launch_args, *popen_args, **popen_kwargs
        )
        if is_xemu:
            self.process = process
            actual_path = self._query_process_image_path(process)
            if actual_path != self.xemu_path:
                self.terminate_process_tree()
                raise RuntimeError(
                    "launched xemu PID image mismatch: "
                    f"expected {self.xemu_path}, got {actual_path}"
                )
            expected_hash = sha256(self.xemu_path)
            actual_hash = sha256(actual_path)
            if actual_hash != expected_hash:
                self.terminate_process_tree()
                raise RuntimeError(
                    "launched xemu PID executable hash mismatch: "
                    f"expected {expected_hash}, got {actual_hash}"
                )
            self.launch_evidence = {
                "pid": process.pid,
                "expected_path": str(self.xemu_path),
                "actual_path": str(actual_path),
                "expected_sha256": expected_hash,
                "actual_sha256": actual_hash,
                "arguments": [str(value) for value in launch_args],
                "validated": True,
            }
            if self.on_start:
                self.on_start(process)
        return process

    def _query_process_image_path(self, process: subprocess.Popen) -> Path:
        if os.name != "nt":
            return self.xemu_path
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        query = ctypes.windll.kernel32.QueryFullProcessImageNameW
        query.argtypes = (
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        )
        query.restype = wintypes.BOOL
        if not query(
            wintypes.HANDLE(process._handle), 0, buffer, ctypes.byref(size)
        ):
            raise ctypes.WinError()
        return Path(buffer.value).resolve()

    def __enter__(self):
        xemu_manager_module.subprocess = self.proxy
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        xemu_manager_module.subprocess = self._subprocess_module

    def terminate_process_tree(self) -> None:
        """Terminate the observed xemu and children after a guest FAIL frame."""

        if self.process is None or self.process.poll() is not None:
            return
        if os.name == "nt":
            subprocess.run(
                ["taskkill.exe", "/PID", str(self.process.pid), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            # Unit tests run on non-Windows hosts; xemu itself is Windows-only
            # in this suite, but retaining this fallback keeps the observer
            # safe for test doubles.
            self.process.terminate()

    def metrics(self) -> dict | None:
        if os.name != "nt" or self.process is None:
            return None

        creation = _FileTime()
        exit_time = _FileTime()
        kernel = _FileTime()
        user = _FileTime()
        get_process_times = ctypes.windll.kernel32.GetProcessTimes
        get_process_times.argtypes = (
            wintypes.HANDLE,
            ctypes.POINTER(_FileTime),
            ctypes.POINTER(_FileTime),
            ctypes.POINTER(_FileTime),
            ctypes.POINTER(_FileTime),
        )
        get_process_times.restype = wintypes.BOOL
        if not get_process_times(
            wintypes.HANDLE(self.process._handle),
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            raise ctypes.WinError()

        ticks_per_second = 10_000_000
        user_seconds = user.ticks() / ticks_per_second
        kernel_seconds = kernel.ticks() / ticks_per_second
        wall_seconds = (exit_time.ticks() - creation.ticks()) / ticks_per_second
        return {
            "pid": self.process.pid,
            "exit_code": self.process.returncode,
            "wall_seconds": wall_seconds,
            "user_seconds": user_seconds,
            "kernel_seconds": kernel_seconds,
            "cpu_seconds": user_seconds + kernel_seconds,
            "average_logical_cores": (
                (user_seconds + kernel_seconds) / wall_seconds
                if wall_seconds > 0
                else None
            ),
            "launch": self.launch_evidence,
        }


class HeldFrameCapture:
    """Capture a completed guest frame and prove the timed guest exit is clean."""

    def __init__(
        self,
        watcher: GuestEventWatcher,
        output_path: Path,
        evidence_path: Path,
        terminate_process_tree,
        terminal_timeout_seconds: float,
        reference_path: Path | None = None,
    ) -> None:
        self.watcher = watcher
        self.output_path = output_path
        self.evidence_path = evidence_path
        self.capture_metadata_path = evidence_path.with_name("held-frame-window.json")
        self.terminate_process_tree = terminate_process_tree
        self.terminal_timeout_seconds = terminal_timeout_seconds
        self.reference_path = reference_path
        self.process: subprocess.Popen | None = None
        self.thread: threading.Thread | None = None
        self.error: str | None = None
        self.evidence: dict | None = None

    def start(self, process: subprocess.Popen) -> None:
        self.process = process
        self.thread = threading.Thread(
            target=self._run,
            name="xemu-held-frame-capture",
            daemon=True,
        )
        self.thread.start()

    def _write_evidence(self, payload: dict) -> None:
        self.evidence_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.evidence_path.with_name(
            f".{self.evidence_path.name}.{os.getpid()}.tmp"
        )
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.evidence_path)

    def _run(self) -> None:
        try:
            if not self.watcher.terminal_event.wait(self.terminal_timeout_seconds):
                raise RuntimeError("guest never reached the held final frame")
            if self.watcher.terminal_event_type != "PASS":
                return
            if self.process is None:
                raise RuntimeError("xemu process handle is unavailable")

            # PASS is guest-authored after the final draw. This only lets the
            # submitted final image reach the host window; no frame-perfect
            # host input timing is attempted.
            time.sleep(1.0)
            command = [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(WINDOW_CAPTURE),
                    "-OutputPath",
                    str(self.output_path),
                    "-ProcessId",
                    str(self.process.pid),
                    "-ExpectedWidth",
                    "640",
                    "-ExpectedHeight",
                    "480",
                    "-MinimumNonBlackRatio",
                    "0.90",
                    "-MinimumRightSideNonBlackRatio",
                    "0.50",
                    "-MetadataPath",
                    str(self.capture_metadata_path),
                ]
            if self.reference_path is not None:
                command.extend(
                    (
                        "-ReferencePath",
                        str(self.reference_path),
                        "-DifferencePath",
                        str(self.evidence_path.with_name("held-frame-difference.png")),
                    )
                )
            completed = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                check=False,
            )
            if completed.returncode != 0:
                raise RuntimeError(
                    "held-frame capture failed: "
                    + (completed.stdout.strip() or f"exit {completed.returncode}")
                )
            try:
                capture = json.loads(completed.stdout)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"held-frame capture returned invalid JSON: {completed.stdout!r}"
                ) from exc
            if not self.output_path.is_file():
                raise RuntimeError("held-frame capture did not create the PNG artifact")
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError("xemu did not exit after the timed final-frame pause") from exc
            if self.process.returncode != 0:
                raise RuntimeError(
                    f"xemu exited with {self.process.returncode} after the final-frame pause"
                )
            self.evidence = {
                "schema_version": 1,
                "status": "CAPTURED_AND_GUEST_EXITED",
                "terminal_event": self.watcher.terminal_event_type,
                "capture": capture,
                "image_sha256": sha256(self.output_path),
                "comparison_eligible": True,
                "normalization": {
                    "source": capture.get("CaptureSource"),
                    "width": 640,
                    "height": 480,
                    "minimum_non_black_ratio": 0.90,
                    "minimum_right_side_non_black_ratio": 0.50,
                },
            }
            self._write_evidence(self.evidence)
        except Exception as exc:
            self.error = str(exc)
            capture = None
            if self.capture_metadata_path.is_file():
                try:
                    capture = json.loads(
                        self.capture_metadata_path.read_text(encoding="utf-8")
                    )
                except (OSError, json.JSONDecodeError):
                    capture = None
            self.evidence = {
                "schema_version": 1,
                "status": "CAPTURE_FAILED",
                "terminal_event": self.watcher.terminal_event_type,
                "error": self.error,
                "image_path": str(self.output_path),
                "capture": capture,
                "comparison_eligible": False,
            }
            self._write_evidence(self.evidence)
            self.terminate_process_tree()

    def finish(self) -> dict:
        if self.thread is None:
            raise RuntimeError("held-frame capture was never started")
        self.thread.join(timeout=self.terminal_timeout_seconds + 35)
        if self.thread.is_alive():
            self.terminate_process_tree()
            raise RuntimeError("held-frame capture worker did not stop")
        if self.error is not None:
            raise RuntimeError(self.error)
        if self.evidence is None:
            raise RuntimeError("held-frame capture produced no evidence")
        return self.evidence


class TimedFrameCapture:
    """Capture exact client crops at requested process-relative checkpoints."""

    def __init__(
        self,
        capture_seconds: list[float],
        output_dir: Path,
        require_frame_change: bool,
    ) -> None:
        self.capture_seconds = sorted(set(capture_seconds))
        self.output_dir = output_dir
        self.require_frame_change = require_frame_change
        self.thread: threading.Thread | None = None
        self.error: str | None = None
        self.evidence: dict | None = None

    def start(self, process: subprocess.Popen) -> None:
        self.thread = threading.Thread(
            target=self._run,
            args=(process,),
            name="xemu-timed-frame-capture",
            daemon=True,
        )
        self.thread.start()

    def _run(self, process: subprocess.Popen) -> None:
        start = time.monotonic()
        captures: list[dict] = []
        try:
            self.output_dir.mkdir(parents=True, exist_ok=False)
            for index, capture_second in enumerate(self.capture_seconds, 1):
                remaining = start + capture_second - time.monotonic()
                if remaining > 0:
                    threading.Event().wait(remaining)
                if process.poll() is not None:
                    raise RuntimeError(
                        "xemu exited before capture checkpoint "
                        f"{capture_second:g}s"
                    )
                label = f"checkpoint-{index:03d}-{capture_second:08.3f}s"
                output_path = self.output_dir / f"{label}.png"
                metadata_path = self.output_dir / f"{label}.json"
                completed = subprocess.run(
                    [
                        "powershell.exe",
                        "-NoProfile",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        str(WINDOW_CAPTURE),
                        "-OutputPath",
                        str(output_path),
                        "-ProcessId",
                        str(process.pid),
                        "-ExpectedWidth",
                        "640",
                        "-ExpectedHeight",
                        "480",
                        "-MinimumNonBlackRatio",
                        "0.02",
                        "-MinimumRightSideNonBlackRatio",
                        "0.02",
                        "-MetadataPath",
                        str(metadata_path),
                    ],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=20,
                    check=False,
                )
                if completed.returncode != 0:
                    raise RuntimeError(
                        f"capture checkpoint {capture_second:g}s failed: "
                        + (completed.stdout.strip() or f"exit {completed.returncode}")
                    )
                capture = json.loads(completed.stdout)
                captures.append(
                    {
                        "capture_second": capture_second,
                        "image_path": str(output_path),
                        "image_sha256": sha256(output_path),
                        "capture": capture,
                    }
                )
            hashes = [item["image_sha256"] for item in captures]
            frozen = len(hashes) >= 2 and len(set(hashes)) == 1
            if frozen and self.require_frame_change:
                raise RuntimeError(
                    "all timed frame captures are identical; frozen-frame check failed"
                )
            self.evidence = {
                "schema_version": 1,
                "status": "CAPTURED",
                "captures": captures,
                "frozen_frame_detected": frozen,
                "frame_change_required": self.require_frame_change,
                "canonical_client_size": [640, 480],
                "window_chrome_excluded": True,
            }
        except Exception as exc:
            self.error = str(exc)
            self.evidence = {
                "schema_version": 1,
                "status": "CAPTURE_FAILED",
                "error": self.error,
                "captures": captures,
            }
        finally:
            if self.output_dir.parent.is_dir():
                (self.output_dir.parent / "timed-frame-capture.json").write_text(
                    json.dumps(self.evidence, indent=2) + "\n", encoding="utf-8"
                )

    def finish(self) -> dict:
        if self.thread is None:
            raise RuntimeError("timed frame capture was never started")
        self.thread.join(timeout=max(self.capture_seconds, default=0) + 30)
        if self.thread.is_alive():
            raise RuntimeError("timed frame capture worker did not stop")
        if self.error is not None:
            raise RuntimeError(self.error)
        if self.evidence is None:
            raise RuntimeError("timed frame capture produced no evidence")
        return self.evidence


def read_build_info(xemu_path: Path) -> dict[str, str]:
    info_path = xemu_path.parent / "BUILD_INFO.txt"
    values: dict[str, str] = {}
    if info_path.is_file():
        for line in info_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    values["XEMU_PATH"] = str(xemu_path)
    values["XEMU_SHA256"] = sha256(xemu_path)
    return values


def validate_build_cleanliness(
    build_info: dict[str, str], allow_dirty_build: bool
) -> dict:
    """Keep dirty binaries opt-in and permanently label accepted diagnostics."""

    source_state = build_info.get("SOURCE_STATE")
    override_used = bool(source_state and source_state != "clean")
    if override_used and not allow_dirty_build:
        raise RuntimeError(f"refusing benchmark run from SOURCE_STATE={source_state}")
    return {
        "source_state": source_state,
        "override_used": override_used,
        "performance_claim_eligible": False if override_used else None,
        "warning": DIRTY_BUILD_TIMING_WARNING if override_used else None,
    }


def clear_diagnostic_environment() -> list[str]:
    removed: list[str] = []
    exact = {
        "VK_INSTANCE_LAYERS",
        "VK_LAYER_PATH",
        "VK_LOADER_LAYERS_ENABLE",
        "VK_LOADER_LAYERS_DISABLE",
    }
    for key in list(os.environ):
        if key.startswith("XEMU_") or key in exact:
            removed.append(key)
            del os.environ[key]
    return sorted(removed)


def xemu_config_addend(
    backend: str, scale: int, vsync: bool, vulkan_validation: bool
) -> str:
    return f"""
[display]
renderer = '{backend.upper()}'
setup_nvidia_profile = false

[display.vulkan]
validation_layers = {str(vulkan_validation).lower()}
debug_shaders = false
assert_on_validation_msg = false

[display.quality]
surface_scale = {scale}

[display.window]
vsync = {str(vsync).lower()}
startup_size = '640x480'
"""


def collect_vulkan_validation(run_dir: Path, enabled: bool) -> dict:
    result = {
        "enabled": enabled,
        "active": False if enabled else None,
        "vuid_count": 0,
        "unique_vuid_count": 0,
        "unique_vuids": [],
    }
    if not enabled:
        return result

    log_path = run_dir / "xemu.log"
    if not log_path.is_file():
        raise RuntimeError("xemu.log is missing from the Vulkan validation run")
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    if "Selected physical device:" not in log_text:
        raise RuntimeError("Vulkan did not initialize during the validation run")
    if "Warning: Validation layers enabled." not in log_text:
        unavailable = (
            "desired validation layer not found" in log_text
            or "Warning: validation layers not available" in log_text
        )
        detail = (
            "validation layer unavailable"
            if unavailable
            else "activation not proven"
        )
        raise RuntimeError(
            "Vulkan validation was requested but is inactive: " + detail
        )

    counts = collections.Counter(
        re.findall(r"VUID-[A-Za-z0-9_-]+", log_text)
    )
    unique = sorted(counts)
    (run_dir / "unique-vuids.txt").write_text(
        "".join(f"{vuid}\n" for vuid in unique), encoding="utf-8"
    )
    (run_dir / "vuid-counts.txt").write_text(
        "".join(f"{counts[vuid]:8d} {vuid}\n" for vuid in unique),
        encoding="utf-8",
    )
    result.update(
        {
            "active": True,
            "vuid_count": sum(counts.values()),
            "unique_vuid_count": len(unique),
            "unique_vuids": unique,
        }
    )
    return result


def parse_xemu_environment(assignments: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for assignment in assignments:
        if "=" not in assignment:
            raise ValueError(f"invalid --xemu-env assignment: {assignment!r}")
        name, value = assignment.split("=", 1)
        if not re.fullmatch(r"XEMU_[A-Z0-9_]+", name):
            raise ValueError(
                f"xemu experiment environment name must match XEMU_[A-Z0-9_]+: {name!r}"
            )
        if name.startswith(("XEMU_PERF_", "XEMU_LAB_")):
            raise ValueError(f"reserved xemu environment name: {name}")
        if name in result:
            raise ValueError(f"duplicate xemu environment assignment: {name}")
        result[name] = value
    return result


def perf_marker_environment(live_marker_path: Path) -> dict[str, str]:
    """Return the mandatory live-marker transport for every perf child."""

    return {
        "XEMU_PERF_GUEST_MARKERS": "1",
        "XEMU_PERF_LIVE_MARKER_PATH": str(live_marker_path),
    }


def configure_vulkan_lab_counters(run_dir: Path, enabled: bool) -> dict:
    """Set the lab counter sink for one child and describe its evidence."""

    path = run_dir / VULKAN_LAB_PERFLOG_NAME
    if enabled:
        os.environ[VULKAN_LAB_PERFLOG_ENV] = str(path)
    return {
        "enabled": enabled,
        "path": str(path) if enabled else None,
        "validated": False,
        "data_window_count": 0,
        "timing_eligible": False if enabled else None,
        "warning": VULKAN_LAB_TIMING_WARNING if enabled else None,
    }


def clear_vulkan_lab_counters() -> None:
    os.environ.pop(VULKAN_LAB_PERFLOG_ENV, None)


def validate_vulkan_lab_counter_log(path: Path, enabled: bool) -> dict:
    """Require at least one emitted, non-comment Vulkan counter window."""

    result = {
        "enabled": enabled,
        "path": str(path) if enabled else None,
        "validated": False,
        "data_window_count": 0,
        "timing_eligible": False if enabled else None,
        "warning": VULKAN_LAB_TIMING_WARNING if enabled else None,
    }
    if not enabled:
        return result
    if not path.is_file():
        raise RuntimeError(
            "xemu did not write the requested Vulkan lab counter log; "
            "use a Vulkan lab-instrumented build"
        )

    windows = [
        line
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.strip()
        and not line.lstrip().startswith("#")
        and re.search(r"(?:^|\s)kind=window(?:\s|$)", line)
    ]
    if not windows:
        raise RuntimeError(
            "Vulkan lab counter log contains no non-comment kind=window data window"
        )
    result.update({"validated": True, "data_window_count": len(windows)})
    return result


def normalize_guest_results(raw_text: str) -> list[dict]:
    # Current xemu-perf-tests writes a trailing comma after the final object.
    normalized = re.sub(r",\s*\]", "\n]", raw_text)
    parsed = json.loads(normalized)
    if not isinstance(parsed, list) or not parsed:
        raise ValueError("guest result file did not contain any benchmark records")
    return parsed


SUITE_RESULTS_CSV_COLUMNS = (
    "schema_version",
    "id",
    "revision",
    "kind",
    "name",
    "outcome",
    "iterations",
    "sample_count",
    "measurement_iterations_multiplier",
    "warmup_iterations",
    "gpu_completion_mode",
    "completion_wait_us",
    "total_us",
    "total_seconds",
    "average_us",
    "min_us",
    "max_us",
    "median_us",
    "p95_us",
    "mad_us",
    "unit",
    "direction",
    "framebuffer_fnv1a64",
    "child_result_count",
    "metadata_json",
    "raw_results_json",
)


def write_suite_results_csv(path: Path, records: list[dict]) -> None:
    """Write every guest record in a stable, spreadsheet-friendly shape."""

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=SUITE_RESULTS_CSV_COLUMNS, lineterminator="\n"
        )
        writer.writeheader()
        for record in records:
            total_us = record.get("total_us")
            total_seconds = (
                f"{float(total_us) / 1_000_000.0:.9f}".rstrip("0").rstrip(".")
                if isinstance(total_us, (int, float)) and not isinstance(total_us, bool)
                else ""
            )
            row = {
                key: record.get(key, "")
                for key in SUITE_RESULTS_CSV_COLUMNS
                if key not in {"total_seconds", "metadata_json", "raw_results_json"}
            }
            row["total_seconds"] = total_seconds
            row["metadata_json"] = json.dumps(
                record.get("metadata"), separators=(",", ":"), sort_keys=True
            )
            row["raw_results_json"] = json.dumps(
                record.get("raw_results", []), separators=(",", ":")
            )
            writer.writerow(row)


def require_passing_guest_outcomes(records: list[dict]) -> None:
    failures = [
        f"{record.get('id') or record.get('name') or '<unknown>'}="
        f"{record.get('outcome')!r}"
        for record in records
        if record.get("outcome") != "PASS"
    ]
    if failures:
        raise RuntimeError(
            "guest emitted non-PASS benchmark outcomes: " + ", ".join(failures)
        )


class RecordCountMismatch(RuntimeError):
    def __init__(self, expected: int, actual: int):
        self.validation = {
            "status": "FAILED",
            "expected": expected,
            "actual": actual,
        }
        super().__init__(
            f"full-run record count mismatch: expected {expected} unique records, "
            f"got {actual}"
        )


def positive_record_count(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "expected record count must be a positive integer"
        ) from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError(
            "expected record count must be a positive integer"
        )
    return parsed


def validate_expected_record_count(
    records: list[dict], expected: int | None
) -> dict:
    actual = len(records)
    if expected is None:
        return {"status": "NOT_REQUESTED", "expected": None, "actual": actual}
    if actual != expected:
        raise RecordCountMismatch(expected, actual)
    return {"status": "PASSED", "expected": expected, "actual": actual}


class PerfTestExecutor(XemuTestBase):
    def __init__(
        self,
        test_env: Environment,
        results_path: Path,
        suite_config: dict,
        config_addend: str,
        guest_iso: Path,
        timeout_seconds: int,
    ):
        super().__init__(test_env, results_path)
        self.xemu_manager.iso_path = guest_iso
        self.xemu_manager.timeout = timeout_seconds
        self.xemu_manager.config += config_addend
        self.xbox_results_path = "xemu_perf_tests"
        self.suite_config = suite_config
        self.parsed_results: list[dict] = []

    def _prepare_hdd(self):
        super()._prepare_hdd()
        fs_e = self.hdd_manager.get_filesystem("e")
        fs_e.mkdir("/xemu_perf_tests")
        fs_e.write(
            "/xemu_perf_tests/xemu_perf_tests_config.json",
            json.dumps(self.suite_config, indent=2).encode("utf-8"),
        )
        del fs_e

    def _copy_results(self):
        # xemu-test's generic extractor defaults to the C partition. The
        # performance guest intentionally writes to E, so extract that exact
        # file through the same FATX manager instead of guessing a host path.
        fs_e = self.hdd_manager.get_filesystem("e")
        raw_results = bytes(fs_e.read("/xemu_perf_tests/results.txt"))
        del fs_e
        (self.results_path / "results.txt").write_bytes(raw_results)
        (self.results_path / "guest-config.json").write_text(
            json.dumps(self.suite_config, indent=2) + "\n", encoding="utf-8"
        )
        shutil.copy2(self.xemu_manager.config_path, self.results_path)

    def analyze_results(self):
        raw_path = self.results_path / "results.txt"
        self.parsed_results = normalize_guest_results(
            raw_path.read_text(encoding="utf-8", errors="strict")
        )
        (self.results_path / "normalized-results.json").write_text(
            json.dumps(self.parsed_results, indent=2) + "\n", encoding="utf-8"
        )
        write_suite_results_csv(
            self.results_path / "suite-results.csv", self.parsed_results
        )
        require_passing_guest_outcomes(self.parsed_results)
        if self.xemu_manager.exit_status != 0:
            raise RuntimeError(
                f"xemu did not complete through guest shutdown (exit={self.xemu_manager.exit_status})"
            )


def exact_test_filter(test_id: str) -> dict:
    if "::" not in test_id:
        raise ValueError("--test-id must use the exact Suite::Test name")
    suite_name, test_name = test_id.split("::", 1)
    if not suite_name or not test_name:
        raise ValueError("--test-id must use the exact Suite::Test name")
    return {suite_name: {test_name: {"skipped": False}}}


GAME_LOAD_LONG_SCENE_STAGES = frozenset(
    {
        "cpu",
        "pfifo",
        "alpha_overdraw",
        "streaming_surface_reuse",
        "combined",
        "full_system",
    }
)
GAME_LOAD_CROSS_TITLE_STAGE_ORDER = CROSS_TITLE_STAGE_ORDER
GAME_LOAD_CROSS_TITLE_STAGES = frozenset(GAME_LOAD_CROSS_TITLE_STAGE_ORDER)
GAME_LOAD_CROSS_TITLE_ALL_MASK = CROSS_TITLE_ALL_MASK
GAME_LOAD_S3TC_SYNC_FACTOR_STAGE_ORDER = (
    "dxt1_same_address_wait",
    "dxt1_same_address_queued",
    "dxt1_ring",
    "dxt1_dirty_once",
    "rgba8_same_address_wait",
    "rgba8_same_address_queued",
    "rgba8_ring",
    "rgba8_dirty_once",
    "bc2_native_eligible",
    "bc2_bordered_fallback",
    "bc3_native_eligible",
    "bc3_bordered_fallback",
)
GAME_LOAD_S3TC_SYNC_FACTOR_STAGES = frozenset(
    GAME_LOAD_S3TC_SYNC_FACTOR_STAGE_ORDER
)
GAME_LOAD_S3TC_SYNC_FACTOR_ALL_MASK = (1 << len(
    GAME_LOAD_S3TC_SYNC_FACTOR_STAGE_ORDER
)) - 1
GAME_LOAD_CONFIG_TEST_IDS = {
    "long_unlocked_scene": "GameLoadComposite::08-LongUnlockedScene",
    "cross_title_hotpath": "GameLoadComposite::09-CrossTitleHotpath",
    "s3tc_sync_factor": "GameLoadComposite::10-S3tcSyncFactor",
}


def load_game_load_config(path: Path | None) -> dict | None:
    """Load one closed guest-owned GameLoadComposite control object."""

    if path is None:
        return None
    resolved = path.resolve()
    try:
        value = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not parse game-load config {resolved}: {exc}") from exc
    if (
        not isinstance(value, dict)
        or len(value) != 1
        or not set(value) <= set(GAME_LOAD_CONFIG_TEST_IDS)
    ):
        raise ValueError(
            "game-load config must contain exactly one known scene"
        )
    if "cross_title_hotpath" in value:
        scene = value["cross_title_hotpath"]
        if not isinstance(scene, dict):
            raise ValueError("game-load cross_title_hotpath must be an object")
        unknown = set(scene) - {"fast_smoke", "stage_mask", "stages"}
        if unknown:
            raise ValueError(
                "game-load cross_title_hotpath contains unknown keys: "
                f"{', '.join(sorted(unknown))}"
            )
        fast_smoke = scene.get("fast_smoke")
        if not isinstance(fast_smoke, bool):
            raise ValueError("game-load cross_title_hotpath.fast_smoke must be boolean")
        stage_mask = scene.get("stage_mask")
        if (
            not isinstance(stage_mask, int)
            or isinstance(stage_mask, bool)
            or not 1 <= stage_mask <= GAME_LOAD_CROSS_TITLE_ALL_MASK
        ):
            raise ValueError(
                "game-load cross_title_hotpath.stage_mask must select bits 0 through 11"
            )
        stages = scene.get("stages")
        if (
            not isinstance(stages, dict)
            or set(stages) - GAME_LOAD_CROSS_TITLE_STAGES
        ):
            raise ValueError(
                "game-load cross-title stages must name only known stages"
            )
        if any(not isinstance(enabled, bool) for enabled in stages.values()):
            raise ValueError("game-load cross-title stage values must be booleans")
        named_mask = sum(
            1 << index
            for index, name in enumerate(GAME_LOAD_CROSS_TITLE_STAGE_ORDER)
            if stages.get(name, False)
        )
        if stage_mask != named_mask:
            raise ValueError("game-load cross_title_hotpath stage names and mask must match")
        return value

    if "s3tc_sync_factor" in value:
        scene = value["s3tc_sync_factor"]
        if not isinstance(scene, dict):
            raise ValueError("game-load s3tc_sync_factor must be an object")
        unknown = set(scene) - {"stage_mask", "stages"}
        if unknown:
            raise ValueError(
                "game-load s3tc_sync_factor contains unknown keys: "
                f"{', '.join(sorted(unknown))}"
            )
        stage_mask = scene.get("stage_mask")
        if (
            not isinstance(stage_mask, int)
            or isinstance(stage_mask, bool)
            or not 1 <= stage_mask <= GAME_LOAD_S3TC_SYNC_FACTOR_ALL_MASK
        ):
            raise ValueError(
                "game-load s3tc_sync_factor.stage_mask must select bits 0 through 11"
            )
        stages = scene.get("stages")
        if stages is not None:
            if (
                not isinstance(stages, dict)
                or set(stages) - GAME_LOAD_S3TC_SYNC_FACTOR_STAGES
            ):
                raise ValueError(
                    "game-load s3tc_sync_factor stages must name only known stages"
                )
            if any(not isinstance(enabled, bool) for enabled in stages.values()):
                raise ValueError(
                    "game-load s3tc_sync_factor stage values must be booleans"
                )
            named_mask = sum(
                1 << index
                for index, name in enumerate(GAME_LOAD_S3TC_SYNC_FACTOR_STAGE_ORDER)
                if stages.get(name, False)
            )
            if not stage_mask & named_mask:
                raise ValueError("game-load s3tc_sync_factor selects no stages")
        return value

    scene = value["long_unlocked_scene"]
    if not isinstance(scene, dict):
        raise ValueError("game-load long_unlocked_scene must be an object")
    allowed = {
        "stage_mask",
        "stages",
        "measurement_iterations_multiplier",
        "warmup_iterations",
        "gpu_precondition",
    }
    unknown = set(scene) - allowed
    if unknown:
        raise ValueError(
            "game-load long_unlocked_scene contains unknown keys: "
            f"{', '.join(sorted(unknown))}"
        )
    stage_mask = scene.get("stage_mask")
    if stage_mask is not None and (
        not isinstance(stage_mask, int) or isinstance(stage_mask, bool) or not 0 <= stage_mask <= 63
    ):
        raise ValueError("game-load stage_mask must be an integer from 0 through 63")
    stages = scene.get("stages")
    if stages is not None:
        if not isinstance(stages, dict) or set(stages) - GAME_LOAD_LONG_SCENE_STAGES:
            raise ValueError("game-load stages must name only known long-scene stages")
        if any(not isinstance(enabled, bool) for enabled in stages.values()):
            raise ValueError("game-load stages values must be booleans")
    for name in ("measurement_iterations_multiplier", "warmup_iterations"):
        overrides = scene.get(name)
        if overrides is None:
            continue
        if not isinstance(overrides, dict) or set(overrides) - GAME_LOAD_LONG_SCENE_STAGES:
            raise ValueError(f"game-load {name} must name only known long-scene stages")
        for stage, amount in overrides.items():
            minimum = 0 if name == "warmup_iterations" else 1
            if (
                not isinstance(amount, int)
                or isinstance(amount, bool)
                or not minimum <= amount <= 100000
            ):
                raise ValueError(
                    f"game-load {name}.{stage} must be an integer from "
                    f"{minimum} through 100000"
                )
    precondition = scene.get("gpu_precondition")
    if precondition is not None:
        if not isinstance(precondition, dict) or set(precondition) != {"alpha_draws"}:
            raise ValueError("game-load gpu_precondition must contain only alpha_draws")
        alpha_draws = precondition["alpha_draws"]
        if not isinstance(alpha_draws, int) or isinstance(alpha_draws, bool) or alpha_draws < 0:
            raise ValueError("game-load gpu_precondition.alpha_draws must be non-negative")
    return value


def game_load_config_test_id(config: dict | None) -> str | None:
    if config is None:
        return None
    return GAME_LOAD_CONFIG_TEST_IDS[next(iter(config))]


def game_load_config_group_child_masks(config: dict | None) -> dict[str, int]:
    """Map a closed scene's stage mask onto its catalog group children."""

    test_id = game_load_config_test_id(config)
    if test_id is None:
        return {}
    scene = config[next(iter(config))]
    stage_mask = scene.get("stage_mask")
    return {} if stage_mask is None else {test_id: stage_mask}


def validate_game_load_config_selection(
    required_test_id: str | None, *, test_id: str | None, full_suite: bool
) -> None:
    """Allow a closed GameLoadComposite override for its test or a full plan."""

    if required_test_id is None or full_suite or test_id == required_test_id:
        return
    raise ValueError(f"game-load config requires --test-id {required_test_id}")


def final_measurement_is_composite(records: list[dict]) -> bool:
    """Host counter windows describe only the last completed guest test."""
    return bool(
        records
        and str(records[-1].get("name", "")).startswith("GameLoadComposite::")
    )


def build_perf_config(
    test_filter: dict,
    warmup_iterations: int,
    completion_mode: str,
    measurement_iterations_multiplier: int,
    game_load_config: dict | None = None,
    hold_final_frame_on_completion: bool = False,
    enable_xemu_only_tests: bool = False,
) -> dict:
    config = {
        "settings": {
            "disable_autorun": False,
            "enable_autorun_immediately": True,
            "enable_shutdown_on_completion": True,
            "hold_final_frame_on_completion": hold_final_frame_on_completion,
            "hold_final_frame_milliseconds": (
                8000 if hold_final_frame_on_completion else 0
            ),
            "skip_tests_by_default": True,
            "delay_milliseconds_between_tests": 0,
            "reboot_or_shutdown_delay": 0,
            "warmup_iterations": warmup_iterations,
            "measurement_iterations_multiplier": measurement_iterations_multiplier,
            "gpu_completion_mode": completion_mode,
            "enable_xemu_only_tests": enable_xemu_only_tests,
            "output_directory_path": "e:/xemu_perf_tests",
        },
        "test_suites": test_filter,
    }
    if game_load_config is not None:
        config["game_load_composite"] = game_load_config
    return config


def summarize_records(records: list[dict]) -> list[dict]:
    summary: list[dict] = []
    for record in records:
        raw = [int(value) for value in record.get("raw_results", [])]
        item = {
            "id": record.get("id"),
            "revision": record.get("revision"),
            "kind": record.get("kind"),
            "name": record.get("name"),
            "outcome": record.get("outcome"),
            "iterations": record.get("iterations"),
            "sample_count": record.get("sample_count"),
            "measurement_iterations_multiplier": record.get(
                "measurement_iterations_multiplier"
            ),
            "raw_result_count": len(raw),
            "guest_total_us": record.get("total_us"),
            "guest_average_us": record.get("average_us"),
            "guest_min_us": record.get("min_us"),
            "guest_max_us": record.get("max_us"),
            "warmup_iterations": record.get("warmup_iterations"),
            "gpu_completion_mode": record.get("gpu_completion_mode"),
            "completion_wait_us": record.get("completion_wait_us"),
            "framebuffer_fnv1a64": record.get("framebuffer_fnv1a64"),
            "metadata": record.get("metadata"),
        }
        if raw:
            item["guest_median_us"] = statistics.median(raw)
            item["guest_mad_us"] = statistics.median(
                [abs(value - statistics.median(raw)) for value in raw]
            )
        summary.append(item)
    return summary


def format_record_success(record: dict) -> str:
    """Render total duration first and identify secondary unit-cost timings."""

    total_us = record.get("guest_total_us")
    total = (
        f"{float(total_us) / 1_000_000:.3f} s"
        if isinstance(total_us, (int, float)) and not isinstance(total_us, bool)
        else "n/a"
    )

    def per_iteration(value: object) -> str:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return f"{float(value):.3f} us/iteration"
        return "n/a"

    return (
        f"guest measured total={total}; "
        f"median={per_iteration(record.get('guest_median_us'))}; "
        f"average={per_iteration(record.get('guest_average_us'))}; "
        f"test={record.get('name')}"
    )


def normalize_perf_records(
    records: list[dict],
    measurement_iterations_multiplier: int,
    warmup_iterations: int | None = None,
    completion_mode: str | None = None,
) -> list[dict]:
    """Fill metadata omitted by older guest images from authoritative inputs."""
    normalized: list[dict] = []
    for record in records:
        item = dict(record)
        raw_results = item.get("raw_results")
        if item.get("sample_count") is None and isinstance(raw_results, list):
            item["sample_count"] = len(raw_results)
        if item.get("measurement_iterations_multiplier") is None:
            item["measurement_iterations_multiplier"] = (
                measurement_iterations_multiplier
            )
        if item.get("warmup_iterations") is None and warmup_iterations is not None:
            item["warmup_iterations"] = warmup_iterations
        if item.get("gpu_completion_mode") is None and completion_mode is not None:
            item["gpu_completion_mode"] = completion_mode
        normalized.append(item)
    return normalized


REPEATED_DISPLAY_PROFILE_PREFIX = "GameLoadComposite::12-RepeatedDisplay-"
REPEATED_DISPLAY_SHAPES = frozenset(("Boosted", "Idle"))
REPEATED_DISPLAY_COUNTERS = (
    "DISPLAY_COMPOSE_REQUESTS",
    "DISPLAY_COMPOSE_HITS",
    "DISPLAY_COMPOSE_MISSES",
    "DISPLAY_COMPOSES",
    "QUEUE_SUBMIT_5",
)
VERTEX_SNAPSHOT_COUNTERS = (
    "VERTEX_RAM_UPDATE_DEFERRED",
    "VERTEX_RAM_SNAPSHOT_DRAW",
    "VERTEX_RAM_SNAPSHOT_ATTRIBUTE",
    "VERTEX_RAM_SNAPSHOT_BYTES",
    "VERTEX_RAM_DEFERRED_COPY_BYTES",
    "VERTEX_RAM_SNAPSHOT_RETIRE_PERF_COMPLETE",
)
STAGE12_SURF_DOWNLOAD_PER_ITERATION = (6.8, 7.2)
STAGE12_GEOM_INLINE_RATIO = (0.80, 0.88)
STAGE12_QUEUE_SUBMIT_PER_ITERATION = (2.0, 4.0)
STAGE12_AUX_MINUS_SUBMIT5_PER_ITERATION = (7.0, 10.0)


def validate_repeated_display_counters(
    telemetry: dict, profile: str, experiment_role: str
) -> dict | None:
    if not profile.startswith(REPEATED_DISPLAY_PROFILE_PREFIX):
        return None

    shape = profile.removeprefix(REPEATED_DISPLAY_PROFILE_PREFIX)
    if shape not in REPEATED_DISPLAY_SHAPES:
        raise RuntimeError(
            f"unsupported repeated-display profile shape: {shape!r}"
        )

    counters = telemetry.get("counter_totals")
    if not isinstance(counters, dict):
        raise RuntimeError(
            "repeated-display telemetry is missing the counter_totals object"
        )
    missing = [name for name in REPEATED_DISPLAY_COUNTERS if name not in counters]
    if missing:
        raise RuntimeError(
            "repeated-display telemetry is missing required counters: "
            + ", ".join(missing)
        )

    invalid = {
        name: counters[name]
        for name in REPEATED_DISPLAY_COUNTERS
        if (
            not isinstance(counters[name], int)
            or isinstance(counters[name], bool)
            or counters[name] < 0
        )
    }
    if invalid:
        raise RuntimeError(
            "repeated-display telemetry counters must be non-negative integers: "
            f"{invalid}"
        )

    requests = counters["DISPLAY_COMPOSE_REQUESTS"]
    hits = counters["DISPLAY_COMPOSE_HITS"]
    misses = counters["DISPLAY_COMPOSE_MISSES"]
    composes = counters["DISPLAY_COMPOSES"]
    if requests != hits + misses:
        raise RuntimeError(
            "repeated-display counter mismatch: "
            f"DISPLAY_COMPOSE_REQUESTS={requests}, but "
            f"DISPLAY_COMPOSE_HITS + DISPLAY_COMPOSE_MISSES={hits + misses}"
        )
    if composes != misses:
        raise RuntimeError(
            "repeated-display counter mismatch: "
            f"DISPLAY_COMPOSES={composes}, but "
            f"DISPLAY_COMPOSE_MISSES={misses}"
        )
    if misses < 2:
        raise RuntimeError(
            "repeated-display path requires at least 2 misses/composes: "
            f"misses={misses}, composes={composes}"
        )
    if counters["QUEUE_SUBMIT_5"] <= 0:
        raise RuntimeError(
            "repeated-display path requires QUEUE_SUBMIT_5 reachability: "
            f"QUEUE_SUBMIT_5={counters['QUEUE_SUBMIT_5']}"
        )
    requires_hit = shape == "Boosted" and experiment_role != "baseline"
    if requires_hit and hits < 1:
        raise RuntimeError(
            "boosted repeated-display path requires at least one compose hit: "
            f"role={experiment_role}, hits={hits}"
        )

    return {
        "validated": True,
        "shape": shape,
        "experiment_role": experiment_role,
        "requires_hit": requires_hit,
        "counter_totals": {
            name: counters[name] for name in REPEATED_DISPLAY_COUNTERS
        },
    }


def validate_vertex_snapshot_counters(
    counters: object,
    snapshots_enabled: bool,
    measurement_iterations_multiplier: int,
    *,
    require_marker_completion: bool = False,
) -> dict:
    """Validate the selected vertex path in its own telemetry window."""

    if not isinstance(counters, dict):
        raise RuntimeError("vertex telemetry window is missing counter_totals")

    def counter(name: str) -> int:
        value = counters.get(name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise RuntimeError(
                "vertex telemetry window has invalid counter "
                f"{name}: {value!r}"
            )
        return value

    def baseline_snapshot_counter(name: str) -> int:
        """Normalize omitted snapshot-only baseline counters to their exact zero."""

        if (
            not snapshots_enabled
            and name in VERTEX_SNAPSHOT_COUNTERS
            and name not in counters
        ):
            return 0
        return counter(name)

    expected_completions = (
        BOOSTED_VERTEX_STACK_VERTEX_ITERATIONS
        * measurement_iterations_multiplier
    )
    if require_marker_completion:
        f2_completions = counter("FINISH_PERF_COMPLETE")
        minimum_marker_completions = 8 * measurement_iterations_multiplier
        if snapshots_enabled:
            if not minimum_marker_completions <= f2_completions <= expected_completions:
                raise RuntimeError(
                    "vertex telemetry window has invalid F2 completion count: "
                    f"expected range [{minimum_marker_completions}, "
                    f"{expected_completions}], got "
                    f"{counters.get('FINISH_PERF_COMPLETE')!r}"
                )
        elif not 0 <= f2_completions <= expected_completions:
            raise RuntimeError(
                "baseline vertex telemetry window has invalid F2 completion "
                f"count: expected range [0, {expected_completions}], got "
                f"{counters.get('FINISH_PERF_COMPLETE')!r}"
            )
        if counter("FINISH_FLUSH") != 0:
            raise RuntimeError(
                "vertex telemetry window used FLUSH instead of marker-only F2 completion: "
                f"FINISH_FLUSH={counters.get('FINISH_FLUSH')!r}"
            )

    if snapshots_enabled:
        snapshot_draws = counter("VERTEX_RAM_SNAPSHOT_DRAW")
        snapshot_attributes = counter("VERTEX_RAM_SNAPSHOT_ATTRIBUTE")
        deferred = counter("VERTEX_RAM_UPDATE_DEFERRED")
        candidate_expected = {
            "FINISH_VERTEX_BUFFER_DIRTY": 0,
        }
        if not require_marker_completion:
            candidate_expected["QUEUE_SUBMIT"] = expected_completions
            candidate_expected["PIPELINE_RENDERPASSES"] = expected_completions
        for event_name, expected in candidate_expected.items():
            if counter(event_name) != expected:
                raise RuntimeError(
                    "vertex snapshot path assertion failed for "
                    f"{event_name}: expected {expected}, got "
                    f"{counters.get(event_name)!r}"
                )
        if require_marker_completion:
            snapshot_retires = counter("VERTEX_RAM_SNAPSHOT_RETIRE_PERF_COMPLETE")
            minimum_snapshot_retires = 8 * measurement_iterations_multiplier
            if not minimum_snapshot_retires <= snapshot_retires <= f2_completions:
                raise RuntimeError(
                    "vertex snapshot path assertion failed for "
                    "VERTEX_RAM_SNAPSHOT_RETIRE_PERF_COMPLETE: expected range "
                    f"[{minimum_snapshot_retires}, {f2_completions}], got "
                    f"{counters.get('VERTEX_RAM_SNAPSHOT_RETIRE_PERF_COMPLETE')!r}"
                )
        if snapshot_draws < 10_000 * measurement_iterations_multiplier:
            raise RuntimeError(
                "vertex snapshot path did not activate for enough draws: "
                f"{snapshot_draws}"
            )
        if snapshot_attributes != snapshot_draws * 2:
            raise RuntimeError(
                "vertex snapshot attribute count does not match the two "
                f"active attributes per draw: {snapshot_attributes} versus "
                f"{snapshot_draws * 2}"
            )
        if deferred < 5_000 * measurement_iterations_multiplier:
            raise RuntimeError(
                "vertex snapshot path did not defer enough overlapping "
                f"updates: {deferred}"
            )
        if require_marker_completion:
            queue_submit = counter("QUEUE_SUBMIT")
            queue_submit_5 = counter("QUEUE_SUBMIT_5")
            renderpasses = counter("PIPELINE_RENDERPASSES")
            maximum_queue_submits = 128 * measurement_iterations_multiplier
            if queue_submit < f2_completions:
                raise RuntimeError(
                    "vertex snapshot queue reachability failed: "
                    f"QUEUE_SUBMIT={queue_submit}, expected at least "
                    f"FINISH_PERF_COMPLETE={f2_completions}"
                )
            if queue_submit > maximum_queue_submits:
                raise RuntimeError(
                    "vertex snapshot queue bound failed: "
                    f"QUEUE_SUBMIT={queue_submit}, maximum "
                    f"{maximum_queue_submits}"
                )
            if queue_submit_5 <= 0:
                raise RuntimeError(
                    "vertex snapshot queue-submit-5 reachability failed: "
                    f"QUEUE_SUBMIT_5={queue_submit_5}"
                )
            if renderpasses != queue_submit:
                raise RuntimeError(
                    "vertex snapshot renderpass relationship failed: "
                    f"PIPELINE_RENDERPASSES={renderpasses}, "
                    f"QUEUE_SUBMIT={queue_submit}"
                )
            for name in (
                "VERTEX_RAM_SNAPSHOT_BYTES",
                "VERTEX_RAM_DEFERRED_COPY_BYTES",
            ):
                if counter(name) <= 0:
                    raise RuntimeError(
                        "vertex snapshot path did not record copied bytes: "
                        f"{name}={counters.get(name)!r}"
                    )
        path = "snapshots"
    else:
        minimum_dirty = (
            1_500 if require_marker_completion else 8_000
        ) * measurement_iterations_multiplier
        dirty = counter("FINISH_VERTEX_BUFFER_DIRTY")
        if dirty < minimum_dirty:
            raise RuntimeError(
                "baseline vertex-dirty synchronization path did not "
                f"activate at least {minimum_dirty:,} times"
            )
        for event_name in VERTEX_SNAPSHOT_COUNTERS:
            if baseline_snapshot_counter(event_name) != 0:
                raise RuntimeError(
                    "baseline unexpectedly activated the snapshot path: "
                    f"{event_name}={counters.get(event_name)!r}"
                )
        if require_marker_completion:
            queue_submit = counter("QUEUE_SUBMIT")
            renderpasses = counter("PIPELINE_RENDERPASSES")
            maximum_additional_submits = 64 * measurement_iterations_multiplier
            if queue_submit < dirty:
                raise RuntimeError(
                    "baseline vertex queue reachability failed: "
                    f"QUEUE_SUBMIT={queue_submit}, expected at least "
                    f"FINISH_VERTEX_BUFFER_DIRTY={dirty}"
                )
            if queue_submit - dirty > maximum_additional_submits:
                raise RuntimeError(
                    "baseline vertex queue spread failed: "
                    f"QUEUE_SUBMIT - FINISH_VERTEX_BUFFER_DIRTY="
                    f"{queue_submit - dirty}, maximum "
                    f"{maximum_additional_submits}"
                )
            if renderpasses != queue_submit:
                raise RuntimeError(
                    "baseline vertex renderpass relationship failed: "
                    f"PIPELINE_RENDERPASSES={renderpasses}, "
                    f"QUEUE_SUBMIT={queue_submit}"
                )
        path = "vertex-dirty-baseline"

    evidence_counters = {
        "FINISH_VERTEX_BUFFER_DIRTY",
        "QUEUE_SUBMIT",
        "PIPELINE_RENDERPASSES",
        *VERTEX_SNAPSHOT_COUNTERS[:3],
    }
    if require_marker_completion:
        evidence_counters.update(
            {
                "FINISH_PERF_COMPLETE",
                "FINISH_FLUSH",
                "QUEUE_SUBMIT_5",
                *VERTEX_SNAPSHOT_COUNTERS[3:],
            }
        )
    return {
        "validated": True,
        "path": path,
        "counter_totals": {
            name: (
                baseline_snapshot_counter(name)
                if not snapshots_enabled and name in VERTEX_SNAPSHOT_COUNTERS
                else counter(name)
            )
            for name in sorted(evidence_counters)
        },
    }


def validate_stage12_host_counters(
    counters: object, measured_iterations: int
) -> dict:
    """Prove the measured Stage12 surface, texture, geometry, and queue shape."""

    if not isinstance(counters, dict):
        raise RuntimeError("boosted-vertex-stack Test12 window lacks counter_totals")
    if measured_iterations <= 0:
        raise RuntimeError(
            f"boosted-vertex-stack Test12 iteration count is invalid: {measured_iterations}"
        )

    def counter(name: str) -> int:
        value = counters.get(name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise RuntimeError(
                "boosted-vertex-stack Test12 window has invalid counter "
                f"{name}: {value!r}"
            )
        return value

    values = {
        name: counter(name)
        for name in (
            "SURF_DOWNLOAD",
            "SURF_TO_TEX",
            "TEX_UPLOAD",
            "GEOM_BUFFER_UPDATE_2",
            "INLINE_ELEMENTS",
            "FINISH_VERTEX_BUFFER_DIRTY",
            "QUEUE_SUBMIT",
            "QUEUE_SUBMIT_5",
            "QUEUE_SUBMIT_AUX",
        )
    }

    def require_per_iteration(name: str, minimum: float, maximum: float) -> float:
        actual = values[name] / measured_iterations
        if not minimum <= actual <= maximum:
            raise RuntimeError(
                f"boosted-vertex-stack Test12 {name} per-iteration assertion failed: "
                f"expected [{minimum}, {maximum}], got {actual:.6f} "
                f"({values[name]}/{measured_iterations})"
            )
        return actual

    per_iteration = {
        "SURF_DOWNLOAD": require_per_iteration(
            "SURF_DOWNLOAD", *STAGE12_SURF_DOWNLOAD_PER_ITERATION
        ),
        "SURF_TO_TEX": require_per_iteration("SURF_TO_TEX", 2.0, 2.0),
        "TEX_UPLOAD": require_per_iteration("TEX_UPLOAD", 1.0, 1.0),
        "QUEUE_SUBMIT": require_per_iteration(
            "QUEUE_SUBMIT", *STAGE12_QUEUE_SUBMIT_PER_ITERATION
        ),
    }
    inline_elements = values["INLINE_ELEMENTS"]
    if inline_elements == 0:
        raise RuntimeError(
            "boosted-vertex-stack Test12 INLINE_ELEMENTS must be positive"
        )
    geom_inline_ratio = values["GEOM_BUFFER_UPDATE_2"] / inline_elements
    if not (
        STAGE12_GEOM_INLINE_RATIO[0]
        <= geom_inline_ratio
        <= STAGE12_GEOM_INLINE_RATIO[1]
    ):
        raise RuntimeError(
            "boosted-vertex-stack Test12 GEOM_BUFFER_UPDATE_2/INLINE_ELEMENTS "
            "assertion failed: expected "
            f"[{STAGE12_GEOM_INLINE_RATIO[0]}, {STAGE12_GEOM_INLINE_RATIO[1]}], "
            f"got {geom_inline_ratio:.6f} "
            f"({values['GEOM_BUFFER_UPDATE_2']}/{inline_elements})"
        )
    if values["FINISH_VERTEX_BUFFER_DIRTY"] != 0:
        raise RuntimeError(
            "boosted-vertex-stack Test12 FINISH_VERTEX_BUFFER_DIRTY assertion "
            f"failed: expected 0, got {values['FINISH_VERTEX_BUFFER_DIRTY']}"
        )
    aux_minus_submit5 = values["QUEUE_SUBMIT_AUX"] - values["QUEUE_SUBMIT_5"]
    aux_minus_submit5_per_iteration = aux_minus_submit5 / measured_iterations
    if not (
        STAGE12_AUX_MINUS_SUBMIT5_PER_ITERATION[0]
        <= aux_minus_submit5_per_iteration
        <= STAGE12_AUX_MINUS_SUBMIT5_PER_ITERATION[1]
    ):
        raise RuntimeError(
            "boosted-vertex-stack Test12 (QUEUE_SUBMIT_AUX - QUEUE_SUBMIT_5) "
            "per-iteration assertion failed: expected "
            f"[{STAGE12_AUX_MINUS_SUBMIT5_PER_ITERATION[0]}, "
            f"{STAGE12_AUX_MINUS_SUBMIT5_PER_ITERATION[1]}], got "
            f"{aux_minus_submit5_per_iteration:.6f} "
            f"(({values['QUEUE_SUBMIT_AUX']} - {values['QUEUE_SUBMIT_5']})/"
            f"{measured_iterations})"
        )

    return {
        "validated": True,
        "measured_iterations": measured_iterations,
        "counter_totals": values,
        "per_iteration": per_iteration,
        "geom_buffer_update_2_to_inline_elements": geom_inline_ratio,
        "queue_submit_aux_minus_queue_submit_5_per_iteration": (
            aux_minus_submit5_per_iteration
        ),
    }


def validate_boosted_vertex_stack_telemetry(
    telemetry: dict,
    backend: str,
    effective_features: dict[str, bool],
    measurement_iterations_multiplier: int,
    experiment_role: str,
) -> dict:
    """Map and prove the Test12 then vertex windows without top-level fallback."""

    if backend != "vulkan":
        raise RuntimeError("boosted-vertex-stack telemetry gates require Vulkan")
    if telemetry.get("schema_version") != 2:
        raise RuntimeError("boosted-vertex-stack requires telemetry schema v2")
    windows = telemetry.get("measurement_windows")
    if not isinstance(windows, list) or len(windows) != 2:
        raise RuntimeError(
            "boosted-vertex-stack requires exactly two ordered telemetry windows: "
            f"got {len(windows) if isinstance(windows, list) else windows!r}"
        )
    for key in ("measurement_windows_count", "measurement_windows_completed"):
        if telemetry.get(key) != len(windows):
            raise RuntimeError(
                "boosted-vertex-stack telemetry window count mismatch: "
                f"{key}={telemetry.get(key)!r}, expected {len(windows)}"
            )
    capacity = telemetry.get("measurement_windows_capacity")
    if not isinstance(capacity, int) or isinstance(capacity, bool) or capacity < 2:
        raise RuntimeError(
            "boosted-vertex-stack telemetry window capacity is invalid: "
            f"{capacity!r}"
        )

    previous_end: int | None = None
    for index, window in enumerate(windows):
        if not isinstance(window, dict) or window.get("index") != index:
            raise RuntimeError(
                "boosted-vertex-stack telemetry window order mismatch at "
                f"index {index}: {window!r}"
            )
        start = window.get("measurement_start_ns")
        end = window.get("measurement_end_ns")
        if (
            not isinstance(start, int)
            or isinstance(start, bool)
            or not isinstance(end, int)
            or isinstance(end, bool)
            or start >= end
            or (previous_end is not None and start < previous_end)
        ):
            raise RuntimeError(
                "boosted-vertex-stack telemetry window timestamps are invalid at "
                f"index {index}: start={start!r}, end={end!r}"
            )
        previous_end = end

    test12_counters = windows[0].get("counter_totals")
    vertex_counters = windows[1].get("counter_totals")
    if not isinstance(test12_counters, dict):
        raise RuntimeError("boosted-vertex-stack Test12 window lacks counter_totals")

    def test12_counter(name: str) -> int:
        value = test12_counters.get(name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise RuntimeError(
                "boosted-vertex-stack Test12 window has invalid counter "
                f"{name}: {value!r}"
            )
        return value

    expected_test12_completions = (
        BOOSTED_VERTEX_STACK_TEST12_ITERATIONS
        * measurement_iterations_multiplier
    )
    if test12_counter("FINISH_PERF_COMPLETE") != expected_test12_completions:
        raise RuntimeError(
            "boosted-vertex-stack Test12 window has invalid F2 completion count: "
            f"expected {expected_test12_completions}, got "
            f"{test12_counters.get('FINISH_PERF_COMPLETE')!r}"
        )
    if test12_counter("FINISH_FLUSH") != 0:
        raise RuntimeError(
            "boosted-vertex-stack Test12 window used FLUSH instead of F2 completion: "
            f"FINISH_FLUSH={test12_counters.get('FINISH_FLUSH')!r}"
        )
    stage12_host_path = validate_stage12_host_counters(
        test12_counters, expected_test12_completions
    )
    test12 = validate_repeated_display_counters(
        {"counter_totals": test12_counters},
        BOOSTED_VERTEX_STACK_RECORDS[0],
        experiment_role,
    )
    assert test12 is not None
    test12["counter_totals"].update(
        {
            "FINISH_PERF_COMPLETE": test12_counters["FINISH_PERF_COMPLETE"],
            "FINISH_FLUSH": test12_counters["FINISH_FLUSH"],
        }
    )
    test12["host_path_assertions"] = stage12_host_path
    vertex = validate_vertex_snapshot_counters(
        vertex_counters,
        effective_features.get("vertex_ram_snapshots") is True,
        measurement_iterations_multiplier,
        require_marker_completion=True,
    )
    return {
        "validated": True,
        "window_record_order": list(BOOSTED_VERTEX_STACK_RECORDS),
        "test12_window": test12,
        "vertex_window": vertex,
    }


def validate_host_telemetry(
    telemetry: object,
    requested_level: str,
    profile: str,
    backend: str,
    effective_features: dict[str, bool],
    measurement_iterations_multiplier: int,
    experiment_role: str = "single",
) -> dict:
    if not isinstance(telemetry, dict):
        raise RuntimeError("xemu host telemetry root is not a JSON object")
    schema_version = telemetry.get("schema_version")
    if schema_version not in (1, 2):
        raise RuntimeError(
            "unsupported xemu host telemetry schema: "
            f"{schema_version!r}"
        )
    if schema_version == 2:
        required_v2 = {
            "measurement_windows_status": "ok",
            "measurement_windows_overflowed": False,
            "measurement_windows_dropped": 0,
            "measurement_active": False,
        }
        for key, expected in required_v2.items():
            if telemetry.get(key) != expected:
                raise RuntimeError(
                    f"invalid v2 measurement-window state {key}="
                    f"{telemetry.get(key)!r}, expected {expected!r}"
                )
        completed = telemetry.get("measurement_windows_completed")
        if not isinstance(completed, int) or completed <= 0:
            raise RuntimeError(
                "v2 measurement windows must contain at least one completed window: "
                f"{completed!r}"
            )
        protocol_errors = telemetry.get("measurement_protocol_errors")
        if protocol_errors != 0:
            raise RuntimeError(
                "v2 measurement-window protocol errors must be zero: "
                f"{protocol_errors!r}"
            )
    expected_timing = requested_level == "timed"
    if telemetry.get("timing_enabled") is not expected_timing:
        raise RuntimeError(
            "xemu host telemetry timing mode mismatch: "
            f"requested {requested_level!r}, got "
            f"timing_enabled={telemetry.get('timing_enabled')!r}"
        )
    if telemetry.get("measurement_seen") is not True:
        raise RuntimeError(
            "xemu host telemetry did not observe the guest measurement markers; "
            "use the marker-enabled guest ISO"
        )

    if backend == "vulkan" and requested_level != "off":
        repeated_display_assertions = validate_repeated_display_counters(
            telemetry, profile, experiment_role
        )
        if repeated_display_assertions is not None:
            telemetry["repeated_display_assertions"] = (
                repeated_display_assertions
            )

    def scaled(value):
        if isinstance(value, dict):
            return {key: scaled(item) for key, item in value.items()}
        if isinstance(value, int):
            return value * measurement_iterations_multiplier
        return value

    assertions = scaled(HOST_TELEMETRY_ASSERTIONS.get(profile, {}))
    if backend == "opengl":
        # Transfer-byte accounting is currently implemented by the Vulkan
        # surface path. OpenGL still has exact event-count and hash guards.
        assertions.pop("byte_totals", None)
        if profile == "vertex-ram-reuse":
            assertions["counter_totals"] = {
                "BEGIN_ENDS": 10_240 * measurement_iterations_multiplier,
                "DRAW_ARRAYS": 10_240 * measurement_iterations_multiplier,
                "ATTR_BIND": 20_480 * measurement_iterations_multiplier,
            }
    if effective_features.get("selective_surface_read_watch"):
        if profile == "surface-cpu-read-clean":
            assertions["counter_totals"] = {
                "SURF_CPU_ACCESS_CALLBACK": 0,
                "SURF_CPU_ACCESS_READ": 0,
                "SURF_CPU_ACCESS_WRITE": 0,
                "SURF_CPU_ACCESS_SURFACE_CHECK": 0,
                "SURF_CPU_ACCESS_SURFACE_MATCH": 0,
                "SURF_CPU_ACCESS_DIRTY": 0,
            }
        elif profile == "surface-cpu-read-after-gpu-write":
            assertions["counter_totals"] = {
                "SURF_DOWNLOAD": 20 * measurement_iterations_multiplier,
                "SURF_CPU_ACCESS_CALLBACK": 20 * measurement_iterations_multiplier,
                "SURF_CPU_ACCESS_READ": 20 * measurement_iterations_multiplier,
                "SURF_CPU_ACCESS_WRITE": 0,
                "SURF_CPU_ACCESS_SURFACE_CHECK": 20 * measurement_iterations_multiplier,
                "SURF_CPU_ACCESS_SURFACE_MATCH": 20 * measurement_iterations_multiplier,
                "SURF_CPU_ACCESS_DIRTY": 20 * measurement_iterations_multiplier,
            }
    for group_name, expected_values in assertions.items():
        actual_group = telemetry.get(group_name)
        if not isinstance(actual_group, dict):
            raise RuntimeError(f"xemu host telemetry is missing {group_name}")
        for event_name, expected in expected_values.items():
            actual = actual_group.get(event_name)
            if actual != expected:
                raise RuntimeError(
                    f"host path assertion failed for {group_name}.{event_name}: "
                    f"expected {expected!r}, got {actual!r}"
                )

    if backend == "opengl" and profile == "vertex-ram-reuse":
        upload_count = telemetry["counter_totals"].get(
            "GEOM_BUFFER_UPDATE_1", 0
        )
        upload_bytes = telemetry["byte_totals"].get(
            "GEOM_BUFFER_UPDATE_1", {}
        )
        logical = upload_bytes.get("logical", 0)
        transferred = upload_bytes.get("transferred", 0)
        minimum_uploads = 9_000 * measurement_iterations_multiplier
        maximum_uploads = 10_240 * measurement_iterations_multiplier
        if not minimum_uploads <= upload_count <= maximum_uploads:
            raise RuntimeError(
                "OpenGL vertex-upload path reachability failed: "
                f"expected {minimum_uploads}-{maximum_uploads} updates, got {upload_count}"
            )
        if logical != transferred or not (
            upload_count * 4_096 <= transferred <= upload_count * 8_192
        ):
            raise RuntimeError(
                "OpenGL vertex-upload byte amplification is outside the "
                f"expected page-aligned range: count={upload_count}, "
                f"logical={logical}, transferred={transferred}"
            )

    if backend == "vulkan" and profile == "vertex-ram-reuse":
        telemetry["vertex_ram_assertions"] = validate_vertex_snapshot_counters(
            telemetry["counter_totals"],
            effective_features.get("vertex_ram_snapshots") is True,
            measurement_iterations_multiplier,
        )
    if backend == "vulkan" and profile == BOOSTED_VERTEX_STACK_PROFILE:
        telemetry["boosted_vertex_stack_assertions"] = (
            validate_boosted_vertex_stack_telemetry(
                telemetry,
                backend,
                effective_features,
                measurement_iterations_multiplier,
                experiment_role,
            )
        )
    if backend == "vulkan" and expected_timing:
        counters = telemetry.get("counter_totals") or {}
        gpu_work_seen = any(
            counters.get(name, 0)
            for name in ("DRAW_ARRAYS", "BEGIN_ENDS", "CLEAR", "QUEUE_SUBMIT")
        )
        gpu_timestamp = telemetry.get("gpu_timestamp")
        if gpu_work_seen and (
            not isinstance(gpu_timestamp, dict)
            or not isinstance(gpu_timestamp.get("count"), int)
            or gpu_timestamp["count"] <= 0
            or not isinstance(gpu_timestamp.get("total_ns"), int)
            or gpu_timestamp["total_ns"] <= 0
        ):
            raise RuntimeError(
                "timed Vulkan telemetry observed GPU work without a GPU timestamp duration"
            )
    return telemetry


def validate_profile_correctness(
    records: list[dict], profile: str, measurement_iterations_multiplier: int,
    backend: str | None = None,
) -> None:
    contract = PROFILE_RECORD_CONTRACTS.get(profile)
    if contract:
        if len(records) != 1:
            raise RuntimeError(
                f"fixed-work contract failed for {profile}: expected one "
                f"record, got {len(records)}"
            )
        record = records[0]
        expected_fields = {
            "name": contract["name"],
            "iterations": contract["iterations"] * measurement_iterations_multiplier,
            "sample_count": contract["raw_result_count"],
            "measurement_iterations_multiplier": measurement_iterations_multiplier,
        }
        for field, expected_value in expected_fields.items():
            if record.get(field) != expected_value:
                raise RuntimeError(
                    f"fixed-work contract failed for {profile}.{field}: "
                    f"expected {expected_value!r}, got {record.get(field)!r}"
                )
        raw_results = record.get("raw_results")
        if not isinstance(raw_results, list) or len(raw_results) != contract["raw_result_count"]:
            raise RuntimeError(
                f"fixed-work contract failed for {profile}.raw_results: "
                f"expected {contract['raw_result_count']} samples, got "
                f"{len(raw_results) if isinstance(raw_results, list) else raw_results!r}"
            )
        minimum_total_us = contract.get("minimum_total_us")
        if minimum_total_us is not None and (
            not isinstance(record.get("total_us"), int)
            or record["total_us"] < minimum_total_us
        ):
            raise RuntimeError(
                f"sustained-work contract failed for {profile}.total_us: "
                f"expected at least {minimum_total_us}, got "
                f"{record.get('total_us')!r}"
            )

    multi_contract = PROFILE_MULTI_RECORD_CONTRACTS.get(profile)
    if multi_contract:
        names = [record.get("name") if isinstance(record, dict) else None for record in records]
        expected_names = [item["name"] for item in multi_contract]
        if names != expected_names:
            raise RuntimeError(
                f"fixed-work contract failed for {profile}: expected ordered records "
                f"{expected_names!r}, got {names!r}"
            )
        for record, expected in zip(records, multi_contract):
            expected_fields = {
                "name": expected["name"],
                "iterations": expected["iterations"] * measurement_iterations_multiplier,
                "sample_count": expected["raw_result_count"],
                "measurement_iterations_multiplier": measurement_iterations_multiplier,
            }
            for field, expected_value in expected_fields.items():
                if record.get(field) != expected_value:
                    raise RuntimeError(
                        f"fixed-work contract failed for {profile}.{expected['name']}.{field}: "
                        f"expected {expected_value!r}, got {record.get(field)!r}"
                    )
            raw_results = record.get("raw_results")
            if (
                not isinstance(raw_results, list)
                or len(raw_results) != expected["raw_result_count"]
            ):
                raise RuntimeError(
                    f"fixed-work contract failed for {profile}.{expected['name']}.raw_results: "
                    f"expected {expected['raw_result_count']} samples, got "
                    f"{len(raw_results) if isinstance(raw_results, list) else raw_results!r}"
                )
            framebuffer_hash = record.get("framebuffer_fnv1a64")
            if not isinstance(framebuffer_hash, str) or not framebuffer_hash:
                raise RuntimeError(
                    f"fixed-work contract failed for {profile}.{expected['name']}."
                    "framebuffer_fnv1a64: expected a non-empty hash"
                )
            expected_hash = expected.get("framebuffer_fnv1a64")
            if expected_hash is not None and framebuffer_hash != expected_hash:
                raise OracleValidationError(
                    f"correctness hash assertion failed for {profile}.{expected['name']}: "
                    f"expected {expected_hash!r}, got {framebuffer_hash!r}"
                )

    expected = PROFILE_BACKEND_CORRECTNESS_HASHES.get(
        (profile, backend)
    ) or PROFILE_CORRECTNESS_HASHES.get(profile)
    if not expected:
        return
    actual = {
        record.get("name"): record.get("framebuffer_fnv1a64")
        for record in records
        if isinstance(record, dict)
    }
    if actual != expected:
        raise OracleValidationError(
            f"correctness hash assertion failed for {profile} "
            f"({PROFILE_CORRECTNESS_HASH_PROVENANCE}): "
            f"expected {expected!r}, got {actual!r}"
        )


def load_output_only_contract(path: Path, args: argparse.Namespace) -> dict:
    """Load the pinned portable manifest used as the post-run oracle contract."""

    resolved = path.resolve()
    try:
        manifest = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not parse guest output contract {resolved}: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ValueError("guest output contract must be a schema_version 1 object")
    workload = manifest.get("workload")
    result_contract = manifest.get("result_contract")
    if not isinstance(workload, dict) or not isinstance(result_contract, dict):
        raise ValueError("guest output contract lacks workload or result_contract")
    exact = {
        "test_id": args.test_id,
        "backend": args.backend,
        "surface_scale": args.scale,
        "memory_megabytes": args.memory_megabytes,
        "vsync": args.vsync,
        "completion_mode": args.completion_mode,
        "host_telemetry": "off",
        "warmup_iterations": args.warmup_iterations,
        "measurement_iterations_multiplier": args.measurement_iterations_multiplier,
        "guest_evidence_mode": GUEST_EVIDENCE_OUTPUT_ONLY,
        "guest_evidence_capability": GUEST_EVIDENCE_CAPABILITIES[
            GUEST_EVIDENCE_OUTPUT_ONLY
        ],
        "held_frame_capture": False,
    }
    for field, expected in exact.items():
        if workload.get(field) != expected:
            raise ValueError(
                f"guest output contract workload.{field} mismatch: "
                f"expected {expected!r}, got {workload.get(field)!r}"
            )
    for field, minimum in (
        ("minimum_measurement_seconds", 15.0),
        ("minimum_warmup_seconds", 5.0),
    ):
        value = workload.get(field)
        if not isinstance(value, (int, float)) or value < minimum:
            raise ValueError(
                f"guest output contract workload.{field} must be at least {minimum:g}"
            )
    order = result_contract.get("record_order")
    if not isinstance(order, list) or not order or any(
        not isinstance(name, str) or not name for name in order
    ):
        raise ValueError("guest output contract record_order must be a non-empty string array")
    expected_records = []
    for name in order:
        matches = [
            value
            for key, value in result_contract.items()
            if key not in ("record_order", "retained_change_gate")
            and isinstance(value, dict)
            and value.get("name") == name
        ]
        if len(matches) != 1:
            raise ValueError(f"guest output contract has no unique record for {name!r}")
        expected = matches[0]
        for field in ("iterations", "sample_count", "framebuffer_fnv1a64", "metadata"):
            if field not in expected:
                raise ValueError(f"guest output contract {name}.{field} is missing")
        expected_records.append(expected)
    return {
        "path": str(resolved),
        "sha256": sha256(resolved),
        "suite_id": manifest.get("suite_id"),
        "workload": workload,
        "records": expected_records,
    }


def validate_output_only_request(args: argparse.Namespace) -> None:
    if args.guest_evidence_mode != GUEST_EVIDENCE_OUTPUT_ONLY:
        if args.guest_output_contract_json is not None:
            raise ValueError(
                "--guest-output-contract-json requires --guest-evidence-mode output-only"
            )
        return
    if args.mode != "perf":
        raise ValueError("--guest-evidence-mode output-only requires --mode perf")
    if args.guest_output_contract_json is None:
        raise ValueError("output-only evidence requires --guest-output-contract-json")
    if args.host_telemetry != "off":
        raise ValueError("output-only evidence requires host telemetry off")
    if args.host_gdb_samples:
        raise ValueError("output-only evidence requires GDB sampling off")
    if getattr(args, "hold_final_frame_on_completion", False) or getattr(
        args, "held_frame_reference", None
    ):
        raise ValueError("output-only evidence requires held-frame capture off")
    if getattr(args, "capture_second", []):
        raise ValueError("output-only evidence requires timed frame capture off")
    if getattr(args, "allow_missing_live_markers", False):
        raise ValueError("output-only evidence cannot combine with marker compatibility mode")


def validate_output_only_records(records: list[dict], contract: dict) -> dict:
    expected_records = contract["records"]
    workload = contract["workload"]
    if len(records) != len(expected_records):
        raise RuntimeError(
            "output-only record count mismatch: "
            f"expected {len(expected_records)}, got {len(records)}"
        )
    for actual, expected in zip(records, expected_records, strict=True):
        name = expected["name"]
        exact = {
            "name": name,
            "iterations": expected["iterations"],
            "sample_count": expected["sample_count"],
            "framebuffer_fnv1a64": expected["framebuffer_fnv1a64"],
            "measurement_iterations_multiplier": workload[
                "measurement_iterations_multiplier"
            ],
            "warmup_iterations": workload["warmup_iterations"],
            "gpu_completion_mode": workload["completion_mode"],
        }
        for field, expected_value in exact.items():
            if actual.get(field) != expected_value:
                raise RuntimeError(
                    f"output-only oracle mismatch for {name}.{field}: "
                    f"expected {expected_value!r}, got {actual.get(field)!r}"
                )
        metadata = actual.get("metadata")
        if not isinstance(metadata, dict):
            raise RuntimeError(f"output-only oracle {name}.metadata is missing")
        for field, expected_value in expected["metadata"].items():
            if metadata.get(field) != expected_value:
                raise RuntimeError(
                    f"output-only oracle mismatch for {name}.metadata.{field}: "
                    f"expected {expected_value!r}, got {metadata.get(field)!r}"
                )
        total_us = actual.get("total_us")
        iterations = actual.get("iterations")
        if not isinstance(total_us, int) or total_us <= 0:
            raise RuntimeError(f"output-only oracle {name}.total_us is invalid")
        measured_seconds = total_us / 1_000_000.0
        warmup_seconds = (
            total_us / iterations * workload["warmup_iterations"] / 1_000_000.0
        )
        if measured_seconds < workload["minimum_measurement_seconds"]:
            raise RuntimeError(
                f"output-only oracle {name} measured only {measured_seconds:.3f}s"
            )
        if warmup_seconds < workload["minimum_warmup_seconds"]:
            raise RuntimeError(
                f"output-only oracle {name} predicts only {warmup_seconds:.3f}s warmup"
            )
    return {
        "status": "PASSED",
        "contract_sha256": contract["sha256"],
        "record_count": len(records),
    }


def validate_held_frame_correctness(
    evidence: dict | None, profile: str, backend: str
) -> None:
    expected = PROFILE_HELD_FRAME_SHA256S.get((profile, backend))
    if expected is None:
        return
    if not isinstance(evidence, dict):
        raise OracleValidationError(
            f"held-frame oracle for {profile}/{backend} was not captured"
        )
    actual = evidence.get("image_sha256")
    if actual != expected:
        raise OracleValidationError(
            f"held-frame hash assertion failed for {profile}/{backend} "
            f"({PROFILE_CORRECTNESS_HASH_PROVENANCE}): expected {expected}, got {actual}"
        )


def validate_profile_telemetry(
    profile: str,
    backend: str,
    host_telemetry: str,
    completion_mode: str,
) -> None:
    """Require the two-window Vulkan/F2 contract for the mixed profile."""

    if profile != BOOSTED_VERTEX_STACK_PROFILE:
        return
    if backend != "vulkan":
        raise ValueError(f"{BOOSTED_VERTEX_STACK_PROFILE} requires --backend vulkan")
    if host_telemetry not in ("counters", "timed"):
        raise ValueError(
            f"{BOOSTED_VERTEX_STACK_PROFILE} requires --host-telemetry counters "
            "or timed to gate both measurement windows"
        )
    if completion_mode != "per_iteration":
        raise ValueError(
            f"{BOOSTED_VERTEX_STACK_PROFILE} requires --completion-mode "
            "per_iteration for marker-only F2 completion"
        )


def validate_boosted_vertex_stack_prerequisites(
    build_info: dict[str, str], guest_sha256: str, role: str
) -> None:
    """Allow each child only on its runtime-proven bde artifact."""

    expected_artifact = BOOSTED_VERTEX_STACK_ARTIFACTS.get(role)
    if expected_artifact is None:
        raise RuntimeError(
            f"{BOOSTED_VERTEX_STACK_PROFILE} requires --experiment-role baseline "
            "or candidate"
        )
    expected = {
        **expected_artifact,
        "guest ISO SHA-256": BOOSTED_VERTEX_STACK_GUEST_SHA256,
    }
    actual = {
        "SOURCE_SHA": build_info.get("SOURCE_SHA"),
        "XEMU_SHA256": build_info.get("XEMU_SHA256"),
        "guest ISO SHA-256": guest_sha256,
    }
    mismatches = [
        f"{name}: expected {expected[name]}, got {actual[name]!r}"
        for name in expected
        if actual[name] != expected[name]
    ]
    if mismatches:
        raise RuntimeError(
            f"{BOOSTED_VERTEX_STACK_PROFILE} {role} requires the explicit "
            f"{BOOSTED_VERTEX_STACK_GUEST_COMMIT}/{expected_artifact['SOURCE_SHA'][:12]} "
            "prerequisites; "
            + "; ".join(mismatches)
        )


def write_summary(
    run_dir: Path,
    mode: str,
    profile: str | None,
    status: str,
    wall_seconds: float,
    build_info: dict[str, str],
    environment_removed: list[str],
    records: list[dict],
    message: str,
    backend: str,
    scale: int,
    vsync: bool,
    guest_iso: Path | None,
    host_process: dict | None,
    host_telemetry: dict | None,
    guest_event_evidence: dict | None,
    xemu_environment: dict[str, str],
    vulkan_validation: dict,
    vulkan_lab_counters: dict,
    experiment: dict,
    measurement_iterations_multiplier: int,
    memory_megabytes: int,
    game_load_config: dict | None,
    composite_work: list[dict],
    composite_interactions: list[dict],
    oracle_validation: dict | None = None,
    held_frame_capture: dict | None = None,
    timed_frame_capture: dict | None = None,
    build_cleanliness: dict | None = None,
    expected_record_count: int | None = None,
    record_count_validation: dict | None = None,
    live_marker_compatibility: dict | None = None,
    guest_evidence: dict | None = None,
) -> None:
    build_cleanliness = build_cleanliness or {
        "source_state": build_info.get("SOURCE_STATE"),
        "override_used": False,
        "performance_claim_eligible": None,
        "warning": None,
    }
    record_count_validation = record_count_validation or {
        "status": "NOT_REQUESTED",
        "expected": expected_record_count,
        "actual": len(records),
    }
    payload = {
        "schema_version": 1,
        "classification": (
            "diagnostic-dirty-build"
            if build_cleanliness["override_used"]
            else (
                "diagnostic-instrumented"
                if vulkan_lab_counters["enabled"]
                else (
                    "smoke"
                    if mode == "official-smoke"
                    else (
                        "benchmark-instrumented"
                        if records
                        and all(
                            record.get("gpu_completion_mode")
                            and record.get("framebuffer_fnv1a64")
                            for record in records
                        )
                        else "benchmark-triage"
                    )
                )
            )
        ),
        "mode": mode,
        "profile": profile,
        "status": status,
        "message": message,
        "host_wall_seconds": wall_seconds,
        "backend": backend,
        "surface_scale": scale,
        "vsync": vsync,
        "measurement_iterations_multiplier": measurement_iterations_multiplier,
        "xbox_memory_megabytes": memory_megabytes,
        "game_load_config": game_load_config,
        "build": build_info,
        "build_cleanliness": build_cleanliness,
        "guest_release": PERF_RELEASE if mode == "perf" else None,
        "guest_image": (
            {"path": str(guest_iso), "sha256": sha256(guest_iso)}
            if guest_iso is not None
            else None
        ),
        "host_process": host_process,
        "host_telemetry": host_telemetry,
        "guest_event_evidence": guest_event_evidence,
        "guest_evidence": guest_evidence,
        "live_marker_compatibility": live_marker_compatibility,
        "vulkan_validation": vulkan_validation,
        "vulkan_lab_counters": vulkan_lab_counters,
        "experiment": experiment,
        "xemu_environment": xemu_environment,
        "cleared_environment_variables": environment_removed,
        "expected_record_count": expected_record_count,
        "record_count_validation": record_count_validation,
        "records": summarize_records(records),
        "composite_work": composite_work,
        "composite_interactions": composite_interactions,
        "functional_hash_validation": oracle_validation,
        "held_frame_capture": held_frame_capture,
        "timed_frame_capture": timed_frame_capture,
        "measurement_warning": (
            build_cleanliness["warning"]
            if build_cleanliness["override_used"]
            else (
                live_marker_compatibility["timing_limitation"]
                if live_marker_compatibility
                and live_marker_compatibility.get("marker_waiver_applied")
                else (
                    VULKAN_LAB_TIMING_WARNING
                    if vulkan_lab_counters["enabled"]
                    else (
                        "Guest QPC measurements are triage data. GPU completion and host-path "
                        "attribution are not yet proven for every workload."
                        if mode == "perf"
                        else None
                    )
                )
            )
        ),
    }
    (run_dir / "summary.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        f"# xemu suite result: {status}",
        "",
        f"- Mode: `{mode}`",
        f"- Profile: `{profile or 'n/a'}`",
        f"- Host wall time: `{wall_seconds:.3f} s`",
        f"- Renderer: `{backend}` at `{scale}x`, VSync `{vsync}`",
        f"- Record-count guard: `{record_count_validation['status']}`; "
        f"expected `{record_count_validation['expected']}`, "
        f"actual `{record_count_validation['actual']}`",
        f"- Vulkan validation requested: `{vulkan_validation['enabled']}`; "
        f"active: `{vulkan_validation.get('active', False)}`; "
        f"unique VUIDs: `{vulkan_validation['unique_vuid_count']}`",
        f"- xemu SHA: `{build_info.get('SOURCE_SHA', 'unknown')}`",
        f"- xemu executable SHA-256: `{build_info['XEMU_SHA256']}`",
        f"- Experiment manifest: `{experiment.get('name', 'none')}`",
        f"- Experiment role: `{experiment['effective']['role']}`",
        f"- Effective host telemetry: "
        f"`{experiment['effective']['host_telemetry']}`",
        f"- Effective features: `{experiment['effective']['features']}`",
    ]
    if guest_evidence:
        lines.append(
            f"- Guest evidence: `{guest_evidence['mode']}` "
            f"(`{guest_evidence['capability']}`)"
        )
    if vulkan_lab_counters["enabled"]:
        lines.extend(
            [
                f"- Vulkan lab counters: `enabled`; data windows: "
                f"`{vulkan_lab_counters['data_window_count']}`; "
                f"validated: `{vulkan_lab_counters['validated']}`",
                f"- Vulkan lab counter log: `{vulkan_lab_counters['path']}`",
                "",
                f"> {VULKAN_LAB_TIMING_WARNING}",
            ]
        )
    if build_cleanliness["override_used"]:
        lines.extend(["", f"> {build_cleanliness['warning']}"])
    if live_marker_compatibility:
        lines.append(
            "- Live-marker waiver applied: "
            f"`{live_marker_compatibility['marker_waiver_applied']}`"
        )
        if live_marker_compatibility.get("timing_limitation"):
            lines.extend(
                [
                    "",
                    f"> {live_marker_compatibility['timing_limitation']} "
                    f"{live_marker_compatibility['correctness_limitation']}",
                ]
            )
    if host_process:
        lines.extend(
            [
                f"- xemu process wall time: `{host_process['wall_seconds']:.3f} s`",
                f"- xemu process CPU time: `{host_process['cpu_seconds']:.3f} s`",
                f"- xemu average logical cores: "
                f"`{host_process['average_logical_cores']:.3f}`",
            ]
        )
    if message:
        lines.extend([f"- Message: `{message}`"])
    if oracle_validation:
        lines.extend(
            [
                f"- Functional hashes: `{oracle_validation.get('status')}`",
                f"- Oracle provenance: "
                f"`{oracle_validation.get('oracle_provenance') or 'none'}`",
            ]
        )
        if oracle_validation.get("profile_hash_provenance"):
            lines.append(
                f"- Profile hash provenance: "
                f"`{oracle_validation['profile_hash_provenance']}`"
            )
    if records:
        lines.extend(["", "## Guest records", ""])
        for item in summarize_records(records):
            lines.append(
                f"- `{item['name']}`: median `{item.get('guest_median_us', 'n/a')} us`, "
                f"average `{item.get('guest_average_us', 'n/a')} us`, "
                f"iterations `{item.get('iterations', 'n/a')}`"
            )
    if composite_interactions:
        lines.extend(["", "## Composite interaction costs", ""])
        for analysis in composite_interactions:
            lines.append(f"Preset `{analysis['preset']}`:")
            for item in analysis["combined_interaction_ranking"]:
                lines.append(
                    f"- `{item['phase']}`: total `{item['total_us']} us`; "
                    f"isolated expectation `{item['expected_isolated_us']} us`; "
                    f"interaction `{item['interaction_us']} us` "
                    f"(`{item['interaction_percent']:.2f}%`)"
                )
    if mode == "perf":
        lines.extend(
            [
                "",
                "> These are benchmark-triage numbers, not yet PR-grade performance evidence. ",
                "> The next layer adds paired A/B process runs, explicit GPU completion, ",
                "> correctness hashes, and xemu host-path counters.",
            ]
        )
    (run_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("official-smoke", "perf"), default="perf")
    parser.add_argument("--profile", choices=tuple(PROFILES), default="surface-download")
    parser.add_argument(
        "--full-suite",
        action="store_true",
        help="Run every guest test instead of silently selecting the default profile",
    )
    parser.add_argument(
        "--enable-xemu-only-tests",
        action="store_true",
        help="Include cataloged xemu-only tests in an explicit full-suite run",
    )
    parser.add_argument(
        "--test-id",
        help="Run one exact dynamically selected test using its Suite::Test result name",
    )
    parser.add_argument("--xemu", type=Path, default=DEFAULT_XEMU)
    parser.add_argument("--guest-iso", type=Path, default=PERF_ISO)
    parser.add_argument(
        "--catalog",
        type=Path,
        help=(
            "Catalog matching the guest ISO. If omitted, use the adjacent "
            "<guest-iso-stem>.catalog.json sidecar when present. Exact dynamic "
            "test selection requires a catalog."
        ),
    )
    parser.add_argument("--backend", choices=("vulkan", "opengl"), default="vulkan")
    parser.add_argument("--scale", type=int, choices=(1, 2, 3, 4), default=1)
    parser.add_argument("--vsync", action="store_true")
    parser.add_argument(
        "--vulkan-validation",
        action="store_true",
        help="Enable VK_LAYER_KHRONOS_validation and export unique VUIDs",
    )
    parser.add_argument(
        "--vulkan-lab-counters",
        action="store_true",
        help=(
            "Write and validate observation-only Vulkan lab counter windows; "
            "all run timings become ineligible for performance claims"
        ),
    )
    parser.add_argument(
        "--vulkan-sdk-bin",
        type=Path,
        default=DEFAULT_VULKAN_SDK_BIN,
        help="Directory containing VkLayer_khronos_validation.dll and its manifest",
    )
    parser.add_argument("--warmup-iterations", type=int, default=2)
    parser.add_argument(
        "--memory-megabytes",
        type=int,
        choices=(64, 128),
        default=64,
        help="Xbox RAM size for memory-placement experiments",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=120,
        help="Terminate xemu when the complete guest run exceeds this deadline",
    )
    parser.add_argument(
        "--measurement-iterations-multiplier",
        type=int,
        default=1,
        help="Multiply fixed guest measurement work; calibrate on baseline and keep fixed for A/B",
    )
    parser.add_argument(
        "--completion-mode",
        choices=("enqueue", "batch_complete", "per_iteration"),
        default="per_iteration",
    )
    parser.add_argument(
        "--hold-final-frame-on-completion",
        action="store_true",
        help=(
            "Pause eight seconds on the final guest frame, capture a validated "
            "PNG, then require clean guest-driven xemu shutdown"
        ),
    )
    parser.add_argument(
        "--held-frame-reference",
        type=Path,
        help="Require an exact held-frame image match and write a difference PNG",
    )
    parser.add_argument(
        "--capture-second",
        action="append",
        type=float,
        default=[],
        help=(
            "Capture the canonical 640x480 client crop at this process-relative "
            "second; repeat for multiple checkpoints"
        ),
    )
    parser.add_argument(
        "--allow-static-captures",
        action="store_true",
        help="Do not fail when two or more timed checkpoint images are identical",
    )
    parser.add_argument(
        "--host-telemetry",
        choices=("off", "counters", "timed"),
        default=None,
    )
    parser.add_argument(
        "--experiment-config",
        type=Path,
        help="Validated TOML manifest containing named patch toggles and telemetry settings",
    )
    parser.add_argument(
        "--experiment-role",
        choices=("single", "baseline", "candidate"),
        default="single",
    )
    parser.add_argument(
        "--xemu-env",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="Explicit xemu experiment environment assignment; repeatable",
    )
    parser.add_argument(
        "--xemu-trace-event",
        choices=("nv2a_pgraph_method_abbrev",),
        help="Enable one reviewed xemu trace event and retain its trace log",
    )
    parser.add_argument(
        "--game-load-config-json",
        type=Path,
        help=(
            "Validated JSON object injected as game_load_composite into the guest "
            "config; requires its matching exact GameLoadComposite --test-id"
        ),
    )
    parser.add_argument(
        "--host-gdb-samples",
        type=int,
        default=0,
        help=(
            "Diagnostic-only all-thread host stack samples during the guest "
            "measurement phase; pauses xemu and must not be used for timing"
        ),
    )
    parser.add_argument(
        "--host-gdb",
        type=Path,
        default=DEFAULT_HOST_GDB,
        help="Path to a same-user Windows GDB executable",
    )
    parser.add_argument(
        "--allow-dirty-build",
        action="store_true",
        help=(
            "Diagnostic only: permit SOURCE_STATE!=clean and label the run as "
            "ineligible for performance claims"
        ),
    )
    parser.add_argument(
        "--oracle-manifest",
        type=Path,
        help="Validate framebuffer/work/result hashes against an explicit oracle",
    )
    parser.add_argument(
        "--oracle-ledger",
        type=Path,
        default=DEFAULT_ORACLE_LEDGER,
        help="Persistent same-backend determinism ledger",
    )
    parser.add_argument(
        "--no-oracle-ledger",
        action="store_true",
        help="Disable the persistent determinism gate for a diagnostic run",
    )
    parser.add_argument(
        "--expected-record-count",
        type=positive_record_count,
        help=(
            "Optional assertion against the catalog-derived total when a "
            "catalog is available; otherwise fail unless the normalized result "
            "contains exactly this many unique records"
        ),
    )
    parser.add_argument(
        "--guest-evidence-mode",
        choices=(GUEST_EVIDENCE_LIVE, GUEST_EVIDENCE_OUTPUT_ONLY),
        default=GUEST_EVIDENCE_LIVE,
        help=(
            "Guest evidence transport. live-markers remains the mandatory default; "
            "output-only is restricted to pinned post-run oracle contracts."
        ),
    )
    parser.add_argument(
        "--guest-output-contract-json",
        type=Path,
        help="Pinned portable manifest containing exact output-only result oracles",
    )
    parser.add_argument(
        "--allow-missing-live-markers",
        action="store_true",
        help=(
            "Allow an uninstrumented xemu build for correctness/hash validation; "
            "timing is explicitly ineligible for performance claims"
        ),
    )
    args = parser.parse_args()
    if args.warmup_iterations < 0:
        parser.error("--warmup-iterations must be non-negative")
    if args.timeout_seconds < 1:
        parser.error("--timeout-seconds must be positive")
    if not 1 <= args.measurement_iterations_multiplier <= 100000:
        parser.error("--measurement-iterations-multiplier must be from 1 through 100000")
    if args.test_id and args.mode != "perf":
        parser.error("--test-id requires --mode perf")
    if args.game_load_config_json and args.mode != "perf":
        parser.error("--game-load-config-json requires --mode perf")
    if args.hold_final_frame_on_completion and args.mode != "perf":
        parser.error("--hold-final-frame-on-completion requires --mode perf")
    if args.held_frame_reference and not args.hold_final_frame_on_completion:
        parser.error(
            "--held-frame-reference requires --hold-final-frame-on-completion"
        )
    if args.capture_second and args.mode != "perf":
        parser.error("--capture-second requires --mode perf")
    if args.capture_second and not args.hold_final_frame_on_completion:
        parser.error(
            "--capture-second requires --hold-final-frame-on-completion for clean teardown"
        )
    if any(second <= 0 or second >= args.timeout_seconds for second in args.capture_second):
        parser.error("every --capture-second must be positive and below --timeout-seconds")
    if args.vulkan_validation and args.backend != "vulkan":
        parser.error("--vulkan-validation requires --backend vulkan")
    if args.vulkan_lab_counters and args.backend != "vulkan":
        parser.error("--vulkan-lab-counters requires --backend vulkan")
    if args.host_gdb_samples < 0:
        parser.error("--host-gdb-samples must be non-negative")
    if args.host_gdb_samples and args.mode != "perf":
        parser.error("--host-gdb-samples requires --mode perf")
    if args.oracle_manifest and args.mode != "perf":
        parser.error("--oracle-manifest requires --mode perf")
    if args.expected_record_count is not None and args.mode != "perf":
        parser.error("--expected-record-count requires --mode perf")
    if args.enable_xemu_only_tests and (
        args.mode != "perf"
        or (
            not args.full_suite
            and args.profile != "pfifo-packet-boundary"
            and not args.test_id
        )
    ):
        parser.error(
            "--enable-xemu-only-tests requires --mode perf and a full suite, "
            "the pfifo-packet-boundary profile, or an exact --test-id"
        )
    if args.xemu_trace_event and (
        args.mode != "perf"
        or args.backend != "vulkan"
        or args.full_suite
        or args.profile != "pfifo-packet-boundary"
        or not args.enable_xemu_only_tests
    ):
        parser.error(
            "--xemu-trace-event requires --mode perf "
            "--backend vulkan --profile pfifo-packet-boundary "
            "--enable-xemu-only-tests"
        )
    return args


def validate_held_frame_request(args: argparse.Namespace) -> None:
    """Reject workloads that do not emit the PASS event required by capture."""

    if not args.hold_final_frame_on_completion:
        return
    selected = "full-suite" if args.full_suite else (args.test_id or args.profile)
    if selected not in HELD_FRAME_SUPPORTED_SELECTIONS:
        raise ValueError(
            "--hold-final-frame-on-completion is unsupported for "
            f"{selected}; this workload does not emit the guest PASS protocol "
            "event required for deterministic held-frame capture"
        )


def main() -> int:
    args = parse_args()
    if args.full_suite and args.test_id:
        raise ValueError("--full-suite cannot be combined with --test-id")
    validate_held_frame_request(args)
    oracle_manifest_path = (
        args.oracle_manifest.resolve() if args.oracle_manifest else None
    )
    oracle_ledger_path = args.oracle_ledger.resolve()
    game_load_config = load_game_load_config(args.game_load_config_json)
    required_test_id = game_load_config_test_id(game_load_config)
    validate_game_load_config_selection(
        required_test_id, test_id=args.test_id, full_suite=args.full_suite
    )
    manifest = load_experiment_config(args.experiment_config)
    role_config = resolve_experiment_role(manifest, args.experiment_role)
    cli_environment = parse_xemu_environment(args.xemu_env)
    xemu_environment, cli_overrides = merge_cli_environment(
        role_config["xemu_environment"], cli_environment
    )
    args.host_telemetry = (
        args.host_telemetry or role_config["host_telemetry"] or "off"
    )
    if args.host_gdb_samples and args.host_telemetry == "off":
        args.host_telemetry = "counters"
    validate_output_only_request(args)
    output_contract = (
        load_output_only_contract(args.guest_output_contract_json, args)
        if args.guest_evidence_mode == GUEST_EVIDENCE_OUTPUT_ONLY
        else None
    )
    guest_evidence = {
        "mode": args.guest_evidence_mode,
        "capability": GUEST_EVIDENCE_CAPABILITIES[args.guest_evidence_mode],
        "live_failure_detection": args.guest_evidence_mode == GUEST_EVIDENCE_LIVE,
        "host_phase_correlation": args.guest_evidence_mode == GUEST_EVIDENCE_LIVE,
        "held_frame_capture": False,
        "output_contract": (
            {
                "path": output_contract["path"],
                "sha256": output_contract["sha256"],
                "suite_id": output_contract["suite_id"],
            }
            if output_contract is not None
            else None
        ),
        "output_validation": None,
    }
    validate_missing_live_marker_compatibility_request(
        args.allow_missing_live_markers,
        args.mode,
        args.host_telemetry,
        args.host_gdb_samples,
    )
    if args.mode == "perf" and not args.test_id and not args.full_suite:
        validate_profile_telemetry(
            args.profile,
            args.backend,
            args.host_telemetry,
            args.completion_mode,
        )
        required_scale = PROFILE_REQUIRED_SCALES.get(args.profile)
        if required_scale is not None and args.scale != required_scale:
            raise ValueError(
                f"profile {args.profile} requires --scale {required_scale}"
            )
    experiment = {
        "name": manifest["name"] if manifest else None,
        "description": manifest["description"] if manifest else None,
        "path": manifest["path"] if manifest else None,
        "sha256": manifest["sha256"] if manifest else None,
        "effective": {
            "role": args.experiment_role,
            "host_telemetry": args.host_telemetry,
            "features": role_config["features"],
            "xemu_environment": xemu_environment,
            "cli_environment_overrides": cli_overrides,
        },
    }
    xemu_path = args.xemu.resolve()
    guest_iso = args.guest_iso.resolve()
    required = [xemu_path, PRIVATE_ROOT / "bios.bin", PRIVATE_ROOT / "mcpx.bin"]
    if args.mode == "perf":
        required.append(guest_iso)
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)
    if args.mode == "perf" and guest_iso == PERF_ISO.resolve() and sha256(guest_iso) != PERF_RELEASE["iso_sha256"]:
        raise RuntimeError("xemu-perf-tests ISO checksum does not match the pinned release")

    removed = clear_diagnostic_environment()
    if args.vulkan_validation:
        validation_dll = args.vulkan_sdk_bin / "VkLayer_khronos_validation.dll"
        validation_manifest = args.vulkan_sdk_bin / "VkLayer_khronos_validation.json"
        for path in (validation_dll, validation_manifest):
            if not path.is_file():
                raise FileNotFoundError(path)
    build_info = read_build_info(xemu_path)
    build_cleanliness = validate_build_cleanliness(
        build_info, args.allow_dirty_build
    )
    if args.mode == "perf" and not args.test_id and args.profile == BOOSTED_VERTEX_STACK_PROFILE:
        validate_boosted_vertex_stack_prerequisites(
            build_info, sha256(guest_iso), args.experiment_role
        )

    selected_profile = "full-suite" if args.full_suite else (args.test_id or args.profile)
    test_filter = (
        {}
        if args.full_suite
        else (exact_test_filter(args.test_id) if args.test_id else PROFILES[args.profile])
    )
    record_contract = None
    catalog_path = None
    effective_expected_record_count = args.expected_record_count
    if args.mode == "perf":
        catalog_path = discover_catalog(guest_iso, args.catalog)
        if args.test_id and catalog_path is None:
            raise ValueError(
                "--test-id requires --catalog or an adjacent guest ISO catalog sidecar"
            )
        if catalog_path is not None:
            record_contract = derive_record_contract(
                load_catalog(catalog_path),
                test_filter,
                full_suite=args.full_suite,
                group_child_masks=game_load_config_group_child_masks(game_load_config),
            )
            record_contract.update(
                {
                    "catalog_path": str(catalog_path),
                    "catalog_sha256": catalog_file_sha256(catalog_path),
                }
            )
            # The guest registers these opt-in suites only when explicitly
            # enabled. Keep the full-suite record contract aligned with the
            # exact set the pinned guest can emit, then qualify every gated
            # leaf in a separate process so an expected legacy abort cannot
            # erase the standard-suite result file.
            if args.full_suite and not args.enable_xemu_only_tests:
                gated_suites = ("PFIFOPacketBoundary::", "TextureCubemapFallback::")
                record_contract["expected_leaf_records"] = [
                    name for name in record_contract["expected_leaf_records"]
                    if not name.startswith(gated_suites)
                ]
                record_contract["expected_leaf_count"] = len(
                    record_contract["expected_leaf_records"]
                )
                record_contract["expected_total_count"] = (
                    record_contract["expected_leaf_count"]
                    + record_contract["expected_group_count"]
                )
            effective_expected_record_count = record_contract["expected_total_count"]
            if (
                args.expected_record_count is not None
                and args.expected_record_count != effective_expected_record_count
            ):
                raise ValueError(
                    "--expected-record-count disagrees with the catalog-derived "
                    f"selection contract: supplied {args.expected_record_count}, "
                    f"catalog expects {effective_expected_record_count} "
                    f"({record_contract['expected_leaf_count']} leaves + "
                    f"{record_contract['expected_group_count']} groups)"
                )
    if (
        (selected_profile, args.backend) in PROFILE_HELD_FRAME_SHA256S
        and not args.hold_final_frame_on_completion
    ):
        raise ValueError(
            f"profile {selected_profile} requires --hold-final-frame-on-completion"
        )
    profile_label = selected_profile if args.mode == "perf" else "test-xbe"
    path_profile_label = re.sub(
        r"[^A-Za-z0-9._-]+", "-", profile_label
    ).strip("-.")
    source_short = build_info.get("SOURCE_SHA", "unknown")[:12]
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    run_dir = RUNS_ROOT / (
        f"{stamp}-{args.mode}-{path_profile_label}-{source_short}"
    )
    run_dir.mkdir(parents=True, exist_ok=False)
    # Emit the durable path before launching xemu so an outer watchdog can
    # preserve partial logs even when this process is terminated mid-run.
    print(f"Evidence: {run_dir}", flush=True)
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    telemetry_path = run_dir / "nv2a-perf.json"
    live_marker_path = run_dir / "guest-measure-markers.txt"
    vulkan_lab_perf_path = run_dir / VULKAN_LAB_PERFLOG_NAME

    old_cwd = Path.cwd()
    os.chdir(WORK_ROOT)
    records: list[dict] = []
    record_count_validation = {
        "status": (
            "PENDING"
            if effective_expected_record_count is not None
            else "NOT_REQUESTED"
        ),
        "expected": effective_expected_record_count,
        "actual": None,
    }
    if record_contract is not None:
        record_count_validation.update(
            {
                "catalog_id": record_contract.get("catalog_id"),
                "catalog_path": record_contract["catalog_path"],
                "catalog_sha256": record_contract["catalog_sha256"],
                "expected_leaf_count": record_contract["expected_leaf_count"],
                "expected_group_count": record_contract["expected_group_count"],
            }
        )
    suite_config: dict | None = None
    composite_work: list[dict] = []
    composite_interactions: list[dict] = []
    oracle_validation: dict | None = None
    host_process: dict | None = None
    host_telemetry: dict | None = None
    guest_event_evidence: dict | None = None
    live_marker_compatibility: dict | None = None
    guest_watcher: GuestEventWatcher | None = None
    held_frame_capture: HeldFrameCapture | None = None
    held_frame_capture_evidence: dict | None = None
    timed_frame_capture: TimedFrameCapture | None = None
    timed_frame_capture_evidence: dict | None = None
    vulkan_validation = {
        "enabled": args.vulkan_validation,
        "active": False if args.vulkan_validation else None,
        "vuid_count": 0,
        "unique_vuid_count": 0,
        "unique_vuids": [],
    }
    vulkan_lab_counters = {
        "enabled": args.vulkan_lab_counters,
        "path": str(vulkan_lab_perf_path) if args.vulkan_lab_counters else None,
        "validated": False,
        "data_window_count": 0,
        "timing_eligible": False if args.vulkan_lab_counters else None,
        "warning": VULKAN_LAB_TIMING_WARNING if args.vulkan_lab_counters else None,
    }
    status = "INFRASTRUCTURE_FAILED"
    message = ""
    start = time.perf_counter()
    try:
        os.environ.update(xemu_environment)
        vulkan_lab_counters = configure_vulkan_lab_counters(
            run_dir, args.vulkan_lab_counters
        )
        if args.vulkan_validation:
            os.environ["VK_LAYER_PATH"] = str(args.vulkan_sdk_bin)
            os.environ["VK_INSTANCE_LAYERS"] = "VK_LAYER_KHRONOS_validation"
        if args.mode == "perf" and args.guest_evidence_mode == GUEST_EVIDENCE_LIVE:
            # The live stream is required for fail-fast guest assertions, not
            # merely for optional host-GDB diagnostic sampling or telemetry.
            os.environ.update(perf_marker_environment(live_marker_path))
        if args.host_telemetry != "off":
            os.environ["XEMU_PERF_TELEMETRY_PATH"] = str(telemetry_path)
            os.environ["XEMU_PERF_TELEMETRY_LEVEL"] = args.host_telemetry
        sampler = None
        if args.host_gdb_samples:
            if not args.host_gdb.is_file():
                raise FileNotFoundError(args.host_gdb)
            sampler = HostGDBSampler(
                args.host_gdb,
                xemu_path,
                live_marker_path,
                run_dir / "host-gdb",
                args.host_gdb_samples,
            )
        env = Environment(private_path=PRIVATE_ROOT, xemu_path=xemu_path)
        config_addend = xemu_config_addend(
            args.backend, args.scale, args.vsync, args.vulkan_validation
        )
        if args.mode == "official-smoke":
            test = TestXBE(env, run_dir, XEMUTEST_DATA / "TestXBE")
            test.xemu_manager.timeout = args.timeout_seconds
            test.xemu_manager.config += config_addend
        else:
            suite_config = build_perf_config(
                test_filter,
                args.warmup_iterations,
                args.completion_mode,
                args.measurement_iterations_multiplier,
                game_load_config,
                args.hold_final_frame_on_completion,
                args.enable_xemu_only_tests,
            )
            if args.full_suite:
                suite_config["settings"]["skip_tests_by_default"] = False
            test = PerfTestExecutor(
                env,
                run_dir,
                suite_config,
                config_addend,
                guest_iso,
                args.timeout_seconds,
            )
        test.xemu_manager.config = test.xemu_manager.config.replace(
            "mem_limit = '64'", f"mem_limit = '{args.memory_megabytes}'"
        )
        trace_path = run_dir / "xemu-trace.log"
        trace_args = (
            ("-trace", f"enable={args.xemu_trace_event},file={trace_path}")
            if args.xemu_trace_event
            else ()
        )
        observer = XemuProcessObserver(xemu_path, extra_args=trace_args)
        if args.guest_evidence_mode == GUEST_EVIDENCE_LIVE:
            guest_watcher = GuestEventWatcher(
                live_marker_path,
                run_dir / "guest-events.jsonl",
                run_dir / "guest-failure.json",
                observer.terminate_process_tree,
                marker_evidence_path=run_dir / "guest-marker-evidence.json",
            )
        def on_xemu_start(process: subprocess.Popen) -> None:
            nonlocal held_frame_capture, timed_frame_capture
            threading.Thread(
                target=focus_process_window,
                args=(process.pid,),
                name="xemu-window-focus",
                daemon=True,
            ).start()
            if guest_watcher is not None:
                guest_watcher.start()
            if args.hold_final_frame_on_completion:
                held_frame_capture = HeldFrameCapture(
                    guest_watcher,
                    run_dir / "held-final-frame.png",
                    run_dir / "held-frame-capture.json",
                    observer.terminate_process_tree,
                    args.timeout_seconds,
                    args.held_frame_reference.resolve()
                    if args.held_frame_reference
                    else None,
                )
                held_frame_capture.start(process)
            if args.capture_second:
                timed_frame_capture = TimedFrameCapture(
                    args.capture_second,
                    run_dir / "timed-frame-captures",
                    require_frame_change=not args.allow_static_captures,
                )
                timed_frame_capture.start(process)
            if sampler:
                sampler.start(process)

        observer.on_start = on_xemu_start
        shutdown_grace_seconds = min(float(args.timeout_seconds), 20.0)
        with XemuExclusiveLock(
            XEMU_LOCK_PATH, timeout_seconds=shutdown_grace_seconds
        ):
            # The process-name check must occur while the interprocess lock is
            # held; otherwise two controllers can both pass before launching.
            ensure_no_running_xemu(timeout_seconds=shutdown_grace_seconds)
            try:
                with observer:
                    result = test.run()
            finally:
                if guest_watcher is not None:
                    guest_event_evidence = guest_watcher.finish()
                if held_frame_capture is not None:
                    held_frame_capture_evidence = held_frame_capture.finish()
                    validate_held_frame_correctness(
                        held_frame_capture_evidence,
                        selected_profile,
                        args.backend,
                    )
                if timed_frame_capture is not None:
                    timed_frame_capture_evidence = timed_frame_capture.finish()
        if guest_watcher is not None and guest_watcher.failure is not None:
            raise GuestValidationFailed(guest_watcher.failure["message"])
        if args.mode == "perf" and args.guest_evidence_mode == GUEST_EVIDENCE_LIVE:
            live_marker_compatibility = assess_live_marker_evidence(
                guest_event_evidence,
                allow_missing_live_markers=args.allow_missing_live_markers,
            )
        if sampler:
            sampler.finish()
        host_process = observer.metrics()
        message = result.message
        vulkan_lab_counters = validate_vulkan_lab_counter_log(
            vulkan_lab_perf_path, args.vulkan_lab_counters
        )
        if isinstance(test, PerfTestExecutor):
            records = normalize_perf_records(
                test.parsed_results,
                args.measurement_iterations_multiplier,
                args.warmup_iterations,
                args.completion_mode,
            )
            if output_contract is not None:
                if result.status != TestStatus.PASSED:
                    raise RuntimeError(
                        "output-only evidence requires a parsed guest PASS result"
                    )
                guest_evidence["output_validation"] = validate_output_only_records(
                    records, output_contract
                )
            try:
                functional_report = build_functional_hash_report(
                    records,
                    guest_image_sha256=sha256(guest_iso),
                    job_config=suite_config,
                    source_backend=args.backend,
                    source_type="XEMU",
                    observation_id=run_dir.name,
                    build=build_info,
                    surface_scale=args.scale,
                )
                functional_report_path = run_dir / "oracle-report.json"
                write_oracle_json(functional_report_path, functional_report)
                try:
                    record_count_validation = (
                        validate_record_contract(records, record_contract)
                        if record_contract is not None
                        else validate_expected_record_count(
                            functional_report["records"], args.expected_record_count
                        )
                    )
                    if record_contract is not None:
                        record_count_validation.update(
                            {
                                "catalog_path": record_contract["catalog_path"],
                                "catalog_sha256": record_contract["catalog_sha256"],
                            }
                        )
                except (RecordCountMismatch, RecordContractError) as exc:
                    record_count_validation = exc.validation
                    write_oracle_json(
                        run_dir / "record-count-validation.json",
                        record_count_validation,
                    )
                    raise
                if effective_expected_record_count is not None:
                    write_oracle_json(
                        run_dir / "record-count-validation.json",
                        record_count_validation,
                    )
                validate_profile_correctness(
                    records,
                    selected_profile,
                    args.measurement_iterations_multiplier,
                    args.backend,
                )
                checks = []
                if not args.no_oracle_ledger:
                    checks.append(
                        update_determinism_ledger(
                            oracle_ledger_path, functional_report
                        )
                    )
                provenance = None
                if oracle_manifest_path is not None:
                    explicit = validate_against_oracle(
                        functional_report, load_oracle(oracle_manifest_path)
                    )
                    checks.append(explicit)
                    provenance = explicit["oracle_provenance"]
                oracle_validation = {
                    "status": "PASSED",
                    "report": str(functional_report_path),
                    "report_id": functional_report["report_id"],
                    "functional_id": functional_report["functional_id"],
                    "oracle_provenance": provenance,
                    "profile_hash_provenance": (
                        PROFILE_CORRECTNESS_HASH_PROVENANCE
                        if selected_profile in PROFILE_CORRECTNESS_HASHES
                        or (selected_profile, args.backend)
                        in PROFILE_BACKEND_CORRECTNESS_HASHES
                        else None
                    ),
                    "checks": checks,
                }
                write_oracle_json(
                    run_dir / "oracle-validation.json", oracle_validation
                )
            except OracleValidationError as exc:
                oracle_validation = {
                    "status": "FAILED",
                    "error": str(exc),
                    "oracle_provenance": None,
                }
                write_oracle_json(
                    run_dir / "oracle-validation.json", oracle_validation
                )
                raise
            legacy_composite_records = [
                record
                for record in records
                if str(record.get("name", "")).startswith("GameLoadComposite::")
                and isinstance(record.get("metadata"), dict)
                and record["metadata"].get("kind") == "game_load_composite"
                and record["metadata"].get("preset")
                in {
                    preset["guest_name"]
                    for preset in GAME_LOAD_LEGACY_PRESETS.values()
                }
            ]
            if legacy_composite_records:
                composite_work = validate_game_load_work(
                    game_load_work_from_records(legacy_composite_records),
                    legacy_composite_records,
                )
                composite_interactions = analyze_game_load_interactions(
                    legacy_composite_records
                )
        if args.host_telemetry != "off":
            if not telemetry_path.is_file():
                raise RuntimeError(
                    "xemu did not write requested NV2A host telemetry; use an instrumented build"
                )
            host_telemetry = validate_host_telemetry(
                json.loads(telemetry_path.read_text(encoding="utf-8")),
                args.host_telemetry,
                selected_profile,
                args.backend,
                role_config["features"],
                args.measurement_iterations_multiplier,
                args.experiment_role,
            )
            if composite_work and final_measurement_is_composite(records):
                host_telemetry["composite_assertions"] = (
                    validate_game_load_host_telemetry(
                        host_telemetry, composite_work, args.backend
                    )
                )
        status = "PASSED" if result.status == TestStatus.PASSED else "FAILED"
    except Exception as exc:
        if guest_watcher is not None and guest_watcher.failure is not None:
            status = "GUEST_VALIDATION_FAILED"
            message = guest_watcher.failure["message"]
            logging.error(message)
        elif isinstance(exc, LiveMarkerEvidenceError):
            status = "INFRASTRUCTURE_FAILED"
            message = str(exc)
            logging.error(message)
        elif isinstance(exc, (SameBackendNondeterminism, OracleValidationError)):
            status = "FUNCTIONAL_MISMATCH"
            message = str(exc)
            logging.error(message)
        elif isinstance(exc, (RecordCountMismatch, RecordContractError)):
            status = "FAILED"
            message = str(exc)
            logging.error(message)
        else:
            logging.exception("Suite infrastructure failed")
            message = str(exc)
    finally:
        wall_seconds = time.perf_counter() - start
        if args.vulkan_validation and (run_dir / "xemu.log").is_file():
            try:
                vulkan_validation = collect_vulkan_validation(run_dir, True)
            except RuntimeError as validation_error:
                status = "INFRASTRUCTURE_FAILED"
                message = str(validation_error)
                logging.error(message)
        os.environ.pop("XEMU_PERF_TELEMETRY_PATH", None)
        os.environ.pop("XEMU_PERF_TELEMETRY_LEVEL", None)
        os.environ.pop("XEMU_PERF_GUEST_MARKERS", None)
        os.environ.pop("XEMU_PERF_LIVE_MARKER_PATH", None)
        os.environ.pop("VK_LAYER_PATH", None)
        os.environ.pop("VK_INSTANCE_LAYERS", None)
        clear_vulkan_lab_counters()
        for name in xemu_environment:
            os.environ.pop(name, None)
        os.chdir(old_cwd)
        write_summary(
            run_dir,
            args.mode,
            profile_label,
            status,
            wall_seconds,
            build_info,
            removed,
            records,
            message,
            args.backend,
            args.scale,
            args.vsync,
            guest_iso if args.mode == "perf" else None,
            host_process,
            host_telemetry,
            guest_event_evidence,
            xemu_environment,
            vulkan_validation,
            vulkan_lab_counters,
            experiment,
            args.measurement_iterations_multiplier,
            args.memory_megabytes,
            game_load_config,
            composite_work,
            composite_interactions,
            oracle_validation,
            held_frame_capture_evidence,
            timed_frame_capture_evidence,
            build_cleanliness,
            expected_record_count=effective_expected_record_count,
            record_count_validation=record_count_validation,
            live_marker_compatibility=live_marker_compatibility,
            guest_evidence=guest_evidence,
        )

    print(f"Status: {status}")
    print(f"Evidence: {run_dir}")
    if records:
        for record in summarize_records(records):
            print(format_record_success(record))
    if message:
        print(f"Message: {message}")
    if args.vulkan_lab_counters:
        print(f"Timing eligibility: INELIGIBLE - {VULKAN_LAB_TIMING_WARNING}")
    if build_cleanliness["override_used"]:
        print(f"Timing eligibility: INELIGIBLE - {build_cleanliness['warning']}")
    return 0 if status == "PASSED" else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        raise SystemExit(main())
    except Exception as exc:
        logging.exception("Suite preflight failed")
        raise SystemExit(2) from exc
