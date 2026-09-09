# Main Vulkan profile: capture passed, thread attribution pending

One external CPU/scheduler/GPU capture of unchanged main completed with **zero lost events or buffers**. The saved trace is ready for further analysis. The first compact exports only provide process/module totals, so they do **not** establish PFIFO CPU time, ready delay, fence-wait time, GPU execution or a removable-copy bottleneck. No optimization or performance gain is claimed from this packet.

Main is `bd1fecb93353272dda2a810991e28945de35b665`, tree `6824a5aa4d9ca288ac96092dc9244684e995b08d`. The retained executable SHA256 is `3489fdcc593e942b92a612bf35a98f509ff0907e3370e1e5f45f2972d83fb16b`. No rebuild or source instrumentation was needed. Stored baseline statistics remain unchanged; this externally traced run is a diagnostic observation, not a replacement baseline or timing control. [Baseline identity and results](../main-apu-load-20260909/REPORT.md).

## What completed

| Check | Result |
| --- | --- |
| Exact executable, runner and controller hashes | Passed before launch |
| Workload | One Vulkan Morrowind snapshot cell, 20.0090458 seconds after the fixed input sequence |
| Selected Vulkan device | NVIDIA GeForce RTX 3070 Ti Laptop GPU; confirmed by the application log, not merely the installed-adapter list |
| Recorder | WPR 10.0.26100, GeneralProfile.Verbose.File + GPU.Verbose.File; normal stop succeeded |
| ETL integrity | 1,804,599,296 bytes; SHA256 `58a8bbeb4d837aeb5d6309f4ef884fc01d939d52c648706a63f642f79c6ac1c1`; zero lost events/buffers |
| Output | Automated nonblack check passed; separate visual inspection found the expected outdoor waterfront, buildings and crosshair, with no pause/menu overlay |
| Cleanup | No remaining owned workload/recorder/exporter process or private HDD; seed hash unchanged |
| Exact-PE symbol map | 60,273 defined text labels; reproducible map hash and known Vulkan label lookup checked |

The trace epoch is `2026-09-09T12:06:17.2135900Z`. The exact measurement range is `21,796,061.5`–`41,805,107.3` microseconds from that epoch. Initial xperf exports used `-range 21796062 41805107`, excluding less than one microsecond at each endpoint. The trace includes startup/cleanup outside this measurement interval; whole-trace totals must not be presented as the measured workload.

The [run record](vulkan-run.json) retains cadence 22.480320/s, p95 53.267 ms and p99 59.018 ms. These are NV2A display-write cadence proxies under WPR, not rendered FPS or evidence of a regression relative to the untraced baseline. No independent pixel/audio oracle, OpenGL profile, full XISO or PGR2 campaign was run for this attribution step. No guest-suite or XISO source changed.

## Preserved setup and extraction limits

The first recorder admission failed with `Invalid temporary trace directory` (`0xc5586004`) before any recorder or workload started. Creating a fresh owned temporary directory corrected the setup; **exactly one gameplay launch** followed. This failed admission is preserved separately from the successful capture.

`xperf -a profile -detail` exports process/module totals; its Usage% denominator includes all 16 CPUs. `xperf -a cswitch` in the initial form exports system-wide CPU occupancy. Neither identifies the PFIFO thread or its wait/ready intervals. This version rejects `xperf -a gpu` as an unsupported action; that error does not show that GPU events were absent. The GPU profile was enabled, but usable per-process GPU activity remains to be established from the saved trace.

The installed WPAExporter supports profile/config-driven offline extraction. A filtered export of sampled CPU, precise scheduling and GPU activity is the next step, using the existing ETL and exact PID/window. No second gameplay run is needed. Large system-wide process maps, raw logs and the ETL remain private; they contain unrelated host data. This public packet includes sanitized identities/results and the exact executable's text-symbol map, with no game assets, guest bytes or private configuration.

## Reproduce the symbol map

[extract-defined-text-symbols.sh](extract-defined-text-symbols.sh) rejects an executable with a different SHA256. It requires Bash, gzip, Perl and MinGW binutils. It uses defined COFF text labels, not source-line or inline-stack information:

```bash
bash extract-defined-text-symbols.sh /path/to/exact/xemu.exe rebuilt-symbols.tsv.gz
sha256sum rebuilt-symbols.tsv.gz
# Expected: 7f6a819281b06566664b15f4d64d381307edd9b3e76af2fedff8f7325b556ee1
```

Subtract the recorded runtime image base from a sampled xemu IP to obtain its RVA; require it to fall inside the recorded image. Do not subtract the preferred PE base from an ASLR address. An example lookup using a known symbol RVA is:

```bash
gzip -dc defined-text-symbols.tsv.gz |
  TARGET_RVA=0x00296c90 perl -F'\t' -ane 'next if /^#/; $last=$_ if hex($F[1]) <= hex($ENV{TARGET_RVA}); END { print $last if defined $last }'
# pgraph_vk_finish
```

A nearest label alone cannot restore missing frames or distinguish this common submission function's copying, submission and fence-wait operations. Caller/callee frames and scheduling/GPU correlation are still required. [Manifest](manifest.json); [sanitized selected-device lines](device-selection.txt); [diagnostic tracking PR](https://github.com/Mainkill1/xemu/pull/54). The separate [STI candidate remains held](../sti-shadow-entry-20260909/REPORT.md).
