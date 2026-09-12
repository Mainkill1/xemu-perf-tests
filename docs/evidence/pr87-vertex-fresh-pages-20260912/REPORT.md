# PR #87: fresh vertex-page writes, focused qualification

**Product:** [Mainkill1/xemu#87](https://github.com/Mainkill1/xemu/pull/87), draft. **Tracking:** [issue #86](https://github.com/Mainkill1/xemu/issues/86). This report measures the exact PR head `d42c81ba32e7c299e4a65f70db05e2ba3363cccc` (tree `1ad8945162e2a8403d63e5f7588dc8d8c2f0827e`; Windows executable SHA-256 `9da192457c4264df3e3025434841c4d72599b47cf673f3a9206416619d24f99b`) against its exact #85 parent `2163208fdc49c7f6b4834bce98e6a11b494d4241` (executable SHA-256 `fdafe9acae32f1a189eff6cd270bdd6443571b7e33f870efaf9bfa1b2a22f0dc`). The fixed cycle baseline is `9f618d6d8c4c446ef023955f3d4de22f661f61a4`; it was not rebuilt.

## Decision from these runs

The new path is active: in a 10-second opt-in Vulkan Morrowind window, 27,642 of 86,007 vertex copies (32.14%) wrote fresh pages directly rather than staging them. The exact candidate then improved **guest display-write cadence** in two order-reversed 60-second Morrowind snapshot pairs by **+6.51% and +5.43%**, with better p95 and p99 intervals in each pair. PGR2 full start was effectively tied at its 30-FPS guest cadence. Both games reached gameplay/race scenes, and their measured runs completed and cleaned up private disks. These results support continued qualification, not a merge yet: full XISO, PGR2 snapshot, OpenGL, Vulkan validation, and a targeted ordered-overwrite oracle remain pending.

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

The remaining 68% of copies still take the ordered staging path. The optimization only bypasses a copy when the page has not been read by an earlier recorded draw in the active command buffer. Before a merge, test a true read-then-overwrite case, command-buffer rollover, surfaces, and buffer generation changes through the production path. Run the full current XISO suite on Vulkan and OpenGL, PGR2 snapshot, and Morrowind OpenGL; check Vulkan validation. There is no evidence yet that the patch improves a driven PGR2 lap or Morrowind map traversal. Keep #87 draft until those gates pass.
