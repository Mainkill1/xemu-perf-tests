#ifndef XEMU_PERF_TESTS_DEBUG_OUTPUT_H
#define XEMU_PERF_TESTS_DEBUG_OUTPUT_H

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wmacro-redefined"
#include <windows.h>
#pragma clang diagnostic pop

#include <string>

#include "printf.h"

#define ASSERT(c)                                      \
  if (!(c)) {                                          \
    PrintAssertAndWaitForever(#c, __FILE__, __LINE__); \
  }

static constexpr uint16_t kXemuPerfMarkerPort = 0xE9;
static constexpr uint8_t kXemuPerfMarkerReadback = 0x58;
static constexpr uint8_t kXemuPerfMarkerMeasureBegin = 0xF0;
static constexpr uint8_t kXemuPerfMarkerMeasureEnd = 0xF1;
static constexpr uint8_t kXemuPerfMarkerGpuComplete = 0xF2;

inline void EmitXemuPerfMarker(uint8_t marker) {
  uint8_t readback;
  asm volatile("inb %w1, %0" : "=a"(readback) : "Nd"(kXemuPerfMarkerPort));
  if (readback == kXemuPerfMarkerReadback) {
    asm volatile("outb %0, %w1" : : "a"(marker), "Nd"(kXemuPerfMarkerPort));
  }
}

template <typename... VarArgs>
inline void PrintMsg(const char *fmt, VarArgs &&...args) {
  int string_length = snprintf_(nullptr, 0, fmt, args...);
  std::string buf;
  buf.resize(string_length);

  snprintf_(&buf[0], string_length + 1, fmt, args...);
  DbgPrint("%s", buf.c_str());
}

[[noreturn]] void PrintAssertAndWaitForever(const char *assert_code, const char *filename, uint32_t line);

#endif  // XEMU_PERF_TESTS_DEBUG_OUTPUT_H
