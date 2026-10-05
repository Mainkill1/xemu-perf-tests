#!/usr/bin/env python3
"""Expand and validate the planned audio torture microbenchmark cases.

This utility does not register catalog leaves. It turns the machine-readable
framework into a deterministic proposed leaf set so implementation work can
happen without silently changing workload semantics.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "resources" / "audio_torture_matrix.json"
ID_RE = re.compile(r"^[a-z0-9_.]+$")


def load_matrix(path: Path = MATRIX_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _case(case_id: str, family: str, backend: str, **params) -> dict:
    return {
        "id": case_id,
        "family": family,
        "backend": backend,
        "implementation_state": "planned",
        "params": params,
    }


def build_cases(matrix: dict) -> list[dict]:
    axes = matrix["axes"]
    curated = matrix["curated_case_sets"]
    cases: list[dict] = []

    for refill_bytes in axes["ac97_refill_bytes"]:
        cases.append(_case(
            f"audio.ac97_dma.refill_{refill_bytes}b",
            "audio.ac97_dma", "ac97_dma",
            sample_format="s16", channels=2, sample_rate_hz=48000,
            refill_bytes=refill_bytes,
        ))
    for layout in axes["memory_layouts"]:
        cases.append(_case(
            f"audio.ac97_dma.layout_{layout}",
            "audio.ac97_dma", "ac97_dma",
            sample_format="s16", channels=2, sample_rate_hz=48000,
            source_layout=layout,
        ))

    for channels, label in ((1, "mono"), (2, "stereo")):
        for voices in curated["vp_scaling_voice_counts"]:
            cases.append(_case(
                f"audio.vp_scaling.s16_{label}.v{voices:03d}",
                "audio.vp_scaling", "mcpx_apu_raw",
                sample_format="s16", channels=channels,
                sample_rate_hz=48000, voice_count=voices,
                source_layout="shared",
            ))

    container_by_format = {
        "u8": "b8",
        "s16": "b16",
        "s24": "b32",
        "s32": "b32",
        "adpcm": "adpcm",
    }
    for sample_format in ("u8", "s16", "s24", "s32", "adpcm"):
        for channels, label in ((1, "mono"), (2, "stereo")):
            for voices in curated["format_voice_counts"]:
                cases.append(_case(
                    f"audio.format_rate.{sample_format}_{label}.v{voices:03d}",
                    "audio.format_rate", "mcpx_apu_raw",
                    sample_format=sample_format,
                    container_format=container_by_format[sample_format],
                    channels=channels, sample_rate_hz=48000,
                    voice_count=voices, source_layout="shared",
                ))

    rate_voices = curated["rate_probe_voice_count"]
    for rate in axes["source_rates_hz"]:
        cases.append(_case(
            f"audio.format_rate.s16_mono.v{rate_voices:03d}.r{rate}",
            "audio.format_rate", "mcpx_apu_raw",
            sample_format="s16", channels=1, sample_rate_hz=rate,
            voice_count=rate_voices, source_layout="shared",
        ))

    for signal in ("near_nyquist_045", "near_nyquist_049"):
        cases.append(_case(
            f"audio.pitch_resample.{signal}",
            "audio.pitch_resample", "mcpx_apu_raw",
            sample_format="s16", channels=1, sample_rate_hz=48000,
            voice_count=64, signal=signal,
        ))

    for samples in axes["vp_buffer_samples"]:
        cases.append(_case(
            f"audio.buffer_boundary.s{samples:03d}",
            "audio.buffer_boundary", "mcpx_apu_raw",
            sample_format="s16", channels=1, sample_rate_hz=48000,
            voice_count=64, buffer_samples=samples,
            source_layout="scattered",
        ))

    for entry in curated["streaming_cases"]:
        voices = entry["voice_count"]
        refill = entry["refill_samples"]
        cases.append(_case(
            f"audio.streaming_dma.v{voices:03d}.s{refill:03d}",
            "audio.streaming_dma", "mcpx_apu_raw",
            sample_format="s16", channels=1, sample_rate_hz=48000,
            voice_count=voices, refill_samples=refill,
            source_layout="scattered",
        ))

    for fanout in axes["mixbin_fanout"]:
        cases.append(_case(
            f"audio.mixbin_fanout.v256.f{fanout}",
            "audio.mixbin_fanout", "mcpx_apu_raw",
            sample_format="s16", channels=1, sample_rate_hz=48000,
            voice_count=256, mixbin_fanout=fanout,
        ))

    for voices in curated["filter_voice_counts"]:
        cases.append(_case(
            f"audio.filter_envelope.v{voices:03d}",
            "audio.filter_envelope", "mcpx_apu_raw",
            sample_format="s16", channels=1, sample_rate_hz=48000,
            voice_count=voices, enable_filter=True, mutate_voice_state=True,
        ))

    for voices in curated["hrtf_voice_counts"]:
        cases.append(_case(
            f"audio.hrtf_3d.v{voices:03d}",
            "audio.hrtf_3d", "mcpx_apu_raw",
            sample_format="s16", channels=1, sample_rate_hz=48000,
            voice_count=voices, enable_3d=True, enable_hrtf=True,
            mutate_voice_state=True,
        ))

    voice_mode_params = {
        "buffer_linear": {},
        "stream_linear": {"stream": True},
        "buffer_loop": {"loop": True},
        "stream_loop": {"stream": True, "loop": True},
        "linked": {"linked": True},
        "persist": {"persist": True},
        "clear_mix": {"clear_mix": True},
        "multipass": {"multipass": True},
    }
    for mode in curated["voice_modes"]:
        cases.append(_case(
            f"audio.voice_modes.{mode}",
            "audio.voice_modes", "mcpx_apu_raw",
            sample_format="s16", channels=1, sample_rate_hz=48000,
            voice_count=64, **voice_mode_params[mode],
        ))

    for control in curated["voice_control"]:
        cases.append(_case(
            f"audio.voice_control.{control}",
            "audio.voice_control", "mcpx_apu_raw",
            sample_format="s16", channels=1, sample_rate_hz=48000,
            voice_count=64, control_sequence=control,
        ))

    for voices in curated["churn_voice_counts"]:
        cases.append(_case(
            f"audio.voice_churn.v{voices:03d}",
            "audio.voice_churn", "mcpx_apu_raw",
            sample_format="s16", channels=1, sample_rate_hz=48000,
            voice_count=voices, mutate_voice_state=True,
        ))

    for layout in axes["memory_layouts"]:
        cases.append(_case(
            f"audio.memory_locality.v256.{layout}",
            "audio.memory_locality", "mcpx_apu_raw",
            sample_format="s16", channels=1, sample_rate_hz=48000,
            voice_count=256, source_layout=layout,
        ))

    for mode in curated["gp_ep_modes"]:
        cases.append(_case(
            f"audio.gp_ep.{mode}",
            "audio.gp_ep", "mcpx_apu_raw",
            sample_format="s16", channels=2, sample_rate_hz=48000,
            voice_count=64, pipeline_mode=mode,
        ))

    cases.append(_case(
        "audio.everything_max.ceiling",
        "audio.everything_max", "mcpx_apu_raw",
        voice_count=256, three_d_voice_count=64,
        mixed_formats=True, mixed_rates=True, source_layout="scattered",
        mixbin_fanout=8, enable_hrtf=True, enable_filter=True,
        mutate_voice_state=True, pipeline_mode="vp_gp_ep_surround",
    ))
    return cases


def validate(matrix: dict, cases: list[dict]) -> None:
    family_by_id = {f["id"]: f for f in matrix["families"]}
    backend_by_id = matrix["backends"]
    ids: set[str] = set()

    for case in cases:
        case_id = case["id"]
        if case.get("implementation_state") != "planned":
            raise ValueError(f"planned case claims executable coverage: {case_id}")
        if case_id in ids:
            raise ValueError(f"duplicate planned case id: {case_id}")
        if not ID_RE.fullmatch(case_id):
            raise ValueError(f"invalid planned case id: {case_id}")
        ids.add(case_id)

        family = family_by_id.get(case["family"])
        if not family:
            raise ValueError(f"unknown family for {case_id}: {case['family']}")
        if case["backend"] != family["backend"]:
            raise ValueError(f"backend mismatch for {case_id}")
        if case["backend"] not in backend_by_id:
            raise ValueError(f"unknown backend for {case_id}")

        params = case["params"]
        voices = params.get("voice_count", 0)
        if case["backend"] == "mcpx_apu_raw" and voices > matrix["ground_truth"]["mcpx_apu"]["max_voices"]:
            raise ValueError(f"voice count exceeds MCPX limit for {case_id}")
        three_d_voices = params.get(
            "three_d_voice_count",
            voices if params.get("enable_3d") or params.get("enable_hrtf") else 0,
        )
        if three_d_voices > matrix["ground_truth"]["mcpx_apu"]["max_3d_voices"]:
            raise ValueError(f"3D/HRTF voice count exceeds MCPX limit for {case_id}")

        if case["backend"] == "mcpx_apu_raw":
            sample_format = params.get("sample_format")
            if sample_format and sample_format not in matrix["ground_truth"]["mcpx_apu"]["formats"]:
                raise ValueError(f"unsupported planned VP sample format for {case_id}: {sample_format}")

        if case["backend"] == "ac97_dma":
            supported = backend_by_id["ac97_dma"]["supported_formats"]
            requested_format = {
                "sample_format": params.get("sample_format"),
                "channels": params.get("channels"),
                "sample_rate_hz": params.get("sample_rate_hz"),
            }
            if requested_format not in supported:
                raise ValueError(f"AC97 case overclaims NXDK XAudio format for {case_id}")
            if any(key in params for key in (
                "voice_count", "container_format", "enable_3d", "enable_hrtf",
                "mixbin_fanout", "three_d_voice_count", "control_sequence",
                "pipeline_mode", "enable_filter", "mutate_voice_state",
            )):
                raise ValueError(f"AC97 case contains APU-only parameters: {case_id}")


    gap = matrix["known_gaps"]["get_voice_position"]
    if gap["normal_gate_allowed"]:
        raise ValueError("GET_VOICE_POSITION must remain outside the normal gate while xemu asserts")
    if any(case["params"].get("control_sequence") == "get_voice_position" for case in cases):
        raise ValueError("GET_VOICE_POSITION is a known-gap probe, not a normal planned case")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="validate the planned case set")
    parser.add_argument("--json", action="store_true", help="print expanded planned cases")
    args = parser.parse_args()

    matrix = load_matrix()
    cases = build_cases(matrix)
    validate(matrix, cases)

    if args.json:
        print(json.dumps({"case_count": len(cases), "cases": cases}, indent=2))
    else:
        counts: dict[str, int] = {}
        for case in cases:
            counts[case["family"]] = counts.get(case["family"], 0) + 1
        print(f"audio torture planned cases: {len(cases)}")
        for family in sorted(counts):
            print(f"  {family}: {counts[family]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
