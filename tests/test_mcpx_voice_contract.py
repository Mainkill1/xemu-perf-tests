"""Compile the independent fixture recipe and verify known input/layout facts."""
import pathlib
import json
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
  if (!McpxVoiceRecipe::MixValueMatches(0x100000, 4096) ||
      !McpxVoiceRecipe::MixValueMatches(0xf00000, -4096)) return 7;
  if (McpxVoiceRecipe::MixValueMatches(0, 4096) ||
      McpxVoiceRecipe::MixValueMatches(0, -4096)) return 8;
  if (McpxVoiceRecipe::MixValueMatches(0xf00000, 4096) ||
      McpxVoiceRecipe::MixValueMatches(0x100000, -4096)) return 9;
  if (!McpxVoiceRecipe::MixValueMatches(0x100020, 4096) ||
      McpxVoiceRecipe::MixValueMatches(0x100021, 4096) ||
      !McpxVoiceRecipe::MixValueMatches(0x0fffe0, 4096) ||
      McpxVoiceRecipe::MixValueMatches(0x0fffdf, 4096) ||
      McpxVoiceRecipe::MixValueMatches(0xff100000, 4096)) return 10;
  if (McpxVoiceRecipe::LoopSamples(true) != 64 ||
      McpxVoiceRecipe::LoopSamples(false) != 4096) return 11;
  for (bool stereo : {false, true}) {
    auto block = McpxVoiceRecipe::EncodedBlock(stereo);
    // Every replayed block crosses the logical boundary and a physically
    // contiguous read encounters poison instead of its encoded tail.
    if (4080 + block.size() <= 4096) return 12;
    std::vector<uint8_t> crossed(5 * 4096, 0xa5);
    if (!McpxVoiceRecipe::CopyLogicalBytes(crossed.data(), crossed.size(),
                                         4080, block.data(), block.size())) return 13;
    for (size_t offset = 16; offset < block.size(); ++offset) {
      if (crossed[4080 + offset] == block[offset] ||
          crossed[8192 + offset - 16] != block[offset]) return 14;
    }
  }
  if (!McpxVoiceRecipe::EngineCanBeOwned(7, 0, 1, 0x3fc8000, 0x3fc4000, {65535, 65535, 65535}) ||
      !McpxVoiceRecipe::EngineCanBeOwned(0, 0, 0, 0, 0, {0, 0, 0})) return 15;
  if (McpxVoiceRecipe::EngineCanBeOwned(8, 0, 1, 0, 0, {65535, 65535, 65535}) ||
      McpxVoiceRecipe::EngineCanBeOwned(7, 3, 1, 0, 0, {65535, 65535, 65535}) ||
      McpxVoiceRecipe::EngineCanBeOwned(7, 0, 3, 0, 0, {65535, 65535, 65535}) ||
      McpxVoiceRecipe::EngineCanBeOwned(7, 0, 1, 0, 0, {64, 65535, 65535}) ||
      McpxVoiceRecipe::EngineCanBeOwned(7, 0, 1, 0x3fc8000, 0x3fc4000, {0, 65535, 65535})) return 16;
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


class McpxVoiceRegistrationTests(unittest.TestCase):
    def test_five_routes_are_xemu_correctness_observations(self):
        catalog = json.loads((ROOT / 'resources/catalog.json').read_text())
        actual = {d['id']: d for d in catalog['tests'] if d['suite_id'] == 'mcpx_voice'}
        expected = {
            'mono_aligned': 'MonoAligned', 'stereo_aligned': 'StereoAligned',
            'mono_page_crossing': 'MonoPageCrossing',
            'stereo_page_crossing': 'StereoPageCrossing', 'pcm_control': 'PcmControl'}
        self.assertEqual(set(actual), {'mcpx_voice.' + name for name in expected})
        for stable, legacy in expected.items():
            descriptor = actual['mcpx_voice.' + stable]
            self.assertEqual(descriptor['legacy_ids'], ['McpxVoice::' + legacy])
            self.assertEqual(descriptor['supported_targets'], ['xemu'])
            self.assertEqual(descriptor['measurement_class'], 'correctness')
            self.assertNotIn('performance', descriptor['tags'])
            self.assertIn({'name': 'apu.mix', 'kind': 'structured', 'scope_version': 1},
                          descriptor['observations'])
        main = (ROOT / 'src/main.cpp').read_text()
        opt_in = main.split('if (runtime_config.enable_xemu_only_tests()) {', 1)[1].split('\n  }', 1)[0]
        self.assertIn('REG_TEST(McpxVoiceTests)', opt_in)
        runtime = (ROOT / 'src/runtime_config.cpp').read_text()
        self.assertIn('== "McpxVoice"', runtime)
        self.assertIn('tests/mcpx_voice_tests.cpp', (ROOT / 'src/CMakeLists.txt').read_text())
        config = json.loads((ROOT / 'resources/mcpx-voice-correctness.json').read_text())
        self.assertEqual(config['resolved_plan']['selected_leaf_count'], 5)
        self.assertEqual(config['settings']['warmup_iterations'], 0)
        self.assertEqual(config['settings']['measurement_iterations_multiplier'], 1)


if __name__ == '__main__':
    unittest.main()
