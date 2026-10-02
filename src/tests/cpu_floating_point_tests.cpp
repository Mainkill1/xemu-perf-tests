#include "cpu_floating_point_tests.h"

#include <cstdint>
#include <cstring>

#include "debug_output.h"
#include "test_host.h"
#include "x87_status_workload.h"

static constexpr char kX87ScalarTest[] = "X87Scalar";
static constexpr char kSseScalarTest[] = "SSEScalar";
static constexpr uint32_t kProfileIterations = 10;
static constexpr uint32_t kX87OuterIterations = 1048576;
static constexpr uint32_t kSseOuterIterations = 196608;
static constexpr uint32_t kUnrolledCycles = 64;
static constexpr uint32_t kOperationsPerCycle = 4;
static constexpr uint32_t kExpectedBits = 0x3F800000;
static constexpr uint16_t kX87ControlWord = 0x007F;
static constexpr uint32_t kMxcsr = 0x00001F80;

static const float kHalf = 0.5f;
static const float kOneAndQuarter = 1.25f;
static volatile uint32_t g_fp_result;

static uint32_t FloatBits(float value) {
  uint32_t bits;
  memcpy(&bits, &value, sizeof(bits));
  return bits;
}

static uint32_t RunX87Scalar(uint16_t &status) {
  uint16_t saved_control_word;
  asm volatile("fnstcw %0" : "=m"(saved_control_word));
  asm volatile("fldcw %0\n\tfnclex" : : "m"(kX87ControlWord));

  float value = 1.0f;
  for (uint32_t i = 0; i < kX87OuterIterations; ++i) {
    asm volatile(
        "flds %[value]\n\t"
        ".rept 64\n\t"
        "fadds %[half]\n\t"
        "fmuls %[half]\n\t"
        "fadds %[one_quarter]\n\t"
        "fmuls %[half]\n\t"
        ".endr\n\t"
        "fstps %[value]"
        : [value] "+m"(value)
        : [half] "m"(kHalf), [one_quarter] "m"(kOneAndQuarter)
        : "st", "memory");
  }

  asm volatile("fnstsw %0" : "=m"(status));
  asm volatile("fldcw %0" : : "m"(saved_control_word));
  return FloatBits(value);
}

static uint32_t RunSseScalar(uint32_t &status) {
  uint32_t saved_mxcsr;
  asm volatile("stmxcsr %0" : "=m"(saved_mxcsr));
  asm volatile("ldmxcsr %0" : : "m"(kMxcsr));

  float value = 1.0f;
  for (uint32_t i = 0; i < kSseOuterIterations; ++i) {
    asm volatile(
        "movss %[value], %%xmm0\n\t"
        ".rept 64\n\t"
        "addss %[half], %%xmm0\n\t"
        "mulss %[half], %%xmm0\n\t"
        "addss %[one_quarter], %%xmm0\n\t"
        "mulss %[half], %%xmm0\n\t"
        ".endr\n\t"
        "movss %%xmm0, %[value]"
        : [value] "+m"(value)
        : [half] "m"(kHalf), [one_quarter] "m"(kOneAndQuarter)
        : "xmm0", "memory");
  }

  asm volatile("stmxcsr %0" : "=m"(status));
  asm volatile("ldmxcsr %0" : : "m"(saved_mxcsr));
  return FloatBits(value);
}

CpuFloatingPointTests::CpuFloatingPointTests(TestHost &host, std::string output_dir, const Config &config)
    : TestSuite(host, std::move(output_dir), "CpuFloatingPoint", config) {
  tests_[kX87ScalarTest] = [this]() { TestX87Scalar(); };
  tests_[kSseScalarTest] = [this]() { TestSseScalar(); };
  tests_["X87StatusVectors"] = [this]() { TestX87StatusVectors(); };
  tests_["X87StatusAX"] = [this]() { TestX87StatusWork(false); };
  tests_["X87CompareStatusAX"] = [this]() { TestX87StatusWork(true); };
}

void CpuFloatingPointTests::TestX87StatusVectors() {
  host_.PrepareDraw(0xFF101010);
  uint32_t failures = 0;
  auto results = Profile("X87StatusVectors", kProfileIterations, [&]() {
    failures |= CheckX87StatusVectors();
  });
  ASSERT(failures == 0);
  PrintMsg("CPU_WORK CpuFloatingPoint::X87StatusVectors cases=%lu failures=%lu\n",
           kX87StatusVectorCases, failures);
  host_.PrepareDraw(0xFF102030);
  host_.FinishDraw(suite_name_, "X87StatusVectors", results);
}

void CpuFloatingPointTests::TestX87StatusWork(bool compare) {
  const char* name = compare ? "X87CompareStatusAX" : "X87StatusAX";
  const uint32_t expected = compare ? kX87CompareStatusExpected : kX87StatusExpected;
  const uint32_t expected_eax = compare ? 0xa5a57000U : 0xa5a50000U;
  host_.PrepareDraw(0xFF101010);
  uint32_t failures = 0;
  X87StatusWorkResult value = {};
  auto results = Profile(name, kProfileIterations, [&]() {
    value = RunX87StatusWork(compare);
    failures |= value.checksum != expected || value.eax != expected_eax;
  });
  ASSERT(failures == 0);
  PrintMsg("CPU_WORK CpuFloatingPoint::%s operations=%lu checksum=%08lx eax=%08lx failures=%lu\n",
           name, kX87StatusOperations, value.checksum, value.eax, failures);
  host_.PrepareDraw(0xFF000000 | (value.checksum & 0x00FFFFFF));
  host_.FinishDraw(suite_name_, name, results);
}

void CpuFloatingPointTests::TestX87Scalar() {
  host_.PrepareDraw(0xFF101010);
  uint32_t result = 0;
  uint16_t status = 0;
  auto results = Profile(kX87ScalarTest, kProfileIterations, [&]() {
    result = RunX87Scalar(status);
    g_fp_result = result;
  });

  ASSERT(result == kExpectedBits);
  ASSERT((status & 0x003F) == 0);
  PrintMsg("CPU_WORK CpuFloatingPoint::%s operations=%lu result=%08lx status=%04x\n", kX87ScalarTest,
           kX87OuterIterations * kUnrolledCycles * kOperationsPerCycle, result, status);
  host_.PrepareDraw(0xFF000000 | (result & 0x00FFFFFF));
  host_.FinishDraw(suite_name_, kX87ScalarTest, results);
}

void CpuFloatingPointTests::TestSseScalar() {
  host_.PrepareDraw(0xFF101010);
  uint32_t result = 0;
  uint32_t status = 0;
  auto results = Profile(kSseScalarTest, kProfileIterations, [&]() {
    result = RunSseScalar(status);
    g_fp_result = result;
  });

  ASSERT(result == kExpectedBits);
  ASSERT((status & 0x003F) == 0);
  PrintMsg("CPU_WORK CpuFloatingPoint::%s operations=%lu result=%08lx mxcsr=%08lx\n", kSseScalarTest,
           kSseOuterIterations * kUnrolledCycles * kOperationsPerCycle, result, status);
  host_.PrepareDraw(0xFF000000 | (result & 0x00FFFFFF));
  host_.FinishDraw(suite_name_, kSseScalarTest, results);
}
