/* SPDX-License-Identifier: Unlicense */
#include <hal/debug.h>
#include <hal/video.h>
#include <pbkit/pbkit_dma.h>
#include <stdint.h>
#include <string.h>
#include <windows.h>
#include <xboxkrnl/xboxkrnl.h>

#include "program.h"

#define APU 0xfe800000u
#define GPX 0x30000u
#define GP_RESET 0x3fffcu
#define EP_RESET 0x5fffcu
#define ENGINE 0x2000u

static uint32_t read_reg(unsigned offset) { return *(volatile uint32_t *)(APU + offset); }

static void write_reg(unsigned offset, uint32_t value) { *(volatile uint32_t *)(APU + offset) = value; }

static int32_t input(unsigned index) {
  static const int32_t edges[] = {0, 1, -1, 0x7fffff, -0x800000, 0x400001, -0x400001, 255};
  return index < 8 ? edges[index] : (int32_t)((index * 7919u) & 0x7fffffu) - 0x400000;
}

static uint32_t expected(unsigned route, int32_t value) {
  /* Exact rational gains, floor toward negative infinity. */
  int64_t numerator = route == 1 ? -(int64_t)value : value;
  int divisor = route == 2 ? 4 : 2;
  int64_t result = numerator >= 0 ? numerator / divisor : -((-numerator + divisor - 1) / divisor);
  return (uint32_t)result & 0xffffff;
}

int main(void) {
  XVideoSetMode(640, 480, 32, REFRESH_DEFAULT);
  debugPrint("Public DSP I/O proof: +1/2, -1/2, +1/4\n");
  /* Dedicated test boot only: do not disturb an active guest audio owner. */
  if ((read_reg(ENGINE) & 0x18) || (read_reg(GP_RESET) & 3) == 3 || (read_reg(EP_RESET) & 3) == 3) {
    debugPrint("UNSUPPORTED: APU already active\n");
    for (;;) Sleep(1000);
  }
  uint8_t *scratch = MmAllocateContiguousMemoryEx(8192, 0, MAXRAM, 4096, PAGE_READWRITE | PAGE_NOCACHE);
  uint32_t *sge = MmAllocateContiguousMemoryEx(4096, 0, MAXRAM, 4096, PAGE_READWRITE | PAGE_NOCACHE);
  if (!scratch || !sge) {
    debugPrint("FAIL: allocation\n");
    for (;;) Sleep(1000);
  }
  memset(scratch, 0, 8192);
  memset(sge, 0, 4096);
  memcpy(scratch, program, sizeof(program));
  sge[0] = (uint32_t)MmGetPhysicalAddress(scratch);
  sge[2] = (uint32_t)MmGetPhysicalAddress(scratch + 4096);
  write_reg(ENGINE, 0);
  write_reg(GP_RESET, 0);
  write_reg(EP_RESET, 0);
  write_reg(0x2040, (uint32_t)MmGetPhysicalAddress(sge));
  write_reg(0x20d4, 1);
  /* Empty voice lists ensure that only this synthetic GP program runs. */
  for (unsigned base = 0x2054; base <= 0x206c; base += 12) {
    for (unsigned i = 0; i < 3; i++) write_reg(base + i * 4, 0xffff);
  }
  /* One linear 32-bit GP scratch DMA exports all arithmetic outputs. */
  static const uint32_t node[] = {0x4000, 0x19e2, 192, 0x200, 0x1800, 0, 0};
  for (unsigned i = 0; i < 7; i++) write_reg(GPX + (0x20 + i) * 4, node[i]);
  for (unsigned i = 0; i < 64; i++) write_reg(GPX + (0x100 + i) * 4, (uint32_t)input(i) & 0xffffff);
  for (unsigned i = 0; i < 192; i++) write_reg(GPX + (0x200 + i) * 4, 0x555555);
  write_reg(GPX + 0x3f0 * 4, 0);
  write_reg(GPX + 0x3f1 * 4, 0);
  write_reg(GPX + 0x3f4 * 4, (uint32_t)MmGetPhysicalAddress(scratch) + 0x1800);
  write_reg(GPX + 0x3f5 * 4, ((uint32_t)MmGetPhysicalAddress(scratch) + 0x1800) >> 24);
  /* The host can distinguish this guest's failure verdict from boot state. */
  write_reg(GPX + 0x3f6 * 4, 0x5a07e1);
  write_reg(0x1100, read_reg(0x1100) & ~0xe0u);
  /* Bootstrap/enable only after every input and descriptor is ready. */
  write_reg(GP_RESET, 3);
  write_reg(ENGINE, 8);
  unsigned wait;
  for (wait = 0; wait < 10000 && read_reg(GPX + 0x3f0 * 4) != 0x51d00d; wait++) Sleep(1);
  /* Let an armed first-frame capture finish before the guest changes SECTL. */
  Sleep(100);
  write_reg(ENGINE, 0);
  /* GP writes acquire the APU execution lock in xemu. Keep buffers alive
   * until emulator exit: a late frame can never read freed DMA memory. */
  write_reg(GPX + 0x3f2 * 4, wait);
  unsigned failures = wait == 10000;
  for (unsigned route = 0; route < 3; route++) {
    for (unsigned i = 0; i < 64; i++) {
      uint32_t want = expected(route, input(i));
#ifdef INJECT_FAILURE
      if (!route && !i) want ^= 1;
#endif
      failures += read_reg(GPX + (0x200 + route * 64 + i) * 4) != want;
      failures += ((volatile uint32_t *)(scratch + 0x1800))[route * 64 + i] != want;
      failures += read_reg(GPX + (0x100 + i) * 4) != ((uint32_t)input(i) & 0xffffff);
    }
  }
  write_reg(GPX + 0x3f3 * 4, failures);
  write_reg(GPX + 0x3f1 * 4, failures ? 0xbad : 0x600d);
  debugPrint("%s: 192 exact output words, input preserved, failures=%u\n", failures ? "FAIL" : "PASS", failures);
  debugPrint("Mailbox GP X:$3f0..3f3; no throughput or hardware qualification.\n");
  for (;;) Sleep(1000);
}
