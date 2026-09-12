# Issue #79 / draft PR #80: warm Vulkan texture-binding candidate

## Current proposed head: `8ec5e2a` (qualification in progress)

The current proposed patch keeps the clean-stage texture-preparation skip and the DMA-source guard, while restoring previous-main's descriptor/uniform update cadence. The original selective cadence moved a synchronous surface-readback wait into the following bind; order-reversed diagnostics did not show a reliable complete-frame gain. The exact proposed source is `8ec5e2a76475b8380adebf9a9b1df1fe442409a0`, tree `9725e0d04ed94d77838bd9ca5a7edc373b87350c`, Windows Release/full-LTO executable SHA-256 `06bffe5204279a5a0ee4cdf62f5c61e8e0e337cd205a1dee622eb94df31bb42c`. Previous main is `5edff26383c6440da35bc92b9fca35f4a404b03b` (retained executable source `a08c4d9` has the same runtime tree); fixed baseline remains `9f618d6d8c4c446ef023955f3d4de22f661f61a4` and was not rebuilt.

A corrected guest fixture now has a **real negative control**. Test source `74013c3` (XISO SHA-256 `848356eef5f4bede318dcd5fa73c848191f323200c15ba224310c61b5c9ff166`) maps clean stage 0 to separate, GPU-visible DMA pages outside retained surfaces and dirties only stage 1. The vulnerable `b5aea97` renders stale red after remap (actual pixel KAT `3138308333`, expected `2028477935`); previous main and final `8ec5e2a` both PASS. A diagnostic guard probe confirms that vulnerable `b5aea97` reached the clean-stage skip with `dirty=0`, `surface_overlap=0`, old source `0x2ff4000`, and new source `0x2ffc000`. The source/pixel result, rather than a failing test label alone, is the negative-control evidence. The palette-DMA focused leaf also passes on the final build.

The matched schema-5 PGR2 Vulkan snapshot runs used the same seed and telemetry with candidate first, previous main second. Lower is better. Improvement % is `100 × (previous main − candidate) / previous main`; positive is favorable.

| Measured 15-second PGR2 window | Previous main | `8ec5e2a` | Improvement |
| --- | ---: | ---: | ---: |
| Texture-binding CPU / guest frame | 4.326 ms | 3.983 ms | **+7.93%** |
| Surface-readback wait / guest frame | 2.589 ms | 2.565 ms | +0.90% |
| Binding minus readback wait / guest frame | 1.737 ms | 1.418 ms | **+18.39%** |
| Mean guest-frame interval | 34.281 ms | 34.108 ms | +0.50% |
| p95 guest-frame interval | 40.679 ms | 40.027 ms | +1.60% |
| p99 guest-frame interval | 44.549 ms | 44.919 ms | -0.83% |

This matched run shows CPU work removed without merely relabeling the readback wait. It does not establish a broad frame-tail PASS. The final head's uninstrumented 30-second PGR2 fresh start admitted 900 guest frames at mean 33.333 ms, p95 33.652 ms, p99 34.554 ms, maximum 38.534 ms, with zero intervals ≥75 ms.

The first matched, uninstrumented Morrowind 15-second snapshot pair used the same snapshot and input sequence, candidate first. It records an NV2A display-write cadence proxy, not displayed FPS.

| Morrowind display-write interval | Previous main | `8ec5e2a` | Improvement |
| --- | ---: | ---: | ---: |
| Mean | 41.715 ms | 42.076 ms | -0.86% |
| p95 | 47.679 ms | 48.671 ms | **-2.08%** |
| p99 | 55.160 ms | 53.989 ms | +2.12% |

Both runs admitted active gameplay and cleaned their private disks. The short p95 signal is adverse, while p99 favors the candidate; a longer paired run is needed before a performance decision.

The first 159-record full XISO image from test source `74013c3` aborted after 78 complete records, immediately after the new palette-DMA leaf passed, at the shared `palette_offset < palette_dma_len` assertion. Previous main reproduced the **same assertion at the same test boundary**, so it is a guest test-sequence problem rather than a PR #80 regression. Test source `457deac` restores non-paletted texture/DMA state at teardown without weakening the pixel oracle. Its XISO SHA-256 is `ecfa6dee7d3f4eb1dcfabf9ab9b29f137c2641d25ad961382da12cd035a5d30e`; a full run still aborted at the same 78-record boundary; further guest-state teardown repair is pending. The separate inherited `report_query.dma_range_guard` failure remains tracked by [xemu#60](https://github.com/Mainkill1/xemu/issues/60).

The machine-readable current-head cells and exact source/build identities are in [results.json](results.json). This PR remains **draft/HOLD** until the latest full XISO and longer Morrowind comparison are resolved. Earlier candidate/diagnostic sections below are retained as historical evidence and do not qualify this head.

---

The first candidate removes redundant texture-binding and fragment-uniform work. It is **on hold**: two short, order-reversed Morrowind snapshot pairs have worse p95 display-write intervals. The cause is not yet attributed. This is an interim, exact-build diagnostic record, not performance acceptance or release qualification.

| Identity | Value |
| --- | --- |
| Product issue / draft PR | [xemu#79](https://github.com/Mainkill1/xemu/issues/79) / [xemu#80](https://github.com/Mainkill1/xemu/pull/80) |
| Candidate source / tree | `7bd80f659aff92b58ddacc4d164612730d815a36` / `fc44211b2a05723606ca933212d17aae679c8fd9` |
| Candidate Windows Release executable SHA-256 | `6de75eecc0b768ea9f041b5920d2d91d0807ae3b14c7720a51ae93ae7be2cacf` |
| Previous-main reference | current `main` `5edff26383c6440da35bc92b9fca35f4a404b03b`; executable source `a08c4d92916554f55f09231f525cda1f93b55129` has the same tree `11981a736703553349357cd89926b443901cadb9` |
| Previous-main executable SHA-256 | `91ca72bddb6ec21441ffbbf3ef5bdddeda84ab3b7768d1f29081dca07136c4b3` |
| Fixed cycle baseline | `9f618d6d8c4c446ef023955f3d4de22f661f61a4`; retained historical results, no rebuild |
| XISO image / test source | `a8f07817b9f1b22ef93ea54497ddfc9f06d34147d734e4ed26a8bcb69c7e8687` / `0bb7618aec5ea73355a03bcb176a922ea8b3ec2e` |
| Build | Windows Release, full LTO, x86-64-v3; pinned Docker toolchain digest `09fdc183…` (full build manifest retained with the run) |
| Host and renderer | Windows test box `10.0.7.1`, Vulkan; the retained configuration and snapshot were used for each pair |

The machine-readable, path-sanitized per-run records are in [results.json](results.json). Each PGR2 run was 15 seconds and admitted guest progression. Vulkan per-guest-frame telemetry was enabled; PresentMon and scheduler ETL were off. The six selected texture XISO cases passed their framebuffer oracles with zero reported Vulkan VUIDs. Focused unit cases passed 9/9. A first XISO attempt failed a harness manifest preflight (`SOURCE_STATE=candidate` instead of `clean`); the executable and source were unchanged, the manifest was corrected, and the accepted run passed. That infrastructure failure is not counted as an xemu failure.

Improvement is `100 × (previous main − candidate) / previous main` for these lower-is-better durations. The A and B columns are separate pairs, with candidate-first and main-first order respectively.

| Workload | Metric | Pair A improvement | Pair B improvement |
| --- | --- | ---: | ---: |
| PGR2 Vulkan snapshot | pipeline preparation CPU ms/guest frame | +9.224% | +6.166% |
| PGR2 Vulkan snapshot | mean guest interval | +0.785% | +1.901% |
| PGR2 Vulkan snapshot | p95 guest interval | +2.585% | +4.451% |
| PGR2 Vulkan snapshot | p99 guest interval | -1.422% | +4.813% |
| Morrowind Vulkan snapshot | mean display-write interval | -0.575% | -2.031% |
| Morrowind Vulkan snapshot | p95 display-write interval | **-4.351%** | **-5.988%** |
| Morrowind Vulkan snapshot | p99 display-write interval | +0.190% | -1.751% |

The Morrowind metric is an NV2A display-write cadence proxy, **not displayed FPS**. Each run confirmed QMP running, Start/B input, image transition, display-write progression, and private-HDD cleanup. Individual screenshot hashes differ, so these short windows do not establish frame-exact workload identity. The prior PGR2 shader-binding profile identifies an opportunity, but its instrumentation was on a different product head; PR #80's schema-5 telemetry measures pipeline preparation and texture binding, not the `pgraph_vk_bind_shaders()` wrapper directly.

A third 15-second Morrowind pair, with Vulkan frame telemetry enabled, measured p95 `49.133 → 48.241 ms` (**+1.815%**) from previous main to candidate. That reverses the adverse p95 direction in the first two pairs, so the short-window signal is not stable. Telemetry changes the measurement conditions and this third pair cannot simply be averaged with the first two.

| Measured-window Vulkan work per guest frame | Previous main | Candidate |
| --- | ---: | ---: |
| Texture binding CPU | 0.764 ms | 0.766 ms |
| Pipeline preparation CPU | 2.372 ms | 2.171 ms |
| Descriptor update region CPU, including any finish | 10.333 ms | 2.528 ms |
| Buffer-space finish submits | 1.000 | 0.196 |
| Surface-down finish submits | 0.805 | 0.804 |
| Sampled buffer-space fence wait | 9.761 ms | 2.006 ms |
| Sampled surface-down fence wait | 0.861 ms | 8.393 ms |
| Total sampled waits across all finish reasons | 12.732 ms | 12.372 ms |
| Vulkan queue submits | 6.335 | 5.724 |

These counters show a **wait-ownership shift**: avoiding descriptor changes usually avoids a buffer-space finish, while the next surface-down operation encounters the GPU wait. The total sampled wait remains close. The worst individual display-write intervals in both builds coincide with fence waits; their pipeline-preparation time stays near 2.1–2.7 ms. This supports a batching/wait-location explanation for variable frame tails and does not identify increased shader-binding CPU cost as the Morrowind cause. Matching uses Windows QPC to align the renderer's monotonic frame timestamps with UTC display-write timestamps; the matched frame precedes the corresponding display write by about 7–8 ms, consistently within each run. These diagnostic runs are not uninstrumented performance acceptance.

The longer, **uninstrumented 30-second Morrowind pair** completed on the same executable hashes with `main → candidate` order and 730/731 measured display-write intervals:

| Lower-is-better interval | Previous main | Candidate | Improvement |
| --- | ---: | ---: | ---: |
| Mean | 41.050 ms | 40.956 ms | +0.231% |
| p95 | 47.740 ms | 47.953 ms | -0.446% |
| p99 | 53.009 ms | 52.905 ms | +0.196% |
| Maximum | 58.404 ms | 59.921 ms | -2.597% |

Both runs passed active-gameplay admission and had zero intervals ≥75 ms. This longer pair does not reproduce the original >2% p95 loss, but a single pair cannot establish that the tail is universally unchanged. The worst single interval also remains variable. The appropriate disposition is **no reproduced persistent p95 regression in the longer window**, with final acceptance tied to the broader candidate qualification and its retained host conditions. The diagnostic wait-shift evidence remains useful for interpreting future tails; changing synchronization solely to restore the old finish-reason label is not justified.

The fixed published baseline from [PR #70's retained qualification](../pr70-spirv-prewarm-20260910/current-main-qualification/REPORT.md) has Morrowind Vulkan snapshot mean 40.903 ms, p95 47.413 ms, p99 52.773 ms. The 30-second candidate differs by -0.129%, -1.139%, and -0.250% improvement respectively, but that historical comparison has a different run session and window length; the paired previous-main result is the incremental test. No baseline executable was rebuilt.

The candidate's complete **157-record Vulkan XISO** run emitted 156 PASS and one FAIL, with zero reported VUIDs and the configured framebuffer-hash validation passing. The failure is `report_query.dma_range_guard`: the later valid B0 report remains at its sentinel after a rejected A1 destination. An exact-test previous-main control on the retained executable emitted the **same FAIL and byte-for-byte same A0/A1/B0/B1 record values**, also with intact range canaries and zero VUIDs. The parent runner needed `--allow-dirty-build` because its historical manifest says `SOURCE_STATE=clean-archive`; the executable SHA and source tree were verified and the control is used for correctness attribution only, never performance. The product candidate does not change report code. [xemu issue #60](https://github.com/Mainkill1/xemu/issues/60) already documents this inherited Vulkan publication gap and its rejected draft repair; no duplicate issue is needed.

| XISO gate | Candidate | Previous-main control | Attribution |
| --- | ---: | ---: | --- |
| Complete 157-record catalog | 156 PASS / 1 FAIL | Not rerun in full | One known report-query failure prevents a suite PASS |
| `report_query.dma_range_guard` | FAIL | **same FAIL and records** | Inherited from previous main |
| Six texture-focused leaves | 6 PASS | Existing functional oracle | Changed texture path admitted |
| Vulkan validation | 0 VUIDs | 0 VUIDs in targeted control | No reported validation issue |

This is **not** a 157/157 qualification claim. The sanitized full 157-row result set and parent-control record are in [results.json](results.json). The guard's ~12-second failure timeout is a correctness-test duration and is excluded from performance conclusions.

PGR2 Vulkan fresh start completed twice per build, with the default fixed input sequence, 5-second warmup and then 60-second or 30-second uninstrumented measured windows. Functional and measurement admission passed; both builds stayed at approximately 30 guest frames/s with zero ≥75-ms stalls. The first pair ran previous main then candidate; the second reversed the order.

| Fresh-start window | Metric | Previous main | Candidate | Improvement |
| --- | --- | ---: | ---: | ---: |
| 60 seconds | Mean interval | 33.333 ms | 33.333 ms | ~0.000% |
| 60 seconds | p95 | 33.625 ms | 33.601 ms | +0.071% |
| 60 seconds | p99 | 34.095 ms | 34.141 ms | -0.135% |
| 60 seconds | **Maximum** | **37.799 ms** | **44.508 ms** | **-17.749%** |
| 30 seconds, reverse order | p95 | 33.631 ms | 33.639 ms | -0.024% |
| 30 seconds, reverse order | p99 | 34.284 ms | 34.493 ms | -0.610% |
| 30 seconds, reverse order | **Maximum** | **38.648 ms** | **47.337 ms** | **-22.482%** |

The candidate's largest interval occurs near the **start** of each measured window (frames 8 and 1); the rest of each distribution is much closer. This tail follows the candidate across run order. It is an unresolved **performance HOLD** even though p95/p99 are near neutral and the isolated PGR2 snapshot's pipeline-preparation CPU improved. A 15-second fresh-start telemetry pair is in progress to attribute the early interval before proposing any change. The inherited #60 XISO failure is separately recorded; it does not explain these frame intervals.

### Clean-stage diagnostic follow-up

At diagnostic head `26b9d96f2c`, texture preparation called `create_texture()` about 4,125 times per guest frame, including about 2,321 clean-stage calls. The narrow clean-stage skip at `b5aea97cc9` reduced this to about 2,218 calls per guest frame in an unpaired 15-second PGR2 capture. Both captures used opt-in Vulkan telemetry. This establishes eliminated work, not an end-to-end speedup.

Six focused texture XISO leaves passed at `b5aea97cc9`, with zero reported VUIDs and the expected framebuffer hashes. A read-only review then found that a changed DMA A/B source could evade the skip on a clean stage. Commit `9ff26f8871` adds DMA-change invalidation and a current-source check; this later head requires its own production-path DMA test and performance assessment. The same-handle RAMIN descriptor rewrite remains an inherited fast-path gap when no other stage triggers a slow bind.

Two **uninstrumented** 30-second PGR2 fresh-start pairs at `b5aea97cc9` had opposite execution orders and zero intervals ≥75 ms:

| Order | Previous-main p95 / p99 / max (ms) | Candidate p95 / p99 / max (ms) |
| --- | ---: | ---: |
| main → candidate | 40.379 / 43.748 / 56.721 | 33.668 / 36.446 / 50.260 |
| candidate → main | 33.642 / 34.086 / 45.441 | 33.730 / 38.556 / 49.771 |

The first executable of each pair had worse p99/max, regardless of identity. The candidate's reverse-pair tail was also adverse. These pairs do not prove a reliable performance gain, and PR #80 remains on hold. Exact per-run rows and source/executable hashes are in `results.json`.

### What the long texture-binding interval contains

The PGR2 Vulkan schema-5 captures can be divided by the recorded per-frame `surface_download` fence wait. `create_texture()` may request a surface download when the texture source overlaps a GPU-authoritative surface, and that download can block while the GPU finishes. The mean wrapper increase in the first main/candidate capture was 1.696 ms per guest frame; the corresponding readback wait increased by 1.652 ms. Six readback submissions occurred per guest frame in each capture.

| Build | `bind_textures` ms/frame | Surface-readback wait ms/frame | Difference | Frame-level correlation |
| --- | ---: | ---: | ---: | ---: |
| Previous main, first capture | 2.098 | 1.064 | 1.033 | 0.989 |
| Initial candidate `7bd80f6` | 3.794 | 2.716 | 1.078 | 0.935 |
| Previous main, repeat | 2.465 | 1.432 | 1.033 | 0.996 |

All 1,335 measured guest frames in those captures had a surface-readback wait no larger than the texture-binding wrapper duration. The nearly unchanged difference supports wait placement as the leading explanation for the wrapper delay. It does not prove that every readback was nested in the wrapper, nor that the candidate increased GPU work.

Commit `91f033d69b` is a **diagnostic only** override on top of `9ff26f8871`; it restores previous-main's unconditional descriptor/uniform update cadence after a slow bind. The two builds differ only in that cadence. Same-schema 15-second PGR2 captures in both orders found:

| Order | Build | `bind_textures` ms/frame | Readback wait ms/frame | Difference | Total sampled wait ms/frame |
| --- | --- | ---: | ---: | ---: | ---: |
| First | `9ff26f` selective cadence | 4.110 | 2.346 | 1.764 | 9.696 |
| Second | `91f033` prior cadence | 2.945 | 1.224 | 1.721 | 9.350 |
| First | `91f033` prior cadence | 2.815 | 1.093 | 1.723 | 9.245 |
| Second | `9ff26f` selective cadence | 3.140 | 1.402 | 1.739 | 9.787 |

The selective cadence moves some observed waiting into the next readback in both orders. Absolute schema-8 microtimed values must not be compared directly with schema-5 previous-main values. Uninstrumented frame results remain the acceptance gate.

The new DMA XISO image from test source `7dc00367` has SHA-256 `d10baeb7daaa885ea62ab3eceec8d3c25718bbe1ebd45f7e0dde4a6ba3269b9c`. Its texture remap leaf passed on `9ff26f`, previous main, **and unpatched `b5aea97`**, so this first version does not distinguish the bug. Its palette remap leaf failed with identical observed KAT on previous main and `9ff26f`; that result is under test-source investigation. Neither leaf currently qualifies the DMA repair. An initial catalog-style test ID was rejected at runner preflight without launching xemu; accepted runs used the exact `Suite::Test` ID.
