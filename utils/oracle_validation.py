#!/usr/bin/env python3
"""Functional hash reports, consensus, and cross-run determinism gates."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any


REGRESSION_CONSENSUS = "REGRESSION_CONSENSUS"
REGRESSION_ONLY = "REGRESSION_ONLY"
RETAIL_XBOX = "RETAIL_XBOX"
ORACLE_PROVENANCE_CLASSES = frozenset((REGRESSION_CONSENSUS, RETAIL_XBOX))
REPORT_KIND = "xemu_functional_hash_report"
MANIFEST_KIND = "xemu_functional_hash_oracle"
SCHEMA_VERSION = 1
_HEX_RE = re.compile(r"^[0-9a-fA-F]+$")
CHECKSUM_PAIR_OPTIONAL_KINDS = frozenset(
    {
        # RepeatedDisplay is a scanout/display-state test. Its framebuffer hash
        # is the functional oracle; the guest's result_checksum is diagnostic.
        "game_load_composite_repeated_display",
    }
)


class OracleValidationError(RuntimeError):
    """The supplied oracle or functional output is invalid."""


class SameBackendNondeterminism(OracleValidationError):
    """Identical guest work produced different hashes on one backend."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def json_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_guest_results(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8", errors="strict")
    parsed = json.loads(re.sub(r",\s*\]", "\n]", raw))
    if not isinstance(parsed, list) or not parsed:
        raise OracleValidationError("guest results must be a non-empty JSON list")
    if not all(isinstance(record, dict) for record in parsed):
        raise OracleValidationError("every guest result must be an object")
    return parsed


def _integer(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise OracleValidationError(f"{field} must be a non-negative integer")
    return value


def _hash(value: Any, field: str, widths: tuple[int, ...]) -> str:
    if isinstance(value, int) and not isinstance(value, bool):
        if value < 0:
            raise OracleValidationError(f"{field} must not be negative")
        width = max(widths)
        result = f"{value:0{width}x}"
    elif isinstance(value, str):
        result = value.strip().lower()
        if result.startswith("0x"):
            result = result[2:]
    else:
        raise OracleValidationError(f"{field} must be a hexadecimal string or integer")
    if len(result) not in widths or not _HEX_RE.fullmatch(result):
        expected = " or ".join(str(width) for width in widths)
        raise OracleValidationError(f"{field} must contain exactly {expected} hex digits")
    return result


def _normalize_kat_node(value: Any, field: str) -> Any:
    if isinstance(value, dict):
        normalized = {
            key: _normalize_kat_node(item, f"{field}.{key}")
            for key, item in sorted(value.items())
        }
        for key, item in normalized.items():
            counterpart = None
            if key == "expected":
                counterpart = "actual"
            elif key.startswith("expected_"):
                counterpart = "actual_" + key.removeprefix("expected_")
            elif key.endswith("_expected"):
                counterpart = key.removesuffix("_expected") + "_actual"
            if counterpart in normalized and normalized[counterpart] != item:
                raise OracleValidationError(
                    f"{field} expected/actual KAT mismatch: "
                    f"{item!r} != {normalized[counterpart]!r}"
                )
        return normalized
    if isinstance(value, list):
        return [
            _normalize_kat_node(item, f"{field}[{index}]")
            for index, item in enumerate(value)
        ]
    if value is None or isinstance(value, (bool, int, str)):
        return value
    raise OracleValidationError(f"{field} contains an unsupported KAT value")


def record_kats(metadata: dict) -> dict[str, Any]:
    selected = {
        key: value
        for key, value in metadata.items()
        if "kat" in key.lower()
        or key.lower().endswith("_final")
        or key.lower().endswith("_final_state")
    }
    return _normalize_kat_node(selected, "metadata.kats")


def record_hashes(record: dict) -> dict[str, Any]:
    name = record.get("name")
    if not isinstance(name, str) or not name:
        raise OracleValidationError("result record is missing name")
    hashes = {
        "framebuffer_fnv1a64": _hash(
            record.get("framebuffer_fnv1a64"),
            f"{name}.framebuffer_fnv1a64",
            (16,),
        )
    }
    metadata = record.get("metadata")
    if isinstance(metadata, dict):
        expected_frame = metadata.get("expected_framebuffer_fnv1a64")
        if expected_frame is not None:
            normalized_expected_frame = _hash(
                expected_frame,
                f"{name}.expected_framebuffer_fnv1a64",
                (16,),
            )
            if normalized_expected_frame != hashes["framebuffer_fnv1a64"]:
                raise OracleValidationError(
                    f"{name} framebuffer hash does not match its metadata oracle"
                )
        work = metadata.get("work_checksum")
        result = metadata.get("result_checksum")
        checksum_pair_optional = (
            metadata.get("kind") in CHECKSUM_PAIR_OPTIONAL_KINDS
        )
        if (work is None) != (result is None) and not checksum_pair_optional:
            raise OracleValidationError(
                f"{name} must provide both work_checksum and result_checksum"
            )
        if work is not None and result is not None:
            hashes["work_checksum"] = _hash(
                work, f"{name}.work_checksum", (8,)
            )
            hashes["result_checksum"] = _hash(
                result, f"{name}.result_checksum", (8,)
            )
        kats = record_kats(metadata)
        if kats:
            hashes["kats"] = kats
    return hashes


def record_comparison_policy(record: dict) -> dict[str, Any] | None:
    """Describe guest-declared observations that cannot be deterministic oracles."""

    metadata = record.get("metadata")
    if not isinstance(metadata, dict):
        return None
    excluded = []
    if metadata.get("framebuffer_comparison_eligible") is False:
        excluded.append("framebuffer_fnv1a64")
    if metadata.get("oracle_applicable") is False:
        for name in record_kats(metadata):
            # Source KATs validate the deterministic bytes written by the guest.
            # Other KATs observe rendered/read-back state and share the guest's
            # explicit oracle-applicability contract.
            if not name.startswith("source_"):
                excluded.append(f"kats.{name}")
    if not excluded:
        return None
    reason = metadata.get("framebuffer_comparison_reason")
    if not isinstance(reason, str) or not reason:
        raise OracleValidationError(
            f"{record.get('name')} excludes observations without a comparison reason"
        )
    return {
        "excluded_observations": sorted(excluded),
        "reason": reason,
    }


def eligible_record_hashes(record: dict) -> tuple[dict[str, Any], dict | None]:
    hashes = record_hashes(record)
    policy = record_comparison_policy(record)
    if policy is None:
        return hashes, None
    for observation in policy["excluded_observations"]:
        if observation == "framebuffer_fnv1a64":
            hashes.pop(observation, None)
            continue
        prefix = "kats."
        if observation.startswith(prefix):
            kats = hashes.get("kats")
            if isinstance(kats, dict):
                kats.pop(observation.removeprefix(prefix), None)
                if not kats:
                    hashes.pop("kats", None)
    if not hashes:
        raise OracleValidationError(
            f"{record.get('name')} has no eligible functional observations"
        )
    return hashes, policy


def record_internal_oracle(record: dict) -> dict[str, Any] | None:
    metadata = record.get("metadata")
    if not isinstance(metadata, dict) or "oracle_status" not in metadata:
        return None
    name = record.get("name")
    status = metadata.get("oracle_status")
    if not isinstance(status, str) or status.upper() not in ("PASS", "FAIL"):
        raise OracleValidationError(f"{name}.oracle_status must be PASS or FAIL")
    assessment = {"status": status.upper()}
    provenance = metadata.get("oracle_provenance")
    if provenance is not None:
        if not isinstance(provenance, str) or not provenance:
            raise OracleValidationError(f"{name}.oracle_provenance is invalid")
        assessment["provenance"] = provenance
    failure_count = metadata.get("oracle_failure_count")
    if failure_count is not None:
        assessment["failure_count"] = _integer(
            failure_count, f"{name}.oracle_failure_count"
        )
    reason = metadata.get("oracle_failure_reason")
    if reason is not None:
        if not isinstance(reason, str) or not reason:
            raise OracleValidationError(f"{name}.oracle_failure_reason is invalid")
        assessment["failure_reason"] = reason
    return assessment


def record_contract(record: dict) -> dict[str, Any]:
    name = record.get("name")
    contract = {
        "iterations": _integer(record.get("iterations"), f"{name}.iterations"),
        "sample_count": _integer(
            record.get("sample_count"), f"{name}.sample_count"
        ),
        "measurement_iterations_multiplier": _integer(
            record.get("measurement_iterations_multiplier"),
            f"{name}.measurement_iterations_multiplier",
        ),
        "warmup_iterations": _integer(
            record.get("warmup_iterations"), f"{name}.warmup_iterations"
        ),
    }
    completion = record.get("gpu_completion_mode")
    if not isinstance(completion, str) or not completion:
        raise OracleValidationError(f"{name}.gpu_completion_mode is required")
    contract["gpu_completion_mode"] = completion
    metadata = record.get("metadata")
    if isinstance(metadata, dict) and "stage_order" in metadata:
        stage_order = metadata["stage_order"]
        if (
            not isinstance(stage_order, list)
            or not stage_order
            or not all(isinstance(stage, str) and stage for stage in stage_order)
        ):
            raise OracleValidationError(f"{name}.stage_order is invalid")
        contract["stage_order"] = stage_order
    return contract


def normalized_records(records: list[dict]) -> list[dict]:
    normalized = []
    for record in records:
        hashes, comparison_policy = eligible_record_hashes(record)
        item = {
            "test_id": record.get("name"),
            "contract": record_contract(record),
            "hashes": hashes,
        }
        if comparison_policy is not None:
            item["comparison_policy"] = comparison_policy
        internal_oracle = record_internal_oracle(record)
        if internal_oracle is not None:
            item["internal_oracle"] = internal_oracle
        normalized.append(item)
    normalized.sort(key=lambda item: (item["test_id"], canonical_json(item["contract"])))
    identities = {
        canonical_json({"test_id": item["test_id"], "contract": item["contract"]})
        for item in normalized
    }
    if len(identities) != len(normalized):
        raise OracleValidationError("functional report contains a duplicate result record")
    return normalized


def build_report(
    records: list[dict],
    *,
    guest_image_sha256: str,
    job_config: dict,
    source_backend: str,
    source_type: str,
    observation_id: str,
    build: dict | None = None,
    surface_scale: int | None = None,
    hardware: dict | None = None,
) -> dict:
    guest_hash = _hash(guest_image_sha256, "guest_image_sha256", (64,))
    if source_type not in ("XEMU", "RETAIL_XBOX"):
        raise OracleValidationError("source_type must be XEMU or RETAIL_XBOX")
    if not isinstance(source_backend, str) or not source_backend:
        raise OracleValidationError("source_backend is required")
    if not isinstance(observation_id, str) or not observation_id:
        raise OracleValidationError("observation_id is required")
    stable = {
        "schema_version": SCHEMA_VERSION,
        "kind": REPORT_KIND,
        "oracle_provenance": None,
        "source_type": source_type,
        "source_backend": source_backend,
        "guest_image_sha256": guest_hash,
        "job_sha256": json_sha256(job_config),
        "records": normalized_records(records),
    }
    report = dict(stable)
    report["functional_id"] = json_sha256(stable)
    report["observation_id"] = observation_id
    report["surface_scale"] = surface_scale
    report["build"] = build or None
    report["hardware"] = hardware or None
    report["report_id"] = json_sha256(
        {
            "functional_id": report["functional_id"],
            "observation_id": observation_id,
            "surface_scale": report["surface_scale"],
            "build": report["build"],
            "hardware": report["hardware"],
        }
    )
    return report


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OracleValidationError(f"could not read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise OracleValidationError(f"{path} must contain a JSON object")
    return value


def _validate_report_shape(report: dict) -> None:
    if report.get("schema_version") != SCHEMA_VERSION or report.get("kind") != REPORT_KIND:
        raise OracleValidationError("unsupported functional hash report")
    guest_hash = _hash(report.get("guest_image_sha256"), "guest_image_sha256", (64,))
    job_hash = _hash(report.get("job_sha256"), "job_sha256", (64,))
    report_id = _hash(report.get("report_id"), "report_id", (64,))
    functional_id = _hash(report.get("functional_id"), "functional_id", (64,))
    observation_id = report.get("observation_id")
    if not isinstance(observation_id, str) or not observation_id:
        raise OracleValidationError("functional report observation_id is required")
    source_type = report.get("source_type")
    if source_type not in ("XEMU", "RETAIL_XBOX"):
        raise OracleValidationError("functional report source_type is invalid")
    source_backend = report.get("source_backend")
    if not isinstance(source_backend, str) or not source_backend:
        raise OracleValidationError("functional report source_backend is required")
    provenance = report.get("oracle_provenance")
    if provenance is not None:
        raise OracleValidationError("raw functional report cannot declare oracle provenance")
    records = report.get("records")
    _validate_normalized_records(records)
    stable = {
        "schema_version": SCHEMA_VERSION,
        "kind": REPORT_KIND,
        "oracle_provenance": provenance,
        "source_type": source_type,
        "source_backend": source_backend,
        "guest_image_sha256": guest_hash,
        "job_sha256": job_hash,
        "records": records,
    }
    expected_functional_id = json_sha256(stable)
    if functional_id != expected_functional_id:
        raise OracleValidationError("functional report functional_id does not match content")
    expected_report_id = json_sha256(
        {
            "functional_id": functional_id,
            "observation_id": observation_id,
            "surface_scale": report.get("surface_scale"),
            "build": report.get("build"),
            "hardware": report.get("hardware"),
        }
    )
    if report_id != expected_report_id:
        raise OracleValidationError("functional report report_id does not match content")


def _validate_normalized_records(records: Any) -> None:
    if not isinstance(records, list) or not records:
        raise OracleValidationError("functional hash data has no records")
    identities = set()
    for record in records:
        if not isinstance(record, dict):
            raise OracleValidationError("functional report record must be an object")
        test_id = record.get("test_id")
        contract = record.get("contract")
        hashes = record.get("hashes")
        if not isinstance(test_id, str) or not test_id:
            raise OracleValidationError("functional report record test_id is required")
        if not isinstance(contract, dict) or not isinstance(hashes, dict):
            raise OracleValidationError(f"{test_id} contract and hashes are required")
        expected_contract_fields = {
            "iterations",
            "sample_count",
            "measurement_iterations_multiplier",
            "warmup_iterations",
            "gpu_completion_mode",
        }
        if set(contract) not in (
            expected_contract_fields,
            expected_contract_fields | {"stage_order"},
        ):
            raise OracleValidationError(f"{test_id} fixed-work contract is incomplete")
        for field in expected_contract_fields - {"gpu_completion_mode"}:
            _integer(contract[field], f"{test_id}.{field}")
        if not isinstance(contract["gpu_completion_mode"], str) or not contract["gpu_completion_mode"]:
            raise OracleValidationError(f"{test_id}.gpu_completion_mode is required")
        if "stage_order" in contract and (
            not isinstance(contract["stage_order"], list)
            or not contract["stage_order"]
            or not all(
                isinstance(stage, str) and stage for stage in contract["stage_order"]
            )
        ):
            raise OracleValidationError(f"{test_id}.stage_order is invalid")
        identity = canonical_json({"test_id": test_id, "contract": contract})
        if identity in identities:
            raise OracleValidationError("functional report contains a duplicate result record")
        identities.add(identity)
        comparison_policy = record.get("comparison_policy")
        if comparison_policy is not None:
            if (
                not isinstance(comparison_policy, dict)
                or set(comparison_policy)
                != {"excluded_observations", "reason"}
                or not isinstance(comparison_policy["excluded_observations"], list)
                or not comparison_policy["excluded_observations"]
                or not all(
                    isinstance(value, str)
                    and (
                        value == "framebuffer_fnv1a64"
                        or (value.startswith("kats.") and len(value) > len("kats."))
                    )
                    for value in comparison_policy["excluded_observations"]
                )
                or not isinstance(comparison_policy["reason"], str)
                or not comparison_policy["reason"]
            ):
                raise OracleValidationError(
                    f"{test_id}.comparison_policy is invalid"
                )
        excluded = set(
            comparison_policy["excluded_observations"]
            if comparison_policy is not None
            else ()
        )
        if "framebuffer_fnv1a64" in excluded:
            if "framebuffer_fnv1a64" in hashes:
                raise OracleValidationError(
                    f"{test_id} retains an excluded framebuffer observation"
                )
        else:
            _hash(
                hashes.get("framebuffer_fnv1a64"),
                f"{test_id}.framebuffer_fnv1a64",
                (16,),
            )
        if ("work_checksum" in hashes) != ("result_checksum" in hashes):
            raise OracleValidationError(
                f"{test_id} must provide both work_checksum and result_checksum"
            )
        if "work_checksum" in hashes:
            _hash(hashes["work_checksum"], f"{test_id}.work_checksum", (8,))
            _hash(hashes["result_checksum"], f"{test_id}.result_checksum", (8,))
        unexpected_hash_fields = set(hashes) - {
            "framebuffer_fnv1a64",
            "work_checksum",
            "result_checksum",
            "kats",
        }
        if unexpected_hash_fields:
            raise OracleValidationError(
                f"{test_id} contains unsupported hash fields: "
                + ", ".join(sorted(unexpected_hash_fields))
            )
        if "kats" in hashes:
            kats = hashes["kats"]
            if not isinstance(kats, dict) or not kats:
                raise OracleValidationError(f"{test_id}.kats must be a non-empty object")
            _normalize_kat_node(kats, f"{test_id}.kats")
        for observation in excluded:
            if observation.startswith("kats.") and observation.removeprefix("kats.") in hashes.get("kats", {}):
                raise OracleValidationError(
                    f"{test_id} retains excluded observation {observation}"
                )
        internal_oracle = record.get("internal_oracle")
        if internal_oracle is not None:
            if not isinstance(internal_oracle, dict):
                raise OracleValidationError(
                    f"{test_id}.internal_oracle must be an object"
                )
            if internal_oracle.get("status") not in ("PASS", "FAIL"):
                raise OracleValidationError(
                    f"{test_id}.internal_oracle status must be PASS or FAIL"
                )
            if "failure_count" in internal_oracle:
                _integer(
                    internal_oracle["failure_count"],
                    f"{test_id}.internal_oracle.failure_count",
                )
            for field in ("provenance", "failure_reason"):
                if field in internal_oracle and (
                    not isinstance(internal_oracle[field], str)
                    or not internal_oracle[field]
                ):
                    raise OracleValidationError(
                        f"{test_id}.internal_oracle.{field} is invalid"
                    )


# The v1 normalized report retains the applicability flags as these two
# exclusions, rather than retaining the guest metadata itself. Restrict the
# compatibility rule to the two inspected S3TC producers: their failure count
# comes exclusively from the explicitly excluded framebuffer/tile readback.
_S3TC_DIAGNOSTIC_RECORDS = frozenset({
    "GameLoadComposite::10-S3tcSyncFactor-02-Dxt1SameAddressQueued",
    "GameLoadComposite::10-S3tcSyncFactor-06-Rgba8SameAddressQueued",
})
_S3TC_DIAGNOSTIC_REASON = (
    "unsynchronized same-address writes have no defined per-draw source generation"
)


def comparison_records(records: list[dict]) -> list[dict]:
    """Return a comparison-only view; never rewrite sealed report identities."""
    projected = json.loads(json.dumps(records))
    for record in projected:
        internal = record.get("internal_oracle", {})
        if internal.get("status") == "FAIL":
            raise OracleValidationError(
                f"{record['test_id']}.internal_oracle.status is FAIL"
            )
        policy = record.get("comparison_policy", {})
        if (
            record["test_id"] in _S3TC_DIAGNOSTIC_RECORDS
            and policy.get("reason") == _S3TC_DIAGNOSTIC_REASON
            and set(policy.get("excluded_observations", []))
                == {"framebuffer_fnv1a64", "kats.tile_center_kat"}
            and internal.get("provenance") == "regression_only"
        ):
            internal.pop("failure_count", None)
    return projected


def first_difference(expected: Any, actual: Any, path: str = "records") -> str | None:
    """Identify the first differing field without dumping the entire report."""
    if type(expected) is not type(actual):
        return path
    if isinstance(expected, dict):
        for key in sorted(set(expected) | set(actual)):
            child = f"{path}.{key}"
            if key not in expected or key not in actual:
                return child
            difference = first_difference(expected[key], actual[key], child)
            if difference:
                return difference
    elif isinstance(expected, list):
        if len(expected) != len(actual):
            return f"{path}.length"
        for index, (left, right) in enumerate(zip(expected, actual)):
            difference = first_difference(left, right, f"{path}[{index}]")
            if difference:
                return difference
    elif expected != actual:
        return path
    return None


def build_consensus(reports: list[dict]) -> dict:
    if len(reports) < 2:
        raise OracleValidationError("REGRESSION_CONSENSUS requires at least two reports")
    for report in reports:
        _validate_report_shape(report)
        if report.get("source_type") != "XEMU":
            raise OracleValidationError("REGRESSION_CONSENSUS accepts only xemu reports")
        if report.get("oracle_provenance") is not None:
            raise OracleValidationError("consensus inputs must be raw observations")
    report_ids = {report["report_id"] for report in reports}
    if len(report_ids) < 2:
        raise OracleValidationError("REGRESSION_CONSENSUS requires two distinct reports")
    first = reports[0]
    for report in reports:
        comparison_records(report["records"])
    stable_fields = ("source_backend", "guest_image_sha256", "job_sha256", "records")
    for report in reports[1:]:
        for field in stable_fields:
            if field == "records":
                difference = first_difference(
                    comparison_records(first["records"]),
                    comparison_records(report["records"]),
                )
                if difference:
                    raise SameBackendNondeterminism(
                        f"same-backend reports disagree on {difference}"
                    )
                continue
            if report.get(field) != first.get(field):
                raise OracleValidationError(
                    f"consensus reports disagree on {field}: "
                    f"{first.get(field)!r} != {report.get(field)!r}"
                )
    stable = {
        "schema_version": SCHEMA_VERSION,
        "kind": MANIFEST_KIND,
        "oracle_provenance": REGRESSION_CONSENSUS,
        "source_backend": first["source_backend"],
        "guest_image_sha256": first["guest_image_sha256"],
        "job_sha256": first["job_sha256"],
        "records": first["records"],
        "consensus_report_count": len(report_ids),
        "consensus_report_ids": sorted(report_ids),
    }
    stable["oracle_id"] = json_sha256(stable)
    return stable


def build_retail_consensus(reports: list[dict]) -> dict:
    if len(reports) < 2:
        raise OracleValidationError("RETAIL_XBOX oracle requires at least two owner reports")
    owner_reports = []
    for report in reports:
        _validate_report_shape(report)
        if (
            report.get("source_type") != "RETAIL_XBOX"
            or report.get("oracle_provenance") is not None
        ):
            raise OracleValidationError(
                "retail consensus accepts only raw RETAIL_XBOX reports"
            )
        hardware = report.get("hardware")
        if not isinstance(hardware, dict):
            raise OracleValidationError("retail report hardware metadata is required")
        owner_id = hardware.get("owner_id")
        revision = hardware.get("revision")
        if not isinstance(owner_id, str) or not owner_id:
            raise OracleValidationError("retail report owner_id is required")
        if not isinstance(revision, str) or not revision:
            raise OracleValidationError("retail report hardware revision is required")
        owner_reports.append(
            {
                "owner_id": owner_id,
                "hardware_revision": revision,
                "report_id": report["report_id"],
            }
        )
    if len({item["owner_id"] for item in owner_reports}) != len(owner_reports):
        raise OracleValidationError("RETAIL_XBOX oracle requires distinct owner IDs")
    first = reports[0]
    stable_fields = ("guest_image_sha256", "job_sha256", "records")
    for report in reports[1:]:
        for field in stable_fields:
            if report.get(field) != first.get(field):
                raise OracleValidationError(
                    f"retail owner reports disagree on {field}"
                )
    owner_reports.sort(key=lambda item: item["owner_id"])
    stable = {
        "schema_version": SCHEMA_VERSION,
        "kind": MANIFEST_KIND,
        "oracle_provenance": RETAIL_XBOX,
        "source_backend": "retail-xbox",
        "guest_image_sha256": first["guest_image_sha256"],
        "job_sha256": first["job_sha256"],
        "records": first["records"],
        "owner_report_count": len(owner_reports),
        "owner_reports": owner_reports,
    }
    stable["oracle_id"] = json_sha256(stable)
    return stable


def _validate_oracle_shape(value: dict) -> None:
    if value.get("schema_version") != SCHEMA_VERSION or value.get("kind") != MANIFEST_KIND:
        raise OracleValidationError("unsupported functional hash oracle")
    provenance = value.get("oracle_provenance")
    if provenance not in ORACLE_PROVENANCE_CLASSES:
        raise OracleValidationError("oracle provenance must be explicit")
    source_backend = value.get("source_backend")
    if not isinstance(source_backend, str) or not source_backend:
        raise OracleValidationError("oracle source_backend is required")
    guest_hash = _hash(value.get("guest_image_sha256"), "guest_image_sha256", (64,))
    job_hash = _hash(value.get("job_sha256"), "job_sha256", (64,))
    _validate_normalized_records(value.get("records"))
    if provenance == REGRESSION_CONSENSUS:
        count = _integer(value.get("consensus_report_count"), "consensus_report_count")
        report_ids = value.get("consensus_report_ids")
        if count < 2 or not isinstance(report_ids, list) or len(report_ids) != count:
            raise OracleValidationError("REGRESSION_CONSENSUS requires distinct reports")
        normalized_ids = sorted(
            _hash(report_id, "consensus_report_id", (64,))
            for report_id in report_ids
        )
        if len(set(normalized_ids)) != count or report_ids != normalized_ids:
            raise OracleValidationError("consensus report IDs must be unique and sorted")
        stable = {
            "schema_version": SCHEMA_VERSION,
            "kind": MANIFEST_KIND,
            "oracle_provenance": provenance,
            "source_backend": source_backend,
            "guest_image_sha256": guest_hash,
            "job_sha256": job_hash,
            "records": value["records"],
            "consensus_report_count": count,
            "consensus_report_ids": normalized_ids,
        }
    else:
        if source_backend != "retail-xbox":
            raise OracleValidationError("RETAIL_XBOX source backend must be retail-xbox")
        count = _integer(value.get("owner_report_count"), "owner_report_count")
        owner_reports = value.get("owner_reports")
        if count < 2 or not isinstance(owner_reports, list) or len(owner_reports) != count:
            raise OracleValidationError("RETAIL_XBOX oracle requires multiple owner reports")
        normalized_owner_reports = []
        for item in owner_reports:
            if not isinstance(item, dict):
                raise OracleValidationError("owner report metadata must be an object")
            owner_id = item.get("owner_id")
            revision = item.get("hardware_revision")
            if not isinstance(owner_id, str) or not owner_id:
                raise OracleValidationError("owner report owner_id is required")
            if not isinstance(revision, str) or not revision:
                raise OracleValidationError("owner report hardware revision is required")
            normalized_owner_reports.append(
                {
                    "owner_id": owner_id,
                    "hardware_revision": revision,
                    "report_id": _hash(item.get("report_id"), "owner report_id", (64,)),
                }
            )
        normalized_owner_reports.sort(key=lambda item: item["owner_id"])
        if (
            len({item["owner_id"] for item in normalized_owner_reports}) != count
            or owner_reports != normalized_owner_reports
        ):
            raise OracleValidationError("owner reports must have distinct sorted owner IDs")
        stable = {
            "schema_version": SCHEMA_VERSION,
            "kind": MANIFEST_KIND,
            "oracle_provenance": provenance,
            "source_backend": source_backend,
            "guest_image_sha256": guest_hash,
            "job_sha256": job_hash,
            "records": value["records"],
            "owner_report_count": count,
            "owner_reports": normalized_owner_reports,
        }
    oracle_id = _hash(value.get("oracle_id"), "oracle_id", (64,))
    if oracle_id != json_sha256(stable):
        raise OracleValidationError("oracle_id does not match oracle content")


def load_oracle(path: Path) -> dict:
    value = _load_json(path)
    _validate_oracle_shape(value)
    return value


def validate_against_oracle(report: dict, oracle: dict) -> dict:
    _validate_report_shape(report)
    _validate_oracle_shape(oracle)
    provenance = oracle.get("oracle_provenance")
    if provenance not in ORACLE_PROVENANCE_CLASSES:
        raise OracleValidationError("oracle provenance must be explicit")
    if provenance == REGRESSION_CONSENSUS and oracle.get("source_backend") != report.get("source_backend"):
        raise OracleValidationError(
            "REGRESSION_CONSENSUS is valid only for its source backend"
        )
    for field in ("guest_image_sha256", "job_sha256", "records"):
        if field == "records":
            difference = first_difference(
                comparison_records(oracle["records"]),
                comparison_records(report["records"]),
            )
            if difference:
                raise OracleValidationError(f"functional oracle mismatch for {difference}")
            continue
        if oracle.get(field) != report.get(field):
            raise OracleValidationError(
                f"functional oracle mismatch for {field}: expected "
                f"{oracle.get(field)!r}, got {report.get(field)!r}"
            )
    return {
        "status": "PASSED",
        "oracle_id": oracle.get("oracle_id"),
        "oracle_provenance": provenance,
    }


def _ledger_key(report: dict, record: dict) -> str:
    return json_sha256(
        {
            "source_backend": report["source_backend"],
            "surface_scale": report["surface_scale"],
            "guest_image_sha256": report["guest_image_sha256"],
            "job_sha256": report["job_sha256"],
            "test_id": record["test_id"],
            "contract": record["contract"],
        }
    )


def _ledger_surface_scale(report: dict) -> int:
    surface_scale = report.get("surface_scale")
    if (
        not isinstance(surface_scale, int)
        or isinstance(surface_scale, bool)
        or not 1 <= surface_scale <= 4
    ):
        raise OracleValidationError(
            "determinism ledger surface_scale must be an integer from 1 through 4"
        )
    return surface_scale


@contextmanager
def _locked_ledger(path: Path):
    lock_path = path.with_name(path.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def update_determinism_ledger(path: Path, report: dict) -> dict:
    _validate_report_shape(report)
    if report.get("source_type") != "XEMU":
        raise OracleValidationError("determinism ledger accepts only xemu reports")
    surface_scale = _ledger_surface_scale(report)
    with _locked_ledger(path):
        if path.exists():
            ledger = _load_json(path)
            if ledger.get("schema_version") != SCHEMA_VERSION:
                raise OracleValidationError("unsupported determinism ledger")
        else:
            ledger = {"schema_version": SCHEMA_VERSION, "entries": {}}
        entries = ledger.get("entries")
        if not isinstance(entries, dict):
            raise OracleValidationError("determinism ledger entries must be an object")

        staged = json.loads(json.dumps(ledger))
        skipped = []
        excluded_observations = []
        for record in report["records"]:
            internal_oracle = record.get("internal_oracle")
            if (
                isinstance(internal_oracle, dict)
                and internal_oracle.get("status") == "FAIL"
            ):
                skipped.append(
                    {
                        "test_id": record["test_id"],
                        "reason": internal_oracle.get(
                            "failure_reason", "guest internal oracle failed"
                        ),
                    }
                )
                continue
            comparison_policy = record.get("comparison_policy")
            if comparison_policy is not None:
                excluded_observations.append(
                    {
                        "test_id": record["test_id"],
                        "observations": comparison_policy["excluded_observations"],
                        "reason": comparison_policy["reason"],
                    }
                )
            key = _ledger_key(report, record)
            existing = staged["entries"].get(key)
            if existing is not None and existing.get("hashes") != record["hashes"]:
                raise SameBackendNondeterminism(
                    f"same-backend nondeterminism for {record['test_id']}: "
                    f"expected {existing.get('hashes')!r}, got {record['hashes']!r}"
                )
            if existing is None:
                existing = {
                    "source_backend": report["source_backend"],
                    "surface_scale": surface_scale,
                    "guest_image_sha256": report["guest_image_sha256"],
                    "job_sha256": report["job_sha256"],
                    "test_id": record["test_id"],
                    "contract": record["contract"],
                    "hashes": record["hashes"],
                    "report_ids": [],
                }
                staged["entries"][key] = existing
            if report["report_id"] not in existing["report_ids"]:
                existing["report_ids"].append(report["report_id"])
                existing["report_ids"].sort()
            existing["observation_count"] = len(existing["report_ids"])

        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False
        ) as destination:
            json.dump(staged, destination, indent=2)
            destination.write("\n")
            temporary = Path(destination.name)
        os.replace(temporary, path)
    return {
        "status": "PASSED",
        "ledger_path": str(path),
        "record_count": len(report["records"]) - len(skipped),
        "skipped_internal_oracle_failures": skipped,
        "excluded_ineligible_observations": excluded_observations,
    }


def load_report(path: Path) -> dict:
    value = _load_json(path)
    _validate_report_shape(value)
    return value
