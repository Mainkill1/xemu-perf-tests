#include "audio_mcpx_raw_backend.h"

#include <array>
#include <chrono>
#include <cstring>

#include "audio_s16_control_oracle.h"
#include "audio_session_guard.h"

namespace AudioTorture {
namespace {
constexpr uint32_t kVoiceIndex = 64;
constexpr uint32_t kVoiceBytes = 256 * 128;
constexpr uint32_t kPageBytes = 4096;
constexpr uint32_t kSampleBytes = 512;
constexpr uint32_t kEngine = 0x2000;
constexpr uint32_t kEngineSamples = 0x200C;
constexpr uint32_t kFrontEnd = 0x1100;
constexpr uint32_t kFrontEndGate = 0x1510;
constexpr uint32_t kVoiceTable = 0x202C;
constexpr uint32_t kSgeTable = 0x2030;
constexpr uint32_t kHeadroom = 0x20200;
constexpr uint32_t kMix = 0x35000;
constexpr uint32_t kListBase = 0x2054;
constexpr uint32_t kEmptyVoice = 0xFFFF;
constexpr uint32_t kRequiredEngineSamples = 256;

bool IsGuardIntact(const uint8_t *samples) {
  for (size_t i = kSampleBytes; i < kPageBytes; ++i) {
    if (samples[i] != 0xA5U) return false;
  }
  return true;
}

void PrepareVoice(uint8_t *voices, uint8_t *sge, uint8_t *samples,
                  const uint8_t *source, uint32_t sample_physical) {
  std::memset(voices, 0, kVoiceBytes);
  std::memset(sge, 0, kPageBytes);
  std::memset(samples, 0xA5, kPageBytes);
  std::memcpy(samples, source, kSampleBytes);
  reinterpret_cast<uint32_t *>(sge)[0] = sample_physical;

  // One 2D mono voice; these bit positions are guest-visible MCPX fields.
  auto *voice = reinterpret_cast<uint32_t *>(voices + kVoiceIndex * 128);
  voice[0x00 / 4] = (1U << 5) | (31U << 10) | (31U << 16) |
                     (31U << 21) | (31U << 26);
  voice[0x04 / 4] = 31U | (31U << 5) | (1U << 25) |
                     (1U << 28) | (1U << 30);
  voice[0x0C / 4] = 0xFF000000U;
  voice[0x14 / 4] = 0xFF000000U;
  voice[0x20 / 4] = 0;
  voice[0x54 / 4] = (1U << 21) | (5U << 24) | (5U << 28);
  voice[0x58 / 4] = 0xFF000000U;
  voice[0x5C / 4] = 0xFF000000U | 255U;
  voice[0x60 / 4] = 0x000F000FU;
  voice[0x64 / 4] = 0xFFFFFFFFU;
  voice[0x68 / 4] = 0xFFFFFFFFU;
  voice[0x7C / 4] = kEmptyVoice;
}

bool WriteListEmpty(ApuRegisterIo &io) {
  bool okay = true;
  for (uint32_t index = 0; index < 9; ++index) {
    okay = io.Write32(kListBase + index * 4, kEmptyVoice) && okay;
  }
  return okay;
}

}  // namespace

bool McpxRawBackend::Run(const AudioCaseDescriptor &descriptor,
                         WorkloadResult &result, std::string &error) {
  result = {};
  error.clear();
  if (AudioSessionPoisoned()) {
    error = "audio session blocked after unsafe prior teardown";
    return false;
  }
  if (std::strcmp(descriptor.id, "audio.vp_scaling.s16_mono.v001") != 0 ||
      descriptor.backend != BackendKind::kMcpxApuRaw ||
      descriptor.workload.format != SampleFormat::kS16 ||
      descriptor.workload.channels != 1 || descriptor.workload.voice_count != 1 ||
      !source_ || source_bytes_ != kSampleBytes) {
    error = "raw S16 control requires its exact 256-frame mono descriptor and source";
    return false;
  }

  ApuStateSnapshot before{};
  if (!OpenAndCheckApuOwnership(io_, before, error)) return false;

  auto *voices = static_cast<uint8_t *>(allocator_.Allocate(kVoiceBytes));
  auto *sge = static_cast<uint8_t *>(allocator_.Allocate(kPageBytes));
  auto *samples = static_cast<uint8_t *>(allocator_.Allocate(kPageBytes));
  if (!voices || !sge || !samples) {
    error = "contiguous audio DMA allocation failed";
    if (samples) allocator_.Free(samples);
    if (sge) allocator_.Free(sge);
    if (voices) allocator_.Free(voices);
    io_.Close();
    return false;
  }
  const uint32_t voice_physical = allocator_.PhysicalAddress(voices);
  const uint32_t sge_physical = allocator_.PhysicalAddress(sge);
  const uint32_t sample_physical = allocator_.PhysicalAddress(samples);
  if (!voice_physical || !sge_physical || !sample_physical ||
      (voice_physical & 0xFFFU) || (sge_physical & 0xFFFU) ||
      (sample_physical & 0xFFFU)) {
    error = "audio DMA allocation has no aligned physical address";
    allocator_.Free(samples);
    allocator_.Free(sge);
    allocator_.Free(voices);
    io_.Close();
    return false;
  }
  PrepareVoice(voices, sge, samples, source_, sample_physical);
  result.source_checksum = Fnv1a64(source_, source_bytes_);

  const uint32_t old_gate = io_.Read32(kFrontEndGate);
  const uint32_t old_headroom_left = io_.Read32(kHeadroom);
  const uint32_t old_headroom_right = io_.Read32(kHeadroom + 4);
  bool writes_ok = true;
  // From this first address write onward, preserve all DMA allocations until
  // stop/readback demonstrates that no voice can still reach them.
  writes_ok = io_.Write32(kVoiceTable, voice_physical) && writes_ok;
  writes_ok = io_.Write32(kSgeTable, sge_physical) && writes_ok;
  writes_ok = io_.Write32(kFrontEndGate, 1) && writes_ok;
  writes_ok = io_.Write32(kHeadroom, 0) && writes_ok;
  writes_ok = io_.Write32(kHeadroom + 4, 0) && writes_ok;
  for (uint32_t word = 0; word < 32; ++word)
    writes_ok = io_.Write32(kMix + word * 4, 0) && writes_ok;
  writes_ok = WriteListEmpty(io_) && writes_ok;
  writes_ok = io_.Write32(kFrontEnd, 0x0000100FU) && writes_ok;
  writes_ok = io_.Write32(kListBase, kVoiceIndex) && writes_ok;
  if (writes_ok) writes_ok = io_.Write32(kEngine, 0x0000000FU);
  if (writes_ok) result.submitted_sample_frames = 256;

  S16ControlObservation observed{};
  observed.source = source_;
  observed.source_bytes = source_bytes_;
  if (writes_ok) {
    const uint32_t first_sample = io_.Read32(kEngineSamples);
    const auto deadline = std::chrono::steady_clock::now() +
                          std::chrono::seconds(3);
    uint32_t progressed = 0;
    do {
      progressed = io_.Read32(kEngineSamples) - first_sample;
    } while (progressed < kRequiredEngineSamples &&
             std::chrono::steady_clock::now() < deadline);
    observed.observed_engine_frames = progressed / kVpSamplesPerFrame;
    result.observed_engine_frames = observed.observed_engine_frames;
  }

  bool stopped = io_.Write32(kEngine, 0);
  stopped = WriteListEmpty(io_) && stopped;
  result.cleanup_stop_writes_passed = stopped;
  // The disable write can leave one final frame in flight. Observe two
  // samples after a settling interval; bounded retries retain DMA on doubt.
  for (unsigned attempt = 0; attempt < 10 && !result.cleanup_counter_quiet;
       ++attempt) {
    auto deadline = std::chrono::steady_clock::now() +
                    std::chrono::milliseconds(3);
    while (std::chrono::steady_clock::now() < deadline) {}
    const uint32_t first = io_.Read32(kEngineSamples);
    deadline = std::chrono::steady_clock::now() +
               std::chrono::milliseconds(3);
    while (std::chrono::steady_clock::now() < deadline) {}
    result.cleanup_counter_quiet = ApuCounterQuiet(first, io_.Read32(kEngineSamples));
  }
  if (stopped && result.cleanup_counter_quiet &&
      result.observed_engine_frames >= 8) {
    for (uint32_t i = 0; i < observed.mix_words.size(); ++i)
      observed.mix_words[i] = io_.Read32(kMix + i * 4);
    result.observed_mix_words = observed.mix_words;
    result.output_oracle_passed = S16ControlOracle::Check(observed);
  }
  stopped = io_.Write32(kVoiceTable, before.registers.vpvaddr) && stopped;
  stopped = io_.Write32(kSgeTable, before.registers.vpsgeaddr) && stopped;
  stopped = io_.Write32(kFrontEndGate, old_gate) && stopped;
  stopped = io_.Write32(kHeadroom, old_headroom_left) && stopped;
  stopped = io_.Write32(kHeadroom + 4, old_headroom_right) && stopped;
  stopped = io_.Write32(kFrontEnd, before.registers.fectl) && stopped;
  stopped = io_.Write32(kEngine, before.registers.sectl) && stopped;
  ApuStateSnapshot after{};
  const bool readable = ReadApuState(io_, after);
  result.observed_voice_terminal = readable && after.lists.vp_lists[0] == kEmptyVoice &&
                                   after.registers.sectl == before.registers.sectl;
  result.cleanup_registers_restored = stopped && readable &&
                                      ApuStateRestored(before, after) &&
                                      io_.Read32(kFrontEndGate) == old_gate &&
                                      io_.Read32(kHeadroom) == old_headroom_left &&
                                      io_.Read32(kHeadroom + 4) == old_headroom_right &&
                                      result.observed_voice_terminal;
  result.cleanup_dma_guard_passed = IsGuardIntact(samples);
  result.cleanup_passed = result.cleanup_stop_writes_passed &&
                          result.cleanup_counter_quiet &&
                          result.cleanup_registers_restored &&
                          result.cleanup_dma_guard_passed;
  if (result.cleanup_passed) {
    allocator_.Free(samples);
    allocator_.Free(sge);
    allocator_.Free(voices);
  } else {
    PoisonAudioSession();
    error = "APU stop/readback or DMA guard failed; allocations retained";
  }
  io_.Close();

  if (!result.cleanup_passed) return false;
  if (!writes_ok) { error = "APU setup write failed"; return false; }
  if (result.observed_engine_frames < 8) {
    error = "APU did not advance eight engine frames";
    return false;
  }
  if (!result.output_oracle_passed) {
    error = "guest-readable GP MIXBUF differs from S16 fixture";
    return false;
  }
  return true;
}

}  // namespace AudioTorture
