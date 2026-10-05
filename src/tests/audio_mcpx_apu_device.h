#ifndef XEMU_PERF_TESTS_AUDIO_MCPX_APU_DEVICE_H
#define XEMU_PERF_TESTS_AUDIO_MCPX_APU_DEVICE_H

#include <cstdint>
#include <string>

namespace AudioTorture {

struct McpxApuPciInfo {
  uint32_t bus{0};
  uint32_t device{0};
  uint32_t function{0};
  uint32_t slot_number{0};
  uint32_t bar0_physical{0};
  uint16_t pci_command{0};
};

struct McpxApuRegisterSnapshot {
  uint32_t fectl{0};
  uint32_t sectl{0};
  uint32_t xgscnt{0};
  uint32_t vpvaddr{0};
  uint32_t vpsgeaddr{0};
  uint32_t vpssladdr{0};
  uint32_t gpsaddr{0};
  uint32_t epsaddr{0};
};

class ApuRegisterIo {
 public:
  virtual ~ApuRegisterIo() = default;
  virtual bool Open(std::string &error) = 0;
  virtual uint32_t Read32(uint32_t offset) const = 0;
  virtual bool Write32(uint32_t offset, uint32_t value) = 0;
  virtual void Close() = 0;
};

// Guest-visible PCI/BAR adapter. ProbeAndMap remains read-only; Open() also
// admits ownership before any write becomes available.
class McpxApuDevice : public ApuRegisterIo {
 public:
  static constexpr uint16_t kVendorId = 0x10DE;
  static constexpr uint16_t kDeviceId = 0x01B0;
  static constexpr uint32_t kMmioBytes = 0x80000;

  McpxApuDevice() = default;
  ~McpxApuDevice();

  McpxApuDevice(const McpxApuDevice &) = delete;
  McpxApuDevice &operator=(const McpxApuDevice &) = delete;

  bool ProbeAndMap(std::string &error);
  bool Open(std::string &error) override;
  void Close() override;

  [[nodiscard]] bool IsMapped() const { return mmio_ != nullptr; }
  [[nodiscard]] const McpxApuPciInfo &PciInfo() const { return pci_info_; }

  bool Snapshot(McpxApuRegisterSnapshot &snapshot, std::string &error) const;
  uint32_t Read32(uint32_t offset) const override;
  bool Write32(uint32_t offset, uint32_t value) override;

 private:
  McpxApuPciInfo pci_info_{};
  volatile uint8_t *mmio_{nullptr};
  bool ownership_admitted_{false};
};

}  // namespace AudioTorture

#endif  // XEMU_PERF_TESTS_AUDIO_MCPX_APU_DEVICE_H
