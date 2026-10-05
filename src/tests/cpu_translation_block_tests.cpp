#include "cpu_translation_block_tests.h"

#include <windows.h>

#include <cstdint>
#include <cstdio>

#include "cpu_code_rewrite_workload.h"
#include "cpu_jump_cache_workload.h"
#include "debug_output.h"
#include "test_host.h"

static constexpr char kDirectLoopTest[] = "DirectLoop";
static constexpr char kIndirectDispatchTest[] = "IndirectDispatch";
static constexpr char kIndirectDispatchStressTest[] = "IndirectDispatchStress";
static constexpr char kCodeStableTest[] = "CodeStable";
static constexpr char kCodeRewriteTest[] = "CodeRewrite";
static constexpr uint32_t kProfileIterations = 10;
static constexpr uint32_t kDirectOperations = 4000000;
static constexpr uint32_t kIndirectOperations = 1000000;
static constexpr uint32_t kIndirectStressOperations = 20000000;
static constexpr uint32_t kDirectExpected = 0x8CECF231;
static constexpr uint32_t kIndirectExpected = 0xD561B779;
static constexpr uint32_t kIndirectStressExpected = 0xC4FDFFCD;
static constexpr uint32_t kCodeStableOperations = 50000000;
static constexpr uint32_t kCodeRewriteOperations = 1000000;
static constexpr uint32_t kCodeStableExpected = 0xF5FF3985;
static constexpr uint32_t kCodeRewriteExpected = 0x65151D67;

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

#define DEFINE_INDIRECT_STEP(ID, ROTATE, XOR_VALUE, ADD_VALUE)                 \
  __attribute__((noinline)) static uint32_t IndirectStep##ID(uint32_t value) { \
    value ^= XOR_VALUE;                                                        \
    value = (value << ROTATE) | (value >> (32 - ROTATE));                      \
    return value * 1664525U + ADD_VALUE;                                       \
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
    IndirectStep0,  IndirectStep1,  IndirectStep2,  IndirectStep3,  IndirectStep4,  IndirectStep5,
    IndirectStep6,  IndirectStep7,  IndirectStep8,  IndirectStep9,  IndirectStep10, IndirectStep11,
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

CpuTranslationBlockTests::CpuTranslationBlockTests(TestHost& host, std::string output_dir, const Config& config)
    : TestSuite(host, std::move(output_dir), "CpuTranslationBlocks", config) {
  tests_[kDirectLoopTest] = [this]() { TestDirectLoop(); };
  tests_[kIndirectDispatchTest] = [this]() { TestIndirectDispatch(); };
  tests_[kIndirectDispatchStressTest] = [this]() { TestIndirectDispatchStress(); };
  tests_[kCodeStableTest] = [this]() {
    TestGeneratedCode(kCodeStableTest, false, kCodeStableOperations, kCodeStableExpected);
  };
  tests_[kCodeRewriteTest] = [this]() {
    TestGeneratedCode(kCodeRewriteTest, true, kCodeRewriteOperations, kCodeRewriteExpected);
  };
  tests_["JumpCacheCollision2"] = [this]() { TestJumpCache("JumpCacheCollision2", 2, true, 0x4F71ED44); };
  tests_["JumpCacheCollision8"] = [this]() { TestJumpCache("JumpCacheCollision8", 8, true, 0x52F08FDA); };
  tests_["JumpCacheCollision10"] = [this]() { TestJumpCache("JumpCacheCollision10", 10, true, 0x9D8149E6); };
  tests_["JumpCacheNoncollision8"] = [this]() { TestJumpCache("JumpCacheNoncollision8", 8, false, 0x52F08FDA); };
}

void CpuTranslationBlockTests::TestDirectLoop() {
  host_.PrepareDraw(0xFF101010);
  uint32_t checksum = 0;
  auto results = Profile(kDirectLoopTest, kProfileIterations, [&checksum]() {
    checksum = RunDirectLoop();
    g_cpu_result = checksum;
  });

  ASSERT(checksum == kDirectExpected);
  PrintMsg("CPU_WORK CpuTranslationBlocks::%s operations=%lu checksum=%08lx\n", kDirectLoopTest, kDirectOperations,
           checksum);
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

void CpuTranslationBlockTests::TestGeneratedCode(const char* name, bool rewrite, uint32_t operations,
                                                 uint32_t expected) {
  auto* code = static_cast<uint8_t*>(VirtualAlloc(nullptr, 4096, MEM_RESERVE | MEM_COMMIT, PAGE_EXECUTE_READWRITE));
  ASSERT(code);
  CpuCodeRewrite::Initialize(code);
  host_.PrepareDraw(0xFF101010);
  uint32_t checksum = 0;
  bool mismatch = false;
  auto results = Profile(name, kProfileIterations, [&]() {
    checksum = CpuCodeRewrite::Run(code, operations, rewrite);
    g_cpu_result = checksum;
    mismatch |= checksum != expected;
  });
  ASSERT(VirtualFree(code, 0, MEM_RELEASE));
  ASSERT(!mismatch);
  PrintMsg("CPU_WORK CpuTranslationBlocks::%s operations=%lu checksum=%08lx\n", name, operations, checksum);
  char metadata[160];
  snprintf(metadata, sizeof(metadata),
           "{\"oracle_status\":\"PASS\",\"operations\":%lu,\"work_checksum\":\"%08lx\","
           "\"result_checksum\":\"%08lx\",\"expected_checksum\":\"%08lx\"}",
           operations, CpuCodeRewrite::WorkChecksum(operations, rewrite), checksum, expected);
  host_.PrepareDraw(0xFF000000 | (checksum & 0x00FFFFFF));
  host_.FinishDraw(suite_name_, name, results, metadata);
}

void CpuTranslationBlockTests::TestJumpCache(const char* name, unsigned targets, bool collide, uint32_t expected) {
  auto* code = static_cast<uint8_t*>(
      VirtualAlloc(nullptr, CpuJumpCache::kPageBytes, MEM_RESERVE | MEM_COMMIT, PAGE_EXECUTE_READWRITE));
  ASSERT(code);
  ASSERT(CpuJumpCache::Initialize(code, targets, collide));
  const uintptr_t base = reinterpret_cast<uintptr_t>(code);
  const unsigned first_slot = CpuJumpCache::Slot(base);
  for (unsigned i = 0; i < targets; ++i) {
    const uintptr_t pc = base + CpuJumpCache::Offset(i, collide);
    ASSERT((pc & ~uintptr_t(4095)) == base);
    ASSERT((CpuJumpCache::Slot(pc) == first_slot) == (collide || i == 0));
    PrintMsg("CPU_TARGET %s index=%u pc=%08lx jump_slot=%u\n", name, i, static_cast<uint32_t>(pc),
             CpuJumpCache::Slot(pc));
  }
  const uint32_t work_checksum = CpuJumpCache::WorkChecksum(code);
  host_.PrepareDraw(0xFF101010);
  uint32_t checksum = 0;
  bool mismatch = false;
  auto results = Profile(name, kProfileIterations, [&]() {
    checksum = CpuJumpCache::Run(code, targets, collide, CpuJumpCache::kOperations);
    g_cpu_result = checksum;
    mismatch |= checksum != expected;
  });
  ASSERT(!mismatch);
  ASSERT(CpuJumpCache::WorkChecksum(code) == work_checksum);
  ASSERT(VirtualFree(code, 0, MEM_RELEASE));
  char metadata[256];
  snprintf(metadata, sizeof(metadata),
           "{\"oracle_status\":\"PASS\",\"operations\":%lu,\"targets\":%u,\"colliding\":%s,"
           "\"work_checksum\":\"%08lx\",\"result_checksum\":\"%08lx\",\"expected_checksum\":\"%08lx\"}",
           CpuJumpCache::kOperations, targets, collide ? "true" : "false", work_checksum, checksum, expected);
  PrintMsg("CPU_WORK CpuTranslationBlocks::%s operations=%lu checksum=%08lx\n", name, CpuJumpCache::kOperations,
           checksum);
  host_.PrepareDraw(0xFF000000 | (checksum & 0x00FFFFFF));
  host_.FinishDraw(suite_name_, name, results, metadata);
}
