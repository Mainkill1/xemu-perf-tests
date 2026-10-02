// SPDX-License-Identifier: GPL-2.0-or-later
#ifndef XEMU_PERF_TESTS_X87_FAULT_WORKLOAD_H
#define XEMU_PERF_TESTS_X87_FAULT_WORKLOAD_H

#include "x87_status_workload.h"

struct alignas(16) X87FaultCapture {
  uint8_t fxsave[512];
  uint32_t eax;
  bool has_fp_state;
};

// Xbox adapter; the native host checker supplies its own OS fault adapter.
X87StatusVectorResult CheckX87GuestFaultVectors();

extern "C" {
extern const char x87_fault_scalar_pc[] asm("x87_fault_scalar_pc");
extern const char x87_fault_scalar_resume[] asm("x87_fault_scalar_resume");
extern const char x87_fault_pair_pc[] asm("x87_fault_pair_pc");
extern const char x87_fault_pair_resume[] asm("x87_fault_pair_resume");
}

static inline uintptr_t X87FaultPc(bool pair) {
  return reinterpret_cast<uintptr_t>(pair ? x87_fault_pair_pc : x87_fault_scalar_pc);
}

static inline uintptr_t X87FaultResumePc(bool pair) {
  return reinterpret_cast<uintptr_t>(pair ? x87_fault_pair_resume : x87_fault_scalar_resume);
}

static inline uint64_t X87FaultReadLittleEndian(const uint8_t* bytes, unsigned count) {
  uint64_t value = 0;
  for (unsigned i = 0; i < count; ++i) {
    value |= uint64_t(bytes[i]) << (8 * i);
  }
  return value;
}

static inline uint32_t CheckX87FaultCapture(const X87FaultCapture& captured, bool pair, uint16_t control) {
  if (!captured.has_fp_state) {
    return 64;
  }
  const uint16_t status = pair ? 0x3000 : 0x3800;
  uint32_t failures = 0;
  failures |= captured.eax != (0xa5a50000U | status) ? 1 : 0;
  failures |= X87FaultReadLittleEndian(captured.fxsave + 2, 2) != status ? 2 : 0;
  failures |= X87FaultReadLittleEndian(captured.fxsave, 2) != control ? 4 : 0;
  failures |= captured.fxsave[4] != (pair ? 0xc0 : 0x80) ? 8 : 0;
  // FXSAVE's register slots are in logical ST order, 16 bytes apart. The
  // low ten bytes are the 80-bit value. Exact 6 and 3 need no FP conversion.
  failures |= X87FaultReadLittleEndian(captured.fxsave + 32, 8) != 0xc000000000000000ULL ||
                      X87FaultReadLittleEndian(captured.fxsave + 40, 2) != 0x4001
                  ? 16
                  : 0;
  if (pair) {
    failures |= X87FaultReadLittleEndian(captured.fxsave + 48, 8) != 0xc000000000000000ULL ||
                        X87FaultReadLittleEndian(captured.fxsave + 56, 2) != 0x4000
                    ? 32
                    : 0;
  }
  return failures;
}

// The critical instruction region has no helper/call/branch between the dirty
// arithmetic, FNSTSW AX and the faulting load. OS adapters accept only this
// exact load at their owned inaccessible page, then resume at its next PC.
__attribute__((noinline, unused)) static uint32_t RunX87FaultScalar(uint16_t control, const void* address,
                                                                    X87FaultCapture& resumed) {
  const uint32_t three = 0x40400000;
  uint32_t eax = 0;
  asm volatile(
      "fninit\n\tfldcw %[control]\n\tflds %[three]\n\tfadd %%st, %%st\n\t"
      "movl $0xa5a50000, %%eax\n\tfnstsw %%ax\n\t"
      ".globl x87_fault_scalar_pc\n\tx87_fault_scalar_pc:\n\t"
      "movl (%[address]), %%edx\n\t"
      ".globl x87_fault_scalar_resume\n\tx87_fault_scalar_resume:\n\tfxsave %[resumed]\n\tfnclex"
      : "+a"(eax), [resumed] "=m"(resumed.fxsave)
      : [control] "m"(control), [three] "m"(three), [address] "c"(address)
      : "memory", "edx", "st");
  resumed.eax = eax;
  resumed.has_fp_state = true;
  return eax;
}

__attribute__((noinline, unused)) static uint32_t RunX87FaultPair(uint16_t control, const void* address,
                                                                  X87FaultCapture& resumed) {
  const uint32_t one = 0x3f800000, two = 0x40000000, three = 0x40400000;
  uint32_t eax = 0;
  asm volatile(
      "fninit\n\tfldcw %[control]\n\tflds %[three]\n\tflds %[two]\n\tflds %[one]\n\t"
      "fadd %%st(2), %%st\n\tfaddp\n\t"
      "movl $0xa5a50000, %%eax\n\tfnstsw %%ax\n\t"
      ".globl x87_fault_pair_pc\n\tx87_fault_pair_pc:\n\t"
      "movl (%[address]), %%edx\n\t"
      ".globl x87_fault_pair_resume\n\tx87_fault_pair_resume:\n\tfxsave %[resumed]\n\tfnclex"
      : "+a"(eax), [resumed] "=m"(resumed.fxsave)
      : [control] "m"(control), [one] "m"(one), [two] "m"(two), [three] "m"(three), [address] "c"(address)
      : "memory", "edx", "st", "st(1)", "st(2)");
  resumed.eax = eax;
  resumed.has_fp_state = true;
  return eax;
}

#endif
