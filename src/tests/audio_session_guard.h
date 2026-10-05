#ifndef XEMU_PERF_TESTS_AUDIO_SESSION_GUARD_H
#define XEMU_PERF_TESTS_AUDIO_SESSION_GUARD_H

namespace AudioTorture {

// A failed device teardown makes later audio work unsafe for this title run.
bool AudioSessionPoisoned();
void PoisonAudioSession();

}  // namespace AudioTorture

#endif  // XEMU_PERF_TESTS_AUDIO_SESSION_GUARD_H
