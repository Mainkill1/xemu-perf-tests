// SPDX-License-Identifier: GPL-2.0-or-later
#include <cstdio>

#include "../src/tests/x87_status_workload.h"

int main() {
  const auto result = CheckX87ExceptionStatusVectors();
  if (result.cases != 384 || result.failures != 0) {
    std::fprintf(stderr, "x87 exception-status cases=%u failures=%u\n", result.cases, result.failures);
    return 1;
  }
  std::printf("PASS: 384 masked/pending nonwaiting x87 status vectors\n");
  return 0;
}
