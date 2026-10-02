// SPDX-License-Identifier: GPL-2.0-or-later
#include <excpt.h>
#include <windows.h>

#include <cstddef>

#include "debug_output.h"
#include "x87_fault_workload.h"

static_assert(offsetof(FLOATING_SAVE_AREA, RegisterArea) == 32);
static_assert(sizeof(FLOATING_SAVE_AREA) >= 512);

// The suite invokes this serially on its owner thread. Its exception filter
// runs on that same thread and accepts only the exact owned-page read below.
struct X87GuestFaultState {
  const void* guard;
  bool active;
  bool pair;
  uint16_t control;
  uint32_t cases;
  uint32_t failures;
  uint32_t context_flags;
};

static X87GuestFaultState state;

static int CaptureFault(EXCEPTION_POINTERS* exception) {
  const auto* record = exception->ExceptionRecord;
  auto* context = exception->ContextRecord;
  if (!state.active || record->ExceptionCode != STATUS_ACCESS_VIOLATION || record->NumberParameters < 2 ||
      record->ExceptionInformation[0] != 0 ||
      record->ExceptionInformation[1] != reinterpret_cast<uintptr_t>(state.guard) ||
      context->Eip != X87FaultPc(state.pair) ||
      reinterpret_cast<uintptr_t>(record->ExceptionAddress) != X87FaultPc(state.pair)) {
    return EXCEPTION_CONTINUE_SEARCH;
  }
  X87FaultCapture captured = {};
  captured.eax = context->Eax;
  captured.has_fp_state = (context->ContextFlags & CONTEXT_FLOATING_POINT) == CONTEXT_FLOATING_POINT;
  const auto* source = reinterpret_cast<const uint8_t*>(&context->FloatSave);
  for (unsigned i = 0; i < sizeof(captured.fxsave); ++i) {
    captured.fxsave[i] = source[i];
  }
  ++state.cases;
  state.context_flags = context->ContextFlags;
  state.failures |= CheckX87FaultCapture(captured, state.pair, state.control);
  context->Eip = X87FaultResumePc(state.pair);
  return EXCEPTION_CONTINUE_EXECUTION;
}

X87StatusVectorResult CheckX87GuestFaultVectors() {
  X87SavedState saved;
  SaveX87(saved);
  void* guard = VirtualAlloc(nullptr, 4096, MEM_RESERVE | MEM_COMMIT, PAGE_NOACCESS);
  if (!guard) {
    RestoreX87(saved);
    return {0, 256};
  }
  state = {};
  state.guard = guard;
  for (uint16_t control : {uint16_t(0x007f), uint16_t(0x027f)}) {
    state.control = control;
    for (bool pair : {false, true}) {
      state.pair = pair;
      state.active = true;
      const uint32_t before = state.cases;
      uint32_t eax = 0;
      X87FaultCapture resumed = {};
      __try {
        eax = pair ? RunX87FaultPair(control, guard, resumed) : RunX87FaultScalar(control, guard, resumed);
        state.failures |= CheckX87FaultCapture(resumed, pair, control);
      } __except (CaptureFault(GetExceptionInformation())) {
        state.failures |= 128;
      }
      state.active = false;
      state.failures |= state.cases != before + 1 ? 128 : 0;
      state.failures |= eax != (pair ? 0xa5a53000U : 0xa5a53800U) ? 1 : 0;
      PrintMsg("CPU_FAULT kind=%s control=%04x captures=%lu context_flags=%08lx failures=%08lx\n",
               pair ? "pair" : "scalar", control, static_cast<unsigned long>(state.cases),
               static_cast<unsigned long>(state.context_flags), static_cast<unsigned long>(state.failures));
    }
  }
  if (!VirtualFree(guard, 0, MEM_RELEASE)) {
    state.failures |= 256;
  }
  state.guard = nullptr;
  RestoreX87(saved);
  return {state.cases, state.failures};
}
