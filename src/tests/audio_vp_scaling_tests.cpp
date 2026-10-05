#include "audio_vp_scaling_tests.h"

#include <utility>

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wignored-attributes"
#include <xboxkrnl/xboxkrnl.h>
#pragma clang diagnostic pop

#include "audio_case_descriptor.h"
#include "audio_mcpx_apu_device.h"
#include "audio_mcpx_raw_backend.h"
#include "audio_vp_scaling_result.h"
#include "audio_vp_scaling_route.h"
#include "audio_vp_scaling_source.h"

namespace {

class XboxAudioDmaAllocator final : public AudioTorture::AudioDmaAllocator {
 public:
  void *Allocate(size_t bytes) override {
    return MmAllocateContiguousMemoryEx(bytes, 0, MAXRAM, 0,
                                        PAGE_NOCACHE | PAGE_READWRITE);
  }
  uint32_t PhysicalAddress(const void *pointer) override {
    return static_cast<uint32_t>(
        MmGetPhysicalAddress(const_cast<void *>(pointer)));
  }
  void Free(void *pointer) override { MmFreeContiguousMemory(pointer); }
};

}  // namespace

AudioVpScalingTests::AudioVpScalingTests(TestHost &host, std::string output_dir,
                                         const Config &config)
    : TestSuite(host, std::move(output_dir), "AudioVpScaling", config) {
  for (size_t i = 0; i < AudioTorture::AudioCaseCount(); ++i) {
    const auto &descriptor = AudioTorture::AudioCaseAt(i);
    if (descriptor.family != AudioTorture::AudioFamily::kVpScaling ||
        !descriptor.executable) continue;
    const auto name = AudioTorture::ScalingLegacyName(descriptor);
    tests_[name] = [this, descriptor, name]() { RunCase(descriptor, name); };
  }
}

void AudioVpScalingTests::RunCase(const AudioTorture::AudioCaseDescriptor &descriptor,
                                 const std::string &legacy_name) {
  host_.PrepareDraw(0xff101010);
  AudioTorture::WorkloadResult result{};
  std::string error;
  bool ran = false;
  if (!descriptor.executable) {
    error = "scaling guest descriptor is not executable";
  } else {
    std::vector<uint8_t> source;
    if (descriptor.expected_allocation_denial ||
        AudioTorture::BuildS16ScalingSource(descriptor.workload, source, error)) {
      AudioTorture::McpxApuDevice device;
      XboxAudioDmaAllocator allocator;
      AudioTorture::McpxRawBackend backend(device, allocator, source.data(),
                                          source.size());
      ran = backend.Run(descriptor, result, error);
    }
  }

  TestHost::ProfileResults profile{};
  host_.FinishDraw(suite_name_, legacy_name, profile,
                   AudioTorture::BuildScalingLeafMetadata(descriptor, ran, result, error));
}
