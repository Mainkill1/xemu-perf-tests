#include <array>
#include <cassert>
#include <cstring>
#include <map>
#include <string>
#include <vector>

#include "audio_mcpx_raw_backend.h"
#include "audio_vp_scaling_recipe.h"

namespace {
struct Allocator : AudioTorture::AudioDmaAllocator {
  struct Block { uint8_t *data; size_t bytes; uint32_t address; bool freed; };
  std::vector<Block> blocks;
  unsigned frees{0};
  ~Allocator() { for (auto &b : blocks) if (!b.freed) delete[] b.data; }
  void *Allocate(size_t bytes) override {
    auto *data = new uint8_t[bytes]{};
    blocks.push_back({data, bytes, 0x100000U + static_cast<uint32_t>(blocks.size()) * 0x10000U, false});
    return data;
  }
  uint32_t PhysicalAddress(const void *pointer) override {
    for (auto &b : blocks) if (pointer == b.data) return b.address;
    return 0;
  }
  uint8_t *Resolve(uint32_t address) const {
    for (const auto &b : blocks)
      if (!b.freed && address >= b.address && address - b.address < b.bytes)
        return b.data + address - b.address;
    return nullptr;
  }
  void Free(void *pointer) override {
    for (auto &b : blocks) if (b.data == pointer && !b.freed) {
      b.freed = true; ++frees; delete[] b.data; return;
    }
    assert(false);
  }
};

struct Io : AudioTorture::ApuRegisterIo {
  Allocator &allocator;
  mutable std::map<uint32_t, uint32_t> registers;
  mutable std::array<uint32_t, 64> mix{};
  std::vector<uint32_t> writes;
  unsigned opens{0};
  mutable uint32_t samples{0};
  bool running{false};
  bool skip_last_voice{false};
  bool reverse_stereo{false};
  bool fail_stop_once{false};
  explicit Io(Allocator &a) : allocator(a) {
    for (uint32_t r = 0x2054; r <= 0x2074; r += 4) registers[r] = 0xFFFF;
    registers[0x1510] = 0x37;
    registers[0x20200] = 3;
    registers[0x20204] = 2;
    for (unsigned i = 0; i < mix.size(); ++i) mix[i] = 0x1234 + i;
  }
  uint32_t Word(uint16_t voice, uint32_t offset) const {
    auto *data = allocator.Resolve(registers[0x202C]);
    assert(data);
    uint32_t value{};
    std::memcpy(&value, data + voice * 128 + offset, 4);
    return value;
  }
  std::vector<uint16_t> Chain() const {
    std::vector<uint16_t> chain;
    uint16_t handle = static_cast<uint16_t>(registers[0x2054]);
    while (handle != 0xFFFF && chain.size() < 256) {
      chain.push_back(handle);
      handle = static_cast<uint16_t>(Word(handle, 0x7C));
    }
    assert(handle == 0xFFFF);
    return chain;
  }
  void Advance() const {
    if (!running) return;
    samples += 32;
    const auto chain = Chain();
    for (size_t i = 0; i < chain.size(); ++i) {
      if (skip_last_voice && i + 1 == chain.size()) continue;
      const auto handle = chain[i];
      auto *voice = allocator.Resolve(registers[0x202C]) + handle * 128;
      uint32_t old{};
      std::memcpy(&old, voice + 0x58, 4);
      const uint32_t next = (old & 0xFF000000U) | ((old + 32) % 257);
      std::memcpy(voice + 0x58, &next, 4);
    }
  }
  void Capture() const {
    if (!running) return;
    int32_t sums[2]{};
    const auto chain = Chain();
    // An empty list does not fetch a sample table, including during a
    // deliberately failed stop followed by register restoration.
    if (chain.empty()) { mix.fill(0); return; }
    auto *sge = allocator.Resolve(registers[0x2030]);
    assert(sge);
    uint32_t source_address{};
    std::memcpy(&source_address, sge, 4);
    const auto *source = allocator.Resolve(source_address);
    assert(source);
    for (size_t i = 0; i < chain.size(); ++i) {
      if (skip_last_voice && i + 1 == chain.size()) continue;
      const bool stereo = (Word(chain[i], 4) & (1U << 27)) != 0;
      for (unsigned channel = 0; channel < 2; ++channel) {
        const unsigned lane = stereo ? (reverse_stereo ? 1 - channel : channel) : 0;
        const uint16_t value = source[lane * 2] | (static_cast<uint16_t>(source[lane * 2 + 1]) << 8);
        sums[channel] += static_cast<int16_t>(value) * 256;
      }
    }
    for (unsigned channel = 0; channel < 2; ++channel)
      for (unsigned sample = 0; sample < 32; ++sample)
        mix[channel * 32 + sample] = static_cast<uint32_t>(sums[channel]) & 0xFFFFFF;
  }
  bool Open(std::string &error) override { ++opens; error.clear(); return true; }
  uint32_t Read32(uint32_t offset) const override {
    if (offset == 0x200C) { Advance(); return samples; }
    if (offset >= 0x35000 && offset < 0x35100) {
      Capture(); return mix[(offset - 0x35000) / 4];
    }
    return registers[offset];
  }
  bool Write32(uint32_t offset, uint32_t value) override {
    writes.push_back(offset);
    if (offset == 0x2000 && value == 0 && running) {
      if (fail_stop_once) { fail_stop_once = false; return false; }
      Capture();
    }
    if (offset >= 0x35000 && offset < 0x35100) mix[(offset - 0x35000) / 4] = value;
    registers[offset] = value;
    if (offset == 0x2000) running = value == 0xF;
    return true;
  }
  void Close() override {}
};

void Run(const AudioTorture::AudioCaseDescriptor &d, bool skip, bool reverse) {
  Allocator allocator;
  Io io(allocator);
  io.skip_last_voice = skip;
  io.reverse_stereo = reverse;
  const auto original_mix = io.mix;
  std::vector<uint8_t> source;
  std::string error;
  if (!d.expected_allocation_denial)
    assert(AudioTorture::BuildS16ScalingSource(d.workload, source, error));
  AudioTorture::McpxRawBackend backend(io, allocator, source.data(), source.size());
  AudioTorture::WorkloadResult result{};
  const bool success = backend.Run(d, result, error);
  assert(success == !(skip || reverse));
  assert(result.completed_sample_frames == 0 && result.cleanup_passed);
  if (!d.workload.voice_count || d.expected_allocation_denial) {
    assert(io.writes.empty() && allocator.blocks.empty() && io.mix == original_mix);
    assert(result.resource_control_passed && result.output_oracle_passed);
    assert(result.requested_voice_count == (d.expected_allocation_denial ? 257U : 0U));
    assert(result.accepted_voice_count == (d.expected_allocation_denial ? 256U : 0U));
    assert(result.refused_voice_count == (d.expected_allocation_denial ? 1U : 0U));
    assert(result.observed_voice_count == 0 && result.observed_engine_frames == 0);
  } else {
    assert(result.accepted_voice_count == d.workload.voice_count);
    assert(result.observed_voice_count == d.workload.voice_count - (skip ? 1 : 0));
    assert(allocator.frees == 3 && result.submitted_sample_frames == 257);
  }
}
}

int main(int argc, char **argv) {
  using namespace AudioTorture;
  if (argc == 1) {
    unsigned count = 0;
    for (size_t i = 0; i < AudioCaseCount(); ++i) {
      const auto &d = AudioCaseAt(i);
      if (d.family == AudioFamily::kVpScaling) { Run(d, false, false); ++count; }
    }
    assert(count == 45);
  } else {
    assert(argc == 2);
    const auto *d = FindAudioCase("audio.vp_scaling.s16_stereo.v256");
    assert(d);
    const std::string scenario = argv[1];
    if (scenario == "skip") Run(*d, true, false);
    else if (scenario == "reverse") Run(*d, false, true);
    else if (scenario == "poison") {
      Allocator a;
      Io io(a);
      io.fail_stop_once = true;
      std::vector<uint8_t> source;
      std::string error;
      assert(BuildS16ScalingSource(d->workload, source, error));
      McpxRawBackend first(io, a, source.data(), source.size());
      WorkloadResult result{};
      assert(!first.Run(*d, result, error) && !result.cleanup_passed && a.frees == 0);
      Allocator later_allocator;
      Io later_io(later_allocator);
      McpxRawBackend later(later_io, later_allocator, source.data(), source.size());
      assert(!later.Run(*d, result, error));
      assert(later_io.opens == 0 && later_io.writes.empty() && later_allocator.blocks.empty());
    } else assert(false);
  }
}
