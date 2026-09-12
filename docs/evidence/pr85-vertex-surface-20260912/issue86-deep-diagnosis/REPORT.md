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

## Where the fence time goes

Two further trace-only builds on the **same product tree** used Vulkan timestamp queries to separate the GPU timeline from the host wait. The two-timestamp build used patch SHA-256 `4908239a5df9e82e0a40a42b39b77dc705bb5df7a8da22cc85a13fe1b5191a9b` and executable SHA-256 `c3d91377fa6bf639fcb803750c63b2926edc12240509329564acf494c6ab09c9`. Its 233-frame measured window recorded 2.685 s of `STALLED` fence wait and 2.580 s from the start of the auxiliary GPU command buffer to the end of the main command buffer. The per-frame series correlated at 0.993. The four-timestamp build used patch SHA-256 `a5babd1f62d807cab7c7c894d883e144107391bc1bc3cdffd7ee358b673aeb4b` and executable SHA-256 `9af9bcc4a6f5c46893bcfe287ffbf0cbfee6506a446918054b930ac2fb5195eb` to split that GPU interval. Both used the same Windows O2/full-LTO/x86-v3 DWARF/assert profile and the same fixed snapshot/input procedure. Their final-image and disk-cleanup checks passed. They are diagnostic builds, not performance candidates.

| Four-timestamp Vulkan window, 230 guest frames | Sum | Median per frame | Share of GPU batch |
| --- | ---: | ---: | ---: |
| Host `STALLED` fence wait | 2.722 s | 11.216 ms | — |
| GPU batch elapsed, auxiliary start to main end | 2.616 s | 10.799 ms | 100% |
| Auxiliary staging/flush commands | 0.111 s | 0.328 ms | 4.2% |
| Auxiliary-to-main handoff | 0.026 s | 0.039 ms | 1.0% |
| Main graphics command buffer | **2.479 s** | **10.404 ms** | **94.8%** |

The GPU batch spans **96.1% of the host fence-wait total** in both diagnostic builds. The dominant elapsed interval is inside the submitted main graphics command buffer, not CPU-side report serialization, auxiliary staging, or pre-execution queue delay. GPU timestamps measure elapsed time between commands; they do not by themselves distinguish shader execution from resource hazards or other waits *inside* the main command buffer. Removing only the host fence call would move or violate the guest-visible synchronization. The next profile should attribute main-buffer time by draw/pass or pipeline activity before selecting a product optimization. [Two-timestamp summary](gpu-batch-summary.json), [four-timestamp summary](gpu-phase-summary.json), and [run records](results/) retain the compact evidence; the raw counter streams remain private on the test host and are identified by SHA-256 in the summaries. The reusable [counter summarizer](../../../../utils/summarize_vk_wait_reasons.py) now reads these optional GPU fields while continuing to support older counter schemas.

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

Private read-only inspection of those guest instruction sites showed a caller that repeatedly invokes the helper at `0x00336940`, compares its result to a fixed status code, and branches back while that status persists. A second, extended read-only inspection of the same helper showed that it tests the fourth word of a 16-byte record against `-1`. When that word is no longer `-1`, it copies the third word to the caller's result output and, if requested, copies the first two words to a timestamp output. Xemu's `pgraph_write_zpass_pixel_cnt_report()` writes exactly that layout: timestamp at bytes 0–7, result at 8–11, completion word at 12–15. The caller passes index zero and retries while the helper reports the pending status. This is **strong source-level evidence that the guest polls a Z-pass report result during the Vulkan fence wait**, rather than an unrelated status API. A dynamic address match between the guest record and the queued report DMA destination has not yet been captured, so the identity is not asserted as fully proven. The guest code bytes and register dump remain private and are not included in this repository. [Compact counts](metrics.json), the exact [PC-run result](results/vulkan-guest-pc.json), and the [extended-inspection run result](results/vulkan-guest-report-layout.json) preserve the reproducible finding.

A further same-executable QMP `info jit` sample, six seconds apart during gameplay, showed TB invalidations rising 4,102 → 7,508 and live TB count 22,355 → 24,667; zero full TB flushes. The TB hash reported 1.016 → 1.025 average buckets per chain. This does not prove that the known same-page invalidation policy in [closed #42](https://github.com/Mainkill1/xemu/issues/42) caused Morrowind's lookup load. Reopen that separate optimization only with its required native counterexample and controls.

## Next causal check

Capture the queued report DMA destination and dynamically match it to the guest record read by the helper. Align the guest's first completion-word read with GPU submission and fence completion. The helper's observed polling pattern makes early publication of a zero-query report particularly risky: the report can be serving as a GPU-completion fence even when its count is zero. The timestamp split now directs the next profile into the **main graphics command buffer**: identify expensive draws/passes, overdraw, shader cost, and internal barriers, then assess an isolated reduction or earlier ordered submission. Measure total guest work, output, frame tails, and both renderers before treating a change as a win. The same trace makes translated-block lookup a separate profile target, but avoid optimizing it as an independent cache problem until its relationship to guest waiting is understood.

The compact [metrics](metrics.json), [ETW thread summary](thread-summary.json), [TCG samples](tcg-stats.json), and exact [per-run result records](results/) contain the numerical evidence. No copyrighted game data, private disk, raw ETL, or local test configuration is published here.
