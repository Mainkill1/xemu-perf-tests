"""Exercise the faulting instruction sequences and captured FP state on Linux."""
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(platform.system() == 'Linux'
                     and platform.machine().lower() in ('x86_64', 'amd64')
                     and shutil.which('c++'), 'requires Linux x86-64 signal FP context')
class X87FaultTests(unittest.TestCase):
    def test_native_memory_fault_state_and_resumption(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / 'x87-fault-check'
            build = subprocess.run(['c++', '-O2', '-std=c++17',
                                    str(ROOT / 'tests/x87_fault_check.cpp'),
                                    '-o', str(executable)], capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            result = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('PASS: 4 actual x87 memory-fault captures and resumptions', result.stdout)

    def test_resumed_exception_flag_negative_control(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            source = temporary / 'check.cpp'
            original = (ROOT / 'tests/x87_fault_check.cpp').read_text()
            original = original.replace('../src/tests/x87_fault_workload.h',
                                        str(ROOT / 'src/tests/x87_fault_workload.h'))
            marker = 'failures |= CheckX87FaultCapture(captured, pair, control_word);'
            self.assertIn(marker, original)
            # Initial capture stays correct; corrupt only the context used by
            # the OS to resume the interrupted instruction sequence.
            source.write_text(original.replace(marker, marker +
                              '\n  context->uc_mcontext.fpregs->swd |= 1;'))
            executable = temporary / 'check'
            build = subprocess.run(['c++', '-O2', '-std=c++17', str(source), '-o', str(executable)],
                                   capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            result = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn('x87 fault cases=4 failures=', result.stderr)
            self.assertNotIn('failures=0', result.stderr)

    def test_dirty_value_and_eax_negative_controls(self):
        header = (ROOT / 'src/tests/x87_fault_workload.h').read_text()
        mutations = [
            ('stale scalar value', 'fadd %%st, %%st', 'fnop'),
            ('missing stack update', 'faddp', 'fnop'),
            ('upper EAX lost', 'movl $0xa5a50000, %%eax', 'movl $0, %%eax'),
            ('resumed state lost', 'fxsave %[resumed]', r'fninit\n\tfxsave %[resumed]'),
        ]
        for name, original, replacement in mutations:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                temporary = Path(directory)
                (temporary / 'src/tests').mkdir(parents=True)
                (temporary / 'tests').mkdir()
                self.assertIn(original, header)
                (temporary / 'src/tests/x87_fault_workload.h').write_text(header.replace(original, replacement))
                (temporary / 'src/tests/x87_status_workload.h').write_text(
                    (ROOT / 'src/tests/x87_status_workload.h').read_text())
                source = temporary / 'tests/x87_fault_check.cpp'
                source.write_text((ROOT / 'tests/x87_fault_check.cpp').read_text())
                executable = temporary / 'check'
                build = subprocess.run(['c++', '-O2', '-std=c++17', str(source), '-o', str(executable)],
                                       capture_output=True, text=True)
                self.assertEqual(build.returncode, 0, build.stderr)
                result = subprocess.run([str(executable)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn('x87 fault cases=4 failures=', result.stderr)
                self.assertNotIn('failures=0', result.stderr)


if __name__ == '__main__':
    unittest.main()
