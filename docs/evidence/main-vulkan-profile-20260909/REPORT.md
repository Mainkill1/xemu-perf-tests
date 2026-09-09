# Main Vulkan profile: PFIFO timing established, wait causes pending

The saved unchanged-main trace identifies PFIFO and supports a complete timing partition for its 20.0090458-second window. PFIFO ran for 4.4943294 s and was off-CPU for 15.5147164 s. The exported ready timestamps further separate waiting from scheduling delay with the disclosed rounding correction below. No fence cause, GPU utilization, FPS change or optimization gain is established.

Main is `bd1fecb93353272dda2a810991e28945de35b665`, tree `6824a5aa4d9ca288ac96092dc9244684e995b08d`. The retained executable SHA256 is `3489fdcc593e942b92a612bf35a98f509ff0907e3370e1e5f45f2972d83fb16b`. No rebuild or source instrumentation was needed. Stored baseline statistics remain unchanged; this externally traced run is a diagnostic observation, not a replacement baseline or timing control. [Baseline identity and results](../main-apu-load-20260909/REPORT.md).

## Bounded attribution

| Observation | Value | Scope |
| --- | ---: | --- |
| PFIFO scheduled running | 4.4943294 s | 22.4615% of the selected window |
| PFIFO waiting | 15.4398723 s |Clipped exported ready-time boundary, with stated rounding correction |
| PFIFO ready for scheduling | 0.0748441 s |Clipped and corrected; not a wait-cause label |
| Process GPU execution union | 7.5774547 s |Overlapping execution intervals counted once; not whole-device utilization |
| Process GPU execution overlapping PFIFO waiting | 7.0244536 s |Temporal overlap only; no wait/submission dependency is proved |

In 52 zero-Waits rows, exported Ready Time precedes Last Switch-Out by 0.1–1.1 µs, 13.9 µs total. The partition clamps those ready edges to Last Switch-Out. The uncorrected clipped ready sum is 0.0748580 s. The packet does not identify whether WPA observed or synthesized each ready edge. `Old Wait Reason` describes the other outgoing thread at PFIFO switch-in and is excluded from PFIFO cause attribution.

The clean export contains 4,183 PFIFO sampled rows, 19,133 PFIFO scheduling rows and 9,652 process-GPU rows. [Compact data and hash bridge](attribution/manifest.json), [reproducible totals](attribution/summary.json), [PFIFO identity proof](attribution/identity.json) and [validation](attribution/validation.json) are included. [Portable export, minimization and analysis tools](../../../utils/wpa-attribution/README.md) recreate the accepted profile and reproduce the compact results. Complete-record checks cannot prove absence of a silently omitted valid block; retain the source hashes, target/range, counts and partition checks together.

The sampled weights total 4,179.0205 ms, separate from precise scheduled time. The leading named xemu leaf is `tlb_reset_dirty_range_all`: 407.9830 ms, 9.7626% of PFIFO sample weight. `create_pipeline` contributes 102.9708 ms, 2.4640%. Names are assigned only through an exact executable `.pdata` extent whose beginning matches a defined text label. [All leaf groups](attribution/sampled-leaf-summary.csv) retain external modules and unknowns separately. Unresolved deeper frames prevent caller attribution; module names do not identify a Vulkan operation.

The next measurement is [diagnostic draft #57](https://github.com/Mainkill1/xemu/pull/57), which reuses existing Vulkan submit/fence counters with deferred output and optional full timing. Source review and the candidate build passed; native checks are pending. Dirty-TLB rearming remains a CPU investigation route. Neither observation justifies removing synchronization or bypassing dirty tracking.

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

The installed WPAExporter subsequently completed the filtered three-table export above using the same ETL and exact PID/window. No second gameplay run occurred. Large system-wide process maps, raw logs and the ETL remain private; they contain unrelated host data. This public packet includes compact target IDs/timestamps, xemu RVAs, external module basenames, GPU intervals and the exact executable's text-symbol map, with no game assets, guest bytes, unrelated process names or private configuration.

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

A nearest label alone cannot restore missing frames or distinguish this common submission function's copying, submission and fence-wait operations. The scheduling/GPU overlap above does not replace the missing caller/callee evidence needed to explain the wait. [Manifest](manifest.json); [sanitized selected-device lines](device-selection.txt); [diagnostic tracking PR](https://github.com/Mainkill1/xemu/pull/54). The separate [STI candidate remains held](../sti-shadow-entry-20260909/REPORT.md).

## Offline exporter diagnosis

[Three failed offline exports](offline-loader-attempts.json) are preserved. After option placement and view/preset construction were corrected, r3 still exited -1 without a CSV. The accompanying missing `MyPresets.wpaPresets` warning initially obscured the actual fault.

An [installed-profile control](loader-control.json) succeeded with the same missing-file warning and produced an [80-byte header-only CSV](loader-control-header.csv). A stronger [single-variable control](loader-guid-control.json) then changed only r3's `AnalysisView.Name` from `main-vk-0` to a valid GUID. With the same symbol options, ETL and measurement window, this profile exited 0. **The invalid view identifier caused r3's loader failure; the missing presets file was unnecessary.**

The successful profile initially exported a collapsed 302-byte CPU table. This is loader evidence only: it cannot identify PFIFO or establish CPU, wait or GPU costs. The later narrow export resolved thread-level extraction as described above. No additional gameplay or baseline change occurred.

The earlier guarded WPA startup/close preserved all six existing settings-file hashes and added one tool-generated optimization file. No preset was fabricated or overwritten. That initialization did not resolve the fault; the profile correction did.

A subsequent [raw-row export](raw-export-failure.json) returned exit code 0 but logged an export error and stopped mid-row after 7,804 complete records. Its totals are excluded. Export validation must inspect stderr and CSV completeness as well as the process exit code; one intact source-exclusive record established thread identity, while all r6 totals remain excluded. The clean narrow export supplies the quantitative results.
