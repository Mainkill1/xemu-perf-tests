# Main dispatcher/state attribution

**Both diagnostic Morrowind cells completed. Flag and FPU-control helpers do not explain the frequent NULL dispatcher returns.** This narrows the next investigation to the actual returning guest paths. It does not establish an optimization or a gameplay speedup.

Base main `bd1fecb93353272dda2a810991e28945de35b665`; probe `6008181a51a454029af768dda3a08fd7cb46829a`; tree `2fea3f4cf196a7f2f6f779bffdfa6174d374c786`. [Draft xemu #54](https://github.com/Mainkill1/xemu/pull/54) was updated before testing. This probe includes merged APU prerequisite #53. Previous probe failures and measurements remain in the [earlier report](../main-cause-20260909/REPORT.md).

| Measured diagnostic event | Vulkan | OpenGL |
| --- | ---: | ---: |
| NULL dispatcher returns/s | 10,487,977 | 3,030,055 |
| Helper cache misses requiring translation/s | 122 | 135 |
| FPU control loads/s | 3,009 | 4,176 |
| FPU precision-bit changes/s | 0 | 0 |
| EFLAGS helper writes/s | 1,651 | 1,768 |
| Writes changing interrupt-enable state/s | 1,491 | 1,600 |
| Writes changing measured TB-key flags/s | 0 | 0 |
| Graphics dirty-tracking entries visited/s | 22,457,980 | 15,719,510 |
| Graphics scans arming no new entry | 17.80% | 22.58% |
| Helper direct-cache hit rate | 93.19% | 92.68% |

Rates use per-thread cumulative differences between the first and last samples inside each recorded measurement window. Vulkan vCPU coverage is 19.002181 seconds; graphics coverage 19.480320 seconds. OpenGL coverage is 19.015170 and 18.250210 seconds respectively. Periodic samples do not cover the entire 20-second window. All lookup outcome/secondary-table accounting checks pass. The temporary counters are cumulative TLS writes with periodic output; instrumentation affects rates and guest throughput.

The state-helper counts are far below the observed returns, rejecting the hypothesis that these helpers dominate dispatcher entries. A future guest-address sample must identify the responsible path before changing chaining or interrupt eligibility. Source already contains static-state helper lookup and empty-MMU skipping. A zero-arm scan alone is insufficient justification for skipping dirty tracking under concurrent writes.

## Validation and limits

Build passed with the retained O2/LTO toolchain/options, symbols and assertions enabled. Executable SHA-256 `78d826d011890d39fcc22eedc575444801b383b2c1d7c473a062f2083d2208b0`. One unchanged 20-second snapshot recipe per renderer completed, 54 counter records per renderer were retained, and both final scenes were manually inspected. They show the expected outdoor bridge/buildings and crosshair without pause/reconnect overlays. This is not an independent pixel oracle or audio-quality qualification. Private disks were removed, no owned processes remained, and the seed hash was unchanged.

Instrumented cadence/p95/p99: Vulkan 15.382/s, 171.872/193.542 ms; OpenGL 21.243/s, 143.225/178.553 ms. These are NV2A display-write cadence proxies, not rendered FPS and not a baseline/candidate performance comparison. No CPU/GPU/RAM/VRAM/power telemetry, full XISO, PGR2 or new guest suite was run. The already tested, uninstrumented APU executable remains the new main baseline; no baseline rebuild occurred.

[Manifest](manifest.json), [exact diagnostic patch](diagnostic.patch), [Vulkan run](vulkan-run.json), [OpenGL run](opengl-run.json), [Vulkan counters](vulkan-counters.jsonl), [OpenGL counters](opengl-counters.jsonl), [Vulkan summary](vulkan-summary.json), [OpenGL summary](opengl-summary.json).

Regenerate summaries using `utils/analyze_cause_counters.py RECORDS --start-utc-us START --end-utc-us END --output OUTPUT`; the exact integer UTC bounds are in each summary. The existing analyzer needs no schema change for the additional integer counters. Model/analyzer checks are separate from the native captures. No game assets, private configuration, full application logs or local paths are published.
