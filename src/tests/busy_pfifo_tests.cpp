#include "busy_pfifo_tests.h"

#include <pbkit/nv_objects.h>
#include <pbkit/pbkit.h>
#include <pbkit/pbkit_dma.h>
#include <pbkit/pbkit_pushbuffer.h>

#include "debug_output.h"
#include "test_host.h"

static constexpr char kTestName[] = "PFIFOSaturation";
static constexpr char kPgraphPatternPollingTestName[] = "PgraphPatternPolling";
static constexpr uint32_t kNumBloatCommandsPerDraw = 1900;
static constexpr uint32_t kNumDrawsSingleFrame = 25;
static constexpr uint32_t kNumDrawsMultiFrame = 7;
static constexpr uint32_t kPatternContextChannel = 15;
static constexpr uint32_t kPatternSubchannel = 7;
static constexpr uint32_t kPatternPollingEpochs = 256;
static constexpr uint32_t kPatternReadsPerEpoch = 100000;
static constexpr uint32_t kPatternValuePrefix = 0xA5000000;
static constexpr uint32_t kPatternResultValue = kPatternValuePrefix | 10;
static constexpr uintptr_t kPgraphPatternColor0Address = 0xFD400B10;

static s_CtxDma g_pattern_context{};

BusyPfifoTests::BusyPfifoTests(TestHost &host, std::string output_dir, const Config &config)
    : TestSuite(host, std::move(output_dir), "BusyPfifo", config) {
  tests_[kTestName] = [this]() { Test(); };
  tests_[kPgraphPatternPollingTestName] = [this]() { TestPgraphPatternPolling(); };
}

/**
 * Initializes the test suite and creates test cases.
 *
 * @tc PFIFOSaturation
 *  Saturates the PFIFO queue and renders simple draws.
 */
void BusyPfifoTests::Initialize() {
  TestSuite::Initialize();

  host_.SetFinalCombiner0Just(PBKitPlusPlus::NV2AState::SRC_DIFFUSE);
  host_.SetFinalCombiner1Just(PBKitPlusPlus::NV2AState::SRC_DIFFUSE, true);

  // Channel 15 is unused by pbkit. The image-pattern object exposes a
  // side-effect-free register that xemu currently protects with the PGRAPH
  // mutex, making it useful for measuring guest-MMIO/PFIFO contention.
  pb_create_gr_ctx(kPatternContextChannel, NV04_IMAGE_PATTERN, &g_pattern_context);
  pb_bind_channel(&g_pattern_context);
  pb_bind_subchannel(kPatternSubchannel, &g_pattern_context);
}

static void FillPFIFO() {
  PBKitPlusPlus::Pushbuffer::Begin();
  for (auto i = 0; i < kNumBloatCommandsPerDraw; ++i) {
    PBKitPlusPlus::Pushbuffer::Push(NV097_SET_TEXGEN_Q, 0);
    PBKitPlusPlus::Pushbuffer::Push(NV097_SET_TEXGEN_R, 0);
    PBKitPlusPlus::Pushbuffer::Push(NV097_SET_TEXGEN_S, 0);
    PBKitPlusPlus::Pushbuffer::Push(NV097_SET_TEXGEN_T, 0);
    PBKitPlusPlus::Pushbuffer::Push(NV097_SET_ALPHA_REF, 0);
    PBKitPlusPlus::Pushbuffer::Push(NV097_SET_COLOR_MATERIAL, 0);
  }
  PBKitPlusPlus::Pushbuffer::End();
}

static void SetPatternColor0(uint32_t value) {
  uint32_t *push = pb_begin();
  push = pb_push1_to(kPatternSubchannel, push, NV04_IMAGE_PATTERN_MONOCHROME_COLOR0, value);
  pb_end(push);
}

static void SetVertexColor(TestHost &host, uint32_t index) {
  float hue = fmodf(index * 222.5f, 360.0f);

  float c = 1.0f;
  float x = c * (1.0f - fabsf(fmodf(hue / 60.0f, 2.0f) - 1.0f));
  float r = 0, g = 0, b = 0;

  if (hue < 60) {
    r = c;
    g = x;
    b = 0;
  } else if (hue < 120) {
    r = x;
    g = c;
    b = 0;
  } else if (hue < 180) {
    r = 0;
    g = c;
    b = x;
  } else if (hue < 240) {
    r = 0;
    g = x;
    b = c;
  } else if (hue < 300) {
    r = x;
    g = 0;
    b = c;
  } else {
    r = c;
    g = 0;
    b = x;
  }

  host.SetDiffuse(r, g, b);
}

void BusyPfifoTests::Test() {
  host_.SetVertexShaderProgram(nullptr);
  host_.SetupFixedFunctionPassthrough();

  host_.PrepareDraw(0xFF222222);

  TestHost::ProfileResults results{};

  const uint32_t num_draws = host_.GetSaveResults() ? kNumDrawsSingleFrame : kNumDrawsMultiFrame;
  results = Profile(kTestName, 10, [this, num_draws] {
    static constexpr float kZ = 1.f;
    static constexpr float kW = 1.f;
    static constexpr uint32_t kNumPrimitives = 10;

    const float screen_w = host_.GetFramebufferWidthF();
    const float screen_h = host_.GetFramebufferHeightF();
    const float center_x = screen_w * 0.5f;
    const float center_y = screen_h * 0.5f;

    const float span_x = screen_w * 0.6f;
    const float span_y = screen_h * 0.6f;
    const float left = center_x - (span_x * 0.5f);
    const float top = center_y - (span_y * 0.5f);

    for (auto draw = 0; draw < num_draws; ++draw) {
      FillPFIFO();

      host_.Begin(TestHost::PRIMITIVE_TRIANGLE_STRIP);
      for (uint32_t i = 0; i < kNumPrimitives + 2; ++i) {
        float x = left + (span_x * (i / 2) / (kNumPrimitives / 2.0f));
        float y = (i % 2 == 0) ? top + span_y : top;
        SetVertexColor(host_, i);
        host_.SetVertex(x, y, kZ, kW);
      }
      host_.End();
    }
  });

  host_.FinishDraw(suite_name_, kTestName, results);
}

void BusyPfifoTests::TestPgraphPatternPolling() {
  host_.PrepareDraw(0xFF101010);

  SetPatternColor0(kPatternValuePrefix);
  host_.WaitForGpu();

  uint32_t invalid_reads = 0;
  uint32_t regressions = 0;
  uint32_t generations_observed = 0;
  uint32_t read_checksum = 2166136261U;
  uint32_t expected_final = kPatternValuePrefix;
  volatile const uint32_t *pattern_color0 =
      reinterpret_cast<volatile const uint32_t *>(kPgraphPatternColor0Address);

  auto results = Profile(kPgraphPatternPollingTestName, 1, [&]() {
    // Warmup and measurement execute the same body. Continue from the actual
    // completed generation so a warmup does not create a false ordering
    // failure in the measured pass.
    uint32_t previous = *pattern_color0;
    for (uint32_t epoch = 1; epoch <= kPatternPollingEpochs; ++epoch) {
      const uint32_t current = previous + 1;

      // Keep the PFIFO worker busy while the vCPU repeatedly enters the
      // PGRAPH MMIO read path. This models register-polling guest code without
      // requiring a retail game or relying on wall-clock frame pacing.
      FillPFIFO();
      SetPatternColor0(current);

      bool saw_current = false;
      for (uint32_t read = 0; read < kPatternReadsPerEpoch; ++read) {
        const uint32_t value = *pattern_color0;
        read_checksum = (read_checksum ^ value) * 16777619U;

        if (value == current) {
          saw_current = true;
        } else if (value != previous) {
          ++invalid_reads;
        } else if (saw_current) {
          ++regressions;
        }
      }

      if (saw_current) {
        ++generations_observed;
      }
      previous = current;
    }
    expected_final = previous;
  });

  host_.WaitForGpu();
  const uint32_t final_value = *pattern_color0;

  ASSERT(invalid_reads == 0);
  ASSERT(regressions == 0);
  ASSERT(final_value == expected_final);
  PrintMsg("CPU_WORK BusyPfifo::%s reads=%lu methods=%lu observed=%lu invalid=%lu regressions=%lu checksum=%08lx final=%08lx\n",
           kPgraphPatternPollingTestName, kPatternPollingEpochs * kPatternReadsPerEpoch,
           kPatternPollingEpochs * (kNumBloatCommandsPerDraw * 6 + 1), generations_observed, invalid_reads,
           regressions, read_checksum, final_value);

  // The exact read interleaving is intentionally scheduler-dependent. Render
  // only the deterministic terminal state; ordering errors are guarded by the
  // assertions above and the detailed checksum remains diagnostic output.
  host_.PrepareDraw(0xFF000000 | (kPatternResultValue & 0x00FFFFFF));
  host_.FinishDraw(suite_name_, kPgraphPatternPollingTestName, results);
}
