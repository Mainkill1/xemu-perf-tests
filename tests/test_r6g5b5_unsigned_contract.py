"""Unsigned R6G5B5 source/pixel oracles, independent of emulator output."""
import json
import re
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'src/tests/texture_cubemap_fallback_tests.cpp'
WORDS = (0x0000, 0xffff, 0xfc00, 0x03e0, 0x001f, 0x8210, 0x7ceb, 0x0001)
RGB = ((0, 0, 0), (255, 255, 255), (255, 0, 0), (0, 255, 0),
       (0, 0, 255), (130, 132, 132), (125, 57, 90), (0, 0, 8))


def payload(size):
    levels = size.bit_length()
    face_bytes = sum((16 >> level) ** 2 * 2 for level in range(levels))
    stride = (face_bytes + 127) & ~127
    data = bytearray(6 * stride)
    for face in range(6):
        offset = face * stride
        for level in range(levels):
            stored, logical = 16 >> level, max(1, size >> level)
            inset = 4 >> level if level < 3 else 0
            for y in range(stored):
                for x in range(stored):
                    word = 0
                    if inset <= x < inset + logical and inset <= y < inset + logical:
                        index = (face * 37 + level * 19 + (x-inset) * 7 +
                                 (y-inset) * 11) % 251 + 1
                        word = WORDS[index % len(WORDS)]
                    morton = sum(((x >> bit) & 1) << (2*bit) |
                                 ((y >> bit) & 1) << (2*bit+1) for bit in range(4))
                    struct.pack_into('<H', data, offset + morton * 2, word)
            offset += stored * stored * 2
    return data


def fnv32(data):
    result = 2166136261
    for byte in data:
        result = ((result ^ byte) * 16777619) & 0xffffffff
    return result


class R6G5B5UnsignedContract(unittest.TestCase):
    def test_guest_literals_match_unsigned_format(self):
        source = SOURCE.read_text()
        words = re.search(r'kR6G5B5Words\[\]\s*=\s*\{([^}]+)', source)
        self.assertIsNotNone(words, 'guest still encodes signed R6G5B5 known answers')
        self.assertEqual(tuple(int(x, 0) for x in words[1].split(',') if x.strip()), WORDS)
        colors = re.search(r'kR6G5B5Rgb\[\]\[3\]\s*=\s*\{(.*?)\n\};', source, re.S)
        self.assertIsNotNone(colors)
        actual = tuple(tuple(map(int, x.split(','))) for x in re.findall(r'\{([^}]+)\}', colors[1]))
        self.assertEqual(actual, RGB)
        self.assertNotIn('SignedColorMatches', source)

    def test_payload_hashes_bind_all_faces_and_mips(self):
        source = SOURCE.read_text()
        match = re.search(r'kR6G5B5SourceKats\[\]\s*=\s*\{([^}]+)', source)
        self.assertIsNotNone(match)
        guest = tuple(int(x, 0) for x in match[1].split(',') if x.strip())
        self.assertEqual(guest, tuple(fnv32(payload(size)) for size in (1, 2, 4, 8)))

    def test_sampled_colors_cover_known_answers_and_horizontal_changes(self):
        selected = set()
        for size in (1, 2, 4, 8):
            for level in range(size.bit_length()):
                logical = max(1, size >> level)
                for face in range(6):
                    for sx, sy in ((0, 0), (1, 0), (0, 1), (1, 1), (2, 2)):
                        x = 0 if sx == 0 else logical-1 if sx == 1 else logical//2
                        y = 0 if sy == 0 else logical-1 if sy == 1 else logical//2
                        index = (face*37 + level*19 + x*7 + y*11) % 251 + 1
                        selected.add(index % len(WORDS))
                    for x in range(logical-1):
                        left = ((face*37 + level*19 + x*7) % 251 + 1) % len(WORDS)
                        right = ((face*37 + level*19 + (x+1)*7) % 251 + 1) % len(WORDS)
                        self.assertNotEqual(left, right)
        self.assertEqual(selected, set(range(len(WORDS))))

    def test_only_affected_catalog_revisions_change(self):
        catalog = json.loads((ROOT/'resources/catalog.json').read_text())
        for entry in catalog['tests']:
            if entry['suite_id'] == 'texture_cubemap_fallback':
                self.assertEqual(entry['revision'], 2 if '.bordered_r6g5b5_' in entry['id'] else 1)
                self.assertEqual(entry['supported_targets'], ['xemu'])


if __name__ == '__main__':
    unittest.main()
