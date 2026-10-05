// SPDX-License-Identifier: GPL-2.0-or-later
#include <cstdio>

#include "../src/tests/x87_status_workload.h"

int main() {
  const unsigned failures = CheckX87StatusVectors();
  if (failures) {
    std::fprintf(stderr, "x87 status vector failures: %u\n", failures);
    return 1;
  }
  const auto plain = RunX87StatusWork(false);
  const auto compare = RunX87StatusWork(true);
  if (kX87StatusOperations != 16777168 || plain.eax != 0xa5a50000U || plain.checksum != 0xf1100000U ||
      compare.eax != 0xa5a57000U || compare.checksum != 0xf0fb0000U) {
    std::fprintf(stderr, "x87 fixed-work oracle mismatch: %08x/%08x %08x/%08x\n", plain.eax, plain.checksum,
                 compare.eax, compare.checksum);
    return 1;
  }
  std::printf("PASS: x87 status vectors and both fixed-work oracles\n");
  return 0;
}
