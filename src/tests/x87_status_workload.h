// SPDX-License-Identifier: GPL-2.0-or-later
#ifndef XEMU_PERF_TESTS_X87_STATUS_WORKLOAD_H
#define XEMU_PERF_TESTS_X87_STATUS_WORKLOAD_H

#include <cstdint>
#include <initializer_list>

static constexpr uint32_t kX87StatusOperations = 16777168;
static constexpr uint32_t kX87StatusExpected = 0xf1100000;
static constexpr uint32_t kX87CompareStatusExpected = 0xf0fb0000;
static constexpr uint32_t kX87StatusVectorCases = 6153;

// FSAVE's 32-bit operand layout is 108 bytes, also in 64-bit long mode.
struct alignas(16) X87SavedState {
  uint8_t bytes[108];
};

static inline void SaveX87(X87SavedState& saved) {
  asm volatile("fnsave %0"
               : "=m"(saved)
               :
               : "memory", "st", "st(1)", "st(2)", "st(3)", "st(4)", "st(5)", "st(6)", "st(7)");
}

static inline void RestoreX87(const X87SavedState& saved) {
  asm volatile("frstor %0"
               :
               : "m"(saved)
               : "memory", "st", "st(1)", "st(2)", "st(3)", "st(4)", "st(5)", "st(6)", "st(7)");
}

static inline uint32_t CheckX87StatusVectors() {
  X87SavedState saved;
  SaveX87(saved);
  uint32_t failures = 0;
  // All rounding modes and the three defined precision controls, exceptions
  // masked. Literals are instruction input, independent of emulator fields.
  static const uint16_t control_words[] = {0x007f, 0x027f, 0x037f, 0x047f, 0x067f, 0x077f,
                                           0x087f, 0x0a7f, 0x0b7f, 0x0c7f, 0x0e7f, 0x0f7f};
  for (uint16_t control : control_words) {
    for (uint32_t top = 0; top < 8; ++top) {
      for (uint32_t conditions = 0; conditions < 16; ++conditions) {
        for (uint16_t flags : {uint16_t(0), uint16_t(1), uint16_t(0x21), uint16_t(0x7f)}) {
          uint32_t environment[7] = {control, 0, 0xffff, 0, 0, 0, 0};
          // C0,C1,C2,C3 at bits8,9,10,14, and architectural TOP at11..13.
          uint16_t expected = (top << 11) | ((conditions & 7) << 8) | ((conditions & 8) << 11) | flags;
          environment[1] = expected;
          uint32_t eax = 0xa5a50000;
          uint16_t memory_status = 0xffff;
          asm volatile("fldenv %2\n\tfnstsw %%ax\n\tfnstsw %1"
                       : "+a"(eax), "=m"(memory_status)
                       : "m"(environment)
                       : "memory");
          failures += eax != (0xa5a50000U | expected) || memory_status != expected;
        }
      }
    }
  }
  // Dirty populated caches, FXCH/pop mapping, later writeback, and upper EAX.
  uint32_t eax = 0xa5a50000;
  uint32_t value = 0;
  uint16_t status = 0xffff;
  asm volatile(
      "fninit\n\tfld1\n\tfld1\n\tfxch %%st(1)\n\t"
      "faddp\n\tfnstsw %%ax\n\tfstps %1\n\tfnstsw %2"
      : "+a"(eax), "=m"(value), "=m"(status)
      :
      : "memory", "st", "st(1)");
  failures += eax != 0xa5a53800U || value != 0x40000000U || status != 0;
  eax = 0xa5a50000;
  asm volatile(
      "fninit\n\tfld1\n\tfincstp\n\tfnstsw %%ax\n\t"
      "fdecstp\n\tfnstsw %1\n\tfstps %2"
      : "+a"(eax), "=m"(status), "=m"(value)
      :
      : "memory", "st");
  failures += eax != 0xa5a50000U || status != 0x3800 || value != 0x3f800000U;
  eax = 0xa5a50000;
  asm volatile(
      "fninit\n\tfld1\n\tfld1\n\tfaddp\n\tfnstsw %%ax\n\t"
      "fxam\n\tfstps %1"
      : "+a"(eax), "=m"(value)
      :
      : "memory", "st", "st(1)");
  failures += eax != 0xa5a53800U || value != 0x40000000U;
  // Distinct exact operands catch FXCH ownership errors that equal operands
  // and commutative arithmetic cannot. Exercise both hard-FPU cache widths.
  const uint32_t one = 0x3f800000, two = 0x40000000, three = 0x40400000;
  for (uint16_t control : {uint16_t(0x007f), uint16_t(0x027f)}) {
    uint32_t other = 0;
    eax = 0xa5a50000;
    asm volatile(
        "fninit\n\tfldcw %4\n\tflds %5\n\tflds %6\n\t"
        "fxch %%st(1)\n\tfsub %%st(1), %%st\n\tfnstsw %%ax\n\t"
        "fstps %1\n\tfstps %2\n\tfnstsw %3"
        : "+a"(eax), "=m"(value), "=m"(other), "=m"(status)
        : "m"(control), "m"(two), "m"(three)
        : "memory", "st", "st(1)");
    failures += eax != 0xa5a53000U || value != 0xbf800000U || other != three || status != 0;
    eax = 0xa5a50000;
    asm volatile(
        "fninit\n\tfldcw %4\n\tflds %5\n\tflds %6\n\tflds %7\n\t"
        "fadd %%st(2), %%st\n\tfaddp\n\tfnstsw %%ax\n\t"
        "fxam\n\tfstps %1\n\tfstps %2\n\tfnstsw %3"
        : "+a"(eax), "=m"(value), "=m"(other), "=m"(status)
        : "m"(control), "m"(three), "m"(two), "m"(one)
        : "memory", "st", "st(1)", "st(2)");
    // ST0=6, ST1=3. FXAM marks positive finite normal (C2), then both pop.
    failures += eax != 0xa5a53000U || value != 0x40c00000U || other != three || status != 0x0400;
    eax = 0xa5a50000;
    asm volatile(
        "fninit\n\tfldcw %2\n\tflds %3\n\tfadd %%st, %%st\n\t"
        "fnstsw %%ax\n\tjmp 1f\n\t1:\n\tfstps %1"
        : "+a"(eax), "=m"(value)
        : "m"(control), "m"(three)
        : "memory", "st");
    failures += eax != 0xa5a53800U || value != 0x40c00000U;
  }
  RestoreX87(saved);
  return failures;
}

struct X87StatusWorkResult {
  uint32_t eax;
  uint32_t checksum;
};

// The asm is the same guest workload for hardware and both emulator builds.
// Odd outer count avoids checksums disappearing through power-of-two wrap.
__attribute__((noinline)) static X87StatusWorkResult RunX87StatusWork(bool compare) {
  X87SavedState saved;
  SaveX87(saved);
  uint32_t eax = 0xa5a50000, checksum = 0, iterations = 1048573;
  asm volatile("fninit" : : : "memory");
  if (compare) {
    asm volatile(
        "fld1\n\tfld1\n\t1:\n\t.rept 16\n\t"
        "fcom %%st(1)\n\tfnstsw %%ax\n\taddl %%eax, %%edx\n\t"
        ".endr\n\tdecl %%ecx\n\tjnz 1b\n\t"
        "fstp %%st(0)\n\tfstp %%st(0)"
        : "+a"(eax), "+d"(checksum), "+c"(iterations)
        :
        : "memory", "cc", "st", "st(1)");
  } else {
    asm volatile(
        "1:\n\t.rept 16\n\tfnstsw %%ax\n\taddl %%eax, %%edx\n\t"
        ".endr\n\tdecl %%ecx\n\tjnz 1b"
        : "+a"(eax), "+d"(checksum), "+c"(iterations)
        :
        : "memory", "cc");
  }
  RestoreX87(saved);
  return {eax, checksum};
}
#endif
