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
#include "audio_s16_control_oracle.h"

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
  bool fail_gate_restore{false};
  bool ignore_headroom_restore{false};
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
    if (offset == 0x1510 && value == 0 && fail_gate_restore &&
        registers[offset] == 1) return false;
    if (offset == 0x20200 && value == 0xA0A0U && ignore_headroom_restore)
      return true;
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

void RunRestoreFailureScenario(const AudioTorture::AudioCaseDescriptor &descriptor,
                               const std::vector<uint8_t> &source,
                               bool fail_gate_write) {
  FakeIo io(source);
  FakeAllocator allocator;
  io.fail_gate_restore = fail_gate_write;
  io.ignore_headroom_restore = !fail_gate_write;
  if (!fail_gate_write) io.registers[0x20200] = 0xA0A0U;
  AudioTorture::McpxRawBackend backend(io, allocator, source.data(), source.size());
  AudioTorture::WorkloadResult result{};
  std::string error;
  assert(!backend.Run(descriptor, result, error));
  assert(!result.cleanup_passed && !result.cleanup_registers_restored);
  assert(allocator.freed == 0);
}

void RunPoisonScenario(const AudioTorture::AudioCaseDescriptor &descriptor,
                       const std::vector<uint8_t> &source) {
  FakeIo first_io(source);
  FakeAllocator first_allocator;
  first_io.fail_stop = true;
  AudioTorture::McpxRawBackend first(first_io, first_allocator,
                                     source.data(), source.size());
  AudioTorture::WorkloadResult first_result{};
  std::string error;
  assert(!first.Run(descriptor, first_result, error));
  assert(!first_result.cleanup_passed && first_allocator.freed == 0);

  FakeIo second_io(source);
  FakeAllocator second_allocator;
  AudioTorture::McpxRawBackend second(second_io, second_allocator,
                                      source.data(), source.size());
  AudioTorture::WorkloadResult second_result{};
  assert(!second.Run(descriptor, second_result, error));
  assert(!second_result.cleanup_passed);
  assert(second_io.writes.empty() && second_allocator.allocated.empty());
}
}  // namespace

int main(int argc, char **argv) {
  AudioTorture::SignalState nyquist_state{};
  assert(AudioTorture::NextS16(AudioTorture::SignalKind::kNearNyquist045,
                                nyquist_state, 0, 48000) != 0);
  assert(argc == 2 || argc == 3);
  std::ifstream stream(argv[1], std::ios::binary);
  std::vector<uint8_t> source((std::istreambuf_iterator<char>(stream)),
                              std::istreambuf_iterator<char>());
  assert(source.size() == 512);
  AudioTorture::S16ControlObservation native_observation{};
  native_observation.source = source.data();
  native_observation.source_bytes = source.size();
  native_observation.observed_engine_frames = 12;
  // Exact guest GP mix words from upstream Deck run
  // 20261005-070955222-06780d14af5d4fb0a8ffe319a30a320a.
  native_observation.mix_words = {
      4450138, 3919055, 3403305, 2876183, 2355583, 1832528, 1308855, 787511,
      263715, 16518871, 15995360, 15473686, 14950404, 14427164, 13906480,
      13379573, 12863328, 12332902, 11816751, 11290944, 10766486, 10730253,
      11241008, 11778384, 12286281, 12821226, 13335655, 13862868, 14384254,
      14906087, 15430748, 15951736};
  assert(AudioTorture::S16ControlOracle::Check(native_observation));
  native_observation.mix_words[10] = 0x123456;
  assert(!AudioTorture::S16ControlOracle::Check(native_observation));
  const auto *descriptor = AudioTorture::FindAudioCase("audio.vp_scaling.s16_mono.v001");
  assert(descriptor);
  assert(RunScenario(*descriptor, source, false, false, false, false, false));
  assert(RunScenario(*descriptor, source, false, false, false, false, false,
                     true, true));
  assert(!RunScenario(*descriptor, source, true, false, false, false, false));
  assert(!RunScenario(*descriptor, source, false, true, false, false, false));
  assert(!RunScenario(*descriptor, source, false, false, true, false, false));
  assert(!RunScenario(*descriptor, source, false, false, false, false, true));
  if (argc == 2)
    assert(!RunScenario(*descriptor, source, false, false, false, true, false));
  if (argc == 3) {
    const std::string scenario = argv[2];
    if (scenario == "gate-restore") RunRestoreFailureScenario(*descriptor, source, true);
    else if (scenario == "headroom-readback")
      RunRestoreFailureScenario(*descriptor, source, false);
    else if (scenario == "poison") RunPoisonScenario(*descriptor, source);
    else assert(false);
  }
  std::cout << "raw S16 observed, rejected, and retained safely\n";
}
