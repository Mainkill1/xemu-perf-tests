#include "audio_fixture_loader.h"

#include <cassert>
#include <cstring>
#include <fstream>
#include <limits>

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wignored-attributes"
#include <hal/debug.h>
#pragma clang diagnostic pop

#include "audio_torture_support.h"

namespace AudioTorture {

#include "generated/audio_fixture_catalog.inc"

namespace {

uint16_t ReadLe16(const uint8_t *value) {
  return static_cast<uint16_t>(value[0]) |
         (static_cast<uint16_t>(value[1]) << 8U);
}

uint32_t ReadLe32(const uint8_t *value) {
  return static_cast<uint32_t>(value[0]) |
         (static_cast<uint32_t>(value[1]) << 8U) |
         (static_cast<uint32_t>(value[2]) << 16U) |
         (static_cast<uint32_t>(value[3]) << 24U);
}

bool FourCcEquals(const uint8_t *value, const char *expected) {
  return std::memcmp(value, expected, 4) == 0;
}

}  // namespace

const AudioFixtureSpec *FindAudioFixture(const std::string &id) {
  for (size_t i = 0; i < kAudioFixtureSpecCount; ++i) {
    if (id == kAudioFixtureSpecs[i].id) {
      return &kAudioFixtureSpecs[i];
    }
  }
  return nullptr;
}

size_t AudioFixtureCount() { return kAudioFixtureSpecCount; }

const AudioFixtureSpec &AudioFixtureAt(size_t index) {
  assert(index < kAudioFixtureSpecCount);
  return kAudioFixtureSpecs[index];
}

bool LoadAudioFixture(const AudioFixtureSpec &spec, std::vector<uint8_t> &bytes,
                      std::string &error) {
  error.clear();
  bytes.clear();

  std::ifstream input(spec.disc_path, std::ios::binary | std::ios::ate);
  if (!input) {
    error = std::string("failed to open audio fixture: ") + spec.disc_path;
    return false;
  }

  const std::streamoff end = static_cast<std::streamoff>(input.tellg());
  if (end < 0 ||
      static_cast<uint64_t>(end) > std::numeric_limits<size_t>::max()) {
    error = std::string("invalid audio fixture size: ") + spec.disc_path;
    return false;
  }

  const size_t size = static_cast<size_t>(end);
  if (size != spec.byte_count) {
    error = std::string("audio fixture size mismatch: ") + spec.id;
    return false;
  }

  bytes.resize(size);
  input.seekg(0, std::ios::beg);
  if (size &&
      !input.read(reinterpret_cast<char *>(bytes.data()),
                  static_cast<std::streamsize>(size))) {
    error = std::string("failed to read audio fixture: ") + spec.disc_path;
    bytes.clear();
    return false;
  }

  if (Fnv1a64(bytes.data(), bytes.size()) != spec.fnv1a64) {
    error = std::string("audio fixture checksum mismatch: ") + spec.id;
    bytes.clear();
    return false;
  }

  return true;
}

bool ParseWavPcm16(const std::vector<uint8_t> &bytes, WavPcm16View &view,
                   std::string &error) {
  view = {};
  error.clear();

  if (bytes.size() < 12 || !FourCcEquals(bytes.data(), "RIFF") ||
      !FourCcEquals(bytes.data() + 8, "WAVE")) {
    error = "audio fixture is not RIFF/WAVE";
    return false;
  }

  bool found_format = false;
  bool found_data = false;
  uint16_t format_tag = 0;
  uint16_t channels = 0;
  uint16_t bits_per_sample = 0;
  uint32_t sample_rate = 0;
  const uint8_t *data = nullptr;
  size_t data_size = 0;

  size_t offset = 12;
  while (offset + 8 <= bytes.size()) {
    const uint8_t *chunk = bytes.data() + offset;
    const uint32_t chunk_size = ReadLe32(chunk + 4);
    const size_t payload = offset + 8;
    if (chunk_size > bytes.size() - payload) {
      error = "WAV chunk extends beyond fixture";
      return false;
    }

    if (FourCcEquals(chunk, "fmt ")) {
      if (chunk_size < 16) {
        error = "WAV fmt chunk is too short";
        return false;
      }
      format_tag = ReadLe16(bytes.data() + payload);
      channels = ReadLe16(bytes.data() + payload + 2);
      sample_rate = ReadLe32(bytes.data() + payload + 4);
      bits_per_sample = ReadLe16(bytes.data() + payload + 14);
      found_format = true;
    } else if (FourCcEquals(chunk, "data")) {
      data = bytes.data() + payload;
      data_size = chunk_size;
      found_data = true;
    }

    const size_t padded_size = static_cast<size_t>(chunk_size) + (chunk_size & 1U);
    if (padded_size > bytes.size() - payload) {
      error = "WAV padded chunk extends beyond fixture";
      return false;
    }
    offset = payload + padded_size;
  }

  if (!found_format || !found_data) {
    error = "WAV fixture is missing fmt or data";
    return false;
  }
  if (format_tag != 1 || bits_per_sample != 16 ||
      (channels != 1 && channels != 2) || sample_rate == 0) {
    error = "WAV fixture is not supported PCM16 mono/stereo";
    return false;
  }

  const uint32_t block_align = channels * sizeof(int16_t);
  if (data_size % block_align != 0) {
    error = "WAV PCM data is not frame aligned";
    return false;
  }

  view.data = data;
  view.byte_count = data_size;
  view.channels = channels;
  view.sample_rate_hz = sample_rate;
  view.frame_count = static_cast<uint32_t>(data_size / block_align);
  return true;
}

}  // namespace AudioTorture
