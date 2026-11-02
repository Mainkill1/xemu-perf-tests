#!/usr/bin/env python3
"""Check captured 48 kHz signed-16 stereo against the public square-wave fixture."""
import argparse
from array import array
import json
import math
from pathlib import Path
import sys

RATE = 48000


def amplitude(samples, frequency):
    coefficient = 2 * math.cos(2 * math.pi * frequency / RATE)
    previous = previous2 = 0.0
    for sample in samples:
        current = sample + coefficient * previous - previous2
        previous2, previous = previous, current
    magnitude = math.sqrt(max(0.0, previous * previous + previous2 * previous2 -
                              coefficient * previous * previous2))
    return 2 * magnitude / len(samples)


def analyze(data, right_left_ratio=1.0):
    if not 0 < right_left_ratio <= 4:
        raise ValueError('invalid expected channel ratio')
    if len(data) % 4 or len(data) < 3 * RATE * 4:
        return {'status': 'INCOMPLETE', 'reason': 'need three complete seconds of stereo PCM'}
    pcm = array('h')
    pcm.frombytes(data)
    if sys.byteorder != 'little':
        pcm.byteswap()
    windows, consecutive, best = [], 0, 0
    for second in range(len(pcm) // (RATE * 2)):
        block = pcm[second * RATE * 2:(second + 1) * RATE * 2]
        left, right = block[::2], block[1::2]
        la, lb = amplitude(left, 480), amplitude(left, 960)
        ra, rb = amplitude(right, 480), amplitude(right, 960)
        lrms = math.sqrt(sum(x * x for x in left) / RATE)
        rrms = math.sqrt(sum(x * x for x in right) / RATE)
        clipping = sum(abs(x) >= 32767 for x in block)
        valid = (1000 <= la <= 20000 and 1000 <= rb <= 20000 and
                 lb < la * .1 and ra < rb * .1 and
                 1000 <= lrms <= 20000 and 1000 <= rrms <= 20000 and
                 abs(rb / la - right_left_ratio) <= right_left_ratio * .08 and clipping == 0)
        consecutive = consecutive + 1 if valid else 0
        best = max(best, consecutive)
        windows.append({'second': second, 'left_rms': lrms, 'right_rms': rrms,
                        'left_480': la, 'left_960': lb, 'right_480': ra,
                        'right_960': rb, 'clipped_samples': clipping, 'valid': valid})
    return {'status': 'PASS' if best >= 3 else 'FAIL', 'consecutive_seconds': best,
            'sample_rate': RATE, 'channels': 2, 'right_left_ratio': right_left_ratio, 'windows': windows,
            'scope': 'fixture stereo tone and channel isolation; not effects or game audio'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('--right-left-ratio', type=float, default=1.0)
    args = parser.parse_args()
    result = analyze(args.capture.read_bytes(), args.right_left_ratio)
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)
