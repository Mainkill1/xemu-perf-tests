#ifndef XEMU_PERF_TESTS_CPU_CODE_REWRITE_WORKLOAD_H
#define XEMU_PERF_TESTS_CPU_CODE_REWRITE_WORKLOAD_H

#include <cstdint>

namespace CpuCodeRewrite {

// The caller supplies a page-aligned, writable and executable buffer. Placing
// the entry at byte 3 aligns the immediate operand for each 32-bit code store.
inline void Initialize(uint8_t* code) {
  const uint8_t bytes[] = {0x90, 0x90, 0x90, 0xB8, 0x5A, 0x5A, 0xA5, 0xA5, 0xC3};
  for (unsigned i = 0; i < sizeof(bytes); ++i) code[i] = bytes[i];
}

inline void SerializeCode() {
  uint32_t eax = 0, ebx, ecx, edx;
  asm volatile("cpuid" : "+a"(eax), "=b"(ebx), "=c"(ecx), "=d"(edx) : : "memory");
}

inline uint32_t Run(uint8_t* code, uint32_t operations, bool rewrite) {
  auto* immediate = reinterpret_cast<volatile uint32_t*>(code + 4);
  auto entry = reinterpret_cast<uint32_t (*)()>(code + 3);
  uint32_t state = 0x12345678;
  for (uint32_t i = 0; i < operations; ++i) {
    if (rewrite) *immediate = (i & 1) ? 0x5A5AA5A5 : 0xA5A55A5A;
    // Both leaves include the same serializing instruction before executing
    // mov eax, immediate; ret. Only the rewrite leaf stores into the code page.
    SerializeCode();
    state = ((state << 5) | (state >> 27)) ^ entry();
    state += i * 0x9E3779B9;
  }
  return state;
}
}  // namespace CpuCodeRewrite

#endif
