#ifndef XEMU_PERF_TESTS_GAME_LOAD_COMPOSITE_TESTS_H
#define XEMU_PERF_TESTS_GAME_LOAD_COMPOSITE_TESTS_H

#include <array>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

#include "test_suite.h"
#include "vertex_buffer.h"

/**
 * Deterministic combined CPU/PFIFO/GPU/streaming workload.
 *
 * The individual phases retain the same operation counts used by the
 * combined phases so host-side tooling can calculate interaction penalties.
 */
class GameLoadCompositeTests : public TestSuite {
 public:
  GameLoadCompositeTests(TestHost &host, std::string output_dir, const Config &config);

  void Initialize() override;
  void Deinitialize() override;

  // Public so the immutable preset/phase tables can live in read-only storage
  // outside each suite instance.
  enum class Phase {
    CPU_ONLY,
    PFIFO_ONLY,
    GPU_ONLY,
    STREAMING_ONLY,
    CPU_PFIFO_GPU,
    CPU_PFIFO_GPU_STREAMING,
    FULL_SYSTEM,
    LONG_UNLOCKED_SCENE,
  };

  struct Preset {
    const char *name;
    uint32_t seed;
    uint32_t cpu_indirect_operations;
    uint32_t cpu_fp_cycles;
    uint32_t cpu_memory_bytes;
    uint32_t decode_bytes;
    uint32_t pfifo_bursts;
    uint32_t pfifo_methods_per_burst;
    uint32_t fence_reads;
    uint32_t gpu_waits;
    uint32_t alpha_draws;
    uint32_t stream_bytes;
    uint32_t stream_draws;
    uint32_t surface_reuses;
    uint32_t audio_voices;
  };

 private:
  static constexpr const char *kCrossTitleHotpathName = "09-CrossTitleHotpath";
  static constexpr const char *kS3tcSyncFactorName = "10-S3tcSyncFactor";

  enum class LongSceneStage : uint32_t {
    CPU = 0,
    PFIFO = 1,
    ALPHA_OVERDRAW = 2,
    STREAMING_SURFACE_REUSE = 3,
    COMBINED = 4,
    FULL_SYSTEM = 5,
  };

  struct WorkTotals {
    uint64_t cpu_indirect_operations{0};
    uint64_t cpu_fp_operations{0};
    uint64_t cpu_memory_bytes{0};
    uint64_t decode_bytes{0};
    uint64_t pfifo_methods{0};
    uint64_t fence_reads{0};
    uint64_t gpu_waits{0};
    uint64_t draws{0};
    uint64_t primitives{0};
    uint64_t alpha_pixels{0};
    uint64_t texture_bytes{0};
    uint64_t vertex_bytes{0};
    uint64_t surface_reuses{0};
    uint64_t audio_voices{0};
    uint64_t audio_buffers{0};
    uint64_t audio_bytes{0};
    uint64_t audio_mix_operations{0};
  };

  struct LoaderJob {
    uint32_t seed{0};
    uint32_t bytes{0};
    uint32_t destination{0};
    uint32_t checksum{0};
  };

  struct IterationComponentKat {
    uint32_t expected_cpu{0};
    uint32_t expected_loader{0};
    uint16_t cpu_assertion{0};
    uint16_t loader_assertion{0};
  };

  static constexpr uint32_t kStreamingBufferBytes = 256 * 256 * 4;

  static unsigned long __stdcall LoaderThreadEntry(void *opaque);
  unsigned long LoaderThread();
  void StartLoader(uint32_t seed, uint32_t bytes, uint32_t destination);
  uint32_t WaitForLoader();

  void RunTest(const Preset &preset, Phase phase);
  void RunLongUnlockedScene();
  void RunCrossTitleHotpath();
  void RunS3tcSyncFactor();
  void RunRepeatedDisplay(const char *test_name, uint32_t hold_ms, uint32_t seed);
  uint32_t ExpectedLongSceneFinalState(const Preset &preset) const;
  void RunIteration(const Preset &preset, Phase phase, uint32_t iteration,
                    uint32_t event_phase = std::numeric_limits<uint32_t>::max(),
                    const IterationComponentKat *component_kat = nullptr);
  uint32_t RunCpuWork(const Preset &preset, uint32_t seed);
  uint32_t RunPfifoWork(const Preset &preset, uint32_t seed);
  void ValidatePfifoTerminal();
  void RunGpuWork(const Preset &preset, uint32_t seed);
  void RunStreamingWork(const Preset &preset, uint32_t seed, uint32_t buffer_index);
  uint32_t RunQueuedVertexCpuWritesWork(const Preset &preset, uint32_t seed);
  uint32_t RunPipelineStateChurnWork(const Preset &preset, uint32_t seed);
  uint32_t RunBlendConstantReuseWork(const Preset &preset, uint32_t seed);
  uint32_t RunTextureBindingReuseWork(const Preset &preset, uint32_t seed);
  uint32_t RunPgr2LagspotInlineElementsWork(const Preset &preset, uint32_t seed);
  uint32_t RunScaledSurfacePressureWork(const Preset &preset, uint32_t seed);
  uint32_t RunS3tcStreamingFencedDrawsWork(const Preset &preset, uint32_t seed);
  uint32_t RunGpuWaitControlWork(const Preset &preset, uint32_t seed);
  uint32_t RunS3tcSyncFactorWork(bool compressed, bool per_draw_wait,
                                 uint32_t seed);
  uint32_t ValidateS3tcSyncFactorFramebuffer(bool compressed,
                                              uint32_t *failure_count,
                                              uint64_t *failure_mask) const;
  void StartAudio(uint32_t voices);
  void WaitForAudio();
  void StopAudio();
  uint32_t ValidateStreamingSurface(uint32_t checksum, const Preset &preset);
  void PrepareCorrectnessRenderState();
  void PrepareCrossTitleWorkState();
  void DrawCorrectnessResult(uint32_t checksum, const Preset &preset, Phase phase);
  WorkTotals ExpectedWork(const Preset &preset, Phase phase) const;
  WorkTotals ExpectedCrossTitleWork(uint32_t stage_index, const Preset &preset) const;
  uint32_t WorkChecksum(uint32_t seed, uint32_t phase_index,
                        const WorkTotals &totals, uint32_t iterations) const;
  uint32_t WorkChecksum(const Preset &preset, Phase phase,
                        const WorkTotals &totals, uint32_t iterations) const;

  static const char *PhaseName(Phase phase);
  static bool HasCpu(Phase phase);
  static bool HasPfifo(Phase phase);
  static bool HasGpu(Phase phase);
  static bool HasStreaming(Phase phase);

  std::shared_ptr<PBKitPlusPlus::VertexBuffer> alpha_vertex_buffer_;
  std::shared_ptr<PBKitPlusPlus::VertexBuffer> factor_vertex_buffer_;
  std::array<std::vector<uint8_t>, 2> streaming_buffers_;
  std::array<uint32_t, 2> streaming_buffer_checksums_{};
  std::array<std::vector<uint8_t>, 16> factor_s3tc_sources_;
  std::array<std::vector<uint8_t>, 16> factor_rgba8_sources_;
  uint8_t *factor_texture_ring_{nullptr};
  uint32_t factor_s3tc_source_checksum_{0};
  uint32_t factor_rgba8_source_checksum_{0};
  std::vector<uint8_t> cpu_memory_;

  void *loader_start_event_{nullptr};
  void *loader_done_event_{nullptr};
  void *loader_thread_{nullptr};
  volatile bool loader_stop_{false};
  LoaderJob loader_job_{};

  uint32_t current_streaming_buffer_{0};
  uint32_t last_streaming_seed_{0};
  uint32_t last_pfifo_pattern_{0};
  uint32_t last_cpu_component_{0};
  uint32_t last_loader_component_{0};
  uint32_t aggregate_checksum_{0};
  uint32_t audio_voices_{0};
  uint32_t long_scene_stage_mask_{Config::kAllGameLoadCompositeStages};
  std::array<uint32_t, Config::kGameLoadCompositeStageCount> long_scene_stage_multipliers_{};
  std::array<uint32_t, Config::kGameLoadCompositeStageCount> long_scene_stage_warmups_{};
  uint32_t long_scene_gpu_precondition_alpha_draws_{0};
  uint32_t cross_title_stage_mask_{Config::kAllGameLoadCompositeCrossTitleStages};
  bool cross_title_fast_smoke_{false};
};

#endif  // XEMU_PERF_TESTS_GAME_LOAD_COMPOSITE_TESTS_H
