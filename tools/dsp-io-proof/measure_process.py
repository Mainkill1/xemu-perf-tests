#!/usr/bin/env python3
"""Linux child-only CPU usage and sampled executable RSS for a launch/quit run."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def measure(command, output):
    start = time.monotonic_ns()
    process = subprocess.Popen(command)
    rss_peak = 0
    while True:
        pid, status, usage = os.wait4(process.pid, os.WNOHANG)
        if pid:
            process.returncode = os.waitstatus_to_exitcode(status)
            break
        try:
            fields = dict(line.split(':', 1) for line in Path(f'/proc/{process.pid}/status').read_text().splitlines() if ':' in line)
            # VmHWM belongs to this executable; ru_maxrss may include pre-exec
            # launcher high water. Retain the latter separately, never infer
            # an emulator allocation from the wrapper's resident memory.
            rss_peak = max(rss_peak, int(fields.get('VmHWM', '0').split()[0]))
        except (OSError, ValueError, IndexError):
            pass
        time.sleep(.05)
    wall = (time.monotonic_ns() - start) / 1e9
    cpu = usage.ru_utime + usage.ru_stime
    report = {'wall_seconds': wall, 'user_seconds': usage.ru_utime,
              'system_seconds': usage.ru_stime, 'cpu_seconds': cpu,
              'one_core_cpu_percent': 100 * cpu / wall,
              'sampled_peak_rss_kib': rss_peak,
              'rusage_peak_rss_kib': usage.ru_maxrss,
              'memory_source': 'sampled child proc-status VmHWM; 50ms sampling',
              'exit': process.returncode}
    output.write_text(json.dumps(report) + '\n')
    return process.returncode


if __name__ == '__main__':
    if len(sys.argv) < 3:
        raise SystemExit(2)
    raise SystemExit(measure(sys.argv[2:], Path(sys.argv[1])))
