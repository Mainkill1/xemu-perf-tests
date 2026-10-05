#ifndef XEMU_PERF_TESTS_AUDIO_VP_SCALING_SOURCE_H
#define XEMU_PERF_TESTS_AUDIO_VP_SCALING_SOURCE_H

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

#include "audio_torture_backend.h"

namespace AudioTorture {

constexpr uint32_t kS16ScalingSourceFrames = 257;
bool BuildS16ScalingSource(const WorkloadSpec &spec, std::vector<uint8_t> &source,
                           std::string &error);

inline std::array<uint8_t, 512> BuildS16ScalingControlSource() {
  std::array<uint8_t, 512> source{};
  for (std::size_t i = 1; i < source.size(); i += 2) source[i] = 0x10;
  return source;
}

}  // namespace AudioTorture

#endif  // XEMU_PERF_TESTS_AUDIO_VP_SCALING_SOURCE_H
