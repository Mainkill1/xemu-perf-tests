#ifndef XEMU_PERF_TESTS_AUDIO_VP_SCALING_ROUTE_H
#define XEMU_PERF_TESTS_AUDIO_VP_SCALING_ROUTE_H

#include <iomanip>
#include <sstream>
#include "audio_case_descriptor.h"

namespace AudioTorture {
inline std::string ScalingLegacyName(const AudioCaseDescriptor &d) {
  if (d.family != AudioFamily::kVpScaling) return {};
  if (d.expected_allocation_denial) return "S16MonoAllocationV257";
  std::ostringstream name;
  name << "S16" << (d.workload.channels == 1 ? "Mono" : "Stereo")
       << 'V' << std::setfill('0') << std::setw(3) << d.workload.voice_count;
  return name.str();
}
}  // namespace AudioTorture
#endif
