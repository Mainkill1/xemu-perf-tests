# PR #87: fresh vertex-page writes, focused qualification

**Product:** [Mainkill1/xemu#87](https://github.com/Mainkill1/xemu/pull/87), draft. **Tracking:** [issue #86](https://github.com/Mainkill1/xemu/issues/86). This report measures the exact PR head `d42c81ba32e7c299e4a65f70db05e2ba3363cccc` (tree `1ad8945162e2a8403d63e5f7588dc8d8c2f0827e`; Windows executable SHA-256 `9da192457c4264df3e3025434841c4d72599b47cf673f3a9206416619d24f99b`) against its exact #85 parent `2163208fdc49c7f6b4834bce98e6a11b494d4241` (executable SHA-256 `fdafe9acae32f1a189eff6cd270bdd6443571b7e33f870efaf9bfa1b2a22f0dc`). The fixed cycle baseline is `9f618d6d8c4c446ef023955f3d4de22f661f61a4`; it was not rebuilt.

## Decision from these runs

The new path is active: in a 10-second opt-in Vulkan Morrowind window, 27,642 of 86,007 vertex copies (32.14%) wrote fresh pages directly rather than staging them. The exact candidate then improved **guest display-write cadence** in two order-reversed 60-second Morrowind snapshot pairs by **+6.51% and +5.43%**, with better p95 and p99 intervals in each pair. PGR2 full start was effectively tied at its 30-FPS guest cadence. However, **PGR2 Vulkan snapshot p95/p99 worsened in both order-reversed pairs**. Keep PR #87 draft and on performance hold; its Morrowind benefit is insufficient for a merge recommendation.

These Morrowind values are **NV2A guest display writes per second, not displayed FPS**. The fixed Morrowind snapshot keeps one camera view; the PGR2 fresh boot reaches the race scene without a driven lap. Neither substitutes for a full-race or map-traversal test.

## Setup and evidence identity

| Item | Exact value |
| --- | --- |
| Build/test hosts | Windows cross-build host; interactive Windows Session 1 test host |
| Build profile | Pinned Windows O2/full-LTO/x86-64-v3 build with DWARF and assertions; product patch matched the committed #87 diff |
| Morrowind runner | SHA-256 `9994bd2d823e8557d39aef582fef8d7f37965d54caa52eaa09514e5d256307ed`; snapshot `vm-20260905015459`; 60-second measurement, same input and renderer; separate private HDD copies |
| PGR2 runner | Retained `capture-pgr2-spirv-prewarm-pr70.ps1`; fresh-boot seed SHA-256 `8b4f7c81be6ece5db3fc98d683d86d0515db43b2447e8dff14bfd9b45078c606`; 30-second warmup then 120-second measurement |
| PGR2 config | Same canonical Vulkan/NVIDIA base config SHA-256 `2fe22ca7513a0b72df9e83e88809b81a4a591595cb7b67d7613bacd5125be0a0` for both executables; renderer Vulkan, surface scale 1 |
| Instrumentation for performance cells | No Vulkan opt-in counters, no WPR/ETL trace, no PresentMon; PGR2 guest intervals from the xemu flip log; Morrowind intervals from the NV2A display-write log |
| Raw evidence | Full PGR2 capture directories and diagnostic streams remain on the test host; compact records here include the raw PGR2 result SHA-256 and the Morrowind opt-in input hashes. Copyrighted game images are not published. |

The per-run launch-config SHA-256 differs because the runner embeds a different private HDD path in each copy. Its base-config SHA-256 and policy validation match. The Morrowind snapshot seed hash was unchanged after all four 60-second runs. No xemu, WPR, xperf, or PresentMon process remained after the campaign.

## Morrowind snapshot: 60-second order-reversed pairs

Positive **Improvement %** means better. Cadence uses `+good`; intervals use `+bad` (lower is better). Each cell completed the same snapshot, passed the final-image nonblack/color oracle, and deleted its private HDD. I also visually inspected the parent and candidate end images from the first pair; the static scene is coherent in both, with expected water variation. That is not a strict pixel-equivalence oracle.

| Order | Metric | Raw + | #85 parent | PR #87 | Improvement % |
| --- | --- | --- | ---: | ---: | ---: |
| Parent → candidate | Guest display writes/s | `+good` | 24.016 | 25.579 | **+6.51%** |
| Parent → candidate | Guest interval p95 | `+bad` | 48.822 ms | 46.060 ms | **+5.66%** |
| Parent → candidate | Guest interval p99 | `+bad` | 55.525 ms | 51.445 ms | **+7.35%** |
| Candidate → parent | Guest display writes/s | `+good` | 24.215 | 25.529 | **+5.43%** |
| Candidate → parent | Guest interval p95 | `+bad` | 48.042 ms | 45.704 ms | **+4.87%** |
| Candidate → parent | Guest interval p99 | `+bad` | 53.874 ms | 53.128 ms | **+1.38%** |

The earlier **single 10-second** uninstrumented candidate cell was neutral/adverse versus a #85 cell from an earlier session: 23.897 versus 23.996 writes/s, p95 50.299 versus 48.498 ms, p99 58.382 versus 59.161 ms. It remains in the results rather than being discarded. The 60-second paired runs provide a better comparison, but still represent one fixed scene and two pairs.

The retained fixed-baseline medians from a different session were p95/p99 **47.413/52.773 ms**. The current candidate two-cell medians are **45.882/52.287 ms**, or descriptively **+3.23%/+0.92%** against that historical baseline. The different sessions and test windows prevent treating that cumulative comparison as a formal same-day baseline pass. [The baseline source and results](../issue79-warm-texture-binding-20260912/README.md) remain unchanged.

## PGR2 fresh boot: full-start 120-second pair

The candidate ran first, then its parent. Both entered the race scene, recorded **3,602 guest frames** and no guest intervals at or above the runner's 75-ms stall threshold. This is a boot/start/race-scene test, not a played race.

| Metric | Raw + | #85 parent | PR #87 | Improvement % |
| --- | --- | ---: | ---: | ---: |
| Guest FPS | `+good` | 30.000 | 30.000 | +0.00% |
| Guest interval p95 | `+bad` | 33.602 ms | 33.629 ms | -0.08% |
| Guest interval p99 | `+bad` | 33.985 ms | 33.978 ms | +0.02% |
| Guest interval maximum | `+bad` | 34.598 ms | 35.026 ms | -1.24% |

The fixed-baseline PGR2 full-start p95/p99 medians were **33.482/34.253 ms** in an earlier campaign. PR #87's values are descriptively **-0.44%/+0.80%** against those medians; this is not a paired baseline test.

The first candidate PGR2 attempt is **excluded**: PresentMon reported 535,414 lost ETW events and emitted no CSV, causing the runner to mark the attempt failed after the capture window. The subsequent parent/candidate pair disabled PresentMon and ETL tracing for both, while retaining the same guest timing source. The failed attempt left no emulator, trace process, or private HDD behind.

## Mechanism, limits, and next gate

The opt-in counter run is diagnostic only and is not pooled with uninstrumented performance cells. Its 246-write window recorded **27,642 direct copies / 213.5 MB** and **58,365 staged copies / 543.2 MB**; median direct and staged copies were 112 and 241 per guest display write. This matches the earlier page-opportunity probe's roughly 31% fresh-page fraction. [Copy-window summary](results/morrowind-vulkan-copy-window.json) identifies the exact raw diagnostic hashes; [wait summary](results/morrowind-vulkan-wait-summary.json) gives sampled timing with instrumentation caveats.

The remaining 68% of copies still take the ordered staging path. The optimization only bypasses a copy when the page has not been read by an earlier recorded draw in the active command buffer. Before a merge, test a true read-then-overwrite case, command-buffer rollover, surfaces, and buffer generation changes through the production path. Morrowind OpenGL remains pending. There is no evidence yet that the patch improves a driven PGR2 lap or Morrowind map traversal.

## Full current XISO suite, both renderers

The unchanged product executable ran the complete current 159-record XISO catalog on each renderer. The test source was `5269072fb1db6b1a7ca3c9679db05bce6e204a38`, image SHA-256 `1e2573d416949ced403426826bf4d8597949468ed117185847f47dfd97b64260`, catalog SHA-256 `a0674f73cef85d43f1dba0ad2059b9fa076841a0f4b1084b59186cf4ffb3871e`, and runner SHA-256 `cd51e2192bf51a5e58862b4ff5f356867119a59c95351bc3a1378994e7917558`. This is a functional run, not a timing comparison. Both overall suite statuses are **FAILED** due previously tracked failures; they must not be called passes.

| Renderer | Passed / total | Failed IDs | Functional hash | Vulkan VUIDs |
| --- | ---: | --- | --- | ---: |
| Vulkan | 158 / 159 | `report_query.dma_range_guard` (#60) | PASSED | 0 |
| OpenGL | 157 / 159 | `report_query.dma_range_guard` (#60); `texture_cubemap_fallback.unbordered_subblock_dxt1` (#82) | PASSED | N/A |

Against the retained prior result catalog, 157 deterministic outcome/framebuffer-hash pairs matched on each renderer. Two successful queued same-address texture-write cases declare framebuffer-hash comparison ineligible; their expected outcomes and internal oracles passed. No unexpected outcome/hash difference was found. [Compact suite summary](results/xiso-full-summary.json) and the [318 per-test rows](results/xiso-full-per-test.csv) preserve the exact comparison. The inherited failures remain real open correctness work.

## PGR2 Vulkan snapshot: performance hold

The 60-second snapshot used the same seed SHA-256 `cbc17b468d49127a09743a63777ee3bef35b63040083989187724cd4a42b594c` and Vulkan base-config SHA-256 `2fe22ca7513a0b72df9e83e88809b81a4a591595cb7b67d7613bacd5125be0a0` in all four cells, with 3-second warmup. No opt-in Vulkan telemetry, ETL, or PresentMon was active. All cells completed and produced sufficient guest frames. Positive improvement means better; intervals use `+bad`.

| Order | Metric | Raw + | #85 parent | PR #87 | Improvement % |
| --- | --- | --- | ---: | ---: | ---: |
| Parent → candidate | Guest FPS | `+good` | 29.593 | 29.284 | **-1.04%** |
| Parent → candidate | Guest interval p95 / p99 | `+bad` | 38.951 / 42.350 ms | 40.350 / 44.326 ms | **-3.59% / -4.67%** |
| Candidate → parent | Guest FPS | `+good` | 29.737 | 29.430 | **-1.03%** |
| Candidate → parent | Guest interval p95 / p99 | `+bad` | 37.762 / 42.026 ms | 39.701 / 42.981 ms | **-5.13% / -2.27%** |

Both orders show a similar FPS loss and adverse tails, making a simple second-run explanation unlikely. The [four compact result records](results/pgr2-snapshot-vulkan-pairs.json) identify each executable and raw-result hash. This does not yet identify whether the extra time is host-mapped writes, added page checks, changed render-pass structure, or GPU execution; isolate those costs before changing the patch.

## What the Morrowind wait counters actually mean

An additional **counter-only exact-parent control** used the same Morrowind snapshot and runner as the earlier candidate counter window. The parent executable SHA-256 was `fdafe9acae32f1a189eff6cd270bdd6443571b7e33f870efaf9bfa1b2a22f0dc`; its 248-display-write window passed the final-image oracle, deleted its private disk, and left no trace process running. The candidate window contained 246 writes. These short diagnostic windows are not a paired performance qualification. Their sampled waits reveal where execution blocks, not a sum of independently additive CPU costs.

| Per guest display write, median | Exact #85 parent | PR #87 candidate |
| --- | ---: | ---: |
| Total sampled finish-fence wait | 12.459 ms | 10.249 ms |
| `NEED_BUFFER_SPACE` fence wait | 9.523 ms | 7.956 ms |
| `STALLED` report fence wait | 2.032 ms | 1.714 ms |
| Vulkan queue submits | 5 | 5 |
| `update_descriptor_sets()` timed region | 10.118 ms | 8.555 ms |
| `draw_flush()` timed region | 16.634 ms | 13.127 ms |

`update_descriptor_sets()` calls `pgraph_vk_finish(... NEED_BUFFER_SPACE)` when descriptor or uniform-staging capacity is exhausted. Thus its timed region **includes the nested fence wait**; the 10.118/8.555 ms values are not separate descriptor-writing CPU costs. The exact parent already has one such submission per Morrowind display write. The earlier issue #86 GPU-timestamp probe used stacked #83, whose descriptor-capacity change removed that finish; comparing its 0.5 ms descriptor region to #87 would falsely blame this PR for a pre-existing wait. The current candidate reduces the parent wait in this fixed Morrowind scene, but it neither removes the capacity gate nor proves a universal win. [Parent counters](results/morrowind-parent-counter-control.json) and [candidate counters](results/morrowind-candidate-counter-control.json) retain window hashes, reason counts, and CPU-region values.

The deeper [issue #86 GPU-timestamp report](https://github.com/Mainkill1/xemu-perf-tests/blob/evidence/pr85-vertex-surface-freshness/docs/evidence/pr85-vertex-surface-20260912/issue86-deep-diagnosis/REPORT.md) measured about 1,151 small draws per guest display write and traced a guest retry loop around the Z-pass report completion record. On stacked #83, 94.8% of the sampled GPU batch elapsed in the main graphics command buffer. This explains why a report/descriptor fence can govern guest progression, but it is a different executable; no exact-parent GPU timestamp comparison has yet isolated PR #87's PGR2 regression. The next focused diagnostic should count its pass endings/direct bytes and timestamp the exact-parent/candidate GPU batches in PGR2, then determine whether the Morrowind and PGR2 tradeoff can be corrected without stale vertex data.
