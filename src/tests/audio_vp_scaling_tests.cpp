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
  tests_["S16MonoV001"] = [this]() { S16MonoV001(); };
}

void AudioVpScalingTests::S16MonoV001() {
  host_.PrepareDraw(0xff101010);
  AudioTorture::WorkloadResult result{};
  std::string error;
  bool ran = false;
  const auto *descriptor = AudioTorture::FindAudioCase("audio.vp_scaling.s16_mono.v001");
  if (!descriptor || !descriptor->executable) {
    error = "S16 mono guest descriptor is not executable";
  } else {
    std::vector<uint8_t> source;
    if (AudioTorture::BuildS16ScalingSource(descriptor->workload, source, error)) {
      AudioTorture::McpxApuDevice device;
      XboxAudioDmaAllocator allocator;
      AudioTorture::McpxRawBackend backend(device, allocator, source.data(),
                                          source.size());
      ran = backend.Run(*descriptor, result, error);
    }
  }

  TestHost::ProfileResults profile{};
  host_.FinishDraw(suite_name_, "S16MonoV001", profile,
                   AudioTorture::BuildS16LeafMetadata(ran, result, error));
}
