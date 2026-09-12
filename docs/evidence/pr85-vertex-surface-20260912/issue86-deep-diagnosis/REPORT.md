# Morrowind snapshot: Vulkan report fence and guest CPU attribution

**Diagnostic result; no performance fix or merge qualification.** This extends [xemu issue #86](https://github.com/Mainkill1/xemu/issues/86) and the [PR #85/#83 evidence](../REPORT.md). The tested product tree is the draft #83 head `5717357917abdd92e7c344d9e4f1b36b6fa61afa` (tree `b0de7c5381392859e82c06a421fd56ac963ae39e`), stacked on draft #85. A trace-only patch (`32dabaa5f6a0a305ebea581ce496d0125a00c17096b5cd2e267914ebfc7ad82f`) produced executable SHA-256 `7f50e2225c8f124f334695df45c96cd503cdd5ba37d0e667a60a06ef7799999e`. The Windows build used the existing O2/full-LTO/x86-v3 DWARF/assert profile. The selected Vulkan device was an NVIDIA RTX 3070 Ti Laptop GPU. No product behavior was changed by the added trace events.

All runs used the pinned Morrowind outdoor snapshot, fixed Start/B input sequence, and a 10-second measurement window. The metric is **NV2A guest display-write cadence, not presented FPS**. Every result reached gameplay, passed the existing final-image oracle, preserved the immutable disk seed, deleted its private disk, and closed xemu. The one OpenGL cell is a same-day, same-executable diagnostic comparison, not a counterbalanced performance qualification.

| Run | Renderer | Display writes/s | p95 interval | p99 interval |
| --- | --- | ---: | ---: | ---: |
| Report trace | Vulkan | 23.874 | 51.241 ms | 59.017 ms |
| CPU ETW | Vulkan | 23.387 | 51.722 ms | 56.186 ms |
| TCG stats | Vulkan | 23.467 | 51.577 ms | 64.855 ms |
| Renderer comparison | OpenGL | **34.664** | 35.483 ms | 41.376 ms |

OpenGL's observed progress rate is 45.2% higher than the report-trace Vulkan cell. The sample interval is about 28.8 ms for OpenGL versus 41.9 ms for Vulkan. Instrumentation, execution order, and short duration prevent calling that a qualified performance delta.

## What the Vulkan report path actually does

The trace recorded 418 `STALLED` report retirements over the full launch and 238 inside its measured window. **Every one** had two queued entries, one clear, zero completed occlusion queries, no active query, and `new_query_needed=1`. The queue sequence is a clear followed by a report. The result-read function performed no `vkGetQueryPoolResults` call in this state: measured result-read time was 0 µs median and at most 1 µs. Therefore the long `STALLED` time is the command-buffer fence, not query-result retrieval.

| Measured 10-second Vulkan window | Result |
| --- | ---: |
| `STALLED` submits | 238, about one per guest display write |
| Median / p95 `STALLED` fence wait | **10.587 / 16.756 ms** |
| Sum of `STALLED` fence waits | **2.696 seconds** |
| Median `FLIP_STALL` fence wait | 1.229 ms |
| Median total sampled finish-fence wait | 11.730 ms/frame |

Source ordering explains the wait. `pfifo_thread()` calls `pgraph_process_pending_reports()` after processing the FIFO. Vulkan sees FIFO GET equal PUT, an active command buffer, and a nonempty report queue; `pgraph_vk_finish(... STALLED)` submits the recorded work and waits for its fence before the report serializer runs. OpenGL's zero-query report path does not call `glGetQueryObjectuiv()` and processes its queued report directly. This is a backend behavior difference. The trace does **not** establish that publishing the Vulkan report before GPU completion would preserve guest semantics; Morrowind may use the report as a GPU completion fence even when its occlusion count is zero.

## CPU scheduling and code samples

A separate 10-second Vulkan xperf capture covered the same snapshot and exact executable. The ETL reported **zero lost buffers and zero lost events**. The raw 668,991,488-byte ETL remains retained in the test environment, SHA-256 `9a5ef50fe716c2b5d49372a480a33985bb7a81a9a9a93ab8718b780dd5248272`. Only the measured window was aggregated; derived large CSVs were discarded after extraction. This trace is for attribution, not performance acceptance.

| Thread identified by sampled code | Running in 10 s | Waiting | Scheduler-ready | Main sample evidence |
| --- | ---: | ---: | ---: | --- |
| Guest CPU/TCG | **9.865 s** | 0.132 s | 0.009 s | 4,671 of 9,738 samples (48.0%) in `lookup_tb_ptr_common()` / `helper_lookup_tb_ptr_i32()` |
| PFIFO/PGRAPH | 2.073 s | 7.896 s | 0.037 s | `pfifo_thread()`, PGRAPH methods, Vulkan preparation, and driver calls |
| APU/DSP | 1.702 s | 8.236 s | 0.068 s | DSP execution and `se_frame()` |

These thread durations overlap across CPU cores; they must not be added as a frame-time budget. The host did not leave the guest CPU thread scheduler-ready for long periods: it ran for 98.6% of the window. The exact PE's symbol table maps the two dominant sampled functions to the translated-block lookup path. This establishes where CPU cycles were spent, **not** why the guest made those branch transitions.

## Guest retry loop during report stalls

One further same-executable Vulkan run sampled guest EIP through QMP 120 times during gameplay and aligned each sample to the trace timestamp of the most recent `STALLED` report event. Samples within 10 ms of a stall were concentrated at two guest addresses: **22/26** were at `0x00336940` or `0x000B2492`. Of the **94** samples more than 10 ms after a stall, only **2** were at those addresses. The run reached 23.767 guest display writes/s, p99 58.576 ms, with valid image and cleanup; QMP sampling makes it diagnostic only.

Private read-only inspection of those guest instruction sites showed a caller that repeatedly invokes the helper at `0x00336940`, compares its result to a fixed status code, and branches back while that status persists. This confirms a **guest retry loop temporally linked to Vulkan report waits**. It does not yet identify the helper's underlying status source or prove that the loop reads the report DMA completion word. The guest code bytes and register dump remain private and are not included in this repository. [Compact counts](metrics.json) and the exact [PC-run result](results/vulkan-guest-pc.json) preserve the reproducible finding.

A further same-executable QMP `info jit` sample, six seconds apart during gameplay, showed TB invalidations rising 4,102 → 7,508 and live TB count 22,355 → 24,667; zero full TB flushes. The TB hash reported 1.016 → 1.025 average buckets per chain. This does not prove that the known same-page invalidation policy in [closed #42](https://github.com/Mainkill1/xemu/issues/42) caused Morrowind's lookup load. Reopen that separate optimization only with its required native counterexample and controls.

## Next causal check

Capture the DMA report destination and the guest's first read of its completion word. Determine which status source the correlated guest helper checks, then align that read with GPU submission and fence completion. If the guest polls the report immediately, simply retiring zero-query reports early would violate the fence contract; a correct change would need ordered, asynchronous completion or less GPU work before the fence. If it reads later, test deferred retirement with a read-time fallback. In either case, measure total guest work, output, frame tails, and both renderers before treating the change as a win. The same trace makes translated-block lookup a separate profile target, but avoid optimizing it as an independent cache problem until its relationship to guest waiting is understood.

The compact [metrics](metrics.json), [ETW thread summary](thread-summary.json), [TCG samples](tcg-stats.json), and exact [per-run result records](results/) contain the numerical evidence. No copyrighted game data, private disk, raw ETL, or local test configuration is published here.
