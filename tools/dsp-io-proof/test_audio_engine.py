#!/usr/bin/env python3
"""Check the DSP/DMA fixture's externally selectable audio engine."""
from pathlib import Path
import importlib.util
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest


class AudioEngineCliTest(unittest.TestCase):
    @staticmethod
    def load_runner():
        runner = Path(__file__).with_name('run_guest.py')
        spec = importlib.util.spec_from_file_location('dsp_io_guest', runner)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_hle_engine_is_advertised(self):
        runner = Path(__file__).with_name('run_guest.py')
        output = subprocess.check_output([sys.executable, str(runner), '--help'], text=True)
        self.assertIn('--audio-engine', output)
        self.assertIn('hle', output)

    def test_guest_failure_finishes_without_a_dsp_completion_marker(self):
        module = self.load_runner()
        self.assertFalse(module.mailbox_terminal([0, 0xbad, 0, 0], False))
        self.assertTrue(module.mailbox_terminal([0, 0xbad, 0, 0], True))
        self.assertFalse(module.mailbox_terminal([0, 0x600d, 0, 0], True))
        self.assertTrue(module.mailbox_terminal([0x51d00d, 0x600d, 0, 0], True))
        self.assertTrue(module.mailbox_terminal([0x51d00d, 0xbad, 0, 0], False))

    def test_circular_dma_wraps_once_and_preserves_data_order(self):
        module = self.load_runner()
        self.assertEqual(module.circular_spans(800, 768, 1024), [(800, 224), (0, 544)])
        self.assertEqual(module.circular_spans(0, 16, 1024), [(0, 16)])
        self.assertEqual(module.circular_spans(256, 1024, 1024), [(256, 768), (0, 256)])
        with self.assertRaises(ValueError):
            module.circular_spans(1024, 4, 1024)
        with self.assertRaises(ValueError):
            module.circular_spans(0, 1028, 1024)

    def test_failed_launch_deletes_only_the_new_private_hdd(self):
        module = self.load_runner()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'original'
            source.write_bytes(b'original disk')
            config = root / 'config.toml'
            config.write_text('[sys.files]\n' + ''.join(
                f'{name} = "{source}"\n' for name in
                ('bootrom_path', 'flashrom_path', 'eeprom_path', 'hdd_path')))
            executable = root / 'not-executable'
            executable.write_bytes(b'not executable')
            args = SimpleNamespace(output=root / 'result', config=config, engine='jit',
                                   audio_engine='default', capture=False, iso=source,
                                   emulator=executable, emulator_binary=None, timeout=1, circular=False)
            with self.assertRaises(PermissionError):
                module.run(args)
            self.assertFalse((args.output / 'private/hdd_path').exists())
            self.assertEqual(source.read_bytes(), b'original disk')

    def test_existing_output_is_not_cleaned(self):
        module = self.load_runner()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            private = root / 'result/private'
            private.mkdir(parents=True)
            existing = private / 'hdd_path'
            existing.write_bytes(b'owned elsewhere')
            with self.assertRaises(FileExistsError):
                module.run(SimpleNamespace(output=root / 'result'))
            self.assertEqual(existing.read_bytes(), b'owned elsewhere')


if __name__ == '__main__':
    unittest.main()
