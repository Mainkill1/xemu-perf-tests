"""Exercise the same instruction workload on the native host x87 engine."""
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class X87StatusWorkloadTests(unittest.TestCase):
    @unittest.skipUnless(platform.machine().lower() in ('x86_64', 'amd64', 'i386', 'i686')
                         and shutil.which('c++'), 'requires a native x86 C++ compiler')
    def test_native_instruction_oracles(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / 'x87-status-check'
            subprocess.run(['c++', '-O2', '-std=c++17',
                            str(ROOT / 'tests/x87_status_workload_check.cpp'),
                            '-o', str(executable)], check=True, capture_output=True)
            result = subprocess.run([str(executable)], check=True,
                                    capture_output=True, text=True)
            self.assertIn('PASS: x87 status vectors and both fixed-work oracles', result.stdout)

if __name__ == '__main__':
    unittest.main()
