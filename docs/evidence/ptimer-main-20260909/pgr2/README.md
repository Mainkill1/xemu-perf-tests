# PGR2 retained-baseline and PTIMER candidate comparison

This packet compares one 60-second retained-baseline observation with one 60-second PR #59 candidate observation for each PGR2 mode and renderer. All four candidate capture and lifecycle gates completed, but the performance disposition is **acceptance held**: Snapshot OpenGL mean, p95, and p99 guest-frame intervals were 7.32%, 7.31%, and 14.45% higher, and Snapshot Vulkan p99 was 2.46% higher. These are unfavorable observations above the 2% threshold. A single non-interleaved pair cannot establish causation or qualify the candidate; repeatable fixed-work evidence remains required.

## Tested identities

| Role | Reference | Tested source / tree | Tested executable SHA-256 |
| --- | --- | --- | --- |
| Fixed baseline | `baseline/cycle-01-start` at `9f618d6d8c4c446ef023955f3d4de22f661f61a4`; product source `bd1fecb93353272dda2a810991e28945de35b665` | `c17591d59c270b352b72e648f5ed65e4b2a3e77e` / `6824a5aa4d9ca288ac96092dc9244684e995b08d` | `3489fdcc593e942b92a612bf35a98f509ff0907e3370e1e5f45f2972d83fb16b` |
| PTIMER candidate | PR #59 | `8da17c3e68c525475f55f3e9d1ddda0ad9c11d5b` / `20c4d0a4551a878485370329e9856766dca7c752` | `6fb3dcdd998e67c18223fd4b6f0bfb74542bdc0b282d95776c5a27c8f8be7ab6` |

The normalized baseline reference, its product source, and the source that produced the retained executable are distinct identities. The comparison reuses the retained executable; it does not claim that `9f618d6d` was rebuilt.

## Snapshot

Guest interval metrics are milliseconds; lower is better. Each `Δ` is `100 × (candidate − baseline) / baseline`.

| Renderer | Metric | Retained baseline | Candidate | Δ |
| --- | --- | ---: | ---: | ---: |
| Vulkan | Mean guest interval | 34.483841 ms | 34.627262 ms | +0.42% |
| Vulkan | p95 guest interval | 40.910 ms | 41.338 ms | +1.05% |
| Vulkan | p99 guest interval | 45.186 ms | 46.296 ms | **+2.46%** |
| Vulkan | Guest flip-log cadence | 29.012075/s | 28.869237/s | -0.49% |
| OpenGL | Mean guest interval | 35.122224 ms | 37.694658 ms | **+7.32%** |
| OpenGL | p95 guest interval | 42.308 ms | 45.400 ms | **+7.31%** |
| OpenGL | p99 guest interval | 46.086 ms | 52.745 ms | **+14.45%** |
| OpenGL | Guest flip-log cadence | 28.519344/s | 26.538510/s | -6.95% |

| Renderer | Guest frames baseline / candidate | PresentMon samples baseline / candidate | Capture/lifecycle gate |
| --- | ---: | ---: | --- |
| Vulkan | 1,740 / 1,732 | 3,597 / 3,594 | Complete |
| OpenGL | 1,708 / 1,592 | 3,598 / 3,596 | Complete |

## FreshBoot

| Renderer | Metric | Retained baseline | Candidate | Δ |
| --- | --- | ---: | ---: | ---: |
| Vulkan | Mean guest interval | 33.333301 ms | 33.342577 ms | +0.03% |
| Vulkan | p95 guest interval | 33.412 ms | 33.554 ms | +0.42% |
| Vulkan | p99 guest interval | 34.497 ms | 34.341 ms | -0.45% |
| Vulkan | Guest flip-log cadence | 29.999982/s | 29.999976/s | -0.00% |
| OpenGL | Mean guest interval | 33.342601 ms | 33.333264 ms | -0.03% |
| OpenGL | p95 guest interval | 33.822 ms | 33.740 ms | -0.24% |
| OpenGL | p99 guest interval | 36.059 ms | 34.440 ms | -4.49% |
| OpenGL | Guest flip-log cadence | 29.990947/s | 29.999966/s | +0.03% |

| Renderer | Guest frames baseline / candidate | PresentMon samples baseline / candidate | Capture/lifecycle gate |
| --- | ---: | ---: | --- |
| Vulkan | 1,801 / 1,801 | 3,595 / 3,595 | Complete |
| OpenGL | 1,800 / 1,802 | 3,596 / 3,597 | Complete |

`Guest flip-log cadence` comes from xemu's logged guest flip events. It is **not rendered FPS**. PresentMon counts show that host-presentation telemetry was present; this packet does not use them as a performance metric. Raw NVIDIA CSVs and sealed ETLs exist, but no reviewed same-window CPU or GPU summary was produced, so CPU/GPU comparisons are omitted.

## Gates and scope

Every retained-baseline and candidate cell reports complete functional and measurement status, exact executable and renderer identity, nonempty guest/PresentMon samples, zero focus loss, zero not-responding samples, zero ETW lost events or buffers, zero guest stalls at the 75 ms threshold, complete private-HDD cleanup, and unchanged source-seed hashes. Snapshot used a 3-second warmup; FreshBoot used its recorded navigation sequence, 10-second BIOS delay, and 30-second warmup. All cells used a 60-second steady-state capture, surface scale 1, CpuScheduler/SteadyState tracing, disabled Vulkan performance telemetry, and renderer-specific pinned configuration.

Offline image review found a stationary race scene and HUD at 0 MPH with no pause overlay. Snapshot showed Position 6/6, Target 2nd, and Lap 1/3; FreshBoot showed the start grid and dashed lap time. This supports static scene and input readiness. It does not prove sustained driving, race progression, a causal performance effect, or a 2% acceptance result.

## Preserved setup failures

| Scope | Failure | Workload started | Disposition |
| --- | --- | ---: | --- |
| Retained-baseline FreshBoot | Initial SSH command-path quoting failure | No | Preserved; corrected invocation completed the intended first valid Vulkan cell |
| Candidate Snapshot Vulkan | Client-side quoting expanded remote PowerShell variables before dispatcher parsing | No | Preserved; a corrected no-game quote control passed before the intended first valid cell |

No valid workload cell failed. These setup failures are infrastructure evidence and are not benchmark observations. Their hashes, the corrected quote-control hash, exact per-cell receipts, lifecycle hashes, inputs, and full-precision values are in [comparison.json](comparison.json).

The unfavorable Snapshot observations keep candidate acceptance held. The FreshBoot rows contain no unfavorable interval increase above 2%, but one observation per identity cannot establish a distribution or override the Snapshot result. This packet does not update the baseline.
