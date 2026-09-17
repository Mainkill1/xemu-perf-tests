# Recovered r2 QPC-only analysis

## Verdict and boundary

**ADMISSIBLE ONLY AS A SETUP-INCLUSIVE, WHOLE-QPC-SPAN OBSERVATION.** This is not the runner's 20-second interval, a baseline comparison, an OpenGL comparison, displayed FPS, or an ETL join.

The input is the complete `vulkan-perf.jsonl` from exact candidate `f16292b472e6bf5aa9d4448cbbf352bc13131b06` (tree `f5cac543ac34e50f4b48f6f4b9799dfbd3bd5e8f`), SHA-256 `4abffea5aa8c017e553d888eb3149e2c77e84389ed571ece6ad6b83b3aafb3da`. It contains one schema, 650 frame records, and one complete terminal record with no drop, overflow, or incomplete flag.

`pgraph_vk_perf_frame` snapshots counters and the QPC-derived timestamp and then resets the counters (`perf.c:306-343,448-499`). It runs after the flip-stall finish at each guest flip (`renderer.c:147-151`). Record 1 therefore includes an unknown prefix from logger initialization to the first captured frame. This analysis excludes record 1 and sums records 2 through 650, whose 649 counter blocks align with the 649 consecutive timestamp intervals from record 1 at `621489515105` us through record 650 at `621516544816` us. The exact observed span is **27,029,711 us**.

The wrapper lost both UTC/QPC anchors after normal shutdown, so this interval cannot be aligned with the runner's UTC timestamps. It includes snapshot/game setup before the 20-second measurement and shutdown activity after it. The script performs no extrapolation.

## Sampling semantics

The schema reports `duration_sampling.mode = all`. In this mode every finish submission is timed (`perf.c:184-195`), and the selected records independently satisfy `submit_count == timed_submit_count == fence_wait_count` for every finish reason. A finish *call* can exceed submissions because `pgraph_vk_finish` records the call before testing `in_command_buffer`; only the latter branch submits and waits (`draw.c:1286-1295,1343-1380`).

Single-time commands always measure their `vkQueueSubmit` and `vkQueueWaitIdle` calls while telemetry is enabled (`command.c:89-119`) and unconditionally add one timed submit and wait to their caller bucket (`perf.c:227-249`). Their selected-record count equalities also hold. Thus the durations below are complete for the instrumented calls in this bounded interval; “sampled” survives only in field names.

The fields called CPU regions use monotonic elapsed timestamps around their named functions, including waits; they are not on-CPU measurements and are not exclusive. In particular, `draw_flush` wraps `pgraph_vk_flush_draw` (`draw.c:1686-1690`), which reaches `begin_pre_draw`; that function contains `pipeline_prepare` and `update_descriptor_sets` (`draw.c:1457-1492`), and pipeline creation calls `bind_textures` (`draw.c:763-771`). Their durations must remain separate and must not be summed as CPU occupancy.

## Observed totals

The finish path issued 2,476 `vkQueueSubmit`/`vkWaitForFences` pairs with 8,485,917 us accumulated fence-wait duration. The single-time path issued 1,577 `vkQueueSubmit`/`vkQueueWaitIdle` pairs with 719,976 us accumulated queue-idle duration. Together the instrumented paths contain 4,053 queue-submit calls, 6,529 submit infos, 6,529 command buffers, 132,185 us of measured submit-call CPU duration, and 9,205,893 us of measured wait duration.

| Finish reason | Calls | Submits / fence waits | Submit CPU us | Fence-wait us | Share of all tracked wait |
|---|---:|---:|---:|---:|---:|
| `need_buffer_space` | 650 | 650 | 32,831 | 6,491,212 | 70.51% |
| `stalled` | 649 | 649 | 25,234 | 1,000,323 | 10.87% |
| `surface_down` | 520 | 519 | 17,712 | 553,831 | 6.02% |
| `flip_stall` | 649 | 648 | 20,688 | 438,779 | 4.77% |
| `surface_create` | 11 | 10 | 214 | 1,772 | 0.02% |

The other five finish reasons have zero calls. Reason totals identify the reason passed to `pgraph_vk_finish`; they do not identify which source call site supplied a shared reason.

| Single-time caller | Queue submits / idle waits | Submit CPU us | Queue-idle us |
|---|---:|---:|---:|
| `display_render` | 1,036 | 24,254 | 492,395 |
| `surface_download` | 519 | 10,578 | 218,965 |
| `surface_create` | 11 | 440 | 5,423 |
| `surface_upload` | 11 | 234 | 3,193 |

The other three single-time callers have zero calls.

The aligned timestamp and tracked-wait distributions use nearest-rank percentiles:

| Per-record quantity | Mean ms | P50 ms | P95 ms | P99 ms | Maximum ms |
|---|---:|---:|---:|---:|---:|
| Consecutive telemetry timestamp interval | 41.648 | 41.045 | 49.953 | 57.897 | 153.045 |
| Sum of instrumented finish and single-time waits | 14.185 | 13.809 | 20.053 | 22.919 | 39.100 |

These are telemetry-interval tails. They are not a displayed-frame metric, and the 153.045 ms maximum cannot be assigned to the runner's measurement phase without the lost clock anchors.

The interval staged **4,571,768,216 bytes** across instrumented submissions. Vertex staging accounts for **1,937,465,344 bytes in 220,885 copies**, an observed mean of 8,771.376 bytes per copy. There were zero vertex-staging capacity growths and zero vertex-staging fallback finishes. Native block-compressed uploads account for 17 uploads and 360,336 source/staged bytes with 37 us preparation time; decoded block-compressed uploads are zero.

## Nonexclusive host elapsed regions

| Region | Calls | Total elapsed us | Mean us/call | Per-record P95 us | Per-record P99 us | Per-record max us |
|---|---:|---:|---:|---:|---:|---:|
| `draw_flush` | 748,235 | 11,120,007 | 14.862 | 22,085 | 24,821 | 54,871 |
| `update_descriptor_sets` | 748,235 | 6,879,830 | 9.195 | 15,334 | 17,322 | 28,879 |
| `pipeline_prepare` | 748,235 | 1,506,400 | 2.013 | 2,375 | 2,542 | 37,880 |
| `bind_textures` | 748,235 | 415,268 | 0.555 | 735 | 770 | 1,295 |
| `draw_begin_surface_update` | 748,235 | 92,887 | 0.124 | 154 | 163 | 7,846 |
| `texture_upload` | 23 | 184 | 8.000 | 0 | 0 | 109 |

The `update_descriptor_sets` region includes the `pgraph_vk_finish(NEED_BUFFER_SPACE)` call inside the descriptor/UBO capacity branch (`shaders.c:229-241`). Across all 649 selected records, its duration is at least the `need_buffer_space` wait duration. The region totals 6,879,830 us; the capacity-wait total is 6,491,212 us (94.35% of that duration). The per-record difference is only 528–1,172 us, and their per-record Pearson correlation is 0.999821. Together with the source, this strongly points to that function; it remains an inference until call-site counters distinguish its triggers. It also means the 6.88-second region is not a separate CPU bottleneck.

The existing counters still cannot distinguish the two booleans in that branch: exhaustion of the fixed 1,024-entry descriptor-set array (`renderer.h:526`, `shaders.c:233-234`) versus exhaustion of the 8 MiB uniform staging buffer (`buffer.c:320-326`, `shaders.c:219-231`). Nor does the region's 748,235 invocation count prove 748,235 `vkUpdateDescriptorSets` API calls, because the function can return at `shaders.c:211-214`.

## Supported next source seams

1. **Disambiguate the descriptor-set and UBO-capacity booleans at `shaders.c:229-241`.** This is now the smallest decisive diagnostic: record separate counts for descriptor exhaustion, UBO exhaustion, and both. If descriptor capacity dominates, the dependency-preserving bounded candidate is to provide enough fresh descriptor sets to reach an existing natural fence-completing finish, without overwriting or reusing a set still referenced by the active command buffer. If UBO capacity dominates, grow the paired uniform/staging allocation before reuse while retaining the same submit/fence dependency. Removing `vkWaitForFences`, resetting an in-use descriptor set, or overwriting an in-flight UBO is not supported by these numbers.
2. **Only after the drain is handled, split `pgraph_vk_flush_draw` into exclusive CPU segments.** Its 11,120,007 us includes the 6,491,212-us nested wait as well as the nested pipeline, texture, and descriptor regions. The current total supports a narrower exclusive-timing diagnostic, not a descriptor-write or draw-path optimization.

The zero `vertex_buffer_dirty` finish count and zero decoded-BC uploads rule out those historical paths for this interval. The large vertex copy/byte totals lack direct copy-duration attribution, and zero staging growth/fallback events provide no basis for changing that path from this packet.

## Reproduction

From this evidence directory:

```text
python3 analyze-r2.py \
  --input vulkan-perf.jsonl \
  --output summary.json
```

Analyzer SHA-256: `e919564a714797ac2e4b616d18f8ad7c5dce0a88f1da9cf06a9adcf2284e9190`. Generated numeric summary SHA-256: `a4a3cccb00245e30a9073822f40891bdb620edd9093fb188b2cb4bb384c11187`.
