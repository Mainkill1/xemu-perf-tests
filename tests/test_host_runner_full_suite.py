#!/usr/bin/env python3
"""Runtime contract for the digest-pinned full-suite runner patch."""

import contextlib
import hashlib
import io
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
PATCH_FILE = ROOT / "utils/host-runner/run-suite-enable-xemu-only-tests.patch"
FIXTURE_ENV = "XEMU_FULL_SUITE_RUNNER"
FIXTURE_SHA256 = "c478e3a38865de180f3751b88904bf18b152dd05208e773326979e3d7b65b64d"


def noop(*_args, **_kwargs):
    return None


class StubXemuTestBase:
    pass


def _runner_import_stubs():
    previous = {}

    def install(name, module):
        previous[name] = sys.modules.get(name)
        sys.modules[name] = module

    xemutest = types.ModuleType("xemutest")
    xemutest.Environment = object
    xemutest.TestStatus = types.SimpleNamespace()
    xemutest.XemuTestBase = StubXemuTestBase
    install("xemutest", xemutest)
    install("xemutest.xemu_manager", types.ModuleType("xemutest.xemu_manager"))
    tests_module = types.ModuleType("xemutest.tests")
    install("xemutest.tests", tests_module)
    test_xbe = types.ModuleType("xemutest.tests.test_xbe")
    test_xbe.TestXBE = object
    install("xemutest.tests.test_xbe", test_xbe)

    def module(name, **values):
        result = types.ModuleType(name)
        for key, value in values.items():
            setattr(result, key, value)
        install(name, result)

    module(
        "perf_lab_config",
        load_experiment_config=noop,
        merge_cli_environment=noop,
        resolve_experiment_role=noop,
    )
    module(
        "game_load_composite",
        CROSS_TITLE_ALL_MASK=0,
        CROSS_TITLE_STAGE_ORDER=(),
        PRESETS={},
        install_profiles=noop,
        interaction_analysis=noop,
        validate_work=noop,
        validate_host_telemetry=noop,
        work_from_records=noop,
    )
    module(
        "xemu_exclusive_lock",
        XemuExclusiveLock=object,
        default_xemu_lock_path=lambda: Path("xemu.lock"),
    )
    module(
        "oracle_validation",
        OracleValidationError=Exception,
        REGRESSION_ONLY="regression-only",
        SameBackendNondeterminism=Exception,
        build_report=noop,
        load_oracle=noop,
        update_determinism_ledger=noop,
        validate_against_oracle=noop,
        write_json=noop,
    )
    module("window_focus", focus_process_window=noop)
    module(
        "record_contract",
        RecordContractError=Exception,
        derive_record_contract=noop,
        discover_catalog=noop,
        file_sha256=noop,
        load_catalog=noop,
        validate_record_contract=noop,
    )
    try:
        yield
    finally:
        for name, original in previous.items():
            if original is None:
                del sys.modules[name]
            else:
                sys.modules[name] = original


runner_import_stubs = contextlib.contextmanager(_runner_import_stubs)


class HostRunnerFullSuiteTests(unittest.TestCase):
    def load_runner(self, apply_patch):
        fixture_name = os.environ.get(FIXTURE_ENV)
        if fixture_name is None:
            self.skipTest(f"set {FIXTURE_ENV} to run the external runner fixture")
        fixture = Path(fixture_name)
        self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(), FIXTURE_SHA256)
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "run-suite.py"
            shutil.copyfile(fixture, copied)
            if apply_patch:
                self.assertTrue(PATCH_FILE.is_file(), "versioned runner patch is missing")
                result = subprocess.run(
                    ["patch", "--batch", "--forward", "-p0", "-i", str(PATCH_FILE)],
                    cwd=temporary,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            with runner_import_stubs():
                spec = importlib.util.spec_from_file_location("patched_runner", copied)
                runner = importlib.util.module_from_spec(spec)
                assert spec.loader is not None
                spec.loader.exec_module(runner)
                yield runner

    def parse(self, runner, *arguments):
        with patch.object(sys, "argv", ["run-suite.py", *arguments]):
            return runner.parse_args()

    def test_exact_old_runner_rejects_opt_in_and_omits_guest_boolean(self):
        for runner in self.load_runner(apply_patch=False):
            config = runner.build_perf_config({}, 0, "per_iteration", 1)
            self.assertNotIn("enable_xemu_only_tests", config["settings"])
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as rejected:
                    self.parse(
                        runner,
                        "--mode",
                        "perf",
                        "--full-suite",
                        "--enable-xemu-only-tests",
                    )
            self.assertEqual(rejected.exception.code, 2)

    def test_opt_in_emits_existing_guest_boolean_without_changing_test_filter(self):
        for runner in self.load_runner(apply_patch=True):
            selected = {"PFIFOPacketBoundary": {"skipped": False}}
            default = runner.build_perf_config(selected, 0, "per_iteration", 1)
            legacy_held = runner.build_perf_config(
                selected, 0, "per_iteration", 1, None, True
            )
            enabled = runner.build_perf_config(
                selected,
                0,
                "per_iteration",
                1,
                enable_xemu_only_tests=True,
            )
            self.assertNotIn("enable_xemu_only_tests", default["settings"])
            self.assertTrue(legacy_held["settings"]["hold_final_frame_on_completion"])
            self.assertNotIn("enable_xemu_only_tests", legacy_held["settings"])
            self.assertTrue(enabled["settings"]["enable_xemu_only_tests"])
            self.assertIs(enabled["test_suites"], selected)
            self.assertTrue(enabled["settings"]["skip_tests_by_default"])

    def test_opt_in_requires_perf_full_suite(self):
        for runner in self.load_runner(apply_patch=True):
            accepted = self.parse(
                runner, "--mode", "perf", "--full-suite", "--enable-xemu-only-tests"
            )
            runner.validate_enable_xemu_only_tests_request(accepted)
            for arguments in (
                ("--mode", "official-smoke", "--full-suite", "--enable-xemu-only-tests"),
                ("--mode", "perf", "--enable-xemu-only-tests"),
            ):
                with self.subTest(arguments=arguments):
                    with self.assertRaisesRegex(ValueError, "--enable-xemu-only-tests"):
                        runner.validate_enable_xemu_only_tests_request(
                            self.parse(runner, *arguments)
                        )


if __name__ == "__main__":
    unittest.main()
