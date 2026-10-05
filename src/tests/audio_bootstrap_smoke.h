#ifndef XEMU_PERF_TESTS_AUDIO_BOOTSTRAP_SMOKE_H
#define XEMU_PERF_TESTS_AUDIO_BOOTSTRAP_SMOKE_H

#include <string>

namespace AudioTorture {

// Development-only smoke used before audio leaves are promoted into the stable
// catalog. It validates one checked-in S16 fixture, the read-only PCI/BAR
// probe, and one real static MCPX voice through the reference backend.
bool RunAudioBootstrapSmoke(std::string &report);

}  // namespace AudioTorture

#endif  // XEMU_PERF_TESTS_AUDIO_BOOTSTRAP_SMOKE_H
