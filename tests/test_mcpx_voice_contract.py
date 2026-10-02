"""Compile the independent fixture recipe and verify known input/layout facts."""
import pathlib
import shutil
import struct
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class McpxVoiceRecipeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        directory = pathlib.Path(cls.temp.name)
        source = directory / 'recipe.cpp'
        source.write_text(r'''
#include "src/tests/mcpx_voice_recipe.h"
#include <cstdio>
#include <vector>
int main() {
  for (bool stereo : {false, true}) {
    auto block = McpxVoiceRecipe::EncodedBlock(stereo);
    fwrite(block.data(), 1, block.size(), stdout);
  }
  std::vector<uint8_t> memory(5 * 4096, 0xa5), input(4608);
  for (size_t i = 0; i < input.size(); ++i) input[i] = uint8_t(i * 17 + 3);
  if (!McpxVoiceRecipe::CopyLogicalBytes(memory.data(), memory.size(),
                                       4080, input.data(), input.size())) return 1;
  fwrite(memory.data(), 1, memory.size(), stdout);
  auto before = memory;
  if (McpxVoiceRecipe::CopyLogicalBytes(memory.data(), memory.size(),
                                      3 * 4096 - 1, input.data(), 2)) return 2;
  if (McpxVoiceRecipe::CopyLogicalBytes(memory.data(), memory.size() - 1,
                                      4080, input.data(), input.size())) return 3;
  if (McpxVoiceRecipe::CopyLogicalBytes(memory.data(), memory.size(),
                                      size_t(-1), input.data(), 2)) return 4;
  if (McpxVoiceRecipe::CopyLogicalBytes(memory.data(), memory.size(),
                                      0, nullptr, 1)) return 5;
  if (memory != before) return 6;
}
''')
        compiler = shutil.which('g++') or shutil.which('clang++')
        if compiler is None:
            raise RuntimeError('A host C++ compiler is required for recipe contracts')
        binary = directory / 'recipe'
        built = subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
                                '-I', str(ROOT), str(source), '-o', str(binary)],
                               capture_output=True, text=True)
        if built.returncode:
            raise AssertionError(built.stderr)
        cls.payload = subprocess.check_output([str(binary)])

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_mono_and_stereo_headers_and_zero_nibbles(self):
        self.assertEqual(len(self.payload), 36 + 72 + 5 * 4096)
        self.assertEqual(self.payload[:36], struct.pack('<hBB', 4096, 0, 0) + bytes(32))
        self.assertEqual(self.payload[36:108],
                         struct.pack('<hBBhBB', 4096, 0, 0, -4096, 0, 0) + bytes(64))

    def test_independent_constant_decoder_known_answer(self):
        # IMA index 0 => step 7, zero nibble => delta 7//8=0,
        # index decrement clamps at 0. No implementation decoder is reused.
        for block, channels in [(self.payload[:36], 1), (self.payload[36:108], 2)]:
            predictors = [struct.unpack_from('<h', block, ch * 4)[0] for ch in range(channels)]
            expected = [4096] if channels == 1 else [4096, -4096]
            decoded = [predictors.copy()]
            for _ in range(64):
                decoded.append([value + 7 // 8 for value in decoded[-1]])
            self.assertEqual(decoded, [expected] * 65)
            self.assertEqual(block[4 * channels:], bytes(32 * channels))

    def test_scattered_mapping_and_every_untouched_byte(self):
        memory = self.payload[108:]
        expected = bytearray([0xa5] * (5 * 4096))
        for i in range(4608):
            logical = 4080 + i
            physical = (logical // 4096) * 2 * 4096 + logical % 4096
            expected[physical] = (i * 17 + 3) & 255
        self.assertEqual(memory, expected)
        self.assertEqual(memory[4096:8192], bytes([0xa5]) * 4096)
        self.assertEqual(memory[12288:16384], bytes([0xa5]) * 4096)


if __name__ == '__main__':
    unittest.main()
