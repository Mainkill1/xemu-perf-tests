#!/usr/bin/env python3
"""Reconstruct and repeat a public XISO capture using xemu PR #384 tools."""
import argparse
import json
from pathlib import Path
import subprocess
import sys


def verify(args):
    output = args.output.resolve()
    result = subprocess.run([sys.executable, str(args.tools / 'dsp_capture_reconstruct.py'),
                             str(args.capture), '--ram-size', '67108864', '--output', str(output)],
                            capture_output=True, text=True, timeout=30)
    reconstruction = json.loads(result.stdout)
    if result.returncode != 1 or reconstruction.get('artifacts_created') is not True:
        print(json.dumps({'status': 'INCOMPLETE', 'reconstruction': reconstruction}))
        return 1
    frames = reconstruction['frames']
    command = [sys.executable, str(args.tools / 'dsp-replay.py'), 'verify-mapped-trace',
               '--worker', str(args.worker), '--frames', str(frames), '--repeat', str(args.repeat)]
    for name in ('gp-initial', 'ep-initial', 'gp-expected', 'ep-expected', 'mixbins',
                 'prior-pcm', 'expected-pcm', 'apu-registers', 'expected-apu-registers',
                 'ram', 'expected-ram', 'control', 'events', 'gp-frame-states', 'ep-frame-states'):
        command += ['--' + name, str(output / (name + '.bin'))]
    result = subprocess.run(command, capture_output=True, text=True, timeout=args.repeat * 35 + 10)
    replay = json.loads(result.stdout)
    report = {'reconstruction': reconstruction, 'replay': replay,
              'status': 'BASELINE_MATCH' if result.returncode == 0 else replay.get('status', 'INCOMPLETE')}
    (output / 'repeat-report.json').write_text(json.dumps(report, sort_keys=True, indent=2) + '\n')
    print(json.dumps(report, sort_keys=True))
    return result.returncode


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('tools', 'worker', 'capture', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--repeat', type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.repeat <= 10000:
        parser.error('repeat must be 1..10000')
    raise SystemExit(verify(args))
