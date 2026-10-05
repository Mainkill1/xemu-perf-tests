"""The raw S16 path must use observations and retain DMA on uncertain stop."""

from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AudioRawS16Tests(unittest.TestCase):
    def test_device_progress_output_and_teardown_are_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            executable = Path(temporary) / "audio_raw_s16_probe"
            compile_result = subprocess.run(
                ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                 "-I", str(ROOT / "src" / "tests"),
                 str(ROOT / "tests" / "audio_raw_s16_probe.cpp"),
                 str(ROOT / "src" / "tests" / "audio_mcpx_raw_backend.cpp"),
                 str(ROOT / "src" / "tests" / "audio_session_guard.cpp"),
                 str(ROOT / "src" / "tests" / "audio_apu_ownership.cpp"),
                 str(ROOT / "src" / "tests" / "audio_torture_support.cpp"),
                 "-o", str(executable)], capture_output=True, text=True)
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            for scenario in (None, "gate-restore", "headroom-readback", "poison"):
                command = [str(executable)]
                if scenario:
                    command.append(scenario)
                result = subprocess.run(command, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, f"{scenario}: {result.stderr}")
                self.assertIn("raw S16 observed, rejected, and retained safely", result.stdout)


if __name__ == "__main__":
    unittest.main()
