# PGR2 manual full-race route

This exploratory route supplements the fixed automated PGR2 captures by
exercising shader and pipeline states encountered while a person drives. It is
not an exact performance qualification because the driving line, traffic,
speed, and track position differ between cells.

Run three cells serially:

1. Previous-main Vulkan.
2. Candidate Vulkan with an empty isolated SPIR-V cache.
3. The same candidate and portable profile with the exact cache published by
   cell 2.

For each cell, clone the immutable FreshBoot HDD seed and copy the exact xemu
binary plus a sibling `xemu.toml` into an isolated portable profile. Automate
the established BIOS and menu sequence through the final race confirmation.
Display a ready prompt, then give a five-second audible countdown. Send the
final confirmation input once and wait seven seconds before starting the
120-second measurement. The runner must send no gameplay input during the
measurement; the operator drives until xemu closes normally.

Admission requires an active-race image, advancing guest frames and host
presents, no focus loss or nonresponsive samples, normal shutdown, deletion of
the private HDD, and an unchanged seed hash. The seven-second alignment is a
fixed preset and does not detect the guest's actual race-start event.

Collect guest FPS, average interval, p95, p99, maximum, stalls, PresentMon,
process CPU and memory, NVIDIA GPU/VRAM/power samples, cache statistics, and
cache file size/hash. If the NVIDIA sampler is force-stopped, disclose any
buffered tail missing from the exported CSV.

Raw paths, screenshots, game media, and writable HDDs do not belong in public
evidence. Publish the sanitized result tables and exact source/build/test
identities.
