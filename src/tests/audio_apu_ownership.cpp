#include "audio_apu_ownership.h"

#include <iomanip>
#include <sstream>

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
  if (offset >= 0x35000 && offset <= 0x350FC) return true;
  // Only registers used by the admitted scaling session are writable.
  switch (offset) {
    case 0x1100: case 0x1510: case 0x2000:
    case 0x20200: case 0x20204:
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
  const bool cold = registers.fectl == 0 && registers.sectl == 0 &&
                    lists.gp_reset == 0 && lists.ep_reset == 0;
  const auto aligned_table = [](uint32_t address) {
    return address != 0 && (address & 0xFFFU) == 0;
  };
  // Retail startup can leave preallocated BIOS tables in a halted FE and
  // sample-counter-off SE state. This exact profile is admitted only with
  // empty lists; the hardware adapter also samples XGSCNT for quiescence.
  const bool firmware_quiescent =
      registers.fectl == 0x1F8FU && registers.sectl == 0x7U &&
      lists.gp_reset == 0 && lists.ep_reset == 1 &&
      aligned_table(registers.vpvaddr) &&
      aligned_table(registers.vpsgeaddr) &&
      aligned_table(registers.vpssladdr) &&
      aligned_table(registers.gpsaddr) && registers.epsaddr == 0;
  if (!cold && !firmware_quiescent) {
    return {false, "APU engine is not in the idle control state"};
  }
  for (uint32_t head : lists.vp_lists) {
    // 0xFFFF is the empty-list sentinel; voice index zero is valid.
    if (head != 0xFFFFU) return {false, "APU voice list is not empty"};
  }
  return {true, nullptr};
}

bool ApuCounterQuiet(uint32_t first, uint32_t second) {
  return first == second && first != 0xFFFFFFFFU;
}

std::string DescribeApuState(const ApuStateSnapshot &state) {
  std::ostringstream out;
  out << std::hex << std::setfill('0');
  auto word = [&out](const char *name, uint32_t value) {
    out << ' ' << name << "=0x" << std::setw(8) << value;
  };
  word("fectl", state.registers.fectl);
  word("sectl", state.registers.sectl);
  word("xgscnt", state.registers.xgscnt);
  word("vpvaddr", state.registers.vpvaddr);
  word("vpsgeaddr", state.registers.vpsgeaddr);
  word("vpssladdr", state.registers.vpssladdr);
  word("gpsaddr", state.registers.gpsaddr);
  word("epsaddr", state.registers.epsaddr);
  word("gp_reset", state.lists.gp_reset);
  word("ep_reset", state.lists.ep_reset);
  out << " lists=[";
  for (size_t index = 0; index < state.lists.vp_lists.size(); ++index) {
    if (index) out << ',';
    out << "0x" << std::setw(8) << state.lists.vp_lists[index];
  }
  out << ']';
  return out.str();
}

bool ApuStateRestored(const ApuStateSnapshot &before, const ApuStateSnapshot &after) {
  const auto &a = before.registers;
  const auto &b = after.registers;
  // XGSCNT is a monotonic observation counter, not restorable control state.
  return a.fectl == b.fectl && a.sectl == b.sectl &&
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
    error = std::string(decision.reason) + DescribeApuState(initial);
    io.Close();
    return false;
  }
  error.clear();
  return true;
}

}  // namespace AudioTorture
