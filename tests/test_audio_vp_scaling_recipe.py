from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AudioVpScalingRecipeTests(unittest.TestCase):
    def test_counts_channels_slots_and_output_are_observed(self):
        with tempfile.TemporaryDirectory() as temp:
            binary = Path(temp) / "scaling_recipe"
            compile_result = subprocess.run([
                "g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                "-I", str(ROOT / "src/tests"),
                str(ROOT / "tests/audio_vp_scaling_recipe_probe.cpp"),
                str(ROOT / "src/tests/audio_vp_scaling_recipe.cpp"),
                "-o", str(binary)], capture_output=True, text=True)
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
