#ifndef XEMU_PERF_TESTS_DEVICE_INFO_H
#define XEMU_PERF_TESTS_DEVICE_INFO_H

#include <cstdint>
#include <string>
#include <vector>

// Polls guest-visible device state. Host CPU/GPU identity and clocks are not
// exposed to Xbox software and are reported as unavailable rather than guessed.
std::vector<std::string> PollDeviceInfo(const std::string &output_directory,
                                        uint32_t framebuffer_width,
                                        uint32_t framebuffer_height);

#endif  // XEMU_PERF_TESTS_DEVICE_INFO_H
