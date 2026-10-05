from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AudioVpScalingBackendTests(unittest.TestCase):
    def test_all_scaling_requests_and_failure_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            binary = Path(temp) / "scaling_backend"
            sources = ["audio_mcpx_raw_backend", "audio_apu_ownership", "audio_session_guard",
                       "audio_vp_scaling_recipe", "audio_torture_support"]
            command = ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                       "-I", str(ROOT / "src/tests"),
                       str(ROOT / "tests/audio_vp_scaling_backend_probe.cpp")]
            command += [str(ROOT / f"src/tests/{s}.cpp") for s in sources]
            result = subprocess.run(command + ["-o", str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            for scenario in (None, "skip", "reverse", "poison", "headroom"):
                result = subprocess.run([str(binary)] + ([scenario] if scenario else []),
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, f"{scenario}: {result.stderr}")


if __name__ == "__main__":
    unittest.main()
