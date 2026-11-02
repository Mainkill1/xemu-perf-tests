#!/usr/bin/env python3
"""Compare one valid second of the periodic public stereo fixture, phase aligned."""
import argparse
from array import array
import json
from pathlib import Path
import sys

from analyze_capture import RATE, analyze


def compare(reference, candidate, ratio=1.0, tolerance=1):
    results = [analyze(data, ratio) for data in (reference, candidate)]
    if any(result['status'] != 'PASS' for result in results):
        return {'status': 'INCOMPLETE', 'reason': 'both captures must pass the tone oracle'}
    samples = []
    for data, result in zip((reference, candidate), results):
        pcm = array('h')
        pcm.frombytes(data)
        if sys.byteorder != 'little':
            pcm.byteswap()
        second = [window['second'] for window in result['windows'] if window['valid']][-1]
        samples.append(pcm[second * RATE * 2:(second + 1) * RATE * 2])
    expected, actual = samples
    # Both public tones repeat every 100 frames. A single shared shift keeps
    # their relative channel phase observable instead of aligning each alone.
    shift = min(range(100), key=lambda offset: sum(
        abs(expected[2 * frame + channel] - actual[2 * ((frame + offset) % RATE) + channel])
        for frame in range(1000) for channel in range(2)))
    maximum = [0, 0]
    total = [0, 0]
    differences = [0, 0]
    for frame in range(RATE):
        for channel in range(2):
            delta = abs(expected[2 * frame + channel] - actual[2 * ((frame + shift) % RATE) + channel])
            maximum[channel] = max(maximum[channel], delta)
            total[channel] += delta
            differences[channel] += delta != 0
    return {'status': 'PASS' if max(maximum) <= tolerance else 'MISMATCH',
            'phase_shift_frames': shift, 'compared_frames': RATE, 'tolerance_lsb': tolerance,
            'max_absolute_difference': maximum, 'mean_absolute_difference': [x / RATE for x in total],
            'differing_samples': differences,
            'scope': 'one second of periodic public stereo tone; not game audio or DSP state'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--right-left-ratio', type=float, default=1.0)
    args = parser.parse_args()
    result = compare(args.reference.read_bytes(), args.candidate.read_bytes(), args.right_left_ratio)
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)
