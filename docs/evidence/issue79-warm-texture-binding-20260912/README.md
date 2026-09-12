# Issue #79 / draft PR #80: warm Vulkan texture-binding candidate

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
