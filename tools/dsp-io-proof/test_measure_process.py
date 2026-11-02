#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

import measure_process

spec = importlib.util.spec_from_file_location('run_guest', Path(__file__).with_name('run_guest.py'))
guest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guest)


class ResourceTests(unittest.TestCase):
    def test_child_cpu_and_executable_memory_are_measured(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'usage.json'
            code = ('import time; data=bytearray(16*1024*1024); '
                    'end=time.process_time()+.1\nwhile time.process_time()<end: pass\ntime.sleep(.1)')
            self.assertEqual(measure_process.measure([sys.executable, '-c', code], output), 0)
            result = json.loads(output.read_text())
            self.assertGreater(result['cpu_seconds'], .05)
            self.assertGreater(result['wall_seconds'], result['cpu_seconds'])
            self.assertGreater(result['sampled_peak_rss_kib'], 16000)
            self.assertLess(result['sampled_peak_rss_kib'], 128000)

    def test_failure_exit_is_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'usage.json'
            self.assertEqual(measure_process.measure([sys.executable, '-c', 'raise SystemExit(3)'], output), 3)
            self.assertEqual(json.loads(output.read_text())['exit'], 3)

    def test_group_cleanup_kills_descendant_after_leader_exits(self):
        code = ('import os,signal,time\nr,w=os.pipe(); pid=os.fork()\n'
                'if pid==0:\n os.close(r); signal.signal(signal.SIGTERM,signal.SIG_IGN); '
                'os.write(w,b"ready"); time.sleep(30)\n'
                'else:\n os.close(w); os.read(r,5); print(pid,flush=True); time.sleep(30)\n')
        process = subprocess.Popen([sys.executable, '-c', code], stdout=subprocess.PIPE,
                                   text=True, start_new_session=True)
        child = int(process.stdout.readline())
        guest.terminate_group(process)
        process.stdout.close()
        status = Path(f'/proc/{child}/status')
        deadline = time.monotonic() + 2
        while status.exists():
            # SIGKILL delivery is asynchronous; wait for exit, not a fixed delay.
            state = next(line for line in status.read_text().splitlines() if line.startswith('State:'))
            if 'Z' in state:
                break
            self.assertLess(time.monotonic(), deadline, state)
            time.sleep(.01)


if __name__ == '__main__':
    unittest.main()
