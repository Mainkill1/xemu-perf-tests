import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pvideo_overlay_oracle', ROOT / 'utils/pvideo_overlay_oracle.py')
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


class ImageSpec:
    size = (640, 480)

    def __init__(self, side=128, inverted=False, damage=None):
        self.side, self.inverted, self.damage = side, inverted, damage

    def getpixel(self, position):
        x, y = position
        if position == self.damage:
            return (99, 99, 99)
        if not (256 <= x < 256 + self.side and 176 <= y < 176 + self.side):
            return (51, 76, 153)
        # Literal normal/inverse quadrant triples, independent of sampler.
        if y < 176 + self.side // 2:
            normal = (0, 0, 0) if x < 256 + self.side // 2 else (255, 255, 255)
        else:
            normal = (255, 255, 255) if x < 256 + self.side // 2 else (0, 0, 0)
        return tuple(255 - channel for channel in normal) if self.inverted else normal


class PvideoOverlayOracleContract(unittest.TestCase):
    def test_known_visual_states(self):
        for side, inverted, want in ((128, False, 'normal128'), (128, True, 'inverse128'),
                                     (64, False, 'normal64'), (64, True, 'inverse64'),
                                     (0, False, 'disabled')):
            self.assertEqual(oracle.classify(ImageSpec(side, inverted), (0, 0, 640, 480)), want)

    def test_damaged_quadrant_or_background_is_not_a_match(self):
        for damage in ((280, 200), (248, 168)):
            self.assertEqual(oracle.classify(ImageSpec(damage=damage), (0, 0, 640, 480)), 'unknown')

    def test_offset_fractional_viewport(self):
        class Scaled:
            size = (1600, 1200)
            def getpixel(self, position):
                x, y = position
                return ImageSpec(64, True).getpixel((int((x - 37) / 2.25), int((y - 21) / 2.25)))
        self.assertEqual(oracle.classify(Scaled(), (37, 21, 1440, 1080)), 'inverse64')

    def test_channel_tolerance_is_two_not_three(self):
        class Noisy(ImageSpec):
            def getpixel(self, position):
                return tuple(min(255, channel + self.noise) for channel in super().getpixel(position))
        image = Noisy()
        image.noise = 2
        self.assertEqual(oracle.classify(image, (0, 0, 640, 480)), 'normal128')
        image.noise = 3
        self.assertEqual(oracle.classify(image, (0, 0, 640, 480)), 'unknown')

    def test_viewport_must_fit_image(self):
        with self.assertRaises(ValueError):
            oracle.classify(ImageSpec(), (1, 0, 640, 480))

    def test_complete_cycle_and_repeated_captures(self):
        states = ['unknown', 'unknown', 'normal128', 'normal128', 'inverse128',
                  'normal128', 'inverse64', 'normal128', 'inverse128', 'disabled', 'inverse128', 'unknown']
        result = oracle.resize_coverage(states)
        self.assertTrue(result['passed'])
        self.assertEqual([r['firstCapture'] for r in result['cycle']], [2, 4, 5, 6, 7, 8, 9, 10])

    def test_missing_resize_disable_stale_pixels_and_unknown_gap_fail(self):
        complete = ['normal128', 'inverse128', 'normal128', 'inverse64',
                    'normal128', 'inverse128', 'disabled', 'inverse128']
        for states in (complete[:3] + complete[4:], complete[:6] + complete[7:],
                       ['normal128'] * 30, complete[:4] + ['unknown'] + complete[4:]):
            self.assertFalse(oracle.resize_coverage(states)['passed'])


if __name__ == '__main__':
    unittest.main()
