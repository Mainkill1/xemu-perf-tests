#include "audio_mcpx_apu_device.h"

#include "audio_apu_ownership.h"

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wignored-attributes"
#include <xboxkrnl/xboxkrnl.h>
#pragma clang diagnostic pop

namespace AudioTorture {
namespace {

constexpr uint32_t kPciVendorDevice = 0x00;
constexpr uint32_t kPciCommand = 0x04;
constexpr uint32_t kPciBar0 = 0x10;

constexpr uint32_t kNvPapuFectl = 0x00001100;
constexpr uint32_t kNvPapuSectl = 0x00002000;
constexpr uint32_t kNvPapuXgscnt = 0x0000200C;
constexpr uint32_t kNvPapuVpvaddr = 0x0000202C;
constexpr uint32_t kNvPapuVpsgeaddr = 0x00002030;
constexpr uint32_t kNvPapuVpssladdr = 0x00002034;
constexpr uint32_t kNvPapuGpsaddr = 0x00002040;
constexpr uint32_t kNvPapuEpsaddr = 0x00002048;

uint32_t PciSlotNumber(uint32_t device, uint32_t function) {
  // Xbox PCI_SLOT_NUMBER stores DeviceNumber in bits 0..4 and
  // FunctionNumber in bits 5..7.
  return (device & 0x1FU) | ((function & 0x07U) << 5U);
}

}  // namespace

McpxApuDevice::~McpxApuDevice() { Close(); }

bool McpxApuDevice::ProbeAndMap(std::string &error) {
  Close();
  error.clear();

  bool found = false;
  for (uint32_t device = 0; device < 32 && !found; ++device) {
    for (uint32_t function = 0; function < 8; ++function) {
      const uint32_t slot = PciSlotNumber(device, function);
      uint32_t vendor_device = 0xFFFFFFFFU;
      HalReadWritePCISpace(0, slot, kPciVendorDevice, &vendor_device,
                           sizeof(vendor_device), FALSE);
      const uint16_t vendor = vendor_device & 0xFFFFU;
      const uint16_t device_id = vendor_device >> 16U;
      if (vendor != kVendorId || device_id != kDeviceId) {
        continue;
      }

      pci_info_.bus = 0;
      pci_info_.device = device;
      pci_info_.function = function;
      pci_info_.slot_number = slot;
      found = true;
      break;
    }
  }

  if (!found) {
    error = "MCPX APU PCI device 10de:01b0 was not found";
    return false;
  }

  uint32_t bar0 = 0;
  HalReadWritePCISpace(pci_info_.bus, pci_info_.slot_number, kPciBar0,
                       &bar0, sizeof(bar0), FALSE);
  HalReadWritePCISpace(pci_info_.bus, pci_info_.slot_number, kPciCommand,
                       &pci_info_.pci_command, sizeof(pci_info_.pci_command),
                       FALSE);
  if (!ValidateApuPciResource(0x01B010DEU, bar0, pci_info_.pci_command,
                              error)) {
    return false;
  }
  pci_info_.bar0_physical = bar0 & ~0x0FU;

  mmio_ = static_cast<volatile uint8_t *>(
      MmMapIoSpace(pci_info_.bar0_physical, kMmioBytes,
                   PAGE_READWRITE | PAGE_NOCACHE));
  if (!mmio_) {
    error = "MmMapIoSpace failed for MCPX APU BAR0";
    return false;
  }
  return true;
}

bool McpxApuDevice::Open(std::string &error) {
  if (!ProbeAndMap(error)) return false;
  ApuStateSnapshot initial{};
  if (!ReadApuState(*this, initial)) {
    error = "MCPX APU ownership snapshot is unreadable";
    Close();
    return false;
  }
  const auto decision = CheckApuOwnership(initial.registers, initial.lists);
  if (!decision.admitted) {
    error = decision.reason;
    Close();
    return false;
  }
  ownership_admitted_ = true;
  return true;
}

void McpxApuDevice::Close() {
  ownership_admitted_ = false;
  if (mmio_) {
    MmUnmapIoSpace(const_cast<uint8_t *>(mmio_), kMmioBytes);
    mmio_ = nullptr;
  }
  pci_info_ = {};
}

bool McpxApuDevice::Write32(uint32_t offset, uint32_t value) {
  if (!mmio_ || !ownership_admitted_ || !IsApuRegisterWriteAllowed(offset)) {
    return false;
  }
  volatile uint32_t *target =
      reinterpret_cast<volatile uint32_t *>(mmio_ + offset);
  *target = value;
  return true;
}

uint32_t McpxApuDevice::Read32(uint32_t offset) const {
  if (!mmio_ || (offset & 3U) != 0 || offset > kMmioBytes - sizeof(uint32_t)) {
    return 0xFFFFFFFFU;
  }
  const volatile uint32_t *value =
      reinterpret_cast<const volatile uint32_t *>(mmio_ + offset);
  return *value;
}

bool McpxApuDevice::Snapshot(McpxApuRegisterSnapshot &snapshot,
                             std::string &error) const {
  snapshot = {};
  error.clear();
  if (!mmio_) {
    error = "MCPX APU is not mapped";
    return false;
  }

  snapshot.fectl = Read32(kNvPapuFectl);
  snapshot.sectl = Read32(kNvPapuSectl);
  snapshot.xgscnt = Read32(kNvPapuXgscnt);
  snapshot.vpvaddr = Read32(kNvPapuVpvaddr);
  snapshot.vpsgeaddr = Read32(kNvPapuVpsgeaddr);
  snapshot.vpssladdr = Read32(kNvPapuVpssladdr);
  snapshot.gpsaddr = Read32(kNvPapuGpsaddr);
  snapshot.epsaddr = Read32(kNvPapuEpsaddr);
  return true;
}

}  // namespace AudioTorture
