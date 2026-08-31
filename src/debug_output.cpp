#include "debug_output.h"

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wignored-attributes"
#include <hal/debug.h>
#pragma clang diagnostic pop

#include <pbkit/pbkit.h>
#include <SDL.h>

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wmacro-redefined"
#include <windows.h>
#pragma clang diagnostic pop

#include <cstdio>

namespace {

volatile uint32_t g_event_phase = 0;
volatile uint32_t g_event_final_state = 0;
volatile uint32_t g_event_sequence = 0;
volatile bool g_event_context_active = false;
volatile bool g_failure_reported = false;
volatile bool g_failure_screen_shown = false;

void ShowSoftFailureScreen(const char *assert_code, const char *filename,
                           uint32_t line) {
  g_failure_screen_shown = true;
  debugClearScreen();
  debugPrint("TEST FAILED\n\n%s\n\n%s:%lu\n", assert_code, filename, line);
  debugPrint("\nContinuing in 10 seconds.\nPress A to continue now.\n");
  pb_show_debug_screen();

  const DWORD start = GetTickCount();
  bool advance = false;
  while (!advance && GetTickCount() - start < 10000) {
    SDL_Event event;
    while (SDL_PollEvent(&event)) {
      if (event.type == SDL_CONTROLLERBUTTONUP &&
          event.cbutton.button == SDL_CONTROLLER_BUTTON_A) {
        advance = true;
      }
    }
    Sleep(16);
  }
  pb_show_front_screen();
}

inline bool XemuPerfMarkerAvailable() {
  uint8_t readback;
  asm volatile("inb %w1, %0" : "=a"(readback) : "Nd"(kXemuPerfMarkerPort));
  return readback == kXemuPerfMarkerReadback;
}

inline void WriteXemuPerfPort(uint8_t value) {
  asm volatile("outb %0, %w1" : : "a"(value), "Nd"(kXemuPerfMarkerPort));
}

uint8_t EventChecksum(const uint8_t *bytes, uint32_t length) {
  uint8_t checksum = 0;
  for (uint32_t i = 0; i < length; ++i) {
    checksum ^= bytes[i];
    for (uint32_t bit = 0; bit < 8; ++bit) {
      checksum = (checksum & 0x80) ? static_cast<uint8_t>((checksum << 1) ^ 0x07)
                                   : static_cast<uint8_t>(checksum << 1);
    }
  }
  return checksum;
}

void AppendU16(uint8_t *bytes, uint32_t &offset, uint16_t value) {
  bytes[offset++] = static_cast<uint8_t>(value);
  bytes[offset++] = static_cast<uint8_t>(value >> 8);
}

void AppendU32(uint8_t *bytes, uint32_t &offset, uint32_t value) {
  for (uint32_t byte = 0; byte < 4; ++byte) {
    bytes[offset++] = static_cast<uint8_t>(value >> (byte * 8));
  }
}

}  // namespace

extern "C" {
void _putchar(char character) { putchar(character); }
}

void SetXemuPerfEventContext(uint32_t phase, uint32_t final_state) {
  g_event_phase = phase;
  g_event_final_state = final_state;
  g_event_context_active = true;
}

void ClearXemuPerfEventContext() {
  g_event_context_active = false;
}

void EmitXemuPerfEvent(XemuPerfEventType type, uint16_t assertion,
                       uint32_t expected, uint32_t actual) {
  if (type == XemuPerfEventType::FAIL) {
    g_failure_reported = true;
  } else if (type == XemuPerfEventType::PASS && g_failure_reported) {
    return;
  }
  if (!g_event_context_active || !XemuPerfMarkerAvailable()) {
    return;
  }

  // Wire format after F8: each raw byte is encoded as two A0..AF nibbles.
  // Raw bytes: version, type, phase:u16, assertion:u16, sequence:u32,
  // expected:u32, actual:u32, final_state:u32, crc8.
  uint8_t bytes[23]{};
  uint32_t offset = 0;
  bytes[offset++] = kXemuPerfEventVersion;
  bytes[offset++] = static_cast<uint8_t>(type);
  AppendU16(bytes, offset, static_cast<uint16_t>(g_event_phase));
  AppendU16(bytes, offset, assertion);
  AppendU32(bytes, offset, ++g_event_sequence);
  AppendU32(bytes, offset, expected);
  AppendU32(bytes, offset, actual);
  AppendU32(bytes, offset, g_event_final_state);
  const uint8_t checksum = EventChecksum(bytes, offset);
  bytes[offset++] = checksum;

  WriteXemuPerfPort(kXemuPerfEventPreamble);
  for (uint32_t i = 0; i < offset; ++i) {
    WriteXemuPerfPort(kXemuPerfEventNibbleBase | (bytes[i] >> 4));
    WriteXemuPerfPort(kXemuPerfEventNibbleBase | (bytes[i] & 0x0F));
  }
}

void EmitXemuPerfHeartbeat() {
  EmitXemuPerfEvent(XemuPerfEventType::HEARTBEAT, 0, 0, 0);
}

void BeginXemuPerfTest() {
  g_failure_reported = false;
  g_failure_screen_shown = false;
}

void FinishXemuPerfTestFailureScreen() {
  if (g_failure_reported && !g_failure_screen_shown) {
    ShowSoftFailureScreen("See saved test result for failure details", "guest test", 0);
  }
}

void AssertXemuPerfEqual(uint32_t expected, uint32_t actual,
                         XemuPerfAssertion assertion, const char *assert_code,
                         const char *filename, uint32_t line) {
  if (expected == actual) {
    return;
  }

  EmitXemuPerfEvent(XemuPerfEventType::FAIL, static_cast<uint16_t>(assertion),
                    expected, actual);
  if (!g_failure_screen_shown) {
    ShowSoftFailureScreen(assert_code, filename, line);
  }
}

[[noreturn]] void PrintAssertAndWaitForever(const char *assert_code, const char *filename, uint32_t line) {
  if (!g_failure_reported) {
    EmitXemuPerfEvent(XemuPerfEventType::FAIL,
                      static_cast<uint16_t>(XemuPerfAssertion::GENERIC_ASSERT),
                      0xFFFFFFFFU, 0xFFFFFFFFU);
  }
  DbgPrint("ASSERT FAILED: '%s' at %s:%d\n", assert_code, filename, line);
  debugPrint("ASSERT FAILED!\n-=[\n\n%s\n\n]=-\nat %s:%d\n", assert_code, filename, line);
  debugPrint("\nHalted, please reboot.\n");
  pb_show_debug_screen();
  while (true) {
    Sleep(2000);
  }
}
