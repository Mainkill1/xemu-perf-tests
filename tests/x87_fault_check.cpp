// SPDX-License-Identifier: GPL-2.0-or-later
#include <sys/mman.h>
#include <ucontext.h>

#include <csignal>
#include <cstdio>
#include <cstdlib>

#include "../src/tests/x87_fault_workload.h"

static const void* guard;
static volatile sig_atomic_t pair_case;
static volatile sig_atomic_t captures;
static volatile sig_atomic_t failures;
static uint16_t control_word;

static void OnFault(int signal, siginfo_t* information, void* opaque) {
  auto* context = static_cast<ucontext_t*>(opaque);
  const bool pair = pair_case != 0;
  if (signal != SIGSEGV || information->si_addr != guard ||
      static_cast<uintptr_t>(context->uc_mcontext.gregs[REG_RIP]) != X87FaultPc(pair)) {
    std::_Exit(3);
  }
  X87FaultCapture captured = {};
  captured.eax = static_cast<uint32_t>(context->uc_mcontext.gregs[REG_RAX]);
  captured.has_fp_state = context->uc_mcontext.fpregs != nullptr;
  if (captured.has_fp_state) {
    const auto* source = reinterpret_cast<const uint8_t*>(context->uc_mcontext.fpregs);
    for (unsigned i = 0; i < sizeof(captured.fxsave); ++i) {
      captured.fxsave[i] = source[i];
    }
  }
  failures |= CheckX87FaultCapture(captured, pair, control_word);
  ++captures;
  context->uc_mcontext.gregs[REG_RIP] = X87FaultResumePc(pair);
}

int main() {
  X87SavedState saved;
  SaveX87(saved);
  struct sigaction action = {}, original = {};
  action.sa_sigaction = OnFault;
  action.sa_flags = SA_SIGINFO;
  sigemptyset(&action.sa_mask);
  if (sigaction(SIGSEGV, &action, &original) != 0) {
    return 2;
  }
  guard = mmap(nullptr, 4096, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
  if (guard == MAP_FAILED) {
    return 2;
  }
  for (uint16_t control : {uint16_t(0x007f), uint16_t(0x027f)}) {
    control_word = control;
    for (bool pair : {false, true}) {
      pair_case = pair;
      X87FaultCapture resumed = {};
      const uint32_t eax = pair ? RunX87FaultPair(control, guard, resumed) : RunX87FaultScalar(control, guard, resumed);
      failures |= CheckX87FaultCapture(resumed, pair, control);
      failures |= eax != (pair ? 0xa5a53000U : 0xa5a53800U);
    }
  }
  munmap(const_cast<void*>(guard), 4096);
  sigaction(SIGSEGV, &original, nullptr);
  RestoreX87(saved);
  if (captures != 4 || failures != 0) {
    std::fprintf(stderr, "x87 fault cases=%d failures=%d\n", captures, failures);
    return 1;
  }
  std::printf("PASS: 4 actual x87 memory-fault captures and resumptions\n");
  return 0;
}
