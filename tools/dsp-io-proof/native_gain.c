/* SPDX-License-Identifier: Unlicense */
/* Standalone native arithmetic prototype. This cannot mutate a live APU.
 * Contract: 64 little-endian signed 24-bit words, three 64-word gain outputs.
 * Reject malformed input before emitting output; no implicit LLE fallback. */
#include <stdint.h>
#include <stdio.h>

int main(void) {
  uint8_t input[256], output[768];
  if (fread(input, 1, sizeof(input), stdin) != sizeof(input) || getchar() != EOF) {
    return 2;
  }
  for (unsigned route = 0; route < 3; route++) {
    for (unsigned index = 0; index < 64; index++) {
      const uint8_t *p = input + index * 4;
      if (p[3]) return 2;
      uint32_t word = (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16;
      int64_t value = word & 0x800000 ? (int64_t)word - 0x1000000 : word;
      if (route == 1) value = -value;
      unsigned shift = route == 2 ? 2 : 1;
      int64_t divisor = (int64_t)1 << shift;
      int64_t scaled = value / divisor;
      if (value < 0 && value % divisor) scaled--;
      uint32_t result = (uint32_t)scaled & 0xffffff;
      uint8_t *out = output + (route * 64 + index) * 4;
      out[0] = result;
      out[1] = result >> 8;
      out[2] = result >> 16;
      out[3] = 0;
    }
  }
  return fwrite(output, 1, sizeof(output), stdout) == sizeof(output) && !fflush(stdout) ? 0 : 3;
}
