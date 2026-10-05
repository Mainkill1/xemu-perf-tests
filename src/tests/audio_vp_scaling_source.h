#ifndef XEMU_PERF_TESTS_AUDIO_VP_SCALING_SOURCE_H
#define XEMU_PERF_TESTS_AUDIO_VP_SCALING_SOURCE_H

#include <cstdint>
#include <string>
#include <vector>

#include "audio_torture_backend.h"

namespace AudioTorture {

constexpr uint32_t kS16ScalingSourceFrames = 257;
bool BuildS16ScalingSource(const WorkloadSpec &spec, std::vector<uint8_t> &source,
                           std::string &error);

}  // namespace AudioTorture

#endif  // XEMU_PERF_TESTS_AUDIO_VP_SCALING_SOURCE_H
