#ifndef XEMU_PERF_TESTS_AUDIO_MCPX_RAW_BACKEND_H
#define XEMU_PERF_TESTS_AUDIO_MCPX_RAW_BACKEND_H

#include <cstddef>
#include <cstdint>
#include <string>

#include "audio_apu_ownership.h"
#include "audio_case_descriptor.h"

namespace AudioTorture {

class AudioDmaAllocator {
 public:
  virtual ~AudioDmaAllocator() = default;
  virtual void *Allocate(size_t bytes) = 0;
  virtual uint32_t PhysicalAddress(const void *pointer) = 0;
  virtual void Free(void *pointer) = 0;
};

class McpxRawBackend {
 public:
  McpxRawBackend(ApuRegisterIo &io, AudioDmaAllocator &allocator,
                 const void *source, size_t source_bytes)
      : io_(io), allocator_(allocator), source_(static_cast<const uint8_t *>(source)),
        source_bytes_(source_bytes) {}

  bool Run(const AudioCaseDescriptor &descriptor, WorkloadResult &result,
           std::string &error);

 private:
  ApuRegisterIo &io_;
  AudioDmaAllocator &allocator_;
  const uint8_t *source_;
  size_t source_bytes_;
};

}  // namespace AudioTorture

#endif  // XEMU_PERF_TESTS_AUDIO_MCPX_RAW_BACKEND_H
