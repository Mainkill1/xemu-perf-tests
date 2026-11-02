#ifndef XEMU_PERF_TESTS_AUDIO_NXAUDIO_BRIDGE_H
#define XEMU_PERF_TESTS_AUDIO_NXAUDIO_BRIDGE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum AudioNxBridgeFormat {
  AUDIO_NX_BRIDGE_U8 = 0,
  AUDIO_NX_BRIDGE_S16,
  AUDIO_NX_BRIDGE_S24_B32,
  AUDIO_NX_BRIDGE_S32,
  AUDIO_NX_BRIDGE_ADPCM,
} AudioNxBridgeFormat;

typedef struct AudioNxBridgeRequest {
  AudioNxBridgeFormat format;
  uint32_t channels;
  uint32_t sample_rate_hz;
  uint32_t voice_count;
  uint32_t audio_frames;
  bool enable_3d;
  bool loop;
} AudioNxBridgeRequest;

typedef struct AudioNxBridgeResult {
  uint32_t created_voices;
  uint32_t started_voices;
  uint32_t completion_timeouts;
  uint32_t backend_error;
  uint64_t completed_frames_per_voice;
} AudioNxBridgeResult;

bool AudioNxBridgeInitialize(void);
void AudioNxBridgeShutdown(void);
bool AudioNxBridgeRun(const AudioNxBridgeRequest *request,
                      const void *source_data,
                      uint32_t source_size,
                      AudioNxBridgeResult *result);

#ifdef __cplusplus
}
#endif

#endif  // XEMU_PERF_TESTS_AUDIO_NXAUDIO_BRIDGE_H
