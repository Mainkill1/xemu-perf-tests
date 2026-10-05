#include <array>
#include <cassert>
#include <cstring>
#include <set>
#include <string>
#include <vector>

#include "audio_voice_slot_pool.h"
#include "audio_vp_scaling_recipe.h"
#include "audio_s16_control_oracle.h"

namespace {
uint32_t Word(const uint8_t *table, uint16_t handle, uint32_t offset) {
  uint32_t value{};
  std::memcpy(&value, table + handle * 128 + offset, 4);
  return value;
}
}

int main() {
  using namespace AudioTorture;
  VoiceSlotPool pool;
  std::set<uint16_t> handles;
  for (unsigned i = 0; i < 256; ++i) {
    uint16_t handle = 0xFFFF;
    assert(pool.Allocate(handle));
    assert(handle == (64 + i) % 256 && handles.insert(handle).second);
  }
  uint16_t refused{};
  assert(!pool.Allocate(refused) && refused == 0xFFFF && pool.Count() == 256);

  WorkloadSpec spec{};
  spec.channels = 2;
  spec.voice_count = 2;
  std::vector<uint8_t> source;
  std::string error;
  assert(BuildS16ScalingSource(spec, source, error) && source.size() == 1028);
  for (size_t i = 0; i < source.size(); i += 4) {
    assert(source[i] == 0 && source[i + 1] == 8);
    assert(source[i + 2] == 0 && source[i + 3] == 0xF8);
  }
  std::array<uint8_t, 32768> voices{};
  assert(PrepareS16ScalingVoiceTable(spec, voices.data(), voices.size(), 257, error));
  assert(Word(voices.data(), 64, 0x7C) == 65);
  assert(Word(voices.data(), 65, 0x7C) == 0xFFFF);
  assert(Word(voices.data(), 64, 0x1C) == 0xFFFF);
  assert(Word(voices.data(), 64, 0x5C) == 0xFF000100U);
  assert(Word(voices.data(), 64, 0x04) == 0x5A0103FFU);
  spec.channels = 1;
  spec.voice_count = 256;
  assert(BuildS16ScalingSource(spec, source, error) && source.size() == 514);
  assert(source[0] == 16 && source[1] == 0);
  assert(PrepareS16ScalingVoiceTable(spec, voices.data(), voices.size(), 257, error));
  for (unsigned i = 0; i < 256; ++i) {
    const auto handle = ScalingVoiceHandle(i);
    assert(Word(voices.data(), handle, 0x1C) == 0xFFFF);
    if (handle < 64) {
      // HRTF bypass does not bypass the first four slots' special routing.
      assert((Word(voices.data(), handle, 0) >> 21 & 31) == 0);
      assert((Word(voices.data(), handle, 0) >> 26 & 31) == 1);
      assert(Word(voices.data(), handle, 0x60) == 0xFFFFFFFFU);
      assert(Word(voices.data(), handle, 0x68) == 0x000F000FU);
    }
    assert(Word(voices.data(), handle, 0x7C) ==
           (i == 255 ? 0xFFFFU : ScalingVoiceHandle(i + 1)));
  }
  spec.voice_count = 257;
  assert(!BuildS16ScalingSource(spec, source, error));
  spec.voice_count = 1;
  spec.channels = 3;
  assert(!BuildS16ScalingSource(spec, source, error));
  spec.channels = 1;
  assert(!PrepareS16ScalingVoiceTable(spec, voices.data(), 127, 257, error));

  spec.channels = 2;
  spec.voice_count = 2;
  assert(BuildS16ScalingSource(spec, source, error));
  S16ScalingObservation observed{};
  observed.source = source.data();
  observed.source_bytes = source.size();
  observed.channels = 2;
  observed.requested_voice_count = 2;
  observed.observed_voice_count = 2;
  observed.observed_engine_frames = 8;
  observed.left_mix_words.fill(0x100000U);
  observed.right_mix_words.fill(0xF00000U);
  assert(S16ScalingOracle::Check(observed));
  observed.observed_voice_count = 1;
  assert(!S16ScalingOracle::Check(observed));
  observed.observed_voice_count = 2;
  observed.observed_engine_frames = 7;
  assert(!S16ScalingOracle::Check(observed));
  observed.observed_engine_frames = 8;
  observed.right_mix_words.fill(0x100000U);
  assert(!S16ScalingOracle::Check(observed));
  observed.right_mix_words.fill(0xF00000U);
  observed.left_mix_words[7] += 33;
  assert(!S16ScalingOracle::Check(observed));
  observed.left_mix_words.fill(0);
  observed.right_mix_words.fill(0);
  assert(!S16ScalingOracle::Check(observed));
}
