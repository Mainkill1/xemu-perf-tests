#include "audio_infrastructure_probe.h"

#include <vector>

#include "audio_fixture_loader.h"
#include "audio_torture_support.h"

namespace AudioTorture {

bool ProbeAudioInfrastructure(AudioInfrastructureProbeResult &result,
                              std::string &error) {
  result = {};
  error.clear();

  const AudioFixtureSpec *fixture =
      FindAudioFixture("vp.s16.mono.48k.256");
  if (!fixture) {
    error = "S16 infrastructure fixture is missing from generated catalog";
    return false;
  }

  std::vector<uint8_t> bytes;
  if (!LoadAudioFixture(*fixture, bytes, error)) {
    return false;
  }

  result.fixture_checksum = Fnv1a64(bytes.data(), bytes.size());
  result.fixture_bytes = static_cast<uint32_t>(bytes.size());

  McpxApuDevice device;
  if (!device.ProbeAndMap(error)) {
    return false;
  }
  result.pci = device.PciInfo();
  if (!device.Snapshot(result.registers, error)) {
    return false;
  }

  return true;
}

}  // namespace AudioTorture
