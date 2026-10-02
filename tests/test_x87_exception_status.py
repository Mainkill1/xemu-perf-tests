"""Validate the guest's pending-exception status instructions on native x86."""
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(platform.machine().lower() in ('x86_64', 'amd64', 'i386', 'i686')
                     and shutil.which('c++'), 'requires a native x86 C++ compiler')
class X87ExceptionStatusTests(unittest.TestCase):
    def test_native_pending_exception_status(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / 'x87-exception-status-check'
            build = subprocess.run(['c++', '-O2', '-std=c++17',
                                    str(ROOT / 'tests/x87_exception_status_check.cpp'),
                                    '-o', str(executable)], capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            result = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('PASS: 384 masked/pending nonwaiting x87 status vectors', result.stdout)

    def test_status_corruption_negative_controls(self):
        header = (ROOT / 'src/tests/x87_status_workload.h').read_text()
        start = header.index('static inline X87StatusVectorResult CheckX87ExceptionStatusVectors()')
        end = header.index('struct X87StatusWorkResult', start)
        original = header[start:end]
        mutations = [
            ('ES/B removed', 'andl $0xffff7f7f, %%eax', 192),
            ('TOP removed', 'andl $0xffffc7ff, %%eax', 336),
            ('upper EAX removed', 'andl $0x0000ffff, %%eax', 384),
        ]
        for name, instruction, expected_failures in mutations:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                temporary = Path(directory)
                (temporary / 'src/tests').mkdir(parents=True)
                (temporary / 'tests').mkdir()
                changed = original.replace('fnstsw %%ax\\n\\t',
                                           'fnstsw %%ax\\n\\t' + instruction + '\\n\\t')
                self.assertNotEqual(changed, original)
                (temporary / 'src/tests/x87_status_workload.h').write_text(
                    header[:start] + changed + header[end:])
                source = temporary / 'tests/x87_exception_status_check.cpp'
                source.write_text((ROOT / 'tests/x87_exception_status_check.cpp').read_text())
                executable = temporary / 'check'
                build = subprocess.run(['c++', '-O2', '-std=c++17', str(source), '-o', str(executable)],
                                       capture_output=True, text=True)
                self.assertEqual(build.returncode, 0, build.stderr)
                result = subprocess.run([str(executable)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(f'cases=384 failures={expected_failures}', result.stderr)


if __name__ == '__main__':
    unittest.main()
