# PR14 texture lookup and cubemap attribution

Research PR #67 extended its opt-in Vulkan telemetry without changing rendering
decisions. The exact Windows Release build used source
`c16cc79a863cf8496645956571c807000822edad`, tree
`bb1cbdf220a3953ea71cc5805197af1d9ff706c6`, and executable SHA-256
`4eb67b28b5b80a4a849962464239e733e33145245973f25a75889810ca82c2c0`.
The focused texture-layout unit executable SHA-256 was
`fbddd855b8fa2d9846d561b863a9a61189e47c1636b34e49e7f1a8693c95a440`;
all 7 tests passed on Windows.

Both repeat cells used the established PGR2 snapshot, Vulkan, B-3 input route,
a three-second warmup, a 60-second measurement, and all optional performance
controls disabled. ETL/WPR tracing was disabled. These are diagnostic timings,
so they cannot qualify PR #14 performance.

## Frame result

Positive Improvement % is favorable. Interval metrics are `+bad`. No
Improvement % is assigned here because both rows use the same instrumented
build and the prior uninstrumented PR #14 comparison remains the performance
gate.

| Metric | Raw + | Repeat 1 | Repeat 2 | Use |
| --- | --- | ---: | ---: | --- |
| Measured guest frames | `+good` | 1,728 | 1,722 | Admission |
| Average interval | `+bad` | 34.705 ms | 34.827 ms | Diagnostic |
| p95 | `+bad` | 41.711 ms | 42.053 ms | Diagnostic |
| p99 | `+bad` | 48.022 ms | 46.346 ms | Diagnostic |
| Maximum | `+bad` | 72.015 ms | 71.640 ms | Diagnostic |
| Stalls above 75 ms | `+bad` | 0 | 0 | Diagnostic |

Both cells completed gameplay admission and cleanup. Afterward, the host had
zero xemu/PresentMon/trace processes and zero disposable private HDDs.

## Path frequency and cost

| Measured result per guest frame | Repeat 1 | Repeat 2 | Finding |
| --- | ---: | ---: | --- |
| Texture creation/key hashes | 9,288.218 | 9,288.382 | Hot path |
| Texture-key hash CPU | 0.278 ms | 0.280 ms | Too small to explain the tail gap |
| Texture-cache lookup CPU | 0.423 ms | 0.423 ms | Too small to explain the tail gap |
| Cache misses | 0.025 | 0.026 | 44 misses in each complete measured window |
| Saturated-cache lookups | 0 | 0 | Saturated LRU free-node scan absent |
| Saturated-cache misses | 0 | 0 | Saturated LRU miss hypothesis rejected |
| Cubemap preparations | 451.126 | 451.161 | Cubemaps are active |
| Same-level cubemap preparations | 451.126 | 451.161 | Every cubemap used `storage_levels == levels` |
| Cubemap length CPU | 0.012 ms | 0.013 ms | Too small |
| Cubemap layout CPU | 0.067 ms | 0.068 ms | Too small |
| Cubemap upload CPU | 0.085 ms | 0.085 ms | Too small |
| Peak summed focused texture CPU | 1.183 ms | 1.057 ms | Below the 10–11 ms adverse tail gap |

Both full process lifetimes and measured windows again recorded zero clamped
cubemap preparations. PR #14's new stored-level behavior requires
`storage_levels > levels`; that condition did not execute on this PGR2 route.

## Repeatable slow frame

| Build / run | Guest frame | Interval | `pipeline_prepare` CPU | `draw_flush` CPU | Focused texture CPU | Native BC uploads |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Previous main, earlier schema-v5 control | 671 | 68.576 ms | 42.966 ms | 53.549 ms | unavailable | 4 |
| PR #14, earlier schema-v5 control | 673 | 66.080 ms | 41.867 ms | 51.647 ms | unavailable | 4 |
| PR #67 repeat 1 | 667 | 72.015 ms | 42.506 ms | 53.220 ms | 0.837 ms | 4 |
| PR #67 repeat 2 | 669 | 71.640 ms | 45.977 ms | 55.811 ms | 0.939 ms | 4 |

The repeatable slow frame is dominated by `create_pipeline()` inside the
`pipeline_prepare` region. It exists in previous main as well as PR #14, and
the measured texture-key, cache, cubemap-layout, and upload work accounts for
less than 1 ms in the two new slow frames. The remaining attribution boundary
is shader binding, pipeline-key lookup, and Vulkan pipeline creation inside
`create_pipeline()`.

## Decision

PR #14 remains **HOLD** because its ordinary uninstrumented phase-peak median
still fails at -20.78% Improvement. This diagnostic rejects clamped cubemap
storage, texture key hashing, cache saturation, and measured cubemap layout as
the source of that 10–11 ms difference. It also identifies the recurring
workload spike separately: pipeline preparation takes about 42–46 ms during
the event and was already present in previous main.

The next PR #67 counter build must divide `create_pipeline()` into shader bind,
pipeline cache lookup, and `vkCreateGraphicsPipelines()` time. After that, a
one-change uninstrumented A/B can separate the OpenGL correctness repair from
the Vulkan/shared-layout integration. No PR #14 speed claim is supported now.

`summary.json` contains sanitized run identities, totals, per-frame means,
worst-frame attribution, and the earlier control rows. Raw multi-megabyte
JSONL, screenshots, and local paths remain outside Git history.
