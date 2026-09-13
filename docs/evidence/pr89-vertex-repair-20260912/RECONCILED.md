> **Source-equivalent current heads:** #87 `1d4524a6df` has the same Git tree as tested `b3b99fb`; #89 `cbb3b4372f` has the same Git tree as tested `150d74a`. A guarded idle-bitmap-clear experiment was [tested and reverted](IDLE-CLEAR.md). The exact tested executable hashes below remain the comparison artifacts; the adverse PGR2 tail is unresolved.

# Reconciled #85 → #87 → #89 stack: exact-head qualification

**Status: draft; no merge verdict yet.** The corrected stack preserves the
prior branch history through merge commits. The cache-only #85 experiment was
reverted; [its build and mixed PGR2 result](CACHE-EXPERIMENT.md) remain in the
evidence. The current #85 repair removes the redundant surface-overlap scan
and clean-overlap vertex-mirror uploads. #89 still receives an overlap signal
from the same traversal, so versioning remains disabled for surface aliases.

| Role | Exact source / tree | Win64 executable SHA-256 | Build |
| --- | --- | --- | --- |
| Current `main` control | `9148241de690617ac0a21a26b41858585c1e3cab` / `2301f1cc976f93e5a943e065c4e12e034f33869f` | `6857240d6e95909d591832685c60e376611924d00a9688da4d7d2b89e84c17f6` | Retained tested tree |
| #85 | `0883fb63009c6cc804681cbdb39e4454b44d8456` / `8849f205571ef98454f7de7c9eaa098b1fdcfbb6` | `e9d763da0e027f9cc21b66c090e7e9199c10bd3846a49c89277c2a07bf34b17b` | PASS |
| #87 | `b3b99fb8832b658a653d53641170da3171ab2e6c` / `87118ebf6d911b9a8b12bf21caf7ac9278cf9cee` | `54b879eb2602c57504e97f2899ee73b91aa22debca4373465896a40b6d8a57e2` | PASS |
| #89 | `150d74ac5525be769e4f44ab35718eb2607a8eec` / `66a6febaf0ac60ea1749e674bace393447fe849a` | `29eac8120cce296e312ba85147109ca5d6b62755d6326d36d4c0358a44231d25` | PASS |

The candidate builds used the same pinned Win64 GCC toolchain image
`sha256:09fdc183a88b493bf3a98d0d00b03aca4d5a23e60cc08228d7752d3c3295e8b2`
with `-O2`, full LTO, x86-64-v3, debug information, and assertions. Each
source was clean at its recorded commit. All regular tracked files were
hash-checked before and after linking (11,404 files for #85/#87; 11,406 for
#89), and changed Vulkan objects were rebuilt. Symlink identities were
inherited from the prior exact checkout; the added/repaired paths are regular
files. The test runner's optional manifest/PDB ownership flag is separate
from this independent full regular-file check and was not requested for these
captures.

The #85 fetch-span unit passed 2/2 on Win64. The reconciled #87 fetch-span
unit passed 2/2. Reconciled #89 passed fetch-span 2/2 and version-policy 3/3.
These are policy/bounds checks, not substitutes for the complete guest suite.

## Complete 161-record XISO

All six exact candidate/renderer cells used the same image
`e9b7996a2521a1b35c36fae074027240944dcc4d8625c131ee3d05d8367cb430`
and catalog `6bd53cf672ba80051dfb677f187da76e362a399412b1acd005c920829a7bbdd5`.
The main controls are retained from the same runner/image revision. The
[per-test comparator](compare_xiso_reconciled.py), [322-row table](results/reconciled-comparison.csv),
[summary](results/reconciled-comparison-summary.json), and each normalized
record set make outcome, hash, and time comparisons reproducible.

| Renderer | Main / #85 / #87 / #89 passes | Unexpected outcome or eligible hash changes | #85 vs main median timed Improvement | #87 vs #85 | #89 vs #87 | #89 vs main |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Vulkan | 160 / 160 / 160 / 160 | 0 | -0.36% | +0.19% | -0.79% | -1.00% |
| OpenGL | 159 / 159 / 159 / 159 | 0 | +0.32% | +0.10% | -0.52% | -0.29% |

Vulkan reported zero VUIDs on all three candidate heads. The inherited
`report_query.dma_range_guard` failed on both renderers; OpenGL also retained
`texture_cubemap_fallback.unbordered_subblock_dxt1`. No new XISO outcome or
eligible framebuffer hash changed at either stacked step. Positive
**Improvement %** means a lower duration. The table's median timed-leaf
figures come from one non-interleaved suite pass per candidate head and are
**directional observations**, not performance acceptance.

The directly relevant `vertex_buffer_allocation.ordered_same_page_overwrite`
leaf measured 5.135 ms on #87 and 15.624 ms on #89 in those single passes
(-204.26% Improvement). Its output and hash matched. A [focused ABBA control](results/reconciled-ordered-same-page.json)
repeated that exact test with both one and five guest iterations per cell:

| Guest iterations/cell | #87 first / #89 first | #89 second / #87 second | Paired Improvement % |
| --- | ---: | ---: | ---: |
| 1 | 15.993 / 16.598 ms | 16.546 / 17.402 ms | -3.78% / +4.92% |
| 5 | 16.400 / 16.427 ms | 16.474 / 16.535 ms | -0.16% / +0.37% |

All eight focused cells passed the same framebuffer hash with zero VUIDs.
The 5.135 ms #87 full-suite observation did not repeat, and the one-iteration
paired direction reverses. This **does not establish a #89 timing regression**
on that leaf. It also does not establish a measurable improvement there.

## #85 versus current main: PGR2 snapshot

The [four complete cells](results/pr85-direct-pgr2-abba.json) used the same
PGR2 Vulkan snapshot, clean seed, configuration hash, scale 1, 30-second
warmup, and 60-second measured window without WPR or telemetry. All reported
complete functional and measurement status, zero focus loss, zero unresponsive
samples, and zero guest-frame stalls. Positive **Improvement %** means a lower
guest-frame interval.

| Run order | Main mean / p95 / p99 | #85 mean / p95 / p99 | Mean / p95 / p99 Improvement |
| --- | ---: | ---: | ---: |
| Main → #85 | 33.750 / 38.289 / 43.300 ms | 33.721 / 38.691 / 43.100 ms | +0.08% / **-1.05%** / +0.46% |
| #85 → main | 33.764 / 38.751 / 42.858 ms | 33.825 / 38.819 / 42.944 ms | -0.18% / **-0.18%** / -0.20% |

The prior #85 head was worse than main by -2.40% and -1.22% at p95, and
-2.49% and -1.25% at p99 in opposite orders. The direct repair removes most
of that repeated adverse signal, but its new p95 remains slightly adverse in
both orders. This is **near-neutral**, not a proven standalone performance
improvement or a merge pass. PGR2 full start, Morrowind, the focused XISO
timing control, and the combined #89 comparison remain necessary for the
final verdict.

## PGR2 full start

The [four exact-head cells](results/reconciled-pgr2-full.json) used the same
fresh-boot seed, config, race-start path, 30-second warmup, and 120-second
measurement without tracing. All completed functional and measurement checks
with 3,601–3,603 guest frames. The game stayed at its 30-frame cap, so the
small interval changes below do not establish a throughput gain or regression.

| Step | Reference p95 / p99 | Candidate p95 / p99 | p95 / p99 Improvement |
| --- | ---: | ---: | ---: |
| Main → #85 | 33.525 / 33.904 ms | 33.646 / 33.869 ms | -0.36% / +0.10% |
| #85 → #87 | 33.646 / 33.869 ms | 33.628 / 34.061 ms | +0.05% / -0.57% |
| #87 → #89 | 33.628 / 34.061 ms | 33.669 / 33.855 ms | -0.12% / +0.61% |
| Main → #89 | 33.525 / 33.904 ms | 33.669 / 33.855 ms | -0.43% / +0.14% |

## Morrowind fixed-scene snapshot: #89 versus #87

The [four exact-head cells](results/reconciled-morrowind-87-89.json) used the
same Vulkan snapshot, seed, Start/B input sequence, and 60-second measurement.
All passed scene validation and deleted their private HDD copies. Guest
display-write cadence is a guest-progression proxy, not displayed FPS.

| Run order | #87 / #89 writes per second | Cadence Improvement | #87 / #89 p95 | p95 Improvement | #87 / #89 p99 | p99 Improvement |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| #87 → #89 | 25.028 / 26.320 | **+5.16%** | 45.886 / 44.871 ms | **+2.21%** | 53.045 / 50.440 ms | **+4.91%** |
| #89 → #87 | 25.151 / 26.360 | **+4.81%** | 46.213 / 44.050 ms | **+4.68%** | 53.557 / 51.108 ms | **+4.57%** |

This is a repeatable positive result for the fixed scene on the current
reconciled heads. The end-image hashes differ as guest progression differs;
all end images passed the runner's scene checks, while XISO supplies the
matching-pixel oracles. A controlled map traversal has not been captured, so
these figures should not be described as a whole-game FPS gain.

## PGR2 Vulkan snapshot: #89 versus #87

The [four exact-head cells](results/reconciled-pgr2-snapshot-87-89.json) used
the same snapshot, B-3 input, and 30-second warmup/60-second measurement.
All completed functionally. Telemetry and ETW were off for timing.

| Run order | #87 / #89 mean | Mean Improvement | #87 / #89 p95 | p95 Improvement | #87 / #89 p99 | p99 Improvement |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| #87 → #89 | 33.819 / 34.027 ms | **-0.61%** | 38.916 / 39.877 ms | **-2.47%** | 42.386 / 44.536 ms | **-5.07%** |
| #89 → #87 | 33.807 / 33.841 ms | **-0.10%** | 38.968 / 39.391 ms | **-1.09%** | 42.388 / 43.513 ms | **-2.65%** |

The adverse p95/p99 directions repeat in opposite run orders, while the
maximum changes direction. This is a merge blocker pending attribution and a
repair. The PGR2 full-start 30-frame cap does not resolve snapshot tails.
The runner marked `source_ownership_valid=false` because these calls did not
pass an external build manifest or PDB; they did verify the executable hash
before each launch. The exact-source build audit separately attests source,
link, and executable identities. This is not evidence of a wrong executable.

## PGR2 path attribution

A [matched opt-in diagnostic pair](results/diagnostic-pgr2-version-path.json)
recorded **zero vertex-version draws or selected ranges on both #87 and #89**
for this PGR2 snapshot, and zero vertex-staging copies. The new version-copy
path therefore was not exercised in the scene with the adverse p99 result.
The diagnostic `draw_flush` CPU total was about 20.18 ms/frame on #87 and
19.71 ms/frame on #89; this does not support a simple claim that #89 spent
more total CPU in that measured region. Instrumented timings are excluded
from performance acceptance. The adverse uninstrumented p99 remains an
unresolved qualification signal, not a demonstrated version-copy cost.

## Current-head three-generation version-path oracle

The [focused XISO result](results/reconciled-three-generation.json) passed on
#89 `150d74ac55` with the same framebuffer oracle, zero Vulkan VUIDs, and
**1,028 version selections/draws** recorded by opt-in telemetry. It exercised
three overwritten generations after a staging rollover. This is diagnostic
correctness evidence; its instrumented duration is excluded from performance
comparisons. It does not directly force a finish between selection and copy or
prove GPU-surface readback into vertex memory.

## Pending exact-head gates

| Gate | Current state |
| --- | --- |
| 161-record XISO on #85/#87/#89, Vulkan and OpenGL | Complete; identical eligible outcomes/hashes; the relevant timing outlier was not reproduced in ABBA controls |
| #89 three-generation guest oracle and version-selection observation | Complete on current head; 1,028 selections, matching output, zero VUIDs |
| PGR2 full start/snapshot and Morrowind snapshot at #87 → #89 | Full start cap-neutral; fixed Morrowind scene positive; PGR2 snapshot adverse in two orders; traversal pending |
| Direct #85 GPU-surface-to-vertex and #89 finish/rollover/stale-fallback tests | Pending focused guest proof |
| Cross-platform build/review | Pending |

The [previous stack report](REPORT.md) retains its historical measurements
and per-test rows. No code has been merged into `main` on the basis of this
new record.
