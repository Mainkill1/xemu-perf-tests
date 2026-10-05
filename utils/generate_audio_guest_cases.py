#!/usr/bin/env python3
"""Compile the audio matrix into typed guest descriptors with explicit promotion."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from audio_torture_cases import build_cases, load_matrix, validate


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "src" / "generated" / "audio_case_catalog.inc"
EXECUTABLE_IDS = frozenset({"audio.vp_scaling.s16_mono.v001"})

FAMILIES = {
    "audio.ac97_dma": "kAc97Dma",
    "audio.vp_scaling": "kVpScaling",
    "audio.format_rate": "kFormatRate",
    "audio.pitch_resample": "kPitchResample",
    "audio.buffer_boundary": "kBufferBoundary",
    "audio.streaming_dma": "kStreamingDma",
    "audio.mixbin_fanout": "kMixbinFanout",
    "audio.filter_envelope": "kFilterEnvelope",
    "audio.hrtf_3d": "kHrtf3d",
    "audio.voice_modes": "kVoiceModes",
    "audio.voice_control": "kVoiceControl",
    "audio.voice_churn": "kVoiceChurn",
    "audio.memory_locality": "kMemoryLocality",
    "audio.gp_ep": "kGpEp",
    "audio.everything_max": "kEverythingMax",
}
FORMATS = {"u8": "kU8", "s16": "kS16", "s24": "kS24", "s32": "kS32", "adpcm": "kAdpcm"}
CONTAINERS = {"b8": "kB8", "b16": "kB16", "b32": "kB32", "adpcm": "kAdpcm"}
LAYOUTS = {"shared": "kShared", "contiguous_unique": "kContiguousUnique", "scattered": "kScattered"}
SIGNALS = {"near_nyquist_045": "kNearNyquist045", "near_nyquist_049": "kNearNyquist049"}
CONTROLS = {"lock_reconfigure": "kLockReconfigure", "on_off": "kOnOff",
            "pause_resume": "kPauseResume", "release": "kRelease"}
PIPELINES = {"vp_only": "kVpOnly", "vp_gp": "kVpGp",
             "vp_gp_ep_stereo": "kVpGpEpStereo", "vp_gp_ep_surround": "kVpGpEpSurround"}
MODE_FLAGS = {"stream": "kVoiceModeStream", "loop": "kVoiceModeLoop",
              "linked": "kVoiceModeLinked", "persist": "kVoiceModePersist",
              "clear_mix": "kVoiceModeClearMix", "multipass": "kVoiceModeMultipass"}
PARAMETERS = frozenset({
    "sample_format", "container_format", "source_layout", "signal", "channels",
    "sample_rate_hz", "voice_count", "audio_frames", "mixbin_fanout", "refill_bytes",
    "buffer_samples", "refill_samples", "three_d_voice_count", "allocation_attempt_count",
    "tone_frequency_hz", "control_sequence", "pipeline_mode", "enable_3d",
    "enable_hrtf", "enable_filter", "mutate_voice_state", "mixed_formats", "mixed_rates",
    "expected_allocation_failure", *MODE_FLAGS,
})


def _enum(name: str, mapping: dict[str, str], value: str) -> str:
    try:
        return f"{name}::{mapping[value]}"
    except KeyError as error:
        raise ValueError(f"unsupported {name} value: {value}") from error


def _boolean(value: object, name: str) -> str:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return "true" if value else "false"


def _number(value: object, name: str) -> str:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > 0xFFFFFFFF:
        raise ValueError(f"{name} must be an unsigned 32-bit integer")
    return str(value)


def _workload(case: dict) -> str:
    params = case["params"]
    unknown = set(params) - PARAMETERS
    if unknown:
        raise ValueError(f"unmapped parameters in {case['id']}: {sorted(unknown)}")
    flags = [flag for key, flag in MODE_FLAGS.items() if params.get(key, False)]
    for key in MODE_FLAGS:
        if key in params:
            _boolean(params[key], key)
    mode_flags = " | ".join(flags) if flags else "kVoiceModeNone"
    voice_count = params.get("voice_count", 0 if case["backend"] == "ac97_dma" else 1)
    attempts = params.get("allocation_attempt_count", voice_count)
    fields = [
        _enum("SampleFormat", FORMATS, params.get("sample_format", "s16")),
        _enum("ContainerFormat", CONTAINERS, params["container_format"])
        if "container_format" in params else "ContainerFormat::kUnspecified",
        _enum("SourceLayout", LAYOUTS, params.get("source_layout", "shared")),
        _enum("SignalKind", SIGNALS, params["signal"])
        if "signal" in params else "SignalKind::kSilence",
        _number(params.get("channels", 2), "channels"),
        _number(params.get("sample_rate_hz", 48000), "sample_rate_hz"),
        _number(voice_count, "voice_count"),
        _number(params.get("audio_frames", 1), "audio_frames"),
        _number(params.get("mixbin_fanout", 1), "mixbin_fanout"),
        _number(params.get("refill_bytes", 0), "refill_bytes"),
        _number(params.get("buffer_samples", 0), "buffer_samples"),
        _number(params.get("refill_samples", 0), "refill_samples"),
        _number(params.get("three_d_voice_count",
                           voice_count if params.get("enable_3d") or params.get("enable_hrtf") else 0),
                "three_d_voice_count"),
        _number(attempts, "allocation_attempt_count"),
        _number(params.get("tone_frequency_hz", 1000), "tone_frequency_hz"),
        mode_flags,
        _enum("VoiceControlSequence", CONTROLS, params["control_sequence"])
        if "control_sequence" in params else "VoiceControlSequence::kNone",
        _enum("PipelineMode", PIPELINES, params.get("pipeline_mode", "vp_only")),
        *(_boolean(params.get(key, False), key) for key in (
            "enable_3d", "enable_hrtf", "enable_filter", "mutate_voice_state",
            "mixed_formats", "mixed_rates")),
    ]
    return "WorkloadSpec{" + ", ".join(fields) + "}"


def generate() -> str:
    matrix = load_matrix()
    cases = build_cases(matrix)
    validate(matrix, cases)
    if len(cases) != 138 or len(FAMILIES) != 15:
        raise ValueError("audio case count or family count changed; review the guest contract")
    if not EXECUTABLE_IDS <= {case["id"] for case in cases}:
        raise ValueError("an executable audio case is missing from the matrix")
    manifest = json.dumps(cases, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(manifest.encode("utf-8")).hexdigest()
    lines = [
        "// Generated by utils/generate_audio_guest_cases.py; do not edit.",
        f'inline constexpr char kAudioCaseManifestDigest[] = "{digest}";',
        "inline constexpr AudioCaseDescriptor kAudioCases[] = {",
    ]
    for case in cases:
        family = FAMILIES.get(case["family"])
        if family is None:
            raise ValueError(f"unmapped family in {case['id']}: {case['family']}")
        backend = {"ac97_dma": "kAc97Dma", "mcpx_apu_raw": "kMcpxApuRaw"}.get(case["backend"])
        if backend is None:
            raise ValueError(f"unmapped backend in {case['id']}: {case['backend']}")
        params = case["params"]
        denial = _boolean(params.get("expected_allocation_failure", False), "expected_allocation_failure")
        attempts = _number(params.get("allocation_attempt_count", params.get("voice_count", 0)),
                           "allocation_attempt_count")
        optional = "true" if case["family"] == "audio.everything_max" else "false"
        paths = json.dumps(case["required_paths"], separators=(",", ":"), ensure_ascii=True)
        lines.append(
            "  {" + ", ".join((
                json.dumps(case["id"]), f"AudioFamily::{family}", f"BackendKind::{backend}",
                _workload(case), denial, attempts, optional, f"OracleProfile::{family}",
                json.dumps(paths), "true" if case["id"] in EXECUTABLE_IDS else "false",
            )) + "},"
        )
    lines.append("};")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    rendered = generate().encode("utf-8")
    if args.check:
        if not args.output.exists() or args.output.read_bytes() != rendered:
            print(f"stale generated audio guest cases: {args.output}", file=sys.stderr)
            return 1
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(rendered)
    print(f"generated 138 audio descriptors: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
