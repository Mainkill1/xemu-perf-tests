# PR #87: fresh vertex-page writes, focused qualification

**Product:** [Mainkill1/xemu#87](https://github.com/Mainkill1/xemu/pull/87), draft. **Tracking:** [issue #86](https://github.com/Mainkill1/xemu/issues/86). The current PR head is `974f2ae63b166f64aa2ea6a77963c77481e28969` (tree `4d49acf74c5069b0cf03a995c7867f55554ac028`, Windows executable SHA-256 `6f5a85d3200135ab1eef6efb4ba4c20697303f9f6ec5fa5f8b0567dda5822cc0`). Earlier full-suite and paired results in this report qualify the previous PR head `d42c81ba32e7c299e4a65f70db05e2ba3363cccc` (tree `1ad8945162e2a8403d63e5f7588dc8d8c2f0827e`; executable SHA-256 `9da192457c4264df3e3025434841c4d72599b47cf673f3a9206416619d24f99b`) against exact #85 parent `2163208fdc49c7f6b4834bce98e6a11b494d4241` (executable SHA-256 `fdafe9acae32f1a189eff6cd270bdd6443571b7e33f870efaf9bfa1b2a22f0dc`). The fixed cycle baseline is `9f618d6d8c4c446ef023955f3d4de22f661f61a4`; it was not rebuilt.

## Decision from these runs

The original direct-copy head improved **guest display-write cadence** in two order-reversed 60-second Morrowind snapshot pairs by **+6.51% and +5.43%**, but **PGR2 Vulkan snapshot p95/p99 worsened in both orders**. A trace-only counter probe found that PGR2 marked read pages on nearly every draw while direct copies occurred in only five measured frames. The current head gates that bookkeeping after quiet batches and conservatively stages the first upload when read history is unavailable. A new exact-current-head 60-second Morrowind pair measured **+5.98%** cadence and **+5.23%/+4.06%** p95/p99 improvement against its exact parent. Its same-session PGR2 snapshot pair did not reproduce the old tail loss, and the new 160-record XISO ran on both renderers with only the inherited #60/#82 failures. Remaining vertex-lifetime and broader game/renderer qualification cases are still pending. Keep PR #87 draft. The [current Morrowind diagnosis](MORROWIND-DIAGNOSIS.md) now directly matches the guest's polled report record to Vulkan's queued destination while separating measured GPU completion cost from unproven per-pass cost and first-read timing.

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

### Exact current head: candidate → parent 60-second pair

The gated current #87 source `974f2ae63b166f64aa2ea6a77963c77481e28969` ran first, followed immediately by exact #85 parent `2163208fdc49c7f6b4834bce98e6a11b494d4241`. The same snapshot, renderer, runner, input and 60-second window were used. Both cells passed the final-image nonblack/color check, retained the same seed hash, deleted their private HDD, and left no xemu or tracing process. Different final-image hashes reflect scene variation; no pixel-equivalence claim is made. [Exact result records and hashes](results/morrowind-current-head-parent-60s-r3.json) are retained.

| Current-head Vulkan metric | Raw + | Exact #85 parent | Current PR #87 | Improvement % |
| --- | --- | ---: | ---: | ---: |
| Guest display writes/s | `+good` | 24.296 | 25.750 | **+5.98%** |
| Guest interval p95 | `+bad` | 48.389 ms | 45.985 ms | **+5.23%** |
| Guest interval p99 | `+bad` | 55.004 ms | 52.860 ms | **+4.06%** |

This confirms a same-session current-head Morrowind gain in one fixed view, with the candidate running first. It is not a map-traversal test or a measured displayed-FPS gain. The earlier exact-current GPU timestamp control had an opposite diagnostic guest-cadence direction; its inserted timestamps and short sequential windows make it an attribution probe, not a replacement for these uninstrumented cells.

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

The remaining 68% of copies still take the ordered staging path. The optimization only bypasses a copy when the page has not been read by an earlier recorded draw in the active command buffer. The true read-then-overwrite focused oracle and new full 160-record suite are reported below; command-buffer rollover, surfaces, buffer-generation changes, and exact-current-head performance qualification remain before a merge. A current-head Morrowind OpenGL comparison is reported below; paired cross-renderer qualification remains pending. There is no evidence yet that the patch improves a driven PGR2 lap or Morrowind map traversal.

### Ordered same-page overwrite oracle on the current head

New XISO source `5b9670e5bbef92ea12a303ecd7a9eef88e956ba3` adds `vertex_buffer_allocation.ordered_same_page_overwrite`. It draws from a vertex page, drains the guest FIFO without declaring GPU completion, overwrites that same page, draws again, then asserts the first and second colors at distinct pixels. The pinned builder produced a **160-record** XISO (SHA-256 `3146ad9da3a8ae8e8185699083c6888f312e9ad2a4707bded2a1c265b75db7a3`) and catalog (SHA-256 `98224982dd86f27cf3e8b87a2b17d34aed3c2f2d2e76b8e70a0c5c72b46899e9`). Host tests and catalog consistency passed. The fixed baseline was run with its retained runtime-equivalent `c17591d59c27` executable; no baseline rebuild was needed.

| Focused one-leaf correctness | Fixed baseline | Exact #85 parent | Current #87 |
| --- | --- | --- | --- |
| Vulkan | PASS; 1/1; VUID 0 | PASS; 1/1; VUID 0 | **PASS; 1/1; VUID 0** |
| OpenGL | PASS; 1/1 | PASS; 1/1 | **PASS; 1/1** |

All six runs produced the same `bbc8caeedc9dff25` framebuffer FNV-1a hash. A separate candidate-only `XEMU_VK_PERF_LOG` diagnostic invocation also passed and recorded **8 direct and 29 staged vertex copies** over its 35-frame focused launch. Those counters show that both production paths were active somewhere in the launch; they do not isolate a specific draw or qualify timing. An initial attempt used the runner's incompatible `--vulkan-lab-counters` format and ended `INFRASTRUCTURE_FAILED`; it is excluded and retained in the [compact six-cell/counter record](results/ordered-same-page-oracle.json). The full-suite follow-up is below.

### Exact-current-head 160-record full XISO

The unchanged #87 executable then ran the new **160-record** XISO catalog on both renderers. The new `vertex_buffer_allocation.ordered_same_page_overwrite` leaf passed in each full run as well as in the six focused baseline/parent/candidate cells. Both runner-level suite statuses remain **FAILED** because of the same previously tracked leaves; a passing record-count check or functional-hash check does not turn the overall suite into a pass.

| Exact #87 head, 160-record XISO | PASS records | Inherited FAIL records | Functional hash | Vulkan VUIDs | Host wall |
| --- | ---: | --- | --- | ---: | ---: |
| Vulkan | 159 / 160 | `report_query.dma_range_guard` (#60) | PASSED | 0 | 115.23 s |
| OpenGL | 158 / 160 | `report_query.dma_range_guard` (#60); `texture_cubemap_fallback.unbordered_subblock_dxt1` (#82) | PASSED | N/A | 128.24 s |

All 159 older test IDs retained their outcomes. On each renderer, 157 eligible framebuffer hashes matched the prior 159-record catalog; the two successful same-address queued texture-write tests intentionally declare their final framebuffer hashes ineligible for cross-run comparison, while their own oracles passed. The new leaf was the only added ID. This is **functional qualification**, not a performance A/B: the test revision changed, Vulkan validation was active, and the old 159-record result used a different #87 head. [Compact exact-head summary](results/xiso-current-head-160-summary.json) and [all 320 per-test rows](results/xiso-current-head-160-per-test.csv) preserve the outcomes and comparisons. The remaining inherited failures stay assigned to #60 and #82.

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

The source and earlier [#86 GPU-timestamp diagnosis](https://github.com/Mainkill1/xemu-perf-tests/blob/evidence/pr85-vertex-surface-freshness/docs/evidence/pr85-vertex-surface-20260912/issue86-deep-diagnosis/REPORT.md) explain the likely chain. Morrowind issues about 1,150 small Vulkan draws and a clear-plus-report pair per guest display write, with zero occlusion queries in the measured #83 window. Vulkan's idle report path finishes the active command buffer before writing the report. On that **older stacked #83 tree**, the report fence wait was 11.216 ms median/write, 96.1% matched elapsed GPU batch time, and 94.8% of GPU batch time was in the main graphics command buffer. The guest's sampled retry loop reads a 16-byte record with the same timestamp/result/completion layout as xemu's report; the later exact-#87 trace below directly matches its physical address to the queued report destination. OpenGL's zero-query path writes the record without waiting for a corresponding query result. These different completion policies can explain faster *guest* progress without proving a same-size GPU-work advantage for OpenGL. Publishing Vulkan's completion early would risk violating the guest's GPU-fence expectation.

The graphics workload itself is heavy: the older #83 counters found roughly **353 dirty vertex staging copies and 348 nondraw pass endings per guest display write**, with 95.6% of all pass endings attributed to nondraw work and their per-write counts correlated at 0.999. The current PR removes some of those copies, but most remain ordered staging transfers; #85/#87 exact-parent counters also retain approximately five synchronous submissions and 10.249 ms median sampled fence wait per write on the **previous #87 head**. Descriptor-update timing includes a nested capacity fence wait, so its 8–10 ms region must not be counted as extra descriptor-writing cost. This is why PR #87 improves the fixed scene by about 6% without removing the broader ~25-write/s limit. Direct OpenGL GPU timestamps and host-present metrics remain unmeasured.

### Current-head wait and slow-interval attribution

One additional **10-second diagnostic run** used exact current PR #87 head `974f2ae63b166f64aa2ea6a77963c77481e28969`, executable SHA-256 `6f5a85d3200135ab1eef6efb4ba4c20697303f9f6ec5fa5f8b0567dda5822cc0`, the pinned Morrowind snapshot and the same runner. Its 229 counter records matched 229 display-write events in the measurement window; the final-image check passed, the private HDD was deleted, and no xemu/trace process remained. Vulkan opt-in counters add overhead, so its 22.879 writes/s and interval values **must not be compared as a performance result** to the uninstrumented 60-second cells. [Exact wait summary](results/morrowind-current-gate-vulkan-wait-summary.json) and [frame association](results/morrowind-current-gate-frame-association.json) include input checksums and method.

| Current head, median per measured display write | Result |
| --- | ---: |
| `NEED_BUFFER_SPACE` submissions | 230 in 229 writes |
| `NEED_BUFFER_SPACE` sampled fence wait | **10.324 ms** |
| `STALLED` report sampled fence wait | 1.987 ms |
| Total sampled finish-fence wait | **13.243 ms** |
| Vulkan queue submissions | 5 |
| Direct vertex copies / staged copies | 112 / 243 |
| Direct vertex bytes / staged bytes | 0.868 / 2.269 MB |

The current 1,024-descriptor branch still submits early at `NEED_BUFFER_SPACE`; the stacked #83 capacity experiment eliminated that submission but moved the long wait to `STALLED` without improving the measured frame path. This new exact-head run confirms the capacity wait remains, rather than assuming the older #83 wait label applies to #87. The direct-copy path is active on almost every measured write, but roughly two-thirds of vertex copies still require ordered staging.

I aligned each counter frame by ordinal to its guest display-write timestamp and compared the fastest and slowest 10% of the **228 intervals wholly inside** the window. Medians are descriptive; the groups are not matched experiments.

| Diagnostic interval group | Guest interval | Capacity wait | Report wait | Total sampled wait | Direct / staged copies |
| --- | ---: | ---: | ---: | ---: | ---: |
| Fastest 22 | 36.977 ms | 6.871 ms | 1.157 ms | 8.345 ms | 112 / 240.5 |
| Slowest 22 | **54.093 ms** | **12.631 ms** | **3.253 ms** | **16.409 ms** | 113 / 247.5 |

Across these intervals, Spearman rank correlation with guest interval was **0.816** for sampled capacity wait, **0.679** for sampled report wait, and **0.832** for total sampled finish wait; staged-copy count correlated **0.361**. Correlation does not prove that shortening a fence makes the whole interval shorter, and the sampled waits are not an exhaustive time budget. It does show that the slow tail co-occurs with longer completion waits while vertex-copy counts remain broadly similar. The separate exact-head GPU timestamp run below closes the GPU-versus-descriptor-CPU attribution for this wait; the subsequent trace matches the guest record to the report destination but does not timestamp its first pending read.

### Exact current-head GPU batch timeline

I reapplied the existing four-timestamp diagnostic patch (`a5babd1f62d807cab7c7c894d883e144107391bc1bc3cdffd7ee358b673aeb4b`) to the **exact current product tree** `4d49acf74c5069b0cf03a995c7867f55554ac028`. The Windows diagnostic executable SHA-256 is `80889154812d794bd6ae4d600fa861cde57110c14d736e9c6dc3ab43e18d0c44`; its build finished and the builder checkout was restored. The timestamp queue supports 64 valid bits at 1 ns per tick. One 10-second Vulkan snapshot matched all 243 counter frames to 243 guest display-write events; final image, immutable seed, private-HDD deletion and process cleanup passed. This instrumentation changes timing: its 24.283 writes/s is **not** a performance comparison with the uninstrumented product.

| Exact-head timestamp window | Host fence wait sum | GPU batch elapsed sum | GPU main graphics sum | Median GPU main per write |
| --- | ---: | ---: | ---: | ---: |
| `NEED_BUFFER_SPACE`, 244 submissions | **2.307 s** | **2.169 s** | **1.952 s** | **8.122 ms** |
| `STALLED` report, 243 submissions | 0.482 s | 0.365 s | 0.239 s | 0.847 ms |

The capacity batch's GPU elapsed interval accounts for **94.0% of its total host fence wait**; its main graphics command buffer accounts for **90.0% of the GPU batch**. The remaining capacity batch is auxiliary staging/flush (0.186 s) and auxiliary-to-main handoff (0.031 s). The capacity wait is therefore primarily waiting for recorded GPU work, not CPU time spent writing descriptors or retrieving zero-query results. Its location is imposed by the 1,024-set capacity; the older #83 experiment moved completion to the later report boundary without reducing that work. [Exact timestamp summary](results/morrowind-current-gate-gpu-phases-summary.json) includes per-reason counts, waits and phase totals.

In the 242 consecutive intervals wholly inside this new window, the fastest 24 had median guest interval **34.699 ms** and capacity-main GPU time **4.984 ms**; the slowest 24 had **49.111 ms** and **10.294 ms**. Interval rank correlation was **0.821** with capacity-main GPU time, **0.829** with capacity-batch GPU time, and **0.827** with host capacity wait. Staged-copy count correlated 0.366; the groups' medians were 193 and 243.5 copies. This is strong timing attribution for the Vulkan completion path, while variation in guest work and the intrusive timestamps prevent a per-copy cost estimate. [Frame association and input identities](results/morrowind-current-gate-gpu-interval-association.json) make the calculation reviewable. The next performance experiment should target the remaining *ordered* vertex-copy pass breaks or another measured component inside the main GPU command buffer; it must keep the report and vertex-data completion contracts intact.

An exact-source report-address diagnostic then closed the previously open **guest record ↔ queued report** identity: four live helper-entry samples read index zero from the guest stack and resolved virtual `0x80fff000` to physical `0x00fff000`; five additional caller-site samples resolved the same address. In its 15-second measured window, **361 queued → stalled → written report triplets** all used physical `0x00fff000` and had **zero occlusion queries**, matching 361 guest display writes. The diagnostic stall-to-write interval was 2.031 ms median and 3.550 ms p95. QMP observed the completed word after publication, not the first pending load, so the exact guest-read timestamp remains open. This is a diagnostic trace, **not a performance A/B**. [Address-match summary and reproduction patch](MORROWIND-DIAGNOSIS.md#direct-guest-to-report-address-match) preserve the source and evidence limits.

An **exact #85 parent timestamp control** used the same diagnostic patch, build profile, snapshot, runner and 10-second window in the following run. Parent source/tree were `2163208fdc49c7f6b4834bce98e6a11b494d4241` / `e71f9bd72997bf81da62fab8029a8a310d00c23c`, executable SHA-256 `ab7a36ae6cd3952bed500cb2dded1e0ca6d79ad761a2ae6bea837299fe0dc74a`. Its 253 counter records matched 253 display-write events; image, seed and private-disk checks passed, and the builder/test processes were cleaned up. These were **current → parent, single sequential diagnostic cells**, not a balanced performance trial.

| Timestamp diagnostic metric | Exact #85 parent | Current PR #87 |
| --- | ---: | ---: |
| Guest display writes/s, diagnostic only | 25.282 | 24.283 |
| Capacity main-buffer GPU mean/write | 8.450 ms | 8.032 ms |
| Capacity main-buffer GPU median/write | 8.042 ms | 8.122 ms |
| Capacity main-buffer GPU p95/write | 12.220 ms | 10.985 ms |
| Total sampled finish-wait median/write | 11.379 ms | 12.161 ms |

The mean and p95 GPU-main directions favor #87, but its median does not, and guest progression went the other way in these intrusive sequential cells. That conflict **does not overturn** the earlier uninstrumented 60-second old-head Morrowind pairs; it does mean this timestamp pair cannot establish an exact-current-head throughput gain or assign the original 5–7% gain solely to GPU pass breaks. The one safe conclusion is the common bottleneck: both exact trees spend substantial time completing the main graphics batch before the guest can proceed. [Parent summary](results/morrowind-parent-gpu-phases-summary.json) and [paired diagnostic identities](results/morrowind-parent-current-gpu-phase-control.json) retain the raw input hashes and adverse result.

### Surface-scale control: pixel fill is not the principal fixed-view limit

I ran a surface-scale **1 → 2 → 1** control on the exact current #87 product source. The three uninstrumented cells used the same executable, snapshot, input sequence and 10-second window. A separate three-cell control used the exact-source four-timestamp diagnostic executable. Each prelaunch config recorded the requested scale, each cell reached gameplay and passed the final-image check, the pinned snapshot seed remained unchanged, and all private disks and processes were cleaned up. This is a scale-sensitivity experiment, not a candidate-versus-baseline performance qualification; scale 2 changes render-target work and the final images are not pixel-identical.

| Surface scale / order | Uninstrumented guest writes/s | Diagnostic guest writes/s | Diagnostic main-GPU median/write | Diagnostic staged / direct vertex copies, median/write |
| --- | ---: | ---: | ---: | ---: |
| 1 / first | 24.642 | 25.313 | 7.783 ms | 239 / 112 |
| 2 / middle | 25.170 | 24.696 | 8.411 ms | 240 / 112 |
| 1 / return | 25.565 | 24.300 | 8.125 ms | 240 / 112 |

Scale 2 produced **+0.27%** uninstrumented guest cadence and **-0.44%** diagnostic cadence versus the mean of its bracketing scale-1 cells. The diagnostic main-GPU median rose **5.75%**. These short cells cannot establish that scaling has no cost, and their p99 intervals moved inconsistently. They do show that increasing configured surface scale did not reproduce the roughly **35%** OpenGL-versus-Vulkan guest-progress gap in this fixed view. A simple pixel-fill explanation is therefore weak; repeated draws, state changes, vertex-copy pass breaks, and ordered completion remain the stronger source-backed path. The [compact scale-control record](results/morrowind-current-head-scale-control.json) retains source/executable identities, aligned counter counts, raw input hashes and each cell's result.

The older stacked #83 per-draw diagnostic can be read more precisely without treating its intrusive timestamps as product timing: in its exact 222-write window, fragment SPIR-V identity `cfb84803a10888b0` covered **244,659 of 258,254 draws (94.7%)**, **27.1% of fragment invocations**, and **92.5% of the probe's summed per-draw GPU time**. This is a many-small-draw signature, not proof of a slow fragment program. The 1,150-draw and roughly 350 ordered-vertex-copy/pass-break counts were measured on #83; the current #87 counter window still records about **240 staged and 112 direct vertex copies per write**, but has no per-draw query breakdown. Porting the per-draw probe to the exact current head would be needed before assigning that old shader identity a current-head percentage.

The [earlier #83 CPU/guest trace](https://github.com/Mainkill1/xemu-perf-tests/blob/evidence/pr85-vertex-surface-freshness/docs/evidence/pr85-vertex-surface-20260912/issue86-deep-diagnosis/REPORT.md#cpu-scheduling-and-code-samples) also explains why a low guest cadence can coexist with high host CPU use. During its 10-second Morrowind Vulkan window, the guest-CPU thread ran for **9.865 s**, was scheduler-ready for only **0.009 s**, and spent **48.0% of its sampled stack hits** in translated-block lookup helpers. Guest instruction samples near a report stall landed at the two observed retry sites in **22/26** cases, versus **2/94** away from a stall. The inspected guest helper polls the completion word of a 16-byte record whose layout matches xemu's Z-pass serializer; the new exact-#87 address trace matches that record to Vulkan's report destination. This supports a guest busy-poll while Vulkan waits for real GPU work, but does not timestamp the first pending read or mean the host scheduler is starving the guest. Reducing TB-lookup cost alone may spend less CPU while leaving the same GPU/report stall and guest cadence.

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
