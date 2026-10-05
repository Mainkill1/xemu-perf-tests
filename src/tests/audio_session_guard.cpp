#include "audio_session_guard.h"

#include <atomic>

namespace AudioTorture {
namespace {
std::atomic<bool> session_poisoned{false};
}  // namespace

bool AudioSessionPoisoned() {
  return session_poisoned.load(std::memory_order_acquire);
}

void PoisonAudioSession() {
  session_poisoned.store(true, std::memory_order_release);
}

}  // namespace AudioTorture
