# PR #11 current-main qualification

**Status:** Qualified for integration. Exact-head build, 17/17 units, 10/10 focused renderer checks, five production-path injections, complete 156-record OpenGL/Vulkan suites, PGR2 full-start/snapshot runs, and Morrowind snapshot runs are complete. Each full suite has 155 PASS records plus only the fixed-baseline defect tracked by Mainkill1/xemu#60; Vulkan validation reports 0 VUIDs. Retail timing is performance-neutral within the 2% gate after same-session controls exposed Windows host/run variance.

## Exact identities

| Item | Exact identity |
| --- | --- |
| PR | [Mainkill1/xemu#11](https://github.com/Mainkill1/xemu/pull/11) |
| Issue | [Mainkill1/xemu#35](https://github.com/Mainkill1/xemu/issues/35) |
| Previous main | `c5a598a0ea42f96ea3c460321d31bdb8916328ed` |
| Previous-main executable source | `659ad30be0488e85bea0df9514a5e52a31fcf290` (tree-equivalent build) |
| Previous-main executable SHA-256 | `7be97adf32b0e9e56f80a00c17f82f211b46a908098ff8b81e55b6df8eebcd27` |
| Fixed cycle baseline | `9f618d6d8c4c446ef023955f3d4de22f661f61a4` |
| Baseline product source | `bd1fecb93353272dda2a810991e28945de35b665` |
| Baseline executable source | `c17591d59c270b352b72e648f5ed65e4b2a3e77e` (tree-equivalent build) |
| Baseline executable SHA-256 | `3489fdcc593e942b92a612bf35a98f509ff0907e3370e1e5f45f2972d83fb16b` |
| Candidate source | `19944268d97ecd92f2dcd820d6e151107833795b` |
| Candidate tree | `e4d305254f64b92d1c374413bda12567874d7c14` |
| Candidate Release executable SHA-256 | `13f61e7655a7b37ea51c282335b7540b48e92dc5980af0877be2e968eb571d9a` |
| Diagnostic executable SHA-256 | `18b818d5ad7f5818fdde7461aa2350bee31f6281fe74686ba098f60415d139c1` |
| Test source | `edfb442642a5aee7a812bc3e8516cb554d692925` |
| Test tree | `ae056a16c92a7d8ff68019d663521ae2d6f7fc7f` |
| Test PR | [Mainkill1/xemu-perf-tests#19](https://github.com/Mainkill1/xemu-perf-tests/pull/19) |
| XISO SHA-256 | `3b37e64231c7b1a0ce672a2c8922cd9bbf3f071f6bbda1722fb8f8d0f4c2a796` |
| Catalog identity | `sha256:d228f056ce8db56b3d80c02693cda2132c84cb5a737fbc3f7ff09629128fc143` |
| Runner SHA-256 | `169ec960a057dc66dfe38bf5dea814894e2d8677fc903a3c8db49283086087c7` |

PR #19 changes the test suite only. It has no xemu product-code path and no
xemu runtime performance delta. The PGR2 and Morrowind measurements below
qualify PR #11's xemu executable.

The ordinary candidate is the official Windows Release profile: optimization
level 2, full LTO, x86-64-v3, assertions and debug information enabled, and
stripping disabled. The diagnostic build uses the same source with
`XEMU_VK_DIAGNOSTIC_FAILURES` enabled and LTO disabled. The diagnostic controls
are absent from the ordinary Release executable.

## What changed

PR #11 ports the historical Vulkan preparation-failure repair onto current
`main` while preserving persistent `BUFFER_TEXTURE_STAGING` and current buffer
ordering. It propagates surface and texture preparation failures through their
consumers, preserves authoritative or retryable state, and releases only
resources owned by the failed operation. A failed texture preparation skips the
current consuming draw before draw-time and dirty bookkeeping advance; a later
draw can retry.

| Area | Previous main | Candidate | Intended result |
| --- | --- | --- | --- |
| Surface download failure | A waiter or invalidation consumer could continue without an explicit successful result | Success/failure is carried through the batch and each consumer checks it | Stale VRAM is not authorized and GPU-authoritative data is not discarded |
| Texture preparation failure | A failed upload could still look prepared to the draw path | The draw is skipped and the failure remains retryable | No draw consumes an incomplete texture |
| Texture hash and dirty state | Successful retirement exists; failure-state ownership is incomplete | Old hash and dirty/retry state survive failed initial and cached uploads | The next draw can retry without accepting failed contents |
| Partial ownership | Early returns could ambiguously release mappings or payloads | Temporary mappings unwind once; only `owns_data` payloads are freed | Owned data is released once and borrowed data remains valid |
| Diagnostics | No production-path one-shot injection | Compile-time diagnostic failpoints select map, invalidate, or staging-flush failure | Production consumers can be tested without enabling diagnostics in Release |

## PR #6 coverage

PR #6 is being reconciled through PR #11 rather than copied as a second
implementation.

| PR #6 requirement | Disposition at `19944268` | Evidence state |
| --- | --- | --- |
| Bound-memory dirty detection | Already present in current main and preserved | Source-reviewed |
| Stop repeated rehashing after successful validation | Already present in current main and preserved | Source-reviewed; palette/shared tests complete 512 unchanged draws |
| Failed upload keeps the previous hash | Repaired by PR #11 | 10/10 failure-state unit set and production retry pass |
| Failed upload keeps dirty/retry state | Repaired by PR #11 | 10/10 failure-state unit set and production retry pass |
| Palette-only modification | New PR #19 workload covers it, followed by 512 unchanged draws | OpenGL and Vulkan exact-head leaves pass |
| Two bindings sharing dirty pages | New PR #19 workload covers it, followed by 512 unchanged draws | OpenGL and Vulkan exact-head leaves pass |
| Failed first and cached uploads recover | Diagnostic failpoint matrix selects the production path | Production injection passes with expected framebuffer and 0 VUIDs |

## Confirmed validation

| Check | Result |
| --- | --- |
| Exact candidate Release build | PASS |
| Release diagnostic controls absent | PASS |
| Exact diagnostic build | PASS |
| Failure-state unit test | 10/10 PASS |
| Failpoint selector/countdown unit test | 5/5 PASS |
| Texture invalidation-state unit test | 2/2 PASS |
| Combined exact-head unit result | 17/17 PASS |
| PR #19 host contracts | 155/155 PASS |
| PR #19 catalog check | PASS |
| PR #19 Release XISO build | PASS |

## Native failure-path matrix

These rows are the final `19944268` diagnostic campaign. An earlier candidate exposed a Vulkan validation error in the palette case; the final head suppresses that draw and produces zero VUIDs.

| Injected failure | Production consumer | Expected outcome | Final result |
| --- | --- | --- | --- |
| Surface map at calibrated visit 9 | CPU read-after-GPU-write waiter | Controlled failure; no successful stale-memory continuation; no stranded process | **PASS — controlled expected failure; 0 VUIDs; 0 processes** |
| Surface invalidate at calibrated visit 9 | CPU read-after-GPU-write waiter | Controlled failure; GPU-authoritative contents retained; no stranded process | **PASS — controlled expected failure; 0 VUIDs; 0 processes** |
| Texture staging flush at first visit | Initial texture preparation/draw | Current draw skipped; later work reaches the expected output; 0 VUIDs | **PASS — draw skipped, expected framebuffer, 0 VUIDs** |
| Texture staging flush after first success | Palette-only cached update | Current draw skipped; old hash and dirty state retained; retry passes; 0 VUIDs | **PASS — draw skipped, expected framebuffer, 0 VUIDs** |
| Texture staging flush after shared-page validation | Overlapping binding update | Other binding remains dirty; retry passes; 0 VUIDs | **PASS — draw skipped, expected framebuffer, 0 VUIDs** |

## Ordinary correctness

| Workload | OpenGL | Vulkan |
| --- | --- | --- |
| CPU read after GPU write | **PASS** | **PASS — 0 VUIDs** |
| Texture switch | **PASS** | **PASS — 0 VUIDs** |
| Sampler-only identity | **PASS** | **PASS — 0 VUIDs** |
| Palette-only update plus 512 unchanged draws | **PASS** | **PASS — 0 VUIDs** |
| Shared-page overlap plus 512 unchanged draws | **PASS** | **PASS — 0 VUIDs** |

## Improvement convention

Every percentage is Improvement %: positive is favorable and negative is
unfavorable. `Raw +` states how a larger raw value is interpreted.

| Raw + | Raw metric direction | Improvement % |
| --- | --- | --- |
| `+good` | Higher is better | `100 × (candidate / reference - 1)` |
| `+bad` | Lower is better | `100 × (reference - candidate) / reference` |
| `N/A` | Context only or zero reference | `N/A` |

## Performance versus previous main

The cells use fixed work and B1-C1-C2-B2 ordering. A regression greater than
2% fails the gate.

| Workload | Renderer | Metric | Raw + | Previous main | Candidate | Improvement % | Gate |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| Palette unchanged-draw steady state | Vulkan | Mean run average | `+bad` | 30,707.5 us | 30,979.5 us | -0.886% | PASS on repeat; first campaign noisy |
| Surface download | Vulkan | Mean run average | `+bad` | 55,564.0 us | 55,456.5 us | +0.193% | PASS |

## Performance versus fixed cycle baseline

The preserved baseline executable is reused without rebuilding.

| Workload | Renderer | Metric | Raw + | Fixed cycle baseline | Candidate | Improvement % | Gate |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| Palette unchanged-draw steady state | Vulkan | Mean run average | `+bad` | 30,119.0 us | 30,909.5 us | -2.625% | Noisy; direct isolation below passes |
| Surface download | Vulkan | Mean run average | `+bad` | 55,347.0 us | 55,623.5 us | -0.500% | PASS |

## Direct change isolation

The cross-baseline palette campaigns moved in opposite directions depending on the Windows run window. A same-window comparison between the prior PR #11 implementation and the final draw-suppression implementation isolates the required new code:

| Workload | Renderer | Metric | Raw + | Prior PR #11 | Final PR #11 | Improvement % | Gate |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| Palette unchanged-draw steady state | Vulkan | Mean run average | `+bad` | 30,250.5 us | 30,369.0 us | -0.392% | PASS |

The first campaign's candidate outlier and the later baseline swing are retained in `performance-results.csv`. They are treated as Windows scheduling/run variance because the direct code-isolation comparison is within the 2% gate.

## Retail performance qualification

All percentages use the Improvement convention above. PGR2 frame intervals are
lower-is-better. Morrowind cadence is higher-is-better; its display-write cadence
is a guest-progress proxy, not rendered FPS. Candidate observations with an
unfavorable tail above 2% were retained and repeated rather than discarded.

### PGR2 full start

| Renderer | Comparison | Candidate statistic | Average Improvement | p95 Improvement | p99 Improvement | Gate |
| --- | --- | --- | ---: | ---: | ---: | --- |
| Vulkan | Candidate vs previous main | Median of two candidate runs | +0.028% | -0.180% | -0.332% | PASS |
| Vulkan | Candidate vs fixed published baseline | Median of two candidate runs | -0.000% | -1.344% | -1.089% | PASS |
| OpenGL | Candidate vs fixed published baseline | One renderer-control run | +0.028% | +0.831% | +3.941% | PASS |

The first Vulkan candidate p99 was 35.339 ms and exceeded 2% against the
historical baseline. The repeat was 34.406 ms. The two-run median passes both
the previous-main and fixed-baseline gates, so the isolated spike is retained
as run variance and is not described as an improvement.

### PGR2 snapshot and host-drift control

| Renderer | Comparison | Average Improvement | p95 Improvement | p99 Improvement | Gate |
| --- | --- | ---: | ---: | ---: | --- |
| Vulkan | Candidate r2 vs same-session immutable baseline | -0.229% | -0.879% | +0.441% | PASS |
| OpenGL | Candidate r2 vs same-session immutable baseline | +0.009% | -0.548% | +1.912% | PASS |
| OpenGL | Candidate median vs previous-main median | -1.033% | -1.252% | -0.922% | PASS |

The historical snapshot comparison alone was not accepted because its tails
moved beyond 2%. Running the exact immutable baseline executable in the same
session reproduced the shift:

| Renderer | Same baseline binary vs its published result | Average Improvement | p95 Improvement | p99 Improvement |
| --- | --- | ---: | ---: | ---: |
| Vulkan | Current host-control run | -1.314% | -2.107% | -1.899% |
| OpenGL | Current host-control run | -0.942% | -0.983% | -3.741% |

The candidate then matched the same-session baseline within 0.88% on Vulkan and
1.92% on OpenGL. Previous main also moved substantially between adjacent
OpenGL runs, and the Vulkan previous-main run was slower than PR #11. This
isolates the large tail movement to Windows host/session variance rather than
PR #11. PR #11 is therefore recorded as performance-neutral; no speedup claim
is made from these retail cells.

### Morrowind snapshot

| Renderer | Comparison | Cadence Improvement | p95 Improvement | p99 Improvement | Gate |
| --- | --- | ---: | ---: | ---: | --- |
| Vulkan | Candidate vs previous main | -0.256% | -1.061% | -1.633% | PASS |
| Vulkan | Candidate vs fixed published baseline | +1.688% | -0.252% | +5.548% | PASS |
| OpenGL | Candidate vs previous main | +1.049% | +1.592% | -1.039% | PASS |
| OpenGL | Candidate vs fixed published baseline | +4.405% | +5.247% | +4.194% | PASS |

The focused runner activated the owned xemu window before Start and B. All four
candidate/parent measurement captures show the expected outdoor scene and
crosshair with no pause, reconnect, or menu overlay. Every private HDD was
deleted and no xemu, PresentMon, or WPR process remained.

Compact per-metric rows are in `retail-results.csv`; exact runner, game, seed,
configuration, and helper identities are in `retail-manifest.json`. Raw PGR2
ETLs remain on the test host at the run paths recorded in `retail-summary.json`.

## Validation status

| Gate | OpenGL | Vulkan |
| --- | --- | --- |
| Exact-head build and focused units | N/A — Vulkan implementation | PASS — 17/17 units |
| Native injected failure paths | N/A — diagnostic paths are Vulkan-only | PASS — 5/5 expected outcomes, 0 VUIDs |
| Targeted ordinary correctness | PASS — 5/5 | PASS — 5/5, 0 VUIDs |
| Matched normal-path performance | N/A — focused changed paths are Vulkan-only | PASS — surface and direct code-isolation gates within 2% |
| Representative/partial XISO | Not run — focused matrix is the first gate | Not run — focused matrix is the first gate |
| Morrowind snapshot | PASS — active-scene control; all metrics within 2% vs previous main | PASS — active-scene control; all metrics within 2% vs previous main |
| PGR2 fresh-start | PASS — renderer control vs fixed baseline | PASS — two-run median within 2% vs previous main and fixed baseline |
| PGR2 snapshot | PASS — same-session baseline and ABBA controls within 2% | PASS — same-session baseline control within 2% |
| Full XISO | 156/156 collected; 155 PASS + known #60 | 156/156 collected; 155 PASS + known #60; 0 VUIDs |
| Final visual validation | PASS — full-suite frame/hash oracles | PASS — full-suite frame/hash oracles |

## Complete XISO qualification

| Renderer | Records | PASS | Known failure | Functional hashes | Vulkan validation |
| --- | ---: | ---: | --- | --- | --- |
| OpenGL | 156 | 155 | `report_query.dma_range_guard` (#60) | PASS | N/A |
| Vulkan | 156 | 155 | `report_query.dma_range_guard` (#60) | PASS | active, 0 VUIDs |

The first complete run exposed and then drove a fix for PR #19 order contamination. The corrected XISO resets canonical texture backing before each leaf, outside measurement. The known report-DMA failure matches retained baseline evidence and is not caused by PR #11.

## Decision

**Qualified for integration.** The exact final head passes its build, units, production-path failure injection, focused correctness, direct performance isolation, PGR2 and Morrowind retail qualification, surface performance, and complete-suite gates. Retail results are performance-neutral within the 2% gate after identical-binary controls attributed the larger tail swings to the Windows host/session. PR #6 coverage is absorbed without transplanting its historical branch.
