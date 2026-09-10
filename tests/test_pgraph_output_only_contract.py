#!/usr/bin/env python3
"""Production-function controls for the pinned PGRAPH output-only patches."""

import ast
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ENV = "XEMU_PGRAPH_RUNNER_ROOT"
CHILD_SHA256 = "c478e3a38865de180f3751b88904bf18b152dd05208e773326979e3d7b65b64d"
PAIR_SHA256 = "e358b55d940e361bf57ef64a7a5cde83fc267d885191c813e7616764a88ee58a"
CHILD_PATCH = ROOT / "utils/host-runner/run-suite-output-only-null-metadata.patch"
PAIR_PATCH = ROOT / "utils/host-runner/run-pair-output-only-forwarding.patch"
RECIPE_DIRECTORY = ROOT / "utils/host-runner/pgraph-output-only-contracts"


class PairRunError(RuntimeError):
    pass


def source_sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_functions(path, names, namespace):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    missing = set(names) - set(found)
    if missing:
        raise AssertionError(f"missing production functions: {sorted(missing)}")
    for name in names:
        module = ast.Module(body=[found[name]], type_ignores=[])
        exec(compile(module, str(path), "exec"), namespace)
    return namespace


class PgraphOutputOnlyContractTests(unittest.TestCase):
    @staticmethod
    def artifact_identity(child, pair, guest_iso_sha256, catalog_sha256):
        return {
            "guest_iso_sha256": guest_iso_sha256,
            "catalog_sha256": catalog_sha256,
            "catalog_id": "sha256:catalog",
            "child_runner_source_sha256": CHILD_SHA256,
            "child_runner_patched_sha256": source_sha256(child),
            "child_patch_sha256": source_sha256(CHILD_PATCH),
            "pair_runner_source_sha256": PAIR_SHA256,
            "pair_runner_patched_sha256": source_sha256(pair),
            "pair_patch_sha256": source_sha256(PAIR_PATCH),
        }

    def patched_sources(self):
        fixture_name = os.environ.get(FIXTURE_ENV)
        if fixture_name is None:
            self.skipTest(f"set {FIXTURE_ENV} to run the external runner fixture")
        fixture_root = Path(fixture_name)
        child_source = fixture_root / "run-suite.py"
        pair_source = fixture_root / "run-pair.py"
        self.assertEqual(source_sha256(child_source), CHILD_SHA256)
        self.assertEqual(source_sha256(pair_source), PAIR_SHA256)
        self.assertTrue(CHILD_PATCH.is_file(), "child patch is missing")
        self.assertTrue(PAIR_PATCH.is_file(), "pair patch is missing")
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            child = directory / "run-suite.py"
            pair = directory / "run-pair.py"
            shutil.copyfile(child_source, child)
            shutil.copyfile(pair_source, pair)
            for patch, target in ((CHILD_PATCH, child), (PAIR_PATCH, pair)):
                result = subprocess.run(
                    ["patch", "--batch", "--forward", "-p0", "-i", str(patch)],
                    cwd=directory,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            yield child, pair

    @staticmethod
    def record(**overrides):
        record = {
            "name": "BusyPfifo::PgraphPatternPolling",
            "iterations": 4,
            "sample_count": 1,
            "framebuffer_fnv1a64": "386d0f085e98c325",
            "measurement_iterations_multiplier": 4,
            "warmup_iterations": 2,
            "gpu_completion_mode": "per_iteration",
            "total_us": 20_000_000,
        }
        record.update(overrides)
        return record

    @staticmethod
    def contract(metadata):
        return {
            "sha256": "pinned-contract",
            "workload": {
                "measurement_iterations_multiplier": 4,
                "warmup_iterations": 2,
                "completion_mode": "per_iteration",
                "minimum_measurement_seconds": 15,
                "minimum_warmup_seconds": 5,
            },
            "records": [
                {
                    "name": "BusyPfifo::PgraphPatternPolling",
                    "iterations": 4,
                    "sample_count": 1,
                    "framebuffer_fnv1a64": "386d0f085e98c325",
                    "metadata": metadata,
                }
            ],
        }

    def test_null_contract_requires_missing_normalized_metadata(self):
        for child, _pair in self.patched_sources():
            namespace = extract_functions(
                child,
                ("normalize_perf_records", "validate_output_only_records"),
                {},
            )
            actual = namespace["normalize_perf_records"](
                [self.record()], 4, 2, "per_iteration"
            )
            self.assertNotIn("metadata", actual[0])
            accepted = namespace["validate_output_only_records"](
                actual, self.contract(None)
            )
            self.assertEqual(accepted["status"], "PASSED")
            for invalid in (
                self.record(metadata=None),
                self.record(metadata={"unexpected": True}),
            ):
                with self.subTest(actual=invalid):
                    with self.assertRaisesRegex(RuntimeError, "metadata"):
                        namespace["validate_output_only_records"](
                            [invalid], self.contract(None)
                        )

    def test_dictionary_and_hash_controls_remain_strict(self):
        for child, _pair in self.patched_sources():
            namespace = extract_functions(
                child, ("validate_output_only_records",), {}
            )
            dictionary_contract = self.contract({"profile": "pgraph"})
            namespace["validate_output_only_records"](
                [self.record(metadata={"profile": "pgraph"})], dictionary_contract
            )
            with self.assertRaisesRegex(RuntimeError, "metadata.profile"):
                namespace["validate_output_only_records"](
                    [self.record(metadata={"profile": "wrong"})], dictionary_contract
                )
            with self.assertRaisesRegex(RuntimeError, "framebuffer_fnv1a64"):
                namespace["validate_output_only_records"](
                        [self.record(framebuffer_fnv1a64="wrong")], self.contract(None)
                    )

    def test_schema_one_loader_accepts_only_null_or_object_metadata(self):
        for child, _pair in self.patched_sources():
            with tempfile.TemporaryDirectory() as temporary:
                contract_path = Path(temporary) / "contract.json"
                manifest = {
                    "schema_version": 1,
                    "artifact_identity": self.artifact_identity(
                        child, _pair, "0" * 64, "1" * 64
                    ),
                    "workload": {
                        "test_id": None,
                        "backend": "opengl",
                        "surface_scale": 1,
                        "memory_megabytes": 64,
                        "vsync": False,
                        "completion_mode": "per_iteration",
                        "host_telemetry": "off",
                        "warmup_iterations": 2,
                        "measurement_iterations_multiplier": 4,
                        "guest_evidence_mode": "output-only",
                        "guest_evidence_capability": "post-run-output-oracles-v1",
                        "held_frame_capture": False,
                        "minimum_measurement_seconds": 15,
                        "minimum_warmup_seconds": 5,
                    },
                    "result_contract": {
                        "record_order": ["BusyPfifo::PgraphPatternPolling"],
                        "pgraph": self.contract(None)["records"][0],
                    },
                }
                contract_path.write_text(json.dumps(manifest), encoding="utf-8")
                namespace = extract_functions(
                    child,
                    ("load_output_only_contract",),
                    {
                        "Path": Path,
                        "argparse": argparse,
                        "json": json,
                        "sha256": source_sha256,
                        "re": __import__("re"),
                        "__file__": str(child),
                        "GUEST_EVIDENCE_OUTPUT_ONLY": "output-only",
                        "GUEST_EVIDENCE_CAPABILITIES": {
                            "output-only": "post-run-output-oracles-v1"
                        },
                    },
                )
                args = SimpleNamespace(
                    test_id=None,
                    profile="pgraph-pattern-poll",
                    backend="opengl",
                    scale=1,
                    memory_megabytes=64,
                    vsync=False,
                    completion_mode="per_iteration",
                    warmup_iterations=2,
                    measurement_iterations_multiplier=4,
                )
                loaded = namespace["load_output_only_contract"](contract_path, args)
                self.assertIsNone(loaded["records"][0]["metadata"])
                manifest.pop("artifact_identity")
                contract_path.write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "artifact_identity"):
                    namespace["load_output_only_contract"](contract_path, args)
                manifest["artifact_identity"] = self.artifact_identity(
                    child, _pair, "0" * 64, "1" * 64
                )
                manifest["artifact_identity"]["child_runner_patched_sha256"] = "2" * 64
                contract_path.write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "child runner digest"):
                    namespace["load_output_only_contract"](contract_path, args)
                manifest["artifact_identity"] = self.artifact_identity(
                    child, _pair, "0" * 64, "1" * 64
                )
                manifest["result_contract"]["pgraph"]["metadata"] = []
                contract_path.write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "null or an object"):
                    namespace["load_output_only_contract"](contract_path, args)

    def test_renderer_recipes_load_as_one_record_null_metadata_contracts(self):
        for child, _pair in self.patched_sources():
            namespace = extract_functions(
                child,
                ("load_output_only_contract",),
                {
                    "Path": Path,
                    "argparse": argparse,
                        "json": json,
                        "sha256": source_sha256,
                        "re": __import__("re"),
                        "__file__": str(child),
                    "GUEST_EVIDENCE_OUTPUT_ONLY": "output-only",
                    "GUEST_EVIDENCE_CAPABILITIES": {
                        "output-only": "post-run-output-oracles-v1"
                    },
                },
            )
            for backend in ("opengl", "vulkan"):
                with self.subTest(backend=backend):
                    recipe = RECIPE_DIRECTORY / (
                        f"pgraph-pattern-polling-{backend}.schema1.json"
                    )
                    args = SimpleNamespace(
                        test_id=None,
                        profile="pgraph-pattern-poll",
                        backend=backend,
                        scale=1,
                        memory_megabytes=64,
                        vsync=False,
                        completion_mode="per_iteration",
                        warmup_iterations=2,
                        measurement_iterations_multiplier=4,
                    )
                    loaded = namespace["load_output_only_contract"](recipe, args)
                    self.assertEqual(loaded["suite_id"], f"pgraph-output-only-{backend}-v1")
                    self.assertEqual(len(loaded["records"]), 1)
                    self.assertIsNone(loaded["records"][0]["metadata"])
                    wrong_selector = SimpleNamespace(**vars(args))
                    wrong_selector.test_id = "BusyPfifo::PgraphPatternPolling"
                    with self.assertRaisesRegex(ValueError, "workload.test_id mismatch"):
                        namespace["load_output_only_contract"](recipe, wrong_selector)

    def test_child_identity_rejects_wrong_guest_or_catalog_before_records(self):
        for child, pair in self.patched_sources():
            with tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                guest = directory / "guest.iso"
                catalog = directory / "catalog.json"
                guest.write_bytes(b"guest")
                catalog.write_text("{}", encoding="utf-8")
                identity = self.artifact_identity(
                    child, pair, source_sha256(guest), source_sha256(catalog)
                )
                namespace = extract_functions(
                    child,
                    ("validate_output_only_artifact_identity",),
                    {"Path": Path, "sha256": source_sha256},
                )
                contract = {"artifact_identity": identity}
                record_contract = {
                    "catalog_sha256": source_sha256(catalog),
                    "catalog_id": "sha256:catalog",
                }
                accepted = namespace["validate_output_only_artifact_identity"](
                    contract, guest, record_contract
                )
                self.assertEqual(accepted["status"], "PASSED")
                guest.write_bytes(b"wrong-guest")
                with self.assertRaisesRegex(RuntimeError, "guest ISO"):
                    namespace["validate_output_only_artifact_identity"](
                        contract, guest, record_contract
                    )
                guest.write_bytes(b"guest")
                record_contract["catalog_sha256"] = "wrong"
                with self.assertRaisesRegex(RuntimeError, "catalog"):
                    namespace["validate_output_only_artifact_identity"](
                        contract, guest, record_contract
                    )

    def test_pair_forwards_contract_and_rejects_unvalidated_children(self):
        for _child, pair in self.patched_sources():
            contract_path = Path("pgraph-contract.json")
            namespace = extract_functions(
                pair,
                (
                    "child_command",
                    "validate_output_only_pair_request",
                    "validate_output_only_child_evidence",
                ),
                {
                    "Path": Path,
                    "argparse": argparse,
                    "Any": Any,
                    "sys": __import__("sys"),
                    "CHILD_RUNNER": Path("run-suite.py"),
                    "PairRunError": PairRunError,
                    "sha256": lambda path: "pinned-contract",
                    "telemetry_mode": lambda args, role: args.host_telemetry,
                },
            )
            args = SimpleNamespace(
                backend="opengl",
                scale=1,
                memory_megabytes=64,
                warmup_iterations=2,
                measurement_iterations_multiplier=4,
                completion_mode="per_iteration",
                test_id=None,
                profile="pgraph-pattern-poll",
                guest_iso=None,
                game_load_config_json=None,
                experiment_config=None,
                baseline_xemu_env=[],
                candidate_xemu_env=[],
                vsync=False,
                allow_missing_live_markers=False,
                compatibility_allowance=[],
                no_oracle_ledger=False,
                allow_short_smoke=False,
                guest_evidence_mode="output-only",
                guest_output_contract_json=contract_path,
                host_telemetry="off",
                output_contract_identity={"guest_iso_sha256": "guest"},
            )
            namespace["validate_output_only_pair_request"](args)
            command = namespace["child_command"](
                args, Path("baseline.exe"), "off", "baseline"
            )
            self.assertEqual(
                command[-4:],
                [
                    "--guest-evidence-mode",
                    "output-only",
                    "--guest-output-contract-json",
                    str(contract_path.resolve()),
                ],
            )
            summary = {
                "guest_evidence": {
                    "mode": "output-only",
                    "output_contract": {"sha256": "pinned-contract"},
                    "output_validation": {
                        "status": "PASSED",
                        "contract_sha256": "pinned-contract",
                    },
                    "identity_validation": {
                        "status": "PASSED",
                        "artifact_identity": {"guest_iso_sha256": "guest"},
                    },
                }
            }
            namespace["validate_output_only_child_evidence"](summary, args)
            summary["guest_evidence"]["output_contract"]["sha256"] = "wrong"
            with self.assertRaisesRegex(PairRunError, "contract digest"):
                namespace["validate_output_only_child_evidence"](summary, args)
            summary["guest_evidence"]["output_contract"]["sha256"] = "pinned-contract"
            summary["guest_evidence"]["identity_validation"]["artifact_identity"] = {}
            with self.assertRaisesRegex(PairRunError, "identity"):
                namespace["validate_output_only_child_evidence"](summary, args)
            summary["guest_evidence"]["identity_validation"]["artifact_identity"] = {
                "guest_iso_sha256": "guest"
            }
            summary["guest_evidence"]["output_validation"]["status"] = "FAILED"
            with self.assertRaisesRegex(PairRunError, "output_validation"):
                namespace["validate_output_only_child_evidence"](summary, args)
            args.compatibility_allowance = [Path("allowance.json")]
            with self.assertRaisesRegex(PairRunError, "compatibility"):
                namespace["validate_output_only_pair_request"](args)

    def test_pair_identity_rejects_missing_or_wrong_patched_runner(self):
        for child, pair in self.patched_sources():
            with tempfile.TemporaryDirectory() as temporary:
                contract_path = Path(temporary) / "contract.json"
                identity = self.artifact_identity(child, pair, "0" * 64, "1" * 64)
                contract_path.write_text(
                    json.dumps({"schema_version": 1, "artifact_identity": identity}),
                    encoding="utf-8",
                )
                namespace = extract_functions(
                    pair,
                    ("load_output_only_pair_identity",),
                    {
                        "Path": Path,
                        "argparse": argparse,
                        "json": json,
                        "re": __import__("re"),
                        "sha256": source_sha256,
                        "PairRunError": PairRunError,
                        "__file__": str(pair),
                    },
                )
                args = SimpleNamespace(
                    guest_evidence_mode="output-only",
                    guest_output_contract_json=contract_path,
                )
                self.assertEqual(
                    namespace["load_output_only_pair_identity"](args), identity
                )
                identity["pair_runner_patched_sha256"] = "2" * 64
                contract_path.write_text(
                    json.dumps({"schema_version": 1, "artifact_identity": identity}),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(PairRunError, "runner digest"):
                    namespace["load_output_only_pair_identity"](args)

    def test_validate_summary_calls_output_only_child_gate_before_timing(self):
        for _child, pair in self.patched_sources():
            namespace = extract_functions(
                pair,
                ("validate_summary",),
                {
                    "argparse": argparse,
                    "Any": Any,
                    "child_status_accepted": lambda summary, args: True,
                    "validate_output_only_child_evidence": (
                        lambda summary, args: (_ for _ in ()).throw(
                            PairRunError("unvalidated child")
                        )
                    ),
                },
            )
            with self.assertRaisesRegex(PairRunError, "unvalidated child"):
                namespace["validate_summary"](
                    {}, SimpleNamespace(warmup_iterations=2), "off", "baseline"
                )


if __name__ == "__main__":
    unittest.main()
