# PR71 revised head: complete latest XISO

The maintained image is from perf-tests main `0bb7618aec5ea73355a03bcb176a922ea8b3ec2e`, ISO SHA-256 `a8f07817b9f1b22ef93ea54497ddfc9f06d34147d734e4ed26a8bcb69c7e8687`. Product PR head is `d21072b3` (test-only follow-up to runtime commit `28290977`); the tested Windows runtime executable SHA-256 is `e161c4cfe6b7b6af9d91fc7f28afde52efa43e6d899db24f1b0d2a2324e0d2c5`. Fixed baseline and previous-main binaries are unchanged from r1. Retail timing is still running; XISO output alone is not a game frame-pacing claim.

The campaign passed **9 full-suite cells** and recorded **10 isolated fixed-baseline gated controls**. The fixed baseline registers 152 records; previous main and revised candidate register the full 157. Candidate and previous-main functional hashes match. Inherited nonpasses are explicitly shown below.

| Full-suite cell | Records | Hash validation | Nonpasses | Vulkan VUIDs |
| --- | ---: | --- | --- | ---: |
| `01-baseline-opengl` | 152 | PASSED | report_query.dma_range_guard | 0 |
| `02-candidate-opengl` | 157 | PASSED | texture_cubemap_fallback.unbordered_subblock_dxt1, report_query.dma_range_guard | 0 |
| `03-previous-opengl` | 157 | PASSED | texture_cubemap_fallback.unbordered_subblock_dxt1, report_query.dma_range_guard | 0 |
| `04-previous-vulkan` | 157 | PASSED | report_query.dma_range_guard | 0 |
| `05-candidate-vulkan-off-cold` | 157 | PASSED | report_query.dma_range_guard | 0 |
| `06-candidate-vulkan-off-warm` | 157 | PASSED | report_query.dma_range_guard | 0 |
| `07-candidate-vulkan-on-cold` | 157 | PASSED | report_query.dma_range_guard | 0 |
| `08-candidate-vulkan-on-warm` | 157 | PASSED | report_query.dma_range_guard | 0 |
| `09-baseline-vulkan` | 152 | PASSED | report_query.dma_range_guard | 0 |

| Candidate Vulkan cache | Cold hits/misses | Warm hits/misses |
| --- | ---: | ---: |
| Hybrid Off | 10 / 61 | 71 / 0 |
| Hybrid On | 10 / 64 | 74 / 0 |

The 10 gated controls were captured separately because the older fixed baseline does not register all newer records; their statuses and individual identifiers are retained in [full-xiso.json](full-xiso.json). This report contains selected public result fields only; private game paths and raw run logs remain on the test host.
