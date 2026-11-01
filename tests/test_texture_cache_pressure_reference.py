"""Independently derive the pressure recipe's byte oracle and test mutations."""

import json
import struct
import unittest
from pathlib import Path


class TextureCachePressureReferenceTests(unittest.TestCase):
    def test_pixel_reference_and_single_word_mutation(self):
        root = Path(__file__).resolve().parents[1]
        reference = json.loads(
            (root / "resources/texture-cache-pressure-reference.json").read_text()
        )[0]
        colors = (0xFFFF0000, 0xFF00FF00, 0xFF0000FF, 0xFFFFFF00)
        words = [colors[tile % 4] for _ in range(3) for tile in range(272)
                 for _ in range(16)]

        def hash_words(values):
            checksum = 2166136261
            for word in values:
                for byte in struct.pack("<I", word):
                    checksum = ((checksum ^ byte) * 16777619) & 0xFFFFFFFF
            return checksum

        self.assertEqual(reference["metadata"]["checked_words"], len(words))
        self.assertEqual(reference["metadata"]["source_kat"], hash_words(words))
        words[256 * 16] ^= 1  # First tile beyond 1,024 four-stage identities.
        self.assertNotEqual(reference["metadata"]["source_kat"], hash_words(words))


if __name__ == "__main__":
    unittest.main()
