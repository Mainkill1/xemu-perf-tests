# PR #104 / #105 qualification

This report compares the exact clean issue #102 build against its previous
main and against the separately proposed PR #104 copy fix. PR #103 is a
diagnostic branch and is not a product-performance candidate.

## Identities and controls

| Role | Source SHA | Win64 executable SHA-256 |
| --- | --- | --- |
| Previous main | `322986f4c5502b3fa887a9605ac8cd88e9b2c579` | `992c5cf7bb25ccfd7d6384ee837c051b31120d227cbc6e0febe8207790e0023e` |
| PR #104 | `c7ad1218a6b3ce3bbbd3c2703a54cac3c5d04109` | `379774b6de338f7ea5a946cd770f51adfff8c5360b9931a1d26f3330e337d5da` |
| PR #105 | `ae95c4433a74ef146b5e018f2f2e45053e9e2894` | `3786c01cc72f0ce946973b9fccecbe289af46185684d319e43b10ae5a4258bde` |
| Fixed cycle baseline | `9f618d6d8c4c446ef023955f3d4de22f661f61a4` | `3489fdcc593e942b92a612bf35a98f509ff0907e3370e1e5f45f2972d83fb16b` |

The retained baseline executable was built from source `c17591d59c270b352b72e648f5ed65e4b2a3e77e`, the runtime source at that baseline. It has not been rebuilt for this investigation.
Older baseline frame-time receipts used 1× scale and different warmup/input
timing. Their values are not used as matched controls here. The retained
baseline executable was run twice with the same settings in this campaign.

The Windows test host has a Ryzen 9 6900HX and NVIDIA RTX 3070 Ti Laptop GPU.
It is **not** the RTX 3090 host on which
the earlier Hybrid-On device loss was reproduced. Source and executable
identities were checked before each run. The retail runs use Vulkan, 4×
surface scale, VSync off, Hybrid On, shader shortcut On, and persistent shader
cache Off. Each run starts from a private copy of the same scene-specific HDD
seed. No WPR or ETL capture runs in this campaign.

Positive improvement means higher FPS or a lower frame interval. A value
below -2% in a repeated tail metric is an adverse signal requiring review.

## Full XISO

The latest available candidate image is `suite-57c2438-20260912`, source
`57c2438c3d46c8f99bc18004f1fd34a5d9ed82b9`, ISO SHA-256
`6a57961a7312bb8ec125181ac5e642d194835df382cbb900c81efaf9765536cd`,
catalog SHA-256
`ea881a43ec71cc37f74e5863e00f0cf4caea94e32933a5a15063e179e743ddfb`.
All three Vulkan runs emitted the expected 162 records (157 leaves, five
groups), and all xemu processes exited normally.

| Role | Guest PASS / total | Non-PASS records | Comparable hashes vs main |
| --- | ---: | --- | --- |
| Previous main | 160 / 162 | `report_query.zero_query`, `report_query.dma_range_guard` | Reference |
| PR #104 | 160 / 162 | `report_query.clear_boundary`, `report_query.dma_range_guard` | 268 / 268 match |
| PR #105 | 159 / 162 | `report_query.zero_query`, `report_query.clear_boundary`, `report_query.dma_range_guard` | 268 / 268 match |

PR #104 versus #105 also matches all 268 comparable functional hashes.
Two queued same-address S3TC framebuffer observations are deliberately
ineligible for comparison in the guest oracle; their work/result checksums
match. The report-query failure set moves among runs. The `clear_boundary`
final recorded values are the same in the main PASS and candidate FAIL
cells, but this leaf repeats internally, so the final record does not erase
an earlier failed sample. The range-guard failure is present on all three.
These are real non-PASS outcomes and are not called a full-suite PASS.

The exact release binaries do not emit the optional live-marker path requested
by this runner. Its compatibility waiver allowed complete correctness and
hash capture, but **guest timing is not PR-grade performance evidence**.
The per-test values and outcomes are retained in [xiso-per-test.csv](xiso-per-test.csv);
it includes positive-good improvement calculations for comparable PASS leaves,
but they should not be read as qualified speed comparisons. Vulkan validation was
not enabled in this timing run, so zero reported VUIDs would have no meaning.

## Retail frame pacing

The PGR2 snapshot bracket is complete in this order: main, #104, #105,
#105, #104, main. Each cell uses a 30-second warmup and a 60-second measured
window. The retained baseline was captured twice with matching settings. The
values below are the mean of two per-run values; individual cells are in
[retail-per-run.csv](retail-per-run.csv).

| PGR2 snapshot | Raw + | Main | PR #104 | Improvement vs main | PR #105 | Improvement vs main | Improvement vs #104 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| FPS | `+good` | 29.412 | 29.665 | +0.86% | 29.589 | +0.60% | -0.26% |
| Mean interval, ms | `+bad` | 33.994 | 33.703 | +0.85% | 33.780 | +0.63% | -0.23% |
| p95, ms | `+bad` | 39.255 | 38.721 | +1.36% | 39.028 | +0.58% | -0.79% |
| p99, ms | `+bad` | 43.558 | 42.184 | +3.15% | 43.073 | +1.11% | **-2.11%** |

| PR #105 vs fixed baseline, PGR2 snapshot | Baseline | PR #105 | Improvement |
| --- | ---: | ---: | ---: |
| FPS | 29.452 | 29.589 | +0.46% |
| Mean interval, ms | 33.948 | 33.780 | +0.50% |
| p95, ms | 40.179 | 39.028 | +2.87% |
| p99, ms | 43.460 | 43.073 | +0.89% |
| Maximum, ms | 56.929 | 91.994 | **-61.59%** |

The first and last main controls diverged substantially (29.801 versus
29.022 FPS; p99 42.059 versus 45.057 ms). This run-order movement prevents a
clean main-versus-candidate improvement claim from this bracket alone. The
per-run maximum intervals are main **61.583/54.446 ms**, PR #104
**48.891/52.663 ms**, and PR #105 **57.579/126.409 ms**. The last #105 cell
has one frame at or above 75 ms; the others have none. A nearby host
presentation gap and GPU-active interval were observed, but no scheduler or
GPU command attribution was captured, so the isolated 126 ms event remains
unexplained. Its existence and the #105-vs-#104 p99 result prevent a
performance PASS at this stage.

The Morrowind snapshot bracket also completed in main, #104, #105, #105,
#104, main order, with two same-settings baseline controls. The fixed camera
showed the same active scene on screenshot inspection; this is not a map
traversal. GPU telemetry for the six main/#104/#105 runs stayed at P0 and
1785 MHz, with 43.63–44.03% GPU utilization. The candidate's mean FPS is
slightly below main and 2.72% below #104; its p99 is essentially equal.

| Morrowind snapshot, two-run mean | Raw + | Baseline | Main | PR #104 | PR #105 | Improvement vs main | Improvement vs #104 | Improvement vs baseline |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| FPS | `+good` | 28.500 | 28.312 | 28.963 | 28.175 | -0.49% | **-2.72%** | -1.14% |
| Mean interval, ms | `+bad` | 35.068 | 35.336 | 34.534 | 35.487 | -0.43% | **-2.76%** | -1.19% |
| p95, ms | `+bad` | 50.002 | 49.998 | 49.962 | 50.002 | -0.01% | -0.08% | 0.00% |
| p99, ms | `+bad` | 50.040 | 50.046 | 50.034 | 50.049 | -0.01% | -0.03% | -0.02% |
| Maximum, ms | `+bad` | 50.931 | 50.450 | 50.413 | 58.519 | **-15.99%** | **-16.08%** | **-14.90%** |

The first full-start main control was spotchecked during its measured window and then
interrupted, so it is excluded. A separate short main preflight exited with
`VK_ERROR_DEVICE_LOST`; a 20-second exact PR #105 preflight completed. Neither
is treated as a matched performance cell. In the repeated full-start campaign,
both main runs and both PR #104 runs exited before measurement with
`VK_ERROR_DEVICE_LOST`. These are functional failures, not zero-FPS samples.

| PGR2 full start, two runs per role | Baseline | Main | PR #104 | PR #105 |
| --- | ---: | ---: | ---: | ---: |
| Completed 120-second captures | 2 / 2 | 0 / 2 | 0 / 2 | **2 / 2** |
| Pre-measurement Vulkan device loss | 0 / 2 | 2 / 2 | 2 / 2 | **0 / 2** |
| Guest frames per completed capture | 3,602 / 3,602 | N/A | N/A | 3,602 / 3,602 |
| p99 interval, ms | 34.326 / 34.332 | N/A | N/A | 33.842 / 33.800 |
| Maximum interval, ms | 36.540 / 35.400 | N/A | N/A | 40.383 / 41.000 |
| Guest intervals ≥75 ms | 0 / 0 | N/A | N/A | 0 / 0 |

There is no matched full-start FPS comparison against previous main or PR #104
because neither survived to measurement on this host. Relative to the retained
baseline, PR #105's two-run mean p99 improved +1.48%, while its maximum was
13.13% worse. Both ran at the game's roughly 30 FPS cap.
FPS and frame intervals come from guest frame and flip logs; PresentMon is host
presentation context only.

### Full-start boot and loading

The launcher sets frame/flip/event log paths before starting xemu. The exact
PR #105 and baseline full-start controls had persistent shader cache disabled.
Frame logging began about 24.7–24.9 seconds before the first scripted key;
host presentation telemetry starts later, at the steady-state window. The
phase split uses the monotonic frame timestamps anchored to that window and
actual input event timestamps. Compact per-run results are in
[cold-load-per-run.csv](cold-load-per-run.csv). The pre-input phase includes
boot and menu idle, input navigation includes scripted menu work and loading,
and the final phase is the 120-second in-game window.

| Full-start phase, two runs | Baseline | PR #105 | Interpretation |
| --- | ---: | ---: | --- |
| First logged frame to first input | 24.885 / 24.880 s | 24.722 / 24.791 s | Small difference; not a material boot improvement |
| First to last scripted input | 36.826 / 36.878 s | 36.782 / 36.802 s | Essentially unchanged |
| Largest no-frame interval during input/navigation | 3474.992 / 3470.012 ms | 3496.479 / 3487.001 ms | **Loading pause not improved** |
| Post-input warmup p99 | 42.446 / 42.100 ms | 42.334 / 37.637 ms | Mixed, small sample |
| In-game capture p99 | 34.326 / 34.332 ms | 33.842 / 33.800 ms | +1.48% two-run mean improvement |

The approximately 3.5-second no-frame gap is a loading event, not an
identified shader compilation. The tested configuration has shader caching
off, but the trace does not attribute the gap to a particular operation.

## Disposition

**HOLD, not a clean performance PASS.** PR #105 survived two full-start runs
that crashed on previous main and PR #104, and its PGR2 snapshot and full-start
p99 values are near or better than the retained baseline. The single 126.409 ms
snapshot spike, Morrowind slowdown against #104, and real XISO report-query
non-PASS outcomes remain. The earlier RTX 3090 played-race survival result
applies to a different diagnostic executable. This clean binary has not been
proven on the original RTX 3090 host. PR #104's specific copy validation
repair is supported, but its device loss remains. PR #103 remains a diagnostic
branch, not a performance candidate.

The later [PGR2 race-to-menu corruption report](https://github.com/Mainkill1/xemu/issues/106)
is a separate correctness gate. These captures end in active gameplay; none
exit a race and inspect the resulting menu. Their passing scene checks and
matching XISO hashes cannot qualify that transition.

## September 15 exact-head review repeat

The reviewed PR heads were rebuilt with the pinned Win64 O2/LTO/x86-64-v3 toolchain and run on the Windows RTX 3070 Ti host. PR #104's BC layout test passes 4/4. PR #105 passes BC layout 4/4, compiled staging-copy ordering 2/2, generated ubershader source 6/6, and glslang/reflection 2/2.

The three disputed report-query records were then repeated three times per role:

| Role | `zero_query` | `clear_boundary` | `dma_range_guard` |
| --- | ---: | ---: | ---: |
| Previous main | 3/3 PASS | 3/3 PASS | 0/3 PASS |
| PR #104 | 2/3 PASS | 3/3 PASS | 0/3 PASS |
| PR #105 | 3/3 PASS | 3/3 PASS | 0/3 PASS |

The failures do not track either patch: the boundary case now passes all roles, the zero-query result varies between executions, and the DMA guard fails identically on unchanged main and both candidates. This clears the review's patch-attribution question while retaining the report-query defect as separate unresolved evidence. [Exact-head protocol and normalized cells](query-repeat-exact-head/README.md).
