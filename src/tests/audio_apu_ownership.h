#ifndef XEMU_PERF_TESTS_AUDIO_APU_OWNERSHIP_H
#define XEMU_PERF_TESTS_AUDIO_APU_OWNERSHIP_H

#include <array>
#include <cstdint>
#include <string>

#include "audio_mcpx_apu_device.h"

namespace AudioTorture {

struct VoiceListSnapshot {
  // Top/current/next for 2D, 3D, and multipass lists.
  std::array<uint32_t, 9> vp_lists{};
  uint32_t gp_reset{0};
  uint32_t ep_reset{0};
};

struct ApuStateSnapshot {
  McpxApuRegisterSnapshot registers{};
  VoiceListSnapshot lists{};
};

struct ApuOwnershipDecision {
  bool admitted{false};
  const char *reason{nullptr};
};

ApuOwnershipDecision CheckApuOwnership(const McpxApuRegisterSnapshot &registers,
                                       const VoiceListSnapshot &lists);
std::string DescribeApuState(const ApuStateSnapshot &state);
bool ApuCounterQuiet(uint32_t first, uint32_t second);
bool ApuStateRestored(const ApuStateSnapshot &before, const ApuStateSnapshot &after);
bool ValidateApuPciResource(uint32_t vendor_device, uint32_t raw_bar0,
                            uint16_t command, std::string &error);
bool IsApuRegisterWriteAllowed(uint32_t offset);
bool ReadApuState(const ApuRegisterIo &io, ApuStateSnapshot &state);
bool OpenAndCheckApuOwnership(ApuRegisterIo &io, ApuStateSnapshot &initial,
                              std::string &error);

}  // namespace AudioTorture

#endif  // XEMU_PERF_TESTS_AUDIO_APU_OWNERSHIP_H
