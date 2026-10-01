#include "pvideo_tests.h"

#include <pbkit/pbkit.h>
#include <windows.h>
#include <xboxkrnl/xboxkrnl.h>

#include "debug_output.h"
#include "pvideo_fixture.h"
#include "test_host.h"

namespace {
constexpr uint32_t kSourceBytes = PvideoFixture::kSourceBytes;
constexpr uint32_t kFramesPerSample = 128;
constexpr uint32_t kSamples = 8;

// Public NV2A register contract, checked against xemu nv2a_regs.h and nxdk's
// pbkit/outer.h. This fixture is xemu-only until physical-console validation.
// Register offsets are absolute within NV2A's 0xfd000000 MMIO aperture.
void Write(uint32_t offset, uint32_t value) { *reinterpret_cast<volatile uint32_t *>(0xfd000000U + offset) = value; }

void Stop() { Write(0x00008704, 1); }

void Program(const PvideoFixture::FrameState &frame, uint32_t physical) {
  Stop();
  Write(0x00008900, physical);                            // BASE
  Write(0x00008908, kSourceBytes - 1);                    // LIMIT
  Write(0x00008920, frame.offset);                        // OFFSET
  Write(0x00008928, frame.width | (frame.height << 16));  // SIZE_IN
  Write(0x00008930, 0);                                   // POINT_IN
  Write(0x00008938, 0x00100000);                          // DS_DX unity
  Write(0x00008940, 0x00100000);                          // DT_DY unity
  Write(0x00008948, 256 | (176 << 16));                   // POINT_OUT
  Write(0x00008950, frame.width | (frame.height << 16));  // SIZE_OUT
  Write(0x00008958, frame.width * 2 | (1 << 16));         // YUY2, no color key
  Write(0x00008700, frame.enabled ? 1 : 0);               // BUFFER_0_USE
}

uint64_t Hash(const uint8_t *bytes, size_t count) {
  uint64_t result = 14695981039346656037ULL;
  for (size_t i = 0; i < count; ++i) result = (result ^ bytes[i]) * 1099511628211ULL;
  return result;
}
}  // namespace

PvideoTests::PvideoTests(TestHost &host, std::string output_dir, const Config &config)
    : TestSuite(host, std::move(output_dir), "Pvideo", config) {
  tests_["SteadyUpload"] = [this]() { RunOverlay(false); };
  tests_["ResizeToggle"] = [this]() { RunOverlay(true); };
}

void PvideoTests::Initialize() {
  TestSuite::Initialize();
  source_ = static_cast<uint8_t *>(
      MmAllocateContiguousMemoryEx(kSourceBytes, 0, 0x03ffffff, 0, PAGE_READWRITE | PAGE_NOCACHE));
  ASSERT(source_);
  physical_ = static_cast<uint32_t>(MmGetPhysicalAddress(source_));
  ASSERT(physical_ <= 0x04000000U - kSourceBytes);
  Stop();
}

void PvideoTests::Deinitialize() {
  Stop();
  if (source_) MmFreeContiguousMemory(source_);
  source_ = nullptr;
  TestSuite::Deinitialize();
}

void PvideoTests::RunOverlay(bool resize) {
  // Independent known answers distinguish both sizes and pixel inversions.
  constexpr uint64_t expected[2][2] = {{0x276e4cfdecdd4325ULL, 0x9fdf411ecdd4325ULL},
                                       {0x63b16935c68ea325ULL, 0xf4e5cbb5c68ea325ULL}};
  for (uint32_t size_index = 0; size_index < 2; ++size_index) {
    uint32_t size = size_index ? 128 : 64;
    for (uint32_t inverse = 0; inverse < 2; ++inverse) {
      ASSERT(PvideoFixture::Fill(source_, PvideoFixture::kWindowBytes, size, size, inverse));
      ASSERT(Hash(source_, size * size * 2) == expected[size_index][inverse]);
    }
  }
  uint32_t frame_index = 0;
  PvideoFixture::FrameState last{};
  auto results = Profile(resize ? "ResizeToggle" : "SteadyUpload", kSamples, [&]() {
    for (uint32_t i = 0; i < kFramesPerSample; ++i, ++frame_index) {
      last = PvideoFixture::Frame(frame_index, resize);
      if ((frame_index % 64) == 0) {
        ASSERT(PvideoFixture::Fill(source_ + last.offset, PvideoFixture::kWindowBytes, last.width, last.height,
                                   last.inverted));
        asm volatile("" ::: "memory");
      }
      host_.PrepareDraw(0xFF334C99);
      Program(last, physical_);
      host_.PBKitPlusPlus::NV2AState::FinishDraw();
    }
  });
  // This source oracle cannot see host PVIDEO compositing.
  uint64_t source_hash = Hash(source_ + last.offset, last.width * last.height * 2);
  bool source_oracle_pass = source_hash == expected[last.width == 128][last.inverted];
  ASSERT(source_oracle_pass);
  char metadata[512];
  snprintf(metadata, sizeof(metadata),
           "{\"pvideo_frame_submissions\":%lu,\"source_kat\":\"%016llx\","
           "\"source_oracle_pass\":true,\"overlay_in_guest_framebuffer_hash\":false,"
           "\"host_overlay_oracle_required\":true}",
           static_cast<unsigned long>(frame_index), static_cast<unsigned long long>(source_hash));
  host_.FinishDraw(suite_name_, resize ? "ResizeToggle" : "SteadyUpload", results, metadata);
  Stop();
}
