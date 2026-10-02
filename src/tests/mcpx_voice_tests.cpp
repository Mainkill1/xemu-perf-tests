// SPDX-License-Identifier: Unlicense
#include "mcpx_voice_tests.h"

#include <pbkit/pbkit_dma.h>

#include <array>
#include <chrono>
#include <cstring>
#include <sstream>

#include "debug_output.h"
#include "mcpx_voice_recipe.h"

namespace {
constexpr uintptr_t kApuBase = 0xfe800000;
constexpr uint32_t kEngine = 0x2000;
constexpr uint32_t kFrontEnd = 0x1100;
constexpr uint32_t kVoiceTable = 0x202c;
constexpr uint32_t kSgeTable = 0x2030;
constexpr uint32_t kGpReset = 0x3fffc;
constexpr uint32_t kEpReset = 0x5fffc;
constexpr uint32_t kMix = 0x35000;
constexpr uint32_t kVoice = 64;
constexpr uint32_t kLoopSamples = 4096;
constexpr uint32_t kProgressSamples = 1024;
constexpr uint32_t kTimeoutUs = 3000000;
constexpr size_t kSampleBytes = 5 * 4096;
constexpr std::array<uint32_t, 3> kListTops = {0x2054, 0x2060, 0x206c};

uint32_t Read(uint32_t offset) { return *reinterpret_cast<volatile uint32_t *>(kApuBase + offset); }
void Write(uint32_t offset, uint32_t value) { *reinterpret_cast<volatile uint32_t *>(kApuBase + offset) = value; }
uint8_t *Allocate(size_t bytes) {
  return static_cast<uint8_t *>(MmAllocateContiguousMemoryEx(bytes, 0, MAXRAM, 0, PAGE_NOCACHE | PAGE_READWRITE));
}
uint32_t Physical(const void *pointer) {
  return static_cast<uint32_t>(MmGetPhysicalAddress(const_cast<void *>(pointer)));
}
uint32_t Hash(const std::vector<uint8_t> &input) {
  uint32_t hash = 2166136261;
  for (auto byte : input) hash = (hash ^ byte) * 16777619;
  return hash;
}
void Check(uint32_t expected, uint32_t actual, XemuPerfAssertion id) {
  AssertXemuPerfEqual(expected, actual, id, "MCPX voice observation", __FILE__, __LINE__);
}

// This fixture owns only a reset/unconfigured engine. It does not take over
// an application voice table, even if that application temporarily stopped it.
struct VoiceMemory {
  uint8_t *voices = nullptr;
  uint8_t *sge = nullptr;
  uint8_t *samples = nullptr;
  uint32_t old_engine = 0;
  uint32_t old_front_end = 0;
  bool armed = false;
  bool safe_to_free = true;

  bool Available() const {
    if ((Read(kEngine) & 0x18) || Read(kVoiceTable) || Read(kSgeTable) || Read(kGpReset) || Read(kEpReset))
      return false;
    for (auto top : kListTops) {
      if (Read(top) != 0 && Read(top) != 0xffff) return false;
    }
    return true;
  }
  bool Initialize() {
    old_engine = Read(kEngine);
    old_front_end = Read(kFrontEnd);
    voices = Allocate(256 * 128);
    sge = Allocate(4096);
    samples = Allocate(kSampleBytes);
    return voices && sge && samples;
  }
  bool Stop() {
    if (!armed) return true;
    Write(kEngine, 0);
    // Unlink BEFORE obtaining the frame mutex through a GP write. A frame
    // already in throttle can still run once after the engine is disabled.
    // Keeping all lists empty also makes that later frame DMA-safe.
    for (auto top : kListTops) {
      Write(top, 0xffff);
      Write(top + 4, 0xffff);
      Write(top + 8, 0xffff);
    }
    Write(kGpReset, 0);
    Write(kVoiceTable, 0);
    Write(kSgeTable, 0);
    Write(kFrontEnd, old_front_end);
    Write(kEngine, old_engine);
    armed = false;
    bool stopped = !(Read(kEngine) & 0x18) && !Read(kVoiceTable) && !Read(kSgeTable);
    for (auto top : kListTops) stopped = stopped && Read(top) == 0xffff;
    safe_to_free = stopped;
    return stopped;
  }
  ~VoiceMemory() {
    Stop();
    // An unverified stop retains the small allocation until process/reset;
    // a failure must never release memory that could still be a DMA target.
    if (!safe_to_free) return;
    if (samples) MmFreeContiguousMemory(samples);
    if (sge) MmFreeContiguousMemory(sge);
    if (voices) MmFreeContiguousMemory(voices);
  }
};
}  // namespace

McpxVoiceTests::McpxVoiceTests(TestHost &host, std::string output_dir, const Config &config)
    : TestSuite(host, std::move(output_dir), "McpxVoice", config) {
  tests_["MonoAligned"] = [this]() { TestVoice("MonoAligned", false, false, false); };
  tests_["StereoAligned"] = [this]() { TestVoice("StereoAligned", true, false, false); };
  tests_["MonoPageCrossing"] = [this]() { TestVoice("MonoPageCrossing", false, true, false); };
  tests_["StereoPageCrossing"] = [this]() { TestVoice("StereoPageCrossing", true, true, false); };
  tests_["PcmControl"] = [this]() { TestVoice("PcmControl", false, false, true); };
}

void McpxVoiceTests::TestVoice(const char *name, bool stereo, bool page_crossing, bool pcm) {
  host_.PrepareDraw(0xff101010);
  VoiceMemory memory;
  bool available = memory.Available();
  Check(1, available, XemuPerfAssertion::MCPX_INACTIVE);
  if (!available) return;
  bool allocated = memory.Initialize();
  Check(1, allocated, XemuPerfAssertion::MCPX_INPUT);
  if (!allocated) return;

  std::vector<uint8_t> payload;
  if (pcm) {
    payload.resize(kLoopSamples * 2);
    for (size_t i = 0; i < payload.size(); i += 2) payload[i + 1] = 0x10;
  } else {
    auto block = McpxVoiceRecipe::EncodedBlock(stereo);
    for (unsigned i = 0; i < 64; ++i) payload.insert(payload.end(), block.begin(), block.end());
  }
  uint32_t input_hash = Hash(payload);
  Check(pcm ? 0x81e31dc5 : (stereo ? 0x12c01dc5 : 0x9862a5c5), input_hash, XemuPerfAssertion::MCPX_INPUT);
  std::memset(memory.voices, 0, 256 * 128);
  std::memset(memory.sge, 0, 4096);
  std::memset(memory.samples, 0xa5, kSampleBytes);
  uint32_t base = page_crossing ? 4080 : 0;
  bool copied = McpxVoiceRecipe::CopyLogicalBytes(memory.samples, kSampleBytes, base, payload.data(), payload.size());
  Check(1, copied, XemuPerfAssertion::MCPX_INPUT);
  if (!copied) return;
  auto *entries = reinterpret_cast<uint32_t *>(memory.sge);
  for (uint32_t page = 0; page < 3; ++page) entries[page * 2] = Physical(memory.samples + page * 8192);

  auto *voice = reinterpret_cast<uint32_t *>(memory.voices + kVoice * 128);
  voice[0x00 / 4] = (1 << 5) | (31 << 10) | (31 << 16) | (31 << 21) | (31U << 26);
  voice[0x04 / 4] =
      31 | (31 << 5) | (1 << 25) | (1 << 28) | (pcm ? (1U << 30) : (2U << 30)) | (stereo ? ((1 << 27) | (1 << 16)) : 0);
  voice[0x0c / 4] = 0xff000000;
  voice[0x14 / 4] = 0xff000000;
  voice[0x20 / 4] = base;
  voice[0x54 / 4] = (1 << 21) | (5 << 24) | (5U << 28);
  voice[0x58 / 4] = 0xff000000;
  voice[0x5c / 4] = 0xff000000 | (kLoopSamples - 1);
  voice[0x60 / 4] = 0x000f000f;
  voice[0x64 / 4] = 0xffffffff;
  voice[0x68 / 4] = 0xffffffff;
  voice[0x7c / 4] = 0xffff;

  memory.armed = true;
  memory.safe_to_free = false;
  for (auto top : kListTops) Write(top, 0xffff);
  Write(kVoiceTable, Physical(memory.voices));
  Write(kSgeTable, Physical(memory.sge));
  Write(kFrontEnd, memory.old_front_end & ~0xe0U);
  Write(kListTops[0], kVoice);
  // Experimental xemu mode, not an independently verified hardware enum.
  asm volatile("" : : : "memory");
  Write(kEngine, (memory.old_engine & ~0x18U) | 0x8);

  uint32_t observed_progress = 0;
  auto results = Profile(name, 1, [&]() {
    auto start = std::chrono::steady_clock::now();
    uint32_t previous = reinterpret_cast<volatile uint32_t *>(voice)[0x58 / 4] & 0xfff;
    observed_progress = 0;
    while (observed_progress < kProgressSamples) {
      uint32_t current = reinterpret_cast<volatile uint32_t *>(voice)[0x58 / 4] & 0xfff;
      observed_progress += (current - previous) & 0xfff;
      previous = current;
      auto elapsed =
          std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now() - start).count();
      if (elapsed >= kTimeoutUs) break;
      Sleep(0);
    }
  });
  Check(1, observed_progress >= kProgressSamples, XemuPerfAssertion::MCPX_PROGRESS);
  std::ostringstream observations;
  observations << "[";
  for (unsigned bin = 0; bin < 2; ++bin) {
    int16_t predictor = bin == 1 && stereo ? -4096 : 4096;
    for (unsigned sample = 0; sample < 32; ++sample) {
      uint32_t actual = Read(kMix + (bin * 32 + sample) * 4);
      bool matches = McpxVoiceRecipe::MixValueMatches(actual, predictor);
      Check(1, matches, XemuPerfAssertion::MCPX_OUTPUT);
      if (bin || sample) observations << ",";
      observations << actual;
    }
  }
  observations << "]";
  bool stopped = memory.Stop();
  Check(1, stopped, XemuPerfAssertion::MCPX_CLEANUP);
  bool guard = true;
  for (unsigned page : {1U, 3U}) {
    for (unsigned i = 0; i < 4096; ++i) guard = guard && memory.samples[page * 4096 + i] == 0xa5;
  }
  Check(1, guard, XemuPerfAssertion::MCPX_GUARD);
  std::ostringstream metadata;
  metadata << "{\"oracle\":\"constant-IMA-predictor-regression\",\"source_fnv32\":" << input_hash
           << ",\"observed_sample_progress\":" << observed_progress << ",\"mix_words\":" << observations.str()
           << ",\"cleanup_passed\":" << (stopped ? "true" : "false")
           << ",\"mix_tolerance_24bit_units\":32,\"full_dsp_required\":true,"
           << "\"timing_comparable\":false,\"timing_reason\":\"timer-paced progress polling\"}";
  host_.PrepareDraw(XemuPerfTestFailed() ? 0xff800000 : 0xff208060);
  host_.FinishDraw(suite_name_, name, results, metadata.str());
}
