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
timing. Their values are not used as matched controls here. The existing
baseline executable is scheduled for new same-settings captures after the
main/PR bracket.

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
they should not be read as qualified speed comparisons. Vulkan validation was
not enabled in this timing run, so zero reported VUIDs would have no meaning.

## Retail frame pacing

The PGR2 snapshot bracket is complete in this order: main, #104, #105,
#105, #104, main. Each cell uses a 30-second warmup and a 60-second measured
window. The values below are the mean of two per-run FPS or interval values;
the individual cells are in [retail-per-run.csv](retail-per-run.csv).

| PGR2 snapshot | Raw + | Main | PR #104 | Improvement vs main | PR #105 | Improvement vs main | Improvement vs #104 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| FPS | `+good` | 29.412 | 29.665 | +0.86% | 29.589 | +0.60% | -0.26% |
| Mean interval, ms | `+bad` | 33.994 | 33.703 | +0.85% | 33.780 | +0.63% | -0.23% |
| p95, ms | `+bad` | 39.255 | 38.721 | +1.36% | 39.028 | +0.58% | -0.79% |
| p99, ms | `+bad` | 43.558 | 42.184 | +3.15% | 43.073 | +1.11% | **-2.11%** |

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

PGR2 full-start and Morrowind snapshot comparisons are pending. The first
full-start main control was spotchecked during its measured window and then
interrupted, so it is excluded. A separate short main preflight exited with
`VK_ERROR_DEVICE_LOST`; a 20-second exact PR #105 preflight completed. Neither
is treated as a matched performance cell. FPS and frame intervals come from
guest frame and flip logs; PresentMon is host presentation context only.

## Disposition

Pending the remaining paired retail measurements, same-settings baseline
controls, and classification of the XISO query failures. The earlier RTX 3090
played-race survival result applies to a
different diagnostic executable. A clean build and hash match on this host do
not establish that the 3090 device loss is fixed.
