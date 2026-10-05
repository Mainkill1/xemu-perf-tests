"""Known-input checks execute the same fixture helper compiled into the XBE."""
import json
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class PvideoFixtureContract(unittest.TestCase):
    def test_guest_failure_record_and_xemu_only_gate(self):
        source = (ROOT / "src/tests/pvideo_tests.cpp").read_text()
        self.assertNotIn("ASSERT(source_oracle_pass)", source)
        self.assertIn('source_oracle_pass ? "PASS" : "FAIL"', source)
        self.assertIn("host_.FinishDraw(", source)
        main = (ROOT / "src/main.cpp").read_text()
        opt_in = main.split("if (runtime_config.enable_xemu_only_tests()) {", 1)[1].split("\n  }", 1)[0]
        self.assertIn("REG_TEST(PvideoTests)", opt_in)
        self.assertIn('== "Pvideo"', (ROOT / "src/runtime_config.cpp").read_text())

    def test_generated_pixels_and_control_sequence(self):
        source = r'''
#include <cstdint>
#include <cstdio>
#include "src/tests/pvideo_fixture.h"
int main() {
  uint8_t bytes[16] = {};
  if (!PvideoFixture::Fill(bytes, sizeof(bytes), 4, 2, false)) return 10;
  const uint8_t want[] = {16,128,16,128,235,128,235,128,
                         235,128,235,128,16,128,16,128};
  for (unsigned i = 0; i < 16; ++i) if (bytes[i] != want[i]) return 11;
  if (!PvideoFixture::Fill(bytes, sizeof(bytes), 4, 2, true)) return 12;
  const uint8_t inverse[] = {235,128,235,128,16,128,16,128,
                            16,128,16,128,235,128,235,128};
  for (unsigned i = 0; i < 16; ++i) if (bytes[i] != inverse[i]) return 13;
  if (PvideoFixture::Fill(bytes, sizeof(bytes), 3, 2, false)) return 14;
  if (PvideoFixture::Fill(bytes, 7, 4, 2, false)) return 15;
  const unsigned frames[] = {0,64,128,192,256,320,384,448,512};
  const unsigned widths[] = {128,128,128,64,128,128,128,128,128};
  const unsigned offsets[] = {0,0,32768,32768,0,0,0,32768,0};
  const bool enabled[] = {true,true,true,true,true,true,false,true,true};
  for (unsigned i = 0; i < 9; ++i) {
    auto f = PvideoFixture::Frame(frames[i], true);
    if (f.width != widths[i] || f.height != widths[i] ||
        f.offset != offsets[i] || f.enabled != enabled[i] ||
        f.inverted != bool(i % 2)) return 20 + i;
    // Real renderer contract: offset + pitch * height <= LIMIT, where
    // the guest programs the inclusive allocation limit. Test both windows.
    if (f.offset + 2 * f.width * f.height > PvideoFixture::kSourceBytes - 1) return 50 + i;
    auto s = PvideoFixture::Frame(frames[i], false);
    if (s.width != 128 || !s.enabled) return 40 + i;
  }
  uint8_t large[32768];
  const uint64_t golden[2][2] = {
    {0x276e4cfdecdd4325ULL, 0x9fdf411ecdd4325ULL},
    {0x63b16935c68ea325ULL, 0xf4e5cbb5c68ea325ULL}};
  for (unsigned size_index = 0; size_index < 2; ++size_index) {
    unsigned side = size_index ? 128 : 64;
    for (unsigned inv = 0; inv < 2; ++inv) {
      if (!PvideoFixture::Fill(large, sizeof(large), side, side, inv)) return 60;
      uint64_t hash = 14695981039346656037ULL;
      for (unsigned i = 0; i < side * side * 2; ++i)
        hash = (hash ^ large[i]) * 1099511628211ULL;
      if (hash != golden[size_index][inv]) return 61 + 2 * size_index + inv;
    }
  }
  return 0;
}
'''
        with tempfile.TemporaryDirectory() as temp:
            cpp = pathlib.Path(temp) / "contract.cpp"
            exe = pathlib.Path(temp) / "contract"
            cpp.write_text(source)
            subprocess.run(["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                            "-I", str(ROOT), str(cpp), "-o", str(exe)], check=True)
            result = subprocess.run([str(exe)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_catalog_and_frozen_profile_contract(self):
        catalog = json.loads((ROOT / "resources/catalog.json").read_text())
        by_id = {item["id"]: item for item in catalog["tests"]}
        for stable, legacy in (("steady_upload", "SteadyUpload"),
                               ("resize_toggle", "ResizeToggle")):
            leaf = by_id[f"pvideo.{stable}"]
            self.assertEqual(leaf["revision"], 2)
            self.assertEqual(leaf["supported_targets"], ["xemu"])
            self.assertEqual(leaf["legacy_ids"], [f"Pvideo::{legacy}"])
            self.assertEqual(leaf["timeout_ms"], 120000)
            self.assertEqual(leaf["measurement_class"], "correctness")
            self.assertNotIn("performance", leaf["tags"])
            self.assertIn("excludes", leaf["description"])
            self.assertIn({"name": "pvideo.source", "kind": "structured", "scope_version": 1},
                          leaf["observations"])
            profile = json.loads((ROOT / f"resources/pvideo-{stable.replace('_', '-')}.json").read_text())
            self.assertEqual(profile["resolved_plan"]["catalog_id"], catalog["catalog_id"])
            self.assertEqual(profile["resolved_plan"]["tests"], [{"id": f"pvideo.{stable}"}])
            self.assertEqual(profile["settings"]["warmup_iterations"], 0)
            self.assertEqual(profile["settings"]["measurement_iterations_multiplier"], 1)


if __name__ == "__main__":
    unittest.main()
