# PR70 current-main qualification

PR70 head `982a6cd5eeec0ec82a2f9b18298b1cb5a0d82830` passes the
incremental performance gate against previous main.  The complete campaign
passes functional, cache-reuse, lifecycle, and cleanup admission.  The wider
optimization cycle remains on hold because one Morrowind warm p99 comparison
is still 2.256% behind the older fixed baseline.

This distinction matters: previous main was already 5.019% behind the fixed
baseline for the same Morrowind p99 metric.  PR70 improves that metric by
2.631% against previous main and recovers more than half of the existing gap.

All percentages are **Improvement %**.  Positive values are favorable and
negative values are adverse.

## Source and build identities

| Role | Logical commit | Compiled source | Tree | Executable SHA-256 |
| --- | --- | --- | --- | --- |
| Fixed baseline | `9f618d6d8c4c446ef023955f3d4de22f661f61a4` | `c17591d59c270b352b72e648f5ed65e4b2a3e77e` | `6824a5aa4d9ca288ac96092dc9244684e995b08d` | `3489fdcc593e942b92a612bf35a98f509ff0907e3370e1e5f45f2972d83fb16b` |
| Previous main | `42490a530168e5a12976cd7840b13bb1a6798f25` | `37cf6cbcc61392aaba14658df6ed8aa4cb566abd` | `53c6683cb85401c680a6ba27402714a45733a4e5` | `af22a8f75811a4c7b9f46de673d9f5ae8e8d0c77e06a3c9ffe9e15736cc2a4d2` |
| PR70 | `982a6cd5eeec0ec82a2f9b18298b1cb5a0d82830` | same | `2c2b03d39bae4e7b4f01bbf5d08f3b6c7c5640fc` | `5c27d5310add91901f5a132c38d250492abf3d5eed253c2e6fe8cf63fb764768` |

The Windows candidate was built with optimization, full LTO, and x86-64-v3.
The fixed baseline executable was reused rather than rebuilt.  The previous
main executable was built from a source commit with the exact previous-main
runtime tree.

The maintained XISO came from xemu-perf-tests
`61012b4e702fbb46a02d813e71f2159a109a1c29`; image SHA-256
`6b2161f1b4abab94648f3fa0ca8da893092bab1b63d7e139a2358eb0319d05ac`.
The catalog contains 157 records: 152 normal leaves and five explicitly gated
leaves.

## Performance result

The table reports candidate medians.  Vulkan has two baseline runs, two
previous-main runs, two cold candidate runs, and three warm candidate runs per
retail workload.

| Workload | Candidate | Metric | Candidate | Improvement vs baseline | Improvement vs previous main |
| --- | --- | --- | ---: | ---: | ---: |
| PGR2 snapshot | Warm | Mean interval | 33.992 ms | +0.924% | -0.339% |
| PGR2 snapshot | Warm | p95 | 39.714 ms | +2.649% | -0.780% |
| PGR2 snapshot | Warm | p99 | 43.144 ms | +3.902% | +1.579% |
| PGR2 snapshot | Warm | Maximum | 52.959 ms | +18.638% | +15.183% |
| PGR2 full start | Warm | Mean interval | 33.333 ms | 0.000% | 0.000% |
| PGR2 full start | Warm | p95 | 33.656 ms | -0.520% | -0.009% |
| PGR2 full start | Warm | p99 | 34.028 ms | +0.655% | -0.324% |
| PGR2 full start | Warm | Maximum | 36.324 ms | +15.631% | +1.895% |
| Morrowind snapshot | Warm | Mean interval | 41.479 ms | -1.407% | +1.259% |
| Morrowind snapshot | Warm | p95 | 48.256 ms | -1.778% | +0.834% |
| Morrowind snapshot | Warm | p99 | 53.963 ms | **-2.256%** | **+2.631%** |
| Morrowind snapshot | Warm | Maximum | 61.636 ms | -1.575% | +3.658% |

No Vulkan metric regressed more than 2% against previous main.  There were no
75 ms guest-frame stalls in any admitted retail cell.  The exact per-cell
results and every cold comparison are in
[the full Improvement table](tables/improvement-comparisons.md).

The OpenGL controls exercise a path PR70 does not modify.  Single OpenGL cells
showed variable maximums, including adverse snapshot maximums; these are
retained in [the cell table](tables/retail-cells.md) and are not used to claim
a Vulkan cache regression or improvement.

## Cache benefit

| Workload | Cold observations | Warm observations | Result |
| --- | --- | --- | --- |
| Full XISO | 10 hits / 61 misses | 71 hits / 0 misses | All known shaders reused |
| PGR2 snapshot, each pair | 20 hits / 121 misses | 141 hits / 0 misses | All known shaders reused |
| PGR2 full start, each pair | 143 hits / 198 misses | 341 hits / 0 misses | All known shaders reused |
| Morrowind pair 1 | 1 hit / 47 misses | 48 hits / 1 newly reached source; reload 49 / 0 | Known shaders reused; new source persisted |
| Morrowind pair 2 | 1 hit / 45 misses | 46 hits / 3 newly reached sources | Known shaders reused; new sources persisted |

Across the nine warm retail cells, PR70 served 1,589 cached artifacts with four
new-source misses.  Including the warm XISO cell gives 1,660 hits and four
misses.  Every cell reported zero cache rejections and zero fallbacks.  The
Morrowind misses are kept as results: repeat guest execution can reach a shader
that its cold seed did not, and the enlarged cache was published for later use.

The cache removes synchronous glslang work for each hit.  It does not remove
GLSL generation, reflection, `VkShaderModule` construction, or graphics
pipeline creation, so a hit is not presented as elimination of the complete
draw-path stall.

## Functional and lifecycle result

| Gate | Result |
| --- | --- |
| Full maintained XISO | PASS on all seven normal cells; 17 total cells including isolated baseline controls |
| Candidate Vulkan validation | Active, zero reported VUIDs |
| Functional-hash admission | PASS in all normal XISO cells |
| PGR2 snapshot | 12/12 cells admitted |
| PGR2 full start | 12/12 cells admitted |
| Morrowind snapshot | 12/12 cells admitted |
| GPU policy | NVIDIA selected automatically in every Vulkan and OpenGL cell |
| Normal close/private HDD cleanup | PASS in every retail cell |
| Final emulator/trace cleanup | PASS; no process remained |
| Incremental PR70 gate | **PASS** |
| Cumulative cycle gate vs fixed baseline | **HOLD** on Morrowind warm p99 only |

The fixed baseline predates three PFIFO oversized-packet controls and the GL
small compressed-cubemap repair.  Those five leaves were run separately so the
baseline assertions could not abort the other 152 records.  The three PFIFO
controls produced their expected old-code aborts; the incrementing fallback
passed; the GL cubemap control retained its known old-code failure while its
Vulkan control passed.  Previous main and PR70 ran the complete 157-record
suite normally.  The remaining `report_query.dma_range_guard` and candidate/
previous-main GL cubemap non-passes are shared tree state, not PR70 deltas.

## Admission correction

The first Morrowind warm capture completed successfully but the original
controller required zero warm misses.  Its log showed 48 cache hits, one new
shader, zero rejections/fallbacks, a loaded cache, and successful republication.
The admission rule was corrected to require demonstrated reuse and clean
fallback behavior while retaining new misses in the record.  That completed
capture was admitted without rerunning it.  Only the six unfinished Morrowind
cells were then executed.  Original and resume script hashes are both recorded
in [the campaign manifest](campaign-manifest.json).

## Evidence

- [Qualification summary](qualification-summary.json)
- [Campaign manifest](campaign-manifest.json)
- [Sanitized retail cells](retail-cells.json)
- [Sanitized XISO cells](full-xiso-cells.json)
- [All retail metrics](tables/retail-cells.md)
- [Improvement comparisons](tables/improvement-comparisons.md)
- [Cache records](tables/cache-proof.md)
- [Full XISO disposition](tables/full-xiso.md)
- [Exact maintained-suite runner adaptation](tooling/run-suite-pr70.py)

Raw game images, writable disks, screenshots, and private host paths are not
published.  The sanitized records retain source/build identities, per-cell
metrics, shader-cache counters, adapter selection, functional outcomes, and
cleanup status.
