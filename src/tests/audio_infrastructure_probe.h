#ifndef XEMU_PERF_TESTS_AUDIO_INFRASTRUCTURE_PROBE_H
#define XEMU_PERF_TESTS_AUDIO_INFRASTRUCTURE_PROBE_H

#include <cstdint>
#include <string>

#include "audio_mcpx_apu_device.h"

namespace AudioTorture {

struct AudioInfrastructureProbeResult {
  McpxApuPciInfo pci{};
  McpxApuRegisterSnapshot registers{};
  uint64_t fixture_checksum{0};
  uint32_t fixture_bytes{0};
};

// Safe, read-only bring-up probe for agent/device testing. It proves that the
// XISO contains the generated fixture, validates its checksum, discovers the
// MCPX APU through PCI, maps BAR0, and reads a small register snapshot.
//
// This is deliberately not a catalog leaf and does not program a voice.
bool ProbeAudioInfrastructure(AudioInfrastructureProbeResult &result,
                              std::string &error);

}  // namespace AudioTorture

#endif  // XEMU_PERF_TESTS_AUDIO_INFRASTRUCTURE_PROBE_H
