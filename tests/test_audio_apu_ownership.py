"""Compile the hardware-independent APU ownership gate with a fake transport."""

import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class AudioApuOwnershipTests(unittest.TestCase):
    def test_admission_rejects_busy_or_missing_device_without_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            executable = pathlib.Path(temporary) / "audio_apu_ownership_probe"
            compile_result = subprocess.run(
                ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                 "-I", str(ROOT / "src" / "tests"),
                 str(ROOT / "tests" / "audio_apu_ownership_probe.cpp"),
                 str(ROOT / "src" / "tests" / "audio_apu_ownership.cpp"),
                 "-o", str(executable)], capture_output=True, text=True)
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            result = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("ownership rejection and restoration guarded", result.stdout)


if __name__ == "__main__":
    unittest.main()
