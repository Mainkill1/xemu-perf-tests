#include "cpu_translation_block_tests.h"

#include <cstdint>

#include "debug_output.h"
#include "test_host.h"

static constexpr char kDirectLoopTest[] = "DirectLoop";
static constexpr char kIndirectDispatchTest[] = "IndirectDispatch";
static constexpr char kIndirectDispatchStressTest[] = "IndirectDispatchStress";
static constexpr uint32_t kProfileIterations = 10;
static constexpr uint32_t kDirectOperations = 4000000;
static constexpr uint32_t kIndirectOperations = 1000000;
static constexpr uint32_t kIndirectStressOperations = 20000000;
static constexpr uint32_t kDirectExpected = 0x8CECF231;
static constexpr uint32_t kIndirectExpected = 0xD561B779;
static constexpr uint32_t kIndirectStressExpected = 0xC4FDFFCD;

static volatile uint32_t g_cpu_result;

static uint32_t RunDirectLoop() {
  uint32_t state = 0x12345678;
  for (uint32_t i = 0; i < kDirectOperations; ++i) {
    state ^= state << 13;
    state ^= state >> 17;
    state ^= state << 5;
    state += i * 0x9E3779B9;

    // Keep the compiler from replacing or vectorizing the recurrence without
    // adding a guest instruction to the measured loop.
    asm volatile("" : "+r"(state));
  }
  return state;
}

using StepFunction = uint32_t (*)(uint32_t);

#define DEFINE_INDIRECT_STEP(ID, ROTATE, XOR_VALUE, ADD_VALUE)          \
  __attribute__((noinline)) static uint32_t IndirectStep##ID(uint32_t value) { \
    value ^= XOR_VALUE;                                                  \
    value = (value << ROTATE) | (value >> (32 - ROTATE));               \
    return value * 1664525U + ADD_VALUE;                                \
  }

DEFINE_INDIRECT_STEP(0, 1, 0x243F6A88, 0x9E3779B9)
DEFINE_INDIRECT_STEP(1, 2, 0x85A308D3, 0x7F4A7C15)
DEFINE_INDIRECT_STEP(2, 3, 0x13198A2E, 0x94D049BB)
DEFINE_INDIRECT_STEP(3, 4, 0x03707344, 0xD1B54A35)
DEFINE_INDIRECT_STEP(4, 5, 0xA4093822, 0xA24BAED5)
DEFINE_INDIRECT_STEP(5, 6, 0x299F31D0, 0x9FB21C65)
DEFINE_INDIRECT_STEP(6, 7, 0x082EFA98, 0xC13FA9A9)
DEFINE_INDIRECT_STEP(7, 8, 0xEC4E6C89, 0x91E10DA5)
DEFINE_INDIRECT_STEP(8, 9, 0x452821E6, 0xD192ED03)
DEFINE_INDIRECT_STEP(9, 10, 0x38D01377, 0xCA5A826B)
DEFINE_INDIRECT_STEP(10, 11, 0xBE5466CF, 0xB492B66F)
DEFINE_INDIRECT_STEP(11, 12, 0x34E90C6C, 0x9AE16A3B)
DEFINE_INDIRECT_STEP(12, 13, 0xC0AC29B7, 0xC949D7C7)
DEFINE_INDIRECT_STEP(13, 14, 0xC97C50DD, 0x8CB92BA7)
DEFINE_INDIRECT_STEP(14, 15, 0x3F84D5B5, 0xDB4F0B91)
DEFINE_INDIRECT_STEP(15, 16, 0xB5470917, 0xBBE05633)

#undef DEFINE_INDIRECT_STEP

static StepFunction volatile kIndirectSteps[] = {
    IndirectStep0,  IndirectStep1,  IndirectStep2,  IndirectStep3,
    IndirectStep4,  IndirectStep5,  IndirectStep6,  IndirectStep7,
    IndirectStep8,  IndirectStep9,  IndirectStep10, IndirectStep11,
    IndirectStep12, IndirectStep13, IndirectStep14, IndirectStep15,
};

static uint32_t RunIndirectDispatch(uint32_t operations) {
  uint32_t state = 0xC001D00D;
  for (uint32_t i = 0; i < operations; ++i) {
    StepFunction step = kIndirectSteps[state >> 28];
    state = step(state + i * 0x9E3779B9);
  }
  return state;
}

CpuTranslationBlockTests::CpuTranslationBlockTests(TestHost &host, std::string output_dir, const Config &config)
    : TestSuite(host, std::move(output_dir), "CpuTranslationBlocks", config) {
  tests_[kDirectLoopTest] = [this]() { TestDirectLoop(); };
  tests_[kIndirectDispatchTest] = [this]() { TestIndirectDispatch(); };
  tests_[kIndirectDispatchStressTest] = [this]() { TestIndirectDispatchStress(); };
}

void CpuTranslationBlockTests::TestDirectLoop() {
  host_.PrepareDraw(0xFF101010);
  uint32_t checksum = 0;
  auto results = Profile(kDirectLoopTest, kProfileIterations, [&checksum]() {
    checksum = RunDirectLoop();
    g_cpu_result = checksum;
  });

  ASSERT(checksum == kDirectExpected);
  PrintMsg("CPU_WORK CpuTranslationBlocks::%s operations=%lu checksum=%08lx\n", kDirectLoopTest,
           kDirectOperations, checksum);
  host_.PrepareDraw(0xFF000000 | (checksum & 0x00FFFFFF));
  host_.FinishDraw(suite_name_, kDirectLoopTest, results);
}

void CpuTranslationBlockTests::TestIndirectDispatch() {
  host_.PrepareDraw(0xFF101010);
  uint32_t checksum = 0;
  auto results = Profile(kIndirectDispatchTest, kProfileIterations, [&checksum]() {
    checksum = RunIndirectDispatch(kIndirectOperations);
    g_cpu_result = checksum;
  });

  ASSERT(checksum == kIndirectExpected);
  PrintMsg("CPU_WORK CpuTranslationBlocks::%s operations=%lu checksum=%08lx\n", kIndirectDispatchTest,
           kIndirectOperations, checksum);
  host_.PrepareDraw(0xFF000000 | (checksum & 0x00FFFFFF));
  host_.FinishDraw(suite_name_, kIndirectDispatchTest, results);
}

void CpuTranslationBlockTests::TestIndirectDispatchStress() {
  host_.PrepareDraw(0xFF101010);
  uint32_t checksum = 0;
  auto results = Profile(kIndirectDispatchStressTest, kProfileIterations, [&checksum]() {
    checksum = RunIndirectDispatch(kIndirectStressOperations);
    g_cpu_result = checksum;
  });

  ASSERT(checksum == kIndirectStressExpected);
  PrintMsg("CPU_WORK CpuTranslationBlocks::%s operations=%lu checksum=%08lx\n", kIndirectDispatchStressTest,
           kIndirectStressOperations, checksum);
  host_.PrepareDraw(0xFF000000 | (checksum & 0x00FFFFFF));
  host_.FinishDraw(suite_name_, kIndirectDispatchStressTest, results);
}
