# PR #89 coherency-stack repair: exact-head qualification

**Status:** Draft. [Product PR #89](https://github.com/Mainkill1/xemu/pull/89) is stacked on repaired [#87](https://github.com/Mainkill1/xemu/pull/87) and [#85](https://github.com/Mainkill1/xemu/pull/85). This report supersedes the **source identities**, not the retained historical measurements, in the [earlier PR #89 report](../pr89-vulkan-vertex-versions-20260912/REPORT.md).

| Role | Source commit | Tree | Win64 executable SHA-256 |
| --- | --- | --- | --- |
| #85 correctness parent | `8d9245ddeb5f13d23a5e3f2aafdb5144c4bdad30` | `4330ee6b527dc43b910d0038476f50c26b6b4267` | `0c0e11d66e5a2b0b75fad38c8bb5acf88b5291b1115a47c6ba501f262fce313d` |
| #87 exact comparison parent | `3fa5a650e108c12d2106a43450f375fefb5ddf6e` | `6fe4be95a1f38a19c67005023b059169d77f03ab` | `ea6d5dc552d71817bd7acc9ad025420ac2d087031b69c2cebd3f944db1995ed0` |
| #89 candidate | `7a159370143566e723cccd8b2ab5018b3b9d70df` | `a19c01fdb566ddd62536ae983be185714f4d964b` | `f2317a7ac7eb1009ccf9788ad76c6ed4c2dc9bdc0b6df986b5828eebb9e405dc` |
| Fixed cycle baseline | logical `9f618d6d8c4c446ef023955f3d4de22f661f61a4`; compiled `c17591d59c270b352b72e648f5ed65e4b2a3e77e` | retained build | `3489fdcc593e942b92a612bf35a98f509ff0907e3370e1e5f45f2972d83fb16b` |

The Win64 builds used the pinned `ghcr.io/xemu-project/xemu-win64-toolchain-gcc@sha256:09fdc183a88b493bf3a98d0d00b03aca4d5a23e60cc08228d7752d3c3295e8b2` toolchain and recompiled all changed Vulkan objects before each link. A [source and binary audit](BUILD-AUDIT.md) found matching `-O2`, LTO, debug-information, and x86-64-v3 compiler settings in the main control and #89 executables; “Release” versus “debug” build labels did not reflect an optimization mismatch. The builder's overlay procedure did not retain a full per-link source-tree digest, so exact-tree build attestation remains a qualification gap. The new guest ISO has SHA-256 `e9b7996a2521a1b35c36fae074027240944dcc4d8625c131ee3d05d8367cb430`; catalog SHA-256 is `6bd53cf672ba80051dfb677f187da76e362a399412b1acd005c920829a7bbdd5`. Its source is [the three-generation test PR](https://github.com/Mainkill1/xemu-perf-tests/pull/37) at `9270fbab40bb8beb3cc5c9ce2ca32ce10e960e29` and it contains 161 records. The guest build used pinned NXDK `73c95900965a16be3a3e34b8d4d5d41bc18498be`.

## Code and focused proof

PR #85 now bounds the actual strided vertex fetch with inclusive DMA and exclusive VRAM rules, downloads overlapping GPU-authored surfaces before CPU inline-value decoding, and dirties the full swizzled readback extent. PR #87 retains fresh-page direct writes on that corrected parent. PR #89 now accepts exact DMA-limit fits, clears stale metadata after a full mirror refresh, and captures version bytes into bounded scratch **before** staging reservation or pre-draw preparation can finish the active command buffer.

The Win64 Release build passed for all three exact heads. The production-header fetch-span unit passed 2/2 cases and the version-policy unit passed 3/3 cases. The focused `XemuVertexRamThreeGenerations` guest test passed on the forced-build #89 executable with framebuffer hash `05e2405b56d7f125`, zero Vulkan VUIDs, and opt-in telemetry recording **1,028 versioned draws / selected ranges**. It checks red, green, and blue generations from the same allocation plus untouched background. Earlier fixture-development attempts selected zero versions and are excluded from this proof.

## Complete XISO comparison

All cells used the same image, catalog, runner revision, scale 1, zero warmup iterations, and per-iteration completion. Vulkan validation was active only for correctness; these one-off medians are directional observations, not performance acceptance. **Improvement % is positive when a lower duration is better (`+bad`).** [All 322 per-test rows](results/comparison.csv) retain raw medians, outcomes, comparison-eligible hashes, and Improvement % for tree-equivalent current `main` → #85 → #87 → #89.

| Renderer | Main / #85 / #87 / #89 passes | Three-generation oracle | Eligible outcome/hash changes | VUIDs | Timed leaves | #85 vs main median Improvement | #87 vs #85 | #89 vs #87 |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Vulkan | 160/161 each | PASS at all heads | 0 at all steps | 0 at all heads | 155 | **-0.99%** | **-0.14%** | **-0.23%** |
| OpenGL | 159/161 each | PASS at all heads | 0 at all steps | N/A | 154 | **-1.10%** | **+1.17%** | **-0.56%** |

The inherited `report_query.dma_range_guard` failure remains on both renderers; OpenGL also retains `texture_cubemap_fallback.unbordered_subblock_dxt1`. Two same-address queued texture leaves can produce different framebuffer hashes because their unsynchronized per-draw source generation is intentionally undefined. The catalog marks those two leaves comparison-ineligible; their outcomes still match. Every **eligible** hash matches at all three steps. The [comparison script](compare_xiso_161.py) reads the normalized data and applies that eligibility rule. These PRs change Vulkan paths, yet OpenGL's isolated medians swing from -1.10% to +1.17% to -0.56%. That is direct evidence of run variation in one-off XISO timings; no broad performance claim follows from the median signs alone.

The retained baseline executable was also attempted with the new 161-record ISO on each renderer, without rebuilding it. Both attempts reached its existing PFIFO inline-packet assertion during the suite and emitted an incomplete guest JSON result (zero accepted records). No 161-record baseline timing or outcome is claimed. Historical fixed-baseline game metrics remain separate, and baseline comparisons must use genuinely comparable work.

The exact pre-#85 `main` commit is `9148241de690617ac0a21a26b41858585c1e3cab`, distinct from that fixed baseline. Its tree `2301f1cc976f93e5a943e065c4e12e034f33869f` is identical to the tested PR #80 head `6bf9e98cdee50fd73e936ff2bd5b485ce14ac4dc`. The retained Windows Release/full-LTO executable has SHA-256 `6857240d6e95909d591832685c60e376611924d00a9688da4d7d2b89e84c17f6`, verified against its build manifest and file bytes. It is a source-equivalent exact-`main` control without a new build; its 161-record suite and matched Morrowind and PGR2 snapshot comparisons are complete. A separate one-time comparison build attempt was blocked because the dedicated builder's root filesystem was full and Docker could not create a container snapshot. It produced no executable or result; the temporary attempt was removed and the shared source checkout verified unchanged.

## Morrowind fixed-scene snapshot

The [four completed cells](results/morrowind-abba.json) used the same snapshot, automated input, 60-second measurement window, Vulkan renderer, and individually cloned disks. Guest display-write cadence is a guest-progress proxy, not displayed FPS. The first setup attempt is excluded: its nonstandard executable basename prevented the runner from identifying its own xemu process. After correcting that harness mismatch, every included cell completed, passed final-image validation, and removed its private disk.

| Order | Metric | Raw + | #87 parent | #89 candidate | Improvement % |
| --- | --- | --- | ---: | ---: | ---: |
| A1 → B1 | Guest display writes/s | `+good` | 25.619 | 26.210 | **+2.31%** |
| A1 → B1 | Guest interval p95 | `+bad` | 46.279 ms | 45.065 ms | **+2.62%** |
| A1 → B1 | Guest interval p99 | `+bad` | 52.871 ms | 51.592 ms | **+2.42%** |
| B2 → A2 | Guest display writes/s | `+good` | 25.154 | 27.778 | **+10.43%** |
| B2 → A2 | Guest interval p95 | `+bad` | 46.799 ms | 43.648 ms | **+6.73%** |
| B2 → A2 | Guest interval p99 | `+bad` | 52.937 ms | 50.979 ms | **+3.70%** |

Both orders favor #89, but their effect sizes differ substantially. The scene is fixed-camera; this does not establish a traversed-map result or a display-present FPS gain. The historical fixed-baseline Morrowind p95/p99 medians, 47.413/52.773 ms, came from a different session and are descriptive reference values only.

## #87 versus #85: Morrowind incremental control

The [separate four-cell ABBA series](results/pr87-morrowind-abba.json) compared the repaired #87 head with its exact #85 parent on the same fixed snapshot and 60-second automated-input window. Every cell completed, passed image validation, and deleted its private disk.

| Order | Metric | Raw + | #85 parent | #87 candidate | Improvement % |
| --- | --- | --- | ---: | ---: | ---: |
| A1 → B1 | Guest display writes/s | `+good` | 24.022 | 25.488 | **+6.10%** |
| A1 → B1 | Guest interval p95 | `+bad` | 49.295 ms | 45.735 ms | **+7.22%** |
| A1 → B1 | Guest interval p99 | `+bad` | 56.396 ms | 52.099 ms | **+7.62%** |
| B2 → A2 | Guest display writes/s | `+good` | 24.435 | 24.893 | **+1.87%** |
| B2 → A2 | Guest interval p95 | `+bad` | 48.170 ms | 46.096 ms | **+4.31%** |
| B2 → A2 | Guest interval p99 | `+bad` | 53.421 ms | 54.631 ms | **-2.27%** |

Cadence and p95 favor #87 in both orders, but p99 changes direction and the second pair crosses a 2% adverse threshold. These four cells do not prove a stable tail benefit for #87. Keep the mixed result visible when judging the stack; a one-off favorable first pair should not erase the adverse second pair.

## #85 versus current main: Morrowind incremental control

The [four-cell ABBA series](results/pr85-morrowind-abba.json) used the tree-identical PR #80 executable as the immediate previous-`main` control. The same snapshot, input, 60-second window, image check, and private-disk cleanup applied in every cell.

| Order | Metric | Raw + | Main control | #85 candidate | Improvement % |
| --- | --- | --- | ---: | ---: | ---: |
| A1 → B1 | Guest display writes/s | `+good` | 24.413 | 23.683 | **-2.99%** |
| A1 → B1 | Guest interval p95 | `+bad` | 47.841 ms | 49.481 ms | **-3.43%** |
| A1 → B1 | Guest interval p99 | `+bad` | 55.291 ms | 54.794 ms | +0.90% |
| B2 → A2 | Guest display writes/s | `+good` | 23.737 | 24.042 | **+1.28%** |
| B2 → A2 | Guest interval p95 | `+bad` | 48.579 ms | 48.333 ms | +0.51% |
| B2 → A2 | Guest interval p99 | `+bad` | 55.074 ms | 54.914 ms | +0.29% |

Cadence and p95 reverse direction with order; the first pair has a material adverse movement, the second a small favorable one. P99 is slightly favorable in both. This does **not** establish a positive standalone #85 performance effect; nor does one adverse pair alone prove a stable regression. The correctness repair still needs its direct surface/readback proof.

The [separate PGR2 snapshot ABBA control](results/pr85-pgr2-snapshot-abba.json) used 30 seconds of warmup and a 60-second measured window per cell. All four runs completed functional and measurement checks. Positive Improvement % means a lower interval than main.

| Run order | Main p95 | #85 p95 | p95 Improvement | Main p99 | #85 p99 | p99 Improvement |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Main → #85 | 38.848 ms | 39.781 ms | **-2.40%** | 42.354 ms | 43.410 ms | **-2.49%** |
| #85 → main | 38.882 ms | 39.357 ms | **-1.22%** | 42.761 ms | 43.296 ms | **-1.25%** |

The repeated adverse p95/p99 direction holds #85's performance gate. Neither the [build audit](BUILD-AUDIT.md) nor these timing cells identifies the runtime operation responsible. The extra per-sync surface-overlap scan and early readback are source-level hypotheses for focused attribution.

## PGR2 full start

The [matched fresh-boot pair](results/pgr2-full.json) used the same clean HDD seed and configuration, a 30-second warmup, and a 120-second measurement window after reaching the race scene. Both cells completed without focus loss or unresponsive samples. They remained at the game's 30-guest-frame/s cap, limiting this workload's sensitivity to throughput gains.

| Metric | Raw + | #87 parent | #89 candidate | Improvement % |
| --- | --- | ---: | ---: | ---: |
| Guest frames | `+good` | 3,602 | 3,601 | Comparable work |
| Guest mean interval | `+bad` | 33.333 ms | 33.333 ms | ~0.00% |
| Guest interval p95 | `+bad` | 33.658 ms | 33.586 ms | **+0.21%** |
| Guest interval p99 | `+bad` | 33.836 ms | 33.968 ms | **-0.39%** |
| Guest maximum interval | `+bad` | 35.889 ms | 34.631 ms | +3.51% |

The single-run maximum and sub-percent tail movements do not establish a PGR2 performance improvement or regression. The fixed cycle baseline's historical full-start p95/p99 medians were 33.482/34.253 ms, from a separate session; these are descriptive, not a same-session comparison.

## PGR2 snapshot

The [matched snapshot pair](results/pgr2-snapshot.json) used the same saved scene, 30-second warmup, and 60-second measurement window. Both cells completed without focus loss or unresponsive samples. This scene is less constrained by the full-start frame cap.

| Metric | Raw + | #87 parent | #89 candidate | Improvement % |
| --- | --- | ---: | ---: | ---: |
| Guest frames | `+good` | 1,772 | 1,775 | Comparable work |
| Guest mean interval | `+bad` | 33.880 ms | 33.812 ms | **+0.20%** |
| Guest interval p95 | `+bad` | 39.312 ms | 39.085 ms | **+0.58%** |
| Guest interval p99 | `+bad` | 43.163 ms | 42.577 ms | **+1.36%** |
| Guest maximum interval | `+bad` | 56.721 ms | 58.268 ms | **-2.73%** |

The single worse maximum needs replication or attribution before it can be called a patch-caused tail regression. The paired mean and percentile movements favor #89, but one order is not a repeatability test.

## Outstanding merge gates

| Gate | Status |
| --- | --- |
| Exact-head Morrowind snapshot ABBA | Complete; both orders favor #89; controlled traversal remains pending |
| Exact-head PGR2 full start and snapshot | Complete; full start effectively neutral at the cap; snapshot p95/p99 favorable, one-run maximum adverse |
| #85 versus immediate previous `main` | Tree-identical retained PR #80 binary verified; full-suite output matches; Morrowind ABBA is mixed and PGR2 snapshot p95/p99 are adverse in both orders; performance hold |
| Candidate build identity | Changed objects and compiler settings verified; whole-tree source digest was not captured at each overlay-build link; exact-checkout rebuild pending |
| #85 direct surface/bounds oracles; #87 rollover; #89 forced finish, stale fallback, and reset | Pending targeted proof |
| Linux/macOS build matrix and submitted independent review | Pending; GitHub reports no checks on these draft heads |
| Complete performance verdict | Held by adverse #85 PGR2 snapshot and incomplete exact-tree attestation; later #89 incremental Morrowind improvement does not erase the parent gate |

This report does not qualify the stack for merge yet. [Issue #86](https://github.com/Mainkill1/xemu/issues/86) remains open for residual ordered work and report-completion behavior.
