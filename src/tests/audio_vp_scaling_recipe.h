#ifndef XEMU_PERF_TESTS_AUDIO_VP_SCALING_RECIPE_H
#define XEMU_PERF_TESTS_AUDIO_VP_SCALING_RECIPE_H

#include "audio_vp_scaling_source.h"

namespace AudioTorture {

uint16_t ScalingVoiceHandle(uint32_t ordinal);
bool PrepareS16ScalingVoiceTable(const WorkloadSpec &spec, uint8_t *voice_memory,
                                 size_t voice_bytes, uint32_t source_frames,
                                 std::string &error);

}  // namespace AudioTorture

#endif  // XEMU_PERF_TESTS_AUDIO_VP_SCALING_RECIPE_H
