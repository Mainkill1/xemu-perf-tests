import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools" / "retail-campaign"
VALIDATOR = TOOLS / "validate_morrowind_workloads.py"
PROFILES = TOOLS / "morrowind-workloads.json"


class MorrowindWorkloadContractTests(unittest.TestCase):
    def run_validator(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VALIDATOR), *args],
            cwd=ROOT,
            check=False,
            text=True,
            capture_output=True,
        )

    def test_profiles_define_independent_fresh_and_snapshot_gates(self) -> None:
        completed = self.run_validator(
            "--manifest", str(PROFILES), "--print-plan", "MORROWIND-FRESH"
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        plan = json.loads(completed.stdout)
        self.assertEqual(plan["workload"], "MORROWIND-FRESH")
        self.assertEqual(plan["launch_mode"], "FreshBoot")
        self.assertIsNone(plan["snapshot"])
        self.assertEqual(plan["admission"]["route"], "fresh-menu-load")
        self.assertTrue(plan["admission"]["require_image_transition"])
        self.assertTrue(plan["admission"]["require_display_progression"])
        self.assertGreaterEqual(len(plan["input_steps"]), 4)

        snapshot = json.loads(
            self.run_validator(
                "--manifest",
                str(PROFILES),
                "--print-plan",
                "MORROWIND-SNAPSHOT",
            ).stdout
        )
        self.assertEqual(snapshot["launch_mode"], "Snapshot")
        self.assertEqual(snapshot["snapshot"], "gameplay-checkpoint")
        self.assertEqual(
            [(step["button"], step["delay_seconds"]) for step in snapshot["input_steps"]],
            [("START", 5), ("B", 2)],
        )
        self.assertEqual(snapshot["post_input_delay_seconds"], 2)

    def test_fresh_and_snapshot_use_identical_measurement_contracts(self) -> None:
        manifest = json.loads(PROFILES.read_text(encoding="utf-8"))
        fresh = manifest["workloads"]["MORROWIND-FRESH"]
        snapshot = manifest["workloads"]["MORROWIND-SNAPSHOT"]

        self.assertEqual(fresh["measurement"], snapshot["measurement"])
        self.assertEqual(fresh["inputs"], snapshot["inputs"])
        self.assertEqual(
            fresh["measurement"]["metrics"],
            [
                "cadence_per_second",
                "average_interval_ms",
                "p95_ms",
                "p99_ms",
                "max_ms",
                "stall_count",
                "worst_intervals_ms",
            ],
        )

    def test_invalid_fresh_profile_cannot_restore_a_snapshot(self) -> None:
        manifest = json.loads(PROFILES.read_text(encoding="utf-8"))
        manifest["workloads"]["MORROWIND-FRESH"]["snapshot"] = "accidental-state"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            completed = self.run_validator("--manifest", str(path))

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("MORROWIND-FRESH must not restore a snapshot", completed.stderr)

    def test_profiles_reject_unpinned_or_unverified_fresh_inputs(self) -> None:
        manifest = json.loads(PROFILES.read_text(encoding="utf-8"))
        manifest["workloads"]["MORROWIND-FRESH"]["inputs"]["seed"]["sha256"] = ""
        manifest["workloads"]["MORROWIND-FRESH"]["admission"][
            "require_image_transition"
        ] = False
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            completed = self.run_validator("--manifest", str(path))

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("seed.sha256 must be a lowercase SHA-256", completed.stderr)

    def test_profiles_reject_a_collapsed_fresh_and_snapshot_gate(self) -> None:
        manifest = json.loads(PROFILES.read_text(encoding="utf-8"))
        manifest["workloads"]["MORROWIND-FRESH"]["admission"]["route"] = (
            manifest["workloads"]["MORROWIND-SNAPSHOT"]["admission"]["route"]
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            completed = self.run_validator("--manifest", str(path))

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("must use distinct admission routes", completed.stderr)

    def test_public_package_contains_no_host_or_private_asset_paths(self) -> None:
        public_files = [ROOT / "docs" / "morrowind-retail-qualification.md"]
        public_files.extend(path for path in TOOLS.iterdir() if path.is_file())
        forbidden_fragments = (
            "xe" + "mu" + "-" + "lab",
            "Us" + "ers" + "\\" + "co" + "dex",
            "pgr" + "2" + "-" + "exclusive",
            "Elder" + " Scrolls" + " III" + ", The",
            "tools" + "-" + "881",
            "suite" + "-" + "eng",
        )
        violations = []
        for path in public_files:
            text = path.read_text(encoding="utf-8")
            if re.search(r"(?i)\b[A-Z]:\\", text):
                violations.append(f"{path}: rooted Windows path")
            for fragment in forbidden_fragments:
                if fragment.lower() in text.lower():
                    violations.append(f"{path}: {fragment}")

        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
