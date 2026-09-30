"""Run the actual generated code and prove the oracle rejects stale code."""
import os
import json
import platform
import shutil
import subprocess
import tempfile
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "utils"))
import oracle_validation


@unittest.skipUnless(platform.system() == "Linux" and platform.machine() in
                     ("x86_64", "i386", "i686"), "requires native Linux x86 executable memory")
class CpuCodeRewriteContractTests(unittest.TestCase):
    def run_fixture(self, stale=False):
        compiler = os.environ.get("CXX", "g++")
        self.assertIsNotNone(shutil.which(compiler), "native C++ compiler is required")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            header = root / "tests/cpu_code_rewrite_workload.h"
            header.parent.mkdir()
            text = (ROOT / "src/tests/cpu_code_rewrite_workload.h").read_text()
            if stale:
                store = "if (rewrite) *immediate = (i & 1) ? 0x5A5AA5A5 : 0xA5A55A5A;"
                self.assertEqual(text.count(store), 1)
                text = text.replace(store, "(void)rewrite; (void)immediate;")
            header.write_text(text)
            executable = root / "check"
            build = subprocess.run([
                compiler, "-O3", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                "-fno-strict-aliasing", "-I", str(root),
                str(ROOT / "tests/cpu_code_rewrite_workload_check.cpp"), "-o", str(executable)
            ], capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            return subprocess.run([str(executable)], capture_output=True, text=True)

    def test_native_code_matches_independent_known_answers(self):
        result = self.run_fixture()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        observed = {(int(count), int(rewrite)): (checksum, signature) for count, rewrite, checksum, signature in
                    (line.split() for line in result.stdout.splitlines())}
        reference = json.loads((ROOT / "resources/cpu-code-rewrite-reference.json").read_text())
        work = {"cpu_translation_blocks.code_stable": (50000000, 0),
                "cpu_translation_blocks.code_rewrite": (1000000, 1)}
        self.assertEqual({record["id"] for record in reference}, set(work))
        for record in reference:
            result, signature = observed[work[record["id"]]]
            self.assertEqual(record["metadata"]["work_checksum"], signature)
            self.assertEqual(record["metadata"]["result_checksum"], result)

    def test_stale_code_is_rejected(self):
        result = self.run_fixture(stale=True)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("operations=2 rewrite=1 expected=dddf8872 actual=5e8f6aff", result.stderr)

    def test_reference_checksum_shape_is_supported_by_host_validator(self):
        records = json.loads((ROOT / "resources/cpu-code-rewrite-reference.json").read_text())
        for record in records:
            record.update(name=record["id"], framebuffer_fnv1a64="0" * 16)
            hashes = oracle_validation.record_hashes(record)
            self.assertEqual(hashes["work_checksum"], record["metadata"]["work_checksum"])
            self.assertEqual(hashes["result_checksum"], record["metadata"]["result_checksum"])


if __name__ == "__main__":
    unittest.main()
