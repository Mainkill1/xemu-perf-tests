# PR #87: fresh vertex-page writes, focused qualification

**Product:** [Mainkill1/xemu#87](https://github.com/Mainkill1/xemu/pull/87), draft. **Tracking:** [issue #86](https://github.com/Mainkill1/xemu/issues/86). The current PR head is `974f2ae63b166f64aa2ea6a77963c77481e28969` (tree `4d49acf74c5069b0cf03a995c7867f55554ac028`, Windows executable SHA-256 `6f5a85d3200135ab1eef6efb4ba4c20697303f9f6ec5fa5f8b0567dda5822cc0`). Earlier full-suite and paired results in this report qualify the previous PR head `d42c81ba32e7c299e4a65f70db05e2ba3363cccc` (tree `1ad8945162e2a8403d63e5f7588dc8d8c2f0827e`; executable SHA-256 `9da192457c4264df3e3025434841c4d72599b47cf673f3a9206416619d24f99b`) against exact #85 parent `2163208fdc49c7f6b4834bce98e6a11b494d4241` (executable SHA-256 `fdafe9acae32f1a189eff6cd270bdd6443571b7e33f870efaf9bfa1b2a22f0dc`). The fixed cycle baseline is `9f618d6d8c4c446ef023955f3d4de22f661f61a4`; it was not rebuilt.

## Decision from these runs

The original direct-copy head improved **guest display-write cadence** in two order-reversed 60-second Morrowind snapshot pairs by **+6.51% and +5.43%**, but **PGR2 Vulkan snapshot p95/p99 worsened in both orders**. A trace-only counter probe found that PGR2 marked read pages on nearly every draw while direct copies occurred in only five measured frames. The current head gates that bookkeeping after quiet batches and conservatively stages the first upload when read history is unavailable. One uninstrumented gated run held Morrowind's gain and moved PGR2 p99 near its exact parent; its cross-renderer and full-suite qualification is pending. Keep PR #87 draft until those gates pass.

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

The remaining 68% of copies still take the ordered staging path. The optimization only bypasses a copy when the page has not been read by an earlier recorded draw in the active command buffer. Before a merge, test a true read-then-overwrite case, command-buffer rollover, surfaces, and buffer generation changes through the production path. A current-head Morrowind OpenGL comparison is reported below; paired cross-renderer qualification remains pending. There is no evidence yet that the patch improves a driven PGR2 lap or Morrowind map traversal.

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

### Focused PGR2 counter control

A separate 20-second parent→candidate diagnostic pair used the same PGR2 snapshot and opt-in aggregate Vulkan telemetry. This pair is **not** an uninstrumented performance acceptance result. Both runs completed with the same seed/config identities; 590 parent and 589 candidate guest frames entered the measured window. The candidate's new direct-copy path was nearly idle: only five frames in each build had any vertex upload. Thus PGR2 gets almost none of the intended saved pass/copy work, while the patch's page-read bookkeeping still runs during draw preparation.

| Measured PGR2 Vulkan window | Exact #85 parent | PR #87 candidate |
| --- | ---: | ---: |
| Draw-flush calls / guest frame | 4,770.49 | 4,770.53 |
| Staged vertex copies / 20 s | 123 | 61 |
| Direct vertex copies / 20 s | N/A | 62 |
| Direct vertex bytes / 20 s | N/A | 471,040 |
| Frames with a vertex copy | 5 / 590 | 5 / 589 |
| Timed draw-flush region / guest frame | 19.602 ms | 19.984 ms |
| Timed pipeline preparation / guest frame | 9.071 ms | 8.925 ms |
| Timed descriptor update / guest frame | 6.116 ms | 6.329 ms |
| Total sampled finish wait / guest frame | 10.756 ms | 10.564 ms |

The 0.382 ms higher draw-flush total is consistent with overhead in a very frequent path, and the saved vertex traffic is too rare to amortize much work in this scene. The timed regions can nest and include fence waits, so their differences must not be added. The short diagnostic pair did **not** reproduce the longer uninstrumented p95 regression; instrumentation and window length limit its performance interpretation. It also did not include GPU timestamps or pass-ending reason counters, so page tracking is a **leading hypothesis**, not a measured sole cause. A minimal next test is an isolated bookkeeping gate that retains the old staged path whenever prior page reads were not tracked; compare the same parent/candidate PGR snapshot and Morrowind scene before accepting it. [Compact counter control](results/pgr2-snapshot-vulkan-counter-control.json) preserves the exact executable and input hashes.

### Read-mark work and current activity gate

A trace-only build on previous head `d42c81ba32` counted the exact read-page operations without changing renderer decisions. Its diagnostic patch SHA-256 was `d4d9acba3105bec49a258826ff3aab52cfe7db234c1228ff4958cbb1a716b0f2`, executable SHA-256 `8a137e00a8bde2f437d11a7e92f0168087025a1197e8aa013daa6c4b71aba6fd`. This counter test is not an FPS comparison.

| Trace-only window | PGR2 snapshot, 584 guest frames | Morrowind snapshot, 246 display writes |
| --- | ---: | ---: |
| Draws whose vertex read pages were marked | 2,761,147 (~4,728/frame) | 284,101 (~1,151/write) |
| Vertex pages marked | 3,814,841 (~6,532/frame) | 429,090 (~1,744/write) |
| Direct vertex copies | 62 total | 27,649 total (~112/write) |
| Frames/writes containing any vertex upload | 5 / 584 | Every measured write |

The current `974f2ae` activity gate starts conservatively: without prior read tracking, an active-batch vertex update uses the old ordered staging path. A batch that updates vertex data enables read tracking for subsequent batches; 16 completed batches without updates retire it. It still clears the read map only after the submission fence. This avoids treating an untracked page as a proven fresh page. The gate changes buffer/draw/renderer state only; no shader, texture, or OpenGL path was changed. [Trace-only counts](results/read-mark-opportunity-control.json) provide raw input hashes and window identities.

The gated source-to-previous-head patch SHA-256 is `b8399582d54e9b41066f2d8a72d020218440e693129a9062013c84b4eb3cf515`; the Windows builder verified that exact patch, completed successfully, and returned to its clean original source. One uninstrumented 60-second cell per game on the new executable gave:

| Workload | Metric | Retained #85 parent range | Previous #87 range | Gated #87 current head |
| --- | --- | ---: | ---: | ---: |
| PGR2 Vulkan snapshot | Guest FPS | 29.593–29.737 | 29.284–29.430 | **29.585** |
| PGR2 Vulkan snapshot | Guest interval p95 | 37.762–38.951 ms | 39.701–40.350 ms | **39.368 ms** |
| PGR2 Vulkan snapshot | Guest interval p99 | 42.026–42.350 ms | 42.981–44.326 ms | **42.471 ms** |
| Morrowind Vulkan snapshot | Guest display writes/s | 24.016–24.215 | 25.529–25.579 | **25.615** |
| Morrowind Vulkan snapshot | Guest interval p95 / p99 | 48.042–48.822 / 53.874–55.525 ms | 45.704–46.060 / 51.445–53.128 ms | **46.019 / 52.945 ms** |

The gate appears to preserve the Morrowind benefit and recover most of the earlier PGR2 tail loss. The initial gated PGR2 p95 exceeded both retained parent cells, but those cells were from another session. A same-session **gate → exact #85 parent** 60-second Vulkan snapshot pair then measured gate/parent guest FPS **29.565/29.491**, p95 **38.872/39.643 ms**, and p99 **43.241/43.306 ms**. That is +0.25% FPS, +1.94% p95, and +0.15% p99 improvement by the template's direction convention. These small directions are compatible with noise; the important result is that the old 2–5% p95/p99 regression was not reproduced in this pair. Both cells used the same pinned seed/config, completed about 1,770 guest frames, and used no ETL/PresentMon. [Pair records](results/activity-gate-pgr2-parent-pair.json) retain their exact executable and raw-result hashes. This is still one same-session pair, not a complete performance PASS. The [two initial gated result records](results/activity-gate-initial-results.json) preserve the earlier source/build/result hashes; Morrowind image and disk cleanup checks passed.

### Why Morrowind still progresses slowly

A same-executable, uninstrumented **Vulkan → OpenGL → Vulkan** return control used the current `974f2ae` binary, identical snapshot seed, private-disk initial hash, EEPROM, runner, input sequence, 60-second window, and presentation setting. All three cells reached gameplay, passed the final-image oracle, deleted their private disks, and left no emulator/trace process. The first Vulkan run was launched before the gate commit and retains its raw `d42c81ba32+gate-b8399582` source label; its executable SHA-256 is identical to the committed current-head build. [Compact exact records](results/morrowind-renderer-return-control.json) retain raw-result and control hashes.

| Current-head Morrowind fixed snapshot | Guest display writes/s | Guest interval p95 | Guest interval p99 |
| --- | ---: | ---: | ---: |
| Vulkan first | 25.613 | 46.019 ms | 52.945 ms |
| OpenGL middle | **34.383** | **36.102 ms** | **41.013 ms** |
| Vulkan return | 25.364 | 46.936 ms | 55.083 ms |

OpenGL's guest progress was **34.90% higher than the mean of the bracketing Vulkan cells**; the Vulkan return changed cadence by only -0.97% from its first cell. This is a robust *guest-progress* gap in this scene, not measured displayed FPS or proof that OpenGL executes its graphics commands faster. Host presentation counts, OpenGL GPU time, and game-wide traversal are not in this capture.

I attempted a separate host-presentation diagnostic after this return control. PresentMon 1.10 exited without a CSV. A bounded PresentMon 2.5 capture during a later Vulkan cell reported **107,174 lost ETW events** and also emitted no CSV, so **no host-present FPS can be inferred**. The latter runner completed its image and private-disk cleanup checks, but its result contains a `seed_sha256_after` value different from the pinned seed; a subsequent direct hash of that same source file matched the pinned value, and its file timestamp had not changed. The transient mismatch remains unexplained. That cell and both PresentMon attempts are excluded from every renderer/performance comparison above. No xemu or trace process remained. [Failed host-present attempt record](results/morrowind-host-present-attempt.json) preserves the tool outcome and raw-result hash without implying a valid measurement.

The source and earlier [#86 GPU-timestamp diagnosis](https://github.com/Mainkill1/xemu-perf-tests/blob/evidence/pr85-vertex-surface-freshness/docs/evidence/pr85-vertex-surface-20260912/issue86-deep-diagnosis/REPORT.md) explain the likely chain. Morrowind issues about 1,150 small Vulkan draws and a clear-plus-report pair per guest display write, with zero occlusion queries in the measured #83 window. Vulkan's idle report path finishes the active command buffer before writing the report. On that **older stacked #83 tree**, the report fence wait was 11.216 ms median/write, 96.1% matched elapsed GPU batch time, and 94.8% of GPU batch time was in the main graphics command buffer. The guest's sampled retry loop reads a 16-byte record with the same timestamp/result/completion layout as xemu's report; dynamic DMA-address identity is still unproven. OpenGL's zero-query path writes the record without waiting for a corresponding query result. These different completion policies can explain faster *guest* progress without proving a same-size GPU-work advantage for OpenGL. Publishing Vulkan's completion early would risk violating the guest's GPU-fence expectation.

The graphics workload itself is heavy: the older #83 counters found roughly **353 dirty vertex staging copies and 348 nondraw pass endings per guest display write**, with 95.6% of all pass endings attributed to nondraw work and their per-write counts correlated at 0.999. The current PR removes some of those copies, but most remain ordered staging transfers; #85/#87 exact-parent counters also retain approximately five synchronous submissions and 10.249 ms median sampled fence wait per write on the **previous #87 head**. Descriptor-update timing includes a nested capacity fence wait, so its 8–10 ms region must not be counted as extra descriptor-writing cost. This is why PR #87 improves the fixed scene by about 6% without removing the broader ~25-write/s limit. Exact current-head GPU timestamps and host-present metrics remain the decisive missing measurements.

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
