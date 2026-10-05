#include <sys/mman.h>

#include <cstdint>
#include <cstdio>

#include "tests/cpu_code_rewrite_workload.h"

int main() {
  auto* code = static_cast<uint8_t*>(
      mmap(nullptr, 4096, PROT_READ | PROT_WRITE | PROT_EXEC, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0));
  if (code == MAP_FAILED) return 2;
  struct Case {
    uint32_t operations;
    bool rewrite;
    uint32_t expected;
  };
  const Case cases[] = {
      {0, false, 0x12345678},        {0, true, 0x12345678},  {1, false, 0xE32F9558},       {1, true, 0xE32F9558},
      {2, false, 0x5E8F6AFF},        {2, true, 0xDDDF8872},  {3, false, 0xB0B6F923},       {3, true, 0x5AC34773},
      {16, false, 0x87414987},       {16, true, 0xDA7190D8}, {1000000, false, 0x2FD8B528}, {1000000, true, 0x65151D67},
      {50000000, false, 0xF5FF3985},
  };
  for (const auto& test : cases) {
    CpuCodeRewrite::Initialize(code);
    const auto result = CpuCodeRewrite::Run(code, test.operations, test.rewrite);
    if (result != test.expected) {
      std::fprintf(stderr, "operations=%u rewrite=%d expected=%08x actual=%08x\n", test.operations, test.rewrite,
                   test.expected, result);
      return 1;
    }
    std::printf("%u %d %08x %08x\n", test.operations, test.rewrite, result,
                CpuCodeRewrite::WorkChecksum(test.operations, test.rewrite));
  }
  return munmap(code, 4096) ? 2 : 0;
}
