"""Exercise the same instruction workload on the native host x87 engine."""
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class X87StatusWorkloadTests(unittest.TestCase):
    def test_guest_wrappers_preserve_failing_result_records(self):
        source = (ROOT / 'src/tests/cpu_floating_point_tests.cpp').read_text()
        for name in ('TestX87StatusVectors', 'TestX87ExceptionStatus',
                     'TestX87FaultCheckpoint', 'TestX87StatusWork'):
            body = source.split(f'void CpuFloatingPointTests::{name}(', 1)[1].split('\n}\n', 1)[0]
            self.assertNotIn('ASSERT(failures == 0)', body, name)
            self.assertIn('oracle_status', body, name)
            self.assertIn('host_.FinishDraw(', body, name)

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
