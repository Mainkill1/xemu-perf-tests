#include "audio_bootstrap_smoke.h"

#include <sstream>
#include <vector>

#include "audio_fixture_loader.h"
#include "audio_infrastructure_probe.h"
#include "audio_nxaudio_backend.h"

namespace AudioTorture {

bool RunAudioBootstrapSmoke(std::string &report) {
  report.clear();
  std::ostringstream out;

  AudioInfrastructureProbeResult infrastructure{};
  std::string error;
  if (!ProbeAudioInfrastructure(infrastructure, error)) {
    report = "infrastructure probe failed: " + error;
    return false;
  }

  out << "PCI " << std::hex << infrastructure.pci.bus << ":"
      << infrastructure.pci.device << "." << infrastructure.pci.function
      << " BAR0=0x" << infrastructure.pci.bar0_physical << std::dec
      << " fixture_bytes=" << infrastructure.fixture_bytes << "\n";

  const AudioFixtureSpec *fixture =
      FindAudioFixture("vp.s16.mono.48k.256");
  if (!fixture) {
    report = "reference S16 fixture is missing";
    return false;
  }

  std::vector<uint8_t> bytes;
  if (!LoadAudioFixture(*fixture, bytes, error)) {
    report = "fixture load failed: " + error;
    return false;
  }

  NxAudioBackend backend;
  if (!backend.Initialize()) {
    report = "nxdk-audio initialization failed";
    return false;
  }

  WorkloadSpec spec{};
  spec.format = SampleFormat::kS16;
  spec.channels = 1;
  spec.source_rate_hz = 48000;
  spec.voice_count = 1;
  spec.audio_frames = 8;
  spec.mixbin_fanout = 1;

  WorkloadResult result{};
  const bool ran =
      backend.Run(spec, bytes.data(), bytes.size(), result);
  backend.Shutdown();

  if (!ran) {
    out << "reference voice failed backend_errors=" << result.backend_errors
        << " completion_timeouts=" << result.completion_timeouts
        << " underruns=" << result.underruns;
    report = out.str();
    return false;
  }

  out << "S16 mono voice PASS"
      << " source_fnv=0x" << std::hex << result.source_checksum << std::dec
      << " active=" << result.peak_active_voices
      << " completed_frames=" << result.completed_sample_frames
      << " backend_errors=" << result.backend_errors
      << " completion_timeouts=" << result.completion_timeouts
      << " underruns=" << result.underruns;
  report = out.str();
  return true;
}

}  // namespace AudioTorture
