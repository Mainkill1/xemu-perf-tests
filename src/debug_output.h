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

// Extended events deliberately use 0xF8 followed by 0xA0..0xAF nibbles.
// Older marker receivers only recognize F0..F2, so they ignore an event
// instead of mistaking an event payload for a timing marker.
static constexpr uint8_t kXemuPerfEventPreamble = 0xF8;
static constexpr uint8_t kXemuPerfEventNibbleBase = 0xA0;
static constexpr uint8_t kXemuPerfEventVersion = 1;

enum class XemuPerfEventType : uint8_t {
  CONTEXT = 1,
  HEARTBEAT = 2,
  FAIL = 3,
  PASS = 4,
};

// Stable assertion IDs used by the host-side event decoder.  Do not reuse an
// ID for a different check: persisted failure artifacts use this as a key.
enum class XemuPerfAssertion : uint16_t {
  GENERIC_ASSERT = 1,
  COMPOSITE_PFIFO_TERMINAL = 0x100,
  COMPOSITE_AUDIO_BATCH = 0x101,
  COMPOSITE_SURFACE_FIRST = 0x102,
  COMPOSITE_SURFACE_CENTER = 0x103,
  COMPOSITE_SURFACE_LAST = 0x104,
  COMPOSITE_SCENE_CPU = 0x110,
  COMPOSITE_SCENE_FINAL = 0x111,
  CROSS_TITLE_S3TC_SOURCE0 = 0x126,
  CROSS_TITLE_S3TC_SOURCE1 = 0x127,
  CROSS_TITLE_S3TC_RESULT = 0x128,
  CROSS_TITLE_GPU_WAIT_CONTROL = 0x129,
  PFIFO_ARRAY_VERTEX_INPUT = 0x140,
  PFIFO_ARRAY_SURFACE = 0x141,
  PFIFO_ARRAY_FINAL = 0x142,
  PFIFO_ARRAY_FRAMEBUFFER = 0x143,
  PIPELINE_TEXTURE_INPUT = 0x150,
  PIPELINE_TEXTURE_BACKING = 0x151,
  PIPELINE_TEXTURE_SURFACE = 0x152,
  PIPELINE_TEXTURE_FINAL = 0x153,
  PIPELINE_TEXTURE_FRAMEBUFFER = 0x154,
};

inline void EmitXemuPerfMarker(uint8_t marker) {
  uint8_t readback;
  asm volatile("inb %w1, %0" : "=a"(readback) : "Nd"(kXemuPerfMarkerPort));
  if (readback == kXemuPerfMarkerReadback) {
    asm volatile("outb %0, %w1" : : "a"(marker), "Nd"(kXemuPerfMarkerPort));
  }
}

// Event frames are sent only when the existing opt-in marker device reports
// its 0x58 capability. The host receiver owns the durable event artifact;
// this guest path does no filesystem I/O.
void SetXemuPerfEventContext(uint32_t phase, uint32_t final_state);
void ClearXemuPerfEventContext();
void EmitXemuPerfEvent(XemuPerfEventType type, uint16_t assertion,
                       uint32_t expected, uint32_t actual);
void EmitXemuPerfHeartbeat();
void BeginXemuPerfTest();
void FinishXemuPerfTestFailureScreen();
void AssertXemuPerfEqual(uint32_t expected, uint32_t actual,
                         XemuPerfAssertion assertion, const char *assert_code,
                         const char *filename, uint32_t line);

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
