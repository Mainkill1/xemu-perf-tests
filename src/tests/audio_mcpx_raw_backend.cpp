#include "audio_mcpx_raw_backend.h"

#include <array>
#include <atomic>
#include <chrono>
#include <cstring>

#include "audio_s16_control_oracle.h"
#include "audio_session_guard.h"
#include "audio_voice_slot_pool.h"
#include "audio_vp_scaling_recipe.h"

namespace AudioTorture {
namespace {
constexpr uint32_t kVoiceBytes = 256 * 128;
constexpr uint32_t kPageBytes = 4096;
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

bool IsGuardIntact(const uint8_t *samples, size_t used, size_t capacity) {
  for (size_t i = used; i < capacity; ++i) {
    if (samples[i] != 0xA5U) return false;
  }
  return true;
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
  const auto &spec = descriptor.workload;
  if (descriptor.family != AudioFamily::kVpScaling ||
      descriptor.backend != BackendKind::kMcpxApuRaw ||
      spec.format != SampleFormat::kS16 || spec.voice_count > 256 ||
      (spec.channels != 1 && spec.channels != 2) || spec.source_rate_hz != 48000 ||
      spec.source_layout != SourceLayout::kShared || spec.enable_3d ||
      spec.enable_hrtf || spec.enable_filter || spec.mutate_voice_state ||
      spec.voice_mode_flags || spec.control_sequence != VoiceControlSequence::kNone ||
      spec.pipeline_mode != PipelineMode::kVpOnly) {
    error = "raw scaling requires its bounded shared S16 mono/stereo descriptor";
    return false;
  }
  const bool control = !spec.voice_count || descriptor.expected_allocation_denial;
  if (descriptor.expected_allocation_denial &&
      (spec.voice_count != 256 || spec.channels != 1 ||
       descriptor.allocation_attempt_count != 257)) {
    error = "allocation denial requires exactly 257 requests for 256 slots";
    return false;
  }
  if (!control && (!source_ ||
      source_bytes_ != kS16ScalingSourceFrames * spec.channels * 2)) {
    error = "raw scaling requires its deterministic 257-frame source";
    return false;
  }

  ApuStateSnapshot before{};
  if (!OpenAndCheckApuOwnership(io_, before, error)) return false;

  VoiceSlotPool slots;
  result.requested_voice_count = descriptor.expected_allocation_denial ?
      descriptor.allocation_attempt_count : spec.voice_count;
  for (uint32_t request = 0; request < result.requested_voice_count; ++request) {
    uint16_t handle{};
    if (slots.Allocate(handle)) ++result.accepted_voice_count;
    else ++result.refused_voice_count;
  }

  if (control) {
    std::array<uint32_t, 64> old_mix{};
    for (uint32_t i = 0; i < old_mix.size(); ++i) old_mix[i] = io_.Read32(kMix + i * 4);
    const uint32_t old_gate = io_.Read32(kFrontEndGate);
    const uint32_t old_left = io_.Read32(kHeadroom);
    const uint32_t old_right = io_.Read32(kHeadroom + 4);
    ApuStateSnapshot after{};
    const bool readable = ReadApuState(io_, after);
    bool mix_unchanged = true;
    for (uint32_t i = 0; i < old_mix.size(); ++i) {
      const uint32_t value = io_.Read32(kMix + i * 4);
      mix_unchanged = mix_unchanged && value == old_mix[i];
      (i < 32 ? result.observed_mix_words : result.observed_right_mix_words)[i % 32] = value;
    }
    result.cleanup_stop_writes_passed = true;  // No work was armed.
    result.cleanup_counter_quiet = readable && ApuCounterQuiet(before.registers.xgscnt, after.registers.xgscnt);
    result.cleanup_registers_restored = readable && ApuStateRestored(before, after) &&
        io_.Read32(kFrontEndGate) == old_gate && io_.Read32(kHeadroom) == old_left &&
        io_.Read32(kHeadroom + 4) == old_right;
    result.cleanup_dma_guard_passed = true;  // No DMA was allocated.
    result.cleanup_passed = result.cleanup_counter_quiet && result.cleanup_registers_restored;
    result.output_oracle_passed = mix_unchanged;
    result.observed_voice_terminal = result.cleanup_registers_restored;
    result.resource_control_passed = descriptor.expected_allocation_denial ?
        result.accepted_voice_count == 256 && result.refused_voice_count == 1 :
        result.accepted_voice_count == 0 && result.refused_voice_count == 0;
    io_.Close();
    if (!result.cleanup_passed) PoisonAudioSession();
    if (!result.cleanup_passed || !result.output_oracle_passed || !result.resource_control_passed) {
      error = "resource control changed APU state or returned an incorrect denial";
      return false;
    }
    return true;
  }

  auto *voices = static_cast<uint8_t *>(allocator_.Allocate(kVoiceBytes + kPageBytes));
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
  std::memset(voices, 0xA5, kVoiceBytes + kPageBytes);
  std::memset(sge, 0xA5, kPageBytes);
  std::memset(samples, 0xA5, kPageBytes);
  if (!PrepareS16ScalingVoiceTable(spec, voices, kVoiceBytes,
                                  kS16ScalingSourceFrames, error)) {
    allocator_.Free(samples);
    allocator_.Free(sge);
    allocator_.Free(voices);
    io_.Close();
    return false;
  }
  std::memcpy(samples, source_, source_bytes_);
  reinterpret_cast<uint32_t *>(sge)[0] = sample_physical;
  reinterpret_cast<uint32_t *>(sge)[1] = 0;
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
  for (uint32_t word = 0; word < 64; ++word)
    writes_ok = io_.Write32(kMix + word * 4, 0) && writes_ok;
  writes_ok = WriteListEmpty(io_) && writes_ok;
  writes_ok = io_.Write32(kFrontEnd, 0x0000100FU) && writes_ok;
  writes_ok = io_.Write32(kListBase, ScalingVoiceHandle(0)) && writes_ok;
  std::atomic_thread_fence(std::memory_order_seq_cst);
  if (writes_ok) writes_ok = io_.Write32(kEngine, 0x0000000FU);
  if (writes_ok) result.submitted_sample_frames = kS16ScalingSourceFrames;

  S16ScalingObservation observed{};
  observed.source = source_;
  observed.source_bytes = source_bytes_;
  observed.channels = spec.channels;
  observed.requested_voice_count = spec.voice_count;
  if (writes_ok) {
    const uint32_t first_sample = io_.Read32(kEngineSamples);
    const auto deadline = std::chrono::steady_clock::now() +
                          std::chrono::seconds(3);
    uint32_t progressed = 0;
    std::array<bool, 256> advanced{};
    do {
      progressed = io_.Read32(kEngineSamples) - first_sample;
      for (uint32_t i = 0; i < spec.voice_count; ++i) {
        const auto *offset = reinterpret_cast<const volatile uint32_t *>(
            voices + ScalingVoiceHandle(i) * 128 + 0x58);
        const uint32_t current = *offset & 0xFFFFFFU;
        if (!advanced[i] && current > 0 && current < kS16ScalingSourceFrames) {
          advanced[i] = true;
          ++result.observed_voice_count;
        }
      }
    } while ((progressed < kRequiredEngineSamples ||
              result.observed_voice_count != spec.voice_count) &&
             std::chrono::steady_clock::now() < deadline);
    observed.observed_engine_frames = progressed / kVpSamplesPerFrame;
    result.observed_engine_frames = observed.observed_engine_frames;
    result.peak_active_voices = result.observed_voice_count;
    observed.observed_voice_count = result.observed_voice_count;
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
    for (uint32_t i = 0; i < 32; ++i) {
      observed.left_mix_words[i] = io_.Read32(kMix + i * 4);
      observed.right_mix_words[i] = io_.Read32(kMix + (32 + i) * 4);
    }
    result.observed_mix_words = observed.left_mix_words;
    result.observed_right_mix_words = observed.right_mix_words;
    result.output_oracle_passed = S16ScalingOracle::Check(observed);
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
  result.cleanup_dma_guard_passed = IsGuardIntact(samples, source_bytes_, kPageBytes) &&
      IsGuardIntact(sge, 8, kPageBytes) &&
      IsGuardIntact(voices, kVoiceBytes, kVoiceBytes + kPageBytes);
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
  if (result.observed_voice_count != spec.voice_count) {
    error = "not all submitted VP voices advanced their source offsets";
    return false;
  }
  if (!result.output_oracle_passed) {
    error = "guest-readable GP MIXBUF differs from S16 fixture";
    return false;
  }
  return true;
}

}  // namespace AudioTorture
