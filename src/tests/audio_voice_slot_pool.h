#ifndef XEMU_PERF_TESTS_AUDIO_VOICE_SLOT_POOL_H
#define XEMU_PERF_TESTS_AUDIO_VOICE_SLOT_POOL_H

#include <cstdint>

namespace AudioTorture {

class VoiceSlotPool {
 public:
  bool Allocate(uint16_t &handle) {
    if (used_ == 256) {
      handle = 0xFFFF;
      return false;
    }
    handle = static_cast<uint16_t>((64 + used_++) % 256);
    return true;
  }
  uint32_t Count() const { return used_; }

 private:
  uint32_t used_{0};
};

}  // namespace AudioTorture

#endif  // XEMU_PERF_TESTS_AUDIO_VOICE_SLOT_POOL_H
