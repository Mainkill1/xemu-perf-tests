#ifndef XEMU_PERF_TESTS_AUDIO_FIXTURE_LOADER_H
#define XEMU_PERF_TESTS_AUDIO_FIXTURE_LOADER_H

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace AudioTorture {

enum class AudioFixtureEncoding : uint8_t {
  kWavPcmS16,
  kVpPcmS16,
  kVpPcmS24B32,
  kVpPcmS32,
  kVpImaAdpcm,
  kGoldenPcmS16,
};

struct AudioFixtureSpec {
  const char *id;
  const char *disc_path;
  AudioFixtureEncoding encoding;
  uint32_t channels;
  uint32_t sample_rate_hz;
  uint32_t frames;
  uint32_t byte_count;
  uint64_t fnv1a64;
};

struct WavPcm16View {
  const uint8_t *data{nullptr};
  size_t byte_count{0};
  uint16_t channels{0};
  uint32_t sample_rate_hz{0};
  uint32_t frame_count{0};
};

const AudioFixtureSpec *FindAudioFixture(const std::string &id);
size_t AudioFixtureCount();
const AudioFixtureSpec &AudioFixtureAt(size_t index);

bool LoadAudioFixture(const AudioFixtureSpec &spec, std::vector<uint8_t> &bytes,
                      std::string &error);
bool ParseWavPcm16(const std::vector<uint8_t> &bytes, WavPcm16View &view,
                   std::string &error);

}  // namespace AudioTorture

#endif  // XEMU_PERF_TESTS_AUDIO_FIXTURE_LOADER_H
