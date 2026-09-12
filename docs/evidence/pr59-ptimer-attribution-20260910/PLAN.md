# PR59 PTIMER attribution: declared repeat plan

Status: investigation; no product change, merge, or baseline advancement.

This follows [the reviewed #40 handoff](https://github.com/Mainkill1/xemu/issues/40#issuecomment-5626660345). The first question is whether the earlier PGR2 OpenGL snapshot slowdown repeats when the retained binaries run close together in alternating order. Vulkan is a control. This is diagnostic reproduction, not full performance acceptance.

## Pinned comparison

| Identity | Retained reference B | Combined PTIMER candidate AM |
| --- | --- | --- |
| Source commit | `c17591d59c270b352b72e648f5ed65e4b2a3e77e` | `8da17c3e68c525475f55f3e9d1ddda0ad9c11d5b` |
| Tree | `6824a5aa4d9ca288ac96092dc9244684e995b08d` | `20c4d0a4551a878485370329e9856766dca7c752` |
| Executable SHA-256 | `3489fdcc593e942b92a612bf35a98f509ff0907e3370e1e5f45f2972d83fb16b` | `6fb3dcdd998e67c18223fd4b6f0bfb74542bdc0b282d95776c5a27c8f8be7ab6` |

B is tree-identical to PR59's original construction base `bd1fecb93353272dda2a810991e28945de35b665`. The canonical baseline branch is `9f618d6d8c4c446ef023955f3d4de22f661f61a4`. Current main is `e18ba8d6274cf227cc9e5ae1b5684f28ed911a99`; this repeat does **not** measure the incremental effect of applying PR59 to that later main. Existing binaries are reused.

## Before measurement

One excluded 10-second readiness pilot per build and renderer, ordered OpenGL B, OpenGL AM, Vulkan AM, Vulkan B. Check the restored scene and controller-overlay dismissal, focus, frame samples, complete capture, and cleanup. Preserve pilots and any failure. A readiness failure stops dependent measurement until its cause and any recipe change are recorded. Neither a screenshot hash nor host presents establishes equal guest work.

## Measurement order

Each cell is a fresh process loading the same immutable original v4 snapshot, followed by the same keyboard reconnection, B input, three-second warmup, and 60-second measurement. Use the unchanged historical capture scripts and CpuScheduler tracing, scale 1, PresentMon enabled, Vulkan detailed telemetry disabled, host-CPU-reduction setting off. No interactive driving input is supplied. Driver caches are left in their normal persistent state; no cache clearing between cells.

| Pair | First renderer / build order | Second renderer / build order |
| ---: | --- | --- |
| 1 | OpenGL B → AM | Vulkan AM → B |
| 2 | Vulkan B → AM | OpenGL AM → B |
| 3 | OpenGL B → AM | Vulkan AM → B |
| 4 | Vulkan B → AM | OpenGL AM → B |
| 5 | OpenGL B → AM | Vulkan AM → B |

Five observations per build/renderer: 20 measured cells. Five pairs cannot balance first position exactly within a renderer; the opposite ordering in the control renderer and per-pair reporting keep that limitation visible. Stop on an invalid cell, retain it, and report the cause before continuing; no unrecorded retries. No exclusion for being slow. Do not stop after a favorable pair.

Admission requires pinned executable/input/script hashes, the elevated interactive session, and no conflicting emulator or capture process. A valid receipt requires completed functional and measurement gates, zero focus loss and ETW lost events/buffers, positive guest and host sample counts, unchanged seed, and completed cleanup. A measured cell with a visible input overlay is invalid even if telemetry exists. Keep all valid unfavorable results.

Every run owns a private writable HDD clone. Existing build-side result summaries are preserved before launch. Runs are serialized through capture stop and cleanup. No heavy ETL export runs concurrently with a capture. Automated admission and cleanup replace manual repeated memory inventories.

## Analysis and next decision

Report each run's guest flip cadence, mean/p95/p99/maximum frame interval, frame count, and capture gates; host presentation is context only. Report each pair's improvement and the median/range of those paired improvements. Do not average percentiles and label the result a pooled percentile. Positive improvement is favorable: higher-is-better uses `100 * (candidate/reference - 1)`; lower-is-better uses `100 * (reference-candidate)/reference`. Raw directions are `+good` or `+bad`; counts without a work oracle are context.

Recheck CPU/scheduler attribution only after captures have stopped. Existing GPU sensor data has a known tail-coverage limitation ([perf-tests #24](https://github.com/Mainkill1/xemu-perf-tests/issues/24)); it cannot establish a complete resource pass. Reproducible snapshot timing is still not proof of a PTIMER cause or fixed guest work.

Next, admit a deterministic fixed-operation guest workload with an independent output/terminal oracle, elapsed host time, and per-thread CPU. If adverse behavior persists, evaluate arithmetic-only and state-handling-only diagnostic variants from the **same** base. Count real PTIMER/IRQ/timer-list behavior before altering policy. Characterize clock changes that cross an alarm separately; an already-overdue due-now callback is not the future-alarm truncation defect.

No speculative timer rewrite is authorized by a timing sign. A bounded result of not reproduced or insufficient attribution is valid. PR59 stays draft until correctness, Morrowind snapshot readiness, full XISO, fixed-work/resource checks, and exact submission-head qualification are satisfied. Historical results remain linked and are not erased by this repeat.
