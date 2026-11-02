#ifndef XEMU_PERF_TESTS_AUDIO_NXAUDIO_BACKEND_H
#define XEMU_PERF_TESTS_AUDIO_NXAUDIO_BACKEND_H

#include <cstdint>

#include "audio_torture_backend.h"

namespace AudioTorture {

// Bootstrap/reference hardware backend built on the MIT nxdk-audio project.
// This is intentionally separate from McpxApuDevice: nxdk-audio owns complete
// APU/GP/AC97 initialization and teardown, while McpxApuDevice remains the
// read-only/raw bring-up path used for future focused register-level tests.
class NxAudioBackend final : public Backend {
 public:
  NxAudioBackend() = default;
  ~NxAudioBackend() override;

  BackendCapabilities Capabilities() const override;
  bool Initialize() override;
  bool Run(const WorkloadSpec &spec, const void *source_data,
           size_t source_size, WorkloadResult &result) override;
  void Reset() override;
  void Shutdown() override;

 private:
  bool initialized_{false};
};

}  // namespace AudioTorture

#endif  // XEMU_PERF_TESTS_AUDIO_NXAUDIO_BACKEND_H
