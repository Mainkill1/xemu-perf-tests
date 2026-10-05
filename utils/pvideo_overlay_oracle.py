#!/usr/bin/env python3
"""Check synthetic PVIDEO host images against specified quadrant colors.

Pillow is needed only by the CLI. Explicit viewport geometry avoids treating
window borders or guest framebuffer hashes as overlay correctness evidence.
"""
import argparse
import hashlib
import json
from pathlib import Path

BACKGROUND = (51, 76, 153)
NORMAL = 'normal128'
INVERSE = 'inverse128'
SMALL = 'inverse64'
DISABLED = 'disabled'
RESIZE_SEQUENCE = [NORMAL, INVERSE, NORMAL, SMALL, NORMAL, INVERSE, DISABLED, INVERSE]
PROBE_X = (248, 264, 280, 304, 312, 328, 344, 368, 376, 392)
PROBE_Y = (168, 184, 200, 224, 232, 248, 264, 288, 296, 312)


def classify(image, viewport):
    """Return a specified visual state, or unknown; never derive expected pixels."""
    vx, vy, vw, vh = viewport
    if min(vx, vy) < 0 or min(vw, vh) <= 0 or vx + vw > image.size[0] or vy + vh > image.size[1]:
        raise ValueError('viewport must fit the captured image')
    candidates = [('normal128', 128, False), ('inverse128', 128, True),
                  ('normal64', 64, False), ('inverse64', 64, True), ('disabled', 0, False)]
    samples = [(gx, gy, image.getpixel((int(vx + (gx + 0.5) * vw / 640),
                                      int(vy + (gy + 0.5) * vh / 480)))[:3])
               for gy in PROBE_Y for gx in PROBE_X]
    for state, side, inverted in candidates:
        matches = True
        # Explicit four-quadrant luma specification; no observed golden image.
        quadrants = ((255, 0), (0, 255)) if inverted else ((0, 255), (255, 0))
        for gx, gy, pixel in samples:
            want = BACKGROUND
            if 256 <= gx < 256 + side and 176 <= gy < 176 + side:
                luma = quadrants[int(gy >= 176 + side / 2)][int(gx >= 256 + side / 2)]
                want = (luma, luma, luma)
            if any(abs(int(a) - b) > 2 for a, b in zip(pixel, want)):
                matches = False
                break
        if matches:
            return state
    return 'unknown'


def resize_coverage(states):
    """Require one full ordered cycle; duplicate captures do not add coverage.

    Unknown captures break an ordered cycle. Prefix/suffix boot or result
    screens are allowed, but cannot substitute for a required overlay state.
    This does not prove every frame or exact transition timing.
    """
    compressed = []
    for index, state in enumerate(states):
        if not compressed or compressed[-1]['state'] != state:
            compressed.append({'state': state, 'firstCapture': index})
    for start in range(len(compressed) - len(RESIZE_SEQUENCE) + 1):
        cycle = compressed[start:start + len(RESIZE_SEQUENCE)]
        if [row['state'] for row in cycle] == RESIZE_SEQUENCE:
            return {'passed': True, 'cycle': cycle, 'compressed': compressed}
    return {'passed': False, 'cycle': [], 'compressed': compressed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('images', nargs='+', type=Path, help='captures in chronological order')
    parser.add_argument('--viewport', required=True, nargs=4, type=int, metavar=('X', 'Y', 'WIDTH', 'HEIGHT'))
    args = parser.parse_args()
    from PIL import Image
    observations = []
    for path in args.images:
        with Image.open(path) as loaded:
            state = classify(loaded.convert('RGB'), args.viewport)
        observations.append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'state': state})
    coverage = resize_coverage([row['state'] for row in observations])
    print(json.dumps({'oracle': 'specified YUY2 black/white quadrants and RGB background, 100 interior/exterior probes, tolerance2/255',
                      'viewport': args.viewport, 'observations': observations, 'resizeToggleCoverage': coverage,
                      'scope': 'at least one ordered visual cycle; not every frame, timing, allocation or performance qualification'}, indent=2))
    return 0 if coverage['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
