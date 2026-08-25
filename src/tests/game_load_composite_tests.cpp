#include "game_load_composite_tests.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <limits>
#include <sstream>

#include <hal/audio.h>
#include <pbkit/nv_objects.h>
#include <pbkit/pbkit.h>
#include <pbkit/pbkit_dma.h>
#include <pbkit/pbkit_pushbuffer.h>
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wmacro-redefined"
#include <windows.h>
#pragma clang diagnostic pop

#include "debug_output.h"
#include "test_host.h"
#include "texture_format.h"

using namespace PBKitPlusPlus;

namespace {

static constexpr uint32_t kProfileSamples = 8;
static constexpr uint32_t kPatternContextChannel = 14;
static constexpr uint32_t kPatternSubchannel = 6;
static constexpr uintptr_t kPgraphPatternColor0Address = 0xFD400B10;
static constexpr uint32_t kPatternPrefix = 0xC4000000;
static constexpr uint32_t kTextureWidth = 256;
static constexpr uint32_t kTextureHeight = 256;
static constexpr uint32_t kAlphaQuadWidth = 96;
static constexpr uint32_t kAlphaQuadHeight = 72;
static constexpr uint32_t kVerticesPerDraw = 4;
static constexpr uint32_t kPrimitivesPerDraw = 1;
static constexpr uint32_t kVertexBytesPerUpdate = kVerticesPerDraw * 8 * sizeof(float);
static constexpr uint32_t kFpOperationsPerCycle = 8;
static constexpr uint32_t kAudioBufferBytes = 24 * 1024;
static constexpr uint32_t kAudioBuffersPerMeasurement = 16;
static constexpr uint32_t kAudioBufferCount = kAudioBuffersPerMeasurement;
static constexpr uint32_t kAudioFramesPerBuffer = kAudioBufferBytes / (2 * sizeof(int16_t));
static constexpr char kLongUnlockedSceneName[] = "08-LongUnlockedScene";
static constexpr uint32_t kLongSceneSamples = 8;
// Synthetic regression oracle, captured from the exact deterministic guest
// algorithm/build in the 2026-08-25 long-scene smoke. It is not a retail
// hardware claim. Update only with an audited guest KAT capture.
static constexpr uint32_t kLongSceneCpuKatSeed = 0x21A40C11;
static constexpr uint32_t kLongSceneCpuKatExpected = 0xF44B0F70;
static constexpr uint32_t kLongSceneCombinedCpuKatExpected = 0xFDE599A1;
static constexpr uint32_t kLongSceneFullSystemCpuKatExpected = 0x2A3A0774;
static constexpr uint32_t kLongSceneFullSystemStreamingSeed = 0xE7B9609F;
static constexpr uint32_t kLongSceneStreamingLoaderKatExpected = 0xC6FEDB8B;
static constexpr uint32_t kLongSceneCombinedLoaderKatExpected = 0x2C63685E;
static constexpr uint32_t kLongSceneFullSystemLoaderKatExpected = 0x2E10E673;
// Stable event assertion IDs for post-F1 component-oracle capture.
static constexpr auto kLongSceneCombinedComponentOracle =
    static_cast<XemuPerfAssertion>(0x112);
static constexpr auto kLongSceneFullSystemComponentOracle =
    static_cast<XemuPerfAssertion>(0x113);

static s_CtxDma g_pattern_context{};
static volatile uint32_t g_composite_result;

static std::array<std::array<uint8_t, kAudioBufferBytes>, kAudioBufferCount> g_audio_buffers{};
static volatile uint32_t g_audio_voice_count;
static volatile uint32_t g_audio_buffer_index;
static volatile uint32_t g_audio_phase;
static volatile uint32_t g_audio_submitted_buffers;

static uint32_t XorShift32(uint32_t &state) {
  state ^= state << 13;
  state ^= state >> 17;
  state ^= state << 5;
  return state;
}

using StepFunction = uint32_t (*)(uint32_t);

#define DEFINE_COMPOSITE_STEP(ID, ROTATE, XOR_VALUE, ADD_VALUE)          \
  __attribute__((noinline)) static uint32_t CompositeStep##ID(uint32_t value) { \
    value ^= XOR_VALUE;                                                   \
    value = (value << ROTATE) | (value >> (32 - ROTATE));                \
    return value * 1664525U + ADD_VALUE;                                 \
  }

DEFINE_COMPOSITE_STEP(0, 1, 0x243F6A88, 0x9E3779B9)
DEFINE_COMPOSITE_STEP(1, 3, 0x85A308D3, 0x7F4A7C15)
DEFINE_COMPOSITE_STEP(2, 5, 0x13198A2E, 0x94D049BB)
DEFINE_COMPOSITE_STEP(3, 7, 0x03707344, 0xD1B54A35)
DEFINE_COMPOSITE_STEP(4, 9, 0xA4093822, 0xA24BAED5)
DEFINE_COMPOSITE_STEP(5, 11, 0x299F31D0, 0x9FB21C65)
DEFINE_COMPOSITE_STEP(6, 13, 0x082EFA98, 0xC13FA9A9)
DEFINE_COMPOSITE_STEP(7, 15, 0xEC4E6C89, 0x91E10DA5)

#undef DEFINE_COMPOSITE_STEP

static StepFunction volatile kCompositeSteps[] = {
    CompositeStep0, CompositeStep1, CompositeStep2, CompositeStep3,
    CompositeStep4, CompositeStep5, CompositeStep6, CompositeStep7,
};

static const GameLoadCompositeTests::Preset kPresets[] = {
    {
        .name = "DoaxMenuRepresentative",
        .seed = 0xD0A40001,
        .cpu_indirect_operations = 250000,
        .cpu_fp_cycles = 32768,
        .cpu_memory_bytes = 512 * 1024,
        .decode_bytes = 128 * 1024,
        .pfifo_bursts = 8,
        .pfifo_methods_per_burst = 768,
        .fence_reads = 8192,
        .alpha_draws = 768,
        .stream_bytes = 128 * 1024,
        .stream_draws = 1,
        .surface_reuses = 4,
        .audio_voices = 8,
    },
    {
        .name = "DoaxMenuStress",
        .seed = 0xD0A40002,
        .cpu_indirect_operations = 500000,
        .cpu_fp_cycles = 65536,
        .cpu_memory_bytes = 1024 * 1024,
        .decode_bytes = 256 * 1024,
        .pfifo_bursts = 16,
        .pfifo_methods_per_burst = 768,
        .fence_reads = 16384,
        .alpha_draws = 1536,
        .stream_bytes = 256 * 1024,
        .stream_draws = 2,
        .surface_reuses = 8,
        .audio_voices = 16,
    },
    {
        .name = "Pgr2AiBackup",
        .seed = 0x50475232,
        .cpu_indirect_operations = 1000000,
        .cpu_fp_cycles = 32768,
        .cpu_memory_bytes = 512 * 1024,
        .decode_bytes = 64 * 1024,
        .pfifo_bursts = 16,
        .pfifo_methods_per_burst = 768,
        .fence_reads = 100000,
        .alpha_draws = 4000,
        .stream_bytes = 128 * 1024,
        .stream_draws = 1,
        .surface_reuses = 2,
        .audio_voices = 4,
    },
};

static const GameLoadCompositeTests::Phase kPhases[] = {
    GameLoadCompositeTests::Phase::CPU_ONLY,
    GameLoadCompositeTests::Phase::PFIFO_ONLY,
    GameLoadCompositeTests::Phase::GPU_ONLY,
    GameLoadCompositeTests::Phase::STREAMING_ONLY,
    GameLoadCompositeTests::Phase::CPU_PFIFO_GPU,
    GameLoadCompositeTests::Phase::CPU_PFIFO_GPU_STREAMING,
    GameLoadCompositeTests::Phase::FULL_SYSTEM,
};

static void SetPatternColor0(uint32_t value) {
  uint32_t *push = pb_begin();
  push = pb_push1_to(kPatternSubchannel, push, NV04_IMAGE_PATTERN_MONOCHROME_COLOR0, value);
  pb_end(push);
}

static void SubmitAudioBuffer(bool final) {
  const uint32_t buffer_index = g_audio_buffer_index++ % kAudioBufferCount;
  auto &buffer = g_audio_buffers[buffer_index];
  const uint32_t configured_voices = g_audio_voice_count;
  const uint32_t voices = std::max<uint32_t>(1, configured_voices);
  uint32_t phase = g_audio_phase;
  auto *samples = reinterpret_cast<int16_t *>(buffer.data());
  const uint32_t sample_count = buffer.size() / sizeof(int16_t);
  for (uint32_t i = 0; i < sample_count; i += 2) {
    int32_t mixed = 0;
    for (uint32_t voice = 0; voice < voices; ++voice) {
      const uint32_t period = 37 + voice * 11;
      mixed += ((phase + voice * 17) % period) < (period / 2) ? 384 : -384;
    }
    mixed = std::clamp(mixed, -12000, 12000);
    samples[i] = static_cast<int16_t>(mixed);
    samples[i + 1] = static_cast<int16_t>(mixed);
    ++phase;
  }
  g_audio_phase = phase;
  XAudioProvideSamples(buffer.data(), buffer.size(), final);
  ++g_audio_submitted_buffers;
}

}  // namespace

GameLoadCompositeTests::GameLoadCompositeTests(TestHost &host, std::string output_dir, const Config &config)
    : TestSuite(host, std::move(output_dir), "GameLoadComposite", config) {
  long_scene_stage_mask_ = config.game_load_composite_stage_mask;
  long_scene_stage_multipliers_ = config.game_load_composite_stage_multipliers;
  long_scene_stage_warmups_ = config.game_load_composite_stage_warmups;
  long_scene_gpu_precondition_alpha_draws_ =
      config.game_load_composite_gpu_precondition_alpha_draws;
  for (const auto &preset : kPresets) {
    const Preset *preset_ptr = &preset;
    for (const auto phase : kPhases) {
      std::string name = preset.name;
      name += "-";
      name += PhaseName(phase);
      tests_[name] = [this, preset_ptr, phase]() { RunTest(*preset_ptr, phase); };
    }
  }
  // This test is intentionally registered as a normal named case. Existing
  // runtime config can select it alone (or skip it) without adding a second
  // configuration mechanism.
  tests_[kLongUnlockedSceneName] = [this]() { RunLongUnlockedScene(); };
}

void GameLoadCompositeTests::Initialize() {
  TestSuite::Initialize();

  host_.SetVertexShaderProgram(nullptr);
  host_.SetupFixedFunctionPassthrough();
  host_.SetBlend(true);
  host_.SetFinalCombiner0Just(TestHost::SRC_DIFFUSE);
  host_.SetFinalCombiner1Just(TestHost::SRC_DIFFUSE, true);

  alpha_vertex_buffer_ = host_.AllocateVertexBuffer(kVerticesPerDraw);
  auto vertex = alpha_vertex_buffer_->Lock();
  const float left = (host_.GetFramebufferWidthF() - kAlphaQuadWidth) * 0.5f;
  const float top = (host_.GetFramebufferHeightF() - kAlphaQuadHeight) * 0.5f;
  const float right = left + kAlphaQuadWidth;
  const float bottom = top + kAlphaQuadHeight;
  const std::array<std::array<float, 2>, 4> positions{{
      {left, top}, {right, top}, {right, bottom}, {left, bottom},
  }};
  const std::array<std::array<float, 2>, 4> texcoords{{
      {0.f, 0.f}, {1.f, 0.f}, {1.f, 1.f}, {0.f, 1.f},
  }};
  for (uint32_t i = 0; i < kVerticesPerDraw; ++i, ++vertex) {
    vertex->SetPosition(positions[i][0], positions[i][1], 1.f);
    vertex->SetDiffuse(0.25f + i * 0.15f, 0.8f - i * 0.1f, 0.5f, 0.18f);
    vertex->SetTexCoord0(texcoords[i][0], texcoords[i][1]);
  }
  alpha_vertex_buffer_->Unlock();

  uint32_t streaming_seed = 0xC07EC7ED;
  for (auto &buffer : streaming_buffers_) {
    buffer.resize(kStreamingBufferBytes);
    for (auto &value : buffer) {
      value = static_cast<uint8_t>(XorShift32(streaming_seed));
    }
  }
  cpu_memory_.resize(1024 * 1024);
  uint32_t seed = 0x58E6C21D;
  for (auto &value : cpu_memory_) {
    value = static_cast<uint8_t>(XorShift32(seed));
  }

  auto &texture_stage = host_.GetTextureStage(0);
  texture_stage.SetFormat(GetTextureFormatInfo(NV097_SET_TEXTURE_FORMAT_COLOR_SZ_A8B8G8R8));
  texture_stage.SetTextureDimensions(kTextureWidth, kTextureHeight);
  texture_stage.SetEnabled(true);
  host_.SetupTextureStages();
  host_.SetShaderStageProgram(TestHost::STAGE_2D_PROJECTIVE);
  host_.SetVertexBuffer(alpha_vertex_buffer_);

  pb_create_gr_ctx(kPatternContextChannel, NV04_IMAGE_PATTERN, &g_pattern_context);
  pb_bind_channel(&g_pattern_context);
  pb_bind_subchannel(kPatternSubchannel, &g_pattern_context);
  SetPatternColor0(kPatternPrefix);
  host_.WaitForGpu();

  loader_start_event_ = CreateEvent(nullptr, FALSE, FALSE, nullptr);
  loader_done_event_ = CreateEvent(nullptr, FALSE, FALSE, nullptr);
  ASSERT(loader_start_event_ != nullptr);
  ASSERT(loader_done_event_ != nullptr);
  loader_thread_ = CreateThread(nullptr, 64 * 1024, LoaderThreadEntry, this, 0, nullptr);
  ASSERT(loader_thread_ != nullptr);
}

void GameLoadCompositeTests::Deinitialize() {
  StopAudio();
  loader_stop_ = true;
  SetEvent(loader_start_event_);
  ASSERT(WaitForSingleObject(loader_thread_, INFINITE) == WAIT_OBJECT_0);
  CloseHandle(loader_thread_);
  CloseHandle(loader_start_event_);
  CloseHandle(loader_done_event_);
  loader_thread_ = nullptr;
  loader_start_event_ = nullptr;
  loader_done_event_ = nullptr;

  host_.SetShaderStageProgram(TestHost::STAGE_NONE);
  host_.SetTextureStageEnabled(0, false);
  host_.ClearVertexBuffer();
  alpha_vertex_buffer_.reset();
  TestSuite::Deinitialize();
}

unsigned long __stdcall GameLoadCompositeTests::LoaderThreadEntry(void *opaque) {
  return static_cast<GameLoadCompositeTests *>(opaque)->LoaderThread();
}

unsigned long GameLoadCompositeTests::LoaderThread() {
  while (true) {
    ASSERT(WaitForSingleObject(loader_start_event_, INFINITE) == WAIT_OBJECT_0);
    if (loader_stop_) {
      break;
    }

    uint32_t state = loader_job_.seed;
    uint32_t checksum = 2166136261U;
    auto &destination = streaming_buffers_[loader_job_.destination];
    const uint32_t bytes = std::min<uint32_t>(loader_job_.bytes, destination.size());

    // Deterministic generated RLE-like decode. Runs are capped at 64-byte
    // chunks to retain branch/copy behavior without shipping any assets.
    uint32_t output = 0;
    while (output < bytes) {
      const uint32_t token = XorShift32(state);
      const uint32_t chunk = std::min<uint32_t>(1 + ((token >> 24) & 63), bytes - output);
      const uint8_t value = static_cast<uint8_t>(token ^ (token >> 8));
      memset(destination.data() + output, value, chunk);
      for (uint32_t i = 0; i < chunk; ++i) {
        checksum = (checksum ^ destination[output + i]) * 16777619U;
      }
      output += chunk;
    }
    loader_job_.checksum = checksum;
    SetEvent(loader_done_event_);
  }
  return 0;
}

void GameLoadCompositeTests::StartLoader(uint32_t seed, uint32_t bytes, uint32_t destination) {
  loader_job_.seed = seed;
  loader_job_.bytes = bytes;
  loader_job_.destination = destination;
  loader_job_.checksum = 0;
  SetEvent(loader_start_event_);
}

uint32_t GameLoadCompositeTests::WaitForLoader() {
  ASSERT(WaitForSingleObject(loader_done_event_, INFINITE) == WAIT_OBJECT_0);
  return loader_job_.checksum;
}

void GameLoadCompositeTests::RunTest(const Preset &preset, Phase phase) {
  aggregate_checksum_ = preset.seed ^ static_cast<uint32_t>(phase);
  SetXemuPerfEventContext(static_cast<uint32_t>(phase), aggregate_checksum_);
  EmitXemuPerfEvent(XemuPerfEventType::CONTEXT, 0, preset.seed, aggregate_checksum_);
  current_streaming_buffer_ = 0;
  memcpy(host_.GetTextureMemoryForStage(0), streaming_buffers_[0].data(),
         kStreamingBufferBytes);
  auto &texture_stage = host_.GetTextureStage(0);
  texture_stage.SetEnabled(true);
  host_.SetupTextureStages();
  host_.SetShaderStageProgram(TestHost::STAGE_2D_PROJECTIVE);
  host_.SetVertexBuffer(alpha_vertex_buffer_);
  host_.SetBlend(true);
  host_.PrepareDraw(0xFF101820);

  std::string test_name = preset.name;
  test_name += "-";
  test_name += PhaseName(phase);
  const uint32_t warmup_iterations =
      host_.GetSaveResults() ? host_.GetWarmupIterations() : 0;
  const uint32_t measured_iterations =
      host_.GetSaveResults() ?
          kProfileSamples * host_.GetMeasurementIterationsMultiplier() : 1;
  uint32_t invocation = 0;
  uint32_t iteration = 0;
  auto results = Profile(test_name, kProfileSamples,
                         [this, &preset, phase, warmup_iterations,
                          measured_iterations, &invocation, &iteration]() {
    const bool measured = invocation >= warmup_iterations;
    if (invocation == warmup_iterations) {
      // Warmups exercise identical paths but never influence measured seeds,
      // the measured result checksum, streaming-buffer selection, or audio.
      aggregate_checksum_ = preset.seed ^ static_cast<uint32_t>(phase);
      current_streaming_buffer_ = 0;
      iteration = 0;
      if (phase == Phase::FULL_SYSTEM) {
        StartAudio(preset.audio_voices);
      }
    }
    const uint32_t workload_iteration =
        measured ? iteration++ : 0x80000000U + invocation;
    ++invocation;
    RunIteration(preset, phase, workload_iteration);
    if (phase == Phase::FULL_SYSTEM && iteration == measured_iterations) {
      WaitForAudio();
      StopAudio();
    }
  });

  StopAudio();
  if (HasPfifo(phase)) {
    ValidatePfifoTerminal();
  }
  const WorkTotals totals = ExpectedWork(preset, phase);
  const uint64_t multiplier = results.iterations;
  const uint32_t work_checksum =
      WorkChecksum(preset, phase, totals, results.iterations);
  PrintMsg(
      "COMPOSITE_WORK GameLoadComposite::%s preset=%s phase=%s seed=%08lx "
      "iterations=%lu cpu_indirect=%llu cpu_fp=%llu cpu_memory_bytes=%llu "
      "decode_bytes=%llu pfifo_methods=%llu fence_reads=%llu draws=%llu "
      "primitives=%llu alpha_pixels=%llu texture_bytes=%llu vertex_bytes=%llu "
      "surface_reuses=%llu audio_voices=%llu audio_buffers=%llu audio_bytes=%llu "
      "audio_mix_operations=%llu work_checksum=%08lx result_checksum=%08lx\n",
      test_name.c_str(), preset.name, PhaseName(phase), preset.seed, results.iterations,
      totals.cpu_indirect_operations * multiplier, totals.cpu_fp_operations * multiplier,
      totals.cpu_memory_bytes * multiplier, totals.decode_bytes * multiplier,
      totals.pfifo_methods * multiplier, totals.fence_reads * multiplier,
      totals.draws * multiplier, totals.primitives * multiplier,
      totals.alpha_pixels * multiplier, totals.texture_bytes * multiplier,
      totals.vertex_bytes * multiplier, totals.surface_reuses * multiplier,
      totals.audio_voices, totals.audio_buffers, totals.audio_bytes,
      totals.audio_mix_operations, work_checksum, aggregate_checksum_);

  char seed_string[9] = {};
  char work_checksum_string[9] = {};
  char result_checksum_string[9] = {};
  snprintf(seed_string, sizeof(seed_string), "%08lx", preset.seed);
  snprintf(work_checksum_string, sizeof(work_checksum_string), "%08lx", work_checksum);
  snprintf(result_checksum_string, sizeof(result_checksum_string), "%08lx",
           aggregate_checksum_);
  std::ostringstream metadata;
  metadata << "{";
  metadata << "\"schema_version\":2,";
  metadata << "\"kind\":\"game_load_composite\",";
  metadata << "\"preset\":\"" << preset.name << "\",";
  metadata << "\"phase\":\"" << PhaseName(phase) << "\",";
  metadata << "\"seed\":\"" << seed_string << "\",";
  metadata << "\"iterations\":" << results.iterations << ",";
  metadata << "\"work\":{";
  metadata << "\"cpu_indirect\":" << totals.cpu_indirect_operations * multiplier << ",";
  metadata << "\"cpu_fp\":" << totals.cpu_fp_operations * multiplier << ",";
  metadata << "\"cpu_memory_bytes\":" << totals.cpu_memory_bytes * multiplier << ",";
  metadata << "\"decode_bytes\":" << totals.decode_bytes * multiplier << ",";
  metadata << "\"pfifo_methods\":" << totals.pfifo_methods * multiplier << ",";
  metadata << "\"fence_reads\":" << totals.fence_reads * multiplier << ",";
  metadata << "\"draws\":" << totals.draws * multiplier << ",";
  metadata << "\"primitives\":" << totals.primitives * multiplier << ",";
  metadata << "\"alpha_pixels\":" << totals.alpha_pixels * multiplier << ",";
  metadata << "\"texture_bytes\":" << totals.texture_bytes * multiplier << ",";
  metadata << "\"vertex_bytes\":" << totals.vertex_bytes * multiplier << ",";
  metadata << "\"surface_reuses\":" << totals.surface_reuses * multiplier << ",";
  metadata << "\"audio_voices\":" << totals.audio_voices << ",";
  metadata << "\"audio_buffers\":" << totals.audio_buffers << ",";
  metadata << "\"audio_bytes\":" << totals.audio_bytes << ",";
  metadata << "\"audio_mix_operations\":" << totals.audio_mix_operations;
  metadata << "},";
  metadata << "\"work_checksum\":\"" << work_checksum_string << "\",";
  metadata << "\"result_checksum\":\"" << result_checksum_string << "\"";
  metadata << "}";

  DrawCorrectnessResult(aggregate_checksum_, preset, phase);
  EmitXemuPerfEvent(XemuPerfEventType::PASS, 0, work_checksum, aggregate_checksum_);
  host_.FinishDraw(suite_name_, test_name, results, metadata.str());
  ClearXemuPerfEventContext();
}

void GameLoadCompositeTests::RunLongUnlockedScene() {
  // A deliberately single-XBE scene for corruption triage. Each ordered stage
  // has its own Profile window and identity, while the test remains one normal
  // selectable case in the existing runtime configuration.
  const Preset &preset = kPresets[1];
  constexpr uint32_t kCpuStage = 0x8001;
  constexpr uint32_t kPfifoStage = 0x8002;
  constexpr uint32_t kGpuStage = 0x8003;
  constexpr uint32_t kStreamingStage = 0x8004;
  constexpr uint32_t kCombinedStage = 0x8005;
  constexpr uint32_t kFullSystemStage = 0x8006;
  constexpr uint32_t kCpuSeed = kLongSceneCpuKatSeed;
  constexpr uint32_t kPfifoSeed = 0x21A40C12;
  constexpr uint32_t kGpuSeed = 0x21A40C13;
  constexpr uint32_t kStreamingSeed = 0x21A40C14;
  constexpr uint32_t kCombinedIteration = 4;
  constexpr uint32_t kFullSystemIteration = 5;
  auto stage_enabled = [this](LongSceneStage stage) {
    return long_scene_stage_mask_ & (1U << static_cast<uint32_t>(stage));
  };
  auto fold = [this](uint32_t stage, uint32_t value) {
    aggregate_checksum_ = (aggregate_checksum_ ^ value) * 16777619U;
    g_composite_result = aggregate_checksum_;
    SetXemuPerfEventContext(stage, aggregate_checksum_);
  };
  auto begin_stage = [this, &preset](uint32_t stage, const char *name,
                                     uint32_t multiplier, uint32_t warmup) {
    SetXemuPerfEventContext(stage, aggregate_checksum_);
    PrintMsg("COMPOSITE_SCENE_STAGE name=%s stage=%04lx seed=%08lx state=%08lx warmup=%lu multiplier=%lu gpu_precondition_alpha_draws=%lu\n",
             name, stage, preset.seed, aggregate_checksum_, warmup, multiplier,
             long_scene_gpu_precondition_alpha_draws_);
    // CONTEXT expected/actual are the applied stage multiplier/warmup. The
    // stage ID carries identity and final_state carries the prior aggregate.
    EmitXemuPerfEvent(XemuPerfEventType::CONTEXT, 0, multiplier, warmup);
  };
  auto profile_stage = [this, &begin_stage](LongSceneStage stage, uint32_t event_stage,
                                            const char *name,
                                            const std::function<void(void)> &body) {
    const uint32_t index = static_cast<uint32_t>(stage);
    const uint32_t original_multiplier = host_.GetMeasurementIterationsMultiplier();
    const uint32_t original_warmup = host_.GetWarmupIterations();
    const uint32_t multiplier = long_scene_stage_multipliers_[index]
                                    ? long_scene_stage_multipliers_[index]
                                    : original_multiplier;
    const uint32_t warmup = long_scene_stage_warmups_[index] == std::numeric_limits<uint32_t>::max()
                                ? original_warmup
                                : long_scene_stage_warmups_[index];
    host_.SetMeasurementIterationsMultiplier(multiplier);
    host_.SetWarmupIterations(warmup);
    begin_stage(event_stage, name, multiplier, warmup);
    auto results = Profile(name, kLongSceneSamples, body);
    host_.SetMeasurementIterationsMultiplier(original_multiplier);
    host_.SetWarmupIterations(original_warmup);
    return results;
  };

  aggregate_checksum_ = preset.seed ^ static_cast<uint32_t>(Phase::LONG_UNLOCKED_SCENE);
  current_streaming_buffer_ = 0;
  memcpy(host_.GetTextureMemoryForStage(0), streaming_buffers_[0].data(),
         kStreamingBufferBytes);
  auto &texture_stage = host_.GetTextureStage(0);
  texture_stage.SetEnabled(true);
  host_.SetupTextureStages();
  host_.SetShaderStageProgram(TestHost::STAGE_2D_PROJECTIVE);
  host_.SetVertexBuffer(alpha_vertex_buffer_);
  host_.SetBlend(true);
  host_.PrepareDraw(0xFF101820);
  TestHost::ProfileResults final_results{};
  std::array<TestHost::ProfileResults, Config::kGameLoadCompositeStageCount> stage_results{};
  std::array<bool, Config::kGameLoadCompositeStageCount> stage_ran{};
  static constexpr const char *kStageRecordNames[] = {
      "08-LongUnlockedScene-01-CPU",
      "08-LongUnlockedScene-02-PFIFO",
      "08-LongUnlockedScene-03-AlphaOverdraw",
      "08-LongUnlockedScene-04-StreamingSurfaceReuse",
      "08-LongUnlockedScene-05-Combined",
      "08-LongUnlockedScene-06-FullSystem",
  };
  uint32_t actual_cpu = 0;
  if (stage_enabled(LongSceneStage::CPU)) {
    final_results = profile_stage(LongSceneStage::CPU, kCpuStage, "08-LongUnlockedScene-01-CPU", [&]() {
      actual_cpu = RunCpuWork(preset, kCpuSeed);
      fold(kCpuStage, actual_cpu);
    });
    stage_results[static_cast<uint32_t>(LongSceneStage::CPU)] = final_results;
    stage_ran[static_cast<uint32_t>(LongSceneStage::CPU)] = true;
    AssertXemuPerfEqual(kLongSceneCpuKatExpected, actual_cpu, XemuPerfAssertion::COMPOSITE_SCENE_CPU,
                        "actual_cpu == expected_cpu", __FILE__, __LINE__);
    EmitXemuPerfHeartbeat();
  }

  if (stage_enabled(LongSceneStage::PFIFO)) {
    final_results = profile_stage(LongSceneStage::PFIFO, kPfifoStage, "08-LongUnlockedScene-02-PFIFO", [&]() {
      fold(kPfifoStage, RunPfifoWork(preset, kPfifoSeed));
    });
    stage_results[static_cast<uint32_t>(LongSceneStage::PFIFO)] = final_results;
    stage_ran[static_cast<uint32_t>(LongSceneStage::PFIFO)] = true;
    ValidatePfifoTerminal();
    EmitXemuPerfHeartbeat();
  }

  const bool has_final_gpu_stage = stage_enabled(LongSceneStage::ALPHA_OVERDRAW) ||
                                   stage_enabled(LongSceneStage::STREAMING_SURFACE_REUSE) ||
                                   stage_enabled(LongSceneStage::COMBINED) ||
                                   stage_enabled(LongSceneStage::FULL_SYSTEM);
  if (has_final_gpu_stage && long_scene_gpu_precondition_alpha_draws_) {
    static constexpr uint32_t attributes = TestHost::POSITION | TestHost::DIFFUSE | TestHost::TEXCOORD0;
    for (uint32_t draw = 0; draw < long_scene_gpu_precondition_alpha_draws_; ++draw) {
      host_.DrawArrays(attributes, TestHost::PRIMITIVE_QUADS);
    }
    host_.WaitForGpu();
    PrintMsg("COMPOSITE_SCENE_GPU_PRECONDITION alpha_draws=%lu\n",
             long_scene_gpu_precondition_alpha_draws_);
  }

  if (stage_enabled(LongSceneStage::ALPHA_OVERDRAW)) {
    final_results = profile_stage(LongSceneStage::ALPHA_OVERDRAW, kGpuStage,
                                  "08-LongUnlockedScene-03-AlphaOverdraw", [&]() {
      RunGpuWork(preset, kGpuSeed);
      fold(kGpuStage, kGpuSeed);
    });
    stage_results[static_cast<uint32_t>(LongSceneStage::ALPHA_OVERDRAW)] = final_results;
    stage_ran[static_cast<uint32_t>(LongSceneStage::ALPHA_OVERDRAW)] = true;
    EmitXemuPerfHeartbeat();
  }

  if (stage_enabled(LongSceneStage::STREAMING_SURFACE_REUSE)) {
    final_results = profile_stage(LongSceneStage::STREAMING_SURFACE_REUSE, kStreamingStage,
                                  "08-LongUnlockedScene-04-StreamingSurfaceReuse", [&]() {
      const uint32_t destination = current_streaming_buffer_ ^ 1;
      StartLoader(kStreamingSeed ^ 0xDEC0DE01, preset.decode_bytes, destination);
      const uint32_t streaming_decode = WaitForLoader();
      RunStreamingWork(preset, kStreamingSeed, destination);
      current_streaming_buffer_ = destination;
      fold(kStreamingStage, kStreamingSeed ^ streaming_decode);
    });
    stage_results[static_cast<uint32_t>(LongSceneStage::STREAMING_SURFACE_REUSE)] = final_results;
    stage_ran[static_cast<uint32_t>(LongSceneStage::STREAMING_SURFACE_REUSE)] = true;
    (void)ValidateStreamingSurface(aggregate_checksum_, preset);
    EmitXemuPerfHeartbeat();
  }

  if (stage_enabled(LongSceneStage::COMBINED)) {
    final_results = profile_stage(LongSceneStage::COMBINED, kCombinedStage,
                                  "08-LongUnlockedScene-05-Combined", [&]() {
      RunIteration(preset, Phase::CPU_PFIFO_GPU_STREAMING, kCombinedIteration, kCombinedStage);
    });
    stage_results[static_cast<uint32_t>(LongSceneStage::COMBINED)] = final_results;
    stage_ran[static_cast<uint32_t>(LongSceneStage::COMBINED)] = true;
    ValidatePfifoTerminal();
    // These synthetic literals have not yet been captured from a guest smoke.
    // Print exact post-F1 component values before promoting them to typed KATs.
    PrintMsg("COMPOSITE_KAT stage=combined cpu=%08lx loader=%08lx\n",
             last_cpu_component_, last_loader_component_);
    EmitXemuPerfEvent(XemuPerfEventType::HEARTBEAT,
                      static_cast<uint16_t>(kLongSceneCombinedComponentOracle),
                      last_cpu_component_, last_loader_component_);
    EmitXemuPerfHeartbeat();
  }

  if (stage_enabled(LongSceneStage::FULL_SYSTEM)) {
    StartAudio(preset.audio_voices);
    final_results = profile_stage(LongSceneStage::FULL_SYSTEM, kFullSystemStage,
                                  "08-LongUnlockedScene-06-FullSystem", [&]() {
      RunIteration(preset, Phase::FULL_SYSTEM, kFullSystemIteration, kFullSystemStage);
    });
    stage_results[static_cast<uint32_t>(LongSceneStage::FULL_SYSTEM)] = final_results;
    stage_ran[static_cast<uint32_t>(LongSceneStage::FULL_SYSTEM)] = true;
    WaitForAudio();
    StopAudio();
    ValidatePfifoTerminal();
    AssertXemuPerfEqual(kLongSceneFullSystemStreamingSeed, last_streaming_seed_,
                        XemuPerfAssertion::COMPOSITE_SCENE_FINAL,
                        "last_streaming_seed_ == kLongSceneFullSystemStreamingSeed",
                        __FILE__, __LINE__);
    PrintMsg("COMPOSITE_KAT stage=full_system cpu=%08lx loader=%08lx\n",
             last_cpu_component_, last_loader_component_);
    EmitXemuPerfEvent(XemuPerfEventType::HEARTBEAT,
                      static_cast<uint16_t>(kLongSceneFullSystemComponentOracle),
                      last_cpu_component_, last_loader_component_);
    EmitXemuPerfHeartbeat();
  }

  // DrawCorrectnessResult performs the final known surface-output checks and
  // renders a deterministic final checksum image for the host framebuffer hash.
  const bool has_streaming_output = stage_enabled(LongSceneStage::STREAMING_SURFACE_REUSE) ||
                                    stage_enabled(LongSceneStage::COMBINED) ||
                                    stage_enabled(LongSceneStage::FULL_SYSTEM);
  const uint32_t expected_final_state = ExpectedLongSceneFinalState(preset);
  AssertXemuPerfEqual(expected_final_state, aggregate_checksum_,
                      XemuPerfAssertion::COMPOSITE_SCENE_FINAL,
                      "aggregate_checksum_ == expected_final_state", __FILE__, __LINE__);
  DrawCorrectnessResult(aggregate_checksum_, preset,
                        has_streaming_output ? Phase::LONG_UNLOCKED_SCENE : Phase::CPU_ONLY);
  for (uint32_t stage = 0; stage < Config::kGameLoadCompositeStageCount; ++stage) {
    if (!stage_ran[stage]) {
      continue;
    }
    std::ostringstream metadata;
    metadata << "{\"schema_version\":1,\"kind\":\"game_load_composite_long_scene_stage\",";
    metadata << "\"stage_id\":" << (0x8001 + stage) << ",";
    metadata << "\"stage_mask\":" << long_scene_stage_mask_ << ",";
    metadata << "\"applied_warmup_iterations\":" << stage_results[stage].warmup_iterations << ",";
    metadata << "\"applied_measurement_iterations_multiplier\":"
             << stage_results[stage].measurement_iterations_multiplier << ",";
    metadata << "\"gpu_precondition_alpha_draws\":"
             << long_scene_gpu_precondition_alpha_draws_ << ",";
    metadata << "\"gpu_precondition_executed\":"
             << (has_final_gpu_stage && long_scene_gpu_precondition_alpha_draws_ && stage >= 2 ? "true" : "false") << ",";
    metadata << "\"expected_final_state\":" << expected_final_state << ",";
    metadata << "\"actual_final_state\":" << aggregate_checksum_ << "}";
    host_.RecordProfileResult(suite_name_, kStageRecordNames[stage], stage_results[stage], metadata.str());
  }
  EmitXemuPerfEvent(XemuPerfEventType::PASS, 0, preset.seed, aggregate_checksum_);
  // This is an overall summary, deliberately extra to the per-stage records.
  // Runner window accounting must map only kind=..._stage records to F0/F1.
  std::ostringstream summary_metadata;
  summary_metadata << "{\"schema_version\":1,\"kind\":\"game_load_composite_long_scene_summary\",";
  summary_metadata << "\"exclude_from_stage_window_mapping\":true,";
  summary_metadata << "\"stage_record_count\":";
  uint32_t stage_record_count = 0;
  for (bool ran : stage_ran) {
    stage_record_count += ran ? 1 : 0;
  }
  summary_metadata << stage_record_count << ",";
  summary_metadata << "\"expected_final_state\":" << expected_final_state << ",";
  summary_metadata << "\"actual_final_state\":" << aggregate_checksum_ << "}";
  host_.FinishDraw(suite_name_, kLongUnlockedSceneName, final_results, summary_metadata.str());
  ClearXemuPerfEventContext();
}

uint32_t GameLoadCompositeTests::ExpectedLongSceneFinalState(const Preset &preset) const {
  // Every stage body uses a fixed input. This independent accumulator makes
  // the configured exact warmup + measured invocation count part of the KAT,
  // so two equally corrupted baseline/candidate runs cannot self-validate.
  auto invocation_count = [this](LongSceneStage stage) {
    if (!host_.GetSaveResults()) {
      return 1U;
    }
    const uint32_t index = static_cast<uint32_t>(stage);
    const uint32_t multiplier = long_scene_stage_multipliers_[index]
                                    ? long_scene_stage_multipliers_[index]
                                    : host_.GetMeasurementIterationsMultiplier();
    const uint32_t warmup = long_scene_stage_warmups_[index] == std::numeric_limits<uint32_t>::max()
                                ? host_.GetWarmupIterations()
                                : long_scene_stage_warmups_[index];
    return warmup + kLongSceneSamples * multiplier;
  };
  auto enabled = [this](LongSceneStage stage) {
    return long_scene_stage_mask_ & (1U << static_cast<uint32_t>(stage));
  };
  auto fold = [](uint32_t &state, uint32_t value, uint32_t count) {
    for (uint32_t invocation = 0; invocation < count; ++invocation) {
      state = (state ^ value) * 16777619U;
    }
  };
  const uint32_t combined_seed = preset.seed + 4 * 0x9E3779B9U;
  const uint32_t full_system_seed = preset.seed + 5 * 0x9E3779B9U;
  uint32_t expected = preset.seed ^ static_cast<uint32_t>(Phase::LONG_UNLOCKED_SCENE);
  if (enabled(LongSceneStage::CPU)) {
    fold(expected, kLongSceneCpuKatExpected, invocation_count(LongSceneStage::CPU));
  }
  if (enabled(LongSceneStage::PFIFO)) {
    const uint32_t value = (kPatternPrefix | (0x21A40C12 & 0x00FFFFFF)) ^ preset.fence_reads;
    fold(expected, value, invocation_count(LongSceneStage::PFIFO));
  }
  if (enabled(LongSceneStage::ALPHA_OVERDRAW)) {
    fold(expected, 0x21A40C13, invocation_count(LongSceneStage::ALPHA_OVERDRAW));
  }
  if (enabled(LongSceneStage::STREAMING_SURFACE_REUSE)) {
    fold(expected, 0x21A40C14 ^ kLongSceneStreamingLoaderKatExpected,
         invocation_count(LongSceneStage::STREAMING_SURFACE_REUSE));
  }
  if (enabled(LongSceneStage::COMBINED)) {
    const uint32_t value = combined_seed ^ kLongSceneCombinedCpuKatExpected ^
                           ((kPatternPrefix | (combined_seed & 0x00FFFFFF)) ^ preset.fence_reads) ^
                           kLongSceneCombinedLoaderKatExpected;
    fold(expected, value, invocation_count(LongSceneStage::COMBINED));
  }
  if (enabled(LongSceneStage::FULL_SYSTEM)) {
    const uint32_t value = full_system_seed ^ kLongSceneFullSystemCpuKatExpected ^
                           ((kPatternPrefix | (full_system_seed & 0x00FFFFFF)) ^ preset.fence_reads) ^
                           kLongSceneFullSystemLoaderKatExpected;
    fold(expected, value, invocation_count(LongSceneStage::FULL_SYSTEM));
  }
  return expected;
}

void GameLoadCompositeTests::RunIteration(const Preset &preset, Phase phase, uint32_t iteration,
                                          uint32_t event_phase) {
  const uint32_t seed = preset.seed + iteration * 0x9E3779B9U;
  const uint32_t destination = current_streaming_buffer_ ^ 1;
  const bool run_loader = HasCpu(phase) || HasStreaming(phase);
  if (run_loader) {
    StartLoader(seed ^ 0xDEC0DE01, preset.decode_bytes, destination);
  }

  uint32_t checksum = seed;
  if (HasCpu(phase)) {
    last_cpu_component_ = RunCpuWork(preset, seed);
    checksum ^= last_cpu_component_;
  }
  if (HasPfifo(phase)) {
    checksum ^= RunPfifoWork(preset, seed);
  }
  if (HasGpu(phase)) {
    RunGpuWork(preset, seed);
  }

  if (run_loader) {
    last_loader_component_ = WaitForLoader();
    checksum ^= last_loader_component_;
  }
  if (HasStreaming(phase)) {
    RunStreamingWork(preset, seed, destination);
    current_streaming_buffer_ = destination;
  }

  aggregate_checksum_ = (aggregate_checksum_ ^ checksum) * 16777619U;
  g_composite_result = aggregate_checksum_;
  SetXemuPerfEventContext(event_phase == std::numeric_limits<uint32_t>::max()
                              ? static_cast<uint32_t>(phase)
                              : event_phase,
                          aggregate_checksum_);
}

uint32_t GameLoadCompositeTests::RunCpuWork(const Preset &preset, uint32_t seed) {
  uint32_t state = seed ^ 0xC001D00D;
  for (uint32_t i = 0; i < preset.cpu_indirect_operations; ++i) {
    StepFunction step = kCompositeSteps[(state >> 29) & 7];
    state = step(state + i * 0x9E3779B9U);
  }

  float fp = 0.625f;
  for (uint32_t i = 0; i < preset.cpu_fp_cycles; ++i) {
    fp = (fp * 1.0009765625f + 0.03125f) - 0.0306396484375f;
    fp = fp * 0.99951171875f + 0.00030517578125f;
    asm volatile("" : "+x"(fp));
  }

  const uint32_t memory_bytes = std::min<uint32_t>(preset.cpu_memory_bytes, cpu_memory_.size());
  uint32_t offset = seed & (cpu_memory_.size() - 1);
  uint32_t memory_checksum = 2166136261U;
  for (uint32_t i = 0; i < memory_bytes; ++i) {
    offset = (offset + ((state >> 8) | 1)) & (cpu_memory_.size() - 1);
    memory_checksum = (memory_checksum ^ cpu_memory_[offset]) * 16777619U;
    state = (state << 1) | (state >> 31);
  }

  uint32_t fp_bits;
  memcpy(&fp_bits, &fp, sizeof(fp_bits));
  return state ^ memory_checksum ^ fp_bits;
}

uint32_t GameLoadCompositeTests::RunPfifoWork(const Preset &preset, uint32_t seed) {
  ASSERT((preset.pfifo_methods_per_burst % 6) == 0);
  const uint32_t groups = preset.pfifo_methods_per_burst / 6;
  for (uint32_t burst = 0; burst < preset.pfifo_bursts; ++burst) {
    Pushbuffer::Begin();
    for (uint32_t i = 0; i < groups; ++i) {
      Pushbuffer::Push(NV097_SET_TEXGEN_Q, 0);
      Pushbuffer::Push(NV097_SET_TEXGEN_R, 0);
      Pushbuffer::Push(NV097_SET_TEXGEN_S, 0);
      Pushbuffer::Push(NV097_SET_TEXGEN_T, 0);
      Pushbuffer::Push(NV097_SET_ALPHA_REF, seed + burst + i);
      Pushbuffer::Push(NV097_SET_COLOR_MATERIAL, 0);
    }
    Pushbuffer::End();
  }

  last_pfifo_pattern_ = kPatternPrefix | (seed & 0x00FFFFFF);
  SetPatternColor0(last_pfifo_pattern_);
  volatile const uint32_t *pattern_color0 =
      reinterpret_cast<volatile const uint32_t *>(kPgraphPatternColor0Address);
  // These exact reads are the scheduled workload. Their values intentionally
  // do not influence the returned checksum: PFIFO progress is asynchronous,
  // so their interleaving is scheduler-dependent.
  volatile uint32_t scheduled_observed = 0;
  for (uint32_t i = 0; i < preset.fence_reads; ++i) {
    scheduled_observed = *pattern_color0;
  }
  (void)scheduled_observed;
  return last_pfifo_pattern_ ^ preset.fence_reads;
}

void GameLoadCompositeTests::ValidatePfifoTerminal() {
  // This mirrors BusyPfifo: correctness waits for a terminal value only after
  // the scheduled polling workload has completed, so neither the assertion
  // nor the output checksum depends on PFIFO/vCPU interleaving.
  host_.WaitForGpu();
  volatile const uint32_t *pattern_color0 =
      reinterpret_cast<volatile const uint32_t *>(kPgraphPatternColor0Address);
  const uint32_t terminal_observed = *pattern_color0;
  g_composite_result = terminal_observed;
  AssertXemuPerfEqual(last_pfifo_pattern_, terminal_observed,
                      XemuPerfAssertion::COMPOSITE_PFIFO_TERMINAL,
                      "terminal_observed == last_pfifo_pattern_", __FILE__, __LINE__);
}

void GameLoadCompositeTests::RunGpuWork(const Preset &preset, uint32_t seed) {
  host_.SetVertexBuffer(alpha_vertex_buffer_);
  host_.SetDiffuse(0.2f + (seed & 7) * 0.05f, 0.55f, 0.85f, 0.18f);
  static constexpr uint32_t attributes = TestHost::POSITION | TestHost::DIFFUSE | TestHost::TEXCOORD0;
  for (uint32_t draw = 0; draw < preset.alpha_draws; ++draw) {
    host_.DrawArrays(attributes, TestHost::PRIMITIVE_QUADS);
  }
}

void GameLoadCompositeTests::RunStreamingWork(const Preset &preset, uint32_t seed, uint32_t buffer_index) {
  last_streaming_seed_ = seed;
  const uint32_t bytes = std::min<uint32_t>(preset.stream_bytes, kStreamingBufferBytes);
  memcpy(host_.GetTextureMemoryForStage(0), streaming_buffers_[buffer_index].data(), bytes);

  static constexpr uint32_t attributes = TestHost::POSITION | TestHost::DIFFUSE | TestHost::TEXCOORD0;
  for (uint32_t stream_draw = 0; stream_draw < preset.stream_draws; ++stream_draw) {
    auto vertex = alpha_vertex_buffer_->Lock();
    const float jitter = static_cast<float>(((seed >> 8) + stream_draw) & 7) * 0.125f;
    for (uint32_t i = 0; i < kVerticesPerDraw; ++i, ++vertex) {
      const float x = 270.f + ((i == 1 || i == 2) ? kAlphaQuadWidth : 0.f) + jitter;
      const float y = 204.f + (i >= 2 ? kAlphaQuadHeight : 0.f);
      vertex->SetPosition(x, y, 1.f);
      vertex->SetDiffuse(0.3f, 0.6f, 0.9f, 0.2f);
      vertex->SetTexCoord0((i == 1 || i == 2) ? 1.f : 0.f, i >= 2 ? 1.f : 0.f);
    }
    alpha_vertex_buffer_->Unlock();
    host_.DrawArrays(attributes, TestHost::PRIMITIVE_QUADS);
  }

  uint8_t *surface = host_.GetTextureMemoryForStage(1);
  for (uint32_t reuse = 0; reuse < preset.surface_reuses; ++reuse) {
    const uint32_t width = (reuse & 1) ? 160 : 128;
    const uint32_t height = (reuse & 1) ? 120 : 128;
    host_.RenderToSurfaceStart(surface, TestHost::SCF_A8R8G8B8, width, height, false);
    host_.ClearColorRegion(0xFF000000 | ((seed + reuse * 0x10203) & 0x00FFFFFF), 0, 0, width, height);
    host_.RenderToSurfaceEnd();
  }
}

void GameLoadCompositeTests::StartAudio(uint32_t voices) {
  if (!voices) {
    return;
  }
  if (!audio_voices_) {
    XAudioInit(16, 2, nullptr, nullptr);
  }
  audio_voices_ = voices;
  g_audio_voice_count = voices;
  g_audio_phase = 0;
  g_audio_buffer_index = 0;
  g_audio_submitted_buffers = 0;
  for (uint32_t buffer = 0; buffer < kAudioBuffersPerMeasurement; ++buffer) {
    SubmitAudioBuffer(buffer + 1 == kAudioBuffersPerMeasurement);
  }
  XAudioPlay();
}

void GameLoadCompositeTests::WaitForAudio() {
  if (!audio_voices_) {
    return;
  }
  // AC97 drain status is not a portable completion primitive across xemu
  // audio backends. The exact contract is the generated and submitted batch;
  // the host audio worker overlaps for the duration of the measured phase.
  AssertXemuPerfEqual(kAudioBuffersPerMeasurement, g_audio_submitted_buffers,
                      XemuPerfAssertion::COMPOSITE_AUDIO_BATCH,
                      "g_audio_submitted_buffers == kAudioBuffersPerMeasurement",
                      __FILE__, __LINE__);
}

void GameLoadCompositeTests::StopAudio() {
  if (!audio_voices_) {
    return;
  }
  XAudioPause();
}

uint32_t GameLoadCompositeTests::ValidateStreamingSurface(uint32_t checksum,
                                                          const Preset &preset) {
  // Validate the last timed surface clear through a CPU readback before the
  // final framebuffer hash is created. This is outside the measured markers.
  host_.WaitForGpu();
  const uint32_t final_reuse = preset.surface_reuses - 1;
  const uint32_t expected =
      0xFF000000 | ((last_streaming_seed_ + (final_reuse * 0x10203)) & 0x00FFFFFF);
  auto *surface = reinterpret_cast<volatile const uint32_t *>(
      host_.GetTextureMemoryForStage(1));
  const uint32_t first = surface[0];
  const uint32_t center = surface[(120 / 2) * 160 + (160 / 2)];
  const uint32_t last = surface[(120 * 160) - 1];
  AssertXemuPerfEqual(expected, first, XemuPerfAssertion::COMPOSITE_SURFACE_FIRST,
                      "surface[0] == expected", __FILE__, __LINE__);
  AssertXemuPerfEqual(expected, center, XemuPerfAssertion::COMPOSITE_SURFACE_CENTER,
                      "surface[(120 / 2) * 160 + (160 / 2)] == expected", __FILE__, __LINE__);
  AssertXemuPerfEqual(expected, last, XemuPerfAssertion::COMPOSITE_SURFACE_LAST,
                      "surface[(120 * 160) - 1] == expected", __FILE__, __LINE__);
  return (checksum ^ expected) * 16777619U;
}

void GameLoadCompositeTests::DrawCorrectnessResult(uint32_t checksum,
                                                   const Preset &preset,
                                                   Phase phase) {
  if (HasStreaming(phase)) {
    checksum = ValidateStreamingSurface(checksum, preset);
  }

  host_.PrepareDraw(0xFF000000 | (checksum & 0x00FFFFFF));
  if (HasGpu(phase) || HasStreaming(phase)) {
    auto vertex = alpha_vertex_buffer_->Lock();
    const std::array<std::array<float, 2>, 4> positions{{
        {160.f, 120.f}, {480.f, 120.f}, {480.f, 360.f}, {160.f, 360.f},
    }};
    const std::array<std::array<float, 2>, 4> texcoords{{
        {0.f, 0.f}, {1.f, 0.f}, {1.f, 1.f}, {0.f, 1.f},
    }};
    for (uint32_t i = 0; i < kVerticesPerDraw; ++i, ++vertex) {
      vertex->SetPosition(positions[i][0], positions[i][1], 1.f);
      vertex->SetDiffuse(1.f, 1.f, 1.f, 1.f);
      vertex->SetTexCoord0(texcoords[i][0], texcoords[i][1]);
    }
    alpha_vertex_buffer_->Unlock();
    host_.SetTextureStageEnabled(0, true);
    host_.SetupTextureStages();
    host_.SetShaderStageProgram(TestHost::STAGE_2D_PROJECTIVE);
    host_.SetFinalCombiner0Just(TestHost::SRC_TEX0);
    host_.SetVertexBuffer(alpha_vertex_buffer_);
    host_.SetBlend(false);
    static constexpr uint32_t attributes =
        TestHost::POSITION | TestHost::DIFFUSE | TestHost::TEXCOORD0;
    host_.DrawArrays(attributes, TestHost::PRIMITIVE_QUADS);
  }

  host_.SetShaderStageProgram(TestHost::STAGE_NONE);
  host_.SetTextureStageEnabled(0, false);
  host_.SetFinalCombiner0Just(TestHost::SRC_DIFFUSE);
  host_.SetFinalCombiner1Just(TestHost::SRC_DIFFUSE, true);
  host_.Begin(TestHost::PRIMITIVE_QUADS);
  host_.SetDiffuse(0.1f * (static_cast<uint32_t>(phase) + 1), 0.75f, 0.35f, 1.f);
  host_.SetScreenVertex(16.f, 16.f);
  host_.SetScreenVertex(80.f, 16.f);
  host_.SetScreenVertex(80.f, 80.f);
  host_.SetScreenVertex(16.f, 80.f);
  host_.End();
}

GameLoadCompositeTests::WorkTotals GameLoadCompositeTests::ExpectedWork(const Preset &preset, Phase phase) const {
  WorkTotals totals{};
  if (HasCpu(phase)) {
    totals.cpu_indirect_operations = preset.cpu_indirect_operations;
    totals.cpu_fp_operations = static_cast<uint64_t>(preset.cpu_fp_cycles) * kFpOperationsPerCycle;
    totals.cpu_memory_bytes = preset.cpu_memory_bytes;
    totals.decode_bytes = preset.decode_bytes;
  } else if (HasStreaming(phase)) {
    totals.decode_bytes = preset.decode_bytes;
  }
  if (HasPfifo(phase)) {
    totals.pfifo_methods = static_cast<uint64_t>(preset.pfifo_bursts) * preset.pfifo_methods_per_burst + 1;
    totals.fence_reads = preset.fence_reads;
  }
  if (HasGpu(phase)) {
    totals.draws = preset.alpha_draws;
    totals.primitives = static_cast<uint64_t>(preset.alpha_draws) * kPrimitivesPerDraw;
    totals.alpha_pixels = static_cast<uint64_t>(preset.alpha_draws) * kAlphaQuadWidth * kAlphaQuadHeight;
  }
  if (HasStreaming(phase)) {
    totals.draws += preset.stream_draws;
    totals.primitives += preset.stream_draws;
    totals.alpha_pixels += static_cast<uint64_t>(preset.stream_draws) * kAlphaQuadWidth * kAlphaQuadHeight;
    totals.texture_bytes = preset.stream_bytes;
    totals.vertex_bytes = static_cast<uint64_t>(preset.stream_draws) * kVertexBytesPerUpdate;
    totals.surface_reuses = preset.surface_reuses;
  }
  if (phase == Phase::FULL_SYSTEM) {
    totals.audio_voices = preset.audio_voices;
    totals.audio_buffers = kAudioBuffersPerMeasurement;
    totals.audio_bytes =
        static_cast<uint64_t>(kAudioBuffersPerMeasurement) * kAudioBufferBytes;
    totals.audio_mix_operations =
        static_cast<uint64_t>(kAudioBuffersPerMeasurement) *
        kAudioFramesPerBuffer * preset.audio_voices;
  }
  return totals;
}

uint32_t GameLoadCompositeTests::WorkChecksum(const Preset &preset,
                                              Phase phase,
                                              const WorkTotals &totals,
                                              uint32_t iterations) const {
  uint32_t checksum = 2166136261U;
  auto add = [&checksum](uint64_t value) {
    for (uint32_t byte = 0; byte < sizeof(value); ++byte) {
      checksum = (checksum ^ static_cast<uint8_t>(value >> (byte * 8))) *
                 16777619U;
    }
  };
  add(preset.seed);
  add(static_cast<uint32_t>(phase));
  add(iterations);
  add(totals.cpu_indirect_operations * iterations);
  add(totals.cpu_fp_operations * iterations);
  add(totals.cpu_memory_bytes * iterations);
  add(totals.decode_bytes * iterations);
  add(totals.pfifo_methods * iterations);
  add(totals.fence_reads * iterations);
  add(totals.draws * iterations);
  add(totals.primitives * iterations);
  add(totals.alpha_pixels * iterations);
  add(totals.texture_bytes * iterations);
  add(totals.vertex_bytes * iterations);
  add(totals.surface_reuses * iterations);
  add(totals.audio_voices);
  add(totals.audio_buffers);
  add(totals.audio_bytes);
  add(totals.audio_mix_operations);
  return checksum;
}

const char *GameLoadCompositeTests::PhaseName(Phase phase) {
  switch (phase) {
    case Phase::CPU_ONLY: return "01-CPUOnly";
    case Phase::PFIFO_ONLY: return "02-PFIFOOnly";
    case Phase::GPU_ONLY: return "03-GPUOnly";
    case Phase::STREAMING_ONLY: return "04-StreamingOnly";
    case Phase::CPU_PFIFO_GPU: return "05-CPUPFIFOGPU";
    case Phase::CPU_PFIFO_GPU_STREAMING: return "06-CPUPFIFOGPUStreaming";
    case Phase::FULL_SYSTEM: return "07-FullSystem";
    case Phase::LONG_UNLOCKED_SCENE: return "08-LongUnlockedScene";
  }
  return "Unknown";
}

bool GameLoadCompositeTests::HasCpu(Phase phase) {
  return phase == Phase::CPU_ONLY || phase == Phase::CPU_PFIFO_GPU ||
         phase == Phase::CPU_PFIFO_GPU_STREAMING || phase == Phase::FULL_SYSTEM ||
         phase == Phase::LONG_UNLOCKED_SCENE;
}

bool GameLoadCompositeTests::HasPfifo(Phase phase) {
  return phase == Phase::PFIFO_ONLY || phase == Phase::CPU_PFIFO_GPU ||
         phase == Phase::CPU_PFIFO_GPU_STREAMING || phase == Phase::FULL_SYSTEM ||
         phase == Phase::LONG_UNLOCKED_SCENE;
}

bool GameLoadCompositeTests::HasGpu(Phase phase) {
  return phase == Phase::GPU_ONLY || phase == Phase::CPU_PFIFO_GPU ||
         phase == Phase::CPU_PFIFO_GPU_STREAMING || phase == Phase::FULL_SYSTEM ||
         phase == Phase::LONG_UNLOCKED_SCENE;
}

bool GameLoadCompositeTests::HasStreaming(Phase phase) {
  return phase == Phase::STREAMING_ONLY || phase == Phase::CPU_PFIFO_GPU_STREAMING ||
         phase == Phase::FULL_SYSTEM || phase == Phase::LONG_UNLOCKED_SCENE;
}
