#include "device_info.h"

#include <cstdio>
#include <cstring>
#include <intrin.h>

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wmacro-redefined"
#include <windows.h>
#pragma clang diagnostic pop

#include <xboxkrnl/xboxkrnl.h>

namespace {

constexpr UCHAR kSmcAddress = 0x20;
constexpr UCHAR kSmcCpuTemperature = 0x09;
constexpr UCHAR kSmcBoardTemperature = 0x0A;

std::string FormatBytes(const char *label, uint64_t bytes) {
  constexpr uint64_t kBytesPerMiB = 1024ULL * 1024ULL;
  const uint64_t whole = bytes / kBytesPerMiB;
  const uint64_t tenths = (bytes % kBytesPerMiB) * 10 / kBytesPerMiB;
  char text[96] = {};
  snprintf(text, sizeof(text), "%s: %llu.%llu MiB", label,
           static_cast<unsigned long long>(whole),
           static_cast<unsigned long long>(tenths));
  return text;
}

std::string CpuVendor() {
  int registers[4] = {};
  __cpuid(registers, 0);
  char vendor[13] = {};
  memcpy(vendor, &registers[1], 4);
  memcpy(vendor + 4, &registers[3], 4);
  memcpy(vendor + 8, &registers[2], 4);
  return vendor;
}

std::string CpuSignature() {
  int registers[4] = {};
  __cpuid(registers, 1);
  const uint32_t signature = static_cast<uint32_t>(registers[0]);
  const uint32_t stepping = signature & 0xF;
  uint32_t model = (signature >> 4) & 0xF;
  uint32_t family = (signature >> 8) & 0xF;
  const uint32_t extended_model = (signature >> 16) & 0xF;
  const uint32_t extended_family = (signature >> 20) & 0xFF;
  if (family == 0xF) {
    family += extended_family;
  }
  if (family == 0x6 || family == 0xF) {
    model += extended_model << 4;
  }
  char text[80] = {};
  snprintf(text, sizeof(text), "CPU signature: family %lu model %lu step %lu",
           static_cast<unsigned long>(family), static_cast<unsigned long>(model),
           static_cast<unsigned long>(stepping));
  return text;
}

std::string TemperatureStatus() {
  ULONG cpu = 0;
  ULONG board = 0;
  const NTSTATUS cpu_status =
      HalReadSMBusValue(kSmcAddress, kSmcCpuTemperature, FALSE, &cpu);
  const NTSTATUS board_status =
      HalReadSMBusValue(kSmcAddress, kSmcBoardTemperature, FALSE, &board);
  if (!NT_SUCCESS(cpu_status) || !NT_SUCCESS(board_status) || cpu == 0 ||
      board == 0 || cpu > 127 || board > 127) {
    return "CPU / board temperature: no sensor data";
  }
  char text[80] = {};
  snprintf(text, sizeof(text), "CPU / board temperature: %lu C / %lu C",
           static_cast<unsigned long>(cpu),
           static_cast<unsigned long>(board));
  return text;
}

}  // namespace

std::vector<std::string> PollDeviceInfo(const std::string &output_directory,
                                        uint32_t framebuffer_width,
                                        uint32_t framebuffer_height) {
  std::vector<std::string> lines;
  lines.emplace_back("Guest-visible values; A refreshes this page.");
  lines.emplace_back("CPU vendor: " + CpuVendor());
  lines.emplace_back(CpuSignature());

  LARGE_INTEGER frequency{};
  if (QueryPerformanceFrequency(&frequency) && frequency.QuadPart > 0) {
    char text[80] = {};
    snprintf(text, sizeof(text), "Performance timer: %lld.%03lld MHz",
             frequency.QuadPart / 1000000,
             (frequency.QuadPart % 1000000) / 1000);
    lines.emplace_back(text);
  } else {
    lines.emplace_back("Performance timer: Unavailable");
  }

  SYSTEM_INFO system_info{};
  GetSystemInfo(&system_info);
  char cpu_count[64] = {};
  snprintf(cpu_count, sizeof(cpu_count), "Guest processors: %lu",
           static_cast<unsigned long>(system_info.dwNumberOfProcessors));
  lines.emplace_back(cpu_count);

  MM_STATISTICS memory{};
  memory.Length = sizeof(memory);
  if (NT_SUCCESS(MmQueryStatistics(&memory))) {
    const uint64_t page_size = system_info.dwPageSize;
    lines.emplace_back(FormatBytes("RAM total", memory.TotalPhysicalPages * page_size));
    lines.emplace_back(FormatBytes("RAM available", memory.AvailablePages * page_size));
  } else {
    lines.emplace_back("RAM: Unavailable");
  }

  char root[4] = "E:\\";
  if (output_directory.size() >= 2 && output_directory[1] == ':') {
    root[0] = output_directory[0];
  }
  ULARGE_INTEGER available{}, total{}, free{};
  if (GetDiskFreeSpaceEx(root, &available, &total, &free)) {
    lines.emplace_back(FormatBytes("Drive total", total.QuadPart));
    lines.emplace_back(FormatBytes("Drive free", free.QuadPart));
  } else {
    lines.emplace_back(std::string("Drive ") + root + ": Unavailable");
  }

  char hardware[96] = {};
  snprintf(hardware, sizeof(hardware), "NV2A rev %u; MCP rev %u",
           XboxHardwareInfo.GpuRevision, XboxHardwareInfo.McpRevision);
  lines.emplace_back(hardware);
  lines.emplace_back(TemperatureStatus());

  char video[64] = {};
  snprintf(video, sizeof(video), "Test video: %lux%lu RGBA8",
           static_cast<unsigned long>(framebuffer_width),
           static_cast<unsigned long>(framebuffer_height));
  lines.emplace_back(video);

  char kernel[80] = {};
  snprintf(kernel, sizeof(kernel), "Kernel: %u.%u.%u.%u", XboxKrnlVersion.Major,
           XboxKrnlVersion.Minor, XboxKrnlVersion.Build, XboxKrnlVersion.Qfe);
  lines.emplace_back(kernel);
  return lines;
}
