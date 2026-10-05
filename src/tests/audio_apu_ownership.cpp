#include "audio_apu_ownership.h"

namespace AudioTorture {
namespace {
constexpr uint32_t kApuAperture = 0x80000;
constexpr uint32_t kVoiceListBase = 0x2054;
constexpr uint32_t kGpReset = 0x3FFFC;
constexpr uint32_t kEpReset = 0x5FFFC;
constexpr uint16_t kPciMemoryDecode = 1U << 1;
}  // namespace

bool ValidateApuPciResource(uint32_t vendor_device, uint32_t raw_bar0,
                            uint16_t command, std::string &error) {
  error.clear();
  if (vendor_device != 0x01B010DEU) {
    error = "MCPX APU PCI identity is absent or unexpected";
  } else if (raw_bar0 & 1U) {
    error = "MCPX APU BAR0 is I/O space";
  } else if ((raw_bar0 & 0x6U) == 0x4U) {
    error = "MCPX APU BAR0 is 64-bit memory";
  } else if ((raw_bar0 & ~0xFU) == 0 || (raw_bar0 & ~0xFU) == 0xFFFFFFF0U) {
    error = "MCPX APU BAR0 is not assigned";
  } else if (!(command & kPciMemoryDecode)) {
    error = "MCPX APU PCI memory-space decoding is disabled";
  }
  return error.empty();
}

bool IsApuRegisterWriteAllowed(uint32_t offset) {
  if ((offset & 3U) || offset > kApuAperture - sizeof(uint32_t)) return false;
  // Initial adapter admits only address and list-head registers. Engine
  // control/voice writes require a separately validated session contract.
  switch (offset) {
    case 0x202C: case 0x2030: case 0x2034:
    case 0x2040: case 0x2044: case 0x2048: case 0x204C:
    case 0x2054: case 0x2058: case 0x205C:
    case 0x2060: case 0x2064: case 0x2068:
    case 0x206C: case 0x2070: case 0x2074:
      return true;
    default:
      return false;
  }
}

ApuOwnershipDecision CheckApuOwnership(const McpxApuRegisterSnapshot &registers,
                                       const VoiceListSnapshot &lists) {
  if (registers.fectl != 0 || registers.sectl != 0) {
    return {false, "APU engine is not in the idle control state"};
  }
  for (uint32_t head : lists.vp_lists) {
    // 0xFFFF is the empty-list sentinel; voice index zero is valid.
    if (head != 0xFFFFU) return {false, "APU voice list is not empty"};
  }
  if (lists.gp_reset != 0 || lists.ep_reset != 0) {
    return {false, "GP or EP is released from reset"};
  }
  return {true, nullptr};
}

bool ApuStateRestored(const ApuStateSnapshot &before, const ApuStateSnapshot &after) {
  const auto &a = before.registers;
  const auto &b = after.registers;
  return a.fectl == b.fectl && a.sectl == b.sectl && a.xgscnt == b.xgscnt &&
         a.vpvaddr == b.vpvaddr && a.vpsgeaddr == b.vpsgeaddr &&
         a.vpssladdr == b.vpssladdr && a.gpsaddr == b.gpsaddr &&
         a.epsaddr == b.epsaddr &&
         before.lists.vp_lists == after.lists.vp_lists &&
         before.lists.gp_reset == after.lists.gp_reset &&
         before.lists.ep_reset == after.lists.ep_reset;
}

bool ReadApuState(const ApuRegisterIo &io, ApuStateSnapshot &state) {
  state = {};
  auto &r = state.registers;
  r.fectl = io.Read32(0x1100);
  r.sectl = io.Read32(0x2000);
  r.xgscnt = io.Read32(0x200C);
  r.vpvaddr = io.Read32(0x202C);
  r.vpsgeaddr = io.Read32(0x2030);
  r.vpssladdr = io.Read32(0x2034);
  r.gpsaddr = io.Read32(0x2040);
  r.epsaddr = io.Read32(0x2048);
  for (size_t index = 0; index < state.lists.vp_lists.size(); ++index) {
    state.lists.vp_lists[index] = io.Read32(kVoiceListBase + 4U * index);
  }
  state.lists.gp_reset = io.Read32(kGpReset);
  state.lists.ep_reset = io.Read32(kEpReset);
  return r.fectl != 0xFFFFFFFFU && r.sectl != 0xFFFFFFFFU &&
         state.lists.gp_reset != 0xFFFFFFFFU && state.lists.ep_reset != 0xFFFFFFFFU;
}

bool OpenAndCheckApuOwnership(ApuRegisterIo &io, ApuStateSnapshot &initial,
                              std::string &error) {
  initial = {};
  if (!io.Open(error)) return false;
  if (!ReadApuState(io, initial)) {
    error = "MCPX APU ownership snapshot is unreadable";
    io.Close();
    return false;
  }
  const auto decision = CheckApuOwnership(initial.registers, initial.lists);
  if (!decision.admitted) {
    error = decision.reason;
    io.Close();
    return false;
  }
  error.clear();
  return true;
}

}  // namespace AudioTorture
