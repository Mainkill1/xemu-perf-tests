#include <cassert>
#include <cstdint>
#include <iostream>
#include <string>
#include <vector>

#include "audio_apu_ownership.h"

namespace {
struct FakeIo : AudioTorture::ApuRegisterIo {
  bool available{true};
  mutable std::vector<uint32_t> reads;
  std::vector<uint32_t> writes;
  bool Open(std::string &error) override {
    if (!available) { error = "device unavailable"; return false; }
    return true;
  }
  uint32_t Read32(uint32_t offset) const override {
    reads.push_back(offset);
    return offset >= 0x2054 && offset <= 0x2074 ? 0xFFFF : 0;
  }
  bool Write32(uint32_t offset, uint32_t) override {
    writes.push_back(offset);
    return true;
  }
  void Close() override {}
};
}  // namespace

int main() {
  using namespace AudioTorture;
  McpxApuRegisterSnapshot registers{};
  VoiceListSnapshot lists{};
  assert(!CheckApuOwnership(registers, lists).admitted);
  lists.vp_lists.fill(0xFFFF);
  assert(CheckApuOwnership(registers, lists).admitted);
  ApuStateSnapshot diagnostic{};
  diagnostic.registers.fectl = 0x100F;
  diagnostic.registers.sectl = 0xF;
  diagnostic.lists.vp_lists.fill(0xFFFF);
  const std::string diagnostic_text = DescribeApuState(diagnostic);
  assert(diagnostic_text.find("fectl=0x0000100f") != std::string::npos);
  assert(diagnostic_text.find("sectl=0x0000000f") != std::string::npos);
  assert(diagnostic_text.find("lists=[0x0000ffff") != std::string::npos);
  registers.fectl = 0x80;
  assert(!CheckApuOwnership(registers, lists).admitted);
  registers.fectl = 0;
  registers.sectl = 0x8;
  assert(!CheckApuOwnership(registers, lists).admitted);
  registers.sectl = 0;
  lists.vp_lists[0] = 1;
  assert(!CheckApuOwnership(registers, lists).admitted);
  lists.vp_lists[0] = 0xFFFF;
  lists.gp_reset = 3;
  assert(!CheckApuOwnership(registers, lists).admitted);
  lists.gp_reset = 0;
  lists.ep_reset = 3;
  assert(!CheckApuOwnership(registers, lists).admitted);
  lists.ep_reset = 0;

  FakeIo io;
  ApuStateSnapshot initial{};
  std::string error;
  io.available = false;
  assert(!OpenAndCheckApuOwnership(io, initial, error));
  assert(io.writes.empty());
  io.available = true;
  assert(OpenAndCheckApuOwnership(io, initial, error));
  assert(io.writes.empty());
  assert(io.reads.size() >= 19);
  auto changed = initial;
  changed.registers.vpsgeaddr = 0x1000;
  assert(!ApuStateRestored(initial, changed));
  changed = initial;
  changed.registers.xgscnt = 17;
  assert(ApuStateRestored(initial, changed));
  assert(ApuStateRestored(initial, initial));

  assert(ValidateApuPciResource(0x01B010DE, 0xFE800000, 0x0002, error));
  assert(!ValidateApuPciResource(0xFFFFFFFF, 0xFE800000, 0x0002, error));
  assert(!ValidateApuPciResource(0x01B010DE, 0xFE800001, 0x0002, error));
  assert(!ValidateApuPciResource(0x01B010DE, 0xFE800004, 0x0002, error));
  assert(!ValidateApuPciResource(0x01B010DE, 0xFE800000, 0x0000, error));
  assert(!IsApuRegisterWriteAllowed(0x2001));
  assert(!IsApuRegisterWriteAllowed(0x80000));
  assert(!IsApuRegisterWriteAllowed(0x5000));
  assert(IsApuRegisterWriteAllowed(0x1100));
  assert(IsApuRegisterWriteAllowed(0x1510));
  assert(IsApuRegisterWriteAllowed(0x2000));
  assert(IsApuRegisterWriteAllowed(0x20200));
  assert(IsApuRegisterWriteAllowed(0x35000));
  assert(IsApuRegisterWriteAllowed(0x3507C));
  assert(!IsApuRegisterWriteAllowed(0x35080));
  std::cout << "ownership rejection and restoration guarded\n";
}
