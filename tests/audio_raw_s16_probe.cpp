#include <array>
#include <cassert>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <map>
#include <string>
#include <vector>

#include "audio_case_descriptor.h"
#include "audio_mcpx_raw_backend.h"

namespace {
struct FakeIo : AudioTorture::ApuRegisterIo {
  const std::vector<uint8_t> &source;
  mutable std::map<uint32_t, uint32_t> registers;
  std::vector<uint32_t> writes;
  bool busy{false};
  bool stall{false};
  bool bad_output{false};
  bool fail_stop{false};
  bool fail_setup{false};
  bool tearing_while_running{false};
  bool delayed_final_counter{false};
  mutable bool running{false};
  mutable uint32_t frames{0};
  mutable unsigned stop_counter_reads_left{0};
  explicit FakeIo(const std::vector<uint8_t> &bytes) : source(bytes) {
    for (uint32_t offset = 0x2054; offset <= 0x2074; offset += 4) registers[offset] = 0xFFFF;
  }
  bool Open(std::string &error) override { error.clear(); return true; }
  uint32_t Read32(uint32_t offset) const override {
    if (offset == 0x2054 && busy) return 64;
    if (offset == 0x200C) {
      if (running && !stall) return frames += 32;
      if (stop_counter_reads_left) {
        --stop_counter_reads_left;
        return frames += 32;
      }
      return frames;
    }
    if (offset >= 0x35000 && offset < 0x35080) {
      if (tearing_while_running && running && offset == 0x35000) return 0x123456U;
      const size_t sample_index = (offset - 0x35000) / 4;
      const uint16_t bits = static_cast<uint16_t>(source[2 * sample_index]) |
                            (static_cast<uint16_t>(source[2 * sample_index + 1]) << 8);
      const int32_t sample = static_cast<int16_t>(bits);
      return bad_output ? 0x123456U
                        : static_cast<uint32_t>(sample * 256) & 0xFFFFFFU;
    }
    auto entry = registers.find(offset);
    return entry == registers.end() ? 0 : entry->second;
  }
  bool Write32(uint32_t offset, uint32_t value) override {
    writes.push_back(offset);
    if (offset == 0x202C && value != 0 && fail_setup) return false;
    if (offset == 0x2000 && value == 0 && fail_stop && running) return false;
    registers[offset] = value;
    if (offset == 0x2000) {
      if (running && value == 0 && delayed_final_counter) stop_counter_reads_left = 2;
      running = value != 0;
    }
    return true;
  }
  void Close() override {}
};

struct FakeAllocator : AudioTorture::AudioDmaAllocator {
  std::vector<void *> allocated;
  unsigned freed{0};
  void *Allocate(size_t bytes) override {
    auto *pointer = new uint8_t[bytes]{};
    allocated.push_back(pointer);
    return pointer;
  }
  uint32_t PhysicalAddress(const void *pointer) override {
    for (size_t i = 0; i < allocated.size(); ++i)
      if (allocated[i] == pointer) return 0x100000 + static_cast<uint32_t>(i * 0x10000);
    return 0;
  }
  void Free(void *pointer) override { ++freed; delete[] static_cast<uint8_t *>(pointer); }
};

bool RunScenario(const AudioTorture::AudioCaseDescriptor &descriptor,
                 const std::vector<uint8_t> &source, bool busy, bool stall,
                 bool bad_output, bool fail_stop, bool fail_setup,
                 bool tearing_while_running = false,
                 bool delayed_final_counter = false) {
  FakeIo io(source);
  FakeAllocator allocator;
  io.busy = busy;
  io.stall = stall;
  io.bad_output = bad_output;
  io.fail_stop = fail_stop;
  io.fail_setup = fail_setup;
  io.tearing_while_running = tearing_while_running;
  io.delayed_final_counter = delayed_final_counter;
  AudioTorture::McpxRawBackend backend(io, allocator, source.data(), source.size());
  AudioTorture::WorkloadResult result{};
  std::string error;
  const bool success = backend.Run(descriptor, result, error);
  assert(result.completed_sample_frames == 0);  // Not a source-derived completion claim.
  if (busy) {
    assert(!success && io.writes.empty() && allocator.allocated.empty());
  } else if (fail_stop) {
    assert(!success && !result.cleanup_passed && allocator.freed == 0);
    assert(!result.cleanup_stop_writes_passed);
  } else if (fail_setup) {
    assert(!success && result.cleanup_passed && allocator.freed == 3);
    assert(result.submitted_sample_frames == 0);
  } else {
    assert(result.cleanup_passed && allocator.freed == 3);
    assert(result.cleanup_stop_writes_passed && result.cleanup_counter_quiet &&
           result.cleanup_registers_restored && result.cleanup_dma_guard_passed);
    if (stall) assert(!success && result.observed_engine_frames == 0);
    else if (bad_output) assert(!success && !result.output_oracle_passed);
    else assert(success && result.observed_engine_frames >= 8 &&
                result.output_oracle_passed && result.observed_voice_terminal);
  }
  return success;
}
}  // namespace

int main(int argc, char **argv) {
  AudioTorture::SignalState nyquist_state{};
  assert(AudioTorture::NextS16(AudioTorture::SignalKind::kNearNyquist045,
                                nyquist_state, 0, 48000) != 0);
  assert(argc == 2);
  std::ifstream stream(argv[1], std::ios::binary);
  std::vector<uint8_t> source((std::istreambuf_iterator<char>(stream)),
                              std::istreambuf_iterator<char>());
  assert(source.size() == 512);
  const auto *descriptor = AudioTorture::FindAudioCase("audio.vp_scaling.s16_mono.v001");
  assert(descriptor);
  assert(RunScenario(*descriptor, source, false, false, false, false, false));
  assert(RunScenario(*descriptor, source, false, false, false, false, false,
                     true, true));
  assert(!RunScenario(*descriptor, source, true, false, false, false, false));
  assert(!RunScenario(*descriptor, source, false, true, false, false, false));
  assert(!RunScenario(*descriptor, source, false, false, true, false, false));
  assert(!RunScenario(*descriptor, source, false, false, false, true, false));
  assert(!RunScenario(*descriptor, source, false, false, false, false, true));
  std::cout << "raw S16 observed, rejected, and retained safely\n";
}
