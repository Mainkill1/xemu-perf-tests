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
    uint32_t alpha_draws;
    uint32_t stream_bytes;
    uint32_t stream_draws;
    uint32_t surface_reuses;
    uint32_t audio_voices;
  };

 private:

  struct WorkTotals {
    uint64_t cpu_indirect_operations{0};
    uint64_t cpu_fp_operations{0};
    uint64_t cpu_memory_bytes{0};
    uint64_t decode_bytes{0};
    uint64_t pfifo_methods{0};
    uint64_t fence_reads{0};
    uint64_t draws{0};
    uint64_t primitives{0};
    uint64_t alpha_pixels{0};
    uint64_t texture_bytes{0};
    uint64_t vertex_bytes{0};
    uint64_t surface_reuses{0};
    uint64_t audio_voices{0};
  };

  struct LoaderJob {
    uint32_t seed{0};
    uint32_t bytes{0};
    uint32_t destination{0};
    uint32_t checksum{0};
  };

  static constexpr uint32_t kStreamingBufferBytes = 256 * 256 * 4;

  static unsigned long __stdcall LoaderThreadEntry(void *opaque);
  unsigned long LoaderThread();
  void StartLoader(uint32_t seed, uint32_t bytes, uint32_t destination);
  uint32_t WaitForLoader();

  void RunTest(const Preset &preset, Phase phase);
  void RunIteration(const Preset &preset, Phase phase, uint32_t iteration);
  uint32_t RunCpuWork(const Preset &preset, uint32_t seed);
  uint32_t RunPfifoWork(const Preset &preset, uint32_t seed);
  void RunGpuWork(const Preset &preset, uint32_t seed);
  void RunStreamingWork(const Preset &preset, uint32_t seed, uint32_t buffer_index);
  void StartAudio(uint32_t voices);
  void StopAudio();
  void DrawCorrectnessResult(uint32_t checksum, Phase phase);
  WorkTotals ExpectedWork(const Preset &preset, Phase phase) const;

  static const char *PhaseName(Phase phase);
  static bool HasCpu(Phase phase);
  static bool HasPfifo(Phase phase);
  static bool HasGpu(Phase phase);
  static bool HasStreaming(Phase phase);

  std::shared_ptr<PBKitPlusPlus::VertexBuffer> alpha_vertex_buffer_;
  std::array<std::vector<uint8_t>, 2> streaming_buffers_;
  std::vector<uint8_t> cpu_memory_;

  void *loader_start_event_{nullptr};
  void *loader_done_event_{nullptr};
  void *loader_thread_{nullptr};
  volatile bool loader_stop_{false};
  LoaderJob loader_job_{};

  uint32_t current_streaming_buffer_{0};
  uint32_t aggregate_checksum_{0};
  uint32_t audio_voices_{0};
};

#endif  // XEMU_PERF_TESTS_GAME_LOAD_COMPOSITE_TESTS_H
