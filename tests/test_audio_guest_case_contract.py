"""The generated guest table must retain every planned audio case's identity."""

import pathlib
import shutil
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "utils" / "generate_audio_guest_cases.py"
GENERATED = ROOT / "src" / "generated" / "audio_case_catalog.inc"


class AudioGuestCaseContractTests(unittest.TestCase):
    def test_compiled_guest_table_covers_every_family_and_boundary(self):
        with tempfile.TemporaryDirectory() as temporary:
            executable = pathlib.Path(temporary) / "audio_case_catalog_probe"
            subprocess.run(
                ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                 "-I", str(ROOT / "src" / "tests"),
                 str(ROOT / "tests" / "audio_case_catalog_probe.cpp"),
                 "-o", str(executable)],
                check=True, capture_output=True, text=True,
            )
            result = subprocess.run([str(executable)], check=True,
                                    capture_output=True, text=True)
            self.assertIn("138 descriptors, 15 families, 0 executable", result.stdout)

    def test_check_rejects_stale_generated_table(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = pathlib.Path(temporary) / "audio_case_catalog.inc"
            shutil.copyfile(GENERATED, output)
            good = subprocess.run(["python3", str(GENERATOR), "--check", "--output", str(output)],
                                  capture_output=True, text=True)
            self.assertEqual(good.returncode, 0, good.stderr)
            output.write_bytes(output.read_bytes() + b"\n// stale\n")
            stale = subprocess.run(["python3", str(GENERATOR), "--check", "--output", str(output)],
                                   capture_output=True, text=True)
            self.assertNotEqual(stale.returncode, 0)
            self.assertIn("stale", stale.stderr.lower())


if __name__ == "__main__":
    unittest.main()
